# app.py
import streamlit as st
import yaml
import os
import pandas as pd
from datetime import datetime
from utils import load_config
from main_streamlit import streaming_run_analysis

# ======================
# 页面初始化
# ======================

# 加载默认配置
DEFAULT_CONFIG = load_config("config.yaml")

st.set_page_config(
    page_title="arXiv Insight",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 arXiv 预印本智能分析系统")
st.markdown("输入关键词，自动获取最新论文并由 LLM 评分、提取亮点")

# 初始化 session state
if "show_all_papers" not in st.session_state:
    st.session_state.show_all_papers = False
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# ======================
# 侧边栏：配置参数
# ======================

with st.sidebar:
    st.header("⚙️ 配置参数")

    # 查询参数
    default_keywords = ", ".join(DEFAULT_CONFIG.get("query", {}).get("keywords", ["large language models"]))
    keywords = st.text_input("关键词（英文，逗号分隔）", value=default_keywords)

    default_cats = DEFAULT_CONFIG.get("query", {}).get("categories", ["cs.CL", "cs.AI"])
    categories = st.multiselect(
        "学科分类",
        options=["cs.CL", "cs.AI", "cs.LG", "cs.CV", "stat.ML", "physics.comp-ph"],
        default=default_cats
    )

    default_days = DEFAULT_CONFIG.get("query", {}).get("time_window_days", 7)
    days = st.slider("时间窗口（天）", 1, 30, default_days)

    default_topk = DEFAULT_CONFIG.get("query", {}).get("top_k", 5)
    top_k = st.slider("返回篇数（Top K）", 1, 20, default_topk)

    # 作者信息
    author_cfg = DEFAULT_CONFIG.get("features", {}).get("author_info", {})
    use_author_info = st.checkbox(
        "启用作者信息（Semantic Scholar / OpenAlex）",
        value=author_cfg.get("enabled", False)
    )
    
    default_sources = author_cfg.get("sources", ["semantic_scholar", "openalex"])
    author_sources = []
    if use_author_info:
        author_sources = st.multiselect(
            "作者数据源（按优先级排序）",
            options=["semantic_scholar", "openalex"],
            default=[s for s in default_sources if s in ["semantic_scholar", "openalex"]]
        )

    # 解析器
    parser_cfg = DEFAULT_CONFIG.get("parser", {})
    use_grobid = parser_cfg.get("use_grobid", False)
    grobid_url = parser_cfg.get("grobid_url", "http://localhost:8070")
    use_grobid = st.checkbox("使用 Grobid 解析 PDF", value=use_grobid)

    # LLM 设置
    llm_cfg = DEFAULT_CONFIG.get("llm", {})
    default_provider = llm_cfg.get("provider", "qwen")
    
    # 提供商选择
    provider_options = ["qwen", "kimi", "deepseek"]
    provider_index = provider_options.index(default_provider) if default_provider in provider_options else 0
    llm_provider = st.selectbox("模型提供商", provider_options, index=provider_index)
    
    # 根据提供商显示不同的模型选项和 API Key 输入
    if llm_provider == "qwen":
        default_model = llm_cfg.get("model", "qwen-plus")
        model_options = ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-longcontext"]
        model_index = model_options.index(default_model) if default_model in model_options else 1
        llm_model = st.selectbox("模型", model_options, index=model_index)
        api_key = st.text_input("DashScope API Key", type="password", value=llm_cfg.get("api_key", ""))
    elif llm_provider == "kimi":
        default_model = llm_cfg.get("model", "moonshot-v1-8k")
        model_options = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
        model_index = model_options.index(default_model) if default_model in model_options else 0
        llm_model = st.selectbox("模型", model_options, index=model_index)
        api_key = st.text_input("Kimi API Key", type="password", value=llm_cfg.get("api_key", ""))
    else:  # deepseek
        default_model = llm_cfg.get("model", "deepseek-chat")
        model_options = ["deepseek-chat", "deepseek-coder"]
        model_index = model_options.index(default_model) if default_model in model_options else 0
        llm_model = st.selectbox("模型", model_options, index=model_index)
        api_key = st.text_input("DeepSeek API Key", type="password", value=llm_cfg.get("api_key", ""))

    output_cfg = DEFAULT_CONFIG.get("output", {})
    report_path = output_cfg.get("report_path", "export/report.md")
    csv_path = output_cfg.get("csv_path", "export/report.csv")
    json_path = output_cfg.get("json_path", "export/report.json")

    run_btn = st.button("🚀 开始分析", type="primary")

# ======================
# 主逻辑：流式分析 + 动态更新
# ======================

if run_btn:
    # 验证 API Key
    if not api_key.strip():
        provider_names = {
            "qwen": "DashScope",
            "kimi": "Kimi",
            "deepseek": "DeepSeek"
        }
        provider_name = provider_names.get(llm_provider, "API")
        st.error(f"请填写 {provider_name} API Key")
    else:
        # 构建最终配置
        config = {
            "query": {
                "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
                "categories": categories,
                "time_window_days": days,
                "top_k": top_k
            },
            "llm": {
                "provider": llm_provider,
                "model": llm_model,
                "api_key": api_key
            },
            "parser": {
                "use_grobid": use_grobid,
                "grobid_url": grobid_url
            },
            "output": {
                "report_path": report_path,
                "csv_path": csv_path,
                "json_path": json_path
            },
            "features": {
                "author_info": {
                    "enabled": use_author_info,
                    "sources": author_sources if use_author_info else []
                }
            }
        }

        # 创建容器
        status_container = st.empty()
        results_container = st.empty()
        download_container = st.empty()
        progress_bar = st.progress(0)

        all_results = []

        # 流式分析过程
        with st.spinner("正在分析论文..."):
            try:
                for partial_results, total_papers in streaming_run_analysis(config):
                    all_results = partial_results
                    analyzed = len(partial_results)

                    if total_papers > 0:
                        if analyzed == total_papers:
                            # 分析完成
                            status_container.success(f"✅ 分析完成！共处理 {total_papers} 篇论文")
                        else:
                            # 显示带进度条的状态
                            progress = min(analyzed / total_papers, 1.0)
                            with status_container.container():
                                st.markdown(
                                    f"""
                                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px; background-color: #1e3a8a; color: white; border-radius: 6px; margin-bottom: 10px;">
                                        <span style="font-size: 14px; font-weight: normal;">
                                            ⏳ 已分析 <strong>{analyzed}</strong> / <strong>{total_papers}</strong> 篇论文，...
                                        </span>
                                        <div style="width: 200px; height: 10px; background-color: #d1d5da; border-radius: 5px; overflow: hidden;">
                                            <div style="width: {int(progress * 100)}%; height: 100%; background-color: #3b82f6; transition: width 0.3s;"></div>
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                    else:
                        progress_bar.empty()
                        status_container.info("没有找到论文")

                    # === 流式阶段：仅显示 Top K 标题（不展开）===
                    display_papers = sorted(
                        partial_results,
                        key=lambda x: x.get("final_score", 0),
                        reverse=True
                    )[:top_k]

                    results_container.empty()
                    with results_container.container():
                        for i, paper in enumerate(display_papers):
                            st.markdown(
                                f"### {i+1}. [{paper['title']}](https://arxiv.org/abs/{paper['id']})"
                            )
                            # 🔧 修复：f-string 中不能直接用双引号，改用单引号或转义
                            st.caption(
                                f"发表时间: {paper['published'][:10]} | "
                                f"分数: {paper.get('final_score', 0):.2f}"
                            )

            except Exception as e:
                status_container.error(f"分析出错: {str(e)}")
                st.exception(e)
                raise

        # 保存结果到 session state
        if all_results:
            st.session_state.analysis_results = all_results

        results_container.empty()


# ======================
# 渲染最终结果（无论是否刚运行）
# ======================

if st.session_state.analysis_results is not None:
    all_results = st.session_state.analysis_results
    sorted_papers = sorted(all_results, key=lambda x: x.get("final_score", 0), reverse=True)

    # 决定显示范围
    if st.session_state.show_all_papers:
        papers_to_display = sorted_papers
        btn_label = "⬆️ 收起（仅显示 Top 5）"
    else:
        papers_to_display = sorted_papers[:top_k]
        btn_label = f"🔍 显示全部 {len(sorted_papers)} 篇论文"

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button(btn_label, key="toggle_show_all_final"):
            st.session_state.show_all_papers = not st.session_state.show_all_papers
            st.rerun()

    # 渲染最终论文（使用零宽空格确保 expander 唯一）
    for i, paper in enumerate(papers_to_display):
        rank = i + 1
        # \u200b 是零宽空格，用户看不见，但使标题唯一
        unique_title = f"{rank}. {paper['title']}\u200b(arXiv:{paper['id']})"
        with st.expander(unique_title, expanded=(i == 0 and not st.session_state.show_all_papers)):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**发表时间**: {paper['published'][:10]}")
                st.markdown(f"**分数**: `{paper.get('final_score', 0)}` (基础: `{paper.get('total_score', 0)}`, 亮点: `{paper.get('insight_bonus', 0)}`)")
                st.markdown(f"**语言**: {'中文' if paper.get('language') == 'zh' else 'English'}")
                st.markdown(f"[查看全文](https://arxiv.org/abs/{paper['id']}) | [PDF](https://arxiv.org/pdf/{paper['id']})")

                if paper.get("authors_info"):
                    st.markdown("**作者信息**:")
                    for author in paper["authors_info"]:
                        name = author.get("name", "N/A")
                        hindex = author.get("h_index", "N/A")
                        org = author.get("affiliations", ["N/A"])[0] if author.get("affiliations") else "N/A"
                        source = author.get("source_used", "")
                        st.caption(f"- {name} | H-index: {hindex} | {org} ({source})")

                st.markdown("**摘要**:")
                st.write(paper["abstract"])
                st.markdown("**💡 亮点**:")
                st.write(paper["breakthrough"])
                st.markdown("### 🌐 译文（Abstract Translation）")
                st.text(paper.get("translation", "暂无译文"))
                st.markdown("### 🧠 脑图（Mind Map）")
                st.markdown(paper.get("mindmap_markdown", "暂无脑图"))

            with col2:
                st.metric("创新性", paper.get("innovation", 0))
                st.metric("严谨性", paper.get("rigor", 0))
                st.metric("影响力", paper.get("impact", 0))

    # 下载按钮
    df = pd.DataFrame(all_results)
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下载完整 CSV",
        data=csv,
        file_name="arxiv_insight.csv",
        mime="text/csv"
    )

else:
    st.info("点击左侧「开始分析」按钮以启动分析流程。")
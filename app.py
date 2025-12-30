# app.py
import streamlit as st
import yaml
import os
from datetime import datetime
from utils import load_config  # ← 新增导入
from main_streamlit import run_analysis, streaming_run_analysis

# === 1. 加载默认配置 ===
DEFAULT_CONFIG = load_config("config.yaml")

# 页面配置
st.set_page_config(
    page_title="arXiv Insight",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 arXiv 预印本智能分析系统")
st.markdown("输入关键词，自动获取最新论文并由 LLM 评分、提取亮点")

# === 2. 侧边栏：使用 DEFAULT_CONFIG 填充默认值 ===
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
    top_k = st.slider("返回篇数", 1, 20, default_topk)

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
    use_grobid = st.checkbox("使用 Grobid 解析 PDF", value=parser_cfg.get("use_grobid", False))

    # LLM 设置
    llm_cfg = DEFAULT_CONFIG.get("llm", {})
    llm_provider = st.selectbox("模型提供商", ["qwen"], index=0)  # 目前只支持 qwen
    default_model = llm_cfg.get("model", "qwen-plus")
    llm_model = st.selectbox(
        "模型",
        ["qwen-turbo", "qwen-plus", "qwen-max"],
        index=["qwen-turbo", "qwen-plus", "qwen-max"].index(default_model) if default_model in ["qwen-turbo", "qwen-plus", "qwen-max"] else 1
    )
    api_key = st.text_input("DashScope API Key", type="password", value=llm_cfg.get("api_key", ""))

    output_cfg = DEFAULT_CONFIG.get("output", {})
    report_path = output_cfg.get("report_path", "export/report.md")
    csv_path = output_cfg.get("csv_path", "export/report.csv")
    json_path = output_cfg.get("json_path", "export/report.json")

    run_btn = st.button("🚀 开始分析", type="primary")

# === 3. 主逻辑：构建最终 config（UI 覆盖默认）===
if run_btn:
    if not api_key:
        st.error("请填写 DashScope API Key")
    else:
        # 构建最终配置：以 DEFAULT_CONFIG 为基础，用 UI 值覆盖
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
                "grobid_url": "http://localhost:8070"
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

        # === 创建动态更新区域 ===
        status_container = st.empty()
        results_container = st.empty()
        download_container = st.empty()

        all_results = []

        with st.spinner("正在分析论文..."):
            try:
                # 流式处理
                for partial_results in streaming_run_analysis(config):
                    all_results = partial_results  # 保留最新状态

                    # 更新状态
                    status_container.info(f"⏳ 已分析 {len(partial_results)} 篇论文，正在排序...")

                    # 清空并重绘结果（只显示当前 top_k）
                    top_k = config["query"]["top_k"]
                    display_papers = sorted(partial_results, key=lambda x: x.get("final_score", 0), reverse=True)[:top_k]

                    results_container.empty()  # 清空旧内容
                    with results_container.container():
                        for i, paper in enumerate(display_papers):
                            with st.expander(f"{i+1}. {paper['title']}", expanded=(i == 0)):
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

                                with col2:
                                    st.metric("创新性", paper.get("innovation", 0))
                                    st.metric("严谨性", paper.get("rigor", 0))
                                    st.metric("影响力", paper.get("impact", 0))

                # === 全部完成后 ===
                status_container.success(f"✅ 分析完成！共处理 {len(all_results)} 篇论文")

                # 提供下载
                import pandas as pd
                df = pd.DataFrame(all_results)
                csv = df.to_csv(index=False).encode('utf-8-sig')
                download_container.download_button("📥 下载完整 CSV", csv, "arxiv_insight.csv", "text/csv")

            except Exception as e:
                status_container.error(f"分析出错: {str(e)}")
                st.exception(e)
# app.py
import streamlit as st
import yaml
import os
from datetime import datetime
from main_streamlit import run_analysis  # 我们稍后定义这个函数

# 页面配置
st.set_page_config(
    page_title="arXiv Insight",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 arXiv 预印本智能分析系统")
st.markdown("输入关键词，自动获取最新论文并由 LLM 评分、提取亮点")

st.subheader("👥 作者信息")
use_author_info = st.checkbox("启用作者信息增强", value=False)
author_sources = []
if use_author_info:
    author_sources = st.multiselect(
        "数据源（按优先级排序）",
        options=["semantic_scholar", "openalex"],
        default=["semantic_scholar", "openalex"]
    )

# === 侧边栏配置 ===
with st.sidebar:
    st.header("⚙️ 配置参数")

    keywords = st.text_input("关键词（英文，逗号分隔）", "large language models, reasoning")
    categories = st.multiselect(
        "学科分类",
        options=["cs.CL", "cs.AI", "cs.LG", "cs.CV", "stat.ML", "physics.comp-ph"],
        default=["cs.CL", "cs.AI"]
    )
    days = st.slider("时间窗口（天）", 1, 30, 7)
    top_k = st.slider("返回篇数", 1, 20, 5)

    use_author_info = st.checkbox("启用作者信息（Semantic Scholar）", value=False)
    use_grobid = st.checkbox("使用 Grobid 解析 PDF（需本地运行）", value=False)

    st.divider()
    st.subheader("🔑 LLM 设置")
    llm_provider = st.selectbox("模型提供商", ["qwen"])
    llm_model = st.selectbox("模型", ["qwen-turbo", "qwen-plus", "qwen-max"])
    api_key = st.text_input("DashScope API Key", type="password")

    run_btn = st.button("🚀 开始分析", type="primary")

# === 主界面 ===
if run_btn:
    if not api_key:
        st.error("请填写 DashScope API Key")
    else:
        # 构建 config 字典（替代 config.yaml）
        config = {
            "features": {
                "author_info": {
                    "enabled": use_author_info,
                    "sources": author_sources
                }
            },
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
                "report_path": "report.md"
            }
        }

        with st.spinner("正在分析论文...（可能需要几分钟）"):
            try:
                results = run_analysis(config)
                st.success(f"✅ 分析完成！共处理 {len(results)} 篇论文")

                # 显示结果
                for i, paper in enumerate(results):
                    with st.expander(f"{i+1}. {paper['title']}", expanded=(i == 0)):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**发表时间**: {paper['published'][:10]}")
                            st.markdown(f"**分数**: `{paper.get('final_score', 0)}` (基础: `{paper.get('total_score', 0)}`, 亮点加成: `{paper.get('insight_bonus', 0)}`)")
                            st.markdown(f"**语言**: {'中文' if paper.get('language') == 'zh' else 'English'}")
                            st.markdown(f"[查看全文](https://arxiv.org/abs/{paper['id']}) | [PDF](https://arxiv.org/pdf/{paper['id']})")
                            
                            if paper.get("authors_info"):
                                st.markdown("**作者信息**:")
                                for author in paper["authors_info"]:
                                    name = author.get("name", "N/A")
                                    hindex = author.get("hIndex", "N/A")
                                    org = author.get("affiliations", ["N/A"])[0] if author.get("affiliations") else "N/A"
                                    st.caption(f"- {name} | H-index: {hindex} | {org}")

                            st.markdown("**摘要**:")
                            st.write(paper["abstract"])
                            st.markdown("**💡 亮点**:")
                            st.write(paper["breakthrough"])

                        with col2:
                            st.metric("创新性", paper.get("innovation", 0))
                            st.metric("严谨性", paper.get("rigor", 0))
                            st.metric("影响力", paper.get("impact", 0))

                # 提供下载
                import pandas as pd
                df = pd.DataFrame(results)
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下载 CSV", csv, "arxiv_insight.csv", "text/csv")

            except Exception as e:
                st.error(f"分析出错: {str(e)}")
                st.exception(e)
else:
    st.info("点击左侧「开始分析」按钮以启动分析流程。")
# main_streamlit.py
import os
from fetcher import fetch_papers
from parser import PDFParser
from filter import filter_papers
from evaluator import llm_evaluate, extract_breakthrough, compute_insight_score, load_prompt
from reporter import generate_report
from author_fetcher import enrich_paper_with_authors
from utils import download_pdf

def run_analysis(config: dict):
    query = config["query"]
    llm_cfg = config["llm"]
    parser_cfg = config["parser"]
    features = config.get("features", {})

    # Step 1: 获取论文
    papers = fetch_papers(
        keywords=query["keywords"],
        categories=query["categories"],
        days=query["time_window_days"]
    )

    # Step 2: 过滤
    papers = filter_papers(papers, query["keywords"])

    # 加载评分 Prompt
    prompt_tmpl = load_prompt()

    scored_papers = []
    parser = PDFParser(use_grobid=parser_cfg["use_grobid"], grobid_url=parser_cfg["grobid_url"])

    for i, paper in enumerate(papers[:15]):  # 控制数量避免超时
        # 下载 PDF
        pdf_path = f"pdfs/{paper['id']}.pdf"
        os.makedirs("pdfs", exist_ok=True)
        download_pdf(paper["pdf_url"], pdf_path)

        # 解析全文
        parsed = parser.parse(pdf_path)
        full_text = parsed["full_text"]

        # LLM 评分
        eval_result = llm_evaluate(full_text, prompt_tmpl, llm_cfg)
        insight = extract_breakthrough(paper["summary"], full_text, llm_cfg)

        # 计算加权分
        insight_bonus = compute_insight_score(insight["breakthrough"], insight["language"])
        final_score = eval_result["total_score"] + insight_bonus

        paper.update({
            "abstract": insight["abstract"],
            "breakthrough": insight["breakthrough"],
            "language": insight["language"],
            "insight_bonus": round(insight_bonus, 2),
            "final_score": round(final_score, 2),
            **eval_result
        })

        # 添加作者信息（如果启用）
        paper = enrich_paper_with_authors(paper, config)

        scored_papers.append(paper)

    # 排序 & 截断
    scored_papers.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    top_papers = scored_papers[:query["top_k"]]

    # 生成 Markdown 报告（可选）
    generate_report(top_papers, config, config["output"]["report_path"])

    return top_papers
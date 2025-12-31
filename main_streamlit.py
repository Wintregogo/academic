# main_streamlit.py
import os
from exporter import export_to_csv, export_to_json
from fetcher import fetch_papers
from parser import PDFParser
from filter import filter_papers
from evaluator import llm_evaluate, extract_breakthrough, compute_insight_score, load_prompt
from reporter import generate_report
from author_fetcher import enrich_paper_with_authors
from utils import download_pdf

def streaming_run_analysis(config: dict):
    """
    生成器：每分析完一篇论文就 yield 一次当前完整列表（含新 paper）
    """
    query = config["query"]
    llm_cfg = config["llm"]
    parser_cfg = config["parser"]
    features = config.get("features", {})

    # Step 1: 获取论文元数据（快速）
    papers = fetch_papers(
        keywords=query["keywords"],
        categories=query["categories"],
        days=query["time_window_days"]
    )
    papers = filter_papers(papers, query["keywords"])
    #papers = papers[:min(15, len(papers))]  # 控制最大数量

    total_papers = len(papers)

    if total_papers == 0:
        yield [], 0
        return

    # Step 2: 初始化
    prompt_tmpl = load_prompt()
    parser = PDFParser(use_grobid=parser_cfg["use_grobid"], grobid_url=parser_cfg["grobid_url"])
    scored_papers = []

    # Step 3: 逐篇处理
    for i, paper in enumerate(papers):
        paper_id = f"arvix_{paper['id']}"

        try:
            # 下载 PDF
            pdf_path = f"pdfs/{paper['id']}.pdf"
            os.makedirs("pdfs", exist_ok=True)
            download_pdf(paper["pdf_url"], pdf_path)

            # 解析全文
            parsed, errmsg = parser.parse(pdf_path)
            if parsed is None:
                eval_result = {
                    "innovation": 0,
                    "rigor": 0,
                    "impact": 0,
                    "total_score": 0
                }
                insight = {
                    "abstract": paper["summary"],
                    "breakthrough": "",
                    "language": "na"
                }
                paper["error"] = f"Failed to parse paper, error: {errmsg} "
            else:
                # LLM 评分
                full_text = parsed["full_text"]
                eval_result = llm_evaluate(paper_id, full_text, prompt_tmpl, llm_cfg)
                insight = extract_breakthrough(paper_id, paper["summary"], full_text, llm_cfg)

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

            # 实时排序（按 final_score 降序）
            scored_papers.sort(key=lambda x: x.get("final_score", 0), reverse=True)

            # Yield 当前完整列表（用于前端刷新）
            yield list(scored_papers), total_papers  # 返回副本，避免引用问题

        except Exception as e:
            # 即使某篇失败，也继续
            print(f"Error processing {paper.get('id')}: {e}")
            continue

    # 最终生成报告（可选）
    top_papers = sorted(scored_papers, key=lambda x: x.get("final_score", 0), reverse=True)[:config["query"]["top_k"]]
    generate_report(top_papers, config, config["output"]["report_path"])

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
        paper_id = f"arvix_{paper['id']}"
        # 下载 PDF
        pdf_path = f"pdfs/{paper['id']}.pdf"
        os.makedirs("pdfs", exist_ok=True)
        download_pdf(paper["pdf_url"], pdf_path)

        # 解析全文
        parsed = parser.parse(pdf_path)
        if parsed is None:
            continue
        full_text = parsed["full_text"]

        # LLM 评分 + 亮点提取
        eval_result = llm_evaluate(paper_id, full_text, prompt_tmpl, llm_cfg)
        insight = extract_breakthrough(paper_id, paper["summary"], full_text, llm_cfg)

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
    export_to_csv(top_papers, config["output"]["csv_path"])
    export_to_json(top_papers, config["output"]["json_path"])    

    return top_papers
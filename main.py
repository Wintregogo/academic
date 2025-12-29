import os
import yaml
import json
from fetcher import fetch_papers
from parser import PDFParser
from filter import filter_papers
from evaluator import llm_evaluate, load_prompt, extract_breakthrough
from reporter import generate_report
from utils import download_pdf

def main():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    query = config["query"]
    llm_cfg = config["llm"]
    parser_cfg = config["parser"]

    # Step 1: 获取论文
    papers = fetch_papers(
        keywords=query["keywords"],
        categories=query["categories"],
        days=query["time_window_days"]
    )
    print(f"Fetched {len(papers)} papers")

    # Step 2-3: 过滤 + 解析
    papers = filter_papers(papers, query["keywords"])
    parser = PDFParser(use_grobid=parser_cfg["use_grobid"], grobid_url=parser_cfg["grobid_url"])

    scored_papers = []
    prompt_tmpl = load_prompt()

    for i, paper in enumerate(papers[:20]):  # 先处理前20篇（避免超时）
        print(f"Processing {i+1}/{min(20, len(papers))}: {paper['title'][:50]}...")
        
        # 下载 PDF
        pdf_path = f"pdfs/{paper['id']}.pdf"
        os.makedirs("pdfs", exist_ok=True)
        download_pdf(paper["pdf_url"], pdf_path)
        
        # 解析
        parsed = parser.parse(pdf_path)
        full_text = parsed["full_text"]
        
        # 评分
        eval_result = llm_evaluate(full_text, prompt_tmpl, llm_cfg)
        paper.update(eval_result)
        
        # 抽取亮点（简化：用摘要代替）
        paper["abstract"] = paper["summary"]
        paper["breakthrough"] = "（待实现：调用 LLM 提取突破点）"
        
        scored_papers.append(paper)

    # 排序
    scored_papers.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    top_papers = scored_papers[:query["top_k"]]

    # 生成报告
    generate_report(top_papers, config, config["output"]["report_path"])
    print(f"Report saved to {config['output']['report_path']}")

if __name__ == "__main__":
    main()

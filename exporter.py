# exporter.py
import os
import json
import pandas as pd
from typing import List, Dict

def export_to_csv(papers: List[Dict], path: str):
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    print(f"Exporting CSV to {path}")
    df = pd.DataFrame(papers)
    # 选择关键列
    cols = [
        "id", "title", "published", "final_score", "total_score", "insight_bonus",
        "innovation", "rigor", "impact", "language", "breakthrough", "abstract"
    ]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig 支持 Excel 中文
    print(f"✅ Exported CSV to {path}")

def export_to_json(papers: List[Dict], path: str):
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"✅ Exported JSON to {path}")

def export_api_response(papers: List[Dict]) -> Dict:
    """返回符合 REST API 规范的字典"""
    return {
        "meta": {
            "total": len(papers),
            "generated_at": pd.Timestamp.now().isoformat()
        },
        "data": papers
    }
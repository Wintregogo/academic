import re
from typing import List, Dict

def is_relevant(paper: Dict, keywords: List[str]) -> bool:
    text = (paper["title"] + " " + paper["summary"]).lower()
    # 剔除综述类
    if any(w in text for w in ["survey", "review", "tutorial", "overview"]):
        return False
    # 关键词匹配（宽松）
    if not keywords:
        return True
    return any(k.lower() in text for k in keywords)

def filter_papers(papers: List[Dict], keywords: List[str]) -> List[Dict]:
    return [p for p in papers if is_relevant(p, keywords)]

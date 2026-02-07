import arxiv
import pytz
from datetime import datetime
from typing import List, Dict
from utils import days_ago

def fetch_papers(keywords: List[str], categories: List[str], days: int) -> List[Dict]:
    # 构建查询
    parts = []
    if keywords:
        parts.append(" AND ".join([f'"{k}"' for k in keywords]))
    if categories:
        parts.append(" OR ".join([f"cat:{c}" for c in categories]))
    query = " AND ".join(parts) if parts else "*"

    search = arxiv.Search(
        query=query,
        max_results=200,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    cutoff = days_ago(days).replace(tzinfo=pytz.timezone('UTC'))
    papers = []
    for r in search.results():
        if r.published >= cutoff:
            papers.append({
                "id": r.get_short_id(),
                "title": r.title,
                "summary": r.summary,
                "pdf_url": r.pdf_url,
                "published": r.published.isoformat(),
                "authors": [a.name for a in r.authors]
            })
    return papers
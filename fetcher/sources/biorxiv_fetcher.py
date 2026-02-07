# fetcher/sources/biorxiv_fetcher.py
import feedparser
from datetime import date, datetime, timezone
import logging
import re
import time
import sys
import os
import requests
# 将项目根目录加入 Python 路径
#sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
#from utils.db import get_db_connection

logger = logging.getLogger(__name__)

CROSSREF_MAILTO = "wintregogo@gmail.com"  # ← 👈 修改这里！

# 复用 arXiv 的工具函数（批次内去重）
# 注意：我们稍后会重构为公共模块，但现阶段先复制以保持独立
def deduplicate_papers_in_batch(papers: list) -> list:
    paper_dict = {}
    for p in papers:
        pid = p["paper_id"]
        if pid not in paper_dict:
            paper_dict[pid] = p
        else:
            if p["updated_at"] > paper_dict[pid]["updated_at"]:
                paper_dict[pid] = p
    return list(paper_dict.values())

def is_paper_exists(cur, paper_id: str, source: str) -> int | None:
    cur.execute("SELECT id FROM papers WHERE paper_id = %s AND source = %s;", (paper_id, source))
    row = cur.fetchone()
    return row['id'] if row else None


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def fetch_biorxiv_daily(target_date: date) -> list:
    """
    使用 Crossref API 获取某天发布的 bioRxiv 论文
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.fetcher_utils import fetch_bio_med_preprints
    return fetch_bio_med_preprints("biorxiv", target_date)


def get_new_primary_papers_from_biorxiv(target_date: date, db_cur) -> list:
    """
    获取指定日期 bioRxiv 上所有新的、唯一的 primary 论文
    """
    logger.info(f"Starting fetch for bioRxiv on {target_date}")
    raw_papers = fetch_biorxiv_daily(target_date)
    if not raw_papers:
        return []

    unique_papers = deduplicate_papers_in_batch(raw_papers)
    new_papers = []
    for p in unique_papers:
        existing_id = is_paper_exists(db_cur, p['paper_id'], p['source'])
        if existing_id is None:
            new_papers.append(p)
        else:
            logger.debug(f"Skipping existing bioRxiv paper: {p['paper_id']}")

    logger.info(f"bioRxiv: {len(new_papers)} new primary papers")
    return new_papers


# ===== 测试入口 =====
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from utils.db import get_db_connection

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if len(sys.argv) != 2:
        print("Usage: python biorxiv_fetcher.py YYYY-MM-DD")
        sys.exit(1)

    try:
        test_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD")
        sys.exit(1)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        papers = get_new_primary_papers_from_biorxiv(test_date, cur)
        print(f"\n✅ Found {len(papers)} new bioRxiv papers:\n")
        for i, p in enumerate(papers[:3]):
            print(f"{i+1}. DOI: {p['paper_id']}")
            print(f"    Title: {p['title'][:100]}...")
            print(f"    PDF: {p['pdf_url']}\n")
    finally:
        cur.close()
        conn.close()
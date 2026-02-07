# fetcher/sources/medrxiv_fetcher.py
import requests
import re
from datetime import date, datetime, timezone
import logging
import time

logger = logging.getLogger(__name__)

# 替换为你的真实邮箱！
CROSSREF_MAILTO = "wintregogo@gmail.com"


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


OAI_BASE_URL = "https://api.medrxiv.org/oai/provider"
NAMESPACES = {
    'oai': 'http://www.openarchives.org/OAI/2.0/',
    'dc': 'http://purl.org/dc/elements/1.1/'
}

def fetch_medrxiv_daily(target_date: date) -> list:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.fetcher_utils import fetch_bio_med_preprints
    return fetch_bio_med_preprints("medrxiv", target_date)
        

def get_new_primary_papers_from_medrxiv(target_date: date, db_cur) -> list:
    logger.info(f"Starting fetch for medRxiv on {target_date}")
    raw_papers = fetch_medrxiv_daily(target_date)
    if not raw_papers:
        return []

    unique_papers = deduplicate_papers_in_batch(raw_papers)
    new_papers = []
    for p in unique_papers:
        existing_id = is_paper_exists(db_cur, p['paper_id'], p['source'])
        if existing_id is None:
            new_papers.append(p)
        else:
            logger.debug(f"Skipping existing medRxiv paper: {p['paper_id']}")

    logger.info(f"medRxiv: {len(new_papers)} new primary papers")
    return new_papers


# ===== 测试入口 =====
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from utils.db import get_db_connection

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if len(sys.argv) != 2:
        print("Usage: python medrxiv_fetcher.py YYYY-MM-DD")
        sys.exit(1)

    try:
        test_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD")
        sys.exit(1)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        papers = get_new_primary_papers_from_medrxiv(test_date, cur)
        print(f"\n✅ Found {len(papers)} new medRxiv papers:\n")
        for i, p in enumerate(papers[:3]):
            print(f"{i+1}. DOI: {p['paper_id']}")
            print(f"    Title: {p['title'][:100]}...")
            print(f"    PDF: {p['pdf_url']}\n")
    finally:
        cur.close()
        conn.close()
from datetime import date
from typing import List, Dict
import logging
from datetime import date, datetime, timezone
import sys
import os
from arxiv_fetcher import get_new_primary_papers_from_arxiv
from biorxiv_fetcher import get_new_primary_papers_from_biorxiv
from medrxiv_fetcher import get_new_primary_papers_from_medrxiv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.dedup import deduplicate_papers

logger = logging.getLogger(__name__)

def fetch_unified_daily(target_date: date, db_cur) -> List[Dict]:
    all_papers = []

    logger.info("Fetching papers:")
    # Fetch from all sources
    for fetch_func, source_name in [
        (get_new_primary_papers_from_arxiv, "arxiv"),
        (get_new_primary_papers_from_biorxiv, "biorxiv"),
        (get_new_primary_papers_from_medrxiv, "medrxiv"),
    ]:
        try:
            papers = fetch_func(target_date, db_cur)
            logger.info(f"Fetched {len(papers)} papers from {source_name}")
            all_papers.extend(papers)
            print(f"\n✅ -- {source_name}: found {len(papers)} new papers:\n")
        except Exception as e:
            logger.error(f"Error fetching {source_name}: {e}")

    # 去重（基于内容）
    unique_papers = deduplicate_papers(all_papers, threshold=0.85)
    return unique_papers

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
        papers = fetch_unified_daily(test_date, cur)
        print(f"\n✅ Found {len(papers)} new papers:\n")
        for i, p in enumerate(papers[:3]):
            print(f"{i+1}. DOI: {p['paper_id']}")
            print(f"    Title: {p['title'][:100]}...")
            print(f"    PDF: {p['pdf_url']}\n")
    finally:
        cur.close()
        conn.close()
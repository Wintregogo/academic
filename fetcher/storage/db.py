# fetcher/ingest.py
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def insert_papers(papers: list, db_conn):
    """
    将论文列表写入数据库
    - 先插入所有主论文（is_primary=True）
    - 再插入从属论文（is_primary=False）
    - 使用 ON CONFLICT DO NOTHING 实现幂等
    """

    if not papers:
        logger.info("No papers to insert.")
        return

    # 分离主论文和从属论文
    primary_papers = [p for p in papers if p.get("is_primary", False)]
    duplicate_papers = [p for p in papers if not p.get("is_primary", False)]

    try:
        with db_conn.cursor() as cur:
            # 1. 插入主论文
            _bulk_insert_papers(cur, primary_papers)
            logger.info(f"Inserted {len(primary_papers)} primary papers.")

            # 2. 插入从属论文（依赖主论文已存在）
            _bulk_insert_papers(cur, duplicate_papers)
            logger.info(f"Inserted {len(duplicate_papers)} duplicate papers.")

        db_conn.commit()
        logger.info("All papers committed successfully.")
    except Exception as e:
        db_conn.rollback()
        logger.error(f"Database insertion failed: {e}")
        raise
#    finally:
#        db_conn.close()

def _bulk_insert_papers(cur, papers: list):
    if not papers:
        return

    # 准备数据元组
    records = []
    for p in papers:
        record = (
            p["paper_id"],
            p["source"],
            p["title"],
            json.dumps(p.get("title_i18n", {})),
            p.get("abstract", ""),
            json.dumps(p.get("abstract_i18n", {})),
            p.get("doi"),  # 可从 raw_metadata 提取，但你可能已在 paper 中存了
            p["pdf_url"],
            p["published_at"],
            p.get("updated_at"),
            p.get("keywords", []),
            p.get("citation_count", 0),
            p.get("last_citation_update"),
            json.dumps(p["raw_metadata"]),
            p.get("is_primary", False),
            p.get("primary_paper_id"),  # 字符串，如 "arXiv:2405.12345"
            p.get("hash_sha256", ""),
            p.get("local_pdf_path"),
            p.get("fetched_at", datetime.utcnow()),
        )
        records.append(record)

    # 批量插入（使用 execute_values）
    sql = """
        INSERT INTO papers (
            paper_id, source, title, title_i18n, abstract, abstract_i18n,
            doi, pdf_url, published_at, updated_at, keywords,
            citation_count, last_citation_update, raw_metadata,
            is_primary, primary_paper_id, hash_sha256, local_pdf_path, fetched_at
        ) VALUES %s
        ON CONFLICT (paper_id, source) DO NOTHING
    """
    from psycopg2.extras import execute_values
    execute_values(cur, sql, records, template=None, page_size=100)
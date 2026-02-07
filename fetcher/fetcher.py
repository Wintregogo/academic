# fetcher/main.py
import sys
from datetime import date, timedelta, datetime
from fetcher.sources.unified_fetcher import fetch_unified_daily
from fetcher.storage.db import insert_papers
from utils.db import get_db_connection

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Fetcher started")
    if len(sys.argv) == 1:
        # 抓取昨天的论文（避免当天未完全发布）
        target_date = date.today() - timedelta(days=1)        
    else:
        # 抓取制定日期的论文
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

    logger.info(f"Fetching papers of date {target_date}")


    # 连接数据库
    logger.info("Conneccting to database ...")
    conn = get_db_connection()

    try:
        # 获取论文
        logger.info("Fetching papers ...")
        papers = fetch_unified_daily(target_date, conn)
        logger.info(f"Fetched {len(papers)} unified papers for {target_date}")
        
        if papers is not None and len(papers) > 0:  
            logger.info(papers[0])              
            # 插入数据库
            logger.info("Inserting into database ...")
            insert_papers(papers, conn)
            logger.info("Ingestion complete.")

        else:
            logger.info('No papers found, exits')
    finally:
        conn.close()        
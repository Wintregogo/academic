# sources/arxiv_fetcher.py
import feedparser
import urllib.parse
from datetime import date, datetime, timezone
from dateutil import parser as date_parser
import re
import logging
import json
import sys
import os

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"


# ===== 数据库查重函数 =====
def is_paper_exists(cur, paper_id: str, source: str) -> int | None:
    """
    检查论文是否已存在于数据库
    :return: 数据库 id（如果存在），否则 None
    """
    cur.execute("""
        SELECT id FROM papers 
        WHERE paper_id = %s AND source = %s;
    """, (paper_id, source))
    row = cur.fetchone()
    return row['id'] if row else None


def deduplicate_papers_in_batch(papers: list) -> list:
    """
    在同一批次论文中按 paper_id 去重，保留 updated_at 最新的版本
    :param papers: 来自 fetch_arxiv_daily 的论文列表
    :return: 去重后的列表
    """
    paper_dict = {}
    for p in papers:
        pid = p["paper_id"]
        if pid not in paper_dict:
            paper_dict[pid] = p
        else:
            # 保留 updated_at 更晚的版本
            if p["updated_at"] > paper_dict[pid]["updated_at"]:
                paper_dict[pid] = p

    unique_papers = list(paper_dict.values())
    logger.info(f"Deduplicated: {len(papers)} → {len(unique_papers)} papers")
    return unique_papers


def clean_text(text: str) -> str:
    """移除 HTML 标签并清理空白"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def serialize_entry(entry) -> dict:
    """将 feedparser entry 转为可 JSON 序列化的字典（用于 raw_metadata）"""
    def default_serializer(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)

    # 提取所有属性，过滤不可序列化对象
    raw = {}
    for key, value in entry.items():
        try:
            json.dumps(value, default=default_serializer)
            raw[key] = value
        except (TypeError, ValueError):
            raw[key] = str(value)
    return raw


def parse_authors_arxiv(entry) -> list:
    authors = []
    for author in entry.get("authors", []):
        name = author.get("name", "").strip()
        affil = ""
        # 如果你的 entry 包含 affiliation（如从 XML 解析）
        if "affiliation" in author:
            affil = author["affiliation"].strip()
        authors.append({
            "name": name,
            "affiliation": affil,
            "orcid": ""  # arXiv 不提供 ORCID
        })
    return authors


def extract_arxiv_version(paper_id: str) -> str:
    """从 arXiv ID 提取版本，如 'arXiv:2405.12345v2' → 'v2'"""
    match = re.search(r'v(\d+)$', paper_id)
    if match:
        return f"v{match.group(1)}"
    return "v1"  # 默认 v1


def fetch_arxiv_daily(target_date: date) -> list:
    """
    获取 arXiv 上某一天新提交的所有论文元数据，适配 papers 表结构
    
    返回列表，每个元素是 dict，包含：
      - paper_id: str (e.g., '2405.12345')
      - source: 'arxiv'
      - title: str
      - abstract: str
      - pdf_url: str or None
      - published_at: datetime (UTC)
      - updated_at: datetime (UTC)
      - raw_metadata: dict (JSON-serializable)
    """
    start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_time = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    raw_query = f"submittedDate:[{start_time.strftime('%Y%m%d%H%M')} TO {end_time.strftime('%Y%m%d%H%M')}]"
    encoded_query = urllib.parse.quote(raw_query, safe='/:[]')

    all_papers = []
    start = 0
    batch_size = 100

    while True:
        url = f"{ARXIV_API_URL}?search_query={encoded_query}&start={start}&max_results={batch_size}&sortBy=submittedDate&sortOrder=ascending"
        logger.info(f"Fetching from: {url}")

        try:
            feed = feedparser.parse(url)
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"Feed parse warning: {feed.bozo_exception}")

            entries = feed.entries
            if not entries:
                break

            for entry in entries:
                published = date_parser.parse(entry.published).astimezone(timezone.utc)
                # 严格只保留目标日期提交的论文
                if published.date() != target_date:
                    continue

                # 提取 paper_id（去掉版本号）
                arxiv_id_full = entry.id.split('/')[-1]
                paper_id = arxiv_id_full.split('v')[0]  # e.g., '2405.12345v3' → '2405.12345'

                title = clean_text(entry.title)
                abstract = clean_text(entry.summary)

                # PDF URL
                pdf_url = None
                for link in entry.links:
                    if link.get('type') == 'application/pdf':
                        pdf_url = link.href
                        break

                updated_at = date_parser.parse(entry.updated).astimezone(timezone.utc)

                # 原始元数据快照（确保可 JSON 序列化）
                raw_metadata = serialize_entry(entry)

                all_papers.append({
                    "paper_id": paper_id,
                    "version": extract_arxiv_version(entry["id"]),
                    "source": "arxiv",
                    "title": title,
                    "abstract": abstract,
                    "authors": parse_authors_arxiv(entry),
                    "pdf_url": pdf_url,
                    "published_at": published,
                    "updated_at": updated_at,
                    "raw_metadata": raw_metadata,
                    # 以下字段由数据库或后续步骤处理
                    # title_i18n, abstract_i18n, doi, keywords, hash_sha256, local_pdf_path
                    # is_primary=True, primary_paper_id=NULL (由插入逻辑决定)
                })

            logger.info(f"Fetched {len(entries)} entries (total so far: {len(all_papers)})")

            if len(entries) < batch_size:
                break

            start += batch_size
            if start > 10000:
                logger.warning("Hit safety limit (10,000 papers), stopping.")
                break

        except Exception as e:
            logger.error(f"Error fetching batch starting at {start}: {e}")
            break

    logger.info(f"✅ Total papers on {target_date}: {len(all_papers)}")
    return all_papers


def get_new_primary_papers_from_arxiv(target_date: date, db_cur) -> list:
    """
    获取指定日期 arXiv 上所有**新的、唯一的、需作为 primary 处理**的论文
    
    步骤：
      1. 获取当天所有论文
      2. 批次内按 paper_id 去重（保留 updated_at 最新的）
      3. 过滤掉数据库中已存在的 (paper_id, source)
    
    :param target_date: 目标日期
    :param db_cur: 数据库游标（已连接）
    :return: List of papers to be inserted as primary
    """
    logger.info(f"Starting fetch and deduplication for {target_date}")
    
    # Step 1: 获取原始数据
    raw_papers = fetch_arxiv_daily(target_date)
    if not raw_papers:
        logger.info("No papers found for this date.")
        return []

    # Step 2: 批次内去重
    unique_papers = deduplicate_papers_in_batch(raw_papers)

    # Step 3: 过滤掉数据库中已存在的
    new_papers = []
    for p in unique_papers:
        existing_id = is_paper_exists(db_cur, p['paper_id'], p['source'])
        if existing_id is None:
            new_papers.append(p)
        else:
            logger.debug(f"Skipping existing paper: {p['paper_id']} (DB ID={existing_id})")

    logger.info(f"Final result: {len(new_papers)} new primary papers to process")
    return new_papers


# ===== 测试入口（使用高层函数）=====
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    from utils.db import get_db_connection

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if len(sys.argv) != 2:
        print("Usage: python arxiv_fetcher.py YYYY-MM-DD")
        sys.exit(1)

    try:
        test_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD")
        sys.exit(1)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        new_papers = get_new_primary_papers_from_arxiv(test_date, cur)
        print(f"\n✅ Ready to process {len(new_papers)} new primary papers:\n")
        for i, p in enumerate(new_papers[:5]):
            print(f"{i+1}. {p['paper_id']} | {p['title'][:80]}...")
    finally:
        cur.close()
        conn.close()
import requests
from datetime import date, datetime, timezone
import logging
import time

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.biorxiv.org/details"

def fetch_bio_med_preprints(source: str, target_date: date) -> list:
    """
    通用函数：从 bioRxiv/medRxiv 官方 API 获取某日所有预印本
    
    Args:
        source (str): "biorxiv" 或 "medrxiv"
        target_date (date): 目标日期
    
    Returns:
        List[dict]: 论文列表，每篇含 paper_id, title, abstract, pdf_url 等
    """
    if source not in ("biorxiv", "medrxiv"):
        raise ValueError("source must be 'biorxiv' or 'medrxiv'")
    
    start_date = end_date = target_date.isoformat()
    cursor = 1
    all_papers = []
    base_url = f"{API_BASE_URL}/{source}"

    while True:
        url = f"{base_url}/{start_date}/{end_date}/{cursor}"
        logger.info(f"Fetching {source} API: {url}")
        
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            collection = data.get("collection", [])
            if not collection:
                break

            for item in collection:
                doi = item.get("doi")
                if not doi:
                    continue

                # 构造 PDF URL
                domain = "www.biorxiv.org" if source == "biorxiv" else "www.medrxiv.org"
                pdf_url = f"https://{domain}/content/{doi}.full.pdf"

                # 解析发布日期
                try:
                    pub_dt = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, KeyError):
                    pub_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)

                all_papers.append({
                    "paper_id": doi,
                    "source": source,
                    "title": item.get("title", "").strip(),
                    "abstract": item.get("abstract", "").strip(),
                    "pdf_url": pdf_url,
                    "published_at": pub_dt,
                    "updated_at": pub_dt,
                    "raw_metadata": item,
                })

            # 分页控制
            messages = data.get("messages", [{}])[0]
            count = messages.get("count", 0)
            total = messages.get("total", 0)
            logger.debug(f"Fetched {count} papers (total: {total}) from {source}")

            if count < 100 or cursor * 100 >= total:
                break

            cursor += 1
            time.sleep(0.3)  # 礼貌延迟

        except Exception as e:
            logger.error(f"Error fetching {source} API: {e}")
            break

    return all_papers
import requests
from datetime import date, datetime, timezone
import logging
import time
import hashlib
import re
from collections import Counter

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.biorxiv.org/details"


def parse_authors_biorxiv(author_str: str) -> list:
    if not author_str:
        return []
    names = [name.strip() for name in author_str.split(";")]
    return [{"name": name, "affiliation": "", "orcid": ""} for name in names]


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
                    "authors": parse_authors_biorxiv(item.get("authors", "")),
                    "version": str(item.get("version", "")).strip() or None,
                    "pdf_url": pdf_url,
                    "published_at": pub_dt,
                    "updated_at": pub_dt,
                    "raw_metadata": item,
                })

            # 分页控制
            messages = data.get("messages", [{}])[0]
            count_str = messages.get("count", "0")
            total_str = messages.get("total", "0")

            try:
                count = int(count_str)
                total = int(total_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid count/total from API: count={count_str}, total={total_str}")
                count = 0
                total = 0

            logger.debug(f"Fetched {count} papers (total: {total}) from {source}")

            if count < 100 or cursor * 100 >= total:
                break

            cursor += 1
            time.sleep(0.3)  # 礼貌延迟

        except Exception as e:
            logger.error(f"Error fetching {source} API: {e}")
            break

    return all_papers


def compute_content_hash(title: str, abstract: str) -> str:
    """基于标题+摘要生成稳定哈希（忽略大小写和空白）"""
    content = (title or "") + "\n" + (abstract or "")
    normalized = " ".join(content.lower().split())  # 标准化空白
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    
def extract_keywords(text: str, top_k=8) -> list:
    """从文本中提取高频实词作为关键词"""
    if not text:
        return []
    
    # 简单清洗
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    words = text.lower().split()
    
    # 过滤停用词（简化版）
    stop_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "a", "an", "as", "is", "are", "was", "were"}
    filtered = [w for w in words if len(w) > 2 and w not in stop_words]
    
    # 取高频词
    counter = Counter(filtered)
    return [word for word, _ in counter.most_common(top_k)]    
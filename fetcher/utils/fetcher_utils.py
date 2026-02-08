import os
import requests
from datetime import date, datetime, timezone
import logging
import time
import hashlib
import re
import traceback
from collections import Counter
from typing import List, Dict, Optional, Any
from fetcher.storage.db import is_paper_exists
from fetcher.utils.dedup import deduplicate_papers_in_batch


logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.biorxiv.org/details"


def parse_authors_bio_med_rxiv(author_str: str) -> list:
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

                paper = {
                    "paper_id": doi,
                    "source": source,
                    "title": item.get("title", "").strip(),
                    "abstract": item.get("abstract", "").strip(),
                    "authors": parse_authors_bio_med_rxiv(item.get("authors", "")),
                    "version": str(item.get("version", "")).strip() or None,
                    "pdf_url": pdf_url,
                    "published_at": pub_dt,
                    "updated_at": pub_dt,
                    "raw_metadata": item,
                }                
                all_papers.append(paper)

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
            traceback.print_exc()
            break
    
    unique_papers = deduplicate_papers_in_batch(all_papers)
    return unique_papers


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
    

def normalize_orcid(orcid_url: Optional[str]) -> Optional[str]:
    if not orcid_url:
        return None

    return orcid_url.replace("https://orcid.org/", "").strip()


def get_openalex_work_id(paper: dict) -> Optional[str]:
    pid = paper["paper_id"]
    source = paper['source']
    if source == 'arxiv':
        return f'arXiv/{pid}'  # 1234.5678 → arXiv/1234.5678
    else:
        return f"https://doi.org/{pid}"
    return None


def get_safe_string(d: dict, name: str):
    value = d.get(name, "")
    value = value if value and type(value)==str else ""
    return value


def fetch_enriched_authors_from_openalex(paper: dict) -> List[Dict[str, Any]]:
    """返回结构化作者列表，包含完整机构和位置信息"""
    work_id = get_openalex_work_id(paper)
    if not work_id:
        return

    logger.info(f"Fetching author/institute information for {work_id} with OpenAlex")
    url = f"https://api.openalex.org/works/{work_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"OpenAlex {work_id} → {resp.status_code}")
            return
        
        work = resp.json()
        authors = []
        for authorship in work.get("authorships", []):
            author_data = authorship.get("author")
            if not author_data:
                continue

            # === 作者信息 ===
            openalex_author_id = get_safe_string(author_data, "id").replace("https://openalex.org/", "")
            display_name = get_safe_string(author_data, "display_name").strip()
            orcid = normalize_orcid(author_data.get("orcid"))

            # === 作者位置 ===
            position = authorship.get("author_position")  # "first", "middle", "last"

            # === 原始 affiliation 字符串 ===
            raw_affils = authorship.get("raw_affiliation_strings", [])

            # === 机构信息（支持多机构，但通常取第一个）===
            try:
                institutions = []
                for inst in authorship.get("institutions", []):
                    #print(f"lineage:  {inst.get('lineage', [])}")
                    institutions.append({
                        "openalex_id": get_safe_string(inst, "id").replace("https://openalex.org/", ""),
                        "ror_id": inst.get("ror"),  # 可能为 None
                        "name": inst.get("display_name", "").strip(),
                        "country_code": inst.get("country_code"),  # e.g., "NO"
                        "type": inst.get("type"),  # e.g., "education", "government"
                        "lineage": [x.replace("https://openalex.org/", "") for x in inst.get("lineage", [])]
                    })
            except:
                pass

            authors.append({
                "openalex_author_id": openalex_author_id,
                "display_name": display_name,
                "orcid": orcid,
                "author_position": position,  # 新增！
                "raw_affiliations": raw_affils,
                "institutions": institutions  # 支持多机构
            })
        paper['authors'] = authors
    except Exception as e:
        logger.error(f"OpenAlex enrich failed for {work_id}: {e}")
        traceback.print_exc()


def enrich_paper_authors(papers: list):
    if not papers:
        return []

    for paper in papers:
        fetch_enriched_authors_from_openalex(paper)

    return papers
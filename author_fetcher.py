# author_fetcher.py
import requests
import time
import logging
from typing import List, Dict, Optional

# 配置日志（可选）
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_AUTHOR_SEARCH = "https://api.semanticscholar.org/graph/v1/author/search"
OPENALEX_AUTHORS_SEARCH = "https://api.openalex.org/authors"

def _fetch_from_semantic_scholar(name: str) -> Optional[Dict]:
    """从 Semantic Scholar 获取作者信息"""
    try:
        resp = requests.get(
            SEMANTIC_SCHOLAR_AUTHOR_SEARCH,
            params={
                "query": name,
                "fields": "name,hIndex,affiliations,paperCount,citationCount"
            },
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                author = data["data"][0]
                return {
                    "source": "semantic_scholar",
                    "name": author.get("name"),
                    "h_index": author.get("hIndex"),
                    "paper_count": author.get("paperCount"),
                    "citation_count": author.get("citationCount"),
                    "affiliations": [aff.get("name") for aff in author.get("affiliations", []) if aff.get("name")]
                }
    except Exception as e:
        logger.warning(f"Semantic Scholar failed for '{name}': {e}")
    return None


def _fetch_from_openalex(name: str) -> Optional[Dict]:
    """从 OpenAlex 获取作者信息"""
    try:
        # OpenAlex 使用 display_name 搜索
        resp = requests.get(
            OPENALEX_AUTHORS_SEARCH,
            params={
                "filter": f"display_name.search:{name}",
                "select": "display_name,works_count,cited_by_count,summary_stats,affiliations"
            },
            timeout=5
        )
       
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                author = results[0]
                # 提取机构（OpenAlex 的 affiliations 是嵌套的）
                affs = []
                for aff in author.get("affiliations", []):
                    inst = aff.get("institution")
                    if inst and inst.get("display_name"):
                        affs.append(inst["display_name"])

                h_index = author.get("summary_stats", {}).get("h_index")
                return {
                    "source": "openalex",
                    "name": author.get("display_name"),
                    "h_index": h_index,
                    "paper_count": author.get("works_count"),
                    "citation_count": author.get("cited_by_count"),
                    "affiliations": affs
                }
    except Exception as e:
        logger.warning(f"OpenAlex failed for '{name}': {e}")
    return None


def get_author_info(name: str, sources: List[str]) -> Dict:
    """
    根据配置的 sources 列表，依次尝试获取作者信息
    返回统一格式的字典
    """
    result = {
        "name": name,
        "h_index": "N/A",
        "paper_count": "N/A",
        "citation_count": "N/A",
        "affiliations": [],
        "source_used": "none"
    }

    # 按顺序尝试
    for source in sources:
        info = None
        if source == "semantic_scholar":
            info = _fetch_from_semantic_scholar(name)
        elif source == "openalex":
            info = _fetch_from_openalex(name)

        if info:
            result.update({
                "h_index": info.get("h_index", "N/A"),
                "paper_count": info.get("paper_count", "N/A"),
                "citation_count": info.get("citation_count", "N/A"),
                "affiliations": info.get("affiliations", []),
                "source_used": info["source"]
            })
            break  # 找到一个就停止

        time.sleep(0.3)  # 防止 API 限流

    return result


def enrich_paper_with_authors(paper: Dict, config: Dict) -> Dict:
    """
    根据 config 决定是否以及如何 enrich 作者信息
    :param paper: 包含 'authors' 字段的论文 dict
    :param config: 整个配置字典（含 features.author_info）
    """
    author_config = config.get("features", {}).get("author_info", {})
    enabled = author_config.get("enabled", False)
    sources = author_config.get("sources", [])

    if not enabled or not sources:
        return paper

    authors_info = []
    for name in paper.get("authors", []):
        if not name or name == "Unknown":
            continue
        info = get_author_info(name, sources)
        authors_info.append(info)

    paper["authors_info"] = authors_info
    return paper
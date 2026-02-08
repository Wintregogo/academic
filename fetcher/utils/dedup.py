import re
import logging
from typing import List, Dict, Tuple
from itertools import combinations

logger = logging.getLogger(__name__)

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


def normalize_text(text: str) -> str:
    """标准化文本：小写、去标点、去多余空格"""
    if not text:
        return ""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def jaccard_similarity(str1: str, str2: str) -> float:
    """计算两个字符串的 Jaccard 相似度（基于词集合）"""
    set1 = set(normalize_text(str1).split())
    set2 = set(normalize_text(str2).split())
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)

def is_duplicate(paper1: Dict, paper2: Dict, title_weight=0.6, abs_weight=0.4, threshold=0.85) -> bool:
    """
    判断两篇论文是否重复
    - 综合标题和摘要的 Jaccard 相似度
    - 可扩展：加入作者姓氏匹配
    """
    title_sim = jaccard_similarity(paper1["title"], paper2["title"])
    abs_sim = jaccard_similarity(paper1.get("abstract", ""), paper2.get("abstract", ""))
    combined_sim = title_weight * title_sim + abs_weight * abs_sim

    # 可选：加入作者姓氏交集（简单版）
    # authors1 = set(a.split()[0].lower() for a in (paper1.get("authors") or "").split(","))
    # authors2 = set(a.split()[0].lower() for a in (paper2.get("authors") or "").split(","))
    # author_overlap = len(authors1 & authors2) / max(len(authors1), len(authors2), 1)

    if combined_sim >= threshold:
        logger.debug(f"Duplicate detected (sim={combined_sim:.2f}): {paper1['title'][:50]}...")
        return True
    return False

def deduplicate_papers(papers: List[Dict], threshold=0.85) -> List[Dict]:
    """
    对论文列表进行去重
    - 保留第一个出现的版本
    - 时间复杂度 O(n²)，但 n 通常 < 500，可接受
    """
    index = 0
    duplicated = 0
    for paper in papers:
        index += 1
        is_dup = False
        if index == 1:
            paper['is_primary'] = True
            continue

        for existing in papers[:index-1]:
            if not existing['is_primary']:
                continue
            
            if is_duplicate(paper, existing, threshold=threshold):
                is_dup = True
                duplicated += 1
                paper['is_primary'] = False
                paper['primary_paper_id'] = f'{existing['source']}::{existing['paper_id']}'
                break

        if not is_dup:
            paper['is_primary'] = True

    logger.info(f'deduuplicate: found {duplicated} duplications')
    return papers
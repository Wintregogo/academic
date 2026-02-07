from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .arxiv_fetcher import ArxivFetcher
from .biorxiv_medrxiv import BiorxivMedrxivFetcher
from .base import Paper

def search_across_platforms(
    query: str,
    platforms: List[str] = ["arxiv", "biorxiv", "medrxiv"],
    max_results_per_platform: int = 10,
    sort_by: str = "relevance"  # or "date"
) -> List[Paper]:
    """
    跨平台联合搜索论文
    
    Args:
        query: 搜索关键词
        platforms: 要搜索的平台列表，支持 "arxiv", "biorxiv", "medrxiv"
        max_results_per_platform: 每个平台最多返回多少篇
        sort_by: 排序方式（当前仅按平台顺序+时间倒序；如需语义排序需引入向量模型）
    
    Returns:
        List[Paper]: 合并后的论文列表
    """
    fetchers = []
    
    if "arxiv" in platforms:
        fetchers.append(("arxiv", ArxivFetcher()))
    if "biorxiv" in platforms:
        fetchers.append(("biorxiv", BiorxivMedrxivFetcher("biorxiv")))
    if "medrxiv" in platforms:
        fetchers.append(("medrxiv", BiorxivMedrxivFetcher("medrxiv")))
    
    all_papers = []

    # 并行请求各平台（加速）
    with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
        future_to_platform = {
            executor.submit(fetcher.search, query, max_results_per_platform): platform
            for platform, fetcher in fetchers
        }
        
        for future in as_completed(future_to_platform):
            platform = future_to_platform[future]
            try:
                papers = future.result(timeout=15)
                all_papers.extend(papers)
            except Exception as e:
                print(f"Search failed for {platform}: {e}")
    
    # 简单排序：按平台优先级 + 发表日期倒序
    # 你可以后续替换为基于嵌入的语义排序
    platform_priority = {"arxiv": 0, "biorxiv": 1, "medrxiv": 2}
    all_papers.sort(
        key=lambda p: (
            platform_priority.get(p.source, 99),
            p.published or "0000-00-00"
        ),
        reverse=True
    )
    
    return all_papers
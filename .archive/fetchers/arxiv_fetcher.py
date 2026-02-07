import arxiv
from typing import List
from .base import Paper, PaperFetcher

class ArxivFetcher(PaperFetcher):
    def __init__(self):
        # arxiv API 默认每页 100 条，最多返回 300,000 条（实际受限制）
        pass

    def search(self, query: str, max_results: int = 10) -> List[Paper]:
        """
        搜索 arXiv 论文
        支持高级查询语法（如 "cat:cs.CV AND ti:transformer"）
        """
        client = arxiv.Client(page_size=100, delay_seconds=0.5)
        papers = []
        
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            for result in client.results(search):
                paper = self._parse_result(result)
                if paper:
                    papers.append(paper)
                    
        except Exception as e:
            print(f"Arxiv search error: {e}")
            # 可选：返回空列表或抛出异常
            
        return papers

    def get_paper_by_id(self, paper_id: str) -> Paper:
        """
        通过 arXiv ID 获取单篇论文（如 '2301.12345'）
        """
        try:
            result = next(arxiv.Search(id_list=[paper_id]).results())
            return self._parse_result(result)
        except Exception as e:
            print(f"Failed to fetch arXiv paper {paper_id}: {e}")
            return None

    def _parse_result(self, result: arxiv.Result) -> Paper:
        try:
            # arXiv ID 格式如 "2301.12345v1"，我们取主版本 "2301.12345"
            paper_id = result.get_short_id().split('v')[0]
            
            return Paper(
                paper_id=paper_id,
                title=result.title,
                authors=[author.name for author in result.authors],
                abstract=result.summary,
                pdf_url=result.pdf_url,
                published=result.published.strftime("%Y-%m-%d"),  # ISO 8601
                source="arxiv"
            )
        except Exception as e:
            print(f"Parse arXiv result error: {e}")
            return None
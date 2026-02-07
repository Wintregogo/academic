import requests
from typing import List
from .base import Paper, PaperFetcher

class BiorxivMedrxivFetcher(PaperFetcher):
    def __init__(self, source: str = "biorxiv"):
        if source not in ["biorxiv", "medrxiv"]:
            raise ValueError("source must be 'biorxiv' or 'medrxiv'")
        self.source = source
        self.api_base = f"https://api.biorxiv.org"

    def search(self, query: str, max_results: int = 10) -> List[Paper]:
        """
        搜索论文（按关键词）
        注意：官方 API 不支持复杂布尔查询，仅支持简单关键词匹配
        """
        papers = []
        cursor = 0
        collected = 0
        
        while collected < max_results:
            url = f"{self.api_base}/pub/{self.source}/search/{query}/{cursor}/json"
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                
                if "collection" not in data or not data["collection"]:
                    break
                
                for item in data["collection"]:
                    if collected >= max_results:
                        break
                    paper = self._parse_item(item)
                    if paper:
                        papers.append(paper)
                        collected += 1
                
                # 分页：每页最多 100 条，cursor += 100
                cursor += 100
                if len(data["collection"]) < 100:
                    break
                    
            except Exception as e:
                print(f"Warning: Failed to fetch from {self.source}: {e}")
                break
                
        return papers[:max_results]

    def get_paper_by_id(self, paper_id: str) -> Paper:
        """通过 DOI 或版本号获取单篇论文（暂不支持，API 限制）"""
        # 注意：biorxiv API 不提供 by-id 端点，只能通过搜索模拟
        # 这里返回 None 或抛出异常均可，取决于你的使用场景
        raise NotImplementedError("biorxiv/medrxiv API does not support direct ID lookup")

    def _parse_item(self, item: dict) -> Paper:
        try:
            # 提取必要字段
            title = item.get("title", "").strip()
            if not title:
                return None
                
            authors_str = item.get("authors", "")
            authors = [a.strip() for a in authors_str.split(",")] if authors_str else []
            
            abstract = item.get("abstract", "").strip()
            pdf_url = item.get("jatsxml", "").replace(".source.xml", ".full.pdf")
            # 注意：有些条目 jatsxml 为空，可 fallback 到 biorxiv 链接
            if not pdf_url or ".full.pdf" not in pdf_url:
                doi = item.get("doi", "")
                if doi:
                    pdf_url = f"https://www.{self.source}.org/content/{doi}.full.pdf"
            
            published = item.get("date", "")  # 格式: "2023-10-05"
            
            # 构造 paper_id（使用 DOI）
            paper_id = item.get("doi", "").replace("10.1101/", "")
            
            return Paper(
                paper_id=paper_id,
                title=title,
                authors=authors,
                abstract=abstract,
                pdf_url=pdf_url,
                published=published,
                source=self.source
            )
        except Exception as e:
            print(f"Parse error: {e}")
            return None
from abc import ABC, abstractmethod
from typing import List, Dict

class Paper:
    """统一论文数据模型"""
    def __init__(self, 
                 paper_id: str,
                 title: str,
                 authors: List[str],
                 abstract: str,
                 pdf_url: str,
                 published: str,      # ISO 8601 日期字符串
                 source: str):        # "arxiv", "biorxiv", "medrxiv"
        self.paper_id = paper_id
        self.title = title
        self.authors = authors
        self.abstract = abstract
        self.pdf_url = pdf_url
        self.published = published
        self.source = source

    def to_dict(self):
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "pdf_url": self.pdf_url,
            "published": self.published,
            "source": self.source
        }

class PaperFetcher(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> List[Paper]:
        pass

    @abstractmethod
    def get_paper_by_id(self, paper_id: str) -> Paper:
        pass
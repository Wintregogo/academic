# fetchers/__init__.py
from .base import Paper, PaperFetcher
from .arxiv_fetcher import ArxivFetcher
from .biorxiv_medrxiv import BiorxivMedrxivFetcher
from .multi_platform_fetcher import search_across_platforms
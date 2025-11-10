"""
工具模块：提供查询、分析和巡检功能
"""

from .analyze import (
    analyze_abstracts_by_days,
    analyze_authors_by_days,
    analyze_oa_status_by_days,
    analyze_venues_by_days,
    get_papers_by_days,
)
from .daily_ingest import daily_ingest_all, daily_ingest_sources
from .download import download_all_papers, download_arxiv_papers, download_oa_papers
from .logging import setup_logging
from .query import (
    query_all_sources_by_days,
    query_arxiv_by_days,
    query_crossref_by_days,
    query_europe_pmc_by_days,
    query_unpaywall_by_days,
)

__all__ = [
    # 查询功能
    "query_arxiv_by_days",
    "query_crossref_by_days",
    "query_europe_pmc_by_days",
    "query_unpaywall_by_days",
    "query_all_sources_by_days",
    # 分析功能
    "analyze_authors_by_days",
    "analyze_abstracts_by_days",
    "analyze_oa_status_by_days",
    "analyze_venues_by_days",
    "get_papers_by_days",
    # 巡检功能
    "daily_ingest_all",
    "daily_ingest_sources",
    # 下载功能
    "download_arxiv_papers",
    "download_oa_papers",
    "download_all_papers",
    # 工具函数
    "setup_logging",
]


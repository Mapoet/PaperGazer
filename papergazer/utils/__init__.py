"""
工具模块：提供查询、分析和巡检功能
"""

from importlib import import_module
from typing import Any

__all__ = [
    # 查询功能
    "query_arxiv_by_days",
    "query_crossref_by_days",
    "query_europe_pmc_by_days",
    "query_unpaywall_by_days",
    "query_all_sources_by_days",
    # 搜索功能
    "search_papers_by_author",
    "search_papers_by_venue",
    "search_papers_by_keyword",
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
    "process_fulltext_document",
    "process_fulltext_document_sync",
    "GrobidResult",
    "GrobidDisabledError",
    "fetch_crossref_metadata",
    "fetch_openalex_metadata",
    "fetch_unpaywall_metadata",
    "MetadataFetchError",
    "enrich_crossref_metadata",
    "enrich_openalex_metadata",
    "enrich_unpaywall_metadata",
    "extract_figures_from_tei",
    "extract_tables_from_tei",
    "build_identity_cache",
    "normalize_name",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "analyze_abstracts_by_days": ("papergazer.utils.analyze", "analyze_abstracts_by_days"),
    "analyze_authors_by_days": ("papergazer.utils.analyze", "analyze_authors_by_days"),
    "analyze_oa_status_by_days": ("papergazer.utils.analyze", "analyze_oa_status_by_days"),
    "analyze_venues_by_days": ("papergazer.utils.analyze", "analyze_venues_by_days"),
    "get_papers_by_days": ("papergazer.utils.analyze", "get_papers_by_days"),
    "daily_ingest_all": ("papergazer.utils.daily_ingest", "daily_ingest_all"),
    "daily_ingest_sources": ("papergazer.utils.daily_ingest", "daily_ingest_sources"),
    "download_all_papers": ("papergazer.utils.download", "download_all_papers"),
    "download_arxiv_papers": ("papergazer.utils.download", "download_arxiv_papers"),
    "download_oa_papers": ("papergazer.utils.download", "download_oa_papers"),
    "GrobidDisabledError": ("papergazer.utils.grobid", "GrobidDisabledError"),
    "GrobidResult": ("papergazer.utils.grobid", "GrobidResult"),
    "process_fulltext_document": ("papergazer.utils.grobid", "process_fulltext_document"),
    "process_fulltext_document_sync": (
        "papergazer.utils.grobid",
        "process_fulltext_document_sync",
    ),
    "build_identity_cache": ("papergazer.utils.identity", "build_cache"),
    "normalize_name": ("papergazer.utils.identity", "normalize_name"),
    "setup_logging": ("papergazer.utils.logging", "setup_logging"),
    "MetadataFetchError": ("papergazer.utils.metadata", "MetadataFetchError"),
    "enrich_crossref_metadata": ("papergazer.utils.metadata", "enrich_crossref_metadata"),
    "enrich_openalex_metadata": ("papergazer.utils.metadata", "enrich_openalex_metadata"),
    "enrich_unpaywall_metadata": ("papergazer.utils.metadata", "enrich_unpaywall_metadata"),
    "fetch_crossref_metadata": ("papergazer.utils.metadata", "fetch_crossref_metadata"),
    "fetch_openalex_metadata": ("papergazer.utils.metadata", "fetch_openalex_metadata"),
    "fetch_unpaywall_metadata": ("papergazer.utils.metadata", "fetch_unpaywall_metadata"),
    "query_all_sources_by_days": ("papergazer.utils.query", "query_all_sources_by_days"),
    "query_arxiv_by_days": ("papergazer.utils.query", "query_arxiv_by_days"),
    "query_crossref_by_days": ("papergazer.utils.query", "query_crossref_by_days"),
    "query_europe_pmc_by_days": ("papergazer.utils.query", "query_europe_pmc_by_days"),
    "query_unpaywall_by_days": ("papergazer.utils.query", "query_unpaywall_by_days"),
    "search_papers_by_author": ("papergazer.utils.query", "search_papers_by_author"),
    "search_papers_by_keyword": ("papergazer.utils.query", "search_papers_by_keyword"),
    "search_papers_by_venue": ("papergazer.utils.query", "search_papers_by_venue"),
    "extract_figures_from_tei": ("papergazer.utils.tei", "extract_figures_from_tei"),
    "extract_tables_from_tei": ("papergazer.utils.tei", "extract_tables_from_tei"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

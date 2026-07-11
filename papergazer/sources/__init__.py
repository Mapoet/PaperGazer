"""
数据源模块：封装各数据源的 API 调用与数据解析
"""

from .arxiv import query_arxiv, query_arxiv_batch
from .crossref import fetch_crossref_by_doi, fetch_crossref_issn_increment
from .europe_pmc import doi_to_pmcid, fetch_fulltext_xml, search_articles_by_date
from .unpaywall import best_oa

__all__ = [
    "query_arxiv",
    "query_arxiv_batch",
    "fetch_crossref_issn_increment",
    "fetch_crossref_by_doi",
    "best_oa",
    "doi_to_pmcid",
    "fetch_fulltext_xml",
    "search_articles_by_date",
]

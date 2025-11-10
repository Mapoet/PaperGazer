"""
数据源模块：封装各数据源的 API 调用与数据解析
"""

from .arxiv import query_arxiv
from .crossref import fetch_crossref_issn_increment
from .unpaywall import best_oa
from .europe_pmc import doi_to_pmcid, fetch_fulltext_xml

__all__ = [
    "query_arxiv",
    "fetch_crossref_issn_increment",
    "best_oa",
    "doi_to_pmcid",
    "fetch_fulltext_xml",
]


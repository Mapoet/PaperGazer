"""
分析模块聚合
"""

from papergazer.analytics.citation import build_citation_graph
from papergazer.analytics.concepts import analyze_concepts
from papergazer.analytics.oa import monitor_oa

__all__ = [
    "build_citation_graph",
    "analyze_concepts",
    "monitor_oa",
]


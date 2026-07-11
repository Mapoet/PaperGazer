"""
分析模块聚合
"""

from papergazer.analytics.citation import (
    analyze_collaboration_network,
    build_citation_graph,
    summarize_citation_network,
)
from papergazer.analytics.concepts import analyze_concepts
from papergazer.analytics.oa import monitor_oa
from papergazer.analytics.topics import analyze_topic_trends

__all__ = [
    "build_citation_graph",
    "summarize_citation_network",
    "analyze_collaboration_network",
    "analyze_concepts",
    "analyze_topic_trends",
    "monitor_oa",
]

"""
引用网络分析
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from papergazer.config import Settings
from papergazer.store.db import (
    AffiliationIdentity,
    CitationEdge,
    PaperItem,
    get_session,
    init_db,
)
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)

try:  # Optional dependency
    import networkx as nx
except ImportError:  # pragma: no cover - 当缺失 networkx 时提示
    nx = None


def build_citation_graph(
    config: Settings,
    *,
    since_days: int | None = None,
    sources: list[str] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    resolve_local: bool = False,
) -> dict[str, int]:
    """
    根据 references_json 构建引用边

    Args:
        config: 全局配置
        since_days: 仅处理最近 N 天的论文
        sources: 数据源过滤
        limit: 限制处理论文数量
        dry_run: 仅统计、不写入
        force: 重建引用边（删除已有记录）
        resolve_local: 尝试匹配本地论文 ID
    """
    init_db(config.store.db_path)
    session = get_session()

    try:
        query = session.query(PaperItem).filter(PaperItem.references_json.isnot(None))

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        if since_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=since_days)
            query = query.filter(get_effective_date_filter(cutoff))

        query = query.order_by(PaperItem.ingested_at.desc().nullslast())

        if limit:
            query = query.limit(limit)

        papers = query.all()

        stats = {
            "papers": len(papers),
            "edges": 0,
            "resolved": 0,
            "skipped": 0,
        }

        for paper in papers:
            if not paper.references_json:
                stats["skipped"] += 1
                continue
            try:
                references = json.loads(paper.references_json)
            except (json.JSONDecodeError, TypeError):
                stats["skipped"] += 1
                continue

            if not references:
                stats["skipped"] += 1
                continue

            if not dry_run and force:
                session.query(CitationEdge).filter_by(paper_id=paper.id).delete()
                session.flush()

            for ref in references:
                doi = (ref.get("DOI") or ref.get("doi") or ref.get("doi-asserted-by") or "").strip()

                if not doi:
                    continue

                relation_type = ref.get("reference-type") or ref.get("relation-type")
                raw_json = json.dumps(ref, ensure_ascii=False)
                cited_paper_id = None

                if resolve_local:
                    match = session.query(PaperItem).filter(PaperItem.doi == doi.lower()).first()
                    if match:
                        cited_paper_id = match.id
                        stats["resolved"] += 1

                stats["edges"] += 1

                if dry_run:
                    continue

                session.add(
                    CitationEdge(
                        paper_id=paper.id,
                        cited_paper_id=cited_paper_id,
                        cited_doi=doi.lower(),
                        relation_type=relation_type,
                        raw_reference_json=raw_json,
                    )
                )

            if not dry_run:
                session.commit()

    finally:
        session.close()

    logger.info(
        "引用网络构建完成：论文 %s，新增引用 %s，关联本地 %s，跳过 %s，dry_run=%s",
        stats["papers"],
        stats["edges"],
        stats["resolved"],
        stats["skipped"],
        dry_run,
    )

    return stats


def summarize_citation_network(
    config: Settings,
    *,
    since_days: int | None = None,
    max_nodes: int = 10,
) -> dict[str, object]:
    """
    利用 networkx 计算引用网络指标。

    Args:
        config: 全局配置
        since_days: 仅统计最近 N 天写入的引用
        max_nodes: 返回的 Top-N 节点数
    """

    if nx is None:
        raise RuntimeError("请安装 networkx 以启用引用网络分析：`pip install networkx`。")

    init_db(config.store.db_path)
    session = get_session()

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=since_days) if since_days else None

    stats: dict[str, Any] = {
        "nodes": 0,
        "edges": 0,
        "pagerank": [],
        "in_degree": [],
        "since": cutoff.isoformat() if cutoff else None,
    }

    try:
        query = session.query(CitationEdge)
        if cutoff is not None:
            query = query.filter(CitationEdge.created_at >= cutoff)

        edges = query.all()
        if not edges:
            return stats

        graph = nx.DiGraph()

        local_titles = {
            paper.id: paper.title for paper in session.query(PaperItem.id, PaperItem.title)
        }

        for edge in edges:
            source_node = f"paper:{edge.paper_id}"
            target_node = (
                f"paper:{edge.cited_paper_id}" if edge.cited_paper_id else f"doi:{edge.cited_doi}"
            )
            graph.add_edge(source_node, target_node, weight=edge.weight or 1)

        stats["nodes"] = graph.number_of_nodes()
        stats["edges"] = graph.number_of_edges()

        pagerank = nx.pagerank(graph, weight="weight")
        in_degrees = dict(graph.in_degree(weight="weight"))

        def _label(node: str) -> str:
            if node.startswith("paper:"):
                pid = int(node.split(":", 1)[1])
                return local_titles.get(pid) or f"paper#{pid}"
            return node

        stats["pagerank"] = [
            {"node": node, "label": _label(node), "score": score}
            for node, score in sorted(pagerank.items(), key=lambda kv: kv[1], reverse=True)[
                :max_nodes
            ]
        ]

        stats["in_degree"] = [
            {"node": node, "label": _label(node), "score": score}
            for node, score in sorted(in_degrees.items(), key=lambda kv: kv[1], reverse=True)[
                :max_nodes
            ]
        ]

        logger.info(
            "引用网络指标：节点 %s，边 %s，since=%s",
            stats["nodes"],
            stats["edges"],
            stats["since"],
        )
        return stats
    finally:
        session.close()


def analyze_collaboration_network(
    config: Settings,
    *,
    since_days: int | None = None,
    min_weight: int = 1,
    top: int = 20,
) -> dict[str, object]:
    """
    基于标准化机构信息的合作网络统计。

    Args:
        config: 全局配置
        since_days: 仅统计最近 N 天的论文
        min_weight: 至少需要合作次数
        top: 返回前 N 个合作边
    """

    init_db(config.store.db_path)
    session = get_session()

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=since_days) if since_days else None

    stats: dict[str, Any] = {
        "since": cutoff.isoformat() if cutoff else None,
        "edges": [],
        "papers": 0,
    }

    try:
        query = session.query(PaperItem.id)
        if cutoff is not None:
            query = query.filter(get_effective_date_filter(cutoff))

        paper_ids = [row[0] for row in query.all()]
        stats["papers"] = len(paper_ids)
        if not paper_ids:
            return stats

        affiliations = (
            session.query(
                AffiliationIdentity.paper_id,
                AffiliationIdentity.normalized_name,
                AffiliationIdentity.ror_id,
                AffiliationIdentity.country_code,
            )
            .filter(AffiliationIdentity.paper_id.in_(paper_ids))
            .all()
        )

        per_paper: dict[int, list[tuple[str, str]]] = defaultdict(list)
        for paper_id, name, ror_id, country in affiliations:
            label = ror_id or (name.strip() if name else None)
            if not label:
                continue
            per_paper[paper_id].append((label, country or ""))

        edge_counter: dict[tuple[str, str], int] = defaultdict(int)
        for institutions in per_paper.values():
            node_map = {}
            for label, country in institutions:
                node_map[label] = country
            node_labels = sorted(node_map.keys())
            for i, src in enumerate(node_labels):
                for dst in node_labels[i + 1 :]:
                    edge_counter[(src, dst)] += 1

        filtered_edges: list[dict[str, str | int]] = [
            {"source": src, "target": dst, "weight": weight}
            for (src, dst), weight in edge_counter.items()
            if weight >= min_weight
        ]

        filtered_edges.sort(key=lambda item: int(item["weight"]), reverse=True)
        stats["edges"] = filtered_edges[:top]
        logger.info("机构合作网络：统计 %s 条边，since=%s", len(filtered_edges), stats["since"])
        return stats
    finally:
        session.close()

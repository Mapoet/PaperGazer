"""
概念热度分析
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from papergazer.config import Settings
from papergazer.store.db import ConceptMetric, PaperItem, get_session, init_db
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)


def analyze_concepts(
    config: Settings,
    *,
    window_days: int = 30,
    since_days: int | None = None,
    limit: int | None = None,
    sources: list[str] | None = None,
    top: int = 20,
    persist: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """
    分析概念热度

    Args:
        config: 全局配置
        window_days: 滑动窗口天数
        since_days: 仅统计最近 N 天（覆盖 window_days）
        limit: 限制论文数量
        sources: 数据源过滤
        top: 输出 Top-N 概念
        persist: 是否写入 analytics_concepts
        dry_run: 仅统计，不写入

    Returns:
        dict 包含 window 和概念信息
    """
    init_db(config.store.db_path)
    session = get_session()

    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(days=window_days)

    try:
        query = session.query(PaperItem).filter(PaperItem.concepts_json.isnot(None))

        if since_days is not None:
            cutoff = window_end - timedelta(days=since_days)
            query = query.filter(get_effective_date_filter(cutoff))
            window_start = cutoff
        else:
            query = query.filter(get_effective_date_filter(window_start))

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        query = query.order_by(PaperItem.ingested_at.desc().nullslast())

        if limit:
            query = query.limit(limit)

        papers = query.all()

        counts: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "score_sum": 0.0, "name": "", "level": None}
        )

        for paper in papers:
            if not paper.concepts_json:
                continue
            try:
                concepts = json.loads(paper.concepts_json)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(concepts, list):
                continue

            for concept in concepts:
                concept_id = concept.get("id") or concept.get("concept_id")
                display_name = concept.get("display_name") or concept.get("name")
                level = concept.get("level")
                score = float(concept.get("score") or 0.0)

                if not concept_id or not display_name:
                    continue

                key = concept_id.lower()
                counts[key]["count"] += 1
                counts[key]["score_sum"] += score
                counts[key]["name"] = display_name
                counts[key]["level"] = level

        top_concepts: list[tuple[str, dict[str, float]]] = sorted(
            counts.items(),
            key=lambda kv: (kv[1]["count"], kv[1]["score_sum"]),
            reverse=True,
        )[:top]

        metrics = []
        for concept_id, info in top_concepts:
            count = int(info["count"])
            avg_score = info["score_sum"] / count if count else 0.0
            metrics.append(
                {
                    "concept_id": concept_id,
                    "concept_name": info["name"],
                    "concept_level": info["level"],
                    "paper_count": count,
                    "avg_score": avg_score,
                }
            )

        if persist and not dry_run:
            session.query(ConceptMetric).filter(
                ConceptMetric.window_start == window_start,
                ConceptMetric.window_end == window_end,
            ).delete()

            for entry in metrics:
                session.add(
                    ConceptMetric(
                        concept_id=entry["concept_id"],
                        concept_name=entry["concept_name"],
                        concept_level=entry["concept_level"],
                        paper_count=entry["paper_count"],
                        avg_score=f"{entry['avg_score']:.4f}",
                        window_start=window_start,
                        window_end=window_end,
                        metadata_json=None,
                    )
                )
            session.commit()

        result = {
            "window_start": window_start,
            "window_end": window_end,
            "concepts": metrics,
            "persisted": bool(persist and not dry_run),
            "papers": len(papers),
        }

        logger.info(
            "概念分析完成：窗口 %s-%s，概念数 %s，写入=%s",
            window_start.date(),
            window_end.date(),
            len(metrics),
            result["persisted"],
        )
        return result
    finally:
        session.close()

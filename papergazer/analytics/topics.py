"""
基于 OpenAlex concepts 的主题演化分析。

利用 `PaperItem.concepts_json` 与发表时间，统计每个概念在时间序列
上的出现频次，并给出近期增量最大的主题。
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from typing import Deque, Dict, List, Optional, Tuple

from papergazer.config import Settings
from papergazer.store.db import PaperItem, get_session, init_db
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)

PeriodKey = Tuple[int, Optional[int]]


def _period_from_date(value: date | None, granularity: str) -> PeriodKey:
    if value is None:
        return (0, None)
    if granularity == "quarter":
        return (value.year, (value.month - 1) // 3 + 1)
    return (value.year, None)


def analyze_topic_trends(
    config: Settings,
    *,
    granularity: str = "year",
    since_years: int = 3,
    top: int = 15,
    min_support: int = 3,
    sources: Optional[List[str]] = None,
) -> Dict[str, object]:
    """
    统计主题热度趋势。

    Args:
        config: 全局配置
        granularity: `year` 或 `quarter`
        since_years: 统计起始跨度
        top: 返回前 N 个涨幅显著的主题
        min_support: 最少论文数过滤
        sources: 数据源过滤
    """

    if granularity not in {"year", "quarter"}:
        raise ValueError("granularity 仅支持 'year' 或 'quarter'")

    init_db(config.store.db_path)
    session = get_session()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=since_years * 365)

    stats: Dict[str, object] = {
        "granularity": granularity,
        "since": cutoff.date(),
        "top": top,
        "concepts": [],
        "papers": 0,
    }

    try:
        query = session.query(PaperItem).filter(PaperItem.concepts_json.isnot(None))
        query = query.filter(get_effective_date_filter(cutoff))
        if sources:
            query = query.filter(PaperItem.source.in_(sources))
        query = query.order_by(PaperItem.published_date.desc().nullslast())

        papers = query.all()
        stats["papers"] = len(papers)

        timeline: Dict[str, Dict[PeriodKey, int]] = defaultdict(lambda: defaultdict(int))
        concept_meta: Dict[str, Dict[str, object]] = {}

        for paper in papers:
            try:
                concepts = json.loads(paper.concepts_json)
            except (json.JSONDecodeError, TypeError):
                continue

            paper_date = paper.published_date or (
                paper.updated_date.date() if paper.updated_date else None
            )
            period = _period_from_date(paper_date, granularity)
            if period[0] == 0:
                continue

            for concept in concepts if isinstance(concepts, list) else []:
                concept_id = concept.get("id") or concept.get("concept_id")
                concept_name = concept.get("display_name") or concept.get("name")
                if not concept_id or not concept_name:
                    continue
                key = concept_id.lower()
                timeline[key][period] += 1
                concept_meta.setdefault(
                    key,
                    {
                        "concept_name": concept_name,
                        "concept_level": concept.get("level"),
                    },
                )

        trend_entries = []
        for concept_id, period_counts in timeline.items():
            total = sum(period_counts.values())
            if total < min_support:
                continue

            ordered_periods = sorted(period_counts.keys())
            if len(ordered_periods) < 2:
                continue

            latest = ordered_periods[-1]
            prev = ordered_periods[-2]
            latest_count = period_counts[latest]
            prev_count = period_counts[prev]
            growth = (latest_count - prev_count) / max(prev_count, 1)

            history: Deque[Tuple[str, int]] = deque()
            for p in ordered_periods:
                label = f"{p[0]}Q{p[1]}" if granularity == "quarter" and p[1] else str(p[0])
                history.append((label, period_counts[p]))

            trend_entries.append(
                {
                    "concept_id": concept_id,
                    "concept_name": concept_meta[concept_id]["concept_name"],
                    "concept_level": concept_meta[concept_id].get("concept_level"),
                    "latest_period": history[-1][0],
                    "latest_count": latest_count,
                    "previous_period": history[-2][0],
                    "previous_count": prev_count,
                    "growth_rate": growth,
                    "history": list(history),
                }
            )

        trend_entries.sort(
            key=lambda item: (item["growth_rate"], item["latest_count"]), reverse=True
        )
        stats["concepts"] = trend_entries[:top]
        logger.info(
            "主题趋势分析完成：统计 %s 篇论文，输出 %s 个概念",
            stats["papers"],
            len(stats["concepts"]),
        )
        return stats
    finally:
        session.close()

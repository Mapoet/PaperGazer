"""
引用网络分析
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from papergazer.config import Settings
from papergazer.store.db import CitationEdge, PaperItem, get_session, init_db
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)


def build_citation_graph(
    config: Settings,
    *,
    since_days: Optional[int] = None,
    sources: Optional[list[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
    resolve_local: bool = False,
) -> Dict[str, int]:
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
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
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
                doi = (
                    ref.get("DOI")
                    or ref.get("doi")
                    or ref.get("doi-asserted-by")
                    or ""
                ).strip()

                if not doi:
                    continue

                relation_type = ref.get("reference-type") or ref.get("relation-type")
                raw_json = json.dumps(ref, ensure_ascii=False)
                cited_paper_id = None

                if resolve_local:
                    match = (
                        session.query(PaperItem)
                        .filter(PaperItem.doi == doi.lower())
                        .first()
                    )
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


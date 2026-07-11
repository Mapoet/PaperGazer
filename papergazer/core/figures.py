"""
图表抽取核心逻辑
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from papergazer.config import Settings
from papergazer.store.db import PaperItem, get_session, init_db
from papergazer.utils.tei import extract_figures_from_tei, extract_tables_from_tei

logger = logging.getLogger(__name__)


def extract_figures_and_tables(
    config: Settings,
    *,
    since_days: int | None = None,
    limit: int | None = None,
    sources: Iterable[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    only_missing: bool = True,
    max_per_paper: int | None = None,
) -> dict:
    """
    从 TEI 文件中抽取并保存图/表信息

    Args:
        config: 全局配置
        since_days: 仅处理最近 N 天的论文
        limit: 限制处理的论文数量
        sources: 数据源过滤
        dry_run: 仅预览，不写入数据库
        force: 强制重建（忽略已有 figures/tables）
        only_missing: 仅处理缺失图表数据的论文
        max_per_paper: 每篇论文最多保存的图表数量

    Returns:
        统计信息字典
    """
    init_db(config.store.db_path)
    max_slots = max_per_paper or config.figures.max_per_paper

    if not config.figures.enabled:
        logger.warning("figures.enabled 为 false，将继续执行但建议在配置中启用。")

    session = get_session()
    try:
        query = session.query(PaperItem).filter(PaperItem.tei_path.isnot(None))

        if sources:
            query = query.filter(PaperItem.source.in_(list(sources)))

        if since_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=since_days)
            query = query.filter(
                PaperItem.ingested_at.isnot(None),
                PaperItem.ingested_at >= cutoff,
            )

        if only_missing and not force:
            query = query.filter(
                (PaperItem.figures_json.is_(None)) | (PaperItem.figures_json == "")
            ).filter((PaperItem.tables_json.is_(None)) | (PaperItem.tables_json == ""))

        query = query.order_by(PaperItem.ingested_at.desc().nullslast())

        if limit:
            query = query.limit(limit)

        papers = query.all()

        stats = {
            "papers": len(papers),
            "processed": 0,
            "skipped": 0,
            "figures": 0,
            "tables": 0,
            "dry_run": dry_run,
        }

        for paper in papers:
            tei_path = Path(paper.tei_path) if paper.tei_path else None
            if not tei_path or not tei_path.exists():
                logger.warning("TEI 文件缺失，跳过 %s", paper.identifier)
                stats["skipped"] += 1
                continue

            figures = extract_figures_from_tei(tei_path)
            tables = extract_tables_from_tei(tei_path)

            if max_slots:
                figures = figures[:max_slots]
                tables = tables[:max_slots]

            stats["figures"] += len(figures)
            stats["tables"] += len(tables)
            stats["processed"] += 1

            if dry_run:
                continue

            paper.figures_json = json.dumps(figures, ensure_ascii=False)
            paper.tables_json = json.dumps(tables, ensure_ascii=False)
            session.add(paper)
            session.commit()

    finally:
        session.close()

    if stats["processed"] == 0 and stats["papers"] == 0:
        logger.info("未找到符合条件的论文进行图表抽取")
    else:
        logger.info(
            "图表抽取完成：处理 %s 篇（figures=%s, tables=%s, skipped=%s, dry_run=%s)",
            stats["processed"],
            stats["figures"],
            stats["tables"],
            stats["skipped"],
            dry_run,
        )

    return stats

"""
全文处理核心逻辑：批量生成 TEI 文件
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from papergazer.config import Settings
from papergazer.store.db import PaperItem, get_session, init_db
from papergazer.utils.grobid import GrobidDisabledError, process_fulltext_document

logger = logging.getLogger(__name__)


async def generate_tei_for_papers(
    config: Settings,
    *,
    limit: int | None = None,
    since_days: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    output_dir: Path | None = None,
) -> dict:
    """
    为数据库中的论文生成 TEI 文件。

    Args:
        config: 全局配置
        limit: 限制处理的论文数量
        since_days: 仅处理最近 N 天新增的论文
        force: 即使已有 TEI 也重新生成
        dry_run: 仅输出计划，不写入数据库/文件
        output_dir: 覆盖默认的 TEI 输出目录

    Returns:
        统计信息字典
    """
    init_db(config.store.db_path)
    session = get_session()

    stats = {
        "papers": 0,
        "processed": 0,
        "success": 0,
        "skipped": 0,
        "dry_run": dry_run,
    }

    try:
        query = session.query(PaperItem)
        if not force:
            query = query.filter((PaperItem.tei_path.is_(None)) | (PaperItem.tei_path == ""))
        if since_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=since_days)
            query = query.filter(PaperItem.ingested_at.isnot(None)).filter(
                PaperItem.ingested_at >= cutoff
            )
        query = query.order_by(PaperItem.ingested_at.desc().nullslast())
        if limit:
            query = query.limit(limit)

        papers = query.all()
        stats["papers"] = len(papers)

        if not papers:
            logger.info("没有符合条件的论文需要生成 TEI。")
            return stats

        logger.info("准备处理 %s 篇论文以生成 TEI（dry-run=%s）", len(papers), dry_run)

        for paper in papers:
            stats["processed"] += 1
            identifier = paper.doi or paper.identifier

            if not paper.pdf_path:
                logger.debug("缺少 pdf_path，跳过: %s", identifier)
                stats["skipped"] += 1
                continue

            pdf_path = Path(paper.pdf_path)
            if not pdf_path.is_file():
                logger.debug("PDF 文件不存在，跳过: %s", pdf_path)
                stats["skipped"] += 1
                continue

            if dry_run:
                logger.debug("dry-run: 将处理 #%s (%s)", paper.id, identifier)
                stats["success"] += 1
                continue

            try:
                result = await process_fulltext_document(
                    config,
                    pdf_path=pdf_path,
                    document_id=identifier.replace("/", "_"),
                    output_dir=output_dir,
                    save=True,
                )
            except GrobidDisabledError:
                logger.warning("GROBID 未启用，无法处理 PDF：%s", identifier)
                stats["skipped"] += 1
                continue
            except Exception as exc:
                logger.exception("生成 TEI 失败 (%s): %s", identifier, exc)
                stats["skipped"] += 1
                continue

            if result.tei_path:
                paper.tei_path = str(Path(result.tei_path).as_posix())
                session.add(paper)
                session.commit()
                stats["success"] += 1
                logger.debug("TEI 生成成功: %s", paper.tei_path)
            else:
                logger.warning("未生成 TEI 文件: %s", identifier)
                stats["skipped"] += 1

    finally:
        session.close()

    logger.info(
        "TEI 生成完成：共处理 %s 篇，成功 %s，跳过 %s（dry-run=%s）",
        stats["processed"],
        stats["success"],
        stats["skipped"],
        dry_run,
    )
    return stats

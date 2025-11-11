#!/usr/bin/env python3
"""
批量生成 TEI 全文：
- 遍历数据库中缺少 TEI 的论文
- 调用 papergazer.utils.process_fulltext_document
- 保存生成的 TEI 文件并更新数据库记录
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from papergazer.config import load_config  # noqa: E402
from papergazer.store.db import get_session, init_db, PaperItem  # noqa: E402
from papergazer.utils import (  # noqa: E402
    GrobidDisabledError,
    process_fulltext_document,
    setup_logging,
)

logger = logging.getLogger("process_fulltext_batch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量生成 TEI 全文（依赖 GROBID 或文本/已有 XML）",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config.test.yaml",
        help="配置文件路径（默认：configs/config.test.yaml）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="处理的最大论文数量（默认：100）",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        help="仅处理最近 N 天新增的论文",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使已有 tei_path 也重新生成",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出计划，不写入数据库/文件",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="覆盖默认 TEI 输出目录",
    )
    return parser.parse_args()


async def process_batch(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    setup_logging(config.logging)

    if not config.grobid.enabled:
        logger.warning("GROBID 未启用，将仅对有文本/XML 的条目进行包装")

    init_db(config.store.db_path)
    session = get_session()

    try:
        query = session.query(PaperItem)
        if not args.force:
            query = query.filter((PaperItem.tei_path.is_(None)) | (PaperItem.tei_path == ""))
        if args.since_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.since_days)
            query = query.filter(PaperItem.ingested_at >= cutoff)
        query = query.order_by(PaperItem.ingested_at.desc())
        if args.limit:
            query = query.limit(args.limit)

        papers = query.all()
        if not papers:
            logger.info("没有符合条件的论文需要处理。")
            return

        logger.info("准备处理 %s 篇论文（dry-run=%s）", len(papers), args.dry_run)

        processed = 0
        success = 0
        skipped = 0

        for paper in papers:
            processed += 1
            identifier = paper.doi or paper.identifier
            logger.info("开始处理 #%s (%s)", paper.id, identifier)

            if paper.pdf_path:
                pdf_path = Path(paper.pdf_path)
                if not pdf_path.is_file():
                    logger.warning("PDF 文件不存在，跳过: %s", pdf_path)
                    skipped += 1
                    continue
            else:
                logger.warning("缺少 pdf_path，无文本可解析，跳过: %s", identifier)
                skipped += 1
                continue

            if args.dry_run:
                logger.info("dry-run 模式：已预估将生成 TEI 至 %s", args.output_dir or config.grobid.output_dir)
                continue

            try:
                result = await process_fulltext_document(
                    config,
                    pdf_path=pdf_path,
                    document_id=identifier.replace("/", "_"),
                    output_dir=Path(args.output_dir) if args.output_dir else None,
                    save=True,
                )
            except GrobidDisabledError:
                logger.error("GROBID 未启用，无法处理 PDF：%s", identifier)
                skipped += 1
                continue
            except Exception as exc:
                logger.exception("生成 TEI 失败 (%s): %s", identifier, exc)
                skipped += 1
                continue

            if result.tei_path:
                paper.tei_path = str(Path(result.tei_path).as_posix())
                session.add(paper)
                session.commit()
                success += 1
                logger.info("TEI 生成成功: %s", paper.tei_path)
            else:
                logger.warning("未生成 TEI 文件: %s", identifier)
                skipped += 1

        logger.info(
            "批处理完成：共处理 %s 篇，成功 %s，跳过/失败 %s",
            processed,
            success,
            skipped,
        )

    finally:
        session.close()


def main() -> None:
    args = parse_args()
    asyncio.run(process_batch(args))


if __name__ == "__main__":
    main()


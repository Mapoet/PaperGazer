"""
论文下载工具
支持批量下载 arXiv 或其他 OA 来源的论文
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_

from papergazer.config import Settings
from papergazer.core.fetch import fetch_by_identifier
from papergazer.store.db import PaperItem, get_session
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)


async def download_arxiv_papers(
    config: Settings,
    days: int | None = None,
    limit: int | None = None,
) -> dict:
    """
    下载 arXiv 论文

    Args:
        config: 应用配置
        days: 下载最近 N 天的论文，如果为 None 则下载所有未下载的
        limit: 限制下载数量

    Returns:
        下载统计信息
    """
    logger.info("开始下载 arXiv 论文")

    session = get_session()
    try:
        # 查询需要下载的 arXiv 论文
        query = session.query(PaperItem).filter_by(source="arxiv")

        # 过滤已下载的论文（pdf_path 为空或 None）
        query = query.filter(or_(PaperItem.pdf_path.is_(None), PaperItem.pdf_path == ""))

        # 如果指定了天数，只下载最近 N 天的
        if days:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            query = query.filter(get_effective_date_filter(cutoff_date))

        # 按更新日期排序
        query = query.order_by(PaperItem.updated_date.desc())

        if limit:
            query = query.limit(limit)

        items = query.all()

        logger.info(f"找到 {len(items)} 篇需要下载的 arXiv 论文")

        success_count = 0
        error_count = 0
        skipped_count = 0

        for item in items:
            if not item.doi:
                skipped_count += 1
                continue
            try:
                # 使用 identifier（arXiv ID）下载
                result = await fetch_by_identifier(item.identifier, config)

                if result["success"]:
                    success_count += 1
                    logger.info(
                        f"✅ 下载成功: {item.identifier} -> {result.get('pdf_path', 'N/A')}"
                    )
                else:
                    error_count += 1
                    logger.warning(
                        f"❌ 下载失败: {item.identifier} - {result.get('error', '未知错误')}"
                    )

                # 添加小延迟，避免请求过快
                await asyncio.sleep(0.5)

            except Exception as e:
                error_count += 1
                logger.error(f"下载论文失败 {item.identifier}: {e}", exc_info=True)

        return {
            "total": len(items),
            "success": success_count,
            "error": error_count,
            "skipped": skipped_count,
        }
    finally:
        session.close()


async def download_oa_papers(
    config: Settings,
    days: int | None = None,
    limit: int | None = None,
    sources: list[str] | None = None,
) -> dict:
    """
    下载开放获取论文（通过 Unpaywall 或其他 OA 来源）

    Args:
        config: 应用配置
        days: 下载最近 N 天的论文，如果为 None 则下载所有未下载的
        limit: 限制下载数量
        sources: 数据源列表，如果为 None 则下载所有 OA 来源

    Returns:
        下载统计信息
    """
    logger.info("开始下载开放获取论文")

    session = get_session()
    try:
        # 查询需要下载的 OA 论文
        query = session.query(PaperItem).filter(
            and_(
                PaperItem.is_oa,
                PaperItem.doi.isnot(None),
                PaperItem.doi != "",
                or_(PaperItem.pdf_path.is_(None), PaperItem.pdf_path == ""),
            )
        )

        # 如果指定了数据源
        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        # 如果指定了天数
        if days:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            query = query.filter(get_effective_date_filter(cutoff_date))

        # 按更新日期排序
        query = query.order_by(PaperItem.updated_date.desc())

        if limit:
            query = query.limit(limit)

        items = query.all()

        logger.info(f"找到 {len(items)} 篇需要下载的 OA 论文")

        success_count = 0
        error_count = 0
        skipped_count = 0

        for item in items:
            doi = item.doi
            if not doi:
                skipped_count += 1
                continue
            try:
                # 使用 DOI 下载
                result = await fetch_by_identifier(doi, config)

                if result["success"]:
                    success_count += 1
                    logger.info(
                        f"✅ 下载成功: {item.doi} -> {result.get('pdf_path', result.get('xml_path', 'N/A'))}"
                    )
                else:
                    error_count += 1
                    logger.warning(f"❌ 下载失败: {item.doi} - {result.get('error', '未知错误')}")

                # 添加小延迟，避免请求过快
                await asyncio.sleep(0.5)

            except Exception as e:
                error_count += 1
                logger.error(f"下载论文失败 {item.doi}: {e}", exc_info=True)

        return {
            "total": len(items),
            "success": success_count,
            "error": error_count,
            "skipped": skipped_count,
        }
    finally:
        session.close()


async def download_all_papers(
    config: Settings,
    days: int | None = None,
    limit: int | None = None,
    include_arxiv: bool = True,
    include_oa: bool = True,
) -> dict:
    """
    下载所有可用的论文（arXiv + OA）

    Args:
        config: 应用配置
        days: 下载最近 N 天的论文
        limit: 限制下载数量（每个来源）
        include_arxiv: 是否包含 arXiv 论文
        include_oa: 是否包含 OA 论文

    Returns:
        下载统计信息
    """
    logger.info("开始下载所有可用论文")

    results = {}

    if include_arxiv:
        try:
            arxiv_stats = await download_arxiv_papers(config, days=days, limit=limit)
            results["arxiv"] = arxiv_stats
        except Exception as e:
            logger.error(f"arXiv 下载失败: {e}", exc_info=True)
            results["arxiv"] = {"total": 0, "success": 0, "error": 0, "skipped": 0}

    if include_oa:
        try:
            oa_stats = await download_oa_papers(config, days=days, limit=limit)
            results["oa"] = oa_stats
        except Exception as e:
            logger.error(f"OA 下载失败: {e}", exc_info=True)
            results["oa"] = {"total": 0, "success": 0, "error": 0, "skipped": 0}

    total_success = sum(r.get("success", 0) for r in results.values())
    total_error = sum(r.get("error", 0) for r in results.values())
    total = sum(r.get("total", 0) for r in results.values())

    return {
        "results": results,
        "total": total,
        "total_success": total_success,
        "total_error": total_error,
    }

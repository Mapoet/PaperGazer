"""
每日巡检任务工具
支持定时执行多数据源的增量抓取
"""

import asyncio
import logging
from datetime import datetime, timezone

from papergazer.config import Settings
from papergazer.core.ingest import ingest_arxiv, ingest_crossref
from papergazer.store.db import init_db
from papergazer.utils.query import query_europe_pmc_by_days, query_unpaywall_by_days

logger = logging.getLogger(__name__)


async def daily_ingest_all(config: Settings) -> dict:
    """
    执行每日巡检任务（所有数据源）

    Args:
        config: 应用配置

    Returns:
        各数据源的巡检结果
    """
    logger.info("开始执行每日巡检任务")

    # 初始化数据库
    init_db(config.store.db_path)
    logger.info(f"数据库已初始化: {config.store.db_path}")

    results = {}

    # 1. arXiv 巡检
    try:
        logger.info("开始 arXiv 巡检")
        arxiv_count = await ingest_arxiv(config)
        results["arxiv"] = {"count": arxiv_count, "status": "success"}
        logger.info(f"arXiv 巡检完成，处理 {arxiv_count} 条记录")
    except Exception as e:
        logger.error(f"arXiv 巡检失败: {e}", exc_info=True)
        results["arxiv"] = {"count": 0, "status": "error", "error": str(e)}

    # 2. Crossref 巡检（CNS 期刊）
    try:
        logger.info("开始 Crossref 巡检")
        crossref_count = await ingest_crossref(config)
        results["crossref"] = {"count": crossref_count, "status": "success"}
        logger.info(f"Crossref 巡检完成，处理 {crossref_count} 条记录")
    except Exception as e:
        logger.error(f"Crossref 巡检失败: {e}", exc_info=True)
        results["crossref"] = {"count": 0, "status": "error", "error": str(e)}

    # 3. Europe PMC 巡检（最近7天）
    try:
        logger.info("开始 Europe PMC 巡检")
        eupmc_count = await query_europe_pmc_by_days(config, days=7, max_results=1000)
        results["eupmc"] = {"count": eupmc_count, "status": "success"}
        logger.info(f"Europe PMC 巡检完成，处理 {eupmc_count} 条记录")
    except Exception as e:
        logger.error(f"Europe PMC 巡检失败: {e}", exc_info=True)
        results["eupmc"] = {"count": 0, "status": "error", "error": str(e)}

    # 4. Unpaywall OA 状态查询（最近7天）
    try:
        logger.info("开始 Unpaywall OA 状态查询")
        unpaywall_stats = await query_unpaywall_by_days(config, days=7, limit=100)
        results["unpaywall"] = {"stats": unpaywall_stats, "status": "success"}
        logger.info(
            f"Unpaywall 查询完成，OA: {unpaywall_stats.get('oa_count', 0)}, "
            f"非OA: {unpaywall_stats.get('non_oa_count', 0)}"
        )
    except Exception as e:
        logger.error(f"Unpaywall 查询失败: {e}", exc_info=True)
        results["unpaywall"] = {"stats": {}, "status": "error", "error": str(e)}

    # 统计总结果
    total_count = (
        results.get("arxiv", {}).get("count", 0)
        + results.get("crossref", {}).get("count", 0)
        + results.get("eupmc", {}).get("count", 0)
    )

    logger.info(f"每日巡检任务完成，总计处理 {total_count} 条记录")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_count": total_count,
        "results": results,
    }


async def daily_ingest_sources(
    config: Settings,
    sources: list[str],
) -> dict:
    """
    执行指定数据源的每日巡检任务

    Args:
        config: 应用配置
        sources: 数据源列表，可选值：['arxiv', 'crossref', 'eupmc', 'unpaywall']

    Returns:
        各数据源的巡检结果
    """
    logger.info(f"开始执行每日巡检任务（数据源: {', '.join(sources)}）")

    # 初始化数据库
    init_db(config.store.db_path)
    logger.info(f"数据库已初始化: {config.store.db_path}")

    results = {}

    if "arxiv" in sources:
        try:
            logger.info("开始 arXiv 巡检")
            arxiv_count = await ingest_arxiv(config)
            results["arxiv"] = {"count": arxiv_count, "status": "success"}
        except Exception as e:
            logger.error(f"arXiv 巡检失败: {e}", exc_info=True)
            results["arxiv"] = {"count": 0, "status": "error", "error": str(e)}

    if "crossref" in sources:
        try:
            logger.info("开始 Crossref 巡检")
            crossref_count = await ingest_crossref(config)
            results["crossref"] = {"count": crossref_count, "status": "success"}
        except Exception as e:
            logger.error(f"Crossref 巡检失败: {e}", exc_info=True)
            results["crossref"] = {"count": 0, "status": "error", "error": str(e)}

    if "eupmc" in sources:
        try:
            logger.info("开始 Europe PMC 巡检")
            eupmc_count = await query_europe_pmc_by_days(config, days=7, max_results=1000)
            results["eupmc"] = {"count": eupmc_count, "status": "success"}
        except Exception as e:
            logger.error(f"Europe PMC 巡检失败: {e}", exc_info=True)
            results["eupmc"] = {"count": 0, "status": "error", "error": str(e)}

    if "unpaywall" in sources:
        try:
            logger.info("开始 Unpaywall OA 状态查询")
            unpaywall_stats = await query_unpaywall_by_days(config, days=7, limit=100)
            results["unpaywall"] = {"stats": unpaywall_stats, "status": "success"}
        except Exception as e:
            logger.error(f"Unpaywall 查询失败: {e}", exc_info=True)
            results["unpaywall"] = {"stats": {}, "status": "error", "error": str(e)}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


"""
每日巡检 Pipeline：arXiv + Crossref 增量抓取
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from papergazer.config import Settings
from papergazer.exceptions import ArxivAPIError, CrossrefAPIError, DatabaseError
from papergazer.models import PaperMetadata
from papergazer.sources import crossref, query_arxiv
from papergazer.store.db import get_session, get_last_checkpoint, update_checkpoint, upsert_paper

logger = logging.getLogger(__name__)


async def ingest_arxiv(config: Settings) -> int:
    """
    巡检 arXiv

    Args:
        config: 应用配置

    Returns:
        新增/更新的论文数量
    """
    logger.info(f"开始巡检 arXiv，分类: {config.arxiv.categories}")

    session = get_session()
    try:
        # 获取上次检查点
        last_checkpoint = get_last_checkpoint(session, "arxiv")
        if last_checkpoint:
            # 确保 checkpoint 有时区信息（如果从数据库读取的是 naive datetime）
            if last_checkpoint.tzinfo is None:
                last_checkpoint = last_checkpoint.replace(tzinfo=timezone.utc)
            logger.info(f"上次检查点: {last_checkpoint}")
        else:
            # 如果没有检查点，使用 7 天前作为默认值
            last_checkpoint = datetime.now(timezone.utc) - timedelta(days=7)
            logger.info(f"无历史检查点，使用默认值: {last_checkpoint}")

        # 查询 arXiv（批量处理）
        count = 0
        batch_size = 50  # 批量提交大小
        batch = []

        total_fetched = 0
        filtered_count = 0
        async for entry in query_arxiv(
            categories=config.arxiv.categories,
            max_results=config.arxiv.max_results,
            delay_seconds=config.arxiv.delay_seconds,
        ):
            total_fetched += 1
            # 过滤：只处理更新日期晚于检查点的条目
            if entry.updated < last_checkpoint:
                filtered_count += 1
                logger.debug(f"过滤条目 {entry.arxiv_id}: updated={entry.updated}, checkpoint={last_checkpoint}")
                continue

            # 转换为标准化元数据
            metadata = entry.to_metadata()
            batch.append(metadata)
            count += 1

            # 批量提交
            if len(batch) >= batch_size:
                for m in batch:
                    upsert_paper(session, m)
                session.commit()
                logger.debug(f"已处理 {count} 条 arXiv 记录（批量提交）")
                batch.clear()

        # 提交剩余记录
        if batch:
            for m in batch:
                upsert_paper(session, m)
            session.commit()
            logger.debug(f"已处理 {count} 条 arXiv 记录（最终提交）")

        # 更新检查点
        new_checkpoint = datetime.now(timezone.utc)
        update_checkpoint(session, "arxiv", new_checkpoint, count)
        session.commit()

        logger.info(f"arXiv 巡检完成，获取 {total_fetched} 条，过滤 {filtered_count} 条，处理 {count} 条记录")
        return count

    except ArxivAPIError as e:
        session.rollback()
        logger.error(f"arXiv API 错误: {e}", exc_info=True)
        raise
    except DatabaseError as e:
        session.rollback()
        logger.error(f"数据库错误: {e}", exc_info=True)
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"arXiv 巡检失败: {e}", exc_info=True)
        raise ArxivAPIError(f"arXiv 巡检失败: {e}") from e
    finally:
        session.close()


async def ingest_crossref(config: Settings) -> int:
    """
    巡检 Crossref（CNS 期刊）
    使用出版时间（publication date）进行增量查询

    Args:
        config: 应用配置

    Returns:
        新增/更新的论文数量
    """
    logger.info("开始巡检 Crossref（CNS 期刊）")

    session = get_session()
    try:
        # 获取上次检查点（出版时间）
        last_checkpoint = get_last_checkpoint(session, "crossref")
        if last_checkpoint:
            logger.info(f"上次检查点（出版时间）: {last_checkpoint}")
            # 使用检查点前1-2天作为起始日期，留重叠以防出版社回填/修订
            since_date = (last_checkpoint - timedelta(days=2)).date()
        else:
            # 如果没有检查点，使用 7 天前作为默认值
            since_date = (datetime.now(timezone.utc) - timedelta(days=7)).date()
            logger.info(f"无历史检查点，使用默认值: {since_date}")

        # 结束日期：当前日期
        until_date = datetime.now(timezone.utc).date()

        # 收集所有 ISSN
        all_issns: list[str] = []
        for journal_issns in config.cns.issn.values():
            all_issns.extend(journal_issns)

        # 查询 Crossref（批量处理）
        count = 0
        batch_size = 50  # 批量提交大小
        batch = []
        max_issued_date: date | None = None  # 跟踪最大的issued日期

        async for work in crossref.fetch_crossref_issn_increment(
            issns=all_issns,
            since=since_date,
            until=until_date,
            mailto=config.mailto,
        ):
            # 转换为标准化元数据
            metadata = work.to_metadata()
            batch.append(metadata)
            count += 1

            # 提取issued日期（用于checkpoint）
            if work.issued and "date-parts" in work.issued:
                date_parts = work.issued["date-parts"][0] if work.issued.get("date-parts") else None
                if date_parts and len(date_parts) >= 1:
                    try:
                        year = date_parts[0]
                        month = date_parts[1] if len(date_parts) > 1 else 1
                        day = date_parts[2] if len(date_parts) > 2 else 1
                        issued_date = date(year, month, day)
                        if max_issued_date is None or issued_date > max_issued_date:
                            max_issued_date = issued_date
                    except (ValueError, TypeError, IndexError):
                        pass

            # 批量提交
            if len(batch) >= batch_size:
                for m in batch:
                    upsert_paper(session, m)
                session.commit()
                logger.debug(f"已处理 {count} 条 Crossref 记录（批量提交）")
                batch.clear()

        # 提交剩余记录
        if batch:
            for m in batch:
                upsert_paper(session, m)
            session.commit()
            logger.debug(f"已处理 {count} 条 Crossref 记录（最终提交）")

        # 更新检查点：使用max(issued)作为出版时间索引
        if max_issued_date:
            # 转换为datetime（使用UTC时区）
            new_checkpoint = datetime.combine(max_issued_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            logger.info(f"更新检查点（最大出版时间）: {max_issued_date}")
        else:
            # 如果没有获取到issued日期，使用until_date
            new_checkpoint = datetime.combine(until_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            logger.warning("未获取到issued日期，使用结束日期作为检查点")

        update_checkpoint(session, "crossref", new_checkpoint, count)
        session.commit()

        logger.info(f"Crossref 巡检完成，处理 {count} 条记录")
        return count

    except CrossrefAPIError as e:
        session.rollback()
        logger.error(f"Crossref API 错误: {e}", exc_info=True)
        raise
    except DatabaseError as e:
        session.rollback()
        logger.error(f"数据库错误: {e}", exc_info=True)
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Crossref 巡检失败: {e}", exc_info=True)
        raise CrossrefAPIError(f"Crossref 巡检失败: {e}") from e
    finally:
        session.close()


async def run_daily_check(config: Settings) -> dict[str, int]:
    """
    执行每日巡检

    Args:
        config: 应用配置

    Returns:
        各数据源处理记录数
    """
    logger.info("=" * 50)
    logger.info("开始每日巡检")
    logger.info("=" * 50)

    results: dict[str, int] = {}

    try:
        # 巡检 arXiv
        results["arxiv"] = await ingest_arxiv(config)

        # 巡检 Crossref
        results["crossref"] = await ingest_crossref(config)

        logger.info("=" * 50)
        logger.info("每日巡检完成")
        logger.info(f"结果: {results}")
        logger.info("=" * 50)

        return results

    except Exception as e:
        logger.error(f"每日巡检失败: {e}", exc_info=True)
        raise


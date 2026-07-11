"""
每日巡检 Pipeline：arXiv + Crossref 增量抓取
"""

import logging
from datetime import UTC, date, datetime, timedelta

from papergazer.config import Settings
from papergazer.exceptions import ArxivAPIError, CrossrefAPIError, DatabaseError
from papergazer.sources import crossref, query_arxiv
from papergazer.store.db import get_last_checkpoint, get_session, update_checkpoint, upsert_paper

logger = logging.getLogger(__name__)


async def ingest_arxiv(
    config: Settings,
    since: datetime | None = None,
    until: datetime | None = None,
    ignore_checkpoint: bool = False,
) -> int:
    """
    巡检 arXiv

    Args:
        config: 应用配置
        since: 起始时间（可选，如果指定则忽略检查点）
        until: 结束时间（可选，默认为当前时间）
        ignore_checkpoint: 是否忽略检查点过滤（当指定时间范围时自动为 True）

    Returns:
        新增/更新的论文数量
    """
    logger.info(f"开始巡检 arXiv，分类: {config.arxiv.categories}")

    session = get_session()
    try:
        # 如果指定了时间范围，忽略检查点过滤
        if since is not None or ignore_checkpoint:
            if since is not None:
                if since.tzinfo is None:
                    since = since.replace(tzinfo=UTC)
                logger.info(f"手动指定起始时间: {since}，忽略检查点过滤")
            else:
                # 如果没有指定 since，使用 7 天前作为默认值
                since = datetime.now(UTC) - timedelta(days=7)
                logger.info(f"忽略检查点，使用默认起始时间: {since}")
            last_checkpoint = since
            ignore_checkpoint = True
        else:
            # 获取上次检查点
            checkpoint = get_last_checkpoint(session, "arxiv")
            last_checkpoint = checkpoint or (datetime.now(UTC) - timedelta(days=7))
            if checkpoint:
                # 确保 checkpoint 有时区信息（如果从数据库读取的是 naive datetime）
                if last_checkpoint.tzinfo is None:
                    last_checkpoint = last_checkpoint.replace(tzinfo=UTC)
                logger.info(f"上次检查点: {last_checkpoint}")
            else:
                # 如果没有检查点，使用 7 天前作为默认值
                logger.info(f"无历史检查点，使用默认值: {last_checkpoint}")

        # 查询 arXiv（批量处理）
        count = 0
        batch_size = 50  # 批量提交大小
        batch = []

        total_fetched = 0
        filtered_count = 0
        max_updated_time = last_checkpoint  # 跟踪查询到的最大更新时间
        min_updated_time = None  # 跟踪查询到的最小更新时间（用于调试）

        # 如果 max_results 太大，自动减少以避免超时
        # arXiv API 返回大量数据时容易超时，建议单次查询不超过 300 条
        effective_max_results = min(config.arxiv.max_results, 300)
        if config.arxiv.max_results > 300:
            logger.warning(
                f"max_results={config.arxiv.max_results} 较大，可能增加超时风险。"
                f"自动调整为 {effective_max_results} 以减少超时风险。"
            )

        async for entry in query_arxiv(
            categories=config.arxiv.categories,
            max_results=effective_max_results,
            delay_seconds=config.arxiv.delay_seconds,
        ):
            total_fetched += 1

            # 更新最大和最小更新时间（即使被过滤也要记录，用于更新检查点和调试）
            if entry.updated > max_updated_time:
                max_updated_time = entry.updated
            if min_updated_time is None or entry.updated < min_updated_time:
                min_updated_time = entry.updated

            # 过滤：如果未忽略检查点，只处理更新日期晚于检查点的条目
            # 注意：等于检查点的论文应该被视为已经处理过的，所以使用 <=
            if not ignore_checkpoint and entry.updated <= last_checkpoint:
                filtered_count += 1
                if filtered_count <= 3:  # 只记录前3个被过滤的条目，避免日志过多
                    logger.debug(
                        f"过滤条目 {entry.arxiv_id}: updated={entry.updated}, checkpoint={last_checkpoint}"
                    )
                continue

            # 如果指定了 until，过滤掉超过结束时间的条目
            if until is not None:
                if until.tzinfo is None:
                    until = until.replace(tzinfo=UTC)
                if entry.updated > until:
                    filtered_count += 1
                    if filtered_count <= 3:
                        logger.debug(
                            f"过滤条目 {entry.arxiv_id}: updated={entry.updated} 超过结束时间 {until}"
                        )
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

        # 更新检查点：如果忽略了检查点（手动指定时间范围），不更新检查点
        # 否则使用查询到的最大更新时间，而不是当前时间
        if not ignore_checkpoint:
            if max_updated_time > last_checkpoint:
                new_checkpoint = max_updated_time
            elif max_updated_time == last_checkpoint and count > 0:
                # 如果最大更新时间等于检查点但处理了论文，将检查点稍微后移（加1秒）
                # 这样可以确保下次查询时不会重复处理这些论文
                new_checkpoint = max_updated_time + timedelta(seconds=1)
                logger.debug(f"最大更新时间等于检查点但处理了 {count} 条论文，检查点后移1秒")
            else:
                # 如果没有查询到更新的论文，保持原检查点不变
                new_checkpoint = last_checkpoint

            update_checkpoint(session, "arxiv", new_checkpoint, count)
            session.commit()
            logger.info(f"检查点更新: {last_checkpoint} -> {new_checkpoint}")
        else:
            logger.info(
                f"手动指定时间范围，不更新检查点（保持: {get_last_checkpoint(session, 'arxiv')}）"
            )

        logger.info(
            f"arXiv 巡检完成，获取 {total_fetched} 条，过滤 {filtered_count} 条，处理 {count} 条记录"
        )
        if total_fetched > 0:
            logger.info(f"查询到的论文更新时间范围: {min_updated_time} ~ {max_updated_time}")

        # 如果所有论文都被过滤，给出提示
        if total_fetched > 0 and filtered_count == total_fetched:
            logger.warning(
                f"所有 {total_fetched} 条论文都被过滤（更新时间早于检查点）。"
                f"如果这是首次运行或需要重新抓取，可以删除数据库中的检查点记录。"
            )

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


async def ingest_crossref(
    config: Settings,
    since: date | datetime | None = None,
    until: date | datetime | None = None,
    ignore_checkpoint: bool = False,
) -> int:
    """
    巡检 Crossref（期刊）
    使用出版时间（publication date）进行增量查询

    Args:
        config: 应用配置
        since: 起始日期（可选，如果指定则忽略检查点）
        until: 结束日期（可选，默认为当前日期）
        ignore_checkpoint: 是否忽略检查点过滤（当指定时间范围时自动为 True）

    Returns:
        新增/更新的论文数量
    """
    logger.info("开始巡检 Crossref（期刊）")

    session = get_session()
    try:
        # 如果指定了时间范围，忽略检查点过滤
        if since is not None or ignore_checkpoint:
            if since is not None:
                # 转换为 date 类型
                if isinstance(since, datetime):
                    since_date = since.date()
                else:
                    since_date = since
                logger.info(f"手动指定起始日期: {since_date}，忽略检查点过滤")
            else:
                # 如果没有指定 since，使用 7 天前作为默认值
                since_date = (datetime.now(UTC) - timedelta(days=7)).date()
                logger.info(f"忽略检查点，使用默认起始日期: {since_date}")
            ignore_checkpoint = True
        else:
            # 获取上次检查点（出版时间）
            last_checkpoint = get_last_checkpoint(session, "crossref")
            if last_checkpoint:
                logger.info(f"上次检查点（出版时间）: {last_checkpoint}")
                # 使用检查点前1-2天作为起始日期，留重叠以防出版社回填/修订
                if isinstance(last_checkpoint, datetime):
                    since_date = (last_checkpoint - timedelta(days=2)).date()
                else:
                    since_date = last_checkpoint - timedelta(days=2)
            else:
                # 如果没有检查点，使用 7 天前作为默认值
                since_date = (datetime.now(UTC) - timedelta(days=7)).date()
                logger.info(f"无历史检查点，使用默认值: {since_date}")

        # 结束日期
        if until is not None:
            if isinstance(until, datetime):
                until_date = until.date()
            else:
                until_date = until
        else:
            until_date = datetime.now(UTC).date()

        # 收集所有 ISSN
        all_issns: list[str] = []
        for journal_issns in config.journals.issn.values():
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

        # 更新检查点：如果忽略了检查点（手动指定时间范围），不更新检查点
        if not ignore_checkpoint:
            if max_issued_date:
                # 转换为datetime（使用UTC时区）
                new_checkpoint = datetime.combine(max_issued_date, datetime.min.time()).replace(
                    tzinfo=UTC
                )
                logger.info(f"更新检查点（最大出版时间）: {max_issued_date}")
            else:
                # 如果没有获取到issued日期，使用until_date
                new_checkpoint = datetime.combine(until_date, datetime.min.time()).replace(
                    tzinfo=UTC
                )
                logger.warning("未获取到issued日期，使用结束日期作为检查点")

            update_checkpoint(session, "crossref", new_checkpoint, count)
            session.commit()
        else:
            logger.info(
                f"手动指定时间范围，不更新检查点（保持: {get_last_checkpoint(session, 'crossref')}）"
            )

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

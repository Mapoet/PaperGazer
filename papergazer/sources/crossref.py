"""
Crossref API 封装：增量拉取期刊论文
支持通过 print 或 online ISSN 查询特定期刊
"""

import logging
from datetime import date, datetime, timezone
from typing import AsyncIterator, List, Optional, Union

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from papergazer.models import CrossrefWork

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def fetch_crossref_issn_increment(
    issns: List[str],
    since: Union[date, datetime, str],
    until: Optional[Union[date, datetime, str]] = None,
    mailto: str = "",
    rows: int = 1000,
) -> AsyncIterator[CrossrefWork]:
    """
    按 ISSN + 出版日期增量拉取 Crossref 数据

    Args:
        issns: ISSN 列表
        since: 起始出版日期（date, datetime 或 ISO 字符串）
        until: 结束出版日期（可选，date, datetime 或 ISO 字符串）
        mailto: 联系邮箱（用于礼貌池）
        rows: 每页结果数（最大 1000）

    Yields:
        CrossrefWork: Crossref 工作项
    """
    # 格式化日期
    if isinstance(since, (date, datetime)):
        since_str = since.isoformat()
    else:
        since_str = str(since)
    
    if until is None:
        # 如果没有指定结束日期，使用当前日期
        until = datetime.now(timezone.utc).date() if isinstance(since, (date, datetime)) else date.today()
    
    if isinstance(until, (date, datetime)):
        until_str = until.isoformat()
    else:
        until_str = str(until)

    # 构建 filter 参数：使用 from-pub-date 和 until-pub-date
    issn_filter = ",".join([f"issn:{issn}" for issn in issns])
    filter_str = f"{issn_filter},type:journal-article,from-pub-date:{since_str},until-pub-date:{until_str}"

    params = {
        "filter": filter_str,
        "select": "DOI,title,author,issued,published-online,published-print,container-title,ISSN,link,abstract",
        "rows": min(rows, 1000),
        "sort": "issued",  # 按最早已知出版日排序
        "order": "asc",
        "cursor": "*",
        "mailto": mailto,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        seen_cursors = set()  # 跟踪已见过的游标，防止循环
        max_iterations = 10000  # 最大迭代次数，防止无限循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            current_cursor = params.get("cursor", "*")
            
            # 检查是否遇到重复的游标
            if current_cursor in seen_cursors:
                logger.warning(f"检测到重复游标 {current_cursor[:50]}...，退出循环")
                break
            seen_cursors.add(current_cursor)

            response = await client.get(CROSSREF_API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            message = data.get("message", {})

            # 记录API返回的总记录数信息（如果可用）
            total_results = message.get("total-results")
            if total_results is not None and iteration == 1:
                logger.info(f"Crossref API 总记录数: {total_results}")

            # 处理结果
            items = message.get("items", [])
            items_count = len(items)
            logger.debug(f"第 {iteration} 次请求，返回 {items_count} 条记录")

            if not items:
                # 如果没有结果，退出循环
                logger.debug("返回空结果，退出循环")
                break

            for item in items:
                # 转换 DOI 字段（Crossref API 返回 "DOI"，模型需要 "doi"）
                if "DOI" in item:
                    item["doi"] = item.pop("DOI")
                # 转换其他字段
                if "ISSN" in item:
                    item["issn"] = item.pop("ISSN")
                if "container-title" in item:
                    item["container_title"] = item.pop("container-title")
                yield CrossrefWork(**item)

            # 检查是否有下一页
            next_cursor = message.get("next-cursor")
            if not next_cursor:
                logger.debug("API 未返回 next-cursor，退出循环")
                break

            # 检查新游标是否与当前游标相同
            if next_cursor == current_cursor:
                # 如果返回的记录数少于请求的rows数，说明确实没有更多数据了
                if items_count < rows:
                    logger.debug(f"返回记录数 ({items_count}) 少于请求数 ({rows})，且 next-cursor 与当前 cursor 相同，退出循环")
                    break
                else:
                    # 如果返回了满页数据，但next-cursor相同，这是API的限制
                    # 记录警告，但接受这个限制（剩余数据将在下次巡检时继续获取）
                    total_results = message.get("total-results", "未知")
                    fetched_count = iteration * rows
                    logger.warning(
                        f"返回了满页数据 ({items_count} 条)，但 next-cursor 与当前 cursor 相同。"
                        f"API总记录数: {total_results}，已获取约 {fetched_count} 条记录。"
                        f"这是Crossref API游标分页的已知限制，剩余数据将在下次巡检时继续获取。"
                    )
                    break

            # 更新游标
            params["cursor"] = next_cursor
            logger.debug(f"更新游标为: {next_cursor[:50]}...")

        if iteration >= max_iterations:
            logger.error(f"达到最大迭代次数 {max_iterations}，强制退出循环")


async def fetch_crossref_by_doi(doi: str, mailto: str) -> Optional[CrossrefWork]:
    """
    按 DOI 获取单个工作项

    Args:
        doi: DOI
        mailto: 联系邮箱

    Returns:
        CrossrefWork 或 None（如果未找到）
    """
    url = f"{CROSSREF_API_URL}/{doi}"
    params = {"mailto": mailto}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            # 转换字段名
            if "DOI" in message:
                message["doi"] = message.pop("DOI")
            if "ISSN" in message:
                message["issn"] = message.pop("ISSN")
            if "container-title" in message:
                message["container_title"] = message.pop("container-title")
            return CrossrefWork(**message)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


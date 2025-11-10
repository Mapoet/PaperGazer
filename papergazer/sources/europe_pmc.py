"""
Europe PMC API 封装：DOI → PMCID → FullTextXML
"""

import logging
from datetime import date, datetime
from typing import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from papergazer.models import EuropePMCResult

logger = logging.getLogger(__name__)

EUROPE_PMC_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def doi_to_pmcid(doi: str) -> str | None:
    """
    通过 DOI 获取 PMCID

    Args:
        doi: DOI

    Returns:
        PMCID 或 None（如果未找到）
    """
    query = f"search?query=DOI:{doi}&format=json"
    url = f"{EUROPE_PMC_API_URL}/{query}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()
        result_list = data.get("resultList", {})
        results = result_list.get("result", [])

        for item in results:
            if "pmcid" in item:
                return item["pmcid"]

    return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def fetch_fulltext_xml(pmcid: str) -> bytes:
    """
    获取 PMCID 对应的 FullTextXML

    Args:
        pmcid: PMCID（需要去除 "PMC" 前缀）

    Returns:
        XML 内容（bytes）
    """
    # 去除 PMC 前缀（如果存在）
    if pmcid.startswith("PMC"):
        pmcid = pmcid[3:]

    url = f"{EUROPE_PMC_API_URL}/{pmcid}/fullTextXML"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def search_articles_by_date(
    from_date: date | datetime | str,
    to_date: date | datetime | str | None = None,
    page_size: int = 25,
    max_results: int = 1000,
) -> AsyncIterator[dict]:
    """
    按发布日期搜索文章

    Args:
        from_date: 起始日期
        to_date: 结束日期（如果为None，使用当前日期）
        page_size: 每页结果数（最大1000）
        max_results: 最大返回结果数

    Yields:
        文章信息字典，包含 pmcid, title, doi, firstPublicationDate 等字段
    """
    # 格式化日期
    if isinstance(from_date, datetime):
        from_date_str = from_date.date().strftime("%Y-%m-%d")
    elif isinstance(from_date, date):
        from_date_str = from_date.strftime("%Y-%m-%d")
    else:
        from_date_str = str(from_date)

    if to_date is None:
        to_date = datetime.now().date()
    if isinstance(to_date, datetime):
        to_date_str = to_date.date().strftime("%Y-%m-%d")
    elif isinstance(to_date, date):
        to_date_str = to_date.strftime("%Y-%m-%d")
    else:
        to_date_str = str(to_date)

    # 构建查询：使用 FIRST_PDATE 字段
    query = f"FIRST_PDATE:[{from_date_str} TO {to_date_str}]"
    
    page = 1
    total_fetched = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        while total_fetched < max_results:
            params = {
                "query": query,
                "format": "json",
                "pageSize": min(page_size, 1000),  # API限制最大1000
                "page": page,
                "resultType": "core",  # 返回核心字段
                "synonym": "true",  # 启用同义词搜索
            }

            try:
                response = await client.get(f"{EUROPE_PMC_API_URL}/search", params=params)
                response.raise_for_status()
                data = response.json()

                result_list = data.get("resultList", {})
                results = result_list.get("result", [])
                # hitCount 可能在不同位置
                total_hits = (
                    result_list.get("hitCount", 0)
                    or data.get("hitCount", 0)
                    or len(results)
                )

                if page == 1:
                    logger.info(f"Europe PMC API 总记录数: {total_hits} (当前页: {len(results)} 条)")

                if not results:
                    logger.debug("返回空结果，退出循环")
                    break

                for item in results:
                    if total_fetched >= max_results:
                        break
                    yield item
                    total_fetched += 1

                # 检查是否还有更多结果
                if total_fetched >= total_hits or total_fetched >= max_results:
                    break

                page += 1
                # 遵守API速率限制：每秒1次请求
                import asyncio
                await asyncio.sleep(1.1)

            except httpx.HTTPStatusError as e:
                logger.error(f"Europe PMC API 错误: {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Europe PMC API 查询失败: {e}")
                raise

    logger.info(f"Europe PMC 查询完成，获取 {total_fetched} 条记录")


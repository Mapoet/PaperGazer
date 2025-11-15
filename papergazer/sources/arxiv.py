"""
arXiv API 封装：查询与解析 Atom feed
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, List

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from papergazer.models import ArxivEntry

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def query_arxiv(
    categories: List[str],
    max_results: int = 100,
    delay_seconds: float = 3.0,
    start: int = 0,
) -> AsyncIterator[ArxivEntry]:
    """
    查询 arXiv API

    Args:
        categories: arXiv 分类列表（如 ["eess.SP", "physics.space-ph"]）
        max_results: 最大结果数
        delay_seconds: 请求间隔（秒）
        start: 起始位置（用于分页）

    Yields:
        ArxivEntry: arXiv 条目
    """
    # 构建查询字符串（arXiv API 使用空格分隔的 OR）
    if len(categories) == 1:
        query = f"cat:{categories[0]}"
    else:
        query = " OR ".join([f"cat:{cat}" for cat in categories])

    params = {
        "search_query": query,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
        "max_results": min(max_results, 10000),  # arXiv 限制每片不超过 10000
        "start": start,
    }

    # 对于大量数据查询，使用更长的超时时间
    # connect: 连接超时, read: 读取超时, write: 写入超时, pool: 连接池超时
    timeout = httpx.Timeout(
        connect=10.0,  # 连接超时 10 秒
        read=180.0,    # 读取超时 180 秒（大量数据需要更长时间）
        write=10.0,    # 写入超时 10 秒
        pool=10.0,     # 连接池超时 10 秒
    )
    
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(ARXIV_API_URL, params=params)
        response.raise_for_status()

        # 解析 Atom feed
        feed = feedparser.parse(response.text)
        
        # 调试信息
        if len(feed.entries) == 0:
            logger.warning(f"arXiv API 返回空结果，响应长度: {len(response.text)}")
            logger.debug(f"响应内容前500字符: {response.text[:500]}")

        for entry in feed.entries:
            # 提取 arXiv ID
            arxiv_id = entry.id.rsplit("/", 1)[-1]

            # 提取 PDF URL
            pdf_url = None
            for link in entry.get("links", []):
                if link.get("rel") == "related" and link.get("title") == "pdf":
                    pdf_url = link.get("href")
                    break

            # 提取作者
            authors = [author.get("name", "") for author in entry.get("authors", [])]

            # 提取分类
            categories_list = [tag.get("term", "") for tag in entry.get("tags", [])]

            # 解析日期（arXiv API 返回的是 UTC 时间）
            if hasattr(entry, "updated_parsed") and entry.updated_parsed:
                updated = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                updated = datetime.now(timezone.utc)
            
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            # 提取 DOI（如果存在）
            doi = None
            if hasattr(entry, "arxiv_doi"):
                doi = entry.arxiv_doi

            yield ArxivEntry(
                arxiv_id=arxiv_id,
                title=entry.title,
                summary=entry.summary,
                updated=updated,
                published=published,
                authors=authors,
                categories=categories_list,
                pdf_url=pdf_url,
                doi=doi,
            )

        # 请求间隔
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)


async def query_arxiv_batch(
    categories: List[str],
    max_results: int = 100,
    delay_seconds: float = 3.0,
) -> List[ArxivEntry]:
    """
    批量查询 arXiv（处理分页）

    Args:
        categories: arXiv 分类列表
        max_results: 最大结果数
        delay_seconds: 请求间隔（秒）

    Returns:
        ArxivEntry 列表
    """
    results: List[ArxivEntry] = []
    start = 0
    batch_size = 2000  # arXiv 限制

    while len(results) < max_results:
        batch_max = min(batch_size, max_results - len(results))
        async for entry in query_arxiv(categories, batch_max, delay_seconds, start):
            results.append(entry)
            if len(results) >= max_results:
                break

        if len(results) < batch_size:
            break  # 没有更多结果

        start += batch_size

    return results[:max_results]


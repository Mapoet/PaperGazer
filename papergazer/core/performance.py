"""
性能优化模块：并发控制、批量操作等
"""

import asyncio
from typing import List, TypeVar, Callable, Awaitable
from collections.abc import AsyncIterator

T = TypeVar("T")


async def batch_process(
    items: AsyncIterator[T],
    processor: Callable[[T], Awaitable[None]],
    batch_size: int = 10,
    max_concurrent: int = 5,
) -> int:
    """
    批量并发处理异步迭代器中的项目

    Args:
        items: 异步迭代器
        processor: 处理函数（异步）
        batch_size: 批量大小
        max_concurrent: 最大并发数

    Returns:
        处理的项目数
    """
    count = 0
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(item: T) -> None:
        async with semaphore:
            await processor(item)

    batch = []
    async for item in items:
        batch.append(item)
        count += 1

        if len(batch) >= batch_size:
            # 并发处理批次
            await asyncio.gather(*[process_with_semaphore(item) for item in batch])
            batch.clear()

    # 处理剩余项目
    if batch:
        await asyncio.gather(*[process_with_semaphore(item) for item in batch])

    return count


async def rate_limited_gather(
    tasks: List[Awaitable[T]],
    max_concurrent: int = 5,
    delay: float = 0.0,
) -> List[T]:
    """
    限速并发执行任务

    Args:
        tasks: 任务列表
        max_concurrent: 最大并发数
        delay: 任务间延迟（秒）

    Returns:
        结果列表
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def execute_with_semaphore(task: Awaitable[T]) -> T:
        async with semaphore:
            if delay > 0:
                await asyncio.sleep(delay)
            return await task

    results = await asyncio.gather(*[execute_with_semaphore(task) for task in tasks])
    return results


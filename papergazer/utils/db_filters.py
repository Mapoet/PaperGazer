"""
数据库查询过滤器工具
提供统一的时间过滤等功能
"""

from datetime import datetime

from sqlalchemy import func

from papergazer.store.db import PaperItem


def get_effective_date_filter(cutoff_date: datetime):
    """
    获取有效的日期过滤条件

    优先使用 updated_date，如果为 None 则使用 published_date，再为 None 则使用 ingested_at

    这个函数解决了 Crossref 等数据源的 updated_date 为 None 的问题。

    Args:
        cutoff_date: 截止日期

    Returns:
        SQLAlchemy 过滤条件

    Example:
        >>> from datetime import datetime, timedelta, timezone
        >>> cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        >>> query = session.query(PaperItem).filter(get_effective_date_filter(cutoff_date))
    """
    # 将 published_date (Date) 转换为 datetime 以便比较
    # 使用 coalesce 获取第一个非空的日期字段
    effective_date = func.coalesce(
        PaperItem.updated_date,
        func.datetime(PaperItem.published_date),  # 将 Date 转换为 datetime
        PaperItem.ingested_at,
    )
    return effective_date >= cutoff_date

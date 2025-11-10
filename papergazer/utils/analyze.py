"""
论文分析工具
支持摘要分析、作者分析等功能
"""

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from papergazer.store.db import get_session, PaperItem, init_db
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)


def _ensure_db_initialized(db_path: str | Path | None = None) -> None:
    """
    确保数据库已初始化
    
    Args:
        db_path: 数据库路径，如果为 None 则尝试从默认配置加载
    
    Raises:
        RuntimeError: 如果数据库未初始化且无法自动初始化
    """
    # 尝试获取会话，如果成功则数据库已初始化
    try:
        get_session().close()
        return  # 数据库已初始化
    except RuntimeError:
        pass  # 数据库未初始化，继续下面的逻辑
    
    if db_path:
        init_db(db_path)
        return
    
    # 尝试从默认配置文件加载
    try:
        from papergazer.config import load_config
        config_path = Path("configs/config.yaml")
        if not config_path.exists():
            config_path = Path("configs/config.test.yaml")
        
        if config_path.exists():
            config = load_config(config_path)
            init_db(config.store.db_path)
            return
    except Exception as e:
        logger.debug(f"无法自动初始化数据库: {e}")
    
    raise RuntimeError(
        "数据库未初始化。请先调用 init_db(db_path) 或确保配置文件存在。"
    )


def analyze_authors_by_days(
    days: int,
    sources: Optional[List[str]] = None,
    top_n: int = 10,
    db_path: Optional[str | Path] = None,
) -> Dict:
    """
    分析指定天数内的作者信息

    Args:
        days: 查询天数
        sources: 数据源列表，如果为 None 则分析所有数据源
        top_n: 返回前 N 名作者
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        分析结果字典
    """
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = session.query(PaperItem).filter(PaperItem.updated_date >= cutoff_date)

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        items = query.all()

        author_counter = Counter()
        author_affiliations = defaultdict(set)
        author_papers = defaultdict(list)

        for item in items:
            if not item.authors_json:
                continue

            try:
                authors_data = json.loads(item.authors_json)
                for author_data in authors_data:
                    name = author_data.get("name", "").strip()
                    if name:
                        author_counter[name] += 1
                        affiliation = author_data.get("affiliation")
                        if affiliation:
                            author_affiliations[name].add(affiliation)
                        author_papers[name].append(
                            {
                                "title": item.title,
                                "doi": item.doi,
                                "source": item.source,
                                "published_date": str(item.published_date)
                                if item.published_date
                                else None,
                            }
                        )
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"解析作者信息失败: {e}")

        # 获取前 N 名作者
        top_authors = author_counter.most_common(top_n)

        result = {
            "total_authors": len(author_counter),
            "total_papers": len(items),
            "top_authors": [
                {
                    "name": name,
                    "count": count,
                    "affiliations": list(author_affiliations[name]),
                    "papers": author_papers[name][:5],  # 只返回前5篇论文
                }
                for name, count in top_authors
            ],
        }

        return result
    finally:
        session.close()


def analyze_abstracts_by_days(
    days: int,
    sources: Optional[List[str]] = None,
    min_length: int = 100,
    db_path: Optional[str | Path] = None,
) -> Dict:
    """
    分析指定天数内的摘要信息

    Args:
        days: 查询天数
        sources: 数据源列表，如果为 None 则分析所有数据源
        min_length: 摘要最小长度（字符数）
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        分析结果字典
    """
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = session.query(PaperItem).filter(PaperItem.updated_date >= cutoff_date)

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        items = query.all()

        abstracts_with = 0
        abstracts_without = 0
        total_length = 0
        length_distribution = []
        source_stats = defaultdict(lambda: {"with": 0, "without": 0, "total_length": 0})

        for item in items:
            has_abstract = item.abstract_jats and len(item.abstract_jats.strip()) >= min_length

            if has_abstract:
                abstracts_with += 1
                length = len(item.abstract_jats)
                total_length += length
                length_distribution.append(length)
                source_stats[item.source]["with"] += 1
                source_stats[item.source]["total_length"] += length
            else:
                abstracts_without += 1
                source_stats[item.source]["without"] += 1

        avg_length = total_length / abstracts_with if abstracts_with > 0 else 0

        result = {
            "total_papers": len(items),
            "abstracts_with": abstracts_with,
            "abstracts_without": abstracts_without,
            "coverage_rate": abstracts_with / len(items) if items else 0,
            "average_length": round(avg_length, 2),
            "min_length": min(length_distribution) if length_distribution else 0,
            "max_length": max(length_distribution) if length_distribution else 0,
            "source_stats": dict(source_stats),
        }

        return result
    finally:
        session.close()


def analyze_oa_status_by_days(
    days: int,
    sources: Optional[List[str]] = None,
    db_path: Optional[str | Path] = None,
) -> Dict:
    """
    分析指定天数内的 OA 状态

    Args:
        days: 查询天数
        sources: 数据源列表，如果为 None 则分析所有数据源
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        分析结果字典
    """
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = session.query(PaperItem).filter(PaperItem.updated_date >= cutoff_date)

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        items = query.all()

        oa_count = 0
        non_oa_count = 0
        unknown_count = 0
        oa_sources = Counter()
        source_stats = defaultdict(
            lambda: {"oa": 0, "non_oa": 0, "unknown": 0, "total": 0}
        )

        for item in items:
            source_stats[item.source]["total"] += 1

            if item.is_oa:
                oa_count += 1
                if item.oa_source:
                    oa_sources[item.oa_source] += 1
                source_stats[item.source]["oa"] += 1
            elif item.is_oa is False:
                non_oa_count += 1
                source_stats[item.source]["non_oa"] += 1
            else:
                unknown_count += 1
                source_stats[item.source]["unknown"] += 1

        result = {
            "total_papers": len(items),
            "oa_count": oa_count,
            "non_oa_count": non_oa_count,
            "unknown_count": unknown_count,
            "oa_rate": oa_count / len(items) if items else 0,
            "oa_sources": dict(oa_sources),
            "source_stats": dict(source_stats),
        }

        return result
    finally:
        session.close()


def analyze_venues_by_days(
    days: int,
    sources: Optional[List[str]] = None,
    top_n: int = 10,
    db_path: Optional[str | Path] = None,
) -> Dict:
    """
    分析指定天数内的期刊/会议信息

    Args:
        days: 查询天数
        sources: 数据源列表，如果为 None 则分析所有数据源
        top_n: 返回前 N 个期刊/会议
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        分析结果字典
    """
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = session.query(PaperItem).filter(PaperItem.updated_date >= cutoff_date)

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        items = query.all()

        venue_counter = Counter()
        venue_sources = defaultdict(set)

        for item in items:
            if item.venue:
                venue_counter[item.venue] += 1
                venue_sources[item.venue].add(item.source)

        top_venues = venue_counter.most_common(top_n)

        result = {
            "total_venues": len(venue_counter),
            "total_papers": len(items),
            "top_venues": [
                {
                    "venue": venue,
                    "count": count,
                    "sources": list(venue_sources[venue]),
                }
                for venue, count in top_venues
            ],
        }

        return result
    finally:
        session.close()


def get_papers_by_days(
    days: int,
    sources: Optional[List[str]] = None,
    limit: Optional[int] = None,
    order_by: str = "updated_date",
    db_path: Optional[str | Path] = None,
) -> List[Dict]:
    """
    获取指定天数内的论文列表

    Args:
        days: 查询天数
        sources: 数据源列表，如果为 None 则查询所有数据源
        limit: 限制返回数量
        order_by: 排序字段（'updated_date' 或 'published_date'）
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        论文列表
    """
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = session.query(PaperItem).filter(PaperItem.updated_date >= cutoff_date)

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        # 排序
        if order_by == "published_date":
            query = query.order_by(PaperItem.published_date.desc())
        else:
            query = query.order_by(PaperItem.updated_date.desc())

        if limit:
            query = query.limit(limit)

        items = query.all()

        papers = []
        for item in items:
            authors = []
            if item.authors_json:
                try:
                    authors_data = json.loads(item.authors_json)
                    authors = [a.get("name", "") for a in authors_data]
                except (json.JSONDecodeError, TypeError):
                    pass

            papers.append(
                {
                    "id": item.id,
                    "source": item.source,
                    "title": item.title,
                    "doi": item.doi,
                    "identifier": item.identifier,
                    "authors": authors,
                    "venue": item.venue,
                    "published_date": str(item.published_date) if item.published_date else None,
                    "updated_date": str(item.updated_date) if item.updated_date else None,
                    "is_oa": item.is_oa,
                    "oa_source": item.oa_source,
                    "has_abstract": bool(item.abstract_jats and item.abstract_jats.strip()),
                }
            )

        return papers
    finally:
        session.close()


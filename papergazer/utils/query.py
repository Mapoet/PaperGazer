"""
多来源论文查询工具
支持 arXiv、Crossref（期刊）、Europe PMC 等数据源的统一查询接口
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from papergazer.config import Settings
from papergazer.core.ingest import ingest_arxiv, ingest_crossref
from papergazer.models import PaperMetadata
from papergazer.sources.europe_pmc import search_articles_by_date
from papergazer.sources.unpaywall import best_oa
from papergazer.store.db import get_session, PaperItem, upsert_paper
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)


async def query_arxiv_by_days(
    config: Settings,
    days: int,
    categories: Optional[List[str]] = None,
    ingest: bool = False,
) -> int:
    """
    查询指定天数内的 arXiv 论文

    Args:
        config: 应用配置
        days: 查询天数
        categories: arXiv 分类列表，如果为 None 则使用配置中的分类
        ingest: 是否执行 ingest 过程（抓取新数据），默认为 False（只查询已有数据）

    Returns:
        查询到的论文数量
    """
    # 初始化数据库
    from papergazer.store.db import init_db, RunRecord, update_checkpoint
    init_db(config.store.db_path)

    if ingest:
        logger.info(f"抓取并查询近 {days} 天的 arXiv 论文")
        
        # 设置检查点
        session = get_session()
        try:
            checkpoint = datetime.now(timezone.utc) - timedelta(days=days)
            session.query(RunRecord).filter_by(source="arxiv").delete()
            session.commit()
            update_checkpoint(session, "arxiv", checkpoint, 0)
            session.commit()
        finally:
            session.close()

        # 使用配置的分类或指定的分类
        if categories:
            original_categories = config.arxiv.categories
            config.arxiv.categories = categories
            try:
                count = await ingest_arxiv(config)
            finally:
                config.arxiv.categories = original_categories
        else:
            count = await ingest_arxiv(config)
        
        return count
    else:
        logger.info(f"查询数据库中近 {days} 天的 arXiv 论文")
        
        # 只查询数据库中已有的数据
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_date_only = cutoff_date.date()
        session = get_session()
        try:
            query = session.query(PaperItem).filter(
                PaperItem.source == "arxiv",
                PaperItem.published_date >= cutoff_date_only,
            )
            count = query.count()
        finally:
            session.close()
        
        return count


async def query_crossref_by_days(
    config: Settings,
    days: int,
    issns: Optional[List[str]] = None,
    ingest: bool = False,
) -> int:
    """
    查询指定天数内的 Crossref 论文（期刊）

    Args:
        config: 应用配置
        days: 查询天数
        issns: ISSN 列表，如果为 None 则使用配置中的期刊 ISSN
        ingest: 是否执行 ingest 过程（抓取新数据），默认为 False（只查询已有数据）

    Returns:
        查询到的论文数量
    """
    # 初始化数据库
    from papergazer.store.db import init_db, RunRecord, update_checkpoint
    init_db(config.store.db_path)

    if ingest:
        logger.info(f"抓取并查询近 {days} 天的 Crossref 论文")
        
        # 设置检查点
        session = get_session()
        try:
            checkpoint = datetime.now(timezone.utc) - timedelta(days=days)
            session.query(RunRecord).filter_by(source="crossref").delete()
            session.commit()
            update_checkpoint(session, "crossref", checkpoint, 0)
            session.commit()
        finally:
            session.close()

        # 如果指定了 ISSN，临时修改配置
        if issns:
            original_issns = config.journals.issn.copy()
            # 创建一个临时的 ISSN 配置
            config.journals.issn = {"custom": issns}
            try:
                count = await ingest_crossref(config)
            finally:
                config.journals.issn = original_issns
        else:
            count = await ingest_crossref(config)
        
        return count
    else:
        logger.info(f"查询数据库中近 {days} 天的 Crossref 论文")
        
        # 只查询数据库中已有的数据
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_date_only = cutoff_date.date()
        session = get_session()
        try:
            query = session.query(PaperItem).filter(
                PaperItem.source == "crossref",
                PaperItem.published_date >= cutoff_date_only,
            )
            count = query.count()
        finally:
            session.close()
        
        return count


async def query_europe_pmc_by_days(
    config: Settings,
    days: int,
    max_results: int = 1000,
    save_to_db: bool = True,
    ingest: bool = False,
) -> int:
    """
    查询指定天数内的 Europe PMC 论文

    Args:
        config: 应用配置
        days: 查询天数
        max_results: 最大结果数
        save_to_db: 是否保存到数据库
        ingest: 是否执行 ingest 过程（抓取新数据），默认为 False（只查询已有数据）

    Returns:
        查询到的论文数量
    """
    # 初始化数据库
    from papergazer.store.db import init_db
    init_db(config.store.db_path)

    # 计算日期范围
    to_date = datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=days)

    if ingest:
        logger.info(f"抓取并查询近 {days} 天的 Europe PMC 论文")
        
        from papergazer.models import Author
        from papergazer.sources.europe_pmc import search_articles_by_date
        session = get_session()
        count = 0

        def europe_pmc_to_metadata(article: dict) -> PaperMetadata:
            """将 Europe PMC 文章数据转换为 PaperMetadata"""
            title = article.get("title", "") or ""

            # 提取作者
            authors = []
            if "authorList" in article and article["authorList"].get("author"):
                author_list = article["authorList"]["author"]
                if isinstance(author_list, list):
                    for author in author_list:
                        if isinstance(author, dict):
                            given = author.get("firstName", "")
                            last = author.get("lastName", "")
                            name = f"{given} {last}".strip()
                            if name:
                                affiliation = None
                                if "affiliation" in author:
                                    aff_data = author["affiliation"]
                                    if isinstance(aff_data, list) and len(aff_data) > 0:
                                        affiliation = (
                                            aff_data[0]
                                            if isinstance(aff_data[0], str)
                                            else aff_data[0].get("name", "")
                                        )
                                    elif isinstance(aff_data, str):
                                        affiliation = aff_data
                                authors.append(Author(name=name, affiliation=affiliation))
            elif "authorString" in article:
                author_string = article["authorString"]
                if author_string:
                    for name in author_string.split(","):
                        name = name.strip()
                        if name:
                            authors.append(Author(name=name))

            # 提取DOI
            doi = article.get("doi", "").strip() if article.get("doi") else None

            # 提取PMCID作为identifier
            pmcid = article.get("pmcid", "")
            if pmcid and not pmcid.startswith("PMC"):
                pmcid = f"PMC{pmcid}"
            identifier = doi.lower().strip() if doi else pmcid

            # 提取发布日期
            published_date = None
            if "firstPublicationDate" in article:
                try:
                    date_str = article["firstPublicationDate"]
                    published_date = datetime.strptime(date_str.split()[0], "%Y-%m-%d").date()
                except (ValueError, AttributeError):
                    pass
            elif "pubYear" in article:
                try:
                    year = int(article["pubYear"])
                    published_date = date(year, 1, 1)
                except (ValueError, TypeError):
                    pass

            # 提取期刊名称
            venue = None
            if "journalTitle" in article:
                venue = article["journalTitle"]
            elif "source" in article:
                venue = article["source"]

            # 提取摘要
            abstract = None
            if "abstractText" in article and article["abstractText"]:
                abstract = article["abstractText"]
            elif "abstract" in article and article["abstract"]:
                abstract = article["abstract"]

            # 提取URL
            url_landing = None
            if "pmcid" in article:
                pmcid_for_url = article["pmcid"]
                if not pmcid_for_url.startswith("PMC"):
                    pmcid_for_url = f"PMC{pmcid_for_url}"
                url_landing = f"https://europepmc.org/article/MED/{pmcid_for_url}"

            return PaperMetadata(
                source="eupmc",
                identifier=identifier,
                title=title,
                authors=authors,
                venue=venue,
                published_date=published_date,
                updated_date=datetime.now(timezone.utc) if published_date else None,
                doi=doi,
                url_landing=url_landing,
                abstract=abstract,
            )

        try:
            async for article in search_articles_by_date(
                from_date=from_date,
                to_date=to_date,
                page_size=25,
                max_results=max_results,
            ):
                if save_to_db:
                    try:
                        metadata = europe_pmc_to_metadata(article)
                        item = upsert_paper(session, metadata)
                        item.is_oa = True
                        item.oa_source = "eupmc"
                        session.commit()
                        count += 1
                    except Exception as e:
                        logger.warning(f"保存 Europe PMC 文章失败: {e}")
                        session.rollback()
                else:
                    count += 1

                if count >= max_results:
                    break
        finally:
            session.close()

        return count
    else:
        logger.info(f"查询数据库中近 {days} 天的 Europe PMC 论文")
        
        # 只查询数据库中已有的数据
        session = get_session()
        try:
            query = session.query(PaperItem).filter(
                PaperItem.source == "eupmc",
                PaperItem.published_date >= from_date,
                PaperItem.published_date <= to_date,
            )
            count = query.count()
        finally:
            session.close()
        
        return count


async def query_unpaywall_by_days(
    config: Settings,
    days: int,
    limit: Optional[int] = None,
    ingest: bool = False,
) -> dict:
    """
    查询指定天数内论文的 Unpaywall OA 状态

    Args:
        config: 应用配置
        days: 查询天数
        limit: 限制查询的论文数量
        ingest: 是否执行 ingest 过程（查询 Unpaywall API），默认为 False（只统计已有数据）

    Returns:
        统计信息字典
    """
    # 初始化数据库
    from papergazer.store.db import init_db
    init_db(config.store.db_path)
    
    session = get_session()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        items = (
            session.query(PaperItem)
            .filter(PaperItem.doi.isnot(None))
            .filter(PaperItem.doi != "")
            .filter(get_effective_date_filter(cutoff_date))
            .order_by(PaperItem.updated_date.desc())
            .limit(limit if limit else 1000)
            .all()
        )

        oa_count = 0
        non_oa_count = 0
        error_count = 0
        abstract_fetched_count = 0

        if ingest:
            logger.info(f"查询近 {days} 天论文的 Unpaywall OA 状态（调用 API）")
            
            from papergazer.sources.crossref import fetch_crossref_by_doi
            
            for item in items:
                try:
                    oa_info = await best_oa(item.doi, config.mailto)
                    db_item = session.query(PaperItem).filter_by(id=item.id).first()
                    if db_item:
                        db_item.is_oa = oa_info.is_oa
                        if oa_info.is_oa and oa_info.best_oa_location:
                            db_item.oa_source = "unpaywall"
                            db_item.oa_pdf_url = (
                                oa_info.best_oa_location.get("url_for_pdf")
                                or oa_info.best_oa_location.get("url_for_landing_page")
                                or oa_info.best_oa_location.get("url")
                            )
                        else:
                            db_item.oa_source = None
                            db_item.oa_pdf_url = None

                        # 如果数据库中没有摘要，尝试从Crossref获取
                        if not db_item.abstract_jats or db_item.abstract_jats.strip() == "":
                            try:
                                work = await fetch_crossref_by_doi(item.doi, config.mailto)
                                if work and work.abstract:
                                    db_item.abstract_jats = work.abstract
                                    abstract_fetched_count += 1
                            except Exception:
                                pass

                        session.commit()

                    if oa_info.is_oa:
                        oa_count += 1
                    else:
                        non_oa_count += 1

                    await asyncio.sleep(0.5)  # 避免请求过快

                except Exception as e:
                    logger.warning(f"查询 Unpaywall 失败 {item.doi}: {e}")
                    error_count += 1
        else:
            logger.info(f"统计数据库中近 {days} 天论文的 OA 状态（不调用 API）")
            
            # 只统计数据库中已有的 OA 状态
            for item in items:
                if item.is_oa is True:
                    oa_count += 1
                elif item.is_oa is False:
                    non_oa_count += 1
                else:
                    error_count += 1  # 未知状态

        return {
            "total": len(items),
            "oa_count": oa_count,
            "non_oa_count": non_oa_count,
            "error_count": error_count,
            "abstract_fetched_count": abstract_fetched_count,
        }
    finally:
        session.close()


async def query_all_sources_by_days(
    config: Settings,
    days: int,
    sources: Optional[List[str]] = None,
    max_results: Optional[dict] = None,
    ingest: bool = False,
) -> dict:
    """
    查询指定天数内所有数据源的论文

    Args:
        config: 应用配置
        days: 查询天数
        sources: 数据源列表，可选值：['arxiv', 'crossref', 'eupmc', 'unpaywall']
                 如果为 None，则查询所有数据源
        max_results: 各数据源的最大结果数限制，格式：{'eupmc': 1000, 'unpaywall': 100}
        ingest: 是否执行 ingest 过程（抓取新数据），默认为 False（只查询已有数据）

    Returns:
        各数据源的查询结果统计
    """
    # 初始化数据库（所有查询都需要数据库）
    from papergazer.store.db import init_db
    init_db(config.store.db_path)
    
    if sources is None:
        sources = ["arxiv", "crossref", "eupmc", "unpaywall"]

    if max_results is None:
        max_results = {}

    results = {}

    if "arxiv" in sources:
        try:
            count = await query_arxiv_by_days(config, days, ingest=ingest)
            results["arxiv"] = {"count": count, "status": "success"}
        except Exception as e:
            logger.error(f"arXiv 查询失败: {e}")
            results["arxiv"] = {"count": 0, "status": "error", "error": str(e)}

    if "crossref" in sources:
        try:
            count = await query_crossref_by_days(config, days, ingest=ingest)
            results["crossref"] = {"count": count, "status": "success"}
        except Exception as e:
            logger.error(f"Crossref 查询失败: {e}")
            results["crossref"] = {"count": 0, "status": "error", "error": str(e)}

    if "eupmc" in sources:
        try:
            count = await query_europe_pmc_by_days(
                config, days, max_results=max_results.get("eupmc", 1000), ingest=ingest
            )
            results["eupmc"] = {"count": count, "status": "success"}
        except Exception as e:
            logger.error(f"Europe PMC 查询失败: {e}")
            results["eupmc"] = {"count": 0, "status": "error", "error": str(e)}

    if "unpaywall" in sources:
        try:
            stats = await query_unpaywall_by_days(
                config, days, limit=max_results.get("unpaywall"), ingest=ingest
            )
            results["unpaywall"] = {"stats": stats, "status": "success"}
        except Exception as e:
            logger.error(f"Unpaywall 查询失败: {e}")
            results["unpaywall"] = {"stats": {}, "status": "error", "error": str(e)}

    return results


def search_papers_by_author(
    author_name: str,
    sources: Optional[List[str]] = None,
    limit: Optional[int] = None,
    db_path: Optional[str | Path] = None,
) -> List[Dict]:
    """
    按作者名称搜索论文

    Args:
        author_name: 作者名称（支持部分匹配）
        sources: 数据源列表，如果为 None 则查询所有数据源
        limit: 限制返回数量
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        论文列表
    """
    from papergazer.utils.analyze import _ensure_db_initialized
    import json
    
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        query = session.query(PaperItem)
        
        if sources:
            query = query.filter(PaperItem.source.in_(sources))
        
        # 在 authors_json 中搜索作者名称
        items = query.all()
        papers = []
        
        for item in items:
            if not item.authors_json:
                continue
            
            try:
                authors_data = json.loads(item.authors_json)
                for author_data in authors_data:
                    name = author_data.get("name", "").strip()
                    if author_name.lower() in name.lower():
                        authors = [a.get("name", "") for a in authors_data]
                        papers.append({
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
                        })
                        break  # 找到匹配的作者后，不再检查其他作者
            except (json.JSONDecodeError, TypeError):
                continue
            
            if limit and len(papers) >= limit:
                break
        
        return papers[:limit] if limit else papers
    finally:
        session.close()


def search_papers_by_venue(
    venue_name: str,
    sources: Optional[List[str]] = None,
    limit: Optional[int] = None,
    db_path: Optional[str | Path] = None,
) -> List[Dict]:
    """
    按期刊/会议名称搜索论文

    Args:
        venue_name: 期刊/会议名称（支持部分匹配）
        sources: 数据源列表，如果为 None 则查询所有数据源
        limit: 限制返回数量
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        论文列表
    """
    from papergazer.utils.analyze import _ensure_db_initialized
    import json
    
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        query = session.query(PaperItem).filter(
            PaperItem.venue.ilike(f"%{venue_name}%")
        )
        
        if sources:
            query = query.filter(PaperItem.source.in_(sources))
        
        query = query.order_by(PaperItem.published_date.desc())
        
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
            
            papers.append({
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
            })
        
        return papers
    finally:
        session.close()


def search_papers_by_keyword(
    keyword: str,
    sources: Optional[List[str]] = None,
    search_in: str = "both",  # 'title', 'abstract', 'both'
    limit: Optional[int] = None,
    db_path: Optional[str | Path] = None,
) -> List[Dict]:
    """
    按关键词搜索论文（标题和/或摘要）

    Args:
        keyword: 搜索关键词（支持部分匹配）
        sources: 数据源列表，如果为 None 则查询所有数据源
        search_in: 搜索范围：'title', 'abstract', 'both'
        limit: 限制返回数量
        db_path: 数据库路径（可选，如果未提供则尝试自动检测）

    Returns:
        论文列表
    """
    from papergazer.utils.analyze import _ensure_db_initialized
    import json
    
    _ensure_db_initialized(db_path)
    session = get_session()
    try:
        from sqlalchemy import or_
        
        conditions = []
        
        if search_in in ("title", "both"):
            conditions.append(PaperItem.title.ilike(f"%{keyword}%"))
        
        if search_in in ("abstract", "both"):
            conditions.append(PaperItem.abstract_jats.ilike(f"%{keyword}%"))
        
        if not conditions:
            return []
        
        query = session.query(PaperItem).filter(or_(*conditions))
        
        if sources:
            query = query.filter(PaperItem.source.in_(sources))
        
        query = query.order_by(PaperItem.published_date.desc())
        
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
            
            papers.append({
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
            })
        
        return papers
    finally:
        session.close()


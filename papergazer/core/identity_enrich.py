"""
作者/机构身份标准化核心逻辑
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from papergazer.config import Settings
from papergazer.store.db import (
    AffiliationIdentity,
    AuthorIdentity,
    PaperItem,
    get_session,
    init_db,
)
from papergazer.utils.identity import build_cache, normalize_name, search_orcid, search_ror

logger = logging.getLogger(__name__)


def enrich_identities(
    config: Settings,
    *,
    since_days: int | None = None,
    limit: int | None = None,
    sources: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    skip_orcid: bool = False,
    skip_ror: bool = False,
) -> dict[str, int]:
    """
    执行 ORCID / ROR 身份匹配

    Args:
        config: 全局配置
        since_days: 仅处理最近 N 天论文
        limit: 限制论文数量
        sources: 数据源过滤
        dry_run: 仅预览，不写入数据库
        force: 强制重新匹配（删除旧记录）
        skip_orcid: 跳过 ORCID 匹配
        skip_ror: 跳过 ROR 匹配

    Returns:
        统计信息字典
    """
    init_db(config.store.db_path)

    if (
        not config.identity.orcid.enabled
        and not config.identity.ror.enabled
        and not skip_orcid
        and not skip_ror
    ):
        logger.warning("ORCID 和 ROR 均未启用，结果可能为空。")

    cache = build_cache(config.identity)
    session = get_session()

    try:
        query = session.query(PaperItem)

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        if since_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=since_days)
            query = query.filter(
                PaperItem.ingested_at.isnot(None),
                PaperItem.ingested_at >= cutoff,
            )

        query = query.order_by(PaperItem.ingested_at.desc().nullslast())

        papers = query.all()
        if not force:
            # 过滤掉已有身份记录的论文
            filtered: list[PaperItem] = []
            for paper in papers:
                has_author_identity = (
                    session.query(AuthorIdentity).filter_by(paper_id=paper.id).first() is not None
                )
                if not has_author_identity:
                    filtered.append(paper)
            papers = filtered

        if limit:
            papers = papers[:limit]

        stats = {
            "papers": len(papers),
            "authors": 0,
            "affiliations": 0,
            "skipped": 0,
        }

        for paper in papers:
            if not paper.authors_json:
                stats["skipped"] += 1
                continue

            try:
                authors_data = json.loads(paper.authors_json)
            except (json.JSONDecodeError, TypeError):
                stats["skipped"] += 1
                continue

            author_records: list[AuthorIdentity] = []
            affiliation_records: list[AffiliationIdentity] = []

            for idx, author in enumerate(authors_data):
                source_name = author.get("name") or ""
                if not source_name.strip():
                    continue

                normalized = normalize_name(source_name)

                orcid_matches = []
                if not skip_orcid:
                    orcid_matches = search_orcid(source_name, config.identity, cache)

                best_orcid = orcid_matches[0] if orcid_matches else None

                author_records.append(
                    AuthorIdentity(
                        paper_id=paper.id,
                        local_index=idx,
                        source_name=source_name,
                        normalized_name=normalized,
                        orcid=best_orcid.get("orcid") if best_orcid else None,
                        confidence=str(best_orcid.get("score", "")) if best_orcid else None,
                        metadata_json=json.dumps(best_orcid, ensure_ascii=False)
                        if best_orcid
                        else None,
                    )
                )
                stats["authors"] += 1

                affiliations = author.get("affiliation") or []
                if isinstance(affiliations, dict):
                    affiliations = [affiliations]
                elif isinstance(affiliations, str):
                    affiliations = [affiliations]

                for aff_idx, aff in enumerate(affiliations):
                    if isinstance(aff, dict):
                        aff_name = aff.get("name") or ""
                    else:
                        aff_name = str(aff)

                    if not aff_name.strip():
                        continue

                    ror_matches = []
                    if not skip_ror:
                        ror_matches = search_ror(aff_name, config.identity, cache)

                    best_ror = ror_matches[0] if ror_matches else None
                    affiliation_records.append(
                        AffiliationIdentity(
                            paper_id=paper.id,
                            local_index=aff_idx,
                            source_name=aff_name,
                            normalized_name=normalize_name(aff_name),
                            ror_id=best_ror.get("ror_id") if best_ror else None,
                            country_code=best_ror.get("country") if best_ror else None,
                            latitude=str(best_ror.get("latitude"))
                            if best_ror and best_ror.get("latitude")
                            else None,
                            longitude=str(best_ror.get("longitude"))
                            if best_ror and best_ror.get("longitude")
                            else None,
                            confidence=str(best_ror.get("score", "")) if best_ror else None,
                            metadata_json=json.dumps(best_ror, ensure_ascii=False)
                            if best_ror
                            else None,
                        )
                    )
                    stats["affiliations"] += 1

            if dry_run:
                continue

            if force:
                session.query(AuthorIdentity).filter_by(paper_id=paper.id).delete()
                session.query(AffiliationIdentity).filter_by(paper_id=paper.id).delete()
                session.flush()

            for author_record in author_records:
                session.add(author_record)
            for affiliation_record in affiliation_records:
                session.add(affiliation_record)

            session.commit()

    finally:
        session.close()

    logger.info(
        "身份匹配完成：论文 %s，作者记录 %s，机构记录 %s，跳过 %s（dry_run=%s）",
        stats["papers"],
        stats["authors"],
        stats["affiliations"],
        stats["skipped"],
        dry_run,
    )

    return stats

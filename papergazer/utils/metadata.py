"""
外部元数据抓取与补全工具（Crossref / OpenAlex / Unpaywall）
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

import httpx

from papergazer.store.db import PaperItem, get_session

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"
OPENALEX_API_URL = "https://api.openalex.org/works"
UNPAYWALL_API_URL = "https://api.unpaywall.org/v2"


class MetadataFetchError(RuntimeError):
    """外部元数据抓取失败"""


def _build_user_agent(mailto: str | None) -> str:
    suffix = f" ({mailto})" if mailto else ""
    return f"PaperGazer/1.0{suffix}"


def fetch_crossref_metadata(doi: str, mailto: str | None = None, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """获取 Crossref 元数据"""
    if not doi:
        return None

    url = f"{CROSSREF_API_URL}/{quote_plus(doi)}"
    params = {"mailto": mailto} if mailto else {}

    headers = {"User-Agent": _build_user_agent(mailto)}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 404:
                logger.warning("Crossref 未找到 DOI: %s", doi)
                return None
            resp.raise_for_status()
            return resp.json().get("message")
    except httpx.HTTPError as exc:
        raise MetadataFetchError(f"Crossref 请求失败 ({doi}): {exc}") from exc


def fetch_openalex_metadata(doi: str, mailto: str | None = None, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """获取 OpenAlex 元数据"""
    if not doi:
        return None

    openalex_id = f"https://doi.org/{doi}"
    url = f"{OPENALEX_API_URL}/{quote_plus(openalex_id)}"
    params = {"mailto": mailto} if mailto else {}
    headers = {"User-Agent": _build_user_agent(mailto)}

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 404:
                logger.warning("OpenAlex 未找到 DOI: %s", doi)
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise MetadataFetchError(f"OpenAlex 请求失败 ({doi}): {exc}") from exc


def fetch_unpaywall_metadata(doi: str, email: str | None = None, timeout: float = 20.0) -> Optional[Dict[str, Any]]:
    """获取 Unpaywall 元数据"""
    if not doi:
        return None

    params = {}
    if email:
        params["email"] = email
    url = f"{UNPAYWALL_API_URL}/{quote_plus(doi)}"

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 404:
                logger.warning("Unpaywall 未找到 DOI: %s", doi)
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise MetadataFetchError(f"Unpaywall 请求失败 ({doi}): {exc}") from exc


def _select_papers(session, column_name: str, limit: int | None, since_days: int | None, force: bool) -> list[PaperItem]:
    column = getattr(PaperItem, column_name)
    query = session.query(PaperItem).filter(PaperItem.doi.isnot(None))
    if not force:
        query = query.filter((column.is_(None)) | (column == ""))
    if since_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        query = query.filter(PaperItem.ingested_at >= cutoff)
    query = query.order_by(PaperItem.ingested_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def update_paper_from_crossref(paper: PaperItem, message: dict) -> None:
    title_list = message.get("title") or []
    if title_list and not paper.title:
        paper.title = title_list[0]

    if message.get("abstract"):
        paper.abstract_jats = message["abstract"]

    issn_list = message.get("ISSN") or []
    if issn_list:
        if not paper.issn_print:
            paper.issn_print = issn_list[0]
        if len(issn_list) > 1 and not paper.issn_online:
            paper.issn_online = issn_list[1]

    for item in message.get("link", []) or []:
        if item.get("content-type") == "text/html" and not paper.url_landing:
            paper.url_landing = item.get("URL")
            break

    container = message.get("container-title") or []
    if container and not paper.venue:
        paper.venue = container[0]

    pub_dt = _parse_date_parts(message, ("issued", "published-print", "published-online"))
    if pub_dt:
        paper.published_date = pub_dt.date()

    paper.crossref_json = json.dumps(message, ensure_ascii=False)
    paper.references_json = json.dumps(message.get("reference") or [], ensure_ascii=False)
    paper.funder_json = json.dumps(message.get("funder") or [], ensure_ascii=False)
    paper.license_json = json.dumps(message.get("license") or [], ensure_ascii=False)


def update_paper_from_openalex(paper: PaperItem, work: dict) -> None:
    paper.openalex_json = json.dumps(work, ensure_ascii=False)

    if work.get("title") and not paper.title:
        paper.title = work["title"]

    if work.get("host_venue"):
        paper.host_venue_json = json.dumps(work["host_venue"], ensure_ascii=False)
        venue_name = work["host_venue"].get("display_name")
        if venue_name and not paper.venue:
            paper.venue = venue_name

    if work.get("concepts"):
        paper.concepts_json = json.dumps(work["concepts"], ensure_ascii=False)

    if work.get("referenced_works"):
        paper.referenced_work_ids_json = json.dumps(work["referenced_works"], ensure_ascii=False)

    if work.get("cited_by_count") is not None:
        paper.cited_by_count = work["cited_by_count"]

    open_access = work.get("open_access") or {}
    if open_access:
        paper.is_oa = open_access.get("is_oa", paper.is_oa)
        paper.oa_status = open_access.get("oa_status") or paper.oa_status
        paper.oa_license = open_access.get("license") or paper.oa_license
        if open_access.get("oa_url"):
            paper.oa_pdf_url = open_access["oa_url"]

    primary_location = work.get("primary_location") or {}
    landing = primary_location.get("landing_page_url")
    if landing and not paper.url_landing:
        paper.url_landing = landing

    if work.get("doi") and not paper.doi:
        paper.doi = work["doi"].replace("https://doi.org/", "")

    if work.get("publication_date"):
        try:
            paper.published_date = datetime.fromisoformat(work["publication_date"]).date()
        except ValueError:
            pass
    elif work.get("publication_year") and not paper.published_date:
        paper.published_date = datetime(work["publication_year"], 1, 1).date()


def update_paper_from_unpaywall(paper: PaperItem, data: dict) -> None:
    paper.unpaywall_json = json.dumps(data, ensure_ascii=False)

    paper.is_oa = data.get("is_oa", paper.is_oa)
    paper.oa_status = data.get("oa_status") or paper.oa_status

    best = data.get("best_oa_location") or {}
    if best:
        paper.oa_source = best.get("host_type") or paper.oa_source
        paper.oa_license = best.get("license") or paper.oa_license
        pdf_url = best.get("url_for_pdf") or best.get("url")
        if pdf_url:
            paper.oa_pdf_url = pdf_url

    if data.get("license") and not paper.oa_license:
        paper.oa_license = data["license"]

    if data.get("published_date") and not paper.published_date:
        try:
            paper.published_date = datetime.fromisoformat(data["published_date"]).date()
        except ValueError:
            pass


def enrich_crossref_metadata(
    mailto: str | None,
    *,
    limit: int | None = None,
    since_days: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    session = get_session()
    papers = _select_papers(session, "crossref_json", limit, since_days, force)

    success = skipped = failed = 0

    for paper in papers:
        if dry_run:
            logger.info("[Crossref] dry-run 预计更新 #%s (%s)", paper.id, paper.doi)
            continue
        try:
            message = fetch_crossref_metadata(paper.doi, mailto)
            if not message:
                skipped += 1
                continue
            update_paper_from_crossref(paper, message)
            session.add(paper)
            session.commit()
            success += 1
            logger.debug("[Crossref] 更新成功 #%s", paper.id)
        except MetadataFetchError as exc:
            logger.error("[Crossref] 请求失败 #%s (%s): %s", paper.id, paper.doi, exc)
            failed += 1
        except Exception as exc:
            session.rollback()
            logger.exception("[Crossref] 更新失败 #%s (%s): %s", paper.id, paper.doi, exc)
            failed += 1

    session.close()
    return {"success": success, "skipped": skipped, "failed": failed, "total": len(papers)}


def enrich_openalex_metadata(
    mailto: str | None,
    *,
    limit: int | None = None,
    since_days: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    session = get_session()
    papers = _select_papers(session, "openalex_json", limit, since_days, force)

    success = skipped = failed = 0

    for paper in papers:
        if dry_run:
            logger.info("[OpenAlex] dry-run 预计更新 #%s (%s)", paper.id, paper.doi)
            continue
        try:
            work = fetch_openalex_metadata(paper.doi, mailto)
            if not work:
                skipped += 1
                continue
            update_paper_from_openalex(paper, work)
            session.add(paper)
            session.commit()
            success += 1
            logger.debug("[OpenAlex] 更新成功 #%s", paper.id)
        except MetadataFetchError as exc:
            logger.error("[OpenAlex] 请求失败 #%s (%s): %s", paper.id, paper.doi, exc)
            failed += 1
        except Exception as exc:
            session.rollback()
            logger.exception("[OpenAlex] 更新失败 #%s (%s): %s", paper.id, paper.doi, exc)
            failed += 1

    session.close()
    return {"success": success, "skipped": skipped, "failed": failed, "total": len(papers)}


def enrich_unpaywall_metadata(
    email: str | None,
    *,
    limit: int | None = None,
    since_days: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    session = get_session()
    papers = _select_papers(session, "unpaywall_json", limit, since_days, force)

    success = skipped = failed = 0

    for paper in papers:
        if dry_run:
            logger.info("[Unpaywall] dry-run 预计更新 #%s (%s)", paper.id, paper.doi)
            continue
        try:
            data = fetch_unpaywall_metadata(paper.doi, email)
            if not data:
                skipped += 1
                continue
            update_paper_from_unpaywall(paper, data)
            session.add(paper)
            session.commit()
            success += 1
            logger.debug("[Unpaywall] 更新成功 #%s", paper.id)
        except MetadataFetchError as exc:
            logger.error("[Unpaywall] 请求失败 #%s (%s): %s", paper.id, paper.doi, exc)
            failed += 1
        except Exception as exc:
            session.rollback()
            logger.exception("[Unpaywall] 更新失败 #%s (%s): %s", paper.id, paper.doi, exc)
            failed += 1

    session.close()
    return {"success": success, "skipped": skipped, "failed": failed, "total": len(papers)}


def _parse_date_parts(message: dict, keys: tuple[str, ...]) -> Optional[datetime]:
    for key in keys:
        data = message.get(key)
        if data and "date-parts" in data:
            parts = data["date-parts"][0]
            try:
                year = parts[0]
                month = parts[1] if len(parts) > 1 else 1
                day = parts[2] if len(parts) > 2 else 1
                return datetime(year, month, day, tzinfo=timezone.utc)
            except (ValueError, IndexError, TypeError):
                continue
    return None




"""
开放获取与 FAIR 指标分析
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from papergazer.config import Settings
from papergazer.store.db import OAMetric, PaperItem, get_session, init_db
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)

DATA_LINK_HINTS = ["zenodo.org", "figshare.com", "dataverse", "dataset", "data."]
CODE_LINK_HINTS = ["github.com", "gitlab.com", "bitbucket.org", "code."]


def _detect_links(text: str, hints) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in hints)


def monitor_oa(
    config: Settings,
    *,
    window_days: int = 30,
    sources: list[str] | None = None,
    persist: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """
    统计开放获取与 FAIR 指标

    Args:
        config: 全局配置
        window_days: 统计窗口天数
        sources: 数据源过滤
        persist: 是否写入 analytics_oa
        dry_run: 仅统计，不写入
    """
    init_db(config.store.db_path)
    session = get_session()

    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(days=window_days)

    try:
        query = session.query(PaperItem).filter(get_effective_date_filter(window_start))

        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        papers = query.all()

        total_count = len(papers)
        oa_status_counter: Counter[str] = Counter()
        license_counter: Counter[str] = Counter()
        oa_count = 0
        gold_count = 0
        green_count = 0
        bronze_count = 0
        data_links = 0
        code_links = 0

        for paper in papers:
            status = (paper.oa_status or "").lower()
            if status:
                oa_status_counter[status] += 1

            if status in {"gold", "hybrid"}:
                gold_count += 1
            elif status == "green":
                green_count += 1
            elif status == "bronze":
                bronze_count += 1

            if paper.is_oa:
                oa_count += 1

            if paper.license_json:
                try:
                    licenses = json.loads(paper.license_json)
                    if isinstance(licenses, list):
                        for lic in licenses:
                            name = (
                                lic.get("URL") or lic.get("url") or lic.get("content-version") or ""
                            )
                            if name:
                                license_counter[name] += 1
                    elif isinstance(licenses, dict):
                        name = licenses.get("URL") or licenses.get("url") or ""
                        if name:
                            license_counter[name] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
            elif paper.oa_license:
                license_counter[paper.oa_license] += 1

            candidate_texts = [paper.oa_pdf_url or "", paper.url_landing or ""]
            if paper.references_json:
                try:
                    refs = json.loads(paper.references_json)
                    for ref in refs:
                        for key in ("URL", "url", "unstructured"):
                            val = ref.get(key)
                            if isinstance(val, str):
                                candidate_texts.append(val)
                except (json.JSONDecodeError, TypeError):
                    pass

            text_combined = " ".join(candidate_texts)
            if _detect_links(text_combined, DATA_LINK_HINTS):
                data_links += 1
            if _detect_links(text_combined, CODE_LINK_HINTS):
                code_links += 1

        result = {
            "window_start": window_start,
            "window_end": window_end,
            "total_count": total_count,
            "oa_count": oa_count,
            "gold_count": gold_count,
            "green_count": green_count,
            "bronze_count": bronze_count,
            "license_counter": license_counter,
            "oa_status_counter": oa_status_counter,
            "data_link_count": data_links,
            "code_link_count": code_links,
            "persisted": False,
        }

        if persist and not dry_run:
            session.query(OAMetric).filter(
                OAMetric.window_start == window_start,
                OAMetric.window_end == window_end,
                (OAMetric.source == (",".join(sources) if sources else None)),
            ).delete()

            metric = OAMetric(
                window_start=window_start,
                window_end=window_end,
                source=",".join(sources) if sources else None,
                total_count=total_count,
                oa_count=oa_count,
                gold_count=gold_count,
                green_count=green_count,
                bronze_count=bronze_count,
                license_json=json.dumps(license_counter, ensure_ascii=False),
                data_link_count=data_links,
                code_link_count=code_links,
                metadata_json=json.dumps(
                    {
                        "window_days": window_days,
                        "oa_status": dict(oa_status_counter),
                    },
                    ensure_ascii=False,
                ),
            )
            session.add(metric)
            session.commit()
            result["persisted"] = True

        logger.info(
            "OA 指标完成：窗口 %s-%s，OA=%s/%s，数据链接=%s，代码链接=%s，写入=%s",
            window_start.date(),
            window_end.date(),
            oa_count,
            total_count,
            data_links,
            code_links,
            result["persisted"],
        )

        return result
    finally:
        session.close()

"""
作者与机构身份识别工具（ORCID / ROR）
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from papergazer.config import IdentityConfig
from papergazer.utils.http_client import sync_client

logger = logging.getLogger(__name__)


class IdentityCache:
    """简单文件缓存，避免重复请求外部 API"""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / namespace / f"{digest}.json"

    def load(self, namespace: str, key: str) -> dict[str, Any] | None:
        path = self._path_for(namespace, key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            logger.warning("身份缓存损坏，忽略: %s", path)
            return None

    def store(self, namespace: str, key: str, payload: dict[str, Any]) -> None:
        path = self._path_for(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)


def normalize_name(name: str) -> str:
    return " ".join(part.strip().lower() for part in name.split() if part.strip())


def search_orcid(name: str, config: IdentityConfig, cache: IdentityCache) -> list[dict[str, Any]]:
    if not config.orcid.enabled:
        return []

    normalized = normalize_name(name)
    cache_key = f"orcid::{normalized}"
    cached = cache.load("orcid", cache_key)
    if cached is not None:
        return cached.get("results", [])

    headers = {"Accept": "application/json"}
    if config.orcid.token:
        headers["Authorization"] = f"Bearer {config.orcid.token}"

    params = {
        "q": f'"{name}"',
        "rows": str(config.orcid.max_results),
    }

    try:
        with sync_client(timeout=15.0, headers=headers) as client:
            resp = client.get(config.orcid.base_url, params=params)
            if resp.status_code == 404:
                logger.debug("ORCID 未找到：%s", name)
                cache.store("orcid", cache_key, {"results": []})
                return []
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("ORCID 请求失败 (%s): %s", name, exc)
        return []

    expanded = data.get("expanded-result", [])
    results: list[dict[str, Any]] = []
    for item in expanded[: config.orcid.max_results]:
        display_status = item.get("display-name", "")
        score = float(item.get("relevancy-score", 0.0) or 0.0)
        if score < config.orcid.min_score:
            continue
        results.append(
            {
                "name": display_status,
                "orcid": item.get("orcid-id"),
                "score": score,
                "keywords": item.get("keywords"),
                "other_names": item.get("other-names"),
            }
        )

    cache.store("orcid", cache_key, {"results": results})
    return results


def search_ror(name: str, config: IdentityConfig, cache: IdentityCache) -> list[dict[str, Any]]:
    if not config.ror.enabled:
        return []

    normalized = normalize_name(name)
    cache_key = f"ror::{normalized}"
    cached = cache.load("ror", cache_key)
    if cached is not None:
        return cached.get("results", [])

    params = {
        "query": name,
        "all": "true",
    }

    try:
        with sync_client(timeout=15.0) as client:
            resp = client.get(config.ror.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("ROR 请求失败 (%s): %s", name, exc)
        return []

    items = data.get("items", [])
    results: list[dict[str, Any]] = []
    for item in items[: config.ror.max_results]:
        score = float(item.get("score") or 0.0)
        if score < config.ror.min_score:
            continue
        location = item.get("country", {}) or {}
        geo = item.get("addresses", [{}])[0] if item.get("addresses") else {}
        results.append(
            {
                "name": item.get("name"),
                "ror_id": item.get("id"),
                "score": score,
                "country": location.get("country_code"),
                "latitude": geo.get("lat"),
                "longitude": geo.get("lng"),
            }
        )

    cache.store("ror", cache_key, {"results": results})
    return results


def build_cache(config: IdentityConfig) -> IdentityCache:
    return IdentityCache(config.cache_dir)

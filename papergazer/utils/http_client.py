"""Shared httpx client defaults for PaperGazer."""

from typing import Any

import httpx

# httpx defaults to trust_env=True, which picks up HTTP(S)_PROXY from the shell.
# Local proxies (e.g. Clash on 127.0.0.1:7890) often fail TLS to academic APIs
# while direct connections work fine.
DEFAULT_TRUST_ENV = False


def async_client(**kwargs: Any) -> httpx.AsyncClient:
    """Create an AsyncClient that ignores shell proxy env by default."""
    kwargs.setdefault("trust_env", DEFAULT_TRUST_ENV)
    return httpx.AsyncClient(**kwargs)


def sync_client(**kwargs: Any) -> httpx.Client:
    """Create a sync Client that ignores shell proxy env by default."""
    kwargs.setdefault("trust_env", DEFAULT_TRUST_ENV)
    return httpx.Client(**kwargs)

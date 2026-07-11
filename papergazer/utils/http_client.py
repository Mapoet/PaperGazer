"""Shared, explicitly configurable httpx client policy."""

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class _HttpPolicy:
    trust_env: bool = True
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    write_timeout: float = 60.0
    pool_timeout: float = 10.0


_policy = _HttpPolicy()


def configure_http(config: Any) -> None:
    """Apply validated application HTTP settings to subsequent clients."""
    global _policy
    _policy = _HttpPolicy(
        trust_env=config.trust_env,
        connect_timeout=config.connect_timeout,
        read_timeout=config.read_timeout,
        write_timeout=config.write_timeout,
        pool_timeout=config.pool_timeout,
    )


def _default_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=_policy.connect_timeout,
        read=_policy.read_timeout,
        write=_policy.write_timeout,
        pool=_policy.pool_timeout,
    )


def async_client(**kwargs: Any) -> httpx.AsyncClient:
    """Create an async client using the configured application policy."""
    kwargs.setdefault("trust_env", _policy.trust_env)
    kwargs.setdefault("timeout", _default_timeout())
    return httpx.AsyncClient(**kwargs)


def sync_client(**kwargs: Any) -> httpx.Client:
    """Create a sync client using the configured application policy."""
    kwargs.setdefault("trust_env", _policy.trust_env)
    kwargs.setdefault("timeout", _default_timeout())
    return httpx.Client(**kwargs)

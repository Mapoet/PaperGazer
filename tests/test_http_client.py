"""Tests for the shared outbound HTTP policy."""

from papergazer.config import HttpConfig
from papergazer.utils.http_client import configure_http, sync_client


def test_http_policy_respects_environment_by_default() -> None:
    configure_http(HttpConfig())
    client = sync_client()
    try:
        assert client._trust_env is True
    finally:
        client.close()


def test_explicit_client_override_wins_over_application_policy() -> None:
    configure_http(HttpConfig(trust_env=True))
    client = sync_client(trust_env=False)
    try:
        assert client._trust_env is False
    finally:
        client.close()

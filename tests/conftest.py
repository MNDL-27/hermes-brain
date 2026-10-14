import socket
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class ProviderField:
    key: str
    label: str
    kind: str
    description: str = ""
    env_key: str | None = None
    env_fallbacks: tuple[str, ...] = ()
    placeholder: str = ""
    inline: bool = False
    group: str = ""
    default: str | None = None


@dataclass(frozen=True)
class ProviderConfigSchema:
    name: str
    label: str
    storage: str
    fields: tuple[ProviderField, ...]


# Stub constants (D-02)
KIND_SECRET: str = "secret"
KIND_TEXT: str = "text"
STORAGE_FLAT_JSON: str = "flat_json"


def pytest_configure(config):
    """Stub for conftest setup."""
    pass


class _OfflineNetworkAttempt(RuntimeError):
    """Raised when a test makes an unmocked outbound network call.

    The unit suite must be hermetic (CLAUDE.md CI-reliability: "Unit tests must
    run offline without requiring live Notion API credentials or a live Hermes
    daemon"). A blocked-egress environment would otherwise make store._request
    block on requests(..., timeout=30) x3 retries and hang CI for ~10 minutes.
    This fails such calls loud and fast instead of blocking, and surfaces wrong
    mocks. Mark a test needing real egress with @pytest.mark.network.
    """


def _deny_socket_connect(self, *args, **kwargs):
    raise _OfflineNetworkAttempt(
        "Unmocked outbound network attempt in the offline unit suite "
        "(socket.connect). Mock the network call or mark the test "
        "@pytest.mark.network."
    )


def _deny_getaddrinfo(*args, **kwargs):
    raise _OfflineNetworkAttempt(
        "Unmocked DNS resolution in the offline unit suite "
        "(socket.getaddrinfo). Mock the network call or mark the test "
        "@pytest.mark.network."
    )


@pytest.fixture(autouse=True)
def _hermetic_offline(monkeypatch, tmp_path):
    """Neutralize live credentials and deny real network for every test.

    Runs at setup (before each test body) so a test that sets its own key or
    patches store.get_api_key still overrides inside its body.
    """
    # (1) Env neutralization: store.get_api_key() -> None so store._headers()
    # raises "NOTION_API_KEY not set" instantly instead of reaching Notion.
    # Point HERMES_HOME at an empty tmp dir so store._load_env_file() cannot
    # pull a live token out of the host's ~/.hermes/.env.
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    # (2) Network deny at the socket layer: fail before DNS and before the
    # blocking connect, so any unmocked outbound call (including the daemon
    # worker's urlopen to GitHub and requests to Notion) fails fast and loud.
    monkeypatch.setattr(socket.socket, "connect", _deny_socket_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _deny_socket_connect)
    monkeypatch.setattr(socket, "getaddrinfo", _deny_getaddrinfo)

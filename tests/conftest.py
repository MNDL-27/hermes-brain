from dataclasses import dataclass
from typing import Tuple, Type

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

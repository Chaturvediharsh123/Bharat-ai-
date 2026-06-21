"""bharatai.bootstrap — the composition root that wires every layer via DI."""
from __future__ import annotations

from functools import lru_cache

from bharatai.bootstrap.container import Container
from bharatai.bootstrap.factory import build_container
from bharatai.bootstrap.service_bundle import ServiceBundle
from bharatai.bootstrap.testing import build_test_container
from bharatai.config.settings import get_settings


@lru_cache
def get_container() -> Container:
    """Return the process-wide wired container (built once from settings)."""
    return build_container(get_settings())


__all__ = [
    "Container",
    "ServiceBundle",
    "build_container",
    "build_test_container",
    "get_container",
]

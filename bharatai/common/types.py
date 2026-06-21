"""bharatai.common.types — shared type aliases used across layers."""
from __future__ import annotations

from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]
"""A JSON-serializable object decoded into a Python dict."""

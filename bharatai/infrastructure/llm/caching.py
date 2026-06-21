"""bharatai.infrastructure.llm.caching — an in-process cache for the LLM.

Wraps any LLMPort and memoizes DETERMINISTIC completions (temperature == 0), keyed by a
hash of (system, prompt, max_tokens). Non-deterministic calls (temperature > 0) bypass the
cache. This cuts repeated cost for stable prompts (eligibility explanations, simplifications)
without changing any output.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict

from bharatai.application.ports.llm import LLMPort


class CachingLLM:
    """LLMPort decorator that memoizes temperature-0 completions (LRU-bounded)."""

    def __init__(self, inner: LLMPort, max_entries: int = 512) -> None:
        """Wrap an inner LLM; keep at most ``max_entries`` cached completions."""
        self._inner = inner
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._max_entries = max_entries

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Return a completion, served from cache for deterministic repeat calls."""
        if temperature != 0.0:  # non-deterministic — never cache
            return self._inner.complete(
                prompt, system=system, temperature=temperature, max_tokens=max_tokens
            )
        key = self._key(prompt, system, max_tokens)
        if key in self._cache:
            self._cache.move_to_end(key)  # mark as recently used
            return self._cache[key]
        result = self._inner.complete(
            prompt, system=system, temperature=0.0, max_tokens=max_tokens
        )
        self._cache[key] = result
        if len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)  # evict least-recently-used
        return result

    @staticmethod
    def _key(prompt: str, system: str | None, max_tokens: int | None) -> str:
        digest = hashlib.sha256()
        for part in (system or "", "\x00", prompt, "\x00", str(max_tokens)):
            digest.update(part.encode("utf-8"))
        return digest.hexdigest()

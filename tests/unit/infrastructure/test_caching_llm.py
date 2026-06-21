"""Tests for the CachingLLM decorator."""
from __future__ import annotations

from bharatai.infrastructure.llm.caching import CachingLLM


class _CountingLLM:
    """An LLM that returns a unique answer per call and counts its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        self.calls += 1
        return f"answer-{self.calls}"


def test_caches_deterministic_repeat_calls() -> None:
    inner = _CountingLLM()
    llm = CachingLLM(inner)
    first = llm.complete("hello", system="sys")
    second = llm.complete("hello", system="sys")
    assert first == second  # served from cache
    assert inner.calls == 1


def test_distinct_prompts_are_not_shared() -> None:
    inner = _CountingLLM()
    llm = CachingLLM(inner)
    assert llm.complete("a") != llm.complete("b")
    assert inner.calls == 2


def test_non_deterministic_calls_bypass_cache() -> None:
    inner = _CountingLLM()
    llm = CachingLLM(inner)
    llm.complete("hello", temperature=0.7)
    llm.complete("hello", temperature=0.7)
    assert inner.calls == 2  # temperature > 0 is never cached


def test_lru_eviction() -> None:
    inner = _CountingLLM()
    llm = CachingLLM(inner, max_entries=2)
    llm.complete("a")  # call 1 -> {a}
    llm.complete("b")  # call 2 -> {a, b}
    llm.complete("c")  # call 3 -> evicts 'a' (LRU) -> {b, c}
    assert inner.calls == 3
    llm.complete("b")  # cache hit -> {c, b}
    assert inner.calls == 3
    llm.complete("a")  # call 4 ('a' was evicted) -> evicts 'c' -> {b, a}
    assert inner.calls == 4
    llm.complete("b")  # still cached
    assert inner.calls == 4

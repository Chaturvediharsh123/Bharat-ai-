"""Fake LLMPort for offline tests: records calls and returns a canned response."""
from __future__ import annotations


class FakeLLM:
    """A deterministic stand-in for an LLMPort."""

    def __init__(self, response: str = "Grounded fake answer.") -> None:
        self.response = response
        self.calls: list[dict[str, str | None]] = []

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append({"prompt": prompt, "system": system})
        return self.response

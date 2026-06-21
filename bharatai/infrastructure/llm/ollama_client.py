"""bharatai.infrastructure.llm.ollama_client — LLMPort backed by a local Ollama server.

The only place the ``ollama`` client is used; it is imported lazily so the module loads
without the dependency or a running server. Configured for tiered local models.
"""
from __future__ import annotations

from typing import Any


class OllamaLLM:
    """LLMPort implementation calling a local Ollama chat endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gemma3:12b",
        timeout_s: int = 120,
    ) -> None:
        """Store connection/model config; the client connects on first use."""
        self._base_url = base_url
        self._model = model
        self._timeout = timeout_s
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import ollama

            self._client = ollama.Client(host=self._base_url, timeout=self._timeout)
        return self._client

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for the prompt via Ollama chat."""
        client = self._ensure_client()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        response = client.chat(model=self._model, messages=messages, options=options)
        return str(response["message"]["content"])

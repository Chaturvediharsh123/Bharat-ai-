"""bharatai.config.settings — typed application settings loaded from the environment.

Settings are grouped into nested models (db/llm/embedding/knowledge/ocr) and read from
environment variables (or a .env file) using the ``__`` nested delimiter, e.g.
``KNOWLEDGE__MIN_SCORE=0.4`` sets ``settings.knowledge.min_score``.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DeploymentMode = Literal["local_full", "remote_llm", "demo_stub"]


class DbSettings(BaseModel):
    """SQLite database settings."""

    sqlite_path: str = "./data/bharatai.db"
    busy_timeout_ms: int = 5000


class LlmSettings(BaseModel):
    """Ollama LLM settings (tiered models)."""

    base_url: str = "http://localhost:11434"
    default_model: str = "gemma3:12b"
    fast_model: str = "qwen2.5:7b"
    heavy_model: str = "qwen2.5:14b"
    timeout_s: int = 120
    temperature: float = 0.0


class EmbeddingSettings(BaseModel):
    """Local sentence-embedding settings."""

    model_name: str = "BAAI/bge-small-en-v1.5"
    device: str = "cpu"


class KnowledgeSettings(BaseModel):
    """RAG knowledge-base settings."""

    index_dir: str = "./data/index/faiss"
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 20
    min_score: float = 0.35


class OcrSettings(BaseModel):
    """PaddleOCR / document-intake settings."""

    lang: str = "en"
    use_gpu: bool = False
    upload_dir: str = "./data/uploads"
    max_file_mb: int = 10


class SecuritySettings(BaseModel):
    """Authentication and token settings."""

    token_secret: str = "dev-insecure-change-me"  # MUST be overridden outside local dev
    token_ttl_seconds: int = 3600
    pbkdf2_iterations: int = 600_000
    otp_ttl_seconds: int = 300

    @property
    def is_default_secret(self) -> bool:
        """True if the token secret is still the insecure development default."""
        return self.token_secret == "dev-insecure-change-me"


class AppSettings(BaseSettings):
    """Root application settings (all configuration in one typed object)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    log_level: str = "INFO"
    deployment_mode: DeploymentMode = "local_full"

    db: DbSettings = Field(default_factory=DbSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    knowledge: KnowledgeSettings = Field(default_factory=KnowledgeSettings)
    ocr: OcrSettings = Field(default_factory=OcrSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @model_validator(mode="after")
    def _reject_default_secret_outside_local(self) -> AppSettings:
        """Refuse to start outside local dev with the public default token secret."""
        if self.security.is_default_secret and self.app_env != "local":
            raise ValueError(
                "SECURITY__TOKEN_SECRET is the insecure dev default — refusing to start "
                "outside local (tokens would be forgeable with a well-known key)"
            )
        return self


@lru_cache
def get_settings() -> AppSettings:
    """Return the process-wide settings singleton (loaded once)."""
    return AppSettings()

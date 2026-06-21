"""Integration test: build_container wires the real production object graph (lazy models)."""
from __future__ import annotations

from pathlib import Path

from bharatai.bootstrap.factory import build_container
from bharatai.config.settings import AppSettings, DbSettings, KnowledgeSettings, OcrSettings
from bharatai.domain.citizen import CitizenProfile


def test_build_container_wires_and_persists(tmp_path: Path) -> None:
    settings = AppSettings(
        db=DbSettings(sqlite_path=str(tmp_path / "app.db")),
        knowledge=KnowledgeSettings(index_dir=str(tmp_path / "idx")),
        ocr=OcrSettings(upload_dir=str(tmp_path / "uploads")),
    )
    container = build_container(settings)  # constructs real adapters (models load lazily)

    services = container.services
    assert services.graph_runner is not None
    assert services.schemes.list_active() == []  # fresh DB

    profile = CitizenProfile(full_name="Test User")
    services.citizens.save(profile)
    loaded = services.citizens.get(profile.id)
    assert loaded is not None and loaded.full_name == "Test User"

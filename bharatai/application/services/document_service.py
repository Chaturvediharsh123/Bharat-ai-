"""bharatai.application.services.document_service — uploaded document use cases."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bharatai.application.ports.documents import FileStorePort
from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType

UowFactory = Callable[[], UnitOfWork]


class DocumentService:
    """Stores uploaded document bytes and their records; persists analysis results."""

    def __init__(self, uow_factory: UowFactory, file_store: FileStorePort) -> None:
        """Inject the UnitOfWork factory and the file store."""
        self._uow_factory = uow_factory
        self._file_store = file_store

    def save_upload(
        self, citizen_id: str, doc_type: DocumentType, data: bytes, *, filename: str = ""
    ) -> DocumentRecord:
        """Persist the uploaded bytes and create a PENDING document record."""
        path = self._file_store.save(data, suffix=Path(filename).suffix)
        record = DocumentRecord(
            citizen_id=citizen_id,
            doc_type=doc_type,
            file_path=path,
            file_name=filename or None,
            file_size_bytes=len(data),
        )
        with self._uow_factory() as uow:
            return uow.documents.add(record)

    def list_for(self, citizen_id: str) -> list[DocumentRecord]:
        """Return all documents for a citizen."""
        with self._uow_factory() as uow:
            return uow.documents.list_by_citizen(citizen_id)

    def save_analyzed(self, records: list[DocumentRecord]) -> None:
        """Persist analyzed/validated document records (insert or update)."""
        with self._uow_factory() as uow:
            for record in records:
                if uow.documents.get(record.id) is None:
                    uow.documents.add(record)
                else:
                    uow.documents.update(record)

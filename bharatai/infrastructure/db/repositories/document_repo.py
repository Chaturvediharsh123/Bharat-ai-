"""bharatai.infrastructure.db.repositories.document_repo — DocumentRecord persistence."""
from __future__ import annotations

import sqlite3
from typing import Any

from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType, DocumentValidationStatus
from bharatai.domain.value_objects import OcrResult
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteDocumentRepository(SqliteRepository[DocumentRecord]):
    """Stores uploaded document metadata, OCR output, and validation outcomes."""

    table = "documents"

    def _to_row(self, entity: DocumentRecord) -> dict[str, Any]:
        return {
            "id": entity.id,
            "citizen_id": entity.citizen_id,
            "doc_type": entity.doc_type.value,
            "file_path": entity.file_path,
            "file_name": entity.file_name,
            "mime_type": entity.mime_type,
            "file_size_bytes": entity.file_size_bytes,
            "checksum_sha256": entity.checksum_sha256,
            "ocr_result_json": m.model_to_json(entity.ocr_result),
            "extracted_name": entity.extracted_name,
            "extracted_dob": m.date_to_iso(entity.extracted_dob),
            "extracted_document_number": entity.extracted_document_number,
            "issue_date": m.date_to_iso(entity.issue_date),
            "expiry_date": m.date_to_iso(entity.expiry_date),
            "validation_status": entity.validation_status.value,
            "validation_errors_json": m.str_list_to_json(entity.validation_errors),
            "confidence_score": entity.confidence_score,
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            citizen_id=row["citizen_id"],
            doc_type=DocumentType(row["doc_type"]),
            file_path=row["file_path"],
            file_name=row["file_name"],
            mime_type=row["mime_type"],
            file_size_bytes=row["file_size_bytes"],
            checksum_sha256=row["checksum_sha256"],
            ocr_result=m.json_to_model(OcrResult, row["ocr_result_json"]),
            extracted_name=row["extracted_name"],
            extracted_dob=m.date_from_iso(row["extracted_dob"]),
            extracted_document_number=row["extracted_document_number"],
            issue_date=m.date_from_iso(row["issue_date"]),
            expiry_date=m.date_from_iso(row["expiry_date"]),
            validation_status=DocumentValidationStatus(row["validation_status"]),
            validation_errors=m.json_to_str_list(row["validation_errors_json"]),
            confidence_score=row["confidence_score"],
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_by_citizen(self, citizen_id: str) -> list[DocumentRecord]:
        """Return all documents for a citizen, newest first."""
        return self._query("citizen_id = ?", (citizen_id,), "created_at DESC")

    def find_by_checksum(self, checksum_sha256: str) -> DocumentRecord | None:
        """Return a previously-uploaded document with this content hash, if any."""
        return self._query_one("checksum_sha256 = ?", (checksum_sha256,), "created_at DESC")

"""Tests for the DocumentIntelligenceAgent (OCR pipeline behind ports)."""
from __future__ import annotations

from bharatai.agents.base import AgentContext
from bharatai.agents.document_intelligence_agent import DocumentInput, DocumentIntelligenceAgent
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType, DocumentValidationStatus
from bharatai.infrastructure.ocr.field_parsers import ExtractorRegistry, PanExtractor
from bharatai.infrastructure.ocr.service import DocumentIntelligenceService
from tests.fakes.fake_file_store import FakeFileStore
from tests.fakes.fake_ocr import FakeOcr

_CTX = AgentContext(trace_id="trace-1")


def _agent(
    ocr_text: str, files: dict[str, bytes] | None = None, default: bytes | None = b"img"
) -> DocumentIntelligenceAgent:
    analyzer = DocumentIntelligenceService(FakeOcr(ocr_text))
    return DocumentIntelligenceAgent(analyzer=analyzer, file_store=FakeFileStore(files, default))


def test_analyzes_validates_and_scores() -> None:
    agent = _agent("Income Tax Department\nName: Rahul Sharma\nPAN ABCDE1234F")
    record = DocumentRecord(citizen_id="c", doc_type=DocumentType.PAN, file_path="/tmp/pan.png")
    profile = CitizenProfile(full_name="Rahul Sharma")
    result = agent.run(
        DocumentInput(
            documents=[record], profile=profile, required_documents=[DocumentType.PAN]
        ),
        _CTX,
    )
    assert result.documents[0].validation_status is DocumentValidationStatus.VALID
    assert result.documents[0].extracted_document_number == "ABXXXXXF"
    assert result.validated_doc_types == [DocumentType.PAN]
    assert result.readiness_score == 100
    assert result.warnings == []


def test_skips_document_without_file_path() -> None:
    agent = _agent("anything")
    record = DocumentRecord(citizen_id="c", doc_type=DocumentType.PAN)
    result = agent.run(DocumentInput(documents=[record]), _CTX)
    assert any("no file path" in w for w in result.warnings)
    assert result.documents[0].validation_status is DocumentValidationStatus.PENDING


def test_warns_on_unreadable_file() -> None:
    agent = _agent("anything", files={}, default=None)
    record = DocumentRecord(citizen_id="c", doc_type=DocumentType.PAN, file_path="/missing.png")
    result = agent.run(DocumentInput(documents=[record]), _CTX)
    assert any("could not analyze" in w for w in result.warnings)
    assert result.documents[0].validation_status is DocumentValidationStatus.PENDING


def test_batch_continues_when_one_document_fails_analysis() -> None:
    # A PAN-only registry makes the Aadhaar document raise inside analyze_document.
    analyzer = DocumentIntelligenceService(
        FakeOcr("Name: Rahul Sharma\nPAN ABCDE1234F"), registry=ExtractorRegistry([PanExtractor()])
    )
    agent = DocumentIntelligenceAgent(analyzer=analyzer, file_store=FakeFileStore(default=b"img"))
    aadhaar = DocumentRecord(citizen_id="c", doc_type=DocumentType.AADHAAR, file_path="/a.png")
    pan = DocumentRecord(citizen_id="c", doc_type=DocumentType.PAN, file_path="/p.png")
    result = agent.run(DocumentInput(documents=[aadhaar, pan]), _CTX)
    assert len(result.documents) == 2  # the batch did not abort
    assert any("could not analyze" in w for w in result.warnings)
    assert DocumentType.PAN in result.validated_doc_types  # the PAN doc still processed

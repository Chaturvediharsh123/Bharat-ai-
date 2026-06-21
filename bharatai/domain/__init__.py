"""bharatai.domain — Layer 0: the locked, dependency-free domain contract.

This package is the single public import surface for every entity, value object,
and enum. Outer layers import from ``bharatai.domain`` and reuse field names
verbatim. The package depends on nothing but the standard library and pydantic.
"""
from __future__ import annotations

from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.base import DomainModel, Entity, ValueObject
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.eligibility import CriterionEvaluation, EligibilityResult
from bharatai.domain.enums import (
    ApplicationStatus,
    Category,
    ConfidenceTier,
    DocumentType,
    DocumentValidationStatus,
    EligibilityStatus,
    Gender,
    IndianState,
    MaritalStatus,
    ReminderChannel,
    ReminderStatus,
    ResidenceType,
)
from bharatai.domain.reminder import Reminder
from bharatai.domain.scheme import EligibilityCriteria, Scheme, SchemeBenefit
from bharatai.domain.value_objects import (
    Address,
    DateRange,
    Money,
    OcrField,
    OcrResult,
)

__all__ = [
    # base
    "DomainModel",
    "Entity",
    "ValueObject",
    # enums
    "ApplicationStatus",
    "Category",
    "ConfidenceTier",
    "DocumentType",
    "DocumentValidationStatus",
    "EligibilityStatus",
    "Gender",
    "IndianState",
    "MaritalStatus",
    "ReminderChannel",
    "ReminderStatus",
    "ResidenceType",
    # value objects
    "Address",
    "DateRange",
    "Money",
    "OcrField",
    "OcrResult",
    # entities
    "ApplicationHistoryEntry",
    "CitizenProfile",
    "CriterionEvaluation",
    "DocumentRecord",
    "EligibilityCriteria",
    "EligibilityResult",
    "Reminder",
    "Scheme",
    "SchemeBenefit",
]

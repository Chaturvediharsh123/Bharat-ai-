"""bharatai.domain.enums — India-specific enumerations.

All enums mix in ``str`` so their ``.value`` persists directly to SQLite TEXT
columns and serializes cleanly to JSON. Values are FINAL — they are the storage
and integration contract.
"""
from __future__ import annotations

from enum import Enum


class Gender(str, Enum):
    """Citizen gender (transgender recognized as a distinct legal category)."""

    MALE = "male"
    FEMALE = "female"
    TRANSGENDER = "transgender"
    OTHER = "other"


class MaritalStatus(str, Enum):
    """Marital status."""

    SINGLE = "single"
    MARRIED = "married"
    WIDOWED = "widowed"
    DIVORCED = "divorced"
    OTHER = "other"


class Category(str, Enum):
    """Social/caste category used for reservation-based eligibility."""

    GENERAL = "GEN"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"
    EWS = "EWS"


class ResidenceType(str, Enum):
    """Urban vs rural residence (drives some scheme targeting)."""

    URBAN = "urban"
    RURAL = "rural"


class IndianState(str, Enum):
    """All 28 states and 8 union territories, keyed by ISO-3166-2:IN short code."""

    # States
    ANDHRA_PRADESH = "AP"
    ARUNACHAL_PRADESH = "AR"
    ASSAM = "AS"
    BIHAR = "BR"
    CHHATTISGARH = "CG"
    GOA = "GA"
    GUJARAT = "GJ"
    HARYANA = "HR"
    HIMACHAL_PRADESH = "HP"
    JHARKHAND = "JH"
    KARNATAKA = "KA"
    KERALA = "KL"
    MADHYA_PRADESH = "MP"
    MAHARASHTRA = "MH"
    MANIPUR = "MN"
    MEGHALAYA = "ML"
    MIZORAM = "MZ"
    NAGALAND = "NL"
    ODISHA = "OD"
    PUNJAB = "PB"
    RAJASTHAN = "RJ"
    SIKKIM = "SK"
    TAMIL_NADU = "TN"
    TELANGANA = "TG"
    TRIPURA = "TR"
    UTTAR_PRADESH = "UP"
    UTTARAKHAND = "UK"
    WEST_BENGAL = "WB"
    # Union Territories
    ANDAMAN_NICOBAR = "AN"
    CHANDIGARH = "CH"
    DADRA_NAGAR_HAVELI_DAMAN_DIU = "DH"
    DELHI = "DL"
    JAMMU_KASHMIR = "JK"
    LADAKH = "LA"
    LAKSHADWEEP = "LD"
    PUDUCHERRY = "PY"


class DocumentType(str, Enum):
    """Supported citizen document types."""

    AADHAAR = "aadhaar"
    PAN = "pan"
    INCOME = "income"
    DOMICILE = "domicile"
    BONAFIDE = "bonafide"


class EligibilityStatus(str, Enum):
    """Outcome of an eligibility evaluation."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_MORE_INFO = "needs_more_info"
    PENDING = "pending"


class DocumentValidationStatus(str, Enum):
    """Outcome of validating an uploaded document."""

    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    MISMATCH = "mismatch"
    EXPIRED = "expired"
    UNREADABLE = "unreadable"


class ReminderStatus(str, Enum):
    """Lifecycle state of a reminder."""

    SCHEDULED = "scheduled"
    DUE = "due"
    SENT = "sent"
    SNOOZED = "snoozed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DONE = "done"


class ReminderChannel(str, Enum):
    """Delivery channel for a reminder."""

    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class ApplicationStatus(str, Enum):
    """Lifecycle state of a scheme application."""

    NOT_STARTED = "not_started"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class ConfidenceTier(str, Enum):
    """Coarse confidence band for OCR/extraction outputs."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

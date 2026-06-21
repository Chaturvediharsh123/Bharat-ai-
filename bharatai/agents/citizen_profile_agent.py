"""bharatai.agents.citizen_profile_agent — (1) build/normalize a CitizenProfile.

Takes messy raw input (UI form fields and OCR-extracted values), coerces it into domain
types, merges it onto any existing profile, and returns a validated CitizenProfile plus
warnings for anything it could not parse. Full Aadhaar/PAN are never stored — only masked.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.agents.profile_normalizer import ProfileNormalizer
from bharatai.common.ids import now_utc
from bharatai.common.logging import get_logger
from bharatai.common.redaction import aadhaar_last4, mask_pan, redact_pii
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.value_objects import Address

_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_FOUR_DIGITS = re.compile(r"\d{4}")
_SIX_DIGITS = re.compile(r"\d{6}")


class RawProfileInput(BaseModel):
    """Raw input for building a profile: free-form fields plus an optional base profile."""

    model_config = ConfigDict(extra="forbid")

    existing: CitizenProfile | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    source: Literal["user", "agent", "import"] = "user"


class ProfileBuildResult(BaseModel):
    """The built profile, plus which fields were applied and any parse warnings."""

    model_config = ConfigDict(extra="forbid")

    profile: CitizenProfile
    applied_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CitizenProfileAgent(BaseAgent[RawProfileInput, ProfileBuildResult]):
    """Normalizes and validates raw input into a CitizenProfile (PII minimized)."""

    name = "citizen_profile"

    def __init__(
        self,
        normalizer: ProfileNormalizer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Inject the field normalizer and a logger (sensible defaults provided)."""
        self._normalizer = normalizer or ProfileNormalizer()
        self._logger = logger or get_logger(__name__)

    def run(self, data: RawProfileInput, ctx: AgentContext) -> ProfileBuildResult:
        """Build a validated CitizenProfile from raw fields, merged onto any existing one."""
        base = data.existing or CitizenProfile()
        raw = data.raw_fields
        updates: dict[str, Any] = {}
        applied: list[str] = []
        warnings: list[str] = []
        norm = self._normalizer

        def take(field: str, keys: list[str], coerce: Callable[[Any], Any]) -> None:
            for key in keys:
                if key in raw and raw[key] not in (None, ""):
                    value = coerce(raw[key])
                    if value is not None:
                        updates[field] = value
                        applied.append(field)
                    else:
                        warnings.append(f"could not parse '{field}' from {key!r}")
                    return

        # Free-text fields are redacted so an embedded full Aadhaar/PAN is never stored.
        take("full_name", ["full_name", "name"], lambda v: redact_pii(str(v).strip()) or None)
        take("gender", ["gender"], norm.coerce_gender)
        take("category", ["category"], norm.coerce_category)
        take("marital_status", ["marital_status"], norm.coerce_marital_status)
        take("date_of_birth", ["date_of_birth", "dob"], norm.coerce_date)
        take("annual_income", ["annual_income", "income"], norm.coerce_money)
        take("occupation", ["occupation"], lambda v: redact_pii(str(v).strip()) or None)
        take("is_bpl", ["is_bpl"], norm.coerce_bool)
        take("disability_status", ["disability_status"], norm.coerce_bool)

        def percent(value: Any) -> int | None:
            return norm.coerce_int_in_range(value, 0, 100)

        def family(value: Any) -> int | None:
            return norm.coerce_int_in_range(value, 1, 50)

        take("disability_percentage", ["disability_percentage"], percent)
        take("family_size", ["family_size"], family)
        take("mobile", ["mobile"], norm.coerce_mobile)

        if raw.get("languages"):
            languages = norm.coerce_languages(raw["languages"])
            if languages:
                updates["languages"] = languages
                applied.append("languages")

        self._apply_aadhaar(raw, updates, warnings, applied)
        self._apply_pan(raw, updates, warnings, applied)
        address = self._build_address(base.address, raw, warnings, applied)
        if address is not None:
            updates["address"] = address

        merged = base.model_dump()
        merged.update(updates)
        merged["updated_at"] = now_utc()
        profile = CitizenProfile.model_validate(merged)

        self._logger.info(
            "built citizen profile",
            extra={"trace_id": ctx.trace_id, "applied": applied, "warnings": len(warnings)},
        )
        return ProfileBuildResult(profile=profile, applied_fields=applied, warnings=warnings)

    @staticmethod
    def _apply_aadhaar(
        raw: dict[str, Any], updates: dict[str, Any], warnings: list[str], applied: list[str]
    ) -> None:
        if raw.get("aadhaar"):
            last4 = aadhaar_last4(str(raw["aadhaar"]))
            if last4:
                updates["aadhaar_last4"] = last4
                applied.append("aadhaar_last4")
            else:
                warnings.append("aadhaar number is not 12 digits; ignored")
        elif raw.get("aadhaar_last4"):
            value = str(raw["aadhaar_last4"]).strip()
            if _FOUR_DIGITS.fullmatch(value):
                updates["aadhaar_last4"] = value
                applied.append("aadhaar_last4")
            else:
                warnings.append("aadhaar_last4 must be 4 digits; ignored")

    @staticmethod
    def _apply_pan(
        raw: dict[str, Any], updates: dict[str, Any], warnings: list[str], applied: list[str]
    ) -> None:
        if raw.get("pan"):
            pan = str(raw["pan"]).strip().upper()
            if _PAN_RE.fullmatch(pan):
                updates["pan_masked"] = mask_pan(pan)
                applied.append("pan_masked")
            else:
                warnings.append("invalid PAN format; ignored")

    def _build_address(
        self,
        existing: Address | None,
        raw: dict[str, Any],
        warnings: list[str],
        applied: list[str],
    ) -> Address | None:
        fields: dict[str, Any] = {}
        if raw.get("line"):
            fields["line"] = redact_pii(str(raw["line"]).strip())
        city = raw.get("village_or_city") or raw.get("city")
        if city:
            fields["village_or_city"] = redact_pii(str(city).strip())
        if raw.get("district"):
            fields["district"] = redact_pii(str(raw["district"]).strip())
        if raw.get("state"):
            state = self._normalizer.coerce_state(raw["state"])
            if state is not None:
                fields["state"] = state
            else:
                warnings.append("could not parse 'state'")
        if raw.get("pincode"):
            pincode = str(raw["pincode"]).strip()
            if _SIX_DIGITS.fullmatch(pincode):
                fields["pincode"] = pincode
            else:
                warnings.append("pincode must be 6 digits; ignored")
        if raw.get("residence_type"):
            residence = self._normalizer.coerce_residence(raw["residence_type"])
            if residence is not None:
                fields["residence_type"] = residence

        if not fields and existing is None:
            return None
        merged = existing.model_dump() if existing else {}
        merged.update(fields)
        if not any(value is not None for value in merged.values()):
            return None
        if not fields:
            return existing  # existing address unchanged — do not report it as applied
        applied.append("address")
        return Address.model_validate(merged)

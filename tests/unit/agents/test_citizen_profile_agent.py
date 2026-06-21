"""Tests for the CitizenProfileAgent."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.agents.base import AgentContext
from bharatai.agents.citizen_profile_agent import CitizenProfileAgent, RawProfileInput
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.enums import Category, Gender, IndianState, ResidenceType
from bharatai.domain.value_objects import Address, Money

_CTX = AgentContext(trace_id="trace-1")
_AGENT = CitizenProfileAgent()


def test_builds_profile_from_raw_fields() -> None:
    raw = {
        "name": "Asha Devi",
        "gender": "Female",
        "category": "OBC",
        "dob": "01/06/1990",
        "income": "2,50,000",
        "occupation": "weaver",
        "family_size": "4",
        "state": "Rajasthan",
        "district": "Jaipur",
        "pincode": "302001",
        "residence_type": "urban",
    }
    result = _AGENT.run(RawProfileInput(raw_fields=raw), _CTX)
    profile = result.profile
    assert profile.full_name == "Asha Devi"
    assert profile.gender is Gender.FEMALE
    assert profile.category is Category.OBC
    assert profile.date_of_birth == date(1990, 6, 1)
    assert profile.annual_income == Money(amount=Decimal("250000"))
    assert profile.family_size == 4
    assert profile.address is not None
    assert profile.address.state is IndianState.RAJASTHAN
    assert profile.address.pincode == "302001"
    assert profile.address.residence_type is ResidenceType.URBAN
    assert profile.age is not None
    assert result.warnings == []


def test_aadhaar_and_pan_are_masked_never_full() -> None:
    raw = {"aadhaar": "2345 6789 0123", "pan": "ABCDE1234F"}
    result = _AGENT.run(RawProfileInput(raw_fields=raw), _CTX)
    profile = result.profile
    assert profile.aadhaar_last4 == "0123"
    assert profile.pan_masked == "ABXXXXXF"
    dump = profile.model_dump_json()
    assert "234567890123" not in dump  # full Aadhaar must never be stored
    assert "ABCDE1234F" not in dump  # full PAN must never be stored


def test_merges_with_existing_profile() -> None:
    existing = CitizenProfile(full_name="Ravi Kumar", gender=Gender.MALE)
    result = _AGENT.run(
        RawProfileInput(existing=existing, raw_fields={"income": "100000"}), _CTX
    )
    profile = result.profile
    assert profile.full_name == "Ravi Kumar"
    assert profile.gender is Gender.MALE
    assert profile.annual_income == Money(amount=Decimal("100000"))
    assert profile.id == existing.id


def test_warns_on_unparseable_fields() -> None:
    raw = {"gender": "alien", "pincode": "12", "aadhaar": "123"}
    result = _AGENT.run(RawProfileInput(raw_fields=raw), _CTX)
    assert result.profile.gender is None
    assert result.profile.address is None
    assert any("gender" in w for w in result.warnings)
    assert any("pincode" in w for w in result.warnings)
    assert any("aadhaar" in w for w in result.warnings)


def test_state_coercion_by_iso_code() -> None:
    result = _AGENT.run(RawProfileInput(raw_fields={"state": "MH"}), _CTX)
    assert result.profile.address is not None
    assert result.profile.address.state is IndianState.MAHARASHTRA


def test_does_not_crash_on_non_finite_income() -> None:
    result = _AGENT.run(RawProfileInput(raw_fields={"income": "nan"}), _CTX)
    assert result.profile.annual_income is None
    assert any("annual_income" in w for w in result.warnings)


def test_pii_in_free_text_fields_is_redacted() -> None:
    raw = {"name": "Asha 2345 6789 0123", "occupation": "ABCDE1234F"}
    result = _AGENT.run(RawProfileInput(raw_fields=raw), _CTX)
    dump = result.profile.model_dump_json()
    assert "234567890123" not in dump
    assert "2345 6789 0123" not in dump
    assert "ABCDE1234F" not in dump


def test_applied_fields_excludes_unchanged_address() -> None:
    existing = CitizenProfile(
        address=Address(
            village_or_city="Pune", state=IndianState.MAHARASHTRA, pincode="411001"
        )
    )
    result = _AGENT.run(
        RawProfileInput(existing=existing, raw_fields={"income": "5000"}), _CTX
    )
    assert "annual_income" in result.applied_fields
    assert "address" not in result.applied_fields
    assert result.profile.address == existing.address

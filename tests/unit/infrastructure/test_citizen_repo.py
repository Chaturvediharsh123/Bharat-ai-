"""Round-trip tests for the SQLite citizen profile repository."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.enums import Category, Gender, IndianState, ResidenceType
from bharatai.domain.value_objects import Address, Money
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork


def _sample() -> CitizenProfile:
    return CitizenProfile(
        full_name="Asha Devi",
        date_of_birth=date(1990, 6, 1),
        gender=Gender.FEMALE,
        category=Category.OBC,
        annual_income=Money(amount=Decimal("180000.00")),
        occupation="weaver",
        is_bpl=True,
        family_size=4,
        address=Address(
            village_or_city="Jaipur",
            district="Jaipur",
            state=IndianState.RAJASTHAN,
            pincode="302001",
            residence_type=ResidenceType.URBAN,
        ),
        aadhaar_last4="1234",
        languages=["hi", "en"],
    )


def test_citizen_full_roundtrip(uow: SqliteUnitOfWork) -> None:
    citizen = _sample()
    with uow:
        uow.citizens.add(citizen)
    with uow as u:
        loaded = u.citizens.get(citizen.id)
    assert loaded == citizen


def test_find_by_denormalized_state(uow: SqliteUnitOfWork) -> None:
    citizen = _sample()
    with uow:
        uow.citizens.add(citizen)
    with uow as u:
        found = u.citizens.find_by_state(IndianState.RAJASTHAN)
    assert [c.id for c in found] == [citizen.id]


def test_update_persists(uow: SqliteUnitOfWork) -> None:
    citizen = _sample()
    with uow:
        uow.citizens.add(citizen)
    with uow as u:
        fetched = u.citizens.get(citizen.id)
        assert fetched is not None
        fetched.occupation = "potter"
        u.citizens.update(fetched)
    with uow as u:
        again = u.citizens.get(citizen.id)
    assert again is not None
    assert again.occupation == "potter"
    assert again.updated_at >= citizen.updated_at

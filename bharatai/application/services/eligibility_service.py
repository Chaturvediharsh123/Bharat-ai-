"""bharatai.application.services.eligibility_service — eligibility persistence use cases."""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.eligibility import EligibilityResult

UowFactory = Callable[[], UnitOfWork]


class EligibilityService:
    """Appends eligibility results and returns the latest result per scheme."""

    def __init__(self, uow_factory: UowFactory) -> None:
        """Inject the UnitOfWork factory."""
        self._uow_factory = uow_factory

    def save_results(self, results: list[EligibilityResult]) -> None:
        """Append eligibility results (history is append-only)."""
        with self._uow_factory() as uow:
            for result in results:
                uow.eligibility_results.add(result)

    def latest_for(self, citizen_id: str) -> list[EligibilityResult]:
        """Return the most recent eligibility result per scheme for a citizen."""
        with self._uow_factory() as uow:
            rows = uow.eligibility_results.list_by_citizen(citizen_id)
        latest: dict[str, EligibilityResult] = {}
        for row in sorted(rows, key=lambda r: (r.evaluated_at, r.id)):
            latest[row.scheme_id] = row
        return list(latest.values())

"""Application service for manual referral rate conditions."""

from __future__ import annotations

from dataclasses import replace

from app.domain.rate_models import RateCondition
from app.repositories.rate_conditions_repository import RateConditionsRepository
from app.services.rate_conditions_validation_service import RateConditionsValidationService


class RateConditionsService:
    """Create, update, and query rate conditions with validation."""

    def __init__(
        self,
        repository: RateConditionsRepository,
        validation_service: RateConditionsValidationService,
    ) -> None:
        self._repository = repository
        self._validation_service = validation_service

    def list(
        self,
        referral_id: int,
        currency: str | None = None,
        region: str | None = None,
        active: bool | None = None,
    ) -> list[RateCondition]:
        """Return conditions for UI."""
        return self._repository.list(
            referral_id=referral_id,
            currency=currency,
            region=None,
            active=active,
        )

    def save(self, condition: RateCondition) -> int:
        """Validate and persist a condition."""
        normalized = _normalize(condition)
        self._validation_service.validate_no_overlap(normalized)
        if normalized.id is None:
            return self._repository.add(normalized)
        self._repository.update(normalized)
        return int(normalized.id)

    def delete(self, condition_id: int) -> None:
        """Delete a condition."""
        self._repository.delete(condition_id)


def _normalize(condition: RateCondition) -> RateCondition:
    return replace(
        condition,
        operation_type=_blank_to_none(condition.operation_type),
        currency=_blank_to_none(condition.currency.upper() if condition.currency else None),
        region=None,
        date_from=_blank_to_none(condition.date_from),
        date_to=_blank_to_none(condition.date_to),
        comment=_blank_to_none(condition.comment),
        amount_from=condition.amount_from if condition.amount_from is not None else None,
        amount_to=condition.amount_to if condition.amount_to is not None else None,
        amount_basis=_normalize_amount_basis(condition.amount_basis),
        percent_commission_currency=_blank_to_none(
            condition.percent_commission_currency.upper() if condition.percent_commission_currency else None
        ),
        fixed_commission_amount=condition.fixed_commission_amount,
        fixed_commission_currency=_blank_to_none(
            condition.fixed_commission_currency.upper() if condition.fixed_commission_currency else None
        ),
        commission_type=_commission_type(condition),
    )


def _blank_to_none(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_amount_basis(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text in {"deal_currency", "usd_equivalent"} else "deal_currency"


def _commission_type(condition: RateCondition) -> str:
    has_percent = float(condition.rate_value or 0) != 0
    has_fixed = condition.fixed_commission_amount is not None and float(condition.fixed_commission_amount) != 0
    if has_percent and has_fixed:
        return "mixed"
    if has_fixed:
        return "fixed"
    return "percent"

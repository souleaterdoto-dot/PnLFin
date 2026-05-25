"""Rules engine for referral-based rate conditions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.models import RateRuleMatch
from app.domain.rate_models import RateCondition
from app.repositories.rate_conditions_repository import RateConditionsRepository
from app.repositories.referrals_repository import ReferralsRepository


AMOUNT_BASIS_DEAL_CURRENCY = "deal_currency"
AMOUNT_BASIS_USD_EQUIVALENT = "usd_equivalent"


class RateRuleNotFoundError(LookupError):
    """Raised when no active rate condition matches a deal."""


class RateRuleConfigurationError(ValueError):
    """Raised when several active conditions match one deal."""


@dataclass(frozen=True, slots=True)
class RateRuleCheck:
    """Input for checking a referral rate against a hypothetical deal."""

    bank_name: str
    currency: str
    amount: float
    region: str | None
    deal_date: str
    amount_usd: float | None = None
    operation_type: str | None = None
    rule_set_name: str | None = None


class RateRulesEngine:
    """Evaluate referral rate conditions for a deal."""

    def __init__(
        self,
        referrals_repository: ReferralsRepository | None = None,
        conditions_repository: RateConditionsRepository | None = None,
    ) -> None:
        self._referrals_repository = referrals_repository or ReferralsRepository()
        self._conditions_repository = conditions_repository or RateConditionsRepository()

    def find_rate(
        self,
        bank_name: str,
        currency: str,
        amount: float,
        region: str | None,
        deal_date: str,
        rule_set_name: str | None = None,
        amount_usd: float | None = None,
        operation_type: str | None = None,
    ) -> RateRuleMatch:
        """
        Return a matching referral rate.

        ``amount`` is the deal amount in deal currency. ``amount_usd`` is used
        only by conditions marked as ``от eq. USD``.
        """
        referral = self._referrals_repository.find_by_name_or_code(bank_name)
        if referral is None or referral.id is None or not referral.is_active:
            raise RateRuleNotFoundError("Ставка не найдена")
        conditions = self._conditions_repository.list_active(referral.id)
        return self.find_rate_from_rules(
            rules=conditions,
            bank_name=bank_name,
            currency=currency,
            amount=amount,
            region=region,
            deal_date=deal_date,
            amount_usd=amount_usd,
            operation_type=operation_type,
        )

    def find_rate_from_rules(
        self,
        rules: Iterable[RateCondition],
        bank_name: str,
        currency: str,
        amount: float,
        region: str | None,
        deal_date: str,
        amount_usd: float | None = None,
        operation_type: str | None = None,
    ) -> RateRuleMatch:
        """Return one matching condition from a preloaded collection."""
        deal_date_iso = _to_iso_date(deal_date)
        normalized_amount_usd = _normalize_amount_usd(currency, amount, amount_usd)
        matches = [
            condition
            for condition in rules
            if condition.is_active
            and _matches_condition(
                condition=condition,
                currency=currency,
                amount=amount,
                amount_usd=normalized_amount_usd,
                region=region,
                deal_date=deal_date_iso,
                operation_type=operation_type,
            )
        ]
        if not matches:
            raise RateRuleNotFoundError("Ставка не найдена")
        if len(matches) > 1:
            ids = ", ".join(f"#{item.id}" for item in matches)
            raise RateRuleConfigurationError(
                f"Найдено несколько ставок для одной сделки: {ids}"
            )
        condition = matches[0]
        return RateRuleMatch(
            rate=condition.rate_value,
            matched_rule_id=condition.id or 0,
            matched_order_index=condition.priority,
            explanation=_explanation(bank_name, condition),
        )


def _matches_condition(
    condition: RateCondition,
    currency: str,
    amount: float,
    amount_usd: float | None,
    region: str | None,
    deal_date: str,
    operation_type: str | None = None,
) -> bool:
    if condition.operation_type and _norm(condition.operation_type) != _norm(operation_type):
        return False
    if condition.currency and condition.currency.upper() != str(currency or "").strip().upper():
        return False
    check_amount = _amount_for_condition(condition, amount, amount_usd)
    if check_amount is None:
        return False
    if condition.amount_from is not None and check_amount < condition.amount_from:
        return False
    if condition.amount_to is not None and check_amount >= condition.amount_to:
        return False
    if condition.date_from and deal_date < condition.date_from:
        return False
    if condition.date_to and deal_date > condition.date_to:
        return False
    return True


def _amount_for_condition(
    condition: RateCondition,
    amount: float,
    amount_usd: float | None,
) -> float | None:
    if _amount_basis(condition) == AMOUNT_BASIS_USD_EQUIVALENT:
        return amount_usd
    return abs(float(amount or 0.0))


def _normalize_amount_usd(currency: str, amount: float, amount_usd: float | None) -> float | None:
    if amount_usd is not None:
        return abs(float(amount_usd))
    if str(currency or "").strip().upper() == "USD":
        return abs(float(amount or 0.0))
    return None


def _explanation(referral_name: str, condition: RateCondition) -> str:
    amount_range = f"{_fmt(condition.amount_from or 0)}-{_fmt(condition.amount_to)}"
    amount_basis = "eq. USD" if _amount_basis(condition) == AMOUNT_BASIS_USD_EQUIVALENT else "в валюте сделки"
    period = f"{condition.date_from or 'с начала'}-{condition.date_to or 'бессрочно'}"
    currency = condition.currency or "любая валюта"
    return (
        f"Сработало условие #{condition.id or condition.priority}: {referral_name}, "
        f"{currency}, сумма {amount_range} ({amount_basis}), период {period}, "
        f"ставка {_fmt(condition.rate_value)}%"
    )


def _amount_basis(condition: RateCondition) -> str:
    return (
        condition.amount_basis
        if condition.amount_basis in {AMOUNT_BASIS_DEAL_CURRENCY, AMOUNT_BASIS_USD_EQUIVALENT}
        else AMOUNT_BASIS_DEAL_CURRENCY
    )


def _norm(value: str | None) -> str:
    return str(value or "").strip().casefold()


def _to_iso_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return date.today().isoformat()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return date.fromisoformat(text).isoformat()


def _fmt(value: float | None) -> str:
    if value is None:
        return "без лимита"
    text = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return text.rstrip("0").rstrip(",")

"""Validation service for referral rate condition overlaps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.rate_models import RateCondition, RateConditionConflict
from app.repositories.rate_conditions_repository import RateConditionsRepository


class RateConditionOverlapError(ValueError):
    """Raised when an active condition overlaps another active condition."""

    def __init__(self, conflict: RateConditionConflict) -> None:
        super().__init__(conflict.message)
        self.conflict = conflict


@dataclass(slots=True)
class RateConditionsValidationService:
    """Validate condition ranges inside one referral."""

    repository: RateConditionsRepository

    def validate_no_overlap(self, condition: RateCondition) -> None:
        """Raise a user-facing error if the condition conflicts with another one."""
        if not condition.is_active:
            return
        existing = self.repository.list(referral_id=condition.referral_id, active=True)
        for other in existing:
            if condition.id is not None and other.id == condition.id:
                continue
            if _conditions_overlap(condition, other):
                raise RateConditionOverlapError(
                    RateConditionConflict(
                        condition=other,
                        message=_overlap_message(condition, other),
                    )
                )


def _conditions_overlap(left: RateCondition, right: RateCondition) -> bool:
    return (
        _amount_basis(left) == _amount_basis(right)
        and _wildcard_text_overlap(left.operation_type, right.operation_type)
        and _wildcard_text_overlap(left.currency, right.currency)
        and _range_overlap(left.amount_from, left.amount_to, right.amount_from, right.amount_to)
        and _date_range_overlap(left.date_from, left.date_to, right.date_from, right.date_to)
    )


def _wildcard_text_overlap(left: str | None, right: str | None) -> bool:
    if _is_blank(left) or _is_blank(right):
        return True
    return str(left).strip().casefold() == str(right).strip().casefold()


def _range_overlap(
    left_from: float | None,
    left_to: float | None,
    right_from: float | None,
    right_to: float | None,
) -> bool:
    start_left = float(left_from or 0)
    end_left = float("inf") if left_to is None else float(left_to)
    start_right = float(right_from or 0)
    end_right = float("inf") if right_to is None else float(right_to)
    return start_left < end_right and start_right < end_left


def _date_range_overlap(
    left_from: str | None,
    left_to: str | None,
    right_from: str | None,
    right_to: str | None,
) -> bool:
    start_left = _to_date(left_from, date.min)
    end_left = _to_date(left_to, date.max)
    start_right = _to_date(right_from, date.min)
    end_right = _to_date(right_to, date.max)
    return start_left <= end_right and start_right <= end_left


def _to_date(value: str | None, default: date) -> date:
    text = str(value or "").strip()
    if not text:
        return default
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.fromisoformat(text)


def _condition_summary(condition: RateCondition) -> str:
    currency = condition.currency or "любая валюта"
    amount_from = _fmt_amount(condition.amount_from or 0)
    amount_to = _fmt_amount(condition.amount_to) if condition.amount_to is not None else "без лимита"
    amount_basis = _amount_basis_label(condition)
    date_from = _fmt_date(condition.date_from) if condition.date_from else "с начала"
    date_to = _fmt_date(condition.date_to) if condition.date_to else "бессрочно"
    return (
        f"{currency}, сумма {amount_from}-{amount_to} ({amount_basis}), "
        f"период {date_from}-{date_to}"
    )


def _overlap_message(new_condition: RateCondition, existing: RateCondition) -> str:
    matched = _matched_parts(new_condition, existing)
    return "\n".join(
        [
            "Конфликт условий ставок",
            "Новое условие может подойти под ту же сделку, что и уже существующее условие.",
            f"Существующее условие #{existing.id}: {_condition_summary(existing)}",
            f"Совпадающие признаки: {', '.join(matched)}.",
            "Что сделать: сузьте диапазон суммы, период дат, валюту или тип сделки. Либо отредактируйте/архивируйте существующее условие.",
        ]
    )


def _matched_parts(left: RateCondition, right: RateCondition) -> list[str]:
    parts = ["режим суммы"]
    if _wildcard_text_overlap(left.operation_type, right.operation_type):
        parts.append("тип сделки")
    if _wildcard_text_overlap(left.currency, right.currency):
        parts.append("валюта")
    if _range_overlap(left.amount_from, left.amount_to, right.amount_from, right.amount_to):
        parts.append("диапазон суммы")
    if _date_range_overlap(left.date_from, left.date_to, right.date_from, right.date_to):
        parts.append("период дат")
    return parts


def _fmt_amount(value: float | None) -> str:
    if value is None:
        return "без лимита"
    return f"{float(value):,.0f}".replace(",", " ")


def _fmt_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def _is_blank(value: str | None) -> bool:
    return str(value or "").strip() in {"", "0"}


def _amount_basis(condition: RateCondition) -> str:
    return condition.amount_basis if condition.amount_basis in {"deal_currency", "usd_equivalent"} else "deal_currency"


def _amount_basis_label(condition: RateCondition) -> str:
    return "eq. USD" if _amount_basis(condition) == "usd_equivalent" else "в валюте сделки"

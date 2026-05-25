"""Domain models for referral-based rate conditions."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import utc_now_iso


@dataclass(slots=True)
class Referral:
    """Referral, bank, or partner that owns a set of rate conditions."""

    name: str
    code: str
    description: str | None = None
    logo_path: str | None = None
    is_active: bool = True
    id: int | None = None
    active_conditions_count: int = 0
    updated_at: str = field(default_factory=utc_now_iso)
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class RateCondition:
    """Manual condition used to match a deal to a referral commission rate."""

    referral_id: int
    is_active: bool = True
    priority: int = 100
    operation_type: str | None = None
    currency: str | None = None
    amount_from: float | None = None
    amount_to: float | None = None
    amount_basis: str = "deal_currency"
    region: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    rate_value: float = 0.0
    percent_commission_currency: str | None = None
    fixed_commission_amount: float | None = None
    fixed_commission_currency: str | None = None
    commission_type: str = "percent"
    comment: str | None = None
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class RateConditionConflict:
    """Overlap validation result for one conflicting condition."""

    condition: RateCondition
    message: str


@dataclass(slots=True)
class ClientRateException:
    """Client-specific exception requiring manual referral commission review."""

    client_name: str
    note: str
    date_from: str
    date_to: str | None = None
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

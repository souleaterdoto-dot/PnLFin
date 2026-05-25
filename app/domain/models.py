"""Domain entities represented as dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.enums import DealReviewStatus, RateSource


def utc_now_iso() -> str:
    """Return an ISO timestamp suitable for SQLite text storage."""
    return datetime.utcnow().replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Deal:
    """Foreign exchange deal imported from Excel or entered manually."""

    trade_date: str
    value_date: str
    operation_type: str
    counterparty: str
    currency_buy: str
    amount_buy: float
    currency_sell: str
    amount_sell: float
    rate_fact: float
    commission: float = 0.0
    portfolio: str = "Default"
    comment: str | None = None
    external_deal_id: str | None = None
    manager: str | None = None
    is_repeat_payment: bool | None = None
    repeat_payment_commission_percent: float | None = None
    repeat_payment_penalty_usd: float | None = None
    request_date: str | None = None
    client_fix_date: str | None = None
    agent_writeoff_date: str | None = None
    client_receive_date: str | None = None
    is_refund: bool | None = None
    agent_refund_date: str | None = None
    client_refund_date: str | None = None
    payment_status: str | None = None
    client_name: str | None = None
    review_status: DealReviewStatus | str | None = None
    receiver_company: str | None = None
    receiver_bank_country: str | None = None
    deal_amount: float | None = None
    deal_currency: str | None = None
    client_rate_percent: float | None = None
    fixed_commission_amount: float | None = None
    fixed_commission_currency: str | None = None
    swift_amount: float | None = None
    swift_currency: str | None = None
    client_fix_rate: float | None = None
    usd_rate: float | None = None
    client_cross_rate: float | None = None
    payment_agent: str | None = None
    agent_commission_amount: float | None = None
    agent_commission_currency: str | None = None
    swift_commission_amount: float | None = None
    swift_commission_currency: str | None = None
    customer_article_name: str | None = None
    pnl_client_percent_fee_usd: float | None = None
    pnl_fixed_commission_usd: float | None = None
    pnl_swift_usd: float | None = None
    pnl_agent_commission_usd: float | None = None
    pnl_swift_commission_usd: float | None = None
    pnl_referral_commission_usd: float | None = None
    source_file: str | None = None
    source_sheet: str | None = None
    source_row_number: int | None = None
    import_batch_id: int | None = None
    raw_payload_json: str | None = None
    included_in_calc: bool = True
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Rate:
    """Currency rate to RUB for a specific date."""

    rate_date: str
    currency: str
    rate_to_rub: float
    source: str = RateSource.MANUAL.value
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class RateRule:
    """Rule for matching a deal to a client rate."""

    rule_set_name: str
    order_index: int
    bank_name: str
    currency: str
    min_amount: float
    max_amount: float | None
    rate: float
    region: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_active: bool = True
    source_file: str | None = None
    source_sheet: str | None = None
    source_row_number: int | None = None
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class RateRuleMatch:
    """Result of running the rate rules engine."""

    rate: float
    matched_rule_id: int
    matched_order_index: int
    explanation: str


@dataclass(frozen=True, slots=True)
class ValidationError:
    """Structured validation error for imports and manual entry."""

    row_number: int
    field_name: str
    message: str
    raw_value: object | None = None


@dataclass(slots=True)
class CurrencyPosition:
    """Aggregated currency balance and average RUB rate."""

    currency: str
    quantity: float
    average_rate: float
    market_rate: float
    mtm_value_rub: float
    unrealized_pnl_rub: float


@dataclass(slots=True)
class PnlAnalytics:
    """Computed PnL analytics grouped by key business dimensions."""

    realized_pnl_rub: float
    unrealized_pnl_rub: float
    total_pnl_rub: float
    pnl_by_currency: dict[str, float]
    pnl_by_date: dict[str, float]
    pnl_by_portfolio: dict[str, float]
    positions: list[CurrencyPosition]
    deal_count: int
    as_of_date: str = field(default_factory=lambda: date.today().isoformat())

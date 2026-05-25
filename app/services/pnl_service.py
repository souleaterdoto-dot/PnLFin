"""PnL calculation service based on the imported deals registry."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.domain.models import CurrencyPosition, Deal, PnlAnalytics
from app.repositories.deals_repository import DealsRepository
from app.services.rates_service import RatesService


@dataclass(slots=True)
class _PositionState:
    """Signed currency balance and weighted average client fixing rate."""

    quantity: float = 0.0
    weighted_rate_amount: float = 0.0
    weighted_amount: float = 0.0

    @property
    def average_rate(self) -> float:
        return self.weighted_rate_amount / self.weighted_amount if self.weighted_amount else 0.0


@dataclass(frozen=True, slots=True)
class _DealPnl:
    """Normalized per-deal PnL components in reporting currency."""

    gross_fee_rub: float
    referral_commission_rub: float
    subagent_commission_rub: float

    @property
    def net_pnl_rub(self) -> float:
        return self.gross_fee_rub - self.referral_commission_rub - self.subagent_commission_rub


class PnlService:
    """Calculate operational PnL from Excel deal rows.

    Current business formula:
    net PnL = abs(deal amount) * client/general rate - referral commission - subagent commission.

    Referral commission is intentionally a placeholder until referral-rate rules are added.
    Import/export direction is determined by the sign of ``deal_amount`` and is used for balances;
    the fee base uses the absolute deal amount.
    """

    def __init__(
        self,
        deals_repository: DealsRepository | None = None,
        rates_service: RatesService | None = None,
    ) -> None:
        self._deals_repository = deals_repository or DealsRepository()
        self._rates_service = rates_service or RatesService()

    def calculate(self, as_of_date: str | None = None) -> PnlAnalytics:
        """Calculate PnL analytics from included registry deals."""
        as_of = as_of_date or date.today().isoformat()
        deals = self._deals_repository.list(included_only=True, sort_by="trade_date", sort_desc=False, limit=100000)
        positions: dict[str, _PositionState] = defaultdict(_PositionState)
        pnl_by_currency: dict[str, float] = defaultdict(float)
        pnl_by_date: dict[str, float] = defaultdict(float)
        pnl_by_portfolio: dict[str, float] = defaultdict(float)
        realized_pnl = 0.0

        for deal in deals:
            if not self._has_registry_amount(deal):
                continue

            currency = self._deal_currency(deal)
            deal_date = self._deal_date(deal)
            portfolio = deal.portfolio or "Default"
            signed_amount = float(deal.deal_amount or 0.0)

            self._apply_position(positions[currency], deal, signed_amount)
            deal_pnl = self._calculate_deal_pnl(deal, currency, deal_date)
            realized_pnl += deal_pnl.net_pnl_rub
            pnl_by_currency[currency] += deal_pnl.net_pnl_rub
            pnl_by_date[deal_date] += deal_pnl.net_pnl_rub
            pnl_by_portfolio[portfolio] += deal_pnl.net_pnl_rub

        currency_positions = self._build_positions(positions, as_of)

        return PnlAnalytics(
            realized_pnl_rub=realized_pnl,
            unrealized_pnl_rub=0.0,
            total_pnl_rub=realized_pnl,
            pnl_by_currency=dict(sorted(pnl_by_currency.items())),
            pnl_by_date=dict(sorted(pnl_by_date.items())),
            pnl_by_portfolio=dict(sorted(pnl_by_portfolio.items())),
            positions=currency_positions,
            deal_count=len(deals),
            as_of_date=as_of,
        )

    def _calculate_deal_pnl(self, deal: Deal, currency: str, deal_date: str) -> _DealPnl:
        amount_base = abs(float(deal.deal_amount or 0.0))
        gross_fee = amount_base * self._percent(deal.client_rate_percent)
        gross_fee_rub = self._amount_to_rub(gross_fee, currency, deal_date)

        referral_commission = self._referral_commission_amount(deal)
        referral_commission_rub = self._amount_to_rub(referral_commission, currency, deal_date)

        subagent_currency = (deal.agent_commission_currency or currency).upper()
        subagent_commission = float(deal.agent_commission_amount or 0.0)
        subagent_commission_rub = self._amount_to_rub(subagent_commission, subagent_currency, deal_date)

        return _DealPnl(
            gross_fee_rub=gross_fee_rub,
            referral_commission_rub=referral_commission_rub,
            subagent_commission_rub=subagent_commission_rub,
        )

    def _build_positions(self, positions: dict[str, _PositionState], as_of: str) -> list[CurrencyPosition]:
        currency_positions: list[CurrencyPosition] = []
        for currency, state in sorted(positions.items()):
            if abs(state.quantity) < 1e-9:
                continue
            market_rate = self._safe_rate(as_of, currency)
            currency_positions.append(
                CurrencyPosition(
                    currency=currency,
                    quantity=state.quantity,
                    average_rate=state.average_rate,
                    market_rate=market_rate,
                    mtm_value_rub=state.quantity * market_rate,
                    unrealized_pnl_rub=0.0,
                )
            )
        return currency_positions

    @staticmethod
    def _apply_position(state: _PositionState, deal: Deal, signed_amount: float) -> None:
        state.quantity += signed_amount
        amount_base = abs(signed_amount)
        if deal.client_fix_rate is not None and amount_base:
            state.weighted_rate_amount += amount_base * float(deal.client_fix_rate)
            state.weighted_amount += amount_base

    @staticmethod
    def _has_registry_amount(deal: Deal) -> bool:
        return deal.deal_amount is not None and abs(float(deal.deal_amount)) > 1e-9

    @staticmethod
    def _deal_currency(deal: Deal) -> str:
        return (deal.deal_currency or deal.currency_buy or "RUB").upper()

    @staticmethod
    def _deal_date(deal: Deal) -> str:
        return deal.client_fix_date or deal.request_date or deal.trade_date or date.today().isoformat()

    @staticmethod
    def _percent(value: float | None) -> float:
        return float(value or 0.0) / 100.0

    @staticmethod
    def _referral_commission_amount(_: Deal) -> float:
        return 0.0

    def _amount_to_rub(self, amount: float, currency: str, rate_date: str) -> float:
        return amount * self._safe_rate(rate_date, currency)

    def _safe_rate(self, rate_date: str, currency: str) -> float:
        normalized = (currency or "RUB").upper()
        if normalized == "RUB":
            return 1.0
        try:
            rate = self._rates_service.get_rate_to_rub(rate_date, normalized, fetch_cbr=False)
            return rate if rate > 0 else 1.0
        except ValueError:
            return 1.0

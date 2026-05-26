"""Business-level preparation of local analytics data."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.database.connection import DEFAULT_DB_PATH
from app.repositories.deals_repository import DealsRepository
from app.repositories.rates_repository import RatesRepository
from app.services.pnl_service import PnlService
from app.services.rates_service import RatesService


USD_LIKE_CURRENCIES = {"USD", "USDT", "USDC"}
STRONGER_THAN_USD_CURRENCIES = {"EUR", "GBP", "CHF", "KWD", "BHD", "OMR", "JOD", "KYD", "GIP"}
CBR_RATE_NOMINALS = {
    "AMD": 100,
    "HUF": 100,
    "IDR": 10000,
    "JPY": 100,
    "KGS": 10,
    "KRW": 1000,
    "KZT": 100,
    "RSD": 100,
    "TJS": 10,
    "UZS": 10000,
    "VND": 10000,
}


class AnalyticsService:
    """Prepare aggregate analytics without UI or Dash-specific code."""

    def build_dashboard_payload(
        self,
        deals: pd.DataFrame,
        db_path: Path = DEFAULT_DB_PATH,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return KPI values and chart-ready tables for dashboard filters."""
        filtered = self.apply_filters(deals, filters or {})
        pnl_summary = self._pnl_summary(db_path)
        return {
            "kpis": self._build_kpis(filtered, pnl_summary),
            "pnl_by_date": self._pnl_by_date(filtered),
            "pnl_by_date_currency": self._pnl_by_date_currency(filtered),
            "pnl_by_currency": self._pnl_by_currency(filtered),
            "pnl_by_manager": self._pnl_by_manager(filtered),
            "volume_by_date": self._volume_by_date(filtered),
            "turnover_by_date_usd": self._turnover_by_date_usd(filtered),
            "turnover_by_date_currency": self._turnover_by_date_currency(filtered),
            "deals_by_status": self._deals_by_status(filtered),
            "pnl_by_referral": self._pnl_by_referral(filtered),
            "pnl_by_partner": self._pnl_by_partner(filtered),
            "roi_by_referral": self._roi_by(filtered, "customer_article_name", "referral"),
            "roi_by_partner": self._roi_by(filtered, "payment_agent", "partner"),
            "top_clients": self._top_clients(filtered),
            "waterfall": self._waterfall(filtered, pnl_summary),
            "rows_count": int(len(filtered)),
        }

    def build_filter_options(self, deals: pd.DataFrame) -> dict[str, list[str]]:
        """Return distinct filter values for Dash dropdowns."""
        return {
            "currency": _distinct(deals, "deal_currency"),
            "operation_type": _operation_type_options(deals),
            "referral": _distinct(deals, "customer_article_name"),
            "payment_agent": _distinct(deals, "payment_agent"),
            "manager": _distinct(deals, "manager"),
            "status": _distinct(deals, "payment_status"),
        }

    def apply_filters(self, deals: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
        """Apply dashboard filters to a deals DataFrame."""
        if deals.empty:
            return deals.copy()

        result = deals.copy()
        start_date = _safe_date(filters.get("start_date"))
        end_date = _safe_date(filters.get("end_date"))
        if start_date:
            result = result[result["analytics_date"] >= start_date]
        if end_date:
            result = result[result["analytics_date"] <= end_date]

        for column, key in (
            ("deal_currency", "currency"),
            ("operation_type_label", "operation_type"),
            ("client_name", "client"),
            ("customer_article_name", "referral"),
            ("payment_agent", "payment_agent"),
            ("manager", "manager"),
            ("payment_status", "status"),
        ):
            values = filters.get(key)
            if values:
                normalized = {str(value).casefold() for value in values}
                result = result[result[column].fillna("").astype(str).str.casefold().isin(normalized)]
        exclude_clients = filters.get("client_exclude")
        if exclude_clients:
            normalized_exclude = {str(value).casefold() for value in exclude_clients}
            result = result[~result["client_name"].fillna("").astype(str).str.casefold().isin(normalized_exclude)]
        return result

    def _build_kpis(self, deals: pd.DataFrame, pnl_summary: dict[str, float]) -> dict[str, float]:
        gross_fee = float(deals["gross_income_usd"].sum()) if not deals.empty else 0.0
        commissions = float(deals["total_costs_usd"].sum()) if not deals.empty else 0.0
        net_pnl = float(deals["net_pnl_usd"].sum()) if not deals.empty else 0.0
        return {
            "total_pnl": net_pnl,
            "realized_pnl": net_pnl,
            "mtm_pnl": float(pnl_summary.get("mtm_pnl", 0.0)),
            "volume": float(deals["deal_amount_abs"].sum()) if not deals.empty else 0.0,
            "commissions": commissions,
            "count_deals": float(len(deals)),
        }

    def _pnl_by_date(self, deals: pd.DataFrame) -> pd.DataFrame:
        if deals.empty:
            return pd.DataFrame(
                columns=[
                    "date",
                    "pnl",
                    "gross_income",
                    "total_costs",
                    "client_percent_fee",
                    "fixed_commission",
                    "swift_income",
                    "agent_commission",
                    "swift_agent_commission",
                    "referral_commission",
                    "repeat_penalty",
                    "deals_count",
                    "winning_deals_count",
                    "volume_usd",
                ]
            )
        prepared = deals.copy()
        prepared["is_winning_deal"] = prepared["net_pnl_usd"].astype(float) >= 0
        grouped = deals.groupby("analytics_date", as_index=False).agg(
            pnl=("net_pnl_usd", "sum"),
            gross_income=("gross_income_usd", "sum"),
            total_costs=("total_costs_usd", "sum"),
            client_percent_fee=("client_percent_fee_usd", "sum"),
            fixed_commission=("fixed_commission_usd", "sum"),
            swift_income=("swift_usd", "sum"),
            agent_commission=("agent_commission_usd", "sum"),
            swift_agent_commission=("swift_commission_usd", "sum"),
            referral_commission=("referral_commission_usd", "sum"),
            repeat_penalty=("repeat_payment_penalty_usd", "sum"),
            deals_count=("id", "count"),
            volume_usd=("deal_amount_usd", "sum"),
        )
        wins = prepared.groupby("analytics_date", as_index=False).agg(winning_deals_count=("is_winning_deal", "sum"))
        grouped = grouped.merge(wins, on="analytics_date", how="left")
        return grouped.rename(columns={"analytics_date": "date"}).sort_values("date")

    def _pnl_by_date_currency(self, deals: pd.DataFrame) -> pd.DataFrame:
        if deals.empty:
            return pd.DataFrame(
                columns=[
                    "date",
                    "currency",
                    "pnl",
                    "gross_income",
                    "total_costs",
                    "client_percent_fee",
                    "fixed_commission",
                    "swift_income",
                    "agent_commission",
                    "swift_agent_commission",
                    "referral_commission",
                    "repeat_penalty",
                    "deals_count",
                    "winning_deals_count",
                    "volume",
                ]
            )
        native = deals.copy()
        native["is_winning_deal"] = native["net_pnl_usd"].astype(float) >= 0
        usd_amount = native["deal_amount_usd"].replace(0, pd.NA)
        native["native_ratio"] = (native["deal_amount_abs"] / usd_amount).fillna(1.0)
        for source, target in (
            ("net_pnl_usd", "pnl_native"),
            ("gross_income_usd", "gross_income_native"),
            ("total_costs_usd", "total_costs_native"),
            ("client_percent_fee_usd", "client_percent_fee_native"),
            ("fixed_commission_usd", "fixed_commission_native"),
            ("swift_usd", "swift_native"),
            ("agent_commission_usd", "agent_commission_native"),
            ("swift_commission_usd", "swift_commission_native"),
            ("referral_commission_usd", "referral_commission_native"),
            ("repeat_payment_penalty_usd", "repeat_penalty_native"),
        ):
            native[target] = native[source] * native["native_ratio"]
        grouped = native.groupby(["analytics_date", "deal_currency"], as_index=False).agg(
            pnl=("pnl_native", "sum"),
            gross_income=("gross_income_native", "sum"),
            total_costs=("total_costs_native", "sum"),
            client_percent_fee=("client_percent_fee_native", "sum"),
            fixed_commission=("fixed_commission_native", "sum"),
            swift_income=("swift_native", "sum"),
            agent_commission=("agent_commission_native", "sum"),
            swift_agent_commission=("swift_commission_native", "sum"),
            referral_commission=("referral_commission_native", "sum"),
            repeat_penalty=("repeat_penalty_native", "sum"),
            deals_count=("id", "count"),
            winning_deals_count=("is_winning_deal", "sum"),
            volume=("deal_amount_abs", "sum"),
        )
        return grouped.rename(columns={"analytics_date": "date", "deal_currency": "currency"}).sort_values(["date", "currency"])

    def _pnl_by_currency(self, deals: pd.DataFrame) -> pd.DataFrame:
        return _sum_by(deals, "deal_currency", "net_pnl_usd", "currency", "pnl")

    def _pnl_by_manager(self, deals: pd.DataFrame) -> pd.DataFrame:
        return _sum_by(deals, "manager", "net_pnl_usd", "manager", "pnl")

    def _volume_by_date(self, deals: pd.DataFrame) -> pd.DataFrame:
        if deals.empty:
            return pd.DataFrame(columns=["date", "volume"])
        grouped = deals.groupby("analytics_date", as_index=False)["deal_amount_abs"].sum()
        return grouped.rename(columns={"analytics_date": "date", "deal_amount_abs": "volume"}).sort_values("date")

    def _turnover_by_date_usd(self, deals: pd.DataFrame) -> pd.DataFrame:
        if deals.empty:
            return pd.DataFrame(columns=["date", "turnover", "deals_count"])
        grouped = deals.groupby("analytics_date", as_index=False).agg(
            turnover=("deal_amount_usd", "sum"),
            deals_count=("id", "count"),
        )
        return grouped.rename(columns={"analytics_date": "date"}).sort_values("date")

    def _turnover_by_date_currency(self, deals: pd.DataFrame) -> pd.DataFrame:
        if deals.empty:
            return pd.DataFrame(columns=["date", "currency", "turnover", "deals_count"])
        grouped = deals.groupby(["analytics_date", "deal_currency"], as_index=False).agg(
            turnover=("deal_amount_abs", "sum"),
            deals_count=("id", "count"),
        )
        return grouped.rename(columns={"analytics_date": "date", "deal_currency": "currency"}).sort_values(["date", "currency"])

    def _deals_by_status(self, deals: pd.DataFrame) -> pd.DataFrame:
        if deals.empty:
            return pd.DataFrame(columns=["status", "count"])
        result = deals.groupby("payment_status", dropna=False).size().reset_index(name="count")
        result["payment_status"] = result["payment_status"].fillna("Без статуса")
        return result.rename(columns={"payment_status": "status"}).sort_values("count", ascending=False)

    def _pnl_by_referral(self, deals: pd.DataFrame) -> pd.DataFrame:
        return _sum_by(deals, "customer_article_name", "net_pnl_usd", "referral", "pnl")

    def _pnl_by_partner(self, deals: pd.DataFrame) -> pd.DataFrame:
        return _sum_by(deals, "payment_agent", "net_pnl_usd", "partner", "pnl")

    def _top_clients(self, deals: pd.DataFrame, limit: int = 9) -> pd.DataFrame:
        """Return top clients by PnL, with the remaining clients grouped as Other."""
        columns = ["client", "pnl", "deals_count", "volume_usd"]
        if deals.empty or "client_name" not in deals.columns:
            return pd.DataFrame(columns=columns)
        grouped = deals.groupby("client_name", dropna=False, as_index=False).agg(
            pnl=("net_pnl_usd", "sum"),
            deals_count=("id", "count"),
            volume_usd=("deal_amount_usd", "sum"),
        )
        grouped["client_name"] = grouped["client_name"].fillna("Без клиента").astype(str).str.strip()
        grouped.loc[grouped["client_name"] == "", "client_name"] = "Без клиента"
        grouped = grouped.rename(columns={"client_name": "client"}).sort_values("pnl", ascending=False)
        if len(grouped) <= limit:
            return grouped[columns].reset_index(drop=True)
        top = grouped.head(limit).copy()
        rest = grouped.iloc[limit:]
        other = pd.DataFrame(
            [
                {
                    "client": "Остальные",
                    "pnl": float(rest["pnl"].sum()),
                    "deals_count": int(rest["deals_count"].sum()),
                    "volume_usd": float(rest["volume_usd"].sum()),
                }
            ]
        )
        return pd.concat([top[columns], other], ignore_index=True)

    def _roi_by(self, deals: pd.DataFrame, source_column: str, label_column: str) -> pd.DataFrame:
        """Return profitability by dimension as PnL divided by USD turnover."""
        columns = [label_column, "roi", "pnl", "volume_usd", "deals_count"]
        if deals.empty or source_column not in deals.columns:
            return pd.DataFrame(columns=columns)
        grouped = deals.groupby(source_column, dropna=False, as_index=False).agg(
            pnl=("net_pnl_usd", "sum"),
            volume_usd=("deal_amount_usd", "sum"),
            deals_count=("id", "count"),
        )
        grouped[source_column] = grouped[source_column].fillna("Без значения").astype(str).str.strip()
        grouped.loc[grouped[source_column] == "", source_column] = "Без значения"
        grouped["roi"] = grouped.apply(
            lambda row: float(row["pnl"]) / float(row["volume_usd"]) * 100 if float(row["volume_usd"] or 0.0) else 0.0,
            axis=1,
        )
        return grouped.rename(columns={source_column: label_column})[columns].sort_values("roi", ascending=False)

    def _waterfall(self, deals: pd.DataFrame, pnl_summary: dict[str, float]) -> pd.DataFrame:
        client_percent = float(deals["client_percent_fee_usd"].sum()) if not deals.empty else 0.0
        fixed = float(deals["fixed_commission_usd"].sum()) if not deals.empty else 0.0
        swift = float(deals["swift_usd"].sum()) if not deals.empty else 0.0
        agent = -float(deals["agent_commission_usd"].sum()) if not deals.empty else 0.0
        swift_agent = -float(deals["swift_commission_usd"].sum()) if not deals.empty else 0.0
        referral = -float(deals["referral_commission_cost_usd"].sum()) if not deals.empty else 0.0
        repeat_penalty = float(deals["repeat_payment_penalty_usd"].sum()) if not deals.empty else 0.0
        total = client_percent + fixed + swift + agent + swift_agent + referral + repeat_penalty
        return pd.DataFrame(
            [
                {"component": "Ставка клиента %", "value": client_percent, "measure": "relative"},
                {"component": "Фикс. комиссия", "value": fixed, "measure": "relative"},
                {"component": "SWIFT", "value": swift, "measure": "relative"},
                {"component": "Комиссия ПА", "value": agent, "measure": "relative"},
                {"component": "SWIFT ПА", "value": swift_agent, "measure": "relative"},
                {"component": "Ставка реферала", "value": referral, "measure": "relative"},
                {"component": "Штраф переотправки", "value": repeat_penalty, "measure": "relative"},
                {"component": "Итого PnL", "value": total, "measure": "total"},
            ]
        )

    def _pnl_summary(self, db_path: Path) -> dict[str, float]:
        try:
            connection_factory = _read_only_connection_factory(db_path)
            rates_service = RatesService(RatesRepository(connection_factory))
            pnl = PnlService(DealsRepository(connection_factory), rates_service).calculate()
            return {
                "total_pnl": pnl.total_pnl_rub,
                "realized_pnl": pnl.realized_pnl_rub,
                "mtm_pnl": pnl.unrealized_pnl_rub,
            }
        except Exception:
            return {"total_pnl": 0.0, "realized_pnl": 0.0, "mtm_pnl": 0.0}


def prepare_deals_frame(
    deals: pd.DataFrame,
    rates: pd.DataFrame | None = None,
    referrals: pd.DataFrame | None = None,
    rate_conditions: pd.DataFrame | None = None,
    client_exceptions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Normalize raw SQLite deal rows into analytics columns."""
    if deals.empty:
        return _empty_deals_frame()

    result = deals.copy()
    rate_lookup = _build_rate_lookup(rates)
    for column in (
        "pnl_client_percent_fee_usd",
        "pnl_fixed_commission_usd",
        "pnl_swift_usd",
        "pnl_agent_commission_usd",
        "pnl_swift_commission_usd",
        "pnl_referral_commission_usd",
    ):
        result[f"{column}_is_manual"] = pd.to_numeric(result.get(column), errors="coerce").notna()
    for column in (
        "deal_amount",
        "client_rate_percent",
        "fixed_commission_amount",
        "swift_amount",
        "agent_commission_amount",
        "swift_commission_amount",
        "client_cross_rate",
        "client_fix_rate",
        "usd_rate",
        "repeat_payment_commission_percent",
        "repeat_payment_penalty_usd",
        "pnl_client_percent_fee_usd",
        "pnl_fixed_commission_usd",
        "pnl_swift_usd",
        "pnl_agent_commission_usd",
        "pnl_swift_commission_usd",
        "pnl_referral_commission_usd",
    ):
        result[column] = pd.to_numeric(result.get(column), errors="coerce").fillna(0.0)

    result["analytics_date"] = (
        result.get("client_fix_date")
        .fillna(result.get("request_date"))
        .fillna(result.get("trade_date"))
        .fillna("")
        .astype(str)
    )
    result["deal_currency"] = result.get("deal_currency").fillna("RUB").astype(str).str.upper()
    result["client_name"] = result.get("client_name").fillna("Без клиента").astype(str).str.strip()
    result.loc[result["client_name"] == "", "client_name"] = "Без клиента"
    result["customer_article_name"] = result.get("customer_article_name").fillna("Без банка").astype(str).str.strip()
    result.loc[result["customer_article_name"] == "", "customer_article_name"] = "Без банка"
    result["deal_amount_abs"] = result["deal_amount"].abs()
    result["operation_type_label"] = result.apply(_operation_type_label, axis=1)
    result["is_refund_to_client"] = result.get("client_refund_date").fillna("").astype(str).str.strip() != ""
    result["deal_amount_usd"] = result.apply(lambda row: _usd_amount(row.get("deal_amount"), row.get("deal_currency"), row, rate_lookup), axis=1)
    result["client_rate_fraction"] = result["client_rate_percent"].apply(_positive_percent_fraction)
    result["repeat_rate_fraction"] = result["repeat_payment_commission_percent"].apply(_positive_percent_fraction)
    result.loc[result.get("is_repeat_payment", 0).fillna(0).astype(int) == 0, "repeat_rate_fraction"] = 0.0
    result["effective_client_rate"] = result["client_rate_fraction"] + result["repeat_rate_fraction"]
    result["client_percent_fee_usd"] = result["deal_amount_usd"] * result["effective_client_rate"]
    result.loc[result["pnl_client_percent_fee_usd_is_manual"], "client_percent_fee_usd"] = result.loc[
        result["pnl_client_percent_fee_usd_is_manual"], "pnl_client_percent_fee_usd"
    ].abs()
    result["fixed_commission_usd"] = result.apply(
        lambda row: _manual_or_converted(row, "pnl_fixed_commission_usd", "fixed_commission_amount", "fixed_commission_currency", rate_lookup),
        axis=1,
    )
    result["swift_usd"] = result.apply(
        lambda row: _manual_or_converted(row, "pnl_swift_usd", "swift_amount", "swift_currency", rate_lookup),
        axis=1,
    )
    result["agent_commission_usd"] = result.apply(
        lambda row: _manual_or_converted(row, "pnl_agent_commission_usd", "agent_commission_amount", "agent_commission_currency", rate_lookup),
        axis=1,
    )
    result["swift_commission_usd"] = result.apply(
        lambda row: _manual_or_converted(row, "pnl_swift_commission_usd", "swift_commission_amount", "swift_commission_currency", rate_lookup),
        axis=1,
    )
    referral_lookup = _build_referral_lookup(referrals)
    condition_lookup = _build_condition_lookup(rate_conditions)
    exception_lookup = _build_client_exception_lookup(client_exceptions)
    result["referral_commission_usd"] = result.apply(
        lambda row: _analytics_referral_commission_usd(row, referral_lookup, condition_lookup, exception_lookup, rate_lookup),
        axis=1,
    )
    result.loc[result["is_refund_to_client"], ["client_percent_fee_usd", "fixed_commission_usd", "swift_usd", "referral_commission_usd"]] = 0.0
    result.loc[result.get("is_repeat_payment", 0).fillna(0).astype(int) == 1, "referral_commission_usd"] = 0.0
    result["repeat_payment_penalty_usd"] = result["repeat_payment_penalty_usd"].abs()
    result["referral_commission_cost_usd"] = result["referral_commission_usd"].abs()
    result["gross_income_usd"] = (
        result["client_percent_fee_usd"]
        + result["fixed_commission_usd"]
        + result["swift_usd"]
        + result["repeat_payment_penalty_usd"]
    )
    result["total_costs_usd"] = (
        result["agent_commission_usd"]
        + result["swift_commission_usd"]
        + result["referral_commission_cost_usd"]
    )
    result["net_pnl_usd"] = result["gross_income_usd"] - result["total_costs_usd"]
    return result


def _read_only_connection_factory(db_path: Path):
    def connect() -> sqlite3.Connection:
        uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.create_function("CASEFOLD", 1, lambda value: "" if value is None else str(value).casefold())
        connection.execute("PRAGMA query_only = ON")
        return connection

    return connect


def _rub_rate(row: pd.Series) -> float:
    currency = str(row.get("deal_currency") or "RUB").upper()
    if currency == "RUB":
        return 1.0
    for column in ("client_cross_rate", "usd_rate", "client_fix_rate"):
        value = row.get(column)
        if pd.notna(value) and float(value or 0) > 0:
            return float(value)
    return 1.0


def _manual_or_converted(
    row: pd.Series,
    manual_column: str,
    amount_column: str,
    currency_column: str,
    rate_lookup: dict[tuple[str, str], float],
) -> float:
    if bool(row.get(f"{manual_column}_is_manual", False)):
        return abs(float(row.get(manual_column) or 0.0))
    value = _usd_amount(row.get(amount_column), row.get(currency_column) or row.get("deal_currency"), row, rate_lookup)
    return 0.0 if value is None else abs(float(value))


def _usd_amount(amount: Any, currency: Any, row: pd.Series, rate_lookup: dict[tuple[str, str], float] | None = None) -> float:
    value = float(amount or 0.0)
    normalized = _normalize_currency(currency or row.get("deal_currency") or "")
    if normalized in USD_LIKE_CURRENCIES:
        return abs(value)
    deal_currency = _normalize_currency(row.get("deal_currency") or "")
    if rate_lookup is not None and normalized != deal_currency:
        converted = _usd_amount_from_rates(value, normalized, row, rate_lookup)
        return abs(converted) if converted is not None else 0.0
    rate = float(row.get("client_cross_rate") or 0.0)
    if rate <= 0:
        return abs(value)
    converted = value * rate if _should_multiply_to_usd(normalized, rate) else value / rate
    return abs(converted)


def _should_multiply_to_usd(currency: str, rate: float) -> bool:
    normalized = str(currency or "").strip().upper()
    if normalized in STRONGER_THAN_USD_CURRENCIES:
        return rate >= 1
    return rate < 1


def _usd_amount_from_rates(
    amount: float,
    currency: str,
    row: pd.Series,
    rate_lookup: dict[tuple[str, str], float],
) -> float | None:
    rate_date = _safe_date(row.get("client_fix_date")) or _safe_date(row.get("request_date")) or _safe_date(row.get("trade_date"))
    if not rate_date:
        return None
    currency_rate = 1.0 if currency == "RUB" else rate_lookup.get((rate_date, currency))
    usd_rate = rate_lookup.get((rate_date, "USD"))
    if currency_rate is None or usd_rate is None or usd_rate <= 0:
        return None
    return amount * currency_rate / usd_rate


def _build_rate_lookup(rates: pd.DataFrame | None) -> dict[tuple[str, str], float]:
    if rates is None or rates.empty:
        return {}
    lookup: dict[tuple[str, str], float] = {}
    prepared = rates.copy()
    prepared["currency"] = prepared["currency"].fillna("").astype(str).map(_normalize_currency)
    prepared["source_priority"] = prepared["source"].fillna("").astype(str).str.upper().map(lambda value: 0 if value == "MANUAL" else 1)
    prepared = prepared.sort_values(["rate_date", "currency", "source_priority"])
    for row in prepared.itertuples(index=False):
        rate_date = str(getattr(row, "rate_date"))
        currency = str(getattr(row, "currency"))
        source = str(getattr(row, "source") or "").upper()
        nominal = CBR_RATE_NOMINALS.get(currency, 1) if source == "CBR" else 1
        lookup.setdefault((rate_date, currency), float(getattr(row, "rate_to_rub")) / nominal)
    lookup[("", "RUB")] = 1.0
    return lookup


def _normalize_currency(currency: Any) -> str:
    normalized = str(currency or "").strip().upper()
    return "CNH" if normalized == "CNY" else normalized


def _operation_type_label(row: pd.Series) -> str:
    is_usdt = _normalize_currency(row.get("deal_currency")) == "USDT"
    is_export = _is_export_row(row)
    if is_usdt:
        return "USDT-Экспорт" if is_export else "USDT-Импорт"
    return "Экспорт" if is_export else "Импорт"


def _is_export_row(row: pd.Series) -> bool:
    operation_type = str(row.get("operation_type") or "").strip().casefold()
    if operation_type in {"export", "экспорт"}:
        return True
    if operation_type in {"import", "импорт"}:
        return False
    return float(row.get("deal_amount") or row.get("amount_buy") or 0.0) < 0


def _percent_fraction(value: Any) -> float:
    numeric = float(value or 0.0)
    return numeric if abs(numeric) <= 1 else numeric / 100


def _positive_percent_fraction(value: Any) -> float:
    return abs(_percent_fraction(value))


def _build_referral_lookup(referrals: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    """Build case-insensitive referral lookup by name and code."""
    if referrals is None or referrals.empty:
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for row in referrals.to_dict("records"):
        prepared = dict(row)
        for key in ("name", "code"):
            value = str(prepared.get(key) or "").strip()
            if value:
                lookup[value.casefold()] = prepared
    return lookup


def _build_condition_lookup(rate_conditions: pd.DataFrame | None) -> dict[int, list[dict[str, Any]]]:
    """Group active rate conditions by referral id in priority order."""
    if rate_conditions is None or rate_conditions.empty:
        return {}
    prepared = rate_conditions.copy()
    prepared["is_active"] = pd.to_numeric(prepared.get("is_active"), errors="coerce").fillna(0).astype(int)
    prepared["priority"] = pd.to_numeric(prepared.get("priority"), errors="coerce").fillna(100).astype(int)
    prepared = prepared[prepared["is_active"] == 1].sort_values(["referral_id", "priority", "id"])
    lookup: dict[int, list[dict[str, Any]]] = {}
    for row in prepared.to_dict("records"):
        referral_id = int(row.get("referral_id") or 0)
        if referral_id:
            lookup.setdefault(referral_id, []).append(row)
    return lookup


def _build_client_exception_lookup(client_exceptions: pd.DataFrame | None) -> dict[str, list[dict[str, Any]]]:
    """Group client exception rows by normalized client name."""
    if client_exceptions is None or client_exceptions.empty:
        return {}
    lookup: dict[str, list[dict[str, Any]]] = {}
    for row in client_exceptions.to_dict("records"):
        client_name = str(row.get("client_name") or "").strip().casefold()
        if client_name:
            lookup.setdefault(client_name, []).append(dict(row))
    return lookup


def _analytics_referral_commission_usd(
    row: pd.Series,
    referral_lookup: dict[str, dict[str, Any]],
    condition_lookup: dict[int, list[dict[str, Any]]],
    exception_lookup: dict[str, list[dict[str, Any]]],
    rate_lookup: dict[tuple[str, str], float],
) -> float:
    """
    Calculate the same referral amount used by the registry PnL USD column.

    Formula for an auto-matched condition:
    client percent fee USD + client fixed fee USD - condition percent USD - condition fixed USD.
    """
    if bool(row.get("pnl_referral_commission_usd_is_manual", False)):
        return abs(float(row.get("pnl_referral_commission_usd") or 0.0))
    if bool(row.get("is_refund_to_client", False)) or int(row.get("is_repeat_payment") or 0) == 1:
        return 0.0
    if _has_client_exception(row, exception_lookup):
        return 0.0

    referral_name = str(row.get("customer_article_name") or "").strip()
    if not referral_name or referral_name.casefold() in {"без банка", "Р±РµР· Р±Р°РЅРєР°"}:
        return 0.0
    referral = referral_lookup.get(referral_name.casefold())
    if not referral or int(referral.get("is_active") or 0) != 1:
        return 0.0

    referral_id = int(referral.get("id") or 0)
    matches = [
        condition
        for condition in condition_lookup.get(referral_id, [])
        if _condition_matches_deal(condition, row)
    ]
    if len(matches) != 1:
        return 0.0
    return _condition_referral_commission_usd(matches[0], row, rate_lookup)


def _has_client_exception(row: pd.Series, exception_lookup: dict[str, list[dict[str, Any]]]) -> bool:
    client_name = str(row.get("client_name") or "").strip().casefold()
    if not client_name:
        return False
    deal_date = _safe_date(row.get("client_fix_date")) or _safe_date(row.get("analytics_date"))
    if not deal_date:
        return False
    for exception in exception_lookup.get(client_name, []):
        date_from = _safe_date(exception.get("date_from"))
        date_to = _safe_date(exception.get("date_to"))
        if date_from and deal_date < date_from:
            continue
        if date_to and deal_date > date_to:
            continue
        return True
    return False


def _condition_matches_deal(condition: dict[str, Any], row: pd.Series) -> bool:
    operation_type = str(condition.get("operation_type") or "").strip()
    if operation_type and _operation_type_key(operation_type) != _operation_type_key(_operation_type_label(row)):
        return False

    condition_currency = _normalize_currency(condition.get("currency") or "")
    if condition_currency and condition_currency != _normalize_currency(row.get("deal_currency")):
        return False

    deal_date = _safe_date(row.get("client_fix_date")) or _safe_date(row.get("analytics_date"))
    if not deal_date:
        return False
    date_from = _safe_date(condition.get("date_from"))
    date_to = _safe_date(condition.get("date_to"))
    if date_from and deal_date < date_from:
        return False
    if date_to and deal_date > date_to:
        return False

    amount = _amount_for_condition(condition, row)
    if amount is None:
        return False
    amount_from = _optional_float(condition.get("amount_from"))
    amount_to = _optional_float(condition.get("amount_to"))
    if amount_from is not None and amount < amount_from:
        return False
    if amount_to is not None and amount >= amount_to:
        return False
    return True


def _condition_referral_commission_usd(
    condition: dict[str, Any],
    row: pd.Series,
    rate_lookup: dict[tuple[str, str], float],
) -> float:
    base_amount = _amount_for_condition(condition, row) or 0.0
    basis = str(condition.get("amount_basis") or "deal_currency")
    base_currency = "USD" if basis == "usd_equivalent" else _normalize_currency(row.get("deal_currency"))
    condition_rate = abs(_percent_fraction(condition.get("rate_value")))
    condition_percent_native = base_amount * condition_rate
    percent_currency = condition.get("percent_commission_currency") or base_currency
    condition_percent_usd = _usd_amount(condition_percent_native, percent_currency, row, rate_lookup)

    fixed_amount = abs(float(condition.get("fixed_commission_amount") or 0.0))
    fixed_currency = condition.get("fixed_commission_currency") or percent_currency or base_currency
    condition_fixed_usd = _usd_amount(fixed_amount, fixed_currency, row, rate_lookup)

    client_percent_usd = abs(float(row.get("client_percent_fee_usd") or 0.0))
    client_fixed_usd = abs(float(row.get("fixed_commission_usd") or 0.0))
    return client_percent_usd + client_fixed_usd - condition_percent_usd - condition_fixed_usd


def _amount_for_condition(condition: dict[str, Any], row: pd.Series) -> float | None:
    if str(condition.get("amount_basis") or "deal_currency") == "usd_equivalent":
        return abs(float(row.get("deal_amount_usd") or 0.0))
    return abs(float(row.get("deal_amount") or row.get("deal_amount_abs") or 0.0))


def _operation_type_key(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if "usdt" in text:
        return "export" if "export" in text or "экспорт" in text or "СЌРєСЃРїРѕСЂС‚".casefold() in text else "import"
    if text in {"export", "экспорт", "СЌРєСЃРїРѕСЂС‚".casefold()}:
        return "export"
    if text in {"import", "импорт", "РёРјРїРѕСЂС‚".casefold()}:
        return "import"
    return "export" if "export" in text or "экспорт" in text or "СЌРєСЃРїРѕСЂС‚".casefold() in text else "import"


def _optional_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None
        return float(text.replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _sum_by(deals: pd.DataFrame, column: str, value_column: str, label: str, value: str) -> pd.DataFrame:
    if deals.empty:
        return pd.DataFrame(columns=[label, value])
    grouped = deals.groupby(column, dropna=False, as_index=False)[value_column].sum()
    grouped[column] = grouped[column].fillna("Без значения")
    return grouped.rename(columns={column: label, value_column: value}).sort_values(value, ascending=False)


def _distinct(deals: pd.DataFrame, column: str) -> list[str]:
    if deals.empty or column not in deals.columns:
        return []
    values = deals[column].dropna().astype(str).str.strip()
    return sorted({value for value in values if value}, key=str.casefold)


def _operation_type_options(deals: pd.DataFrame) -> list[str]:
    if deals.empty or "operation_type_label" not in deals.columns:
        return []
    existing = set(deals["operation_type_label"].dropna().astype(str).str.strip())
    order = ["Импорт", "Экспорт", "USDT-Импорт", "USDT-Экспорт"]
    return [value for value in order if value in existing]


def _safe_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _empty_deals_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "analytics_date",
            "deal_currency",
            "operation_type_label",
            "client_name",
            "customer_article_name",
            "payment_agent",
            "manager",
            "payment_status",
            "deal_amount_abs",
            "deal_amount_usd",
            "gross_income_usd",
            "client_percent_fee_usd",
            "fixed_commission_usd",
            "swift_usd",
            "agent_commission_usd",
            "swift_commission_usd",
            "referral_commission_usd",
            "referral_commission_cost_usd",
            "repeat_payment_penalty_usd",
            "total_costs_usd",
            "net_pnl_usd",
        ]
    )

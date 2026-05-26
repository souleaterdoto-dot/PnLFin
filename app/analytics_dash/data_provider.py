"""Read-only SQLite data provider for Dash analytics."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from app.services.analytics_service import AnalyticsService, prepare_deals_frame


class AnalyticsDataProvider:
    """Provide cached, read-only analytics data for Dash callbacks."""

    def __init__(self, db_path: Path, analytics_service: AnalyticsService | None = None) -> None:
        self._db_path = Path(db_path)
        self._analytics_service = analytics_service or AnalyticsService()
        self._lock = Lock()
        self._cached_mtime: float | None = None
        self._cached_deals: pd.DataFrame | None = None

    def get_initial_state(self) -> dict[str, Any]:
        """Return filter options and date bounds for initial dashboard render."""
        deals = self._deals()
        options = self._analytics_service.build_filter_options(deals)
        referral_meta = self._referral_meta(options.get("referral", []))
        if deals.empty:
            return {"options": options, "referrals": referral_meta, "min_date": None, "max_date": None}
        dates = deals["analytics_date"].replace("", pd.NA).dropna()
        return {
            "options": options,
            "referrals": referral_meta,
            "min_date": str(dates.min()) if not dates.empty else None,
            "max_date": str(dates.max()) if not dates.empty else None,
        }

    def get_dashboard_data(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return all KPI and chart data for the current filters."""
        deals = self._deals()
        return self._analytics_service.build_dashboard_payload(deals, self._db_path, filters or {})

    def _deals(self) -> pd.DataFrame:
        with self._lock:
            mtime = self._db_path.stat().st_mtime if self._db_path.exists() else 0.0
            if self._cached_deals is not None and self._cached_mtime == mtime:
                return self._cached_deals.copy()

            with self._connect_read_only() as connection:
                raw = pd.read_sql_query(
                    """
                    SELECT
                        id,
                        trade_date,
                        operation_type,
                        request_date,
                        client_fix_date,
                        client_refund_date,
                        payment_status,
                        manager,
                        client_name,
                        deal_amount,
                        deal_currency,
                        currency_buy,
                        amount_buy,
                        currency_sell,
                        client_rate_percent,
                        fixed_commission_amount,
                        fixed_commission_currency,
                        swift_amount,
                        swift_currency,
                        client_fix_rate,
                        usd_rate,
                        client_cross_rate,
                        payment_agent,
                        agent_commission_amount,
                        agent_commission_currency,
                        swift_commission_amount,
                        swift_commission_currency,
                        customer_article_name,
                        is_repeat_payment,
                        repeat_payment_commission_percent,
                        repeat_payment_penalty_usd,
                        pnl_client_percent_fee_usd,
                        pnl_fixed_commission_usd,
                        pnl_swift_usd,
                        pnl_agent_commission_usd,
                        pnl_swift_commission_usd,
                        pnl_referral_commission_usd,
                        included_in_calc
                    FROM deals
                    WHERE included_in_calc = 1
                    """,
                    connection,
                )
                rates = pd.read_sql_query(
                    """
                    SELECT rate_date, currency, rate_to_rub, source
                    FROM rates
                    """,
                    connection,
                )
                referrals = pd.read_sql_query(
                    """
                    SELECT id, name, code, is_active
                    FROM referrals
                    """,
                    connection,
                )
                rate_conditions = pd.read_sql_query(
                    """
                    SELECT
                        id,
                        referral_id,
                        is_active,
                        priority,
                        operation_type,
                        currency,
                        amount_from,
                        amount_to,
                        amount_basis,
                        date_from,
                        date_to,
                        rate_value,
                        percent_commission_currency,
                        fixed_commission_amount,
                        fixed_commission_currency
                    FROM rate_conditions
                    """,
                    connection,
                )
                client_exceptions = pd.read_sql_query(
                    """
                    SELECT client_name, date_from, date_to
                    FROM client_rate_exceptions
                    """,
                    connection,
                )
            self._cached_deals = prepare_deals_frame(raw, rates, referrals, rate_conditions, client_exceptions)
            self._cached_mtime = mtime
            return self._cached_deals.copy()

    def _referral_meta(self, referral_names: list[str]) -> list[dict[str, Any]]:
        if not referral_names:
            return []
        placeholders = ",".join("?" for _ in referral_names)
        with self._connect_read_only() as connection:
            rows = connection.execute(
                f"""
                SELECT name, code, logo_path, is_active, updated_at
                FROM referrals
                WHERE name IN ({placeholders})
                """,
                referral_names,
            ).fetchall()
        by_name = {str(row[0]): row for row in rows}
        result: list[dict[str, Any]] = []
        for name in referral_names:
            row = by_name.get(name)
            logo_path = str(row[2]) if row and row[2] else _default_referral_logo(name)
            result.append(
                {
                    "name": name,
                    "code": str(row[1]) if row and row[1] else "",
                    "logo_path": logo_path,
                    "logo_url": _asset_url(logo_path),
                    "is_active": bool(row[3]) if row else True,
                    "updated_at": str(row[4]) if row and row[4] else "",
                }
            )
        return sorted(result, key=lambda item: (0 if item.get("logo_url") else 1, str(item["name"]).casefold()))

    def _connect_read_only(self) -> sqlite3.Connection:
        uri = f"file:{self._db_path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        connection.execute("PRAGMA query_only = ON")
        return connection


def _asset_url(path: str | None) -> str | None:
    if not path:
        return None
    normalized = str(path).replace("\\", "/").lstrip("/")
    if normalized.startswith("assets/"):
        normalized = normalized[len("assets/") :]
    return f"/local-assets/{normalized}"


def _default_referral_logo(name: str) -> str | None:
    normalized = str(name or "").casefold().replace("_", " ")
    rules = (
        (("альфа", "alfa", "alpha"), "assets/referrals/alfa_bank.png"),
        (("дом рф", "dom rf"), "assets/referrals/dom_rf.png"),
        (("зенит", "zenit"), "assets/referrals/zenit.png"),
        (("металлинвест", "metallinvest"), "assets/referrals/metallinvestbank.png"),
        (("синара", "sinara"), "assets/referrals/sinara.png"),
        (("тинькофф", "tinkoff"), "assets/referrals/tinkoff.png"),
        (("транзакции", "расчеты", "int-pay", "zhulong"), "assets/referrals/transactions_intpay_zhulong.png"),
        (("уралсиб", "uralsib"), "assets/referrals/uralsib.png"),
    )
    for aliases, path in rules:
        if any(alias in normalized for alias in aliases):
            return path
    return None

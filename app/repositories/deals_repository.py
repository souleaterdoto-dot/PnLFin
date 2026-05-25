"""Repository for deal persistence."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from collections.abc import Callable, Iterable
from dataclasses import asdict
from typing import Any

from app.database.connection import get_connection
from app.domain.enums import DealReviewStatus
from app.domain.models import Deal, utc_now_iso


EXCEL_HEADER_FIELDS = (
    "external_deal_id",
    "manager",
    "is_repeat_payment",
    "request_date",
    "client_fix_date",
    "agent_writeoff_date",
    "client_receive_date",
    "is_refund",
    "agent_refund_date",
    "client_refund_date",
    "payment_status",
    "client_name",
    "receiver_company",
    "receiver_bank_country",
    "deal_amount",
    "deal_currency",
    "client_rate_percent",
    "fixed_commission_amount",
    "fixed_commission_currency",
    "swift_amount",
    "swift_currency",
    "client_fix_rate",
    "usd_rate",
    "client_cross_rate",
    "payment_agent",
    "agent_commission_amount",
    "agent_commission_currency",
    "swift_commission_amount",
    "swift_commission_currency",
    "customer_article_name",
)


class DealsRepository:
    """SQLite-backed repository for deals."""

    _SORT_COLUMNS = {
        "id",
        "trade_date",
        "value_date",
        "operation_type",
        "counterparty",
        "currency_buy",
        "currency_sell",
        "amount_buy",
        "amount_sell",
        "rate_fact",
        "commission",
        "portfolio",
        "external_deal_id",
        "manager",
        "request_date",
        "client_fix_date",
        "payment_status",
        "client_name",
        "review_status",
        "deal_amount",
        "payment_agent",
        "customer_article_name",
        "import_batch_id",
        "source_sheet",
        "source_row_number",
        "created_at",
        "updated_at",
    } | set(EXCEL_HEADER_FIELDS)

    _FILTER_COLUMNS = _SORT_COLUMNS | {"included_in_calc"}

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def add(self, deal: Deal) -> int:
        """Insert a deal and return its new id."""
        with closing(self._connection_factory()) as connection, connection:
            return self._insert(connection, deal)

    def add_many(self, deals: Iterable[Deal]) -> int:
        """Insert multiple deals in one transaction and return inserted count."""
        count = 0
        with closing(self._connection_factory()) as connection, connection:
            for deal in deals:
                self._insert(connection, deal)
                count += 1
        return count

    def list(
        self,
        search: str | None = None,
        portfolio: str | None = None,
        currency: str | None = None,
        referral: str | None = None,
        column_filters: dict[str, list[str]] | None = None,
        column_search_filters: dict[str, str] | None = None,
        included_only: bool = False,
        sort_by: str = "trade_date",
        sort_desc: bool = True,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Deal]:
        """Return deals filtered and sorted for registry screens."""
        where_sql, params = self._build_filter_sql(
            search,
            portfolio,
            currency,
            referral,
            column_filters,
            column_search_filters,
            included_only,
        )
        order_column = sort_by if sort_by in self._SORT_COLUMNS else "trade_date"
        direction = "DESC" if sort_desc else "ASC"
        params.extend([limit, offset])

        query = f"""
            SELECT * FROM deals
            {where_sql}
            ORDER BY {order_column} {direction}, id DESC
            LIMIT ? OFFSET ?
        """
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(query, params).fetchall()
            return [self._row_to_deal(row) for row in rows]

    def get(self, deal_id: int) -> Deal | None:
        """Return one deal by id."""
        with closing(self._connection_factory()) as connection, connection:
            row = connection.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
            return self._row_to_deal(row) if row else None

    def update(self, deal: Deal) -> None:
        """Update an existing deal."""
        if deal.id is None:
            raise ValueError("Cannot update a deal without id")

        now = utc_now_iso()
        values = asdict(deal)
        values["currency_buy"] = deal.currency_buy.upper()
        values["currency_sell"] = deal.currency_sell.upper()
        values["deal_currency"] = deal.deal_currency.upper() if deal.deal_currency else None
        values["fixed_commission_currency"] = (
            deal.fixed_commission_currency.upper() if deal.fixed_commission_currency else None
        )
        values["swift_currency"] = deal.swift_currency.upper() if deal.swift_currency else None
        values["agent_commission_currency"] = (
            deal.agent_commission_currency.upper() if deal.agent_commission_currency else None
        )
        values["swift_commission_currency"] = (
            deal.swift_commission_currency.upper() if deal.swift_commission_currency else None
        )
        values["included_in_calc"] = int(deal.included_in_calc)
        values["is_repeat_payment"] = _optional_bool_to_int(deal.is_repeat_payment)
        values["is_refund"] = _optional_bool_to_int(deal.is_refund)
        values["review_status"] = _normalize_review_status(deal.review_status)
        values["updated_at"] = now
        update_columns = [
            column for column in values.keys() if column not in {"id", "created_at"}
        ]
        assignments = ",\n                    ".join(
            f"{column} = :{column}" for column in update_columns
        )
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                f"""
                UPDATE deals
                SET {assignments}
                WHERE id = :id
                """,
                values,
            )

    def update_review_status(self, deal_id: int, review_status: str | DealReviewStatus | None) -> None:
        """Update only the manual review marker for a deal."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                UPDATE deals
                SET review_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (_normalize_review_status(review_status), utc_now_iso(), deal_id),
            )

    def update_review_status_many(
        self,
        deal_ids: Iterable[int],
        review_status: str | DealReviewStatus | None,
    ) -> int:
        """Update the manual review marker for multiple deals."""
        ids = [int(deal_id) for deal_id in deal_ids]
        if not ids:
            return 0
        placeholders = ", ".join("?" for _ in ids)
        params: list[Any] = [_normalize_review_status(review_status), utc_now_iso(), *ids]
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                f"""
                UPDATE deals
                SET review_status = ?, updated_at = ?
                WHERE id IN ({placeholders})
                """,
                params,
            )
            return int(cursor.rowcount or 0)

    def delete(self, deal_id: int) -> None:
        """Delete one deal by id."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute("DELETE FROM deals WHERE id = ?", (deal_id,))

    def delete_all(self) -> int:
        """Delete all deals and return the number of deleted rows."""
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute("DELETE FROM deals")
            return int(cursor.rowcount or 0)

    def count(
        self,
        search: str | None = None,
        portfolio: str | None = None,
        currency: str | None = None,
        referral: str | None = None,
        column_filters: dict[str, list[str]] | None = None,
        column_search_filters: dict[str, str] | None = None,
        included_only: bool = False,
    ) -> int:
        """Return total deal count for the current filters."""
        where_sql, params = self._build_filter_sql(
            search,
            portfolio,
            currency,
            referral,
            column_filters,
            column_search_filters,
            included_only,
        )
        with closing(self._connection_factory()) as connection, connection:
            return int(
                connection.execute(
                    f"SELECT COUNT(*) FROM deals {where_sql}",
                    params,
                ).fetchone()[0]
            )

    def distinct_values(self, column: str, search: str | None = None, limit: int | None = None) -> list[str]:
        """Return distinct text values for filter controls."""
        if column not in self._FILTER_COLUMNS:
            raise ValueError(f"Unsupported distinct column: {column}")
        params: list[Any] = []
        where = f"{column} IS NOT NULL"
        if search:
            where += f" AND CASEFOLD(CAST({column} AS TEXT)) LIKE ?"
            params.append(f"%{search.strip().casefold()}%")
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT {column}
                FROM deals
                WHERE {where}
                ORDER BY CASEFOLD(CAST({column} AS TEXT)), {column}
                """,
                params,
            ).fetchall()
            values: list[str] = []
            seen: set[str] = set()
            for row in rows:
                if row[0] is None:
                    continue
                text = str(row[0]).strip()
                if not text:
                    continue
                key = text.casefold()
                if key in seen:
                    continue
                seen.add(key)
                values.append(text)
                if limit and len(values) >= limit:
                    break
            return values

    @staticmethod
    def _build_filter_sql(
        search: str | None,
        portfolio: str | None,
        currency: str | None,
        referral: str | None,
        column_filters: dict[str, list[str]] | None,
        column_search_filters: dict[str, str] | None,
        included_only: bool,
    ) -> tuple[str, list[Any]]:
        params: list[Any] = []
        where: list[str] = []

        if search:
            like = f"%{search.strip().casefold()}%"
            where.append(
                """
                (
                    CASEFOLD(counterparty) LIKE ?
                    OR CASEFOLD(portfolio) LIKE ?
                    OR CASEFOLD(comment) LIKE ?
                    OR CASEFOLD(source_file) LIKE ?
                    OR CASEFOLD(source_sheet) LIKE ?
                    OR CASEFOLD(operation_type) LIKE ?
                    OR CASEFOLD(external_deal_id) LIKE ?
                    OR CASEFOLD(manager) LIKE ?
                    OR CASEFOLD(client_name) LIKE ?
                    OR CASEFOLD(payment_status) LIKE ?
                )
                """
            )
            params.extend([like, like, like, like, like, like, like, like, like, like])

        if portfolio:
            where.append("CASEFOLD(portfolio) = ?")
            params.append(portfolio.casefold())

        if currency:
            where.append("(currency_buy = ? OR currency_sell = ?)")
            params.extend([currency.upper(), currency.upper()])

        if referral:
            where.append("CASEFOLD(TRIM(COALESCE(customer_article_name, ''))) = ?")
            params.append(referral.strip().casefold())

        for column, values in (column_filters or {}).items():
            selected = [str(value) for value in values if str(value) != ""]
            if column not in DealsRepository._FILTER_COLUMNS or not selected:
                continue
            placeholders = ", ".join("?" for _ in selected)
            where.append(f"CASEFOLD(CAST({column} AS TEXT)) IN ({placeholders})")
            params.extend(value.casefold() for value in selected)

        for column, value in (column_search_filters or {}).items():
            text = str(value).strip()
            if column not in DealsRepository._FILTER_COLUMNS or not text:
                continue
            where.append(f"CASEFOLD(CAST({column} AS TEXT)) LIKE ?")
            params.append(f"%{text.casefold()}%")

        if included_only:
            where.append("included_in_calc = 1")

        return (f"WHERE {' AND '.join(where)}" if where else ""), params

    def _insert(self, connection: sqlite3.Connection, deal: Deal) -> int:
        values = asdict(deal)
        values.pop("id", None)
        values["currency_buy"] = deal.currency_buy.upper()
        values["currency_sell"] = deal.currency_sell.upper()
        values["included_in_calc"] = int(deal.included_in_calc)
        values["is_repeat_payment"] = _optional_bool_to_int(deal.is_repeat_payment)
        values["is_refund"] = _optional_bool_to_int(deal.is_refund)
        values["review_status"] = _normalize_review_status(deal.review_status)
        cursor = connection.execute(
            """
            INSERT INTO deals (
                trade_date,
                value_date,
                operation_type,
                counterparty,
                currency_buy,
                amount_buy,
                currency_sell,
                amount_sell,
                rate_fact,
                commission,
                portfolio,
                comment,
                external_deal_id,
                manager,
                is_repeat_payment,
                repeat_payment_commission_percent,
                repeat_payment_penalty_usd,
                request_date,
                client_fix_date,
                agent_writeoff_date,
                client_receive_date,
                is_refund,
                agent_refund_date,
                client_refund_date,
                payment_status,
                client_name,
                review_status,
                receiver_company,
                receiver_bank_country,
                deal_amount,
                deal_currency,
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
                pnl_client_percent_fee_usd,
                pnl_fixed_commission_usd,
                pnl_swift_usd,
                pnl_agent_commission_usd,
                pnl_swift_commission_usd,
                pnl_referral_commission_usd,
                source_file,
                source_sheet,
                source_row_number,
                import_batch_id,
                raw_payload_json,
                included_in_calc,
                created_at,
                updated_at
            )
            VALUES (
                :trade_date,
                :value_date,
                :operation_type,
                :counterparty,
                :currency_buy,
                :amount_buy,
                :currency_sell,
                :amount_sell,
                :rate_fact,
                :commission,
                :portfolio,
                :comment,
                :external_deal_id,
                :manager,
                :is_repeat_payment,
                :repeat_payment_commission_percent,
                :repeat_payment_penalty_usd,
                :request_date,
                :client_fix_date,
                :agent_writeoff_date,
                :client_receive_date,
                :is_refund,
                :agent_refund_date,
                :client_refund_date,
                :payment_status,
                :client_name,
                :review_status,
                :receiver_company,
                :receiver_bank_country,
                :deal_amount,
                :deal_currency,
                :client_rate_percent,
                :fixed_commission_amount,
                :fixed_commission_currency,
                :swift_amount,
                :swift_currency,
                :client_fix_rate,
                :usd_rate,
                :client_cross_rate,
                :payment_agent,
                :agent_commission_amount,
                :agent_commission_currency,
                :swift_commission_amount,
                :swift_commission_currency,
                :customer_article_name,
                :pnl_client_percent_fee_usd,
                :pnl_fixed_commission_usd,
                :pnl_swift_usd,
                :pnl_agent_commission_usd,
                :pnl_swift_commission_usd,
                :pnl_referral_commission_usd,
                :source_file,
                :source_sheet,
                :source_row_number,
                :import_batch_id,
                :raw_payload_json,
                :included_in_calc,
                :created_at,
                :updated_at
            )
            """,
            values,
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _row_to_deal(row: sqlite3.Row) -> Deal:
        return Deal(
            id=row["id"],
            trade_date=row["trade_date"],
            value_date=row["value_date"],
            operation_type=row["operation_type"],
            counterparty=row["counterparty"],
            currency_buy=row["currency_buy"],
            amount_buy=float(row["amount_buy"]),
            currency_sell=row["currency_sell"],
            amount_sell=float(row["amount_sell"]),
            rate_fact=float(row["rate_fact"]),
            commission=float(row["commission"] or 0),
            portfolio=row["portfolio"],
            comment=row["comment"],
            external_deal_id=_optional_row_value(row, "external_deal_id"),
            manager=_optional_row_value(row, "manager"),
            is_repeat_payment=_optional_row_bool(row, "is_repeat_payment"),
            repeat_payment_commission_percent=_optional_row_float(row, "repeat_payment_commission_percent"),
            repeat_payment_penalty_usd=_optional_row_float(row, "repeat_payment_penalty_usd"),
            request_date=_optional_row_value(row, "request_date"),
            client_fix_date=_optional_row_value(row, "client_fix_date"),
            agent_writeoff_date=_optional_row_value(row, "agent_writeoff_date"),
            client_receive_date=_optional_row_value(row, "client_receive_date"),
            is_refund=_optional_row_bool(row, "is_refund"),
            agent_refund_date=_optional_row_value(row, "agent_refund_date"),
            client_refund_date=_optional_row_value(row, "client_refund_date"),
            payment_status=_optional_row_value(row, "payment_status"),
            client_name=_optional_row_value(row, "client_name"),
            review_status=_optional_row_value(row, "review_status"),
            receiver_company=_optional_row_value(row, "receiver_company"),
            receiver_bank_country=_optional_row_value(row, "receiver_bank_country"),
            deal_amount=_optional_row_float(row, "deal_amount"),
            deal_currency=_optional_row_value(row, "deal_currency"),
            client_rate_percent=_optional_row_float(row, "client_rate_percent"),
            fixed_commission_amount=_optional_row_float(row, "fixed_commission_amount"),
            fixed_commission_currency=_optional_row_value(row, "fixed_commission_currency"),
            swift_amount=_optional_row_float(row, "swift_amount"),
            swift_currency=_optional_row_value(row, "swift_currency"),
            client_fix_rate=_optional_row_float(row, "client_fix_rate"),
            usd_rate=_optional_row_float(row, "usd_rate"),
            client_cross_rate=_optional_row_float(row, "client_cross_rate"),
            payment_agent=_optional_row_value(row, "payment_agent"),
            agent_commission_amount=_optional_row_float(row, "agent_commission_amount"),
            agent_commission_currency=_optional_row_value(row, "agent_commission_currency"),
            swift_commission_amount=_optional_row_float(row, "swift_commission_amount"),
            swift_commission_currency=_optional_row_value(row, "swift_commission_currency"),
            customer_article_name=_optional_row_value(row, "customer_article_name"),
            pnl_client_percent_fee_usd=_optional_row_float(row, "pnl_client_percent_fee_usd"),
            pnl_fixed_commission_usd=_optional_row_float(row, "pnl_fixed_commission_usd"),
            pnl_swift_usd=_optional_row_float(row, "pnl_swift_usd"),
            pnl_agent_commission_usd=_optional_row_float(row, "pnl_agent_commission_usd"),
            pnl_swift_commission_usd=_optional_row_float(row, "pnl_swift_commission_usd"),
            pnl_referral_commission_usd=_optional_row_float(row, "pnl_referral_commission_usd"),
            source_file=row["source_file"],
            source_sheet=_optional_row_value(row, "source_sheet"),
            source_row_number=_optional_row_value(row, "source_row_number"),
            import_batch_id=_optional_row_value(row, "import_batch_id"),
            raw_payload_json=_optional_row_value(row, "raw_payload_json"),
            included_in_calc=bool(row["included_in_calc"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _optional_row_value(row: sqlite3.Row, key: str) -> Any:
    """Return optional row value for databases created before import metadata."""
    return row[key] if key in row.keys() else None


def _optional_row_float(row: sqlite3.Row, key: str) -> float | None:
    value = _optional_row_value(row, key)
    return float(value) if value is not None else None


def _optional_row_bool(row: sqlite3.Row, key: str) -> bool | None:
    value = _optional_row_value(row, key)
    return bool(value) if value is not None else None


def _optional_bool_to_int(value: bool | None) -> int | None:
    return int(value) if value is not None else None


def _normalize_review_status(value: str | DealReviewStatus | None) -> str | None:
    if value is None:
        return None
    text = str(value.value if isinstance(value, DealReviewStatus) else value).strip()
    if text in {DealReviewStatus.VERIFIED.value, DealReviewStatus.QUESTION.value}:
        return text
    return None

"""SQLite repository for referral rate conditions."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict
from typing import Any

from app.database.connection import get_connection
from app.domain.models import utc_now_iso
from app.domain.rate_models import RateCondition


class RateConditionsRepository:
    """Persistence layer for rate condition cards."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def add(self, condition: RateCondition) -> int:
        """Insert a condition and return its id."""
        values = asdict(condition)
        values.pop("id", None)
        values["is_active"] = int(condition.is_active)
        values["operation_type"] = _blank_to_none(condition.operation_type)
        values["currency"] = _blank_to_none(condition.currency.upper() if condition.currency else None)
        values["region"] = _blank_to_none(condition.region)
        values["amount_basis"] = _normalize_amount_basis(condition.amount_basis)
        values["percent_commission_currency"] = _blank_to_none(
            condition.percent_commission_currency.upper() if condition.percent_commission_currency else None
        )
        values["fixed_commission_currency"] = _blank_to_none(
            condition.fixed_commission_currency.upper() if condition.fixed_commission_currency else None
        )
        values["commission_type"] = _commission_type(condition)
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO rate_conditions (
                    referral_id, is_active, priority, operation_type, currency, amount_from, amount_to, amount_basis,
                    region, date_from, date_to, rate_value, percent_commission_currency,
                    fixed_commission_amount, fixed_commission_currency, commission_type, comment,
                    created_at, updated_at
                )
                VALUES (
                    :referral_id, :is_active, :priority, :operation_type, :currency, :amount_from, :amount_to, :amount_basis,
                    :region, :date_from, :date_to, :rate_value, :percent_commission_currency,
                    :fixed_commission_amount, :fixed_commission_currency, :commission_type, :comment,
                    :created_at, :updated_at
                )
                """,
                values,
            )
            return int(cursor.lastrowid)

    def update(self, condition: RateCondition) -> None:
        """Update an existing condition."""
        if condition.id is None:
            raise ValueError("Cannot update condition without id")
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                UPDATE rate_conditions
                SET referral_id = ?,
                    is_active = ?,
                    priority = ?,
                    operation_type = ?,
                    currency = ?,
                    amount_from = ?,
                    amount_to = ?,
                    amount_basis = ?,
                    region = ?,
                    date_from = ?,
                    date_to = ?,
                    rate_value = ?,
                    percent_commission_currency = ?,
                    fixed_commission_amount = ?,
                    fixed_commission_currency = ?,
                    commission_type = ?,
                    comment = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    condition.referral_id,
                    int(condition.is_active),
                    condition.priority,
                    _blank_to_none(condition.operation_type),
                    _blank_to_none(condition.currency.upper() if condition.currency else None),
                    condition.amount_from,
                    condition.amount_to,
                    _normalize_amount_basis(condition.amount_basis),
                    _blank_to_none(condition.region),
                    _blank_to_none(condition.date_from),
                    _blank_to_none(condition.date_to),
                    condition.rate_value,
                    _blank_to_none(
                        condition.percent_commission_currency.upper()
                        if condition.percent_commission_currency
                        else None
                    ),
                    condition.fixed_commission_amount,
                    _blank_to_none(
                        condition.fixed_commission_currency.upper()
                        if condition.fixed_commission_currency
                        else None
                    ),
                    _commission_type(condition),
                    _blank_to_none(condition.comment),
                    utc_now_iso(),
                    condition.id,
                ),
            )

    def delete(self, condition_id: int) -> None:
        """Delete one condition."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute("DELETE FROM rate_conditions WHERE id = ?", (condition_id,))

    def get(self, condition_id: int) -> RateCondition | None:
        """Return condition by id."""
        with closing(self._connection_factory()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM rate_conditions WHERE id = ?",
                (condition_id,),
            ).fetchone()
            return self._row_to_condition(row) if row else None

    def list(
        self,
        referral_id: int,
        currency: str | None = None,
        region: str | None = None,
        active: bool | None = None,
    ) -> list[RateCondition]:
        """Return conditions for a referral."""
        where = ["referral_id = ?"]
        params: list[Any] = [referral_id]
        if currency:
            where.append("currency = ?")
            params.append(currency.upper())
        if region:
            where.append("region = ?")
            params.append(region)
        if active is not None:
            where.append("is_active = ?")
            params.append(int(active))
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT * FROM rate_conditions
                WHERE {' AND '.join(where)}
                ORDER BY is_active DESC, priority ASC, id ASC
                """,
                params,
            ).fetchall()
            return [self._row_to_condition(row) for row in rows]

    def list_active(self, referral_id: int) -> list[RateCondition]:
        """Return active conditions in engine order."""
        return self.list(referral_id=referral_id, active=True)

    def distinct_values(self, referral_id: int, column: str) -> list[str]:
        """Return distinct condition values for filters."""
        if column not in {"currency", "region", "commission_type"}:
            raise ValueError(f"Unsupported condition column: {column}")
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT {column}
                FROM rate_conditions
                WHERE referral_id = ? AND {column} IS NOT NULL AND TRIM({column}) != ''
                ORDER BY {column}
                """,
                (referral_id,),
            ).fetchall()
            return [str(row[0]) for row in rows if row[0]]

    @staticmethod
    def _row_to_condition(row: sqlite3.Row) -> RateCondition:
        return RateCondition(
            id=row["id"],
            referral_id=int(row["referral_id"]),
            is_active=bool(row["is_active"]),
            priority=int(row["priority"]),
            operation_type=_optional_row_value(row, "operation_type"),
            currency=row["currency"],
            amount_from=float(row["amount_from"]) if row["amount_from"] is not None else None,
            amount_to=float(row["amount_to"]) if row["amount_to"] is not None else None,
            amount_basis=row["amount_basis"] if "amount_basis" in row.keys() else "deal_currency",
            region=row["region"],
            date_from=row["date_from"],
            date_to=row["date_to"],
            rate_value=float(row["rate_value"]),
            percent_commission_currency=_optional_row_value(row, "percent_commission_currency"),
            fixed_commission_amount=_optional_row_float(row, "fixed_commission_amount"),
            fixed_commission_currency=_optional_row_value(row, "fixed_commission_currency"),
            commission_type=row["commission_type"] if "commission_type" in row.keys() else "percent",
            comment=row["comment"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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


def _optional_row_value(row: sqlite3.Row, key: str) -> Any:
    return row[key] if key in row.keys() else None


def _optional_row_float(row: sqlite3.Row, key: str) -> float | None:
    value = _optional_row_value(row, key)
    return float(value) if value is not None else None

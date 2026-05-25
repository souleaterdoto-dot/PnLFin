"""Repository for rate rules used by the rules engine."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import asdict
from typing import Any

from app.database.connection import get_connection
from app.domain.models import RateRule, utc_now_iso


class RulesRepository:
    """SQLite-backed repository for rate rules."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def add(self, rule: RateRule) -> int:
        """Insert one rate rule and return its id."""
        with closing(self._connection_factory()) as connection, connection:
            return self._insert(connection, rule)

    def add_many(self, rules: Iterable[RateRule]) -> int:
        """Insert multiple rules preserving their order_index values."""
        count = 0
        with closing(self._connection_factory()) as connection, connection:
            for rule in rules:
                self._insert(connection, rule)
                count += 1
        return count

    def list(
        self,
        bank_name: str | None = None,
        currency: str | None = None,
        region: str | None = None,
        active: bool | None = None,
        rule_set_name: str | None = None,
        limit: int = 1000,
    ) -> list[RateRule]:
        """Return rules filtered for UI or services."""
        where_sql, params = self._build_filter_sql(
            bank_name=bank_name,
            currency=currency,
            region=region,
            active=active,
            rule_set_name=rule_set_name,
        )
        params.append(limit)
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT * FROM rate_rules
                {where_sql}
                ORDER BY rule_set_name ASC, order_index ASC, id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [self._row_to_rule(row) for row in rows]

    def list_active(self, rule_set_name: str | None = None) -> list[RateRule]:
        """Return active rules ordered exactly as the engine should evaluate them."""
        return self.list(active=True, rule_set_name=rule_set_name, limit=100000)

    def distinct_values(self, column: str) -> list[str]:
        """Return distinct values for filter dropdowns."""
        if column not in {"bank_name", "currency", "region", "rule_set_name"}:
            raise ValueError(f"Unsupported distinct column: {column}")
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT {column}
                FROM rate_rules
                WHERE {column} IS NOT NULL AND {column} != ''
                ORDER BY {column}
                """
            ).fetchall()
            return [str(row[0]) for row in rows if row[0]]

    def update(self, rule: RateRule) -> None:
        """Update an existing rate rule."""
        if rule.id is None:
            raise ValueError("Cannot update a rate rule without id")
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                UPDATE rate_rules
                SET rule_set_name = ?,
                    order_index = ?,
                    bank_name = ?,
                    currency = ?,
                    min_amount = ?,
                    max_amount = ?,
                    region = ?,
                    start_date = ?,
                    end_date = ?,
                    rate = ?,
                    is_active = ?,
                    source_file = ?,
                    source_sheet = ?,
                    source_row_number = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    rule.rule_set_name,
                    rule.order_index,
                    rule.bank_name,
                    rule.currency.upper(),
                    rule.min_amount,
                    rule.max_amount,
                    rule.region,
                    rule.start_date,
                    rule.end_date,
                    rule.rate,
                    int(rule.is_active),
                    rule.source_file,
                    rule.source_sheet,
                    rule.source_row_number,
                    utc_now_iso(),
                    rule.id,
                ),
            )

    def delete(self, rule_id: int) -> None:
        """Delete one rate rule by id."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute("DELETE FROM rate_rules WHERE id = ?", (rule_id,))

    def clear_rule_set(self, rule_set_name: str) -> None:
        """Delete all rules from a named set."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute("DELETE FROM rate_rules WHERE rule_set_name = ?", (rule_set_name,))

    def _insert(self, connection: sqlite3.Connection, rule: RateRule) -> int:
        values = asdict(rule)
        values.pop("id", None)
        values["currency"] = rule.currency.upper()
        values["is_active"] = int(rule.is_active)
        cursor = connection.execute(
            """
            INSERT INTO rate_rules (
                rule_set_name,
                order_index,
                bank_name,
                currency,
                min_amount,
                max_amount,
                region,
                start_date,
                end_date,
                rate,
                is_active,
                source_file,
                source_sheet,
                source_row_number,
                created_at,
                updated_at
            )
            VALUES (
                :rule_set_name,
                :order_index,
                :bank_name,
                :currency,
                :min_amount,
                :max_amount,
                :region,
                :start_date,
                :end_date,
                :rate,
                :is_active,
                :source_file,
                :source_sheet,
                :source_row_number,
                :created_at,
                :updated_at
            )
            """,
            values,
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _build_filter_sql(
        bank_name: str | None,
        currency: str | None,
        region: str | None,
        active: bool | None,
        rule_set_name: str | None,
    ) -> tuple[str, list[Any]]:
        where: list[str] = []
        params: list[Any] = []
        if bank_name:
            where.append("bank_name = ?")
            params.append(bank_name)
        if currency:
            where.append("currency = ?")
            params.append(currency.upper())
        if region:
            where.append("region = ?")
            params.append(region)
        if active is not None:
            where.append("is_active = ?")
            params.append(int(active))
        if rule_set_name:
            where.append("rule_set_name = ?")
            params.append(rule_set_name)
        return (f"WHERE {' AND '.join(where)}" if where else ""), params

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> RateRule:
        return RateRule(
            id=row["id"],
            rule_set_name=row["rule_set_name"],
            order_index=int(row["order_index"]),
            bank_name=row["bank_name"],
            currency=row["currency"],
            min_amount=float(row["min_amount"]),
            max_amount=float(row["max_amount"]) if row["max_amount"] is not None else None,
            region=row["region"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            rate=float(row["rate"]),
            is_active=bool(row["is_active"]),
            source_file=row["source_file"],
            source_sheet=row["source_sheet"],
            source_row_number=row["source_row_number"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

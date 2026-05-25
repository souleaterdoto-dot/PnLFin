"""Repository for currency rate persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict

from app.database.connection import get_connection
from app.domain.enums import RateSource
from app.domain.models import Rate


def normalize_rate_currency(currency: str) -> str:
    """Normalize currency aliases used by business data."""
    normalized = str(currency or "").strip().upper()
    aliases = {
        "CNY": "CNH",
    }
    return aliases.get(normalized, normalized)


class RatesRepository:
    """SQLite-backed repository for exchange rates."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def upsert(self, rate: Rate) -> int:
        """Insert or replace a rate for date, currency and source."""
        values = asdict(rate)
        values.pop("id", None)
        values["currency"] = normalize_rate_currency(rate.currency)
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO rates (rate_date, currency, rate_to_rub, source, created_at)
                VALUES (:rate_date, :currency, :rate_to_rub, :source, :created_at)
                ON CONFLICT(rate_date, currency, source)
                DO UPDATE SET rate_to_rub = excluded.rate_to_rub
                """,
                values,
            )
            return int(cursor.lastrowid or 0)

    def list(self, currency: str | None = None, limit: int = 500) -> list[Rate]:
        """Return rates ordered by date descending."""
        params: list[object] = []
        where = ""
        if currency:
            where = "WHERE currency = ?"
            params.append(normalize_rate_currency(currency))
        params.append(limit)
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT * FROM rates
                {where}
                ORDER BY rate_date DESC, currency ASC, source DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [self._row_to_rate(row) for row in rows]

    def counts_by_date(self) -> dict[str, int]:
        """Return number of rates grouped by date."""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                """
                SELECT rate_date, COUNT(*) AS rates_count
                FROM rates
                GROUP BY rate_date
                """
            ).fetchall()
            return {str(row["rate_date"]): int(row["rates_count"]) for row in rows}

    def list_by_date(self, rate_date: str) -> list[Rate]:
        """Return all rates for one date ordered by currency and source."""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                """
                SELECT * FROM rates
                WHERE rate_date = ?
                ORDER BY currency ASC, source DESC
                """,
                (rate_date,),
            ).fetchall()
            return [self._row_to_rate(row) for row in rows]

    def find_preferred(self, rate_date: str, currency: str) -> Rate | None:
        """Return manual rate first, otherwise CBR rate for the same date."""
        currency = normalize_rate_currency(currency)
        if currency == "RUB":
            return Rate(rate_date=rate_date, currency="RUB", rate_to_rub=1.0)
        with closing(self._connection_factory()) as connection, connection:
            row = connection.execute(
                """
                SELECT * FROM rates
                WHERE rate_date = ? AND currency = ?
                ORDER BY CASE source WHEN ? THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (rate_date, currency, RateSource.MANUAL.value),
            ).fetchone()
            return self._row_to_rate(row) if row else None

    def find_latest_on_or_before(self, rate_date: str, currency: str) -> Rate | None:
        """Return the latest available preferred rate not later than the date."""
        currency = normalize_rate_currency(currency)
        if currency == "RUB":
            return Rate(rate_date=rate_date, currency="RUB", rate_to_rub=1.0)
        with closing(self._connection_factory()) as connection, connection:
            row = connection.execute(
                """
                SELECT * FROM rates
                WHERE rate_date <= ? AND currency = ?
                ORDER BY rate_date DESC,
                    CASE source WHEN ? THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (rate_date, currency, RateSource.MANUAL.value),
            ).fetchone()
            return self._row_to_rate(row) if row else None

    def update(self, rate: Rate) -> None:
        """Update an existing rate by id."""
        if rate.id is None:
            raise ValueError("Cannot update a rate without id")
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                UPDATE rates
                SET rate_date = ?, currency = ?, rate_to_rub = ?, source = ?
                WHERE id = ?
                """,
                (
                    rate.rate_date,
                    normalize_rate_currency(rate.currency),
                    rate.rate_to_rub,
                    rate.source,
                    rate.id,
                ),
            )

    def normalize_currency_aliases(self) -> None:
        """Merge legacy CNY rates into CNH and remove the old alias."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                INSERT INTO rates (rate_date, currency, rate_to_rub, source, created_at)
                SELECT rate_date, 'CNH', rate_to_rub, source, created_at
                FROM rates
                WHERE currency = 'CNY'
                ON CONFLICT(rate_date, currency, source)
                DO UPDATE SET rate_to_rub = excluded.rate_to_rub
                """
            )
            connection.execute("DELETE FROM rates WHERE currency = 'CNY'")

    def delete(self, rate_id: int) -> None:
        """Delete one rate by id."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute("DELETE FROM rates WHERE id = ?", (rate_id,))

    @staticmethod
    def _row_to_rate(row: sqlite3.Row) -> Rate:
        return Rate(
            id=row["id"],
            rate_date=row["rate_date"],
            currency=row["currency"],
            rate_to_rub=float(row["rate_to_rub"]),
            source=row["source"],
            created_at=row["created_at"],
        )

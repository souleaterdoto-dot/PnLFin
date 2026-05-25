"""SQLite repository for client-specific referral rate exceptions."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import asdict

from app.database.connection import get_connection
from app.domain.models import utc_now_iso
from app.domain.rate_models import ClientRateException


class ClientRateExceptionsRepository:
    """Persistence layer for client exception rows."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def list(self) -> list[ClientRateException]:
        """Return all configured client exceptions."""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                """
                SELECT *
                FROM client_rate_exceptions
                ORDER BY CASEFOLD(client_name)
                """
            ).fetchall()
            return [self._row_to_exception(row) for row in rows]

    def get_by_client_names(self, client_names: Iterable[str]) -> dict[str, ClientRateException]:
        """Return exceptions keyed by casefolded client name."""
        names = [str(name or "").strip() for name in client_names if str(name or "").strip()]
        if not names:
            return {}
        placeholders = ",".join("?" for _ in names)
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM client_rate_exceptions
                WHERE CASEFOLD(client_name) IN ({placeholders})
                """,
                [name.casefold() for name in names],
            ).fetchall()
            return {row["client_name"].casefold(): self._row_to_exception(row) for row in rows}

    def find_active(self, client_name: str | None, deal_date: str | None) -> ClientRateException | None:
        """Return matching exception when the client and date are inside the configured range."""
        clean_name = str(client_name or "").strip()
        clean_date = str(deal_date or "").strip()
        if not clean_name or not clean_date:
            return None
        with closing(self._connection_factory()) as connection, connection:
            row = connection.execute(
                """
                SELECT *
                FROM client_rate_exceptions
                WHERE CASEFOLD(client_name) = ?
                  AND date_from <= ?
                  AND (date_to IS NULL OR date_to = '' OR date_to >= ?)
                LIMIT 1
                """,
                (clean_name.casefold(), clean_date, clean_date),
            ).fetchone()
            return self._row_to_exception(row) if row else None

    def save(self, exception: ClientRateException) -> int:
        """Create or update one client exception by client name."""
        values = asdict(exception)
        values.pop("id", None)
        values["updated_at"] = utc_now_iso()
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO client_rate_exceptions (
                    client_name, note, date_from, date_to, created_at, updated_at
                )
                VALUES (
                    :client_name, :note, :date_from, :date_to, :created_at, :updated_at
                )
                ON CONFLICT(client_name) DO UPDATE SET
                    note = excluded.note,
                    date_from = excluded.date_from,
                    date_to = excluded.date_to,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            return int(cursor.lastrowid or 0)

    def delete_by_client_name(self, client_name: str) -> None:
        """Delete an exception row for a client."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                "DELETE FROM client_rate_exceptions WHERE CASEFOLD(client_name) = ?",
                (str(client_name or "").strip().casefold(),),
            )

    def _row_to_exception(self, row: sqlite3.Row) -> ClientRateException:
        return ClientRateException(
            id=row["id"],
            client_name=row["client_name"],
            note=row["note"],
            date_from=row["date_from"],
            date_to=row["date_to"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

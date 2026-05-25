"""SQLite repository for referrals."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict
from typing import Any

from app.database.connection import get_connection
from app.domain.models import utc_now_iso
from app.domain.rate_models import Referral


class ReferralsRepository:
    """Persistence layer for referral cards."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def add(self, referral: Referral) -> int:
        """Insert a referral and return its id."""
        values = asdict(referral)
        values.pop("id", None)
        values.pop("active_conditions_count", None)
        values["is_active"] = int(referral.is_active)
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO referrals (
                    name, code, description, logo_path, is_active, created_at, updated_at
                )
                VALUES (
                    :name, :code, :description, :logo_path, :is_active, :created_at, :updated_at
                )
                """,
                values,
            )
            return int(cursor.lastrowid)

    def update(self, referral: Referral) -> None:
        """Update an existing referral."""
        if referral.id is None:
            raise ValueError("Cannot update referral without id")
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                UPDATE referrals
                SET name = ?,
                    code = ?,
                    description = ?,
                    logo_path = ?,
                    is_active = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    referral.name,
                    referral.code,
                    referral.description,
                    referral.logo_path,
                    int(referral.is_active),
                    utc_now_iso(),
                    referral.id,
                ),
            )

    def delete(self, referral_id: int) -> None:
        """Delete a referral and its rate conditions via cascade."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute("DELETE FROM referrals WHERE id = ?", (referral_id,))

    def get(self, referral_id: int) -> Referral | None:
        """Return referral by id."""
        with closing(self._connection_factory()) as connection, connection:
            row = connection.execute(
                """
                SELECT r.*,
                       COALESCE(SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END), 0)
                           AS active_conditions_count
                FROM referrals r
                LEFT JOIN rate_conditions c ON c.referral_id = r.id
                WHERE r.id = ?
                GROUP BY r.id
                """,
                (referral_id,),
            ).fetchone()
            return self._row_to_referral(row) if row else None

    def find_by_name_or_code(self, value: str) -> Referral | None:
        """Find referral by case-insensitive name or code."""
        text = str(value or "").strip()
        if not text:
            return None
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                """
                SELECT r.*,
                       COALESCE(SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END), 0)
                           AS active_conditions_count
                FROM referrals r
                LEFT JOIN rate_conditions c ON c.referral_id = r.id
                GROUP BY r.id
                """,
            ).fetchall()
            lookup = text.casefold()
            for row in rows:
                if str(row["name"]).casefold() == lookup or str(row["code"]).casefold() == lookup:
                    return self._row_to_referral(row)
            return None

    def list(self, search: str | None = None, active: bool | None = None) -> list[Referral]:
        """Return referrals with active condition counts."""
        where: list[str] = []
        params: list[Any] = []
        if search:
            where.append("(r.name LIKE ? OR r.code LIKE ?)")
            pattern = f"%{search.strip()}%"
            params.extend([pattern, pattern])
        if active is not None:
            where.append("r.is_active = ?")
            params.append(int(active))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT r.*,
                       COALESCE(SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END), 0)
                           AS active_conditions_count
                FROM referrals r
                LEFT JOIN rate_conditions c ON c.referral_id = r.id
                {where_sql}
                GROUP BY r.id
                ORDER BY
                    r.is_active DESC,
                    CASE WHEN COALESCE(r.logo_path, '') != '' THEN 0 ELSE 1 END ASC,
                    LOWER(r.name) ASC
                """,
                params,
            ).fetchall()
            return [self._row_to_referral(row) for row in rows]

    def ensure_defaults(self, names: list[str]) -> None:
        """Create default referral cards when they do not exist."""
        self.ensure_names(names)

    def ensure_names(self, names: list[str]) -> None:
        """Create referral records for the provided names when missing."""
        with closing(self._connection_factory()) as connection, connection:
            for name in names:
                clean_name = str(name or "").strip()
                if not clean_name:
                    continue
                code = _code_from_name(clean_name)
                exists = connection.execute(
                    "SELECT 1 FROM referrals WHERE code = ? OR name = ?",
                    (code, clean_name),
                ).fetchone()
                if exists:
                    continue
                now = utc_now_iso()
                connection.execute(
                    """
                    INSERT INTO referrals (name, code, is_active, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                    """,
                    (clean_name, code, now, now),
                )

    def ignore_sync_name(self, name: str) -> None:
        """Prevent a deal-derived referral name from being recreated automatically."""
        clean_name = str(name or "").strip()
        if not clean_name:
            return
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                INSERT INTO referral_sync_ignored (name_key, display_name)
                VALUES (?, ?)
                ON CONFLICT(name_key) DO UPDATE SET
                    display_name = excluded.display_name,
                    deleted_at = CURRENT_TIMESTAMP
                """,
                (_name_key(clean_name), clean_name),
            )

    def unignore_sync_name(self, name: str) -> None:
        """Allow a manually created referral name to sync again."""
        clean_name = str(name or "").strip()
        if not clean_name:
            return
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                "DELETE FROM referral_sync_ignored WHERE name_key = ?",
                (_name_key(clean_name),),
            )

    def ignored_sync_name_keys(self) -> set[str]:
        """Return names that should not be recreated from deals."""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute("SELECT name_key FROM referral_sync_ignored").fetchall()
            return {str(row["name_key"]) for row in rows}

    def delete_empty_codes(self, codes: set[str]) -> int:
        """Delete placeholder referrals that have no conditions or custom data."""
        if not codes:
            return 0
        placeholders = ",".join("?" for _ in codes)
        params = list(codes)
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                f"""
                DELETE FROM referrals
                WHERE code IN ({placeholders})
                  AND COALESCE(description, '') = ''
                  AND COALESCE(logo_path, '') = ''
                  AND NOT EXISTS (
                      SELECT 1 FROM rate_conditions
                      WHERE rate_conditions.referral_id = referrals.id
                  )
                """,
                params,
            )
            return int(cursor.rowcount or 0)

    @staticmethod
    def _row_to_referral(row: sqlite3.Row) -> Referral:
        return Referral(
            id=row["id"],
            name=row["name"],
            code=row["code"],
            description=row["description"],
            logo_path=row["logo_path"],
            is_active=bool(row["is_active"]),
            active_conditions_count=int(row["active_conditions_count"] or 0)
            if "active_conditions_count" in row.keys()
            else 0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _code_from_name(name: str) -> str:
    mapping = {
        "\u0410\u043b\u044c\u0444\u0430 \u0431\u0430\u043d\u043a": "alfa",
        "\u0412\u0422\u0411": "vtb",
        "\u0422\u0438\u043d\u044c\u043a\u043e\u0444\u0444": "tinkoff",
        "\u0421\u0431\u0435\u0440": "sber",
        "\u0413\u0430\u0437\u043f\u0440\u043e\u043c\u0431\u0430\u043d\u043a": "gazprombank",
        "\u0414\u0440\u0443\u0433\u0438\u0435 \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u044b": "other",
    }
    return mapping.get(name, _generic_code_from_name(name))


def _name_key(name: str) -> str:
    return str(name or "").strip().casefold()


def _generic_code_from_name(name: str) -> str:
    code = "_".join(str(name).strip().casefold().split())
    allowed = []
    for char in code:
        if char.isalnum() or char == "_":
            allowed.append(char)
    return "".join(allowed) or "referral"

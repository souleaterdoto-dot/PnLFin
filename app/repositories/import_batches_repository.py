"""Repository for Excel import batches and validation errors."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from typing import Any

from app.database.connection import get_connection
from app.domain.import_models import ImportBatch, ImportErrorRecord


class ImportBatchesRepository:
    """SQLite-backed repository for import batch metadata and row errors."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection] = get_connection,
    ) -> None:
        self._connection_factory = connection_factory

    def create(self, batch: ImportBatch) -> int:
        """Create a new import batch and return its id."""
        with closing(self._connection_factory()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO import_batches (
                    source_file,
                    source_sheet,
                    imported_at,
                    rows_total,
                    rows_success,
                    rows_failed,
                    status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.source_file,
                    batch.source_sheet,
                    batch.imported_at,
                    batch.rows_total,
                    batch.rows_success,
                    batch.rows_failed,
                    batch.status,
                    batch.error_message,
                ),
            )
            return int(cursor.lastrowid)

    def update_status(
        self,
        batch_id: int,
        rows_total: int,
        rows_success: int,
        rows_failed: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update counters and terminal status for a batch."""
        with closing(self._connection_factory()) as connection, connection:
            connection.execute(
                """
                UPDATE import_batches
                SET rows_total = ?,
                    rows_success = ?,
                    rows_failed = ?,
                    status = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (rows_total, rows_success, rows_failed, status, error_message, batch_id),
            )

    def add_errors(self, errors: Iterable[ImportErrorRecord]) -> int:
        """Persist row validation errors and return inserted count."""
        count = 0
        with closing(self._connection_factory()) as connection, connection:
            for error in errors:
                connection.execute(
                    """
                    INSERT INTO import_errors (
                        import_batch_id,
                        source_row_number,
                        field_name,
                        error_message,
                        raw_value,
                        raw_payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        error.import_batch_id,
                        error.source_row_number,
                        error.field_name,
                        error.error_message,
                        _json_value(error.raw_value),
                        error.raw_payload_json,
                        error.created_at,
                    ),
                )
                count += 1
        return count

    def list_errors(self, batch_id: int, limit: int = 500) -> list[ImportErrorRecord]:
        """Return persisted errors for a batch."""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                """
                SELECT * FROM import_errors
                WHERE import_batch_id = ?
                ORDER BY source_row_number ASC, id ASC
                LIMIT ?
                """,
                (batch_id, limit),
            ).fetchall()
            return [self._row_to_error(row) for row in rows]

    def list_recent(self, limit: int = 50) -> list[ImportBatch]:
        """Return recent import batches."""
        with closing(self._connection_factory()) as connection, connection:
            rows = connection.execute(
                """
                SELECT * FROM import_batches
                ORDER BY imported_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_batch(row) for row in rows]

    @staticmethod
    def _row_to_batch(row: sqlite3.Row) -> ImportBatch:
        return ImportBatch(
            id=row["id"],
            source_file=row["source_file"],
            source_sheet=row["source_sheet"],
            imported_at=row["imported_at"],
            rows_total=int(row["rows_total"]),
            rows_success=int(row["rows_success"]),
            rows_failed=int(row["rows_failed"]),
            status=row["status"],
            error_message=row["error_message"],
        )

    @staticmethod
    def _row_to_error(row: sqlite3.Row) -> ImportErrorRecord:
        return ImportErrorRecord(
            id=row["id"],
            import_batch_id=row["import_batch_id"],
            source_row_number=row["source_row_number"],
            field_name=row["field_name"],
            error_message=row["error_message"],
            raw_value=row["raw_value"],
            raw_payload_json=row["raw_payload_json"],
            created_at=row["created_at"],
        )


def _json_value(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)

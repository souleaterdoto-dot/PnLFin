"""SQLite connection helpers for local application storage."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from app.database.schema import create_schema


APP_DATA_DIR = Path.cwd() / "FinancePnL_Data"
DEFAULT_DB_PATH = APP_DATA_DIR / "app.sqlite3"


def ensure_database_directory() -> Path:
    """Create and return the local data directory."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DATA_DIR


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection configured for repository usage."""
    ensure_database_directory()
    connection = sqlite3.connect(db_path or DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.create_function("CASEFOLD", 1, _sqlite_casefold)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _sqlite_casefold(value: object) -> str:
    """Unicode-aware lowercase normalization for SQLite filters."""
    if value is None:
        return ""
    return str(value).casefold()


@contextmanager
def connection_scope(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a connection and commit or rollback around repository operations."""
    connection = get_connection(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: Path | None = None) -> Path:
    """Create the database file and all required tables if they do not exist."""
    target_path = db_path or DEFAULT_DB_PATH
    ensure_database_directory()
    with closing(get_connection(target_path)) as connection, connection:
        create_schema(connection)
    return target_path

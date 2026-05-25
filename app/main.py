"""Application bootstrap."""

from __future__ import annotations

from app.database.connection import APP_DATA_DIR, DEFAULT_DB_PATH, initialize_database
from app.database.lock import DatabaseLockError, acquire_database_lock
from app.ui.app_shell import run_app, run_lock_error_app


def main() -> None:
    """Initialize local storage and start the Flet desktop app."""
    try:
        database_lock = acquire_database_lock(APP_DATA_DIR, DEFAULT_DB_PATH)
    except DatabaseLockError as exc:
        run_lock_error_app(exc)
        return

    try:
        initialize_database()
        run_app()
    finally:
        database_lock.release()


if __name__ == "__main__":
    main()

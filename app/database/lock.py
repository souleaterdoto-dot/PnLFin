"""Process-level database lock for single-user desktop mode."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import BinaryIO

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


LOCK_FILE_NAME = "app.sqlite3.lock"


class DatabaseLockError(RuntimeError):
    """Raised when another running process already owns the database lock."""

    def __init__(self, lock_path: Path, owner_info: str | None = None) -> None:
        self.lock_path = lock_path
        self.owner_info = owner_info
        message = "База данных уже открыта в другом экземпляре приложения."
        if owner_info:
            message = f"{message}\n\n{owner_info}"
        super().__init__(message)


@dataclass(slots=True)
class DatabaseLock:
    """Held lock handle. Keep this object alive while the app is running."""

    path: Path
    _handle: BinaryIO
    _released: bool = False

    def release(self) -> None:
        """Release the process lock and close the lock file handle."""
        if self._released:
            return
        self._released = True
        try:
            self._handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()


def acquire_database_lock(data_dir: Path, db_path: Path) -> DatabaseLock:
    """Acquire an exclusive app-level lock for the SQLite database."""
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / LOCK_FILE_NAME
    handle = lock_path.open("a+b")
    try:
        _try_lock(handle)
    except OSError as exc:
        handle.close()
        raise DatabaseLockError(lock_path, _read_owner_info(lock_path)) from exc

    lock = DatabaseLock(lock_path, handle)
    _write_owner_info(handle, db_path)
    atexit.register(lock.release)
    return lock


def _try_lock(handle: BinaryIO) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _write_owner_info(handle: BinaryIO, db_path: Path) -> None:
    payload = {
        "pid": os.getpid(),
        "db_path": str(db_path),
        "locked_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handle.seek(0)
    handle.truncate()
    handle.write(b"\0")
    handle.write(data)
    handle.flush()


def _read_owner_info(lock_path: Path) -> str | None:
    try:
        with lock_path.open("rb") as handle:
            handle.seek(1)
            raw = handle.read().decode("utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    pid = payload.get("pid")
    locked_at = payload.get("locked_at")
    db_path = payload.get("db_path")
    parts = []
    if pid:
        parts.append(f"PID: {pid}")
    if locked_at:
        parts.append(f"Открыто: {locked_at}")
    if db_path:
        parts.append(f"База: {db_path}")
    return "\n".join(parts) or None

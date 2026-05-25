"""Application-wide active operation tracking."""

from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from threading import RLock
from collections.abc import Callable
from typing import Any, Iterator


class OperationTracker:
    """Track long-running UI operations that should finish before app exit."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._active = 0

    @contextmanager
    def track(self) -> Iterator[None]:
        """Increment active operation count for the duration of a sync block."""
        self.start()
        try:
            yield
        finally:
            self.finish()

    def start(self) -> None:
        """Mark one operation as active."""
        with self._lock:
            self._active += 1

    def finish(self) -> None:
        """Mark one operation as finished."""
        with self._lock:
            self._active = max(0, self._active - 1)

    @property
    def active_count(self) -> int:
        """Return current active operation count."""
        with self._lock:
            return self._active

    async def wait_idle(self, min_visible_seconds: float = 0.45, max_wait_seconds: float = 5.0) -> None:
        """Wait until all tracked operations are done."""
        started_at = time.monotonic()
        while self.active_count > 0 and time.monotonic() - started_at < max_wait_seconds:
            await asyncio.sleep(0.1)
        remaining = min_visible_seconds - (time.monotonic() - started_at)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def wrap_connection_factory(self, factory: Callable[[], Any]) -> Callable[[], "_TrackedConnection"]:
        """Wrap a SQLite connection factory so DB work is counted as active."""
        def create_connection() -> _TrackedConnection:
            self.start()
            try:
                return _TrackedConnection(factory(), self)
            except Exception:
                self.finish()
                raise

        return create_connection


class _TrackedConnection:
    """Lightweight proxy that decrements active operation count on close."""

    def __init__(self, connection: Any, tracker: OperationTracker) -> None:
        self._connection = connection
        self._tracker = tracker
        self._closed = False

    def __enter__(self) -> "_TrackedConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback) -> Any:
        try:
            return self._connection.__exit__(exc_type, exc, traceback)
        finally:
            self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def close(self) -> None:
        try:
            self._connection.close()
        finally:
            if not self._closed:
                self._closed = True
                self._tracker.finish()

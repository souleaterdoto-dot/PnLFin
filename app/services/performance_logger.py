"""Lightweight local performance logging."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import threading
import time
from typing import Any, Iterator

from app.database.connection import APP_DATA_DIR, ensure_database_directory


LOG_FILE_NAME = "performance.log"
MAX_LOG_BYTES = 5 * 1024 * 1024

_LOCK = threading.Lock()


def performance_log_path() -> Path:
    """Return the performance log path stored near the SQLite database."""
    ensure_database_directory()
    return APP_DATA_DIR / LOG_FILE_NAME


@contextmanager
def perf_span(event: str, **details: Any) -> Iterator[None]:
    """Measure a code block and append its duration to the local performance log."""
    started = time.perf_counter()
    error: str | None = None
    try:
        yield
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        if error:
            details = {**details, "error": error}
        log_perf_event(event, duration_ms, details)


@contextmanager
def perf_span_if_slow(event: str, threshold_ms: float = 10.0, **details: Any) -> Iterator[None]:
    """Measure a code block and log only if it exceeds the threshold."""
    started = time.perf_counter()
    error: str | None = None
    try:
        yield
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        if error or duration_ms >= threshold_ms:
            if error:
                details = {**details, "error": error}
            log_perf_event(event, duration_ms, details)


def log_perf_event(event: str, duration_ms: float | None = None, details: dict[str, Any] | None = None) -> None:
    """Append one JSON line to the performance log."""
    payload = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "event": event,
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
        "details": details or {},
    }
    try:
        path = performance_log_path()
        with _LOCK:
            _rotate_if_needed(path)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Performance logging must never affect the application workflow.
        return


def _rotate_if_needed(path: Path) -> None:
    if not path.exists() or path.stat().st_size < MAX_LOG_BYTES:
        return
    rotated = path.with_suffix(".log.1")
    if rotated.exists():
        rotated.unlink()
    path.replace(rotated)

"""Helpers for loading bundled UI assets in source and PyInstaller builds."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sys


@lru_cache(maxsize=128)
def image_source(path: str | None) -> str | bytes | None:
    """Return image bytes for bundled assets or the original path as fallback."""
    if not path:
        return None
    resolved = _resolve_asset_path(path)
    if resolved and resolved.exists():
        return resolved.read_bytes()
    return path


def _resolve_asset_path(path: str) -> Path | None:
    normalized = path.replace("\\", "/").lstrip("/")
    raw_path = Path(path)
    if raw_path.is_absolute():
        return raw_path

    root = _app_root()
    candidates = [root / normalized]
    if not normalized.startswith("assets/"):
        candidates.append(root / "assets" / normalized)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _app_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]

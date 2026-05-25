"""Formatting helpers for the deals registry UI."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _blank(value: Any) -> str:
    """Return a display-safe value for empty table cells."""
    if value is None or value == "":
        return "-"
    return str(value)


def _format_number(value: float | int | None, decimals: int) -> str:
    """Format numbers with spaces as thousand separators and comma decimals."""
    if value is None:
        return "-"
    formatted = f"{float(value):,.{decimals}f}"
    return formatted.replace(",", " ").replace(".", ",")


def _format_percent(value: float | int | None, decimals: int = 2) -> str:
    """Format percentage values with a percent sign."""
    if value is None:
        return "-"
    numeric = float(value)
    display_value = numeric * 100 if abs(numeric) <= 1 else numeric
    return f"{_format_number(display_value, decimals)}%"


def _format_date(value: str | None) -> str:
    """Format stored date values for table output."""
    return _format_short_date(value)


def _format_short_date(value: str | None) -> str:
    """Format date as dd.mm.yy for compact UI cells."""
    if not value:
        return "-"
    parsed = _parse_optional_date(value)
    if not parsed:
        return "-"
    try:
        return datetime.strptime(parsed, "%Y-%m-%d").strftime("%d.%m.%y")
    except ValueError:
        return value


def _format_bool(value: bool | None) -> str:
    """Format boolean values for Russian UI."""
    return "Да" if bool(value) else "Нет"


def _parse_optional_date(value: str) -> str | None:
    """Parse common user-facing date formats into ISO date string."""
    value = (value or "").strip()
    if not value or value == "-":
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value

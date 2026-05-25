"""Domain enums used across services and repositories."""

from __future__ import annotations

from enum import StrEnum


class OperationType(StrEnum):
    """Supported deal operation types."""

    FX_SPOT = "FX_SPOT"
    FX_FORWARD = "FX_FORWARD"
    BUY = "BUY"
    SELL = "SELL"
    CONVERSION = "CONVERSION"


class RateSource(StrEnum):
    """Supported exchange rate sources."""

    CBR = "CBR"
    MANUAL = "manual"


class DealReviewStatus(StrEnum):
    """Manual visual review marker for a deal row."""

    VERIFIED = "verified"
    QUESTION = "question"

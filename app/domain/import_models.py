"""Domain models for Excel import batches and row-level errors."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import ValidationError, utc_now_iso


@dataclass(frozen=True, slots=True)
class ExcelSource:
    """Resolved Excel source containing already calculated tabular data."""

    source_file: str
    source_sheet: str
    source_type: str
    table_name: str | None = None
    cell_range: str | None = None
    available_sheets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExcelRow:
    """One row read from Excel with original and normalized payloads."""

    source_row_number: int
    raw_payload: dict[str, object]
    normalized_payload: dict[str, object]


@dataclass(slots=True)
class ImportBatch:
    """Persistent import batch metadata."""

    source_file: str
    source_sheet: str
    rows_total: int = 0
    rows_success: int = 0
    rows_failed: int = 0
    status: str = "running"
    error_message: str | None = None
    id: int | None = None
    imported_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class ImportErrorRecord:
    """Persistent validation error tied to an import batch and source row."""

    import_batch_id: int
    source_row_number: int
    field_name: str
    error_message: str
    raw_value: object | None = None
    raw_payload_json: str | None = None
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class ImportResult:
    """Result shown in UI after an Excel import attempt."""

    import_batch_id: int | None
    source_file: str
    source_sheet: str | None
    rows_total: int
    rows_success: int
    rows_failed: int
    status: str
    errors: list[ValidationError]
    error_message: str | None = None
    available_sheets: list[str] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        """Backward-compatible successful row count."""
        return self.rows_success

    @property
    def skipped_count(self) -> int:
        """Backward-compatible failed or skipped row count."""
        return self.rows_failed

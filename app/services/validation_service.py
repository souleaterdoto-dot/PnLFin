"""Validation and conversion logic for imported deals."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.domain.models import Deal, ValidationError


SUPPORTED_EXTENDED_CURRENCIES = {"USDT"}


class ValidationService:
    """Validate incoming tabular rows and convert them to domain objects."""

    REQUIRED_COLUMNS = {
        "trade_date",
        "value_date",
        "operation_type",
        "counterparty",
        "currency_buy",
        "amount_buy",
        "currency_sell",
        "amount_sell",
        "rate_fact",
        "portfolio",
    }

    OPTIONAL_COLUMNS = {
        "commission",
        "comment",
        "source_file",
        "included_in_calc",
    }

    COLUMN_ALIASES = {
        "trade date": "trade_date",
        "value date": "value_date",
        "operation type": "operation_type",
        "buy currency": "currency_buy",
        "sell currency": "currency_sell",
        "buy amount": "amount_buy",
        "sell amount": "amount_sell",
        "fact rate": "rate_fact",
    }

    def validate_rows(
        self,
        rows: list[dict[str, Any]],
        source_file: str | None = None,
    ) -> tuple[list[Deal], list[ValidationError]]:
        """Validate normalized rows and return valid deals plus row errors."""
        deals: list[Deal] = []
        errors: list[ValidationError] = []

        for index, row in enumerate(rows, start=2):
            deal, row_errors = self.validate_row(row, index, source_file)
            if row_errors:
                errors.extend(row_errors)
            elif deal:
                deals.append(deal)

        return deals, errors

    def validate_row(
        self,
        raw_row: dict[str, Any],
        row_number: int,
        source_file: str | None = None,
    ) -> tuple[Deal | None, list[ValidationError]]:
        """Validate one row and convert it to a Deal if possible."""
        row = self.normalize_keys(raw_row)
        errors: list[ValidationError] = []

        for column in self.REQUIRED_COLUMNS:
            if self._is_empty(row.get(column)):
                errors.append(ValidationError(row_number, column, "Required value is missing"))

        trade_date = self._parse_date(row.get("trade_date"), row_number, "trade_date", errors)
        value_date = self._parse_date(row.get("value_date"), row_number, "value_date", errors)
        amount_buy = self._parse_float(row.get("amount_buy"), row_number, "amount_buy", errors)
        amount_sell = self._parse_float(row.get("amount_sell"), row_number, "amount_sell", errors)
        is_export_amount = amount_buy is not None and amount_buy < 0
        if amount_buy is not None:
            amount_buy = abs(amount_buy)
        if amount_sell is not None:
            amount_sell = abs(amount_sell)
        rate_fact = self._parse_float(row.get("rate_fact"), row_number, "rate_fact", errors)
        commission = self._parse_float(
            row.get("commission", 0),
            row_number,
            "commission",
            errors,
            allow_empty=True,
        )

        currency_buy = str(row.get("currency_buy") or "").strip().upper()
        currency_sell = str(row.get("currency_sell") or "").strip().upper()
        if currency_buy and not self._is_supported_currency_code(currency_buy):
            errors.append(ValidationError(row_number, "currency_buy", "Currency must be ISO code or supported crypto code"))
        if currency_sell and not self._is_supported_currency_code(currency_sell):
            errors.append(ValidationError(row_number, "currency_sell", "Currency must be ISO code or supported crypto code"))

        if amount_buy is not None and amount_buy <= 0:
            errors.append(ValidationError(row_number, "amount_buy", "Amount must be positive"))
        if amount_sell is not None and amount_sell <= 0:
            errors.append(ValidationError(row_number, "amount_sell", "Amount must be positive"))
        if rate_fact is not None and rate_fact <= 0:
            errors.append(ValidationError(row_number, "rate_fact", "Rate must be positive"))

        if errors:
            return None, errors

        return (
            Deal(
                trade_date=trade_date or "",
                value_date=value_date or "",
                operation_type="EXPORT" if is_export_amount else str(row.get("operation_type")).strip(),
                counterparty=str(row.get("counterparty")).strip(),
                currency_buy=currency_buy,
                amount_buy=amount_buy or 0,
                currency_sell=currency_sell,
                amount_sell=amount_sell or 0,
                rate_fact=rate_fact or 0,
                commission=commission or 0,
                portfolio=str(row.get("portfolio")).strip(),
                comment=self._optional_text(row.get("comment")),
                source_file=self._optional_text(row.get("source_file")) or source_file,
                included_in_calc=self._parse_bool(row.get("included_in_calc", True)),
            ),
            [],
        )

    def normalize_keys(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        """Normalize Excel headers to snake_case field names."""
        normalized: dict[str, Any] = {}
        for key, value in raw_row.items():
            normalized_key = str(key).strip().lower().replace("\n", " ")
            normalized_key = self.COLUMN_ALIASES.get(normalized_key, normalized_key)
            normalized_key = normalized_key.replace(" ", "_").replace("-", "_")
            normalized[normalized_key] = value
        return normalized

    @staticmethod
    def _parse_date(
        value: Any,
        row_number: int,
        field_name: str,
        errors: list[ValidationError],
    ) -> str | None:
        if ValidationService._is_empty(value):
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()

        text = str(value).strip()
        formats = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y")
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        errors.append(ValidationError(row_number, field_name, "Invalid date format", value))
        return None

    @staticmethod
    def _parse_float(
        value: Any,
        row_number: int,
        field_name: str,
        errors: list[ValidationError],
        allow_empty: bool = False,
    ) -> float | None:
        if ValidationService._is_empty(value):
            return 0.0 if allow_empty else None
        try:
            return float(str(value).replace(" ", "").replace(",", "."))
        except ValueError:
            errors.append(ValidationError(row_number, field_name, "Invalid number", value))
            return None

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        return text not in {"0", "false", "no", "n", "нет"}

    @staticmethod
    def _is_supported_currency_code(value: str) -> bool:
        code = value.strip().upper()
        return len(code) == 3 or code in SUPPORTED_EXTENDED_CURRENCIES

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if ValidationService._is_empty(value):
            return None
        return str(value).strip()

    @staticmethod
    def _is_empty(value: Any) -> bool:
        if value is None:
            return True
        try:
            import pandas as pd

            if pd.isna(value):
                return True
        except Exception:
            pass
        return str(value).strip() == ""


def source_name(path: str) -> str:
    """Return a stable source file label."""
    return Path(path).name

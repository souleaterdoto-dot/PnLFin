"""Business logic for exchange rate retrieval and storage."""

from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

from app.domain.enums import RateSource
from app.domain.models import Rate
from app.repositories.rates_repository import RatesRepository, normalize_rate_currency


class RatesService:
    """Resolve rates with manual priority and optional CBR fallback."""

    CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"

    def __init__(self, rates_repository: RatesRepository | None = None) -> None:
        self._rates_repository = rates_repository or RatesRepository()
        self._rates_repository.normalize_currency_aliases()

    def add_manual_rate(self, rate_date: str, currency: str, rate_to_rub: float) -> int:
        """Create or update a manual rate."""
        return self._rates_repository.upsert(
            Rate(
                rate_date=rate_date,
                currency=normalize_rate_currency(currency),
                rate_to_rub=rate_to_rub,
                source=RateSource.MANUAL.value,
            )
        )

    def get_rate_to_rub(self, rate_date: str, currency: str, fetch_cbr: bool = False) -> float:
        """Return preferred rate to RUB for a currency and date."""
        currency = normalize_rate_currency(currency)
        if currency == "RUB":
            return 1.0
        existing = self._rates_repository.find_preferred(rate_date, currency)
        if existing:
            return existing.rate_to_rub

        if fetch_cbr:
            fetched = self.fetch_cbr_rate(rate_date, currency)
            if fetched:
                self._rates_repository.upsert(fetched)
                return fetched.rate_to_rub

        latest = self._rates_repository.find_latest_on_or_before(rate_date, currency)
        if latest:
            return latest.rate_to_rub

        raise ValueError(f"Rate is missing for {currency} on {rate_date}")

    def fetch_cbr_rate(self, rate_date: str, currency: str) -> Rate | None:
        """Load one daily CBR rate and return it without overwriting manual data."""
        currency = normalize_rate_currency(currency)
        if currency == "RUB":
            return Rate(rate_date=rate_date, currency="RUB", rate_to_rub=1.0)
        date_obj = datetime.strptime(rate_date, "%Y-%m-%d").date()
        rates = self.fetch_cbr_rates(date_obj)
        value = rates.get(currency)
        if value is None:
            return None
        return Rate(
            rate_date=rate_date,
            currency=currency,
            rate_to_rub=value,
            source=RateSource.CBR.value,
        )

    def fetch_cbr_rates(self, rate_date: date) -> dict[str, float]:
        """Fetch all CBR rates for a date from the public XML endpoint."""
        query = urlencode({"date_req": rate_date.strftime("%d/%m/%Y")})
        with urlopen(f"{self.CBR_DAILY_URL}?{query}", timeout=20) as response:
            payload = response.read()

        root = ElementTree.fromstring(payload)
        rates: dict[str, float] = {"RUB": 1.0}
        for valute in root.findall("Valute"):
            char_code = valute.findtext("CharCode")
            value = valute.findtext("Value")
            if not char_code or not value:
                continue
            rate = float(value.replace(",", "."))
            rates[normalize_rate_currency(char_code)] = rate
        return rates

    def sync_cbr_rates(self, rate_date: str) -> int:
        """Fetch CBR rates for a date and save them as CBR source records."""
        date_obj = datetime.strptime(rate_date, "%Y-%m-%d").date()
        rates = self.fetch_cbr_rates(date_obj)
        count = 0
        for currency, value in rates.items():
            if currency == "RUB":
                continue
            self._rates_repository.upsert(
                Rate(
                    rate_date=rate_date,
                    currency=currency,
                    rate_to_rub=value,
                    source=RateSource.CBR.value,
                )
            )
            count += 1
        return count

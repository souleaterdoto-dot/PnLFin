"""Application service for referrals."""

from __future__ import annotations

from dataclasses import replace

from app.domain.rate_models import Referral
from app.repositories.deals_repository import DealsRepository
from app.repositories.referrals_repository import ReferralsRepository


LEGACY_DEFAULT_CODES = {"alfa", "vtb", "tinkoff", "sber", "gazprombank", "other"}
DEFAULT_LOGO_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("альфабанк", "альфа банк", "alfa", "alpha"), "assets/referrals/alfa_bank.png"),
    (("дом рф", "дом_рф", "dom rf"), "assets/referrals/dom_rf.png"),
    (("зенит", "zenit"), "assets/referrals/zenit.png"),
    (("металлинвестбанк", "металлинвест", "metallinvest"), "assets/referrals/metallinvestbank.png"),
    (("синара", "sinara"), "assets/referrals/sinara.png"),
    (("тинькофф", "tinkoff"), "assets/referrals/tinkoff.png"),
    (("транзакции и расчеты", "int-pay", "zhulong"), "assets/referrals/transactions_intpay_zhulong.png"),
    (("уралсиб", "uralsib"), "assets/referrals/uralsib.png"),
)


class ReferralsService:
    """Manage referral cards and default dictionary values."""

    def __init__(
        self,
        repository: ReferralsRepository,
        deals_repository: DealsRepository | None = None,
    ) -> None:
        self._repository = repository
        self._deals_repository = deals_repository

    def ensure_defaults(self) -> None:
        """Default fixed referral cards are not created; sync uses imported deals."""

    def list(self, search: str | None = None) -> list[Referral]:
        """Return referrals for UI cards."""
        self.sync_from_deals()
        return self._repository.list(search=search)

    def sync_from_deals(self) -> int:
        """Create missing referral cards from unique deal referral names."""
        if self._deals_repository is None:
            return 0
        self._repository.delete_empty_codes(LEGACY_DEFAULT_CODES)
        ignored = self._repository.ignored_sync_name_keys()
        names = [
            name
            for name in self._deals_repository.distinct_values("customer_article_name")
            if str(name or "").strip().casefold() not in ignored
        ]
        before = len(self._repository.list())
        self._repository.ensure_names(names)
        self._ensure_default_logos()
        after = len(self._repository.list())
        return max(0, after - before)

    def get(self, referral_id: int) -> Referral | None:
        """Return one referral."""
        return self._repository.get(referral_id)

    def save(
        self,
        name: str,
        code: str,
        description: str | None = None,
        logo_path: str | None = None,
        is_active: bool = True,
        referral: Referral | None = None,
    ) -> int:
        """Create or update a referral."""
        normalized_code = _normalize_code(code or name)
        self._repository.unignore_sync_name(name)
        if referral is None:
            return self._repository.add(
                Referral(
                    name=name.strip(),
                    code=normalized_code,
                    description=_blank_to_none(description),
                    logo_path=_blank_to_none(logo_path),
                    is_active=is_active,
                )
            )
        updated = replace(
            referral,
            name=name.strip(),
            code=normalized_code,
            description=_blank_to_none(description),
            logo_path=_blank_to_none(logo_path),
            is_active=is_active,
        )
        self._repository.update(updated)
        return int(referral.id or 0)

    def delete(self, referral: Referral) -> None:
        """Delete a referral and prevent automatic recreation from deals."""
        if referral.id is None:
            return
        self._repository.ignore_sync_name(referral.name)
        self._repository.delete(int(referral.id))

    def _ensure_default_logos(self) -> None:
        """Populate bundled logos for known referrals when logo_path is empty."""
        for referral in self._repository.list():
            if referral.logo_path:
                continue
            logo_path = _default_logo_path(referral)
            if not logo_path:
                continue
            self._repository.update(replace(referral, logo_path=logo_path))


def _normalize_code(value: str) -> str:
    return str(value or "").strip().casefold().replace(" ", "_")


def _blank_to_none(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _default_logo_path(referral: Referral) -> str | None:
    haystack = f"{referral.name or ''} {referral.code or ''}".casefold().replace("_", " ")
    for aliases, logo_path in DEFAULT_LOGO_RULES:
        if any(alias.casefold().replace("_", " ") in haystack for alias in aliases):
            return logo_path
    return None

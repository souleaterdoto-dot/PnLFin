"""Dialogs for creating and editing rate conditions."""

from __future__ import annotations

from dataclasses import replace

import flet as ft

from app.domain.rate_models import RateCondition, Referral
from app.services.rate_conditions_validation_service import RateConditionOverlapError
from app.ui import theme as ui_theme


AMOUNT_BASIS_LABELS = {
    "deal_currency": "в валюте сделки",
    "usd_equivalent": "от eq. USD",
}
CURRENCIES = ["", "USD", "EUR", "CNY", "CNH", "RUB", "AED", "HKD", "TRY", "USDT"]
OPERATION_TYPE_LABELS = {
    "": "\u041b\u044e\u0431\u043e\u0439 \u0442\u0438\u043f",
    "import": "\u0418\u043c\u043f\u043e\u0440\u0442",
    "export": "\u042d\u043a\u0441\u043f\u043e\u0440\u0442",
}


def open_rate_condition_form(
    context,
    referral: Referral,
    on_saved,
    condition: RateCondition | None = None,
    fixed_amount_basis: str | None = None,
    fixed_commission_type: str | None = None,
) -> None:
    """Open a modal form for one condition."""
    locked_amount_basis = _amount_basis(fixed_amount_basis) if fixed_amount_basis else None
    current = condition or RateCondition(
        referral_id=int(referral.id or 0),
        amount_basis=locked_amount_basis or "deal_currency",
        commission_type="mixed",
    )
    is_edit = condition is not None

    active = ft.Checkbox(label="Активно", value=current.is_active)
    operation_type = _dropdown(
        "\u0422\u0438\u043f \u0441\u0434\u0435\u043b\u043a\u0438",
        current.operation_type,
        ["", "import", "export"],
        "\u041b\u044e\u0431\u043e\u0439 \u0442\u0438\u043f",
        labels=OPERATION_TYPE_LABELS,
    )
    currency = _dropdown("Валюта сделки", current.currency, CURRENCIES, "Любая валюта")
    amount_basis = _dropdown(
        "Диапазон суммы",
        locked_amount_basis or _amount_basis(current.amount_basis),
        ["deal_currency", "usd_equivalent"],
        "",
        labels=AMOUNT_BASIS_LABELS,
    )
    amount_from = _field("Сумма от", _fmt_value(current.amount_from))
    amount_to = _field("Сумма до", _fmt_value(current.amount_to))
    date_from = _field("Дата от", current.date_from or "", hint_text="2026-01-01")
    date_to = _field("Дата до", current.date_to or "", hint_text="2026-12-31")

    percent_rate = _field("Процентная комиссия, %", _fmt_value(current.rate_value))
    percent_currency = _dropdown(
        "Валюта процентной комиссии",
        current.percent_commission_currency,
        CURRENCIES,
        "Валюта сделки",
    )
    fixed_amount = _field("Фиксированная комиссия", _fmt_value(current.fixed_commission_amount))
    fixed_currency = _dropdown(
        "Валюта фикс. комиссии",
        current.fixed_commission_currency,
        CURRENCIES,
        "Валюта сделки",
    )
    comment = ft.TextField(
        label="Комментарий",
        value=current.comment or "",
        multiline=True,
        min_lines=3,
        max_lines=4,
    )

    for field in (amount_from, amount_to, date_from, date_to, percent_rate, fixed_amount, comment):
        _style_field(field)
    for dropdown in (operation_type, currency, amount_basis, percent_currency, fixed_currency):
        _style_dropdown(dropdown)

    error_text = ft.Text("", color=ui_theme.DANGER, visible=False)

    def save(_: ft.ControlEvent) -> None:
        try:
            updated = replace(
                current,
                referral_id=int(referral.id or current.referral_id),
                is_active=bool(active.value),
                priority=current.priority or 100,
                operation_type=_blank(operation_type.value),
                currency=_blank(currency.value),
                amount_from=_parse_optional_float(amount_from.value),
                amount_to=_parse_optional_float(amount_to.value),
                amount_basis=locked_amount_basis or _amount_basis(amount_basis.value),
                region=None,
                date_from=_blank(date_from.value),
                date_to=_blank(date_to.value),
                rate_value=_parse_float(percent_rate.value),
                percent_commission_currency=_blank(percent_currency.value),
                fixed_commission_amount=_parse_optional_float(fixed_amount.value),
                fixed_commission_currency=_blank(fixed_currency.value),
                commission_type="mixed",
                comment=_blank(comment.value),
            )
            context.rate_conditions_service.save(updated)
            context.page.pop_dialog()
            on_saved()
        except RateConditionOverlapError as exc:
            context.page.pop_dialog()
            on_saved(exc.conflict.condition.id, str(exc))
        except Exception as exc:
            error_text.value = str(exc)
            error_text.visible = True
            context.page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=10,
                    bgcolor=ui_theme.PRIMARY_SOFT,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.PERCENT, color=ui_theme.PRIMARY),
                ),
                ft.Column(
                    controls=[
                        ft.Text("Условие ставок", size=20, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                        ft.Text(referral.name, size=13, color=ui_theme.MUTED),
                    ],
                    spacing=1,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=860,
            content=ft.Column(
                controls=[
                    _section(
                        "Когда применять",
                        ft.ResponsiveRow(
                            controls=[
                                ft.Container(currency, col={"sm": 12, "md": 4}),
                                ft.Container(operation_type, col={"sm": 12, "md": 4}),
                                ft.Container(
                                    _locked_badge(AMOUNT_BASIS_LABELS[locked_amount_basis])
                                    if locked_amount_basis
                                    else amount_basis,
                                    col={"sm": 12, "md": 4},
                                ),
                                ft.Container(amount_from, col={"sm": 12, "md": 6}),
                                ft.Container(amount_to, col={"sm": 12, "md": 6}),
                                ft.Container(date_from, col={"sm": 12, "md": 6}),
                                ft.Container(date_to, col={"sm": 12, "md": 6}),
                            ],
                            spacing=12,
                            run_spacing=12,
                        ),
                    ),
                    _section(
                        "Комиссии",
                        ft.ResponsiveRow(
                            controls=[
                                ft.Container(percent_rate, col={"sm": 12, "md": 6}),
                                ft.Container(percent_currency, col={"sm": 12, "md": 6}),
                                ft.Container(fixed_amount, col={"sm": 12, "md": 6}),
                                ft.Container(fixed_currency, col={"sm": 12, "md": 6}),
                            ],
                            spacing=12,
                            run_spacing=12,
                        ),
                    ),
                    ft.Row([active], wrap=True),
                    _section("Комментарий", comment),
                    error_text,
                ],
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
            ui_theme.primary_button("Сохранить" if is_edit else "Добавить", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
        ],
    )
    context.page.show_dialog(dialog)


def _section(title: str, content: ft.Control) -> ft.Control:
    return ft.Container(
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#D8E2F0"),
        border_radius=10,
        padding=ft.Padding(14, 12, 14, 12),
        content=ft.Column(
            controls=[
                ft.Text(title, size=13, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                content,
            ],
            spacing=10,
            tight=True,
        ),
    )


def _locked_badge(label: str) -> ft.Control:
    return ft.Container(
        height=40,
        padding=ft.Padding(12, 0, 12, 0),
        border=ui_theme.border("#BFDBFE"),
        border_radius=8,
        bgcolor=ui_theme.PRIMARY_SOFT,
        alignment=ft.Alignment.CENTER_LEFT,
        content=ft.Text(label, size=13, weight=ft.FontWeight.W_700, color=ui_theme.PRIMARY),
    )


def _field(label: str, value: str, width: int | None = None, hint_text: str | None = None) -> ft.TextField:
    return ft.TextField(label=label, value=value, dense=True, width=width, hint_text=hint_text)


def _dropdown(
    label: str,
    value: str | None,
    values: list[str],
    empty_text: str,
    labels: dict[str, str] | None = None,
) -> ft.Dropdown:
    labels = labels or {}
    return ft.Dropdown(
        label=label,
        value=value or None,
        options=[ft.dropdown.Option(key=item, text=labels.get(item, item or empty_text)) for item in values],
        dense=True,
        editable=False,
    )


def _style_field(field: ft.TextField) -> None:
    field.filled = True
    field.fill_color = "#F8FAFC"
    field.border_color = "#D8E2F0"
    field.focused_border_color = ui_theme.PRIMARY
    field.border_radius = 8
    field.content_padding = ft.Padding(12, 10, 12, 10)


def _style_dropdown(dropdown: ft.Dropdown) -> None:
    dropdown.filled = True
    dropdown.fill_color = "#F8FAFC"
    dropdown.border_color = "#D8E2F0"
    dropdown.focused_border_color = ui_theme.PRIMARY
    dropdown.border_radius = 8
    dropdown.content_padding = ft.Padding(12, 10, 12, 10)


def _blank(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _amount_basis(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text in {"deal_currency", "usd_equivalent"} else "deal_currency"


def _parse_float(value: str | None) -> float:
    text = str(value or "").replace(" ", "").replace(",", ".").strip()
    return float(text or 0)


def _parse_optional_float(value: str | None) -> float | None:
    text = str(value or "").replace(" ", "").replace(",", ".").strip()
    return float(text) if text else None


def _fmt_value(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{float(value):,.4f}".replace(",", " ").replace(".", ",")
    return text.rstrip("0").rstrip(",")

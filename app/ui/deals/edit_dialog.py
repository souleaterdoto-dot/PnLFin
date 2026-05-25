"""Edit dialog for deals registry rows."""

from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import date, datetime
from typing import Any, Callable

import flet as ft

from app.domain.models import Deal
from app.ui import theme as ui_theme
from app.ui.deals.constants import (
    EDIT_FIELD_SPECS,
    EDIT_FINANCE_FIELDS,
    EDIT_GENERAL_FIELDS,
    EDIT_RATES_FIELDS,
)
from app.ui.deals.formatters import (
    _format_date,
    _format_number,
    _format_short_date,
    _parse_optional_date,
)


def _source_label(deal: Deal) -> str:
    if deal.source_sheet and deal.source_row_number:
        return f"{deal.source_sheet}:{deal.source_row_number}"
    return deal.source_file or "-"


EditControl = ft.TextField | ft.Dropdown
USD_LIKE_CURRENCIES = {"USD", "USDT", "USDC"}
STRONGER_THAN_USD_CURRENCIES = {"EUR", "GBP", "CHF", "KWD", "BHD", "OMR", "JOD", "KYD", "GIP"}

PNL_MANUAL_FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("pnl_client_percent_fee_usd", "Ставка клиента %, USD", "float"),
    ("pnl_fixed_commission_usd", "Фикс. комиссия, USD", "float"),
    ("pnl_swift_usd", "SWIFT, USD", "float"),
    ("pnl_agent_commission_usd", "Комиссия ПА, USD", "float"),
    ("pnl_swift_commission_usd", "Комиссия за SWIFT ПА, USD", "float"),
    ("pnl_referral_commission_usd", "Ставка реферала, USD", "float"),
    ("repeat_payment_penalty_usd", "Штраф за переотправку, USD", "float"),
)

REQUIRED_NEW_GENERAL_FIELDS = (
    "manager",
    "request_date",
    "client_fix_date",
    "agent_writeoff_date",
    "client_name",
    "receiver_company",
    "receiver_bank_country",
)
REQUIRED_NEW_RATES_FIELDS = EDIT_RATES_FIELDS


def _build_text_fields(
    deal: Deal,
    specs: tuple[tuple[str, str, str], ...],
    context=None,
) -> dict[str, EditControl]:
    fields: dict[str, EditControl] = {}
    for attr, label, kind in specs:
        if kind == "bool":
            value = ""
        elif kind == "percent":
            source_value = getattr(deal, attr)
            if attr == "client_rate_percent" and source_value is not None:
                source_value = abs(float(source_value))
            value = _edit_percent_value(source_value)
        else:
            value = _edit_value(getattr(deal, attr))
        if _is_dropdown_edit_field(attr):
            fields[attr] = _edit_dropdown(context, attr, label, value)
        elif kind in {"date", "date_required"}:
            fields[attr] = _edit_date_field(context, label, _format_short_date(value))
        else:
            fields[attr] = ft.TextField(label=label, value=value)
            _style_edit_field(fields[attr])
    return fields


def _edit_date_field(context, label: str, value: str) -> ft.TextField:
    field = ft.TextField(
        label=label,
        value=value,
        hint_text="дд.мм.гг",
        suffix=_calendar_icon_button(None),
    )
    field.suffix.on_click = lambda _: _open_date_picker(context, field, storage_format=False)
    _style_edit_field(field)
    return field


def _is_dropdown_edit_field(attr: str) -> bool:
    return attr in {
        "deal_currency",
        "fixed_commission_currency",
        "swift_currency",
        "agent_commission_currency",
        "swift_commission_currency",
        "currency_buy",
        "currency_sell",
        "customer_article_name",
        "payment_agent",
        "payment_status",
        "receiver_bank_country",
        "client_name",
    }


def _edit_dropdown(context, attr: str, label: str, value: str) -> ft.Dropdown:
    options = _edit_dropdown_options(context, attr, value)
    dropdown = ft.Dropdown(
        label=label,
        value=value or None,
        options=[ft.dropdown.Option(key=item, text=item) for item in options],
        editable=True,
        enable_filter=True,
        enable_search=True,
        menu_height=320,
        trailing_icon=ft.Icons.EXPAND_MORE,
    )
    _style_edit_dropdown(dropdown)
    return dropdown


def _edit_dropdown_options(context, attr: str, current_value: str) -> list[str]:
    values: list[str] = []
    if attr in {
        "deal_currency",
        "fixed_commission_currency",
        "swift_currency",
        "agent_commission_currency",
        "swift_commission_currency",
        "currency_buy",
        "currency_sell",
    }:
        values.extend(["USD", "EUR", "CNY", "CNH", "RUB", "AED", "HKD", "TRY", "USDT"])
        source_columns = {
            "deal_currency": ["deal_currency", "fixed_commission_currency", "swift_currency", "agent_commission_currency", "swift_commission_currency"],
            "currency_buy": ["currency_buy", "currency_sell", "deal_currency"],
            "currency_sell": ["currency_sell", "currency_buy", "deal_currency"],
        }.get(attr, [attr, "deal_currency"])
    elif attr == "customer_article_name":
        if context is not None and hasattr(context, "referrals_service"):
            values.extend(referral.name for referral in context.referrals_service.list())
        source_columns = []
    elif attr == "payment_agent":
        source_columns = ["payment_agent", "portfolio"]
    elif attr == "payment_status":
        source_columns = ["payment_status"]
    elif attr == "receiver_bank_country":
        source_columns = ["receiver_bank_country"]
    elif attr == "client_name":
        source_columns = ["client_name"]
    else:
        source_columns = [attr]
    if context is not None:
        for column in source_columns:
            try:
                values.extend(context.deals_repository.distinct_values(column, limit=300))
            except Exception:
                continue
    if current_value:
        values.insert(0, current_value)
    return _unique_non_empty(values)


def _unique_non_empty(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def _style_edit_field(field: ft.TextField) -> None:
    field.height = 58
    field.data = {"label": field.label}
    field.filled = True
    field.fill_color = "#F8FAFC"
    field.border_color = "#D8E2F0"
    field.focused_border_color = ui_theme.PRIMARY
    field.border_radius = 8
    field.content_padding = ft.Padding(12, 14, 12, 8)


def _style_edit_dropdown(dropdown: ft.Dropdown) -> None:
    dropdown.height = 58
    dropdown.data = {"label": dropdown.label}
    dropdown.filled = True
    dropdown.fill_color = "#F8FAFC"
    dropdown.border_color = "#D8E2F0"
    dropdown.focused_border_color = ui_theme.PRIMARY
    dropdown.border_radius = 8
    dropdown.content_padding = ft.Padding(12, 14, 10, 8)


def _calendar_icon_button(on_click) -> ft.IconButton:
    return ft.IconButton(
        ft.Icons.CALENDAR_MONTH_OUTLINED,
        icon_size=18,
        icon_color=ui_theme.PRIMARY,
        bgcolor=ui_theme.PRIMARY_SOFT,
        hover_color="#DBEAFE",
        splash_color="#BFDBFE",
        tooltip="Выбрать дату",
        on_click=on_click,
    )


def _open_date_picker(
    context,
    field: ft.TextField,
    on_selected: Callable[[], None] | None = None,
    storage_format: bool = False,
) -> None:
    if context is None or not hasattr(context, "page"):
        return

    month_names = (
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    )
    weekday_names = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    selected_date = {"value": _date_picker_value(field.value)}
    visible_month = {"year": selected_date["value"].year, "month": selected_date["value"].month}
    holder = ft.Container(width=372)

    def commit(selected: date | None) -> None:
        field.value = "" if selected is None else selected.isoformat() if storage_format else _format_short_date(selected.isoformat())
        if on_selected:
            on_selected()
        else:
            context.page.update(field)
        context.page.pop_dialog()

    def shift_month(delta: int) -> None:
        month = visible_month["month"] + delta
        year = visible_month["year"]
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        visible_month["year"] = min(max(2000, year), 2100)
        visible_month["month"] = month
        rebuild()
        context.page.update(holder)

    def choose_day(day: int) -> None:
        selected_date["value"] = date(visible_month["year"], visible_month["month"], day)
        rebuild()
        context.page.update(holder)

    def day_cell(day: int) -> ft.Control:
        if day == 0:
            return ft.Container(width=44, height=38)
        current = date(visible_month["year"], visible_month["month"], day)
        is_selected = current == selected_date["value"]
        is_today = current == date.today()
        return ft.Container(
            width=44,
            height=38,
            border_radius=10,
            alignment=ft.Alignment.CENTER,
            bgcolor=ui_theme.PRIMARY if is_selected else "#EFF6FF" if is_today else ui_theme.SURFACE,
            border=ui_theme.border(ui_theme.PRIMARY if is_selected else "#BFDBFE" if is_today else "#E2E8F0"),
            ink=True,
            ink_color="#DBEAFE",
            on_click=lambda _, value=day: choose_day(value),
            content=ft.Text(
                str(day),
                size=13,
                weight=ft.FontWeight.W_700 if is_selected or is_today else None,
                color=ft.Colors.WHITE if is_selected else ui_theme.PRIMARY if is_today else ui_theme.TEXT,
            ),
        )

    def rebuild() -> None:
        year = visible_month["year"]
        month = visible_month["month"]
        weeks = calendar.monthcalendar(year, month)
        holder.content = ft.Container(
            padding=ft.Padding(16, 14, 16, 14),
            bgcolor=ui_theme.SURFACE,
            border_radius=14,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.IconButton(
                                ft.Icons.CHEVRON_LEFT,
                                icon_color=ui_theme.PRIMARY,
                                bgcolor=ui_theme.PRIMARY_SOFT,
                                tooltip="Предыдущий месяц",
                                on_click=lambda _: shift_month(-1),
                            ),
                            ft.Container(
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(
                                    f"{month_names[month - 1]} {year}",
                                    size=18,
                                    weight=ft.FontWeight.W_700,
                                    color=ui_theme.TEXT,
                                ),
                            ),
                            ft.IconButton(
                                ft.Icons.CHEVRON_RIGHT,
                                icon_color=ui_theme.PRIMARY,
                                bgcolor=ui_theme.PRIMARY_SOFT,
                                tooltip="Следующий месяц",
                                on_click=lambda _: shift_month(1),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=44,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(name, size=12, weight=ft.FontWeight.W_700, color=ui_theme.MUTED),
                            )
                            for name in weekday_names
                        ],
                        spacing=6,
                    ),
                    *[
                        ft.Row(
                            controls=[day_cell(day) for day in week],
                            spacing=6,
                        )
                        for week in weeks
                    ],
                    ft.Container(
                        padding=ft.Padding(10, 8, 10, 8),
                        bgcolor="#F8FAFC",
                        border=ui_theme.border("#E2E8F0"),
                        border_radius=10,
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.EVENT_AVAILABLE_OUTLINED, size=18, color=ui_theme.PRIMARY),
                                ft.Text(
                                    f"Выбрано: {_format_short_date(selected_date['value'].isoformat())}",
                                    size=13,
                                    weight=ft.FontWeight.W_700,
                                    color=ui_theme.TEXT,
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                spacing=10,
                tight=True,
            ),
        )

    rebuild()
    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ui_theme.SURFACE,
        barrier_color="#0F172A66",
        title=ft.Row(
            controls=[
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=ui_theme.PRIMARY_SOFT,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=20, color=ui_theme.PRIMARY),
                ),
                ft.Column(
                    controls=[
                        ft.Text("Выбор даты", size=18, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                        ft.Text("Формат: дд.мм.гг", size=12, color=ui_theme.MUTED),
                    ],
                    spacing=0,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=holder,
        actions=[
            ft.TextButton("Очистить", on_click=lambda _: commit(None)),
            ft.TextButton("Сегодня", on_click=lambda _: (selected_date.update({"value": date.today()}), visible_month.update({"year": date.today().year, "month": date.today().month}), rebuild(), context.page.update(holder))),
            ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
            ui_theme.primary_button("Выбрать", icon=ft.Icons.CHECK, on_click=lambda _: commit(selected_date["value"])),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    context.page.show_dialog(dialog)


def _date_picker_value(value: str | None) -> date:
    parsed = _parse_optional_date(value or "")
    if not parsed:
        return date.today()
    try:
        return datetime.strptime(parsed, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _fields_grid(
    fields: dict[str, EditControl],
    exclude: set[str] | None = None,
    only: tuple[str, ...] | None = None,
) -> ft.ResponsiveRow:
    excluded = exclude or set()
    attrs = only or tuple(fields.keys())
    return ft.ResponsiveRow(
        controls=[
            ft.Container(_field_shell(field), col={"sm": 12, "md": 4})
            for attr in attrs
            if attr in fields and attr not in excluded
            for field in (fields[attr],)
        ],
        spacing=10,
        run_spacing=8,
    )


def _field_shell(field: EditControl) -> ft.Control:
    data = getattr(field, "data", None)
    label = str(data.get("label") if isinstance(data, dict) else getattr(field, "label", "") or "")
    field.label = None
    return ft.Column(
        controls=[
            ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=ui_theme.MUTED),
            field,
        ],
        spacing=4,
        tight=True,
    )


def _parse_field_updates(
    fields: dict[str, EditControl],
    specs: tuple[tuple[str, str, str], ...],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for attr, _, kind in specs:
        if kind == "bool":
            continue
        raw_value = fields[attr].value
        updates[attr] = _parse_edit_value(raw_value, kind)
    return updates


def _parse_edit_value(value: str | None, kind: str) -> Any:
    text = (value or "").strip()
    if kind == "text":
        return text or None
    if kind == "text_required":
        return text
    if kind == "upper":
        return text.upper() if text else None
    if kind == "upper_required":
        return text.upper()
    if kind == "float":
        return _parse_optional_float(text)
    if kind == "percent":
        return _parse_optional_percent(text)
    if kind == "float_required":
        if not text:
            return 0.0
        return float(text.replace(" ", "").replace(",", "."))
    if kind == "date":
        return _parse_optional_date(text)
    if kind == "date_required":
        return _parse_optional_date(text) or ""
    return text


def _parse_optional_float(value: str) -> float | None:
    if not value:
        return None
    return float(value.replace(" ", "").replace(",", "."))


def _parse_optional_percent(value: str) -> float | None:
    text = value.replace("%", "").strip()
    if not text:
        return None
    return abs(float(text.replace(" ", "").replace(",", "."))) / 100


def _wire_cross_rate_autocalc(context, fields: dict[str, EditControl]) -> None:
    """Auto-calculate client cross rate from deal currency, currency rate and USD rate."""
    currency_field = fields.get("deal_currency")
    fix_rate_field = fields.get("client_fix_rate")
    usd_rate_field = fields.get("usd_rate")
    cross_rate_field = fields.get("client_cross_rate")
    if not currency_field or not fix_rate_field or not usd_rate_field or not cross_rate_field:
        return

    def recalculate(update: bool = True) -> None:
        cross_rate = _calculate_client_cross_rate(
            currency=_control_value(currency_field),
            client_fix_rate=_control_float(fix_rate_field),
            usd_rate=_control_float(usd_rate_field),
        )
        if cross_rate is None:
            return
        cross_rate_field.value = _edit_value(cross_rate)
        if update and context is not None and hasattr(context, "page"):
            context.page.update(cross_rate_field)

    def chain_on_change(control: EditControl) -> None:
        previous_handler = getattr(control, "on_change", None)

        def handler(event: ft.ControlEvent) -> None:
            if previous_handler:
                previous_handler(event)
            recalculate(update=True)

        control.on_change = handler

    for control in (currency_field, fix_rate_field, usd_rate_field):
        chain_on_change(control)

    if not _control_value(cross_rate_field):
        recalculate(update=False)


def _control_value(control: EditControl) -> str:
    return str(getattr(control, "value", "") or "").strip()


def _control_float(control: EditControl) -> float | None:
    value = _control_value(control)
    if not value:
        return None
    try:
        return _parse_optional_float(value)
    except ValueError:
        return None


def _calculate_client_cross_rate(currency: str, client_fix_rate: float | None, usd_rate: float | None) -> float | None:
    """Return a display cross rate to USD; cross rate is always normalized above one."""
    normalized_currency = (currency or "").strip().upper()
    if normalized_currency in USD_LIKE_CURRENCIES:
        return 1.0
    if not normalized_currency or not client_fix_rate or not usd_rate or client_fix_rate <= 0 or usd_rate <= 0:
        return None
    if normalized_currency in STRONGER_THAN_USD_CURRENCIES:
        cross_rate = client_fix_rate / usd_rate
    else:
        cross_rate = usd_rate / client_fix_rate
    if cross_rate <= 0:
        return None
    return cross_rate if cross_rate >= 1 else 1 / cross_rate



def _edit_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return _format_number(value, 4).rstrip("0").rstrip(",")
    return str(value)


def _edit_percent_value(value: Any) -> str:
    if value is None:
        return ""
    numeric = float(value)
    return _format_number(numeric * 100, 4).rstrip("0").rstrip(",")


def _edit_dialog_header(deal: Deal) -> ft.Container:
    title = "Новая сделка" if deal.id is None else f"Сделка {deal.external_deal_id or deal.id or '-'}"
    return ft.Container(
        padding=ft.Padding(16, 12, 16, 12),
        border_radius=8,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#BFDBFE"),
        shadow=ft.BoxShadow(blur_radius=28, color="#2563EB1A", offset=ft.Offset(0, 12)),
        content=ft.Row(
            controls=[
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=8,
                    bgcolor=ui_theme.PRIMARY,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, color=ui_theme.SURFACE, size=22),
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            title,
                            size=20,
                            weight=ft.FontWeight.W_700,
                            color=ui_theme.TEXT,
                        ),
                        ft.Text(
                            f"{deal.client_name or 'Без клиента'} · {_format_date(deal.client_fix_date or deal.request_date)}",
                            color=ui_theme.MUTED,
                            selectable=True,
                        ),
                    ],
                    spacing=1,
                    expand=True,
                ),
                _edit_header_metric("Сумма", _format_number(deal.deal_amount, 2), deal.deal_currency or "-"),
                _edit_header_metric("ПА", deal.payment_agent or "-", "субагент"),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _edit_header_metric(label: str, value: str, caption: str) -> ft.Container:
    return ft.Container(
        width=150,
        padding=ft.Padding(12, 8, 12, 8),
        border_radius=8,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#D8E2F0"),
        content=ft.Column(
            controls=[
                ft.Text(label, size=11, color=ui_theme.MUTED),
                ft.Text(value, size=14, weight=ft.FontWeight.W_700, color=ui_theme.TEXT, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(caption, size=11, color=ui_theme.MUTED, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=1,
        ),
    )


def _edit_section_card(
    title: str,
    subtitle: str,
    content: ft.Control,
    header_trailing: ft.Control | None = None,
) -> ft.Container:
    return ft.Container(
        expand=True,
        padding=ft.Padding(18, 14, 18, 16),
        border_radius=8,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#D8E2F0"),
        shadow=ft.BoxShadow(blur_radius=24, color="#0F172A12", offset=ft.Offset(0, 10)),
        content=ft.Column(
            controls=[
                ft.Container(
                    height=42,
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                width=30,
                                height=30,
                                border_radius=8,
                                bgcolor=ui_theme.PRIMARY_SOFT,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.EDIT_NOTE_OUTLINED, size=18, color=ui_theme.PRIMARY),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(title, size=15, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                                    ft.Text(subtitle, size=11, color=ui_theme.MUTED),
                                ],
                                spacing=0,
                                tight=True,
                                expand=True,
                            ),
                            *([header_trailing] if header_trailing is not None else []),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding(0, 22, 0, 0),
                    content=ft.Column([content], scroll=ft.ScrollMode.AUTO, expand=True),
                ),
            ],
            spacing=0,
        ),
    )


def _open_edit_dialog(context, deal: Deal, on_saved) -> None:
    is_new = deal.id is None
    excel_fields = _build_text_fields(deal, EDIT_FIELD_SPECS, context)
    pnl_fields = _build_text_fields(deal, PNL_MANUAL_FIELD_SPECS, context)
    pulled_auto_pnl_values: dict[str, float | None] = {}
    _wire_cross_rate_autocalc(context, excel_fields)
    pnl_total_value = ft.Text("0,00 USD", size=26, weight=ft.FontWeight.W_800, color="#92400E")
    pnl_formula_value = ft.Text(size=12, color=ui_theme.MUTED, selectable=True)
    repeat_payment = ft.Checkbox(
        label="\u041f\u043e\u0432\u0442\u043e\u0440\u043d\u044b\u0439 \u043f\u043b\u0430\u0442\u0451\u0436",
        value=bool(deal.is_repeat_payment),
        tristate=False,
    )
    refund = ft.Checkbox(
        label="\u0412\u043e\u0437\u0432\u0440\u0430\u0442",
        value=bool(deal.is_refund),
        tristate=False,
    )
    for checkbox in (repeat_payment, refund):
        checkbox.check_color = ui_theme.SURFACE
        checkbox.fill_color = ui_theme.PRIMARY
        checkbox.visual_density = ft.VisualDensity.COMPACT
        checkbox.height = 32
        checkbox.label_style = ft.TextStyle(size=12, color=ui_theme.TEXT)
    status_flags = ft.Container(
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=999,
        bgcolor="#F8FAFC",
        border=ui_theme.border("#D8E2F0"),
        content=ft.Row(
            controls=[repeat_payment, refund],
            spacing=6,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    section_holder = ft.Container(expand=True)
    section_switch = ft.SegmentedButton(
        selected=["general"],
        show_selected_icon=False,
        segments=[
            ft.Segment(value="general", label="Общее", icon=ft.Icons.DESCRIPTION_OUTLINED),
            ft.Segment(value="rates", label="Курсы", icon=ft.Icons.CURRENCY_EXCHANGE_OUTLINED),
            ft.Segment(value="finance", label="Финансы", icon=ft.Icons.INSIGHTS_OUTLINED),
            ft.Segment(value="pnl", label="PnL", icon=ft.Icons.SSID_CHART_OUTLINED),
        ],
    )

    def recalc_pnl_preview(update: bool = True) -> None:
        try:
            pnl_updates = _parse_field_updates(pnl_fields, PNL_MANUAL_FIELD_SPECS)
            preview_deal = replace(
                deal,
                **pnl_updates,
                is_repeat_payment=bool(repeat_payment.value),
                is_refund=bool(refund.value),
            )
            from app.ui.deals.table_view import _pnl_breakdown

            breakdown = _pnl_breakdown(context, {"referral_rate_cache": {}}, preview_deal)
            gross = breakdown.gross
            costs = breakdown.costs
            pnl = breakdown.pnl
            pnl_total_value.value = "Нет данных" if pnl is None else f"{_format_number(pnl, 2)} USD"
            pnl_total_value.color = "#B91C1C" if pnl is not None and pnl < 0 else "#166534"
            pnl_formula_value.value = (
                "Доходы: "
                f"{_format_number(gross, 2) if gross is not None else 'нет данных'} USD  ·  "
                "Расходы: "
                f"{_format_number(costs, 2) if costs is not None else 'нет данных'} USD"
            )
        except Exception as exc:
            pnl_total_value.value = "Проверьте значения"
            pnl_total_value.color = "#B91C1C"
            pnl_formula_value.value = str(exc)
        if update:
            context.page.update(pnl_total_value, pnl_formula_value)

    for attr, field in pnl_fields.items():
        field.hint_text = "0,00"
        field.on_change = lambda _, field_attr=attr: (
            pulled_auto_pnl_values.pop(field_attr, None),
            recalc_pnl_preview(),
        )
    repeat_payment.on_change = lambda _: recalc_pnl_preview()
    refund.on_change = lambda _: recalc_pnl_preview()

    def pull_pnl_from_db(_: ft.ControlEvent | None = None) -> None:
        if deal.id is None:
            try:
                source_deal = replace(
                    deal,
                    **_parse_field_updates(excel_fields, EDIT_FIELD_SPECS),
                    is_repeat_payment=bool(repeat_payment.value),
                    is_refund=bool(refund.value),
                )
                source_deal = _prepare_manual_deal_for_insert(source_deal)
            except Exception:
                source_deal = deal
        else:
            source_deal = context.deals_repository.get(deal.id)
        if source_deal is None:
            source_deal = deal
        source_deal = replace(
            source_deal,
            pnl_client_percent_fee_usd=None,
            pnl_fixed_commission_usd=None,
            pnl_swift_usd=None,
            pnl_agent_commission_usd=None,
            pnl_swift_commission_usd=None,
            pnl_referral_commission_usd=None,
        )
        from app.ui.deals.table_view import (
            _client_percent_fee_usd,
            _referral_commission_result,
            _usd_component_or_zero,
        )

        values = {
            "pnl_client_percent_fee_usd": _client_percent_fee_usd(source_deal),
            "pnl_fixed_commission_usd": _usd_component_or_zero(
                source_deal.fixed_commission_amount,
                source_deal.fixed_commission_currency,
                source_deal,
            ),
            "pnl_swift_usd": _usd_component_or_zero(source_deal.swift_amount, source_deal.swift_currency, source_deal),
            "pnl_agent_commission_usd": _usd_component_or_zero(
                source_deal.agent_commission_amount,
                source_deal.agent_commission_currency,
                source_deal,
            ),
            "pnl_swift_commission_usd": _usd_component_or_zero(
                source_deal.swift_commission_amount,
                source_deal.swift_commission_currency,
                source_deal,
            ),
            "pnl_referral_commission_usd": _referral_commission_result(
                context,
                {"referral_rate_cache": {}},
                source_deal,
            ).amount_usd,
        }
        for attr, value in values.items():
            pnl_fields[attr].value = "" if value is None else _edit_value(float(value))
        pulled_auto_pnl_values.clear()
        pulled_auto_pnl_values.update(values)
        recalc_pnl_preview(update=False)
        context.page.update(*pnl_fields.values(), pnl_total_value, pnl_formula_value)

    pull_pnl_button = ft.OutlinedButton(
        "Подтянуть из БД",
        icon=ft.Icons.DOWNLOAD_OUTLINED,
        style=ft.ButtonStyle(
            color="#92400E",
            side=ft.BorderSide(1, "#FCD34D"),
            bgcolor="#FFFBEB",
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(14, 10, 14, 10),
        ),
        on_click=pull_pnl_from_db,
    )

    def set_section(section: str) -> None:
        if section == "rates":
            section_holder.content = _edit_section_card(
                title="Курсы и сумма",
                subtitle="Сумма сделки, валюта и клиентские курсы.",
                content=_fields_grid(excel_fields, only=EDIT_RATES_FIELDS),
            )
        elif section == "finance":
            section_holder.content = _edit_section_card(
                title="Финансы и комиссии",
                subtitle="Ставки, комиссии, платежный агент и статья клиента.",
                content=_fields_grid(excel_fields, only=EDIT_FINANCE_FIELDS),
            )
        elif section == "pnl":
            recalc_pnl_preview(update=False)
            section_holder.content = _edit_section_card(
                title="PnL",
                subtitle="Ручные значения в USD. Пустое поле оставляет авторасчет для этой компоненты.",
                content=ft.Column(
                    controls=[
                        ft.Container(
                            padding=ft.Padding(16, 14, 16, 14),
                            border_radius=12,
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment(-1, -1),
                                end=ft.Alignment(1, 1),
                                colors=["#FFF7ED", "#FEF3C7", "#FFFFFF"],
                            ),
                            border=ui_theme.border("#FCD34D"),
                            content=ft.Row(
                                controls=[
                                    ft.Container(
                                        width=44,
                                        height=44,
                                        border_radius=14,
                                        bgcolor="#111827",
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.LOCK_OUTLINED, size=22, color="#FCD34D"),
                                    ),
                                    ft.Column(
                                        controls=[
                                            ft.Text("Итоговый PnL", size=12, weight=ft.FontWeight.W_700, color="#92400E"),
                                            pnl_total_value,
                                            pnl_formula_value,
                                        ],
                                        spacing=1,
                                        expand=True,
                                    ),
                                    pull_pnl_button,
                                ],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding(12, 10, 12, 10),
                            border_radius=12,
                            bgcolor="#F8FAFC",
                            border=ui_theme.border("#E2E8F0"),
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=18, color="#166534"),
                                    ft.Text("Доходы", size=13, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                                ],
                                spacing=8,
                            ),
                        ),
                        _fields_grid(
                            pnl_fields,
                            only=(
                                "pnl_client_percent_fee_usd",
                                "pnl_fixed_commission_usd",
                                "pnl_swift_usd",
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding(12, 10, 12, 10),
                            border_radius=12,
                            bgcolor="#F8FAFC",
                            border=ui_theme.border("#E2E8F0"),
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=18, color="#B91C1C"),
                                    ft.Text("Расходы", size=13, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                                ],
                                spacing=8,
                            ),
                        ),
                        _fields_grid(
                            pnl_fields,
                            only=(
                                "pnl_agent_commission_usd",
                                "pnl_swift_commission_usd",
                                "pnl_referral_commission_usd",
                                "repeat_payment_penalty_usd",
                            ),
                        ),
                    ],
                    spacing=12,
                ),
            )
        else:
            section_holder.content = _edit_section_card(
                title="Основные данные",
                subtitle="Клиент, даты, статус и реквизиты получателя.",
                content=_fields_grid(excel_fields, only=EDIT_GENERAL_FIELDS),
                header_trailing=status_flags,
            )

    def change_section(event: ft.ControlEvent) -> None:
        selected = list(event.control.selected or ["general"])
        set_section(selected[0] if selected else "general")
        context.page.update()

    section_switch.on_change = change_section
    set_section("general")

    def save(_: ft.ControlEvent) -> None:
        try:
            excel_updates = _parse_field_updates(excel_fields, EDIT_FIELD_SPECS)
            pnl_updates = _parse_field_updates(pnl_fields, PNL_MANUAL_FIELD_SPECS)
            _clear_unchanged_pulled_pnl_values(pnl_updates, pulled_auto_pnl_values)
            excel_updates["is_repeat_payment"] = bool(repeat_payment.value)
            excel_updates["is_refund"] = bool(refund.value)
            if is_new:
                missing = _missing_new_deal_fields(excel_fields, excel_updates)
                if missing:
                    _show_edit_error(
                        context,
                        "Заполните обязательные поля",
                        "Для ручного добавления сделки нужно заполнить:\n\n"
                        + "\n".join(f"• {item}" for item in missing),
                    )
                    return
            updated = replace(
                deal,
                **excel_updates,
                **pnl_updates,
                included_in_calc=True,
            )
            if is_new:
                updated = _prepare_manual_deal_for_insert(updated)
                updated = _fill_missing_pnl_defaults(context, updated)
                created_id = context.deals_repository.add(updated)
                updated = context.deals_repository.get(created_id) or replace(updated, id=created_id)
            else:
                context.deals_repository.update(updated)
            context.page.pop_dialog()
            on_saved(updated)
        except Exception as exc:
            _show_edit_error(context, "Не удалось сохранить сделку", str(exc))

    dialog = ft.AlertDialog(
        modal=True,
        title=None,
        content=ft.Container(
            width=1040,
            height=660,
            padding=12,
            bgcolor="#F8FAFC",
            border_radius=8,
            content=ft.Column(
                controls=[
                    _edit_dialog_header(deal),
                    ft.Container(
                        padding=ft.Padding(10, 6, 10, 6),
                        bgcolor=ui_theme.SURFACE,
                        border=ui_theme.border("#D8E2F0"),
                        border_radius=8,
                        content=section_switch,
                    ),
                    section_holder,
                ],
                spacing=8,
            ),
        ),
        actions=[
            ft.TextButton("\u0417\u0430\u043a\u0440\u044b\u0442\u044c", on_click=lambda _: _close_dialog(context, dialog)),
            ui_theme.primary_button(
                "\u0421\u043e\u0437\u0434\u0430\u0442\u044c" if is_new else "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c",
                icon=ft.Icons.ADD if is_new else ft.Icons.SAVE_OUTLINED,
                on_click=save,
            ),
        ],
    )
    context.page.show_dialog(dialog)


def _missing_new_deal_fields(fields: dict[str, EditControl], updates: dict[str, Any]) -> list[str]:
    """Return labels for required fields missing in manual deal creation."""
    missing: list[str] = []
    for attr in (*REQUIRED_NEW_GENERAL_FIELDS, *REQUIRED_NEW_RATES_FIELDS):
        if _is_missing_required_value(updates.get(attr)):
            missing.append(_field_label(fields.get(attr), attr))
    return missing


def _clear_unchanged_pulled_pnl_values(
    pnl_updates: dict[str, Any],
    pulled_auto_values: dict[str, float | None],
) -> None:
    """Keep pulled PnL values as automatic unless the user changed them manually."""
    for attr, pulled_value in pulled_auto_values.items():
        if attr not in pnl_updates:
            continue
        current_value = pnl_updates[attr]
        if _same_optional_number(current_value, pulled_value):
            pnl_updates[attr] = None


def _same_optional_number(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    try:
        return abs(float(left) - float(right)) <= 0.000001
    except (TypeError, ValueError):
        return False


def _is_missing_required_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _field_label(field: EditControl | None, fallback: str) -> str:
    data = getattr(field, "data", None)
    if isinstance(data, dict) and data.get("label"):
        return str(data["label"])
    label = getattr(field, "label", None)
    return str(label or fallback)


def _prepare_manual_deal_for_insert(deal: Deal) -> Deal:
    """Fill legacy required deal fields from the manually entered registry fields."""
    today = date.today().isoformat()
    trade_date = deal.client_fix_date or deal.request_date or today
    value_date = deal.agent_writeoff_date or trade_date
    currency = (deal.deal_currency or "USD").upper()
    amount = abs(float(deal.deal_amount or 0.0))
    is_export = float(deal.deal_amount or 0.0) < 0
    return replace(
        deal,
        trade_date=trade_date,
        value_date=value_date,
        operation_type="export" if is_export else "import",
        counterparty=deal.client_name or deal.receiver_company or deal.payment_agent or "Manual",
        currency_buy="USD" if is_export else currency,
        amount_buy=amount,
        currency_sell=currency if is_export else "USD",
        amount_sell=amount,
        rate_fact=float(deal.client_fix_rate or 0.0),
        commission=float(deal.fixed_commission_amount or 0.0) + float(deal.swift_amount or 0.0),
        portfolio=deal.payment_agent or "Manual",
        source_file=deal.source_file or "Ручной ввод",
        source_sheet=deal.source_sheet or "Реестр",
        customer_article_name=deal.customer_article_name or "Без банка",
        included_in_calc=True,
    )


def _fill_missing_pnl_defaults(context, deal: Deal) -> Deal:
    """Calculate PnL manual fields for a new deal; fallback to zero when calculation is impossible."""
    from app.ui.deals.table_view import (
        _client_percent_fee_usd,
        _referral_commission_result,
        _usd_component_or_zero,
    )

    calculated = {
        "pnl_client_percent_fee_usd": _client_percent_fee_usd(deal),
        "pnl_fixed_commission_usd": _usd_component_or_zero(
            deal.fixed_commission_amount,
            deal.fixed_commission_currency,
            deal,
        ),
        "pnl_swift_usd": _usd_component_or_zero(deal.swift_amount, deal.swift_currency, deal),
        "pnl_agent_commission_usd": _usd_component_or_zero(
            deal.agent_commission_amount,
            deal.agent_commission_currency,
            deal,
        ),
        "pnl_swift_commission_usd": _usd_component_or_zero(
            deal.swift_commission_amount,
            deal.swift_commission_currency,
            deal,
        ),
        "pnl_referral_commission_usd": _referral_commission_result(
            context,
            {"referral_rate_cache": {}, "active_referral_rules_cache": {}},
            deal,
        ).amount_usd,
    }
    updates = {
        attr: 0.0 if value is None else float(value)
        for attr, value in calculated.items()
        if getattr(deal, attr) is None
    }
    return replace(deal, **updates) if updates else deal


def _show_edit_error(context, title: str, message: str) -> None:
    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=ui_theme.SURFACE,
            barrier_color="#0F172A66",
            title=ft.Text(title),
            content=ft.Text(message, selectable=True),
            actions=[ft.TextButton("ОК", on_click=lambda _: context.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _delete_deal(context, deal: Deal, refresh) -> None:
    if deal.id is None:
        return
    context.deals_repository.delete(deal.id)
    refresh()


def _close_dialog(context, dialog: ft.AlertDialog) -> None:
    context.page.pop_dialog()

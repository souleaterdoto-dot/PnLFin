"""Rates registry screen."""

from __future__ import annotations

import calendar
from datetime import date

import flet as ft

from app.domain.models import Rate
from app.ui import theme as ui_theme


MONTH_NAMES = (
    "\u044f\u043d\u0432\u0430\u0440\u044c",
    "\u0444\u0435\u0432\u0440\u0430\u043b\u044c",
    "\u043c\u0430\u0440\u0442",
    "\u0430\u043f\u0440\u0435\u043b\u044c",
    "\u043c\u0430\u0439",
    "\u0438\u044e\u043d\u044c",
    "\u0438\u044e\u043b\u044c",
    "\u0430\u0432\u0433\u0443\u0441\u0442",
    "\u0441\u0435\u043d\u0442\u044f\u0431\u0440\u044c",
    "\u043e\u043a\u0442\u044f\u0431\u0440\u044c",
    "\u043d\u043e\u044f\u0431\u0440\u044c",
    "\u0434\u0435\u043a\u0430\u0431\u0440\u044c",
)
WEEKDAY_NAMES = (
    "\u041f\u043d",
    "\u0412\u0442",
    "\u0421\u0440",
    "\u0427\u0442",
    "\u041f\u0442",
    "\u0421\u0431",
    "\u0412\u0441",
)


def create_rates_view(context) -> ft.Control:
    """Create a full-page rates calendar with day drill-down."""
    today = date.today()
    state = {"year": today.year, "month": today.month, "selected_date": None}
    content_holder = ft.Container(expand=True)

    def render_calendar(update: bool = True) -> None:
        content_holder.content = _calendar_page(context, state, open_day, previous_month, next_month)
        if update:
            context.page.update()

    def render_day(day: date, update: bool = True) -> None:
        content_holder.content = _day_page(
            context,
            day,
            back_to_calendar,
            lambda: render_day(day),
        )
        if update:
            context.page.update()

    def refresh(update: bool = True) -> None:
        selected_date = state.get("selected_date")
        if selected_date:
            render_day(date.fromisoformat(str(selected_date)), update=update)
        else:
            render_calendar(update=update)

    def open_day(day: date) -> None:
        state["selected_date"] = day.isoformat()
        state["year"] = day.year
        state["month"] = day.month
        render_day(day)

    def back_to_calendar() -> None:
        state["selected_date"] = None
        render_calendar()

    def previous_month(_: ft.ControlEvent | None = None) -> None:
        state["selected_date"] = None
        year = int(state["year"])
        month = int(state["month"])
        if month == 1:
            state["year"] = year - 1
            state["month"] = 12
        else:
            state["month"] = month - 1
        render_calendar()

    def next_month(_: ft.ControlEvent | None = None) -> None:
        state["selected_date"] = None
        year = int(state["year"])
        month = int(state["month"])
        if month == 12:
            state["year"] = year + 1
            state["month"] = 1
        else:
            state["month"] = month + 1
        render_calendar()

    root = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("Rates", size=28, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                            ft.Text(
                                "\u041a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c "
                                "\u043a\u0443\u0440\u0441\u043e\u0432: \u0434\u043d\u0438 "
                                "\u0441 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043d\u044b\u043c\u0438 "
                                "\u043a\u0443\u0440\u0441\u0430\u043c\u0438 "
                                "\u043f\u043e\u0434\u0441\u0432\u0435\u0447\u0435\u043d\u044b.",
                                color=ui_theme.MUTED,
                            ),
                        ],
                        spacing=2,
                    ),
                    ft.Container(expand=True),
                    ui_theme.primary_button(
                        "\u0421\u0435\u0433\u043e\u0434\u043d\u044f",
                        icon=ft.Icons.TODAY_OUTLINED,
                        on_click=lambda _: _go_today(state, render_calendar),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content_holder,
        ],
        expand=True,
        spacing=14,
    )
    refresh(update=False)
    return root


def _calendar_page(context, state: dict, open_day, previous_month, next_month) -> ft.Control:
    year = int(state["year"])
    month = int(state["month"])
    counts = context.rates_repository.counts_by_date()
    month_matrix = calendar.monthcalendar(year, month)
    total_month_rates = sum(
        count
        for date_text, count in counts.items()
        if date_text.startswith(f"{year:04d}-{month:02d}-")
    )
    active_days = sum(
        1
        for date_text, count in counts.items()
        if count and date_text.startswith(f"{year:04d}-{month:02d}-")
    )

    return ft.Container(
        expand=True,
        padding=18,
        border_radius=22,
        bgcolor="#F7FAFF",
        border=ui_theme.border("#D8E7FA"),
        shadow=ft.BoxShadow(blur_radius=28, color="#2563EB10", offset=ft.Offset(0, 12)),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        _month_button(ft.Icons.CHEVRON_LEFT, "\u041f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0439 \u043c\u0435\u0441\u044f\u0446", previous_month),
                        ft.Text(
                            f"{MONTH_NAMES[month - 1].capitalize()} {year}",
                            size=24,
                            weight=ft.FontWeight.W_800,
                            color=ui_theme.TEXT,
                        ),
                        _month_button(ft.Icons.CHEVRON_RIGHT, "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u043c\u0435\u0441\u044f\u0446", next_month),
                        ft.Container(expand=True),
                        _calendar_metric("\u0414\u043d\u0435\u0439 \u0441 \u043a\u0443\u0440\u0441\u0430\u043c\u0438", str(active_days)),
                        _calendar_metric("\u0412\u0441\u0435\u0433\u043e \u043a\u0443\u0440\u0441\u043e\u0432", str(total_month_rates)),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[_weekday_header(name) for name in WEEKDAY_NAMES],
                    spacing=8,
                ),
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[_day_cell(year, month, day, counts, open_day) for day in week],
                            spacing=7,
                            expand=True,
                        )
                        for week in month_matrix
                    ],
                    spacing=7,
                    expand=True,
                ),
            ],
            spacing=12,
            expand=True,
        ),
    )


def _month_button(icon: str, tooltip: str, on_click) -> ft.IconButton:
    return ft.IconButton(
        icon,
        tooltip=tooltip,
        icon_color=ui_theme.PRIMARY,
        bgcolor="#EFF6FF",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=on_click,
    )


def _weekday_header(name: str) -> ft.Container:
    return ft.Container(
        expand=True,
        height=32,
        alignment=ft.Alignment.CENTER,
        content=ft.Text(name, size=12, weight=ft.FontWeight.W_700, color=ui_theme.MUTED),
    )


def _day_cell(year: int, month: int, day: int, counts: dict[str, int], open_day) -> ft.Control:
    if day == 0:
        return ft.Container(expand=True)
    current = date(year, month, day)
    key = current.isoformat()
    count = counts.get(key, 0)
    has_rates = count > 0
    is_today = current == date.today()
    tooltip = (
        f"{_format_date_ru(key)}: {count} \u043a\u0443\u0440\u0441\u043e\u0432"
        if has_rates
        else f"{_format_date_ru(key)}: \u043a\u0443\u0440\u0441\u043e\u0432 \u043d\u0435\u0442"
    )
    return ft.Container(
        expand=True,
        border_radius=16,
        padding=ft.Padding(10, 8, 10, 8),
        bgcolor="#FFFFFF" if not has_rates else "#EAF2FF",
        border=ui_theme.border("#2563EB" if is_today else "#8CB8FF" if has_rates else "#E6EEF8"),
        shadow=ft.BoxShadow(blur_radius=18, color="#2563EB14", offset=ft.Offset(0, 8)) if has_rates else None,
        tooltip=tooltip,
        ink=True,
        ink_color="#DBEAFE",
        on_click=lambda _, value=current: open_day(value),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            str(day),
                            size=18,
                            weight=ft.FontWeight.W_800,
                            color=ui_theme.PRIMARY if has_rates else ui_theme.TEXT,
                        ),
                        ft.Container(expand=True),
                        ft.Icon(ft.Icons.RADIO_BUTTON_CHECKED, size=12, color="#16A34A")
                        if has_rates
                        else ft.Container(width=12),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    height=22,
                    padding=ft.Padding(7, 2, 7, 2),
                    border_radius=999,
                    bgcolor="#DCEBFF" if has_rates else "#F4F7FB",
                    content=ft.Text(
                        f"{count} \u043a\u0443\u0440\u0441\u043e\u0432"
                        if has_rates
                        else "\u043d\u0435\u0442 \u043a\u0443\u0440\u0441\u043e\u0432",
                        size=11,
                        weight=ft.FontWeight.W_700 if has_rates else ft.FontWeight.W_500,
                        color=ui_theme.PRIMARY if has_rates else ui_theme.MUTED,
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=4,
            expand=True,
        ),
    )


def _day_page(context, selected_day: date, back_to_calendar, refresh_day) -> ft.Control:
    rates = context.rates_repository.list_by_date(selected_day.isoformat())
    return ft.Container(
        expand=True,
        padding=18,
        border_radius=22,
        bgcolor="#F8FBFF",
        border=ui_theme.border("#D8E2F0"),
        shadow=ft.BoxShadow(blur_radius=28, color="#0F172A12", offset=ft.Offset(0, 12)),
        content=ft.Column(
            controls=[
                _day_header(selected_day, len(rates), back_to_calendar),
                ft.ListView(
                    controls=[
                        _day_actions_panel(context, selected_day, refresh_day),
                        _rates_table(context, rates, refresh_day),
                    ],
                    spacing=14,
                    expand=True,
                    auto_scroll=False,
                ),
            ],
            spacing=14,
            expand=True,
        ),
    )


def _day_header(selected_day: date, rates_count: int, back_to_calendar) -> ft.Control:
    return ft.Row(
        controls=[
            ft.IconButton(
                ft.Icons.ARROW_BACK,
                tooltip="\u041d\u0430\u0437\u0430\u0434 \u0432 \u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c",
                icon_color=ui_theme.PRIMARY,
                bgcolor="#EFF6FF",
                on_click=lambda _: back_to_calendar(),
            ),
            ft.Column(
                controls=[
                    ft.Text(
                        f"\u041a\u0443\u0440\u0441\u044b \u043d\u0430 {_format_date_ru(selected_day.isoformat())}",
                        size=24,
                        weight=ft.FontWeight.W_800,
                        color=ui_theme.TEXT,
                    ),
                    ft.Text(
                        f"\u0417\u0430\u043f\u0438\u0441\u0435\u0439 \u043a\u0443\u0440\u0441\u043e\u0432: {rates_count}",
                        color=ui_theme.MUTED,
                    ),
                ],
                spacing=1,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _day_actions_panel(context, selected_day: date, refresh_day) -> ft.Control:
    rate_date = ft.TextField(
        label="\u0414\u0430\u0442\u0430 \u043a\u0443\u0440\u0441\u0430",
        value=selected_day.isoformat(),
        dense=True,
        width=150,
    )
    currency = ft.TextField(label="\u0412\u0430\u043b\u044e\u0442\u0430", value="USD", dense=True, width=105)
    value = ft.TextField(label="\u041a\u0443\u0440\u0441 \u043a RUB", dense=True, width=130)
    for field in (rate_date, currency, value):
        _style_field(field)

    def add_manual(_: ft.ControlEvent) -> None:
        try:
            context.rates_service.add_manual_rate(rate_date.value, currency.value, float(value.value))
            value.value = ""
            _snackbar(context, "\u041a\u0443\u0440\u0441 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d.")
            refresh_day()
        except Exception as exc:
            _snackbar(context, str(exc))

    def sync_cbr(_: ft.ControlEvent) -> None:
        try:
            count = context.rates_service.sync_cbr_rates(rate_date.value)
            _snackbar(
                context,
                f"\u0417\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043e {count} "
                f"\u043a\u0443\u0440\u0441\u043e\u0432 \u0438\u0437 \u0426\u0411 "
                f"\u0437\u0430 {_format_date_ru(rate_date.value)}.",
            )
            refresh_day()
        except Exception as exc:
            _snackbar(context, str(exc))

    return ft.Container(
        padding=ft.Padding(14, 12, 14, 12),
        border_radius=18,
        bgcolor="#FFFFFF",
        border=ui_theme.border("#D8E2F0"),
        shadow=ft.BoxShadow(blur_radius=18, color="#0F172A0D", offset=ft.Offset(0, 8)),
        content=ft.Row(
            controls=[
                ft.Container(
                    width=34,
                    height=34,
                    border_radius=12,
                    bgcolor="#EFF6FF",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.ADD_CHART_OUTLINED, size=18, color=ui_theme.PRIMARY),
                ),
                ft.Text(
                    "\u0414\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u043a\u0443\u0440\u0441\u043e\u0432",
                    size=13,
                    weight=ft.FontWeight.W_800,
                    color=ui_theme.TEXT,
                ),
                rate_date,
                currency,
                value,
                ft.FilledButton(
                    "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c",
                    icon=ft.Icons.ADD,
                    height=40,
                    style=ft.ButtonStyle(
                        bgcolor=ui_theme.PRIMARY,
                        color="#FFFFFF",
                        padding=ft.Padding(14, 0, 14, 0),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=add_manual,
                ),
                ft.OutlinedButton(
                    "\u0417\u0430\u0431\u0440\u0430\u0442\u044c \u0438\u0437 \u0426\u0411",
                    icon=ft.Icons.CLOUD_SYNC_OUTLINED,
                    height=40,
                    style=ft.ButtonStyle(
                        padding=ft.Padding(14, 0, 14, 0),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=sync_cbr,
                ),
            ],
            wrap=True,
            spacing=10,
            run_spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _rates_table(context, rates: list[Rate], refresh) -> ft.Control:
    if not rates:
        return ft.Container(
            height=260,
            alignment=ft.Alignment.CENTER,
            bgcolor="#FFFFFF",
            border_radius=18,
            border=ui_theme.border("#E2E8F0"),
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.EVENT_BUSY_OUTLINED, size=42, color=ui_theme.MUTED),
                    ft.Text(
                        "\u041a\u0443\u0440\u0441\u043e\u0432 \u043d\u0430 \u044d\u0442\u043e\u0442 \u0434\u0435\u043d\u044c \u043d\u0435\u0442",
                        size=16,
                        weight=ft.FontWeight.W_700,
                        color=ui_theme.TEXT,
                    ),
                    ft.Text(
                        "\u0414\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u043a\u0443\u0440\u0441 "
                        "\u0432\u0440\u0443\u0447\u043d\u0443\u044e \u0438\u043b\u0438 "
                        "\u0437\u0430\u0431\u0435\u0440\u0438\u0442\u0435 \u0435\u0433\u043e \u0438\u0437 \u0426\u0411.",
                        color=ui_theme.MUTED,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
        )

    rows = [
        ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(rate.currency, weight=ft.FontWeight.W_700, color=ui_theme.TEXT)),
                ft.DataCell(ft.Text(_format_rate(rate.rate_to_rub), color=ui_theme.TEXT)),
                ft.DataCell(_source_badge(rate.source)),
                ft.DataCell(ft.Text(_format_created_at(rate.created_at), color=ui_theme.MUTED)),
                ft.DataCell(
                    ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip="\u0420\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c",
                                icon_color=ui_theme.PRIMARY,
                                on_click=lambda _, item=rate: _open_rate_dialog(context, item, refresh),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="\u0423\u0434\u0430\u043b\u0438\u0442\u044c",
                                icon_color=ui_theme.DANGER,
                                on_click=lambda _, item=rate: _delete_rate(context, item, refresh),
                            ),
                        ],
                        spacing=0,
                    )
                ),
            ]
        )
        for rate in rates
    ]
    return ft.Container(
        height=max(280, min(620, 92 + len(rates) * 58)),
        bgcolor="#FFFFFF",
        border_radius=18,
        border=ui_theme.border("#E2E8F0"),
        padding=10,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("\u0412\u0430\u043b\u044e\u0442\u0430")),
                                ft.DataColumn(ft.Text("\u041a\u0443\u0440\u0441 \u043a RUB"), numeric=True),
                                ft.DataColumn(ft.Text("\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a")),
                                ft.DataColumn(ft.Text("\u0421\u043e\u0437\u0434\u0430\u043d\u043e")),
                                ft.DataColumn(ft.Text("\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u044f")),
                            ],
                            rows=rows,
                            bgcolor=ui_theme.SURFACE,
                            heading_row_color=ui_theme.PRIMARY_SOFT,
                            heading_text_style=ft.TextStyle(color=ui_theme.TEXT, weight=ft.FontWeight.W_700),
                            horizontal_lines=ft.BorderSide(1, ui_theme.BORDER),
                            border=ui_theme.border("#D8E2F0"),
                            border_radius=12,
                        )
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def _open_rate_dialog(context, rate: Rate, refresh) -> None:
    rate_date = ft.TextField(label="\u0414\u0430\u0442\u0430", value=rate.rate_date)
    currency = ft.TextField(label="\u0412\u0430\u043b\u044e\u0442\u0430", value=rate.currency)
    value = ft.TextField(label="\u041a\u0443\u0440\u0441 \u043a RUB", value=str(rate.rate_to_rub))
    source = ft.TextField(label="\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a", value=rate.source)
    for field in (rate_date, currency, value, source):
        _style_dialog_field(field)

    def save(_: ft.ControlEvent) -> None:
        try:
            context.rates_repository.update(
                Rate(
                    id=rate.id,
                    rate_date=rate_date.value,
                    currency=currency.value,
                    rate_to_rub=float(value.value),
                    source=source.value,
                    created_at=rate.created_at,
                )
            )
            context.page.pop_dialog()
            refresh()
        except Exception as exc:
            _snackbar(context, str(exc))

    dialog = ft.AlertDialog(
        modal=True,
        content=ft.Container(
            width=520,
            padding=0,
            border_radius=24,
            bgcolor="#F8FBFF",
            border=ui_theme.border("#D8E7FA"),
            shadow=ft.BoxShadow(blur_radius=28, color="#0F172A18", offset=ft.Offset(0, 14)),
            content=ft.Column(
                controls=[
                    ft.Container(
                        padding=ft.Padding(18, 16, 14, 14),
                        border_radius=20,
                        bgcolor="#EFF6FF",
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    width=42,
                                    height=42,
                                    border_radius=14,
                                    bgcolor=ui_theme.PRIMARY,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.EDIT_OUTLINED, size=20, color="#FFFFFF"),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "\u0420\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043a\u0443\u0440\u0441",
                                            size=18,
                                            weight=ft.FontWeight.W_800,
                                            color=ui_theme.TEXT,
                                        ),
                                        ft.Text(
                                            f"ID #{rate.id} \u00b7 {_format_date_ru(rate.rate_date)} \u00b7 {rate.currency}",
                                            size=12,
                                            color=ui_theme.MUTED,
                                        ),
                                    ],
                                    spacing=1,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    tooltip="\u0417\u0430\u043a\u0440\u044b\u0442\u044c",
                                    icon_color=ui_theme.MUTED,
                                    on_click=lambda _: _close_dialog(context),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Container(
                        padding=ft.Padding(18, 16, 18, 8),
                        content=ft.Column(
                            controls=[
                                ft.Row([rate_date, currency], spacing=12),
                                ft.Row([value, source], spacing=12),
                            ],
                            spacing=12,
                            tight=True,
                        ),
                    ),
                    ft.Container(
                        padding=ft.Padding(18, 8, 18, 18),
                        content=ft.Row(
                            controls=[
                                ft.Container(expand=True),
                                ft.OutlinedButton(
                                    "\u041e\u0442\u043c\u0435\u043d\u0430",
                                    height=40,
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(18, 0, 18, 0),
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                    ),
                                    on_click=lambda _: _close_dialog(context),
                                ),
                                ft.FilledButton(
                                    "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c",
                                    icon=ft.Icons.SAVE_OUTLINED,
                                    height=40,
                                    style=ft.ButtonStyle(
                                        bgcolor=ui_theme.PRIMARY,
                                        color="#FFFFFF",
                                        padding=ft.Padding(18, 0, 18, 0),
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                    ),
                                    on_click=save,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                spacing=0,
                tight=True,
            ),
        ),
    )
    context.page.show_dialog(dialog)


def _delete_rate(context, rate: Rate, refresh) -> None:
    if rate.id is not None:
        context.rates_repository.delete(rate.id)
        refresh()


def _calendar_metric(label: str, value: str) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(14, 8, 14, 8),
        border_radius=14,
        bgcolor="#FFFFFF",
        border=ui_theme.border("#D8E2F0"),
        content=ft.Column(
            controls=[
                ft.Text(label, size=11, color=ui_theme.MUTED),
                ft.Text(value, size=18, weight=ft.FontWeight.W_800, color=ui_theme.PRIMARY),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _source_badge(source: str) -> ft.Container:
    is_manual = source.casefold() == "manual"
    return ft.Container(
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=999,
        bgcolor="#DCFCE7" if is_manual else "#DBEAFE",
        content=ft.Text(
            source,
            size=11,
            weight=ft.FontWeight.W_700,
            color="#166534" if is_manual else ui_theme.PRIMARY,
        ),
    )


def _style_field(field: ft.TextField) -> None:
    field.height = 42
    field.filled = True
    field.fill_color = "#F8FBFF"
    field.border_color = "#D8E2F0"
    field.focused_border_color = ui_theme.PRIMARY
    field.border_radius = 12
    field.text_size = 12
    field.label_style = ft.TextStyle(size=11, color=ui_theme.MUTED)
    field.content_padding = ft.Padding(12, 7, 12, 7)


def _style_dialog_field(field: ft.TextField) -> None:
    field.expand = True
    field.height = 52
    field.filled = True
    field.fill_color = "#FFFFFF"
    field.border_color = "#D8E2F0"
    field.focused_border_color = ui_theme.PRIMARY
    field.border_radius = 14
    field.text_size = 13
    field.label_style = ft.TextStyle(size=12, color=ui_theme.MUTED)
    field.content_padding = ft.Padding(14, 9, 14, 9)


def _go_today(state: dict, refresh) -> None:
    today = date.today()
    state["selected_date"] = None
    state["year"] = today.year
    state["month"] = today.month
    refresh()


def _close_dialog(context) -> None:
    context.page.pop_dialog()


def _snackbar(context, message: str) -> None:
    context.page.show_dialog(ft.SnackBar(ft.Text(message)))


def _format_date_ru(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def _format_created_at(value: str | None) -> str:
    if not value:
        return "-"
    return value.split("T", 1)[0]


def _format_rate(value: float) -> str:
    return f"{value:,.4f}".replace(",", " ").replace(".", ",")

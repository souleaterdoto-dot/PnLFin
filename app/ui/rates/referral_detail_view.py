"""Referral detail screen with separated rate condition tables."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import flet as ft

from app.database.connection import APP_DATA_DIR
from app.domain.rate_models import RateCondition, Referral
from app.ui.asset_loader import image_source
from app.ui import theme as ui_theme
from app.ui.rates.rate_condition_form import open_rate_condition_form


ActiveFilter = str

SECTIONS = (
    {
        "title": "Ставки от эквивалента USD",
        "subtitle": "Процент и фиксированная комиссия в одном условии. Диапазон суммы проверяется в USD.",
        "amount_basis": "usd_equivalent",
        "icon": ft.Icons.PERCENT,
    },
    {
        "title": "Ставки в валюте сделки",
        "subtitle": "Процент и фиксированная комиссия в одном условии. Диапазон суммы проверяется в валюте сделки.",
        "amount_basis": "deal_currency",
        "icon": ft.Icons.PERCENT,
    },
)


def create_referral_detail_view(
    context,
    referral: Referral,
    on_back: Callable[[], None],
    conflict_id: int | None = None,
    message: str = "",
) -> ft.Control:
    """Create a fresh referral detail page."""
    current_referral = _reload_referral(context, referral)

    def rebuild(
        next_conflict_id: int | None = None,
        next_message: str = "",
    ) -> None:
        context.set_content(
            create_referral_detail_view(
                context=context,
                referral=current_referral,
                on_back=on_back,
                conflict_id=next_conflict_id,
                message=next_message,
            )
        )

    def add_condition(amount_basis: str):
        def handler(_: ft.ControlEvent) -> None:
            open_rate_condition_form(
                context,
                current_referral,
                lambda saved_conflict_id=None, saved_message=None: rebuild(
                    next_conflict_id=saved_conflict_id,
                    next_message=saved_message or "",
                ),
                fixed_amount_basis=amount_basis,
                fixed_commission_type="mixed",
            )

        return handler

    def edit_condition(condition: RateCondition) -> None:
        open_rate_condition_form(
            context,
            current_referral,
            lambda saved_conflict_id=None, saved_message=None: rebuild(
                next_conflict_id=saved_conflict_id,
                next_message=saved_message or "",
            ),
            condition,
            fixed_amount_basis=condition.amount_basis,
            fixed_commission_type=condition.commission_type,
        )

    def delete_condition(condition: RateCondition) -> None:
        if condition.id is not None:
            context.rate_conditions_service.delete(condition.id)
            rebuild()

    def edit_referral(_: ft.ControlEvent) -> None:
        _open_referral_form(context, current_referral, lambda: rebuild())

    def delete_referral(_: ft.ControlEvent) -> None:
        _open_delete_referral_dialog(context, current_referral, on_back)

    def open_archive(_: ft.ControlEvent) -> None:
        _open_archive_dialog(
            context=context,
            referral=current_referral,
            conditions=_load_archived_conditions(context, current_referral),
            on_edit=edit_condition,
            on_delete=delete_condition,
        )

    file_picker = ft.FilePicker()

    async def import_conditions(_: ft.ControlEvent) -> None:
        files = await file_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx", "xlsm"],
        )
        if not files or not files[0].path:
            return
        try:
            result = await asyncio.to_thread(context.rate_conditions_excel_service.import_file, files[0].path)
            context.referrals_service.sync_from_deals()
            rebuild(
                next_message=(
                    "\u0418\u043c\u043f\u043e\u0440\u0442 \u0441\u0442\u0430\u0432\u043e\u043a: "
                    f"{result.rows_success} \u0443\u0441\u043f\u0435\u0448\u043d\u043e, "
                    f"{result.rows_failed} \u0441 \u043e\u0448\u0438\u0431\u043a\u0430\u043c\u0438."
                    + (f" {'; '.join(result.errors[:3])}" if result.errors else "")
                )
            )
        except Exception as exc:
            rebuild(next_message=str(exc))

    def show_example(_: ft.ControlEvent) -> None:
        try:
            path = context.rate_conditions_excel_service.create_example_file(
                Path(APP_DATA_DIR) / "rate_conditions_import_example.xlsx"
            )
            os.startfile(path)
        except Exception as exc:
            rebuild(next_message=str(exc))

    conditions = _load_conditions(
        context=context,
        referral=current_referral,
    )
    archived_count = len(_load_archived_conditions(context, current_referral))

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                _title_bar(current_referral, on_back, edit_referral, delete_referral, len(conditions)),
                _conditions_panel(
                    conditions=conditions,
                    conflict_id=conflict_id,
                    message=message,
                    archived_count=archived_count,
                    on_add=add_condition,
                    on_edit=edit_condition,
                    on_delete=delete_condition,
                    on_archive=open_archive,
                    on_import=import_conditions,
                    on_example=show_example,
                ),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
    )


def _reload_referral(context, referral: Referral) -> Referral:
    if referral.id is None:
        return referral
    fresh = context.referrals_repository.get(int(referral.id))
    return fresh or referral


def _load_conditions(
    context,
    referral: Referral,
) -> list[RateCondition]:
    active_conditions = context.rate_conditions_service.list(
        referral_id=int(referral.id or 0),
        active=True,
    )
    today = date.today()
    return [
        condition
        for condition in active_conditions
        if _condition_is_current_on(condition, today)
    ]


def _load_archived_conditions(context, referral: Referral) -> list[RateCondition]:
    all_conditions = context.rate_conditions_service.list(
        referral_id=int(referral.id or 0),
        active=None,
    )
    today = date.today()
    return [
        condition
        for condition in all_conditions
        if not condition.is_active or not _condition_is_current_on(condition, today)
    ]


def _condition_is_current_on(condition: RateCondition, current_date: date) -> bool:
    start = _parse_date(condition.date_from, date.min)
    end = _parse_date(condition.date_to, date.max)
    return start <= current_date <= end


def _parse_date(value: str | None, default: date) -> date:
    text = str(value or "").strip()
    if not text:
        return default
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text)
    except ValueError:
        return default


def _title_bar(referral: Referral, on_back, on_edit_referral, on_delete_referral, current_count: int) -> ft.Control:
    status_color = "#DCFCE7" if referral.is_active else "#E2E8F0"
    status_text = "Активен" if referral.is_active else "Неактивен"
    return ft.Row(
        controls=[
            ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Назад", on_click=lambda _: on_back()),
            _referral_logo(referral),
            ft.Column(
                controls=[
                    ft.Text(f"Ставки / {referral.name}", size=26, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                    ft.Text(f"Код: {referral.code} · Действуют сегодня: {current_count}", color=ui_theme.MUTED),
                ],
                spacing=1,
                expand=True,
            ),
            ft.Container(
                padding=ft.Padding(10, 5, 10, 5),
                border_radius=999,
                bgcolor=status_color,
                content=ft.Text(status_text, size=12, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
            ),
            ft.OutlinedButton("Редактировать", icon=ft.Icons.EDIT_OUTLINED, on_click=on_edit_referral),
            ft.OutlinedButton("Удалить", icon=ft.Icons.DELETE_OUTLINE, on_click=on_delete_referral),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _referral_logo(referral: Referral) -> ft.Control:
    logo_src = image_source(referral.logo_path)
    if logo_src:
        return ft.Container(
            width=42,
            height=42,
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            bgcolor=ui_theme.PRIMARY_SOFT,
            content=ft.Image(
                src=logo_src,
                width=42,
                height=42,
                fit="cover",
                error_content=_fallback_referral_logo(),
            ),
        )
    return _fallback_referral_logo()


def _fallback_referral_logo() -> ft.Container:
    return ft.Container(
        width=42,
        height=42,
        border_radius=10,
        bgcolor=ui_theme.PRIMARY_SOFT,
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, color=ui_theme.PRIMARY, size=22),
    )


def _conditions_panel(
    conditions: list[RateCondition],
    conflict_id: int | None,
    message: str,
    archived_count: int,
    on_add,
    on_edit,
    on_delete,
    on_archive,
    on_import,
    on_example,
) -> ft.Control:
    return ft.Column(
        controls=[
            ui_theme.panel(
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text("Условия ставок", size=18, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                                ft.OutlinedButton(
                                    f"Архив ({archived_count})",
                                    icon=ft.Icons.ARCHIVE_OUTLINED,
                                    on_click=on_archive,
                                ),
                                ft.OutlinedButton(
                                    "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043f\u0440\u0438\u043c\u0435\u0440",
                                    icon=ft.Icons.TABLE_VIEW_OUTLINED,
                                    on_click=on_example,
                                ),
                                ui_theme.primary_button(
                                    "\u0418\u043c\u043f\u043e\u0440\u0442 Excel",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    on_click=on_import,
                                ),
                            ],
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        _message(message),
                    ],
                    spacing=12,
                    tight=True,
                ),
                padding=16,
            ),
            *[
                _condition_table_section(
                    title=str(section["title"]),
                    subtitle=str(section["subtitle"]),
                    icon=section["icon"],
                    amount_basis=str(section["amount_basis"]),
                    conditions=_section_conditions(
                        conditions,
                        amount_basis=str(section["amount_basis"]),
                    ),
                    conflict_id=conflict_id,
                    on_add=on_add(str(section["amount_basis"])),
                    on_edit=on_edit,
                    on_delete=on_delete,
                )
                for section in SECTIONS
            ],
        ],
        spacing=14,
        expand=True,
    )


def _open_archive_dialog(
    context,
    referral: Referral,
    conditions: list[RateCondition],
    on_edit,
    on_delete,
) -> None:
    def edit_archived(condition: RateCondition) -> None:
        context.page.pop_dialog()
        on_edit(condition)

    def delete_archived(condition: RateCondition) -> None:
        context.page.pop_dialog()
        on_delete(condition)

    content_controls: list[ft.Control]
    if conditions:
        content_controls = [
            _archive_section(
                title=str(section["title"]),
                conditions=_section_conditions(
                    conditions,
                    amount_basis=str(section["amount_basis"]),
                ),
                on_edit=edit_archived,
                on_delete=delete_archived,
            )
            for section in SECTIONS
            if _section_conditions(
                conditions,
                amount_basis=str(section["amount_basis"]),
            )
        ]
    else:
        content_controls = [
            ft.Container(
                padding=ft.Padding(18, 18, 18, 18),
                border=ui_theme.border("#D8E2F0"),
                border_radius=10,
                bgcolor=ui_theme.SURFACE,
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ARCHIVE_OUTLINED, color=ui_theme.PRIMARY),
                        ft.Text("В архиве пока нет условий", color=ui_theme.MUTED),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        ]

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Архив условий / {referral.name}", weight=ft.FontWeight.W_700),
        content=ft.Container(
            width=820,
            height=620,
            content=ft.Column(
                controls=content_controls,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            ft.TextButton("Закрыть", on_click=lambda _: context.page.pop_dialog()),
        ],
    )
    context.page.show_dialog(dialog)


def _archive_section(title: str, conditions: list[RateCondition], on_edit, on_delete) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(14, 12, 14, 14),
        border=ui_theme.border("#D8E2F0"),
        border_radius=10,
        bgcolor=ui_theme.SURFACE,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                        _count_badge(len(conditions)),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    controls=[
                        _archive_condition_card(
                            condition=condition,
                            on_edit=on_edit,
                            on_delete=on_delete,
                        )
                        for condition in conditions
                    ],
                    spacing=10,
                    tight=True,
                ),
            ],
            spacing=10,
            tight=True,
        ),
    )


def _archive_condition_card(condition: RateCondition, on_edit, on_delete) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(14, 12, 14, 12),
        border=ui_theme.border("#D8E2F0"),
        border_radius=10,
        bgcolor="#F8FAFC",
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    f"{condition.currency or 'Любая валюта'} · {_amount_range(condition)}",
                                    size=15,
                                    weight=ft.FontWeight.W_700,
                                    color=ui_theme.TEXT,
                                ),
                                ft.Text(f"Период: {_period(condition)}", size=12, color=ui_theme.MUTED),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        _status_badge(condition.is_active),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Row(
                    controls=[
                        _archive_metric("Процент", _percent_label(condition)),
                        _archive_metric("Валюта %", condition.percent_commission_currency or "Валюта сделки"),
                        _archive_metric("Фикс", _fixed_label(condition)),
                        _archive_metric("Валюта фикса", condition.fixed_commission_currency or "Валюта сделки"),
                    ],
                    spacing=8,
                    wrap=True,
                ),
                ft.Container(
                    visible=bool(condition.comment),
                    padding=ft.Padding(10, 8, 10, 8),
                    border_radius=8,
                    bgcolor=ui_theme.SURFACE,
                    border=ui_theme.border("#E2E8F0"),
                    content=ft.Text(condition.comment or "", size=12, color=ui_theme.MUTED),
                ),
                ft.Row(
                    controls=[
                        ft.OutlinedButton(
                            "Редактировать",
                            icon=ft.Icons.EDIT_OUTLINED,
                            on_click=lambda _: on_edit(condition),
                        ),
                        ft.OutlinedButton(
                            "Удалить",
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=lambda _: on_delete(condition),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                    spacing=8,
                ),
            ],
            spacing=10,
            tight=True,
        ),
    )


def _archive_metric(label: str, value: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(10, 7, 10, 7),
        border_radius=8,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#E2E8F0"),
        content=ft.Column(
            controls=[
                ft.Text(label, size=11, color=ui_theme.MUTED),
                ft.Text(value, size=13, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
            ],
            spacing=1,
            tight=True,
        ),
    )


def _section_conditions(
    conditions: list[RateCondition],
    amount_basis: str,
) -> list[RateCondition]:
    return [
        condition
        for condition in conditions
        if _amount_basis(condition) == amount_basis
    ]


def _condition_table_section(
    title: str,
    subtitle: str,
    icon,
    amount_basis: str,
    conditions: list[RateCondition],
    conflict_id: int | None,
    on_add,
    on_edit,
    on_delete,
) -> ft.Control:
    return ui_theme.panel(
        ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            width=42,
                            height=42,
                            border_radius=10,
                            bgcolor=ui_theme.PRIMARY_SOFT,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=ui_theme.PRIMARY, size=22),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(title, size=17, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                                ft.Text(subtitle, size=12, color=ui_theme.MUTED),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                        _count_badge(len(conditions)),
                        ui_theme.primary_button("Добавить", icon=ft.Icons.ADD, on_click=on_add),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                _conditions_table(
                    conditions=conditions,
                    conflict_id=conflict_id,
                    amount_basis=amount_basis,
                    on_add=on_add,
                    on_edit=on_edit,
                    on_delete=on_delete,
                ),
            ],
            spacing=12,
            tight=True,
        ),
        padding=16,
    )


def _conditions_table(
    conditions: list[RateCondition],
    conflict_id: int | None,
    amount_basis: str,
    on_add,
    on_edit,
    on_delete,
) -> ft.Control:
    if not conditions:
        return _empty_table(amount_basis, on_add)

    return ft.Container(
        border=ui_theme.border("#D8E2F0"),
        border_radius=10,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        bgcolor=ui_theme.SURFACE,
        content=ft.Column(
            controls=[
                _table_header(),
                ft.Container(
                    height=min(390, max(120, len(conditions) * 52 + len(_condition_currency_groups(conditions)) * 36)),
                    content=ft.Column(
                        controls=_grouped_condition_controls(
                            conditions=conditions,
                            conflict_id=conflict_id,
                            on_edit=on_edit,
                            on_delete=on_delete,
                        ),
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ),
            ],
            spacing=0,
            tight=True,
        ),
    )


def _grouped_condition_controls(
    conditions: list[RateCondition],
    conflict_id: int | None,
    on_edit,
    on_delete,
) -> list[ft.Control]:
    controls: list[ft.Control] = []
    for currency, items in _condition_currency_groups(conditions):
        controls.append(_currency_group_header(currency, len(items)))
        controls.extend(
            _condition_row(
                condition=condition,
                conflicted=condition.id == conflict_id,
                on_edit=on_edit,
                on_delete=on_delete,
            )
            for condition in items
        )
    return controls


def _condition_currency_groups(conditions: list[RateCondition]) -> list[tuple[str, list[RateCondition]]]:
    grouped: dict[str, list[RateCondition]] = {}
    for condition in conditions:
        key = str(condition.currency or "Любая валюта").strip().upper() or "Любая валюта"
        grouped.setdefault(key, []).append(condition)
    return sorted(grouped.items(), key=lambda item: (_currency_sort_key(item[0]), item[0]))


def _currency_sort_key(currency: str) -> int:
    priority = {
        "USD": 0,
        "EUR": 1,
        "CNY": 2,
        "CNH": 3,
        "AED": 4,
        "USDT": 5,
        "RUB": 6,
        "ЛЮБАЯ ВАЛЮТА": 99,
    }
    return priority.get(str(currency or "").upper(), 50)


def _currency_group_header(currency: str, count: int) -> ft.Control:
    return ft.Container(
        height=36,
        bgcolor="#F8FAFC",
        border=ft.Border(bottom=ft.BorderSide(1, "#E2E8F0")),
        padding=ft.Padding(10, 0, 10, 0),
        content=ft.Row(
            controls=[
                ft.Container(
                    width=24,
                    height=24,
                    border_radius=8,
                    bgcolor="#DBEAFE",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.INFO_OUTLINED, size=15, color=ui_theme.PRIMARY),
                ),
                ft.Text(currency, size=13, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                ft.Container(
                    padding=ft.Padding(7, 3, 7, 3),
                    border_radius=999,
                    bgcolor="#EFF6FF",
                    content=ft.Text(f"{count} условий", size=11, weight=ft.FontWeight.W_700, color=ui_theme.PRIMARY),
                ),
                ft.Text(
                    "условия ниже применяются только для этой валюты",
                    size=11,
                    color=ui_theme.MUTED,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _icon_action(icon, tooltip: str, bgcolor: str, color: str, on_click) -> ft.Control:
    return ft.Container(
        width=34,
        height=34,
        border_radius=9,
        bgcolor=bgcolor,
        border=ui_theme.border("#E2E8F0"),
        content=ft.IconButton(
            icon,
            icon_size=17,
            icon_color=color,
            tooltip=tooltip,
            on_click=on_click,
        ),
    )


def _table_header() -> ft.Control:
    return ft.Container(
        height=44,
        bgcolor="#F1F5F9",
        border=ft.Border(bottom=ft.BorderSide(1, "#D8E2F0")),
        content=ft.Row(
            controls=[
                _cell("Условие", 250, header=True),
                _cell("Период", 170, header=True),
                _cell("%", 74, header=True, numeric=True),
                _cell("Фикс", 86, header=True, numeric=True),
                _cell("Валюты", 120, header=True),
                _cell("Статус", 96, header=True),
                _cell("Комментарий", 170, header=True),
                _cell("", 82, header=True),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _condition_row(condition: RateCondition, conflicted: bool, on_edit, on_delete) -> ft.Control:
    return ft.Container(
        height=52,
        bgcolor="#FFF7ED" if conflicted else ui_theme.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, "#D8E2F0")),
        content=ft.Row(
            controls=[
                _condition_cell(condition),
                _cell(_period(condition), 170),
                _cell(_percent_label(condition), 74, numeric=True, accent=True),
                _cell(_fixed_label(condition), 86, numeric=True),
                _cell(_currency_pair(condition), 120),
                ft.Container(width=96, padding=ft.Padding(8, 0, 8, 0), content=_status_badge(condition.is_active)),
                _cell(condition.comment or "-", 170),
                ft.Container(
                    width=82,
                    padding=ft.Padding(4, 0, 4, 0),
                    content=ft.Row(
                        controls=[
                            _icon_action(ft.Icons.EDIT_OUTLINED, "Редактировать", "#EFF6FF", ui_theme.PRIMARY, lambda _: on_edit(condition)),
                            _icon_action(ft.Icons.DELETE_OUTLINE, "Удалить", "#FEF2F2", ui_theme.DANGER, lambda _: on_delete(condition)),
                        ],
                        spacing=5,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _condition_cell(condition: RateCondition) -> ft.Control:
    return ft.Container(
        width=250,
        padding=ft.Padding(10, 0, 8, 0),
        content=ft.Column(
            controls=[
                ft.Text(
                    f"{condition.currency or 'Любая валюта'} · {_amount_range(condition)}",
                    size=13,
                    weight=ft.FontWeight.W_700,
                    color=ui_theme.TEXT,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(_operation_type_label(condition.operation_type), size=11, color=ui_theme.MUTED),
            ],
            spacing=0,
            tight=True,
        ),
    )


def _empty_table(amount_basis: str, on_add) -> ft.Control:
    description = "Нет условий"
    basis = "eq. USD" if amount_basis == "usd_equivalent" else "в валюте сделки"
    return ft.Container(
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#D8E2F0"),
        border_radius=10,
        padding=ft.Padding(16, 14, 16, 14),
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.INFO_OUTLINED, color=ui_theme.PRIMARY, size=22),
                ft.Column(
                    controls=[
                        ft.Text(description, size=15, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                        ft.Text(f"Добавьте первое условие для диапазона {basis}.", size=12, color=ui_theme.MUTED),
                    ],
                    spacing=1,
                    expand=True,
                ),
                ft.OutlinedButton("Добавить", icon=ft.Icons.ADD, on_click=on_add),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _cell(value: str, width: int, header: bool = False, numeric: bool = False, accent: bool = False) -> ft.Control:
    return ft.Container(
        width=width,
        padding=ft.Padding(8, 0, 8, 0),
        alignment=ft.Alignment.CENTER_RIGHT if numeric else ft.Alignment.CENTER_LEFT,
        content=ft.Text(
            value,
            size=12 if header else 13,
            weight=ft.FontWeight.W_700 if header else None,
            color=ui_theme.PRIMARY if accent and not header else ui_theme.TEXT,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )


def _count_badge(count: int) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(9, 4, 9, 4),
        border_radius=999,
        bgcolor="#EFF6FF",
        content=ft.Text(f"{count} условий", size=12, weight=ft.FontWeight.W_700, color=ui_theme.PRIMARY),
    )


def _status_badge(active: bool) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=999,
        bgcolor="#DCFCE7" if active else "#E2E8F0",
        content=ft.Text(
            "Активно" if active else "Неактивно",
            size=11,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.GREEN_700 if active else ui_theme.MUTED,
        ),
    )


def _filter_button(label: str, selected: bool, on_click) -> ft.Control:
    if selected:
        return ft.FilledButton(label, on_click=on_click, bgcolor=ui_theme.PRIMARY, color=ft.Colors.WHITE)
    return ft.OutlinedButton(label, on_click=on_click)


def _message(value: str) -> ft.Control:
    if not value:
        return ft.Container(visible=False)
    lines = [line.strip() for line in str(value).splitlines() if line.strip()]
    if lines and lines[0] == "Конфликт условий ставок":
        return ft.Container(
            bgcolor="#FFF7ED",
            border=ui_theme.border("#FDBA74"),
            border_radius=10,
            padding=ft.Padding(14, 12, 14, 12),
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=38,
                        height=38,
                        border_radius=10,
                        bgcolor="#FFEDD5",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color="#C2410C", size=22),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(lines[0], size=15, weight=ft.FontWeight.W_700, color="#9A3412"),
                            *[
                                ft.Text(
                                    line,
                                    size=12,
                                    color=ui_theme.TEXT if index < 3 else ui_theme.MUTED,
                                )
                                for index, line in enumerate(lines[1:], start=1)
                            ],
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )
    return ft.Container(
        bgcolor="#FEF2F2",
        border=ui_theme.border("#FCA5A5"),
        border_radius=8,
        padding=ft.Padding(12, 8, 12, 8),
        content=ft.Text(value, color=ui_theme.DANGER),
    )


def _text_filter(label: str, value: str, hint: str) -> ft.TextField:
    field = ft.TextField(label=label, value=value, hint_text=hint, dense=True, width=150)
    _style_field(field)
    return field


def _amount_basis(condition: RateCondition) -> str:
    return condition.amount_basis if condition.amount_basis in {"deal_currency", "usd_equivalent"} else "deal_currency"


def _operation_type_label(value: str | None) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized == "import":
        return "\u0418\u043c\u043f\u043e\u0440\u0442"
    if normalized == "export":
        return "\u042d\u043a\u0441\u043f\u043e\u0440\u0442"
    return "\u041b\u044e\u0431\u043e\u0439"


def _amount_range(condition: RateCondition) -> str:
    start = _fmt(condition.amount_from or 0)
    end = _fmt(condition.amount_to) if condition.amount_to is not None else "без лимита"
    return f"{start}-{end}"


def _period(condition: RateCondition) -> str:
    start = condition.date_from or "с начала"
    end = condition.date_to or "бессрочно"
    return f"{start}-{end}"


def _percent_label(condition: RateCondition) -> str:
    return f"{_fmt(condition.rate_value)}%"


def _fixed_label(condition: RateCondition) -> str:
    if condition.fixed_commission_amount is None:
        return "-"
    return _fmt(condition.fixed_commission_amount)


def _currency_pair(condition: RateCondition) -> str:
    percent_currency = condition.percent_commission_currency or "Сделка"
    fixed_currency = condition.fixed_commission_currency or "Сделка"
    if percent_currency == fixed_currency:
        return percent_currency
    return f"% {percent_currency} / фикс {fixed_currency}"


def _fmt(value: float | None) -> str:
    if value is None:
        return "без лимита"
    text = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return text.rstrip("0").rstrip(",")


def _open_referral_form(context, referral: Referral, on_saved) -> None:
    name = ft.TextField(label="Название", value=referral.name)
    code = ft.TextField(label="Код", value=referral.code)
    description = ft.TextField(label="Описание", value=referral.description or "", multiline=True)
    logo_path = ft.TextField(label="Logo path", value=referral.logo_path or "")
    active = ft.Checkbox(label="Активен", value=referral.is_active)
    for field in (name, code, description, logo_path):
        _style_field(field)

    def save(_: ft.ControlEvent) -> None:
        try:
            updated = replace(
                referral,
                name=name.value or referral.name,
                code=code.value or referral.code,
                description=_blank(description.value),
                logo_path=_blank(logo_path.value),
                is_active=bool(active.value),
            )
            context.referrals_repository.update(updated)
            context.page.pop_dialog()
            on_saved()
        except Exception as exc:
            context.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Реферал", weight=ft.FontWeight.W_700),
        content=ft.Container(
            width=560,
            content=ft.Column([name, code, description, logo_path, active], spacing=12, tight=True),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
            ui_theme.primary_button("Сохранить", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
        ],
    )
    context.page.show_dialog(dialog)


def _open_delete_referral_dialog(context, referral: Referral, on_deleted) -> None:
    def delete(_: ft.ControlEvent) -> None:
        try:
            context.referrals_service.delete(referral)
            context.page.pop_dialog()
            on_deleted()
        except Exception as exc:
            context.page.pop_dialog()
            context.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor="#FEE2E2",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.DELETE_OUTLINE, color=ui_theme.DANGER, size=21),
                ),
                ft.Text("Удалить реферала?", weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=520,
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Реферал «{referral.name}» будет удален вместе со всеми условиями ставок.",
                        color=ui_theme.TEXT,
                    ),
                    ft.Text(
                        "Он не появится снова из реестра сделок автоматически. При необходимости его можно добавить вручную.",
                        color=ui_theme.MUTED,
                        size=12,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
            ft.FilledButton(
                "Удалить",
                icon=ft.Icons.DELETE_OUTLINE,
                bgcolor=ui_theme.DANGER,
                color=ft.Colors.WHITE,
                on_click=delete,
            ),
        ],
    )
    context.page.show_dialog(dialog)


def _style_field(field: ft.TextField) -> None:
    field.filled = True
    field.fill_color = "#F8FAFC"
    field.border_color = "#D8E2F0"
    field.focused_border_color = ui_theme.PRIMARY
    field.border_radius = 8
    field.content_padding = ft.Padding(12, 10, 12, 10)


def _blank(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None

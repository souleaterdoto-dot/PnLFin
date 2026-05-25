"""Rate condition card component."""

from __future__ import annotations

from datetime import datetime

import flet as ft

from app.domain.rate_models import RateCondition
from app.ui import theme as ui_theme


def rate_condition_card(
    condition: RateCondition,
    on_edit,
    on_delete,
    conflicted: bool = False,
) -> ft.Container:
    """Build a compact condition card."""
    return ft.Container(
        padding=16,
        border_radius=8,
        bgcolor="#FFF7ED" if conflicted else ui_theme.SURFACE,
        border=ui_theme.border("#F97316" if conflicted else "#D8E2F0"),
        shadow=ft.BoxShadow(blur_radius=18, color="#0F172A10", offset=ft.Offset(0, 8)),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(_main_line(condition), size=16, weight=ft.FontWeight.W_700, color=ui_theme.TEXT, expand=True),
                        _status_badge(condition.is_active),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DATE_RANGE_OUTLINED, size=16, color=ui_theme.MUTED),
                        ft.Text(f"Период: {_period(condition)}", color=ui_theme.MUTED),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        ft.Container(
                            padding=ft.Padding(10, 6, 10, 6),
                            border_radius=8,
                            bgcolor=ui_theme.PRIMARY_SOFT,
                            content=ft.Text(
                                f"Ставка: {_fmt(condition.rate_value)}%",
                                color=ui_theme.PRIMARY,
                                weight=ft.FontWeight.W_700,
                            ),
                        ),
                        ft.Text(f"Тип: {condition.commission_type}", color=ui_theme.MUTED),
                        ft.Container(expand=True),
                        ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Редактировать", on_click=lambda _: on_edit(condition)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Удалить", on_click=lambda _: on_delete(condition)),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    f"Комментарий: {condition.comment}" if condition.comment else "Комментарий: -",
                    color=ui_theme.MUTED,
                    size=12,
                ),
            ],
            spacing=8,
        ),
    )


def _main_line(condition: RateCondition) -> str:
    currency = condition.currency or "Любая валюта"
    return f"{currency} · {_amount_range(condition)}"


def _amount_range(condition: RateCondition) -> str:
    start = _fmt(condition.amount_from or 0)
    end = _fmt(condition.amount_to) if condition.amount_to is not None else "без лимита"
    return f"{start}-{end}"


def _period(condition: RateCondition) -> str:
    start = _fmt_date(condition.date_from) if condition.date_from else "с начала"
    end = _fmt_date(condition.date_to) if condition.date_to else "бессрочно"
    return f"{start}-{end}"


def _status_badge(active: bool) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=8,
        bgcolor="#DCFCE7" if active else "#E2E8F0",
        content=ft.Text(
            "Активно" if active else "Неактивно",
            size=11,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.GREEN_700 if active else ui_theme.MUTED,
        ),
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "без лимита"
    text = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return text.rstrip("0").rstrip(",")


def _fmt_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value

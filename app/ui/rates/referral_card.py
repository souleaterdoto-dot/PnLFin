"""Referral card component."""

from __future__ import annotations

import flet as ft

from app.domain.rate_models import Referral
from app.ui.asset_loader import image_source
from app.ui import theme as ui_theme


def referral_card(referral: Referral, on_click, on_delete=None) -> ft.Container:
    """Build a clickable referral card."""
    status_color = "#16A34A" if referral.is_active else ui_theme.MUTED
    return ft.Container(
        col={"sm": 12, "md": 6, "lg": 4, "xl": 3},
        padding=18,
        border_radius=8,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#D8E2F0"),
        shadow=ft.BoxShadow(blur_radius=22, color="#0F172A12", offset=ft.Offset(0, 10)),
        ink=True,
        on_click=lambda _: on_click(referral),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        _logo_placeholder(referral),
                        ft.Container(expand=True),
                        ft.Container(
                            padding=ft.Padding(8, 4, 8, 4),
                            border_radius=8,
                            bgcolor="#DCFCE7" if referral.is_active else "#E2E8F0",
                            content=ft.Text(
                                "Активен" if referral.is_active else "Неактивен",
                                size=11,
                                weight=ft.FontWeight.W_700,
                                color=status_color,
                            ),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Text(referral.name, size=20, weight=ft.FontWeight.W_700, color=ui_theme.TEXT, expand=True),
                        ft.TextButton(
                            "Удалить",
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ui_theme.DANGER,
                            style=ft.ButtonStyle(
                                color=ui_theme.DANGER,
                                padding=ft.Padding(8, 4, 8, 4),
                            ),
                            on_click=lambda event: on_delete(referral) if on_delete else None,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    referral.description or "Справочник условий ставок",
                    color=ui_theme.MUTED,
                    size=12,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Divider(height=12, color=ui_theme.BORDER),
                ft.Row(
                    controls=[
                        _small_metric("Активных условий", str(referral.active_conditions_count)),
                        _small_metric("Изменено", _format_date(referral.updated_at)),
                    ],
                    spacing=10,
                ),
            ],
            spacing=12,
        ),
    )


def _logo_placeholder(referral: Referral) -> ft.Container:
    logo_src = image_source(referral.logo_path)
    if logo_src:
        return ft.Container(
            width=52,
            height=52,
            border_radius=8,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            bgcolor=ui_theme.PRIMARY_SOFT,
            content=ft.Image(
                src=logo_src,
                width=52,
                height=52,
                fit="cover",
                error_content=_letters_logo(referral, size=52),
            ),
        )
    return _letters_logo(referral, size=52)


def _letters_logo(referral: Referral, size: int) -> ft.Container:
    letters = "".join(part[:1] for part in referral.name.split()[:2]).upper() or "R"
    return ft.Container(
        width=size,
        height=size,
        border_radius=8,
        bgcolor=ui_theme.PRIMARY_SOFT,
        alignment=ft.Alignment.CENTER,
        content=ft.Text(letters, size=18, weight=ft.FontWeight.W_700, color=ui_theme.PRIMARY),
    )


def _small_metric(label: str, value: str) -> ft.Container:
    return ft.Container(
        expand=True,
        padding=ft.Padding(10, 8, 10, 8),
        border_radius=8,
        bgcolor="#F8FAFC",
        border=ui_theme.border("#E2E8F0"),
        content=ft.Column(
            controls=[
                ft.Text(label, size=10, color=ui_theme.MUTED),
                ft.Text(value, size=13, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
            ],
            spacing=1,
        ),
    )


def _format_date(value: str | None) -> str:
    if not value:
        return "-"
    return str(value).split("T", 1)[0]

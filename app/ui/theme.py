"""Shared visual constants and helpers for the Flet UI."""

from __future__ import annotations

import flet as ft


PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_SOFT = "#EFF6FF"
PRIMARY_TINT = "#DBEAFE"
APP_BG = "#F8FAFC"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F1F5F9"
BORDER = "#E2E8F0"
TEXT = "#0F172A"
MUTED = "#64748B"
SUCCESS = "#16A34A"
DANGER = "#DC2626"
WARNING = "#D97706"
SHADOW = "#0F172A14"


def app_theme() -> ft.Theme:
    """Return the app-wide Material theme."""
    return ft.Theme(color_scheme_seed=PRIMARY, use_material3=True)


def border(color: str = BORDER) -> ft.Border:
    """Create a one-pixel border on all sides."""
    side = ft.BorderSide(1, color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def shadow() -> ft.BoxShadow:
    """Subtle elevation for panels and metric cards."""
    return ft.BoxShadow(blur_radius=18, color=SHADOW, offset=ft.Offset(0, 6))


def panel(content: ft.Control, padding: int = 16, expand: bool | int | None = None) -> ft.Container:
    """White panel used for forms, filters and tables."""
    return ft.Container(
        content=content,
        padding=padding,
        expand=expand,
        bgcolor=SURFACE,
        border=border(),
        border_radius=10,
        shadow=shadow(),
    )


def primary_button(label: str, icon: str | None = None, on_click=None, visible: bool = True) -> ft.FilledButton:
    """Create a consistently colored primary button."""
    return ft.FilledButton(
        label,
        icon=icon,
        on_click=on_click,
        visible=visible,
        bgcolor=PRIMARY,
        color=ft.Colors.WHITE,
    )

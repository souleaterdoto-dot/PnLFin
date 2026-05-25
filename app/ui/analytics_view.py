"""Flet host view for the local Dash analytics dashboard."""

from __future__ import annotations

import webbrowser
from urllib.parse import urlsplit, urlunsplit

import flet as ft

from app.services.analytics_server_service import LOCAL_ANALYTICS_HOST
from app.ui import theme as ui_theme


_OPENED_BROWSER_URLS: set[str] = set()


def create_analytics_view(context) -> ft.Control:
    """Start the local Dash server and show the dashboard browser launcher."""
    status = context.analytics_server_service.ensure_started()
    if not status.is_running or not status.url:
        return _error_view(
            status.error_message
            or "\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u0430\u044f "
            "\u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 "
            "\u043d\u0435 \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u043b\u0430\u0441\u044c."
        )
    return _dashboard_view(_localhost_url(status.url))


def _dashboard_view(url: str) -> ft.Control:
    _open_once(url)
    controls: list[ft.Control] = [
        ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(
                            "\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430",
                            size=28,
                            weight=ft.FontWeight.W_800,
                            color=ui_theme.TEXT,
                        ),
                        ft.Text(
                            "Dash/Plotly dashboard \u0437\u0430\u043f\u0443\u0449\u0435\u043d "
                            "\u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e \u0438 "
                            "\u0447\u0438\u0442\u0430\u0435\u0442 SQLite \u0432 read-only "
                            "\u0440\u0435\u0436\u0438\u043c\u0435.",
                            color=ui_theme.MUTED,
                        ),
                    ],
                    spacing=2,
                ),
                ft.Container(expand=True),
                ft.OutlinedButton(
                    "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0432 "
                    "\u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435",
                    icon=ft.Icons.OPEN_IN_BROWSER,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    on_click=lambda _: webbrowser.open(url),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ft.Container(
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=16,
            bgcolor="#EFF6FF",
            border=ui_theme.border("#DBEAFE"),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LINK, size=18, color=ui_theme.PRIMARY),
                    ft.Text(url, selectable=True, color=ui_theme.PRIMARY, weight=ft.FontWeight.W_700),
                    ft.Container(expand=True),
                    ft.Text("127.0.0.1 only", size=12, color=ui_theme.MUTED),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ),
    ]
    controls.append(_browser_fallback(url))

    return ft.Column(controls=controls, expand=True, spacing=14)


def _browser_fallback(url: str) -> ft.Control:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        border_radius=22,
        bgcolor="#F8FBFF",
        border=ui_theme.border("#D8E7FA"),
        shadow=ft.BoxShadow(blur_radius=28, color="#0F172A12", offset=ft.Offset(0, 12)),
        content=ft.Column(
            controls=[
                ft.Container(
                    width=70,
                    height=70,
                    border_radius=24,
                    bgcolor="#EFF6FF",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.INSIGHTS_OUTLINED, size=36, color=ui_theme.PRIMARY),
                ),
                ft.Text(
                    "Dashboard \u043e\u0442\u043a\u0440\u044b\u0442 \u0432\u043e "
                    "\u0432\u043d\u0435\u0448\u043d\u0435\u043c "
                    "\u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435",
                    size=22,
                    weight=ft.FontWeight.W_800,
                    color=ui_theme.TEXT,
                ),
                ft.Text(
                    "\u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 "
                    "\u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 "
                    "\u0432 \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u043c "
                    "\u043e\u043a\u043d\u0435 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0430. "
                    "\u0414\u0430\u043d\u043d\u044b\u0435 \u043d\u0435 "
                    "\u0443\u0445\u043e\u0434\u044f\u0442 \u0432 \u0441\u0435\u0442\u044c: "
                    "\u0430\u0434\u0440\u0435\u0441 \u0442\u043e\u043b\u044c\u043a\u043e 127.0.0.1.",
                    width=520,
                    text_align=ft.TextAlign.CENTER,
                    color=ui_theme.MUTED,
                ),
                ft.FilledButton(
                    "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0435\u0449\u0435 \u0440\u0430\u0437",
                    icon=ft.Icons.OPEN_IN_BROWSER,
                    bgcolor=ui_theme.PRIMARY,
                    color="#FFFFFF",
                    on_click=lambda _: webbrowser.open(url),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )


def _error_view(message: str) -> ft.Control:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Container(
            width=620,
            padding=ft.Padding(28, 28, 28, 28),
            border_radius=24,
            bgcolor="#FFFFFF",
            border=ui_theme.border("#FECACA"),
            shadow=ft.BoxShadow(blur_radius=32, color="#7F1D1D18", offset=ft.Offset(0, 16)),
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=42, color=ui_theme.DANGER),
                    ft.Text(
                        "\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 "
                        "\u043d\u0435 \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u043b\u0430\u0441\u044c",
                        size=24,
                        weight=ft.FontWeight.W_800,
                        color=ui_theme.TEXT,
                    ),
                    ft.Text(message, color=ui_theme.MUTED, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
            ),
        ),
    )


def _open_once(url: str) -> None:
    if url in _OPENED_BROWSER_URLS:
        return
    _OPENED_BROWSER_URLS.add(url)
    webbrowser.open(url)


def _localhost_url(url: str) -> str:
    """Force analytics links to stay on loopback even on RDP/server hosts."""
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    port = parsed.port
    netloc = f"{LOCAL_ANALYTICS_HOST}:{port}" if port else LOCAL_ANALYTICS_HOST
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

"""Dashboard screen."""

from __future__ import annotations

import flet as ft

from app.domain.models import PnlAnalytics
from app.ui import theme as ui_theme


def create_dashboard_view(context) -> ft.Control:
    """Create dashboard with top-level PnL metrics."""
    analytics = context.pnl_service.calculate()
    return ft.Column(
        controls=[
            _header("Dashboard", f"As of {analytics.as_of_date}"),
            ft.ResponsiveRow(
                controls=[
                    _metric_card("Total PnL", analytics.total_pnl_rub, ft.Icons.ACCOUNT_BALANCE_WALLET),
                    _metric_card("Realized", analytics.realized_pnl_rub, ft.Icons.CHECK_CIRCLE_OUTLINE),
                    _metric_card("Unrealized MTM", analytics.unrealized_pnl_rub, ft.Icons.TRENDING_UP),
                    _metric_card("Deals", analytics.deal_count, ft.Icons.RECEIPT_LONG, money=False),
                ],
                spacing=16,
                run_spacing=16,
            ),
            ft.Row(
                controls=[
                    _summary_panel("PnL by currency", analytics.pnl_by_currency),
                    _summary_panel("PnL by portfolio", analytics.pnl_by_portfolio),
                ],
                expand=True,
            ),
        ],
        expand=True,
        spacing=20,
        scroll=ft.ScrollMode.AUTO,
    )


def _header(title: str, subtitle: str) -> ft.Control:
    return ft.Row(
        controls=[
            ft.Column(
                controls=[
                    ft.Text(title, size=28, weight=ft.FontWeight.W_700),
                    ft.Text(subtitle, color=ui_theme.MUTED),
                ],
                spacing=2,
            )
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )


def _metric_card(title: str, value: float, icon: str, money: bool = True) -> ft.Control:
    display = _money(value) if money else f"{int(value)}"
    color = ft.Colors.GREEN_600 if value >= 0 else ft.Colors.RED_600
    return ft.Container(
        col={"sm": 6, "md": 3},
        padding=20,
        border_radius=10,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border(),
        shadow=ui_theme.shadow(),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            ft.Icon(icon, size=20, color=ui_theme.PRIMARY),
                            width=38,
                            height=38,
                            alignment=ft.Alignment.CENTER,
                            border_radius=8,
                            bgcolor=ui_theme.PRIMARY_SOFT,
                        ),
                        ft.Text(title, weight=ft.FontWeight.W_600, color=ui_theme.MUTED),
                    ],
                    spacing=8,
                ),
                ft.Text(display, size=26, weight=ft.FontWeight.W_700, color=color if money else None),
            ],
            spacing=10,
        ),
    )


def _summary_panel(title: str, values: dict[str, float]) -> ft.Control:
    rows = [
        ft.Row(
            controls=[
                ft.Text(key, width=120, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(
                    height=8,
                    expand=True,
                    border_radius=4,
                    bgcolor=ui_theme.PRIMARY_TINT,
                ),
                ft.Text(_money(value), width=120, text_align=ft.TextAlign.RIGHT),
            ],
            spacing=10,
        )
        for key, value in values.items()
    ]
    if not rows:
        rows = [ft.Text("No data yet", color=ui_theme.MUTED)]
    return ui_theme.panel(
        ft.Column(
            controls=[ft.Text(title, size=18, weight=ft.FontWeight.W_700), *rows],
            spacing=12,
        ),
        padding=20,
        expand=True,
    )


def _money(value: float) -> str:
    return f"{value:,.2f} RUB"

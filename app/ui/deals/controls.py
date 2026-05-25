"""Reusable controls for the deals registry screen."""

from __future__ import annotations

from typing import Any

import flet as ft

from app.ui import theme as ui_theme
from app.ui.deals.constants import MODE_THEMES, VIEW_MODES


def _style_filter_text_field(control: ft.TextField) -> None:
    """Apply shared styling to compact filter text fields."""
    control.height = 40
    control.filled = True
    control.fill_color = "#F8FBFF"
    control.border_color = "#D8E2F0"
    control.focused_border_color = ui_theme.PRIMARY
    control.border_radius = 12
    control.text_size = 12
    control.label_style = ft.TextStyle(size=11, color=ui_theme.MUTED)
    control.content_padding = ft.Padding(12, 6, 12, 6)


def _style_filter_dropdown(control: ft.Dropdown) -> None:
    """Apply shared styling to compact filter dropdowns."""
    control.height = 40
    control.filled = True
    control.fill_color = "#F8FBFF"
    control.border_color = "#D8E2F0"
    control.focused_border_color = ui_theme.PRIMARY
    control.hover_color = "#EFF6FF"
    control.border_radius = 12
    control.text_size = 12
    control.label_style = ft.TextStyle(size=11, color=ui_theme.MUTED)
    control.content_padding = ft.Padding(12, 6, 8, 6)
    control.trailing_icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED


def _style_registry_dropdown(control: ft.Dropdown) -> None:
    """Apply premium styling to the top registry dropdown filters."""
    control.height = 46
    control.filled = True
    control.fill_color = "#FFFFFF"
    control.border_color = "#CFE0F5"
    control.focused_border_color = ui_theme.PRIMARY
    control.hover_color = "#EFF6FF"
    control.border_radius = 16
    control.text_size = 12
    control.label_style = ft.TextStyle(size=11, weight=ft.FontWeight.W_800, color="#31537D")
    control.text_style = ft.TextStyle(size=12, weight=ft.FontWeight.W_700, color=ui_theme.TEXT)
    control.content_padding = ft.Padding(14, 7, 10, 7)
    control.trailing_icon = ft.Icons.EXPAND_MORE_ROUNDED


def _style_page_input(control: ft.TextField) -> None:
    """Apply shared styling to pagination input."""
    control.height = 38
    control.width = 112
    control.dense = False
    control.filled = True
    control.fill_color = "#F8FBFF"
    control.border_color = "#BFDBFE"
    control.focused_border_color = ui_theme.PRIMARY
    control.border_radius = 12
    control.text_size = 13
    control.text_style = ft.TextStyle(weight=ft.FontWeight.W_800, color=ui_theme.TEXT)
    control.hint_style = ft.TextStyle(size=12, color=ui_theme.MUTED)
    control.content_padding = ft.Padding(16, 8, 16, 8)


def _style_page_size_dropdown(control: ft.Dropdown) -> None:
    """Apply compact styling to the page-size selector."""
    control.label = None
    control.height = 38
    control.width = 104
    control.dense = True
    control.filled = True
    control.fill_color = "#F8FBFF"
    control.border_color = "#BFDBFE"
    control.focused_border_color = ui_theme.PRIMARY
    control.border_radius = 12
    control.text_size = 12
    control.text_style = ft.TextStyle(size=12, weight=ft.FontWeight.W_800, color=ui_theme.TEXT)
    control.content_padding = ft.Padding(17, 7, 8, 7)
    control.trailing_icon = ft.Icons.EXPAND_MORE_ROUNDED


def _pagination_panel(
    state: dict[str, Any],
    pager_label: ft.Text,
    rows_label: ft.Text,
    page_input: ft.TextField,
    page_size_dropdown: ft.Dropdown,
    go_to_page,
    go_to_entered_page,
) -> ft.Container:
    """Build the bottom pagination bar."""
    pager_label.color = "#FFFFFF"
    pager_label.weight = ft.FontWeight.W_800
    rows_label.size = 12
    rows_label.weight = ft.FontWeight.W_700
    return ft.Container(
        padding=ft.Padding(12, 9, 12, 9),
        border_radius=18,
        bgcolor="#FFFFFFF7",
        border=ui_theme.border("#DCE8F8"),
        shadow=ft.BoxShadow(blur_radius=24, color="#2563EB12", offset=ft.Offset(0, 8)),
        content=ft.Row(
            controls=[
                ft.Container(
                    padding=ft.Padding(11, 8, 12, 8),
                    border_radius=999,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=["#FFFFFF", "#EFF6FF"],
                    ),
                    border=ui_theme.border("#D8E7FA"),
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                width=24,
                                height=24,
                                border_radius=8,
                                bgcolor=ui_theme.PRIMARY,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.TABLE_ROWS_OUTLINED, size=15, color="#FFFFFF"),
                            ),
                            rows_label,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Container(expand=True),
                ft.Container(
                    padding=ft.Padding(7, 6, 7, 6),
                    border_radius=18,
                    bgcolor="#F8FBFF",
                    border=ui_theme.border("#D8E7FA"),
                    content=ft.Row(
                    controls=[
                        _pager_icon(ft.Icons.FIRST_PAGE, "Первая страница", lambda _: go_to_page(1)),
                        _pager_icon(
                            ft.Icons.CHEVRON_LEFT,
                            "Предыдущая страница",
                            lambda _: go_to_page(max(1, int(state["page"]) - 1)),
                        ),
                        ft.Container(
                            height=38,
                            padding=ft.Padding(14, 0, 14, 0),
                            border_radius=14,
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment(-1, -1),
                                end=ft.Alignment(1, 1),
                                colors=["#2563EB", "#3B82F6"],
                            ),
                            shadow=ft.BoxShadow(blur_radius=16, color="#2563EB2A", offset=ft.Offset(0, 5)),
                            alignment=ft.Alignment.CENTER,
                            content=pager_label,
                        ),
                        _pager_icon(
                            ft.Icons.CHEVRON_RIGHT,
                            "Следующая страница",
                            lambda _: go_to_page(int(state["page"]) + 1),
                        ),
                        _pager_icon(ft.Icons.LAST_PAGE, "Последняя страница", lambda _: go_to_page(10**9)),
                    ],
                        spacing=5,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Container(expand=True),
                ft.Container(
                    height=58,
                    padding=ft.Padding(12, 8, 18, 8),
                    border_radius=16,
                    bgcolor="#F8FBFF",
                    border=ui_theme.border("#D8E7FA"),
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                width=28,
                                height=28,
                                border_radius=10,
                                bgcolor="#EFF6FF",
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.TABLE_ROWS_OUTLINED, size=16, color=ui_theme.PRIMARY),
                            ),
                            page_size_dropdown,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Container(
                    height=58,
                    padding=ft.Padding(12, 8, 12, 8),
                    border_radius=16,
                    bgcolor="#F8FBFF",
                    border=ui_theme.border("#D8E7FA"),
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                width=78,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text("Страница", size=12, weight=ft.FontWeight.W_800, color=ui_theme.MUTED),
                            ),
                            page_input,
                            ft.Container(
                                width=38,
                                height=38,
                                border_radius=12,
                                bgcolor=ui_theme.PRIMARY,
                                shadow=ft.BoxShadow(blur_radius=14, color="#2563EB2E", offset=ft.Offset(0, 5)),
                                alignment=ft.Alignment.CENTER,
                                ink=True,
                                ink_color="#60A5FA",
                                on_click=go_to_entered_page,
                                tooltip="Перейти к странице",
                                content=ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=18, color="#FFFFFF"),
                            ),
                        ],
                        spacing=7,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _pager_icon(icon: str, tooltip: str, on_click, enabled: bool = True) -> ft.Container:
    return ft.Container(
        width=38,
        height=38,
        border_radius=13,
        bgcolor="#FFFFFF" if enabled else "#F1F5F9",
        border=ui_theme.border("#BFDBFE" if enabled else "#E2E8F0"),
        shadow=ft.BoxShadow(blur_radius=12, color="#2563EB18", offset=ft.Offset(0, 4)) if enabled else None,
        alignment=ft.Alignment.CENTER,
        ink=enabled,
        ink_color="#DBEAFE",
        tooltip=tooltip,
        on_click=on_click if enabled else None,
        content=ft.Icon(icon, size=21, color=ui_theme.PRIMARY if enabled else "#94A3B8"),
    )


def _filters_panel(
    state: dict[str, object],
    search: ft.TextField,
    portfolio_filter: ft.Dropdown,
    operation_type_filter: ft.Dropdown,
    referral_filter: ft.Dropdown,
    sort_by: ft.Dropdown,
    sort_desc: ft.IconButton,
    apply_filters,
    clear_filters,
    add_deal,
    delete_deal,
) -> ft.Container:
    """Build top filters panel."""
    is_pnl = state.get("view_mode") == "pnl"
    return ft.Container(
        padding=14,
        border_radius=8,
        bgcolor="#171009" if is_pnl else ui_theme.SURFACE,
        border=ui_theme.border("#B88A35" if is_pnl else "#D8E2F0"),
        shadow=ft.BoxShadow(blur_radius=30 if is_pnl else 26, color="#D6A84F30" if is_pnl else "#0F172A12", offset=ft.Offset(0, 10)),
        animate=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
        content=ft.Column(
            controls=[
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(search, col={"sm": 12, "md": 2.7}),
                        ft.Container(portfolio_filter, col={"sm": 6, "md": 1.5}),
                        ft.Container(operation_type_filter, col={"sm": 6, "md": 1.6}),
                        ft.Container(referral_filter, col={"sm": 6, "md": 2.0}),
                        ft.Container(
                            ft.Row(
                                controls=[
                                    ft.FilledButton(
                                        "\u041d\u0430\u0439\u0442\u0438",
                                        icon=ft.Icons.SEARCH,
                                        height=38,
                                        style=ft.ButtonStyle(
                                            bgcolor=ui_theme.PRIMARY,
                                            color="#FFFFFF",
                                            padding=ft.Padding(12, 0, 12, 0),
                                            shape=ft.RoundedRectangleBorder(radius=11),
                                        ),
                                        on_click=apply_filters,
                                    ),
                                    ft.OutlinedButton(
                                        "\u0421\u0431\u0440\u043e\u0441",
                                        icon=ft.Icons.CLEAR,
                                        height=38,
                                        style=ft.ButtonStyle(
                                            padding=ft.Padding(10, 0, 10, 0),
                                            shape=ft.RoundedRectangleBorder(radius=11),
                                        ),
                                        on_click=clear_filters,
                                    ),
                                    ft.FilledButton(
                                        "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c",
                                        icon=ft.Icons.ADD,
                                        height=38,
                                        style=ft.ButtonStyle(
                                            bgcolor="#16A34A",
                                            color="#FFFFFF",
                                            padding=ft.Padding(12, 0, 12, 0),
                                            shape=ft.RoundedRectangleBorder(radius=11),
                                        ),
                                        on_click=add_deal,
                                    ),
                                    ft.OutlinedButton(
                                        "\u0423\u0434\u0430\u043b\u0438\u0442\u044c",
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        height=38,
                                        style=ft.ButtonStyle(
                                            color="#DC2626",
                                            side=ft.BorderSide(1, "#FCA5A5"),
                                            padding=ft.Padding(10, 0, 10, 0),
                                            shape=ft.RoundedRectangleBorder(radius=11),
                                        ),
                                        on_click=delete_deal,
                                    ),
                                ],
                                spacing=6,
                                wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            col={"sm": 12, "md": 3.2},
                        ),
                    ],
                    spacing=10,
                    run_spacing=10,
                ),
            ],
            spacing=12,
        ),
    )


def _view_switcher(mode_buttons: dict[str, ft.Container], on_change, active_mode: str) -> ft.Container:
    """Build the view mode segmented control."""
    buttons = [_mode_button(mode, mode == active_mode, on_change) for mode in VIEW_MODES]
    for mode, button in zip(VIEW_MODES, buttons):
        mode_buttons[mode] = button
    return ft.Container(
        padding=ft.Padding(7, 7, 7, 7),
        border_radius=20,
        bgcolor="#FFFFFFF2",
        border=ui_theme.border("#E1E8F0"),
        shadow=ft.BoxShadow(blur_radius=22, color="#0F172A14", offset=ft.Offset(0, 8)),
        content=ft.Row(
            controls=[
                ft.Container(
                    width=34,
                    height=34,
                    border_radius=12,
                    bgcolor="#F8FAFC",
                    border=ui_theme.border("#E2E8F0"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_OUTLINED, size=18, color=ui_theme.PRIMARY),
                ),
                ft.Row(controls=buttons, spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _mode_button(mode: str, active: bool, on_change) -> ft.Container:
    theme = MODE_THEMES[mode]
    accent = str(theme["accent"])
    soft = str(theme["soft"])
    tint = str(theme["tint"])
    shadow_color = str(theme.get("shadow", "#2563EB"))
    is_pnl = mode == "pnl"
    return ft.Container(
        data=mode,
        height=38,
        padding=ft.Padding(12 if active else 10, 0, 12 if active else 10, 0),
        border_radius=13,
        bgcolor=soft if active else "#FFFFFF",
        border=ui_theme.border(tint if active else "#E6ECF3"),
        shadow=(
            ft.BoxShadow(blur_radius=20 if is_pnl else 12, color=f"{shadow_color}38" if is_pnl else f"{shadow_color}18", offset=ft.Offset(0, 6 if is_pnl else 4))
            if active
            else None
        ),
        animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        ink=True,
        ink_color=tint,
        on_click=lambda _, value=mode: on_change(value),
        content=ft.Row(
            controls=[
                ft.Icon(theme["icon"], size=17, color=accent),
                ft.Text(
                    str(theme["label"]),
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=accent if active else "#475569",
                ),
            ],
            spacing=7,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _sync_view_switcher(mode_buttons: dict[str, ft.Container], active_mode: str) -> None:
    """Update visual state of already-created mode buttons."""
    for mode, button in mode_buttons.items():
        theme = MODE_THEMES[mode]
        active = mode == active_mode
        accent = str(theme["accent"])
        soft = str(theme["soft"])
        tint = str(theme["tint"])
        shadow_color = str(theme.get("shadow", "#2563EB"))
        is_pnl = mode == "pnl"
        button.padding = ft.Padding(12 if active else 10, 0, 12 if active else 10, 0)
        button.bgcolor = soft if active else "#FFFFFF"
        button.border = ui_theme.border(tint if active else "#E6ECF3")
        button.shadow = (
            ft.BoxShadow(blur_radius=20 if is_pnl else 12, color=f"{shadow_color}38" if is_pnl else f"{shadow_color}18", offset=ft.Offset(0, 6 if is_pnl else 4))
            if active
            else None
        )
        button.ink_color = tint
        row = button.content
        if isinstance(row, ft.Row) and len(row.controls) >= 2:
            icon = row.controls[0]
            label = row.controls[1]
            if isinstance(icon, ft.Icon):
                icon.color = accent
            if isinstance(label, ft.Text):
                label.color = accent if active else "#475569"


def _mode_gradient(mode: str) -> ft.LinearGradient:
    """Return the soft gradient for a view mode."""
    colors = MODE_THEMES.get(mode, MODE_THEMES["general"])["gradient"]
    return ft.LinearGradient(
        begin=ft.Alignment(-1, -1),
        end=ft.Alignment(1, 1),
        colors=list(colors),
    )

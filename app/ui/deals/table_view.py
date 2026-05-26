"""Virtualized deals table view."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import replace
from difflib import get_close_matches
import time
from typing import Any

import flet as ft

from app.domain.enums import DealReviewStatus
from app.domain.models import Deal
from app.repositories.rates_repository import normalize_rate_currency
from app.ui import theme as ui_theme
from app.ui.deals.constants import (
    BASE_FIELDS,
    CELL_FONT_SIZE,
    CELL_X_PADDING,
    COLUMN_BY_FIELD,
    COLUMN_WIDTH_SCALE,
    COMPUTED_FILTER_COLUMNS,
    EXCEL_COLUMNS,
    FINANCE_COMMON_FIELDS,
    FINANCE_CURRENCY_FIELDS,
    FINANCE_RATE_COLUMNS,
    FINANCE_USD_COMPUTED_COLUMNS,
    GENERAL_FIELDS,
    HEADER_FONT_SIZE,
    HEADER_HEIGHT,
    MIN_COLUMN_WIDTH,
    PINNED_COLUMN_COUNT,
    PNL_COMPUTED_COLUMNS,
    RATES_FIELDS,
    ROW_HEIGHT,
    VIEW_MODES,
    ColumnGetter,
    ColumnSpec,
)
from app.ui.deals.edit_dialog import _calendar_icon_button, _open_date_picker, _open_edit_dialog
from app.ui.deals.filters import _open_header_filter_overlay
from app.ui.deals.formatters import _blank, _format_date, _format_number, _parse_optional_date
from app.services.performance_logger import perf_span, perf_span_if_slow


USD_LIKE_CURRENCIES = {"USD", "USDT", "USDC"}
STRONGER_THAN_USD_CURRENCIES = {"EUR", "GBP", "CHF", "KWD", "BHD", "OMR", "JOD", "KYD", "GIP"}
CBR_RATE_NOMINALS = {
    "AMD": 100,
    "HUF": 100,
    "IDR": 10000,
    "JPY": 100,
    "KGS": 10,
    "KRW": 1000,
    "KZT": 100,
    "RSD": 100,
    "TJS": 10,
    "UZS": 10000,
    "VND": 10000,
}
USD_COMPONENT_FIELDS = {
    "__fixed_commission_usd": ("Фикс. комиссия", "fixed_commission_amount", "fixed_commission_currency"),
    "__swift_usd": ("SWIFT", "swift_amount", "swift_currency"),
    "__agent_commission_usd": ("Комиссия ПА", "agent_commission_amount", "agent_commission_currency"),
    "__swift_commission_usd": ("Комиссия за SWIFT ПА", "swift_commission_amount", "swift_commission_currency"),
}


@dataclass(frozen=True)
class _ReferralCommissionResult:
    label: str
    tooltip: str
    ok: bool
    amount_usd: float | None = None


class _InactiveReferralError(LookupError):
    """Raised when referral exists, but must not affect PnL because it is inactive."""


@dataclass(frozen=True)
class _PnlBreakdown:
    client_percent_fee: float | None
    fixed_commission: float | None
    swift: float | None
    agent_commission: float | None
    swift_commission: float | None
    referral: _ReferralCommissionResult
    repeat_payment_penalty: float | None = 0.0

    @property
    def gross(self) -> float | None:
        if (
            self.client_percent_fee is None
            or self.fixed_commission is None
            or self.swift is None
            or self.repeat_payment_penalty is None
        ):
            return None
        return self.client_percent_fee + self.fixed_commission + self.swift + self.repeat_payment_penalty

    @property
    def costs(self) -> float | None:
        if (
            self.agent_commission is None
            or self.swift_commission is None
            or self.referral.amount_usd is None
        ):
            return None
        return self.agent_commission + self.swift_commission + self.referral.amount_usd

    @property
    def pnl(self) -> float | None:
        if self.gross is None or self.costs is None:
            return None
        return self.gross - self.costs


def _deals_table(
    context,
    deals: list[Deal],
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    on_deal_saved,
    mode: str | None = None,
) -> ft.Control:
    mode_name = mode or str(state.get("view_mode") or "general")
    columns = _compact_columns(state, _visible_columns(mode_name))
    state.setdefault("mode_column_keys", {})[mode_name] = [_column_key(column) for column in columns]
    table_width = sum(width for _, _, _, width, _ in columns)
    empty_state = ft.Container(
        padding=40,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=34, color=ui_theme.MUTED),
                ft.Text("\u0421\u0434\u0435\u043b\u043a\u0438 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b", color=ui_theme.MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )
    header = _fixed_table_header(context, state, sort_by, refresh, columns, mode_name)
    body = _virtualized_table_body(context, state, columns, deals, refresh, on_deal_saved, mode_name, list_kind="full")
    table = ft.Column(
        width=table_width,
        expand=True,
        spacing=0,
        controls=[header, body],
    )
    state["active_table_column"] = table
    state["active_header_container"] = header
    state["active_columns"] = columns
    return ui_theme.panel(
        empty_state
        if not deals
        else ft.Row(controls=[table], expand=True, scroll=ft.ScrollMode.AUTO),
        padding=6,
        expand=True,
    )


def _compact_columns(state: dict[str, Any], columns: tuple[ColumnSpec, ...]) -> tuple[ColumnSpec, ...]:
    """Return columns scaled for the dense registry layout."""
    return tuple(
        (label, field_name, getter, _compact_width(state, width), numeric)
        for label, field_name, getter, width, numeric in columns
    )


def _compact_width(state: dict[str, Any], width: int) -> int:
    return max(MIN_COLUMN_WIDTH, int(width * COLUMN_WIDTH_SCALE))


def _column_key(column: ColumnSpec) -> str:
    label, field_name, _, _, _ = column
    return field_name or label


def _replace_visible_columns(
    context,
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    on_deal_saved,
    previous_mode: str,
    next_mode: str,
) -> dict[int, list[ft.Control]]:
    with perf_span("deals.table.replace_visible_columns.total", previous_mode=previous_mode, next_mode=next_mode):
        columns = _compact_columns(state, _visible_columns(next_mode))
        previous_keys = [_column_key(column) for column in _visible_columns(previous_mode)]
        next_keys = [_column_key(column) for column in columns]
        changed_indexes = {
            index
            for index, key in enumerate(next_keys)
            if index >= len(previous_keys) or previous_keys[index] != key
        }
        state.setdefault("mode_column_keys", {})[next_mode] = next_keys
        state.setdefault("mode_column_controls", {})[next_mode] = {}
        state["review_status_menus"] = {}
        table = state.get("active_table_column")
        header = state.get("active_header_container")
        deals = list(state.get("current_deals") or [])
        rows = list(state.get("active_body_rows") or [])
        if isinstance(table, ft.Column):
            table.width = sum(width for _, _, _, width, _ in columns)
        if isinstance(header, ft.Container) and isinstance(header.content, ft.Row):
            with perf_span("deals.table.replace_header", columns=len(columns)):
                header.content.controls = [
                    _header_cell(context, state, sort_by, refresh, label, field_name, width, numeric, column_index, next_mode)
                    for column_index, (label, field_name, _, width, numeric) in enumerate(columns)
                ]
        state["row_controls_by_mode"] = {next_mode: {}}
        prepared: dict[int, list[ft.Control]] = {}
        with perf_span("deals.table.replace_rows", rows=len(rows), columns=len(columns), next_mode=next_mode):
            for row_index, (row, deal) in enumerate(zip(rows, deals)):
                if not isinstance(row, ft.Container) or not isinstance(row.content, ft.Row):
                    continue
                deal_key = _deal_selection_key(deal)
                row.data = {"deal_key": deal_key, "deal": deal}
                selected = _is_deal_key_selected(state, deal_key)
                row.content.controls = _cached_row_cells(
                    context,
                    state,
                    columns,
                    deal,
                    row_index,
                    next_mode,
                    on_deal_saved,
                    selected=selected,
                )
                state["row_controls_by_mode"][next_mode][deal_key] = row
                if selected:
                    _apply_selected_row_style(row)
                    state["selected_row_control"] = row
                else:
                    _apply_default_row_style(row)
        for column_index in changed_indexes:
            if column_index < PINNED_COLUMN_COUNT:
                continue
            for control in (state.get("mode_column_controls") or {}).get(next_mode, {}).get(column_index, []):
                control.opacity = 1.0
                control.offset = ft.Offset(0, 0)
                prepared.setdefault(column_index, []).append(control)
        state["active_columns"] = columns
        state["table_list_view"] = state.get("table_list_view")
        return prepared


def _sync_selected_row_in_mode(state: dict[str, Any], mode: str) -> list[ft.Control]:
    selected_keys = _selected_deal_keys(state)
    if not selected_keys:
        return []
    for mode_name, rows in (state.get("row_controls_by_mode") or {}).items():
        if mode_name == mode:
            continue
        for row in rows.values():
            _apply_default_row_style(row)
    rows_by_mode = (state.get("row_controls_by_mode") or {}).get(mode, {})
    selected_key = state.get("selected_deal_key")
    next_row = rows_by_mode.get(selected_key) if selected_key else None
    controls: list[ft.Control] = []
    previous_row = state.get("selected_row_control")
    if previous_row is not None and previous_row is not next_row:
        _apply_default_row_style(previous_row)
        controls.append(previous_row)
    for row_key, row in rows_by_mode.items():
        should_select = row_key in selected_keys
        if should_select:
            _apply_selected_row_style(row)
            controls.append(row)
        elif row.bgcolor == _selected_row_bg():
            _apply_default_row_style(row)
            controls.append(row)
    if next_row is not None:
        state["selected_row_control"] = next_row
    return controls


def _selected_deal_keys(state: dict[str, Any]) -> set[str]:
    selected = state.get("selected_deal_keys")
    if isinstance(selected, set):
        return set(selected)
    if isinstance(selected, (list, tuple)):
        return {str(value) for value in selected}
    selected_key = state.get("selected_deal_key")
    return {str(selected_key)} if selected_key else set()


def _is_deal_key_selected(state: dict[str, Any], deal_key: str) -> bool:
    return deal_key in _selected_deal_keys(state)


def _next_selected_deal_keys(state: dict[str, Any], deal_key: str, row_index: int) -> set[str]:
    previous = _selected_deal_keys(state)
    modifiers = _active_selection_modifiers(state)
    current_deals = list(state.get("current_deals") or [])
    if modifiers["shift"] and current_deals:
        anchor = state.get("selection_anchor_index")
        try:
            anchor_index = int(anchor if anchor is not None else row_index)
        except (TypeError, ValueError):
            anchor_index = row_index
        start, end = sorted((max(0, anchor_index), max(0, row_index)))
        range_keys = {
            _deal_selection_key(deal)
            for deal in current_deals[start : min(end + 1, len(current_deals))]
        }
        state["selection_anchor_index"] = anchor_index
        return previous | range_keys
    if modifiers["ctrl"]:
        state["selection_anchor_index"] = row_index
        if deal_key in previous:
            previous.remove(deal_key)
        else:
            previous.add(deal_key)
        return previous or {deal_key}
    state["selection_anchor_index"] = row_index
    return {deal_key}


def _active_selection_modifiers(state: dict[str, Any]) -> dict[str, bool]:
    modifier_state = state.get("selection_modifier_state") or {}
    event_age = time.monotonic() - float(modifier_state.get("at") or 0.0)
    if event_age > 30.0:
        return {"shift": False, "ctrl": False}
    return {
        "shift": bool(modifier_state.get("shift")),
        "ctrl": bool(modifier_state.get("ctrl")),
    }


def _apply_selection_delta_to_rows(
    state: dict[str, Any],
    mode: str,
    previous_keys: set[str],
    next_keys: set[str],
) -> list[ft.Control]:
    rows_by_mode = (state.get("row_controls_by_mode") or {}).get(mode, {})
    controls: list[ft.Control] = []
    for key in previous_keys | next_keys:
        row = rows_by_mode.get(key)
        if row is None:
            continue
        if key in next_keys:
            _apply_selected_row_style(row)
        else:
            _apply_default_row_style(row)
        controls.append(row)
    return controls


def _deals_modes_stack(
    context,
    deals: list[Deal],
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    on_deal_saved,
) -> ft.Control:
    active_mode = str(state.get("view_mode") or "general")
    with perf_span("deals.table.build_modes_stack", rows=len(deals), mode=active_mode):
        state["mode_table_controls"] = {}
        state["table_list_views"] = {}
        state["mode_column_controls"] = {}
        state["mode_column_keys"] = {}
        state["mode_row_cells_cache"] = {}
        state["row_controls_by_mode"] = {}
        state["review_status_menus"] = {}
        wrapper = _build_mode_table_wrapper(
            context,
            deals,
            state,
            sort_by,
            refresh,
            on_deal_saved,
            active_mode,
            visible=True,
        )
        state["mode_table_controls"][active_mode] = wrapper
        state["table_list_view"] = state["table_list_views"].get(active_mode)
        return ft.Stack(controls=[wrapper], expand=True, fit=ft.StackFit.EXPAND)


def _add_mode_to_stack(
    stack: ft.Control | None,
    context,
    deals: list[Deal],
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    on_deal_saved,
    mode: str,
) -> bool:
    if not isinstance(stack, ft.Stack) or mode not in VIEW_MODES:
        return False
    if mode in state.get("mode_table_controls", {}):
        return False
    wrapper = _build_mode_table_wrapper(
        context,
        deals,
        state,
        sort_by,
        refresh,
        on_deal_saved,
        mode,
        visible=False,
    )
    state.setdefault("mode_table_controls", {})[mode] = wrapper
    stack.controls.append(wrapper)
    return True


def _build_mode_table_wrapper(
    context,
    deals: list[Deal],
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    on_deal_saved,
    mode: str,
    visible: bool,
) -> ft.Container:
    with perf_span("deals.table.build_mode_wrapper", rows=len(deals), mode=mode):
        return ft.Container(
            content=_deals_table(context, deals, state, sort_by, refresh, on_deal_saved, mode=mode),
            expand=True,
            visible=visible,
            opacity=1.0 if visible else 0.0,
            offset=ft.Offset(0, 0),
            animate_opacity=170,
            animate_offset=210,
        )


def _virtualized_table_body(
    context,
    state: dict[str, Any],
    columns: tuple[ColumnSpec, ...],
    deals: list[Deal],
    refresh,
    on_deal_saved,
    mode: str,
    start_column_index: int = 0,
    list_kind: str = "scroll",
) -> ft.ListView:
    """Render table body with Flet's native lazy list virtualization."""
    def remember_scroll(event: ft.OnScrollEvent) -> None:
        offset = max(0.0, float(event.pixels or 0.0))
        suppress_until = float(state.get("suppress_scroll_capture_until") or 0.0)
        restore_offset = max(0.0, float(state.get("scroll_restore_offset") or 0.0))
        if time.monotonic() < suppress_until and offset <= 1.0 < restore_offset:
            state["table_scroll_offset"] = restore_offset
            return
        state["table_scroll_offset"] = offset
        if offset > 1.0:
            state["scroll_restore_offset"] = offset

    rows = [
        _table_body_row(
            context,
            state,
            columns,
            deal,
            refresh,
            on_deal_saved,
            row_index,
            mode,
            start_column_index=start_column_index,
        )
        for row_index, deal in enumerate(deals)
    ]
    list_view = ft.ListView(
        controls=rows,
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        scroll_interval=60,
        on_scroll=remember_scroll,
        item_extent=ROW_HEIGHT,
        cache_extent=ROW_HEIGHT * 6,
        build_controls_on_demand=True,
    )
    state.setdefault("table_list_views", {})[mode] = list_view
    state["active_body_rows"] = rows
    return list_view


def _fixed_table_header(
    context,
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    columns: tuple[ColumnSpec, ...],
    mode: str,
    start_column_index: int = 0,
) -> ft.Container:
    is_pnl = mode == "pnl"
    return ft.Container(
        height=HEADER_HEIGHT,
        bgcolor="#171009" if is_pnl else "#F8FBFF",
        border=ui_theme.border("#B88A35" if is_pnl else "#CFE0F5"),
        border_radius=10,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=ft.BoxShadow(blur_radius=18 if is_pnl else 12, color="#D6A84F30" if is_pnl else "#1E3A8A10", offset=ft.Offset(0, 4)),
        animate=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
        content=ft.Row(
            controls=[
                _header_cell(context, state, sort_by, refresh, label, field_name, width, numeric, column_index, mode)
                for column_index, (label, field_name, _, width, numeric) in enumerate(
                    columns,
                    start=start_column_index,
                )
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
    )


def _table_body_row(
    context,
    state: dict[str, Any],
    columns: tuple[ColumnSpec, ...],
    deal: Deal,
    refresh,
    on_deal_saved,
    row_index: int,
    mode: str,
    start_column_index: int = 0,
) -> ft.Container:
    deal_key = _deal_selection_key(deal)
    selected = _is_deal_key_selected(state, deal_key)

    def select_row() -> None:
        active_mode = str(state.get("view_mode") or mode)
        previous_keys = _selected_deal_keys(state)
        next_keys = _next_selected_deal_keys(state, deal_key, row_index)
        state["selected_deal_id"] = deal.id
        state["selected_deal_key"] = deal_key
        state["selected_deal_keys"] = next_keys
        state["selected_row_control"] = (state.get("row_controls_by_mode") or {}).get(active_mode, {}).get(deal_key, row)
        update_controls = _apply_selection_delta_to_rows(state, active_mode, previous_keys, next_keys)
        try:
            if update_controls:
                context.page.update(*update_controls)
            else:
                _apply_selected_row_style(row)
                context.page.update(row)
        except Exception:
            context.page.update(row)

    def handle_row_click(_: ft.ControlEvent) -> None:
        now = time.monotonic()
        last_key = state.get("last_row_click_key")
        last_at = float(state.get("last_row_click_at") or 0.0)
        is_double_click = last_key == deal_key and now - last_at <= 0.45
        state["last_row_click_key"] = deal_key
        state["last_row_click_at"] = now
        select_row()
        if is_double_click:
            state["last_row_click_at"] = 0.0
            _open_edit_dialog(context, deal, on_deal_saved)

    def handle_row_hover(event: ft.ControlEvent) -> None:
        hovered = str(getattr(event, "data", "")).lower() == "true"
        if isinstance(row.data, dict):
            row.data["hovered"] = hovered
        selected_now = _is_deal_key_selected(state, deal_key)
        row.border = _row_border(selected_now, hovered)
        _apply_row_hover_overlay(row, hovered, selected_now)
        _apply_row_cell_styles(row, selected=selected_now)
        context.page.update(row)

    cells = _cached_row_cells(
        context,
        state,
        columns,
        deal,
        row_index,
        mode,
        on_deal_saved,
        selected=selected,
        start_column_index=start_column_index,
    )
    row = ft.Container(
        height=ROW_HEIGHT,
        bgcolor=ui_theme.SURFACE,
        border=_row_border(selected),
        ink=True,
        ink_color="#00000000",
        on_click=handle_row_click,
        on_hover=handle_row_hover,
        data={"deal_key": deal_key, "deal": deal},
        content=ft.Row(
            controls=cells,
            spacing=0,
        ),
    )
    state.setdefault("row_controls_by_mode", {}).setdefault(mode, {})[deal_key] = row
    if selected:
        state["selected_row_control"] = row
    return row


def _cached_row_cells(
    context,
    state: dict[str, Any],
    columns: tuple[ColumnSpec, ...],
    deal: Deal,
    row_index: int,
    mode: str,
    on_deal_saved,
    selected: bool = False,
    start_column_index: int = 0,
) -> list[ft.Control]:
    deal_key = _deal_selection_key(deal)
    mode_cache = state.setdefault("mode_row_cells_cache", {}).setdefault(mode, {})
    cache_key = f"{deal_key}:{start_column_index}:{len(columns)}"
    cached = mode_cache.get(cache_key)
    if cached is None:
        cached = _row_cells(
            context,
            state,
            columns,
            deal,
            row_index,
            mode,
            on_deal_saved,
            selected=selected,
            start_column_index=start_column_index,
        )
        mode_cache[cache_key] = cached
        return cached
    _register_cached_column_controls(state, mode, cached, row_index, start_column_index=start_column_index)
    return cached


def _register_cached_column_controls(
    state: dict[str, Any],
    mode: str,
    controls: list[ft.Control],
    row_index: int,
    start_column_index: int = 0,
) -> None:
    mode_columns = state.setdefault("mode_column_controls", {}).setdefault(mode, {})
    for column_index, control in enumerate(controls, start=start_column_index):
        control.data = {"row_index": row_index, "column_index": column_index}
        control.animate_opacity = 100
        control.animate_offset = None
        mode_columns.setdefault(column_index, []).append(control)


def _row_cells(
    context,
    state: dict[str, Any],
    columns: tuple[ColumnSpec, ...],
    deal: Deal,
    row_index: int,
    mode: str,
    on_deal_saved,
    selected: bool = False,
    start_column_index: int = 0,
) -> list[ft.Control]:
    return [
        _animated_column_control(
            state,
            column_index,
            ft.Container(
                width=width,
                padding=ft.Padding(CELL_X_PADDING, 0, CELL_X_PADDING, 0),
                alignment=ft.Alignment.CENTER_RIGHT if numeric else ft.Alignment.CENTER_LEFT,
                bgcolor=_base_cell_bg(deal, column_index, selected),
                gradient=_base_cell_gradient(deal, column_index),
                border=_base_cell_border(column_index),
                content=_cell_content(
                    context,
                    state,
                    field_name,
                    getter,
                    deal,
                    width - CELL_X_PADDING * 2,
                    numeric,
                    mode,
                    on_deal_saved,
                ),
            ),
            row_index=row_index,
            mode=mode,
        )
        for column_index, (_, field_name, getter, width, numeric) in enumerate(
            columns,
            start=start_column_index,
        )
    ]


def _animated_column_control(
    state: dict[str, Any],
    column_index: int,
    control: ft.Control,
    row_index: int | None = None,
    mode: str | None = None,
) -> ft.Control:
    control.data = {"row_index": row_index, "column_index": column_index}
    if mode is not None:
        mode_columns = state.setdefault("mode_column_controls", {}).setdefault(mode, {})
        mode_columns.setdefault(column_index, []).append(control)
    control.animate_opacity = 100
    control.animate_offset = None
    return control


def _deal_selection_key(deal: Deal) -> str:
    if deal.id is not None:
        return f"id:{deal.id}"
    if deal.external_deal_id:
        return f"external:{deal.external_deal_id}"
    return "|".join(
        (
            str(deal.client_name or ""),
            str(deal.client_fix_date or ""),
            str(deal.deal_amount or ""),
            str(deal.deal_currency or ""),
        )
    )


def _selected_row_bg() -> str:
    return "#F5F3FF"


def _row_border(selected: bool, hovered: bool = False) -> ft.Border:
    if selected:
        width = 1.4
        color = "#8B5CF6"
    elif hovered:
        width = 1.4
        color = "#60A5FA"
    else:
        width = 1
        color = ui_theme.BORDER
    return ft.Border(
        bottom=ft.BorderSide(width, color),
    )


def _base_cell_bg(deal: Deal, column_index: int, selected: bool, hovered: bool = False) -> str | None:
    if hovered:
        return "#F8FBFF"
    if column_index < len(BASE_FIELDS):
        return None
    return _selected_row_bg() if selected else None


def _base_cell_gradient(deal: Deal | None, column_index: int, hovered: bool = False) -> ft.LinearGradient | None:
    if hovered or column_index >= len(BASE_FIELDS):
        return None
    return _deal_cell_gradient(deal)


def _base_cell_border(column_index: int) -> ft.Border | None:
    if column_index == len(BASE_FIELDS) - 1:
        return ft.Border(right=ft.BorderSide(1, "#CBD5E1"))
    return None


def _deal_row_bg(deal: Deal | None) -> str:
    if deal is None:
        return ui_theme.SURFACE
    if _is_usdt_deal(deal):
        return "#F4F0FF" if _is_export_deal(deal) else "#ECFEFF"
    if _is_export_deal(deal):
        return "#FFF1F1"
    return "#F0FAF4"


def _deal_cell_gradient(deal: Deal | None, hovered: bool = False) -> ft.LinearGradient:
    if deal is None:
        colors = ("#FFFFFF", "#F8FAFC")
    elif _is_usdt_deal(deal) and _is_export_deal(deal):
        colors = ("#FBF7FF", "#EFE7FF")
    elif _is_usdt_deal(deal):
        colors = ("#F4FDFF", "#DDF7FB")
    elif _is_export_deal(deal):
        colors = ("#FFF8F8", "#FCEDED")
    else:
        colors = ("#F7FFF9", "#EAF8F0")
    return ft.LinearGradient(
        begin=ft.Alignment(-1, 0),
        end=ft.Alignment(1, 0),
        colors=list(colors),
    )


def _deal_row_border(deal: Deal | None) -> ft.Border:
    if deal is None:
        return _row_border(False)
    if _is_usdt_deal(deal) and _is_export_deal(deal):
        color = "#D8B4FE"
    elif _is_usdt_deal(deal):
        color = "#99F6E4"
    elif _is_export_deal(deal):
        color = "#F3C2C2"
    else:
        color = "#BCE6CC"
    return ft.Border(bottom=ft.BorderSide(1, color))


def _is_usdt_deal(deal: Deal) -> bool:
    return str(deal.deal_currency or "").strip().upper() == "USDT"


def _is_export_deal(deal: Deal) -> bool:
    operation_type = str(deal.operation_type or "").strip().upper()
    if operation_type == "EXPORT":
        return True
    return float(deal.deal_amount or deal.amount_buy or 0.0) < 0


def _apply_selected_row_style(row: ft.Container) -> None:
    hovered = bool(row.data.get("hovered")) if isinstance(row.data, dict) else False
    row.bgcolor = ui_theme.SURFACE
    row.border = _row_border(True, hovered)
    _apply_row_hover_overlay(row, hovered, selected=True)
    _apply_row_cell_styles(row, selected=True)


def _apply_default_row_style(row: ft.Container) -> None:
    hovered = bool(row.data.get("hovered")) if isinstance(row.data, dict) else False
    deal = row.data.get("deal") if isinstance(row.data, dict) else None
    row.bgcolor = ui_theme.SURFACE
    row.border = _row_border(False, hovered)
    _apply_row_hover_overlay(row, hovered, selected=False)
    _apply_row_cell_styles(row, selected=False)


def _apply_row_hover_overlay(row: ft.Container, hovered: bool, selected: bool) -> None:
    row.foreground_decoration = None


def _apply_row_cell_styles(row: ft.Container, selected: bool, hovered: bool = False) -> None:
    if isinstance(row.data, dict) and "scroll_cells" in row.data:
        deal = row.data.get("deal")
        for column_index, control in enumerate(row.data.get("pinned_cells") or []):
            if isinstance(control, ft.Container):
                data = getattr(control, "data", None)
                actual_index = int(data.get("column_index", column_index)) if isinstance(data, dict) else column_index
                control.bgcolor = "#F8FBFF" if hovered else None
                control.gradient = None if hovered else _deal_cell_gradient(deal)
                control.border = _base_cell_border(actual_index)
        for fallback_index, control in enumerate(row.data.get("scroll_cells") or [], start=PINNED_COLUMN_COUNT):
            if isinstance(control, ft.Container):
                data = getattr(control, "data", None)
                column_index = int(data.get("column_index", fallback_index)) if isinstance(data, dict) else fallback_index
                control.bgcolor = _selected_row_bg() if selected else ("#F8FBFF" if hovered else None)
                control.gradient = None
                control.border = _base_cell_border(column_index)
        return
    if not isinstance(row.content, ft.Row):
        return
    deal = row.data.get("deal") if isinstance(row.data, dict) else None
    for fallback_index, control in enumerate(row.content.controls):
        if isinstance(control, ft.Container):
            data = getattr(control, "data", None)
            column_index = int(data.get("column_index", fallback_index)) if isinstance(data, dict) else fallback_index
            if column_index < len(BASE_FIELDS):
                control.bgcolor = "#F8FBFF" if hovered else None
                control.gradient = None if hovered else _deal_cell_gradient(deal)
            else:
                control.bgcolor = _selected_row_bg() if selected else ("#F8FBFF" if hovered else None)
                control.gradient = None
            control.border = _base_cell_border(column_index)



def _visible_columns(mode: str) -> tuple[ColumnSpec, ...]:
    if mode == "all":
        base_columns = [COLUMN_BY_FIELD[field_name] for field_name in BASE_FIELDS if field_name in COLUMN_BY_FIELD]
        base_keys = set(BASE_FIELDS)
        remaining_columns = [column for column in EXCEL_COLUMNS if column[1] not in base_keys]
        return tuple([*base_columns, *remaining_columns])
    mode_fields = {
        "general": GENERAL_FIELDS,
        "rates": RATES_FIELDS,
        "finance_usd": FINANCE_COMMON_FIELDS,
        "finance_currency": FINANCE_CURRENCY_FIELDS,
        "pnl": (),
    }.get(mode, GENERAL_FIELDS)
    fields = [*BASE_FIELDS, *mode_fields]
    unique_fields = list(dict.fromkeys(fields))
    columns = [COLUMN_BY_FIELD[field_name] for field_name in unique_fields if field_name in COLUMN_BY_FIELD]
    if mode == "finance_usd":
        columns = [column for column in columns if column[1] != "customer_article_name"]
        columns.extend(FINANCE_USD_COMPUTED_COLUMNS)
        if "customer_article_name" in COLUMN_BY_FIELD:
            columns.append(COLUMN_BY_FIELD["customer_article_name"])
        columns.extend(FINANCE_RATE_COLUMNS)
    if mode == "finance_currency":
        columns.extend(FINANCE_RATE_COLUMNS)
    if mode == "pnl":
        columns.extend(PNL_COMPUTED_COLUMNS)
    return tuple(columns)


def _column_value(context, state: dict[str, Any], field_name: str | None, getter: ColumnGetter, deal: Deal) -> Any:
    if field_name == "__deal_amount_usd":
        return _format_usd_amount(deal.deal_amount, deal.deal_currency, deal)
    if field_name == "__fixed_commission_usd":
        return _format_usd_amount(deal.fixed_commission_amount, deal.fixed_commission_currency, deal, context)
    if field_name == "__swift_usd":
        return _format_usd_amount(deal.swift_amount, deal.swift_currency, deal, context)
    if field_name == "__agent_commission_usd":
        return _format_usd_amount(deal.agent_commission_amount, deal.agent_commission_currency, deal, context)
    if field_name == "__swift_commission_usd":
        return _format_usd_amount(deal.swift_commission_amount, deal.swift_commission_currency, deal, context)
    if field_name == "__client_percent_fee_usd":
        return _format_optional_usd_value(_client_percent_fee_usd(deal))
    if field_name == "__repeat_payment_penalty_usd":
        return _format_optional_usd_value(_repeat_payment_penalty_usd(deal))
    if field_name == "__pnl_usd":
        return _format_optional_usd_value(_pnl_usd(context, state, deal))
    if field_name == "__referral_rate":
        return _manual_or_calculated_referral(context, state, deal).label
    return getter(deal)


def _header_cell(
    context,
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    label: str,
    field_name: str,
    width: int,
    numeric: bool,
    column_index: int,
    mode: str,
) -> ft.Control:
    is_pnl = mode == "pnl"
    is_filterable_computed = bool(field_name and field_name in COMPUTED_FILTER_COLUMNS)
    is_computed = not field_name or field_name.startswith("__")
    active = (
        False
        if is_computed and not is_filterable_computed
        else bool(state["column_filters"].get(field_name))
        or bool(state["column_search_filters"].get(field_name))
        or bool(field_name == "external_deal_id" and state.get("suspicious_rates_only"))
        or bool(field_name == "client_name" and state["column_filters"].get("review_status"))
    )
    is_sorted = state["sort_by"] == field_name
    icon = ft.Icons.FILTER_ALT if active else ft.Icons.FILTER_ALT_OUTLINED
    sort_icon = ft.Icons.SOUTH if state.get("sort_desc") else ft.Icons.NORTH
    filter_control: ft.Control
    if is_computed and not is_filterable_computed:
        filter_control = ft.Container(height=22)
    else:
        def open_filter(event: ft.TapEvent) -> None:
            _open_header_filter_overlay(
                context,
                state,
                sort_by,
                refresh,
                label,
                field_name,
                numeric,
                event.global_position,
                _open_date_picker,
                _calendar_icon_button,
            )

        filter_control = ft.Container(
            content=ft.Container(
                content=ft.Icon(icon, size=13, color="#F4D58A" if is_pnl else ui_theme.PRIMARY if active else "#64748B"),
                width=24,
                height=22,
                alignment=ft.Alignment.CENTER,
                border_radius=7,
                bgcolor="#3A2810" if is_pnl else "#DBEAFE" if active else "#FFFFFF",
                border=ui_theme.border("#D6A84F" if is_pnl else "#93C5FD" if active else "#CBD5E1"),
                shadow=ft.BoxShadow(blur_radius=10 if is_pnl else 8, color="#D6A84F2A" if is_pnl else "#1E3A8A12", offset=ft.Offset(0, 2)),
                tooltip="Фильтр и сортировка",
            ),
            on_tap_down=open_filter,
        )
    return _animated_column_control(
        state,
        column_index,
        ft.Container(
            width=width,
            height=HEADER_HEIGHT,
            padding=ft.Padding(6, 7, 6, 14),
            bgcolor="#2A1C0C" if is_pnl and (active or is_sorted) else "#171009" if is_pnl else "#EEF5FF" if active or is_sorted else "#F8FBFF",
            border=ft.Border(
                right=ft.BorderSide(1, "#5F4219" if is_pnl else "#D8E2F0"),
                bottom=ft.BorderSide(
                    2 if active or is_sorted else 1,
                    "#D6A84F" if is_pnl and (active or is_sorted) else "#5F4219" if is_pnl else ui_theme.PRIMARY if active or is_sorted else "#D8E2F0",
                ),
            ),
            content=ft.Column(
                controls=[
                    ft.Container(
                        height=33,
                        alignment=ft.Alignment.CENTER_RIGHT if numeric else ft.Alignment.CENTER_LEFT,
                        content=ft.Text(
                            label,
                            max_lines=2,
                            overflow=ft.TextOverflow.CLIP,
                            size=HEADER_FONT_SIZE,
                            weight=ft.FontWeight.W_700,
                            color="#F8E7BA" if is_pnl else ui_theme.TEXT,
                            text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT,
                        ),
                    ),
                    ft.Row(
                        height=22,
                        controls=[
                            _header_sort_badge(sort_icon, is_pnl) if is_sorted else ft.Container(width=1, height=22),
                            ft.Container(expand=True),
                            filter_control,
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=3,
                tight=True,
            ),
        ),
        mode=mode,
    )


def _header_sort_badge(icon: str, is_pnl: bool = False) -> ft.Control:
    return ft.Container(
        width=22,
        height=22,
        border_radius=999,
        bgcolor="#D6A84F" if is_pnl else ui_theme.PRIMARY,
        alignment=ft.Alignment.CENTER,
        tooltip="Активная сортировка",
        content=ft.Icon(icon, size=12, color="#171009" if is_pnl else ft.Colors.WHITE),
    )



def _format_usd_amount(amount: float | None, currency: str | None, deal: Deal, context=None) -> str:
    if amount is None:
        return "-"
    value = _usd_amount_value(amount, currency, deal, context)
    if value is None:
        return "Нет курса"
    return _format_number(value, 2)


def _format_optional_usd_value(value: float | None) -> str:
    if value is None:
        return "Нет данных"
    return _format_number(value, 2)


def _client_percent_fee_usd(deal: Deal) -> float | None:
    if _is_client_refund(deal):
        return 0.0
    if deal.pnl_client_percent_fee_usd is not None:
        return abs(float(deal.pnl_client_percent_fee_usd))
    amount_usd = _usd_amount_value(deal.deal_amount, deal.deal_currency, deal)
    if amount_usd is None:
        return None
    repeat_fee = _repeat_payment_commission_usd(deal)
    if repeat_fee is None:
        return None
    return amount_usd * _client_rate_fraction(deal.client_rate_percent) + repeat_fee


def _base_client_percent_fee_usd(deal: Deal) -> float | None:
    if _is_client_refund(deal):
        return 0.0
    amount_usd = _usd_amount_value(deal.deal_amount, deal.deal_currency, deal)
    if amount_usd is None:
        return None
    return amount_usd * _client_rate_fraction(deal.client_rate_percent)


def _repeat_payment_commission_usd(deal: Deal) -> float | None:
    if _is_client_refund(deal):
        return 0.0
    if not deal.is_repeat_payment:
        return 0.0
    amount_usd = _usd_amount_value(deal.deal_amount, deal.deal_currency, deal)
    if amount_usd is None:
        return None
    return amount_usd * _client_rate_fraction(deal.repeat_payment_commission_percent)


def _repeat_payment_penalty_usd(deal: Deal) -> float:
    return float(deal.repeat_payment_penalty_usd or 0.0) if deal.is_repeat_payment else 0.0


def _pnl_usd(context, state: dict[str, Any], deal: Deal) -> float | None:
    return _pnl_breakdown(context, state, deal).pnl


def _pnl_breakdown(context, state: dict[str, Any], deal: Deal) -> _PnlBreakdown:
    cache = state.setdefault("pnl_breakdown_cache", {})
    cache_key = _deal_pnl_cache_key(deal)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    with perf_span_if_slow("deals.calc.pnl_breakdown", 8.0, deal_id=deal.id, external_deal_id=deal.external_deal_id):
        breakdown = _PnlBreakdown(
            client_percent_fee=_cached_client_percent_fee_usd(state, deal),
            fixed_commission=_cached_usd_component_value(context, state, deal, "__fixed_commission_usd"),
            swift=_cached_usd_component_value(context, state, deal, "__swift_usd"),
            agent_commission=_cached_usd_component_value(context, state, deal, "__agent_commission_usd"),
            swift_commission=_cached_usd_component_value(context, state, deal, "__swift_commission_usd"),
            referral=_manual_or_calculated_referral(context, state, deal),
            repeat_payment_penalty=_repeat_payment_penalty_usd(deal),
        )
    cache[cache_key] = breakdown
    return breakdown


def _deal_pnl_cache_key(deal: Deal) -> tuple[Any, ...]:
    return (
        deal.id,
        deal.deal_amount,
        deal.deal_currency,
        deal.client_rate_percent,
        deal.fixed_commission_amount,
        deal.fixed_commission_currency,
        deal.swift_amount,
        deal.swift_currency,
        deal.agent_commission_amount,
        deal.agent_commission_currency,
        deal.swift_commission_amount,
        deal.swift_commission_currency,
        deal.customer_article_name,
        deal.payment_agent,
        deal.client_fix_date,
        deal.client_cross_rate,
        deal.operation_type,
        deal.pnl_client_percent_fee_usd,
        deal.pnl_fixed_commission_usd,
        deal.pnl_swift_usd,
        deal.pnl_agent_commission_usd,
        deal.pnl_swift_commission_usd,
        deal.pnl_referral_commission_usd,
        deal.is_repeat_payment,
        deal.repeat_payment_commission_percent,
        deal.repeat_payment_penalty_usd,
    )


def _cached_client_percent_fee_usd(state: dict[str, Any], deal: Deal) -> float | None:
    cache = state.setdefault("usd_component_cache", {})
    cache_key = ("__client_percent_fee_usd", _deal_pnl_cache_key(deal))
    if cache_key not in cache:
        cache[cache_key] = _client_percent_fee_usd(deal)
    return cache[cache_key]


def _cached_usd_component_value(
    context,
    state: dict[str, Any],
    deal: Deal,
    field_name: str,
) -> float | None:
    cache = state.setdefault("usd_component_cache", {})
    cache_key = (field_name, _deal_pnl_cache_key(deal))
    if cache_key in cache:
        return cache[cache_key]
    with perf_span_if_slow(
        "deals.calc.usd_component",
        5.0,
        field=field_name,
        deal_id=deal.id,
        external_deal_id=deal.external_deal_id,
    ):
        value = _calculate_usd_component_value(context, deal, field_name)
    cache[cache_key] = value
    return value


def _calculate_usd_component_value(context, deal: Deal, field_name: str) -> float | None:
    if _is_client_refund(deal) and field_name in {"__fixed_commission_usd", "__swift_usd"}:
        return 0.0
    _, amount_attr, currency_attr = USD_COMPONENT_FIELDS[field_name]
    manual_attr = _usd_component_manual_attr(field_name)
    manual_value = getattr(deal, manual_attr, None) if manual_attr else None
    if manual_value is not None:
        return float(manual_value)
    amount = getattr(deal, amount_attr, None)
    currency = getattr(deal, currency_attr, None) or deal.deal_currency or ""
    return _usd_component_or_zero(amount, currency, deal, context)


def _usd_component_manual_attr(field_name: str | None) -> str | None:
    return {
        "__fixed_commission_usd": "pnl_fixed_commission_usd",
        "__swift_usd": "pnl_swift_usd",
        "__agent_commission_usd": "pnl_agent_commission_usd",
        "__swift_commission_usd": "pnl_swift_commission_usd",
    }.get(str(field_name))


def _cached_tooltip(state: dict[str, Any], cache_key: tuple[Any, ...], factory) -> str:
    cache = state.setdefault("tooltip_cache", {})
    if cache_key not in cache:
        cache[cache_key] = factory()
    return cache[cache_key]


def _manual_or_calculated_usd(
    manual_value: float | None,
    amount: float | None,
    currency: str | None,
    deal: Deal,
    context=None,
) -> float | None:
    if _is_client_refund(deal) and _is_client_income_component(amount, currency, deal):
        return 0.0
    if manual_value is not None:
        return float(manual_value)
    return _usd_component_or_zero(amount, currency, deal, context)


def _is_client_income_component(amount: float | None, currency: str | None, deal: Deal) -> bool:
    return (
        amount == deal.fixed_commission_amount
        and currency == deal.fixed_commission_currency
    ) or (
        amount == deal.swift_amount
        and currency == deal.swift_currency
    )


def _manual_or_calculated_referral(context, state: dict[str, Any], deal: Deal) -> _ReferralCommissionResult:
    if _is_client_refund(deal):
        return _client_refund_referral_commission_result(deal.customer_article_name or deal.payment_agent)
    if deal.is_repeat_payment:
        return _repeat_payment_referral_commission_result(deal.customer_article_name or deal.payment_agent)
    if deal.pnl_referral_commission_usd is None:
        return _referral_commission_result(context, state, deal)
    value = float(deal.pnl_referral_commission_usd)
    return _ReferralCommissionResult(
        f"{_format_number(value, 2)} USD",
        "\n".join(
            (
                "Ставка реферала введена вручную в карточке сделки.",
                f"Ручное значение: {_format_number(value, 2)} USD",
                "Итоговый PnL пересчитывается от этого значения.",
            )
        ),
        True,
        value,
    )


def _usd_component_or_zero(amount: float | None, currency: str | None, deal: Deal, context=None) -> float | None:
    if amount is None or float(amount) == 0:
        return 0.0
    return _usd_amount_value(amount, currency, deal, context)


def _percent_fraction(value: float | int | None) -> float:
    if value is None:
        return 0.0
    numeric = float(value)
    return numeric if abs(numeric) <= 1 else numeric / 100


def _client_rate_fraction(value: float | int | None) -> float:
    return abs(_percent_fraction(value))


def _usd_amount_value(amount: float | None, currency: str | None, deal: Deal, context=None) -> float | None:
    if amount is None:
        return None
    normalized_currency = normalize_rate_currency(currency or deal.deal_currency or "")
    if normalized_currency in USD_LIKE_CURRENCIES:
        return abs(float(amount))
    if context is not None and normalized_currency != normalize_rate_currency(deal.deal_currency or ""):
        value = _usd_amount_from_rate_registry(float(amount), normalized_currency, deal, context)
        if value is not None:
            return abs(value)
        return None
    rate = _usd_cross_rate(deal)
    if rate is None:
        return None
    value = _convert_by_currency_strength(float(amount), normalized_currency, rate)
    return abs(value)


def _usd_cross_rate(deal: Deal) -> float | None:
    if deal.client_cross_rate is not None and float(deal.client_cross_rate) > 0:
        return float(deal.client_cross_rate)
    return None


def _usd_amount_from_rate_registry(amount: float, currency: str, deal: Deal, context) -> float | None:
    rate_date = _component_rate_date(deal)
    if not rate_date:
        return None
    currency_rate = _preferred_rate_per_unit(context, rate_date, currency)
    usd_rate = _preferred_rate_per_unit(context, rate_date, "USD")
    if currency_rate is None or usd_rate is None or usd_rate <= 0:
        return None
    return amount * currency_rate / usd_rate


def _component_rate_date(deal: Deal) -> str | None:
    return _parse_optional_date(deal.client_fix_date or deal.request_date or deal.trade_date)


def _preferred_rate_per_unit(context, rate_date: str, currency: str) -> float | None:
    normalized_currency = normalize_rate_currency(currency)
    if normalized_currency == "RUB":
        return 1.0
    rate = context.rates_repository.find_preferred(rate_date, normalized_currency)
    if rate is None:
        return None
    nominal = CBR_RATE_NOMINALS.get(normalized_currency, 1) if str(rate.source or "").upper() == "CBR" else 1
    return float(rate.rate_to_rub) / nominal


def _referral_commission_result(context, state: dict[str, Any], deal: Deal) -> _ReferralCommissionResult:
    cache = state.setdefault("referral_rate_cache", {})
    referral_name = deal.customer_article_name or deal.payment_agent or ""
    if _is_client_refund(deal):
        return _client_refund_referral_commission_result(referral_name)
    if deal.is_repeat_payment:
        return _repeat_payment_referral_commission_result(referral_name)
    deal_currency = (deal.deal_currency or "").upper()
    deal_amount = abs(float(deal.deal_amount or 0.0))
    amount_usd = _usd_amount_value(deal.deal_amount, deal.deal_currency, deal)
    cache_key = (
        referral_name,
        deal_currency,
        round(deal_amount, 2),
        round(amount_usd, 2) if amount_usd is not None else None,
        deal.client_fix_date or "",
        _deal_operation_type(deal) or "",
        bool(deal.is_repeat_payment),
        deal.client_rate_percent,
        deal.repeat_payment_commission_percent,
        deal.fixed_commission_amount,
        deal.fixed_commission_currency,
        deal.pnl_client_percent_fee_usd,
        deal.pnl_fixed_commission_usd,
    )
    if cache_key in cache:
        return cache[cache_key]
    if not referral_name.strip():
        result = _ReferralCommissionResult(
            "Нет реферала",
            "В сделке не заполнен реферал. Ставка реферала не подбиралась.",
            False,
        )
        cache[cache_key] = result
        return result
    if not deal.client_fix_date:
        result = _ReferralCommissionResult(
            "Нет даты",
            "Ставка не подбирается: в сделке не заполнена Дата фиксации с клиентом.",
            False,
        )
        cache[cache_key] = result
        return result
    try:
        referral, rules = _cached_active_referral_rules(context, state, referral_name)
        match = context.rate_rules_engine.find_rate_from_rules(
            rules=rules,
            bank_name=referral.name if referral is not None else referral_name,
            currency=deal_currency,
            amount=deal_amount,
            amount_usd=amount_usd,
            region=None,
            deal_date=deal.client_fix_date,
            operation_type=_deal_operation_type(deal),
        )
        condition = next((rule for rule in rules if rule.id == match.matched_rule_id), None)
        if condition is None:
            result = _ReferralCommissionResult("Нет ставки", "Условие ставки не найдено в справочнике.", False)
        else:
            result = _build_referral_commission_result(context, state, deal, referral_name, match, condition, deal_amount, amount_usd)
    except _InactiveReferralError:
        result = _inactive_referral_commission_result(referral_name)
    except Exception:
        result = (
            _zero_referral_commission_result(referral_name)
            if _is_zero_referral(referral_name)
            else _ReferralCommissionResult(
                "Нет ставки",
                "Ставка не найдена: нет подходящего активного условия для реферала, валюты, суммы и даты сделки.",
                False,
            )
        )
    cache[cache_key] = result
    return result


def _cached_active_referral_rules(context, state: dict[str, Any], referral_name: str):
    cache = state.setdefault("active_referral_rules_cache", {})
    key = str(referral_name or "").strip().casefold()
    if key in cache:
        return cache[key]
    referral = context.referrals_repository.find_by_name_or_code(referral_name)
    if referral is None or referral.id is None:
        raise LookupError("Ставка не найдена")
    if not referral.is_active:
        raise _InactiveReferralError(referral.name)
    rules = context.rate_conditions_repository.list_active(referral.id)
    result = (referral, rules)
    cache[key] = result
    return result


def _is_zero_referral(referral_name: str | None) -> bool:
    return str(referral_name or "").strip().casefold() == "без банка"


def _zero_referral_commission_result(referral_name: str | None) -> _ReferralCommissionResult:
    return _ReferralCommissionResult(
        "0,00 USD",
        f"Реферал: {referral_name or 'Без банка'}\nСтавка не найдена, для 'Без банка' комиссия считается равной 0 USD.",
        True,
        0.0,
    )


def _repeat_payment_referral_commission_result(referral_name: str | None) -> _ReferralCommissionResult:
    return _ReferralCommissionResult(
        "0,00 USD",
        f"Реферал: {referral_name or '-'}\nПовторная переотправка: комиссия реферала не применяется. Процент и фикс считаются равными 0 USD.",
        True,
        0.0,
    )


def _client_refund_referral_commission_result(referral_name: str | None) -> _ReferralCommissionResult:
    return _ReferralCommissionResult(
        "0,00 USD",
        f"Реферал: {referral_name or '-'}\nЗаполнена дата возврата средств клиенту. Комиссия реферала, процент и фикс считаются равными 0 USD.",
        True,
        0.0,
    )


def _inactive_referral_commission_result(referral_name: str | None) -> _ReferralCommissionResult:
    return _ReferralCommissionResult(
        "0,00 USD",
        f"Реферал: {referral_name or '-'}\nРеферал неактивен. Комиссия реферала считается равной 0 USD.",
        True,
        0.0,
    )


def _deal_operation_type(deal: Deal) -> str | None:
    text = str(deal.operation_type or "").strip().casefold()
    if text in {"import", "импорт"}:
        return "import"
    if text in {"export", "экспорт"}:
        return "export"
    if deal.deal_amount is not None and float(deal.deal_amount) < 0:
        return "export"
    if deal.deal_amount is not None:
        return "import"
    return None


def _build_referral_commission_result(
    context,
    state: dict[str, Any],
    deal: Deal,
    referral_name: str,
    match: Any,
    condition: Any,
    deal_amount: float,
    amount_usd: float | None,
) -> _ReferralCommissionResult:
    deal_currency = (deal.deal_currency or "").upper()
    basis_is_usd = getattr(condition, "amount_basis", "") == "usd_equivalent"
    base_amount = amount_usd if basis_is_usd else deal_amount
    base_currency = "USD" if basis_is_usd else deal_currency
    if base_amount is None:
        return _ReferralCommissionResult(
            "Нет курса",
            "Нельзя посчитать ставку реферала: для диапазона eq. USD нужен кросс-курс сделки.",
            False,
        )

    rate_percent = float(getattr(condition, "rate_value", 0.0) or 0.0)
    rate_fraction = rate_percent / 100
    percent_native = abs(float(base_amount)) * rate_fraction
    percent_currency = (getattr(condition, "percent_commission_currency", None) or base_currency or deal_currency).upper()
    percent_usd = _convert_component_to_usd(percent_native, percent_currency, deal)
    if percent_usd is None:
        return _ReferralCommissionResult(
            "Нет курса",
            f"Нельзя перевести процентную комиссию из {percent_currency or 'валюты сделки'} в USD: нет кросс-курса.",
            False,
        )

    fixed_amount = abs(float(getattr(condition, "fixed_commission_amount", 0.0) or 0.0))
    fixed_currency = (
        getattr(condition, "fixed_commission_currency", None)
        or getattr(condition, "percent_commission_currency", None)
        or deal_currency
        or "USD"
    ).upper()
    fixed_usd = 0.0 if fixed_amount == 0 else _convert_component_to_usd(fixed_amount, fixed_currency, deal)
    if fixed_usd is None:
        return _ReferralCommissionResult(
            "Нет курса",
            f"Нельзя перевести фиксированную комиссию из {fixed_currency} в USD: нет кросс-курса.",
            False,
        )

    client_percent_usd = _cached_client_percent_fee_usd(state, deal)
    if client_percent_usd is None:
        return _ReferralCommissionResult(
            "Нет курса",
            "Нельзя посчитать ставку реферала: нет USD-эквивалента для клиентской процентной комиссии.",
            False,
        )
    client_fixed_usd = _cached_usd_component_value(context, state, deal, "__fixed_commission_usd")
    if client_fixed_usd is None:
        return _ReferralCommissionResult(
            "Нет курса",
            "Нельзя посчитать ставку реферала: нет USD-эквивалента для фиксированной комиссии клиента.",
            False,
        )

    condition_total_usd = percent_usd + fixed_usd
    total_usd = client_percent_usd + client_fixed_usd - condition_total_usd
    label = f"{_format_number(total_usd, 2)} USD"
    tooltip = _referral_commission_tooltip(
        deal=deal,
        referral_name=referral_name,
        condition=condition,
        match=match,
        base_amount=abs(float(base_amount)),
        base_currency=base_currency,
        rate_percent=rate_percent,
        percent_native=percent_native,
        percent_currency=percent_currency,
        percent_usd=percent_usd,
        fixed_amount=fixed_amount,
        fixed_currency=fixed_currency,
        fixed_usd=fixed_usd,
        client_percent_usd=client_percent_usd,
        client_fixed_usd=client_fixed_usd,
        condition_total_usd=condition_total_usd,
        total_usd=total_usd,
    )
    return _ReferralCommissionResult(label, tooltip, True, total_usd)


def _convert_component_to_usd(amount: float, currency: str | None, deal: Deal) -> float | None:
    value = float(amount)
    if value == 0:
        return 0.0
    normalized_currency = (currency or deal.deal_currency or "").upper()
    if normalized_currency in USD_LIKE_CURRENCIES:
        return value
    rate = _usd_cross_rate(deal)
    if rate is None:
        return None
    return _convert_by_currency_strength(value, normalized_currency, rate)


def _convert_by_currency_strength(amount: float, currency: str, rate: float) -> float:
    """Convert an amount to USD using the likely quote direction for the currency."""
    return amount * rate if _should_multiply_to_usd(currency, rate) else amount / rate


def _should_multiply_to_usd(currency: str, rate: float) -> bool:
    normalized_currency = currency.strip().upper()
    if normalized_currency in STRONGER_THAN_USD_CURRENCIES:
        return rate >= 1
    return rate < 1


def _referral_commission_tooltip(
    deal: Deal,
    referral_name: str,
    condition: Any,
    match: Any,
    base_amount: float,
    base_currency: str,
    rate_percent: float,
    percent_native: float,
    percent_currency: str,
    percent_usd: float,
    fixed_amount: float,
    fixed_currency: str,
    fixed_usd: float,
    client_percent_usd: float,
    client_fixed_usd: float,
    condition_total_usd: float,
    total_usd: float,
) -> str:
    basis = "eq. USD" if getattr(condition, "amount_basis", "") == "usd_equivalent" else "валюта сделки"
    amount_from = _format_number(getattr(condition, "amount_from", None) or 0, 2)
    amount_to_value = getattr(condition, "amount_to", None)
    amount_to = _format_number(amount_to_value, 2) if amount_to_value is not None else "без лимита"
    date_from = getattr(condition, "date_from", None) or "с начала"
    date_to = getattr(condition, "date_to", None) or "бессрочно"
    cross_rate = _usd_cross_rate(deal)
    conversion_parts = []
    if percent_currency not in USD_LIKE_CURRENCIES and cross_rate:
        operation = "умножение" if _should_multiply_to_usd(percent_currency, cross_rate) else "деление"
        conversion_parts.append(f"%: {operation}")
    if fixed_currency not in USD_LIKE_CURRENCIES and cross_rate:
        operation = "умножение" if _should_multiply_to_usd(fixed_currency, cross_rate) else "деление"
        conversion_parts.append(f"фикс: {operation}")
    cross_text = (
        "не нужен"
        if percent_currency in USD_LIKE_CURRENCIES and fixed_currency in USD_LIKE_CURRENCIES
        else (_format_number(cross_rate, 4) if cross_rate else "нет")
    )
    conversion_text = ", ".join(conversion_parts) if conversion_parts else "не требуется"
    return "\n".join(
        (
            f"Реферал: {referral_name or '-'}",
            f"Условие #{getattr(condition, 'id', None) or getattr(match, 'matched_rule_id', '-')}, база: {basis}",
            f"Диапазон условия: {amount_from}-{amount_to}, даты {date_from}-{date_to}",
            f"База для %: {_format_number(base_amount, 2)} {base_currency or '-'}",
            f"Комиссия клиента %: {_format_number(client_percent_usd, 2)} USD",
            f"Фикс клиента: {_format_number(client_fixed_usd, 2)} USD",
            f"Условие %: {_format_number(rate_percent, 2)}% = {_format_number(percent_native, 2)} {percent_currency or '-'} -> {_format_number(percent_usd, 2)} USD",
            f"Условие фикс: {_format_number(fixed_amount, 2)} {fixed_currency} -> {_format_number(fixed_usd, 2)} USD",
            f"Комиссия по условию: {_format_number(condition_total_usd, 2)} USD",
            f"Кросс-курс: {cross_text}",
            f"Конвертация: {conversion_text}",
            "Формула: комиссия клиента % + фикс клиента - условие % - условие фикс",
            f"Итого: {_format_number(client_percent_usd, 2)} + {_format_number(client_fixed_usd, 2)} - {_format_number(percent_usd, 2)} - {_format_number(fixed_usd, 2)} = {_format_number(total_usd, 2)} USD",
        )
    )


def _cell_content(
    context,
    state: dict[str, Any],
    field_name: str | None,
    getter: ColumnGetter,
    deal: Deal,
    width: int,
    numeric: bool,
    mode: str,
    on_deal_saved,
) -> ft.Control:
    if field_name == "external_deal_id":
        return _external_deal_id_cell(context, deal, width, on_deal_saved)
    if field_name == "client_name":
        return _client_name_cell(context, state, deal, width, on_deal_saved)
    if field_name == "__referral_rate":
        return _referral_commission_cell(
            context,
            state,
            deal,
            width,
            on_deal_saved,
            wait_duration=850 if mode == "pnl" else 250,
        )
    if field_name == "__pnl_usd":
        return _pnl_cell(context, state, deal, width)
    if field_name == "deal_amount" and mode == "pnl":
        return _deal_amount_with_usd_tooltip(deal, width)
    if field_name == "client_rate_percent" and mode in {"finance_usd", "finance_currency", "all"}:
        return _effective_client_rate_percent_cell(deal, width)
    if mode == "pnl" and field_name == "__client_percent_fee_usd":
        return _client_percent_fee_cell(state, deal, width)
    if mode == "pnl" and field_name == "__repeat_payment_penalty_usd":
        return _repeat_payment_penalty_cell(deal, width)
    if field_name in USD_COMPONENT_FIELDS:
        return _usd_component_cell(context, state, deal, field_name, width, on_deal_saved)
    return _cell(_column_value(context, state, field_name, getter, deal), width, numeric)


def _external_deal_id_cell(context, deal: Deal, width: int, on_deal_saved) -> ft.Control:
    label = _blank(deal.external_deal_id)
    indicators: list[ft.Control] = []
    if _has_suspicious_equal_usd_rates(deal):
        indicators.append(_suspicious_rate_icon(context, deal, on_deal_saved))
    if deal.is_repeat_payment:
        indicators.append(_repeat_payment_icon(context, deal, on_deal_saved))
    if not indicators:
        return _cell(label, width, False)
    return ft.Row(
        width=width,
        spacing=5,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                label,
                size=CELL_FONT_SIZE,
                overflow=ft.TextOverflow.ELLIPSIS,
                selectable=False,
                expand=True,
            ),
            *indicators,
        ],
    )


def _client_name_cell(context, state: dict[str, Any], deal: Deal, width: int, on_deal_saved) -> ft.Control:
    label = _blank(deal.client_name)
    status = str(deal.review_status or "").strip()
    status_menu: ft.PopupMenuButton | None = None

    def apply_status(next_status: str | None) -> None:
        targets = _review_status_target_deals(state, deal)
        _save_review_status(context, targets, next_status)
        controls: list[ft.Control] = []
        menus_by_key = state.get("review_status_menus") or {}
        for target in targets:
            menu = menus_by_key.get(_deal_selection_key(target))
            if isinstance(menu, ft.PopupMenuButton):
                _set_review_menu_state(menu, next_status)
                controls.append(menu)
        if controls:
            context.page.update(*controls)

    status_menu = _review_status_menu(status, apply_status)
    state.setdefault("review_status_menus", {})[_deal_selection_key(deal)] = status_menu
    return ft.Row(
        width=width,
        spacing=5,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                label,
                size=CELL_FONT_SIZE,
                overflow=ft.TextOverflow.ELLIPSIS,
                selectable=False,
                expand=True,
            ),
            status_menu,
        ],
    )


def _review_status_menu(status: str, on_status_selected) -> ft.PopupMenuButton:
    icon, color, tooltip = _review_status_icon(status)

    def set_status(next_status: str | None) -> None:
        on_status_selected(next_status)

    return ft.PopupMenuButton(
        icon=icon,
        icon_color=color,
        icon_size=15,
        padding=0,
        menu_position=ft.PopupMenuPosition.UNDER,
        tooltip=tooltip,
        items=[
            ft.PopupMenuItem(
                content=_review_menu_item(ft.Icons.CHECK_CIRCLE, "Проверено", "#16A34A"),
                checked=status == DealReviewStatus.VERIFIED.value,
                height=38,
                on_click=lambda _: set_status(DealReviewStatus.VERIFIED.value),
            ),
            ft.PopupMenuItem(
                content=_review_menu_item(ft.Icons.HELP_OUTLINE, "Под вопросом", "#D97706"),
                checked=status == DealReviewStatus.QUESTION.value,
                height=38,
                on_click=lambda _: set_status(DealReviewStatus.QUESTION.value),
            ),
            ft.PopupMenuItem(
                content=_review_menu_item(ft.Icons.CLOSE, "Снять маркер", "#64748B"),
                height=38,
                on_click=lambda _: set_status(None),
            ),
        ],
    )


def _open_review_status_dialog(context, deal: Deal, on_status_selected) -> None:
    def choose(status: str | None) -> None:
        on_status_selected(status)
        context.page.pop_dialog()

    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=ui_theme.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Text("Маркер проверки", size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
            content=ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    ft.Text(_blank(deal.client_name), size=12, color=ui_theme.MUTED),
                    ft.Row(
                        spacing=8,
                        controls=[
                            _review_dialog_button("Проверено", ft.Icons.CHECK_CIRCLE, "#16A34A", lambda _: choose(DealReviewStatus.VERIFIED.value)),
                            _review_dialog_button("Под вопросом", ft.Icons.HELP_OUTLINE, "#D97706", lambda _: choose(DealReviewStatus.QUESTION.value)),
                        ],
                    ),
                    _review_dialog_button("Снять маркер", ft.Icons.CLOSE, "#64748B", lambda _: choose(None), full_width=True),
                ],
            ),
            actions=[
                ft.TextButton("Закрыть", on_click=lambda _: context.page.pop_dialog()),
            ],
        )
    )


def _review_dialog_button(label: str, icon: Any, color: str, on_click, full_width: bool = False) -> ft.Control:
    return ft.Container(
        expand=full_width,
        padding=ft.Padding(10, 8, 10, 8),
        border_radius=12,
        border=ui_theme.border("#E2E8F0"),
        bgcolor="#FFFFFF",
        ink=True,
        on_click=on_click,
        content=ft.Row(
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=16, color=color),
                ft.Text(label, size=12, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
            ],
        ),
    )


def _review_status_target_deals(state: dict[str, Any], clicked_deal: Deal) -> list[Deal]:
    selected_keys = _selected_deal_keys(state)
    clicked_key = _deal_selection_key(clicked_deal)
    if clicked_key not in selected_keys or len(selected_keys) <= 1:
        return [clicked_deal]
    targets = [
        deal
        for deal in list(state.get("current_deals") or [])
        if _deal_selection_key(deal) in selected_keys and deal.id is not None
    ]
    return targets or [clicked_deal]


def _save_review_status(context, deals: list[Deal], status: str | None) -> None:
    deal_ids = [int(deal.id) for deal in deals if deal.id is not None]
    if not deal_ids:
        return
    context.deals_repository.update_review_status_many(deal_ids, status)
    for deal in deals:
        deal.review_status = status


def _set_review_menu_state(menu: ft.PopupMenuButton, status: str | None) -> None:
    normalized = str(status or "").strip()
    icon, color, tooltip = _review_status_icon(normalized)
    menu.icon = icon
    menu.icon_color = color
    menu.tooltip = tooltip
    if len(menu.items) >= 2:
        menu.items[0].checked = normalized == DealReviewStatus.VERIFIED.value
        menu.items[1].checked = normalized == DealReviewStatus.QUESTION.value


def _review_status_icon(status: str) -> tuple[Any, str, str]:
    if status == DealReviewStatus.VERIFIED.value:
        return ft.Icons.CHECK_CIRCLE, "#16A34A", "Проверено"
    if status == DealReviewStatus.QUESTION.value:
        return ft.Icons.HELP_OUTLINE, "#D97706", "Под вопросом"
    return ft.Icons.MORE_HORIZ, "#94A3B8", "Поставить маркер"


def _review_menu_item(icon: Any, label: str, color: str) -> ft.Control:
    return ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(icon, size=16, color=color),
            ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=ui_theme.TEXT),
        ],
    )


def _effective_client_rate_percent(deal: Deal) -> float:
    if _is_client_refund(deal):
        return 0.0
    base_rate = _client_rate_fraction(deal.client_rate_percent)
    repeat_rate = _client_rate_fraction(deal.repeat_payment_commission_percent) if deal.is_repeat_payment else 0.0
    return base_rate + repeat_rate


def _effective_client_rate_percent_cell(deal: Deal, width: int) -> ft.Control:
    if _is_client_refund(deal):
        tooltip = "\n".join(
            (
                "Общая ставка для клиента",
                f"Дата возврата средств клиенту: {_format_date(deal.client_refund_date)}",
                "По возврату общая ставка считается равной 0,00%.",
            )
        )
        return ft.Container(
            width=width,
            alignment=ft.Alignment.CENTER_RIGHT,
            tooltip=_premium_tooltip(tooltip, wait_duration=850),
            content=ft.Container(
                padding=ft.Padding(8, 2, 8, 3),
                border_radius=999,
                bgcolor="#F1F5F9",
                border=ui_theme.border("#CBD5E1"),
                content=ft.Text(
                    "0,00%",
                    size=CELL_FONT_SIZE,
                    weight=ft.FontWeight.W_800,
                    color="#475569",
                    overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.RIGHT,
                    selectable=False,
                ),
            ),
        )
    base_rate = _client_rate_fraction(deal.client_rate_percent)
    repeat_rate = _client_rate_fraction(deal.repeat_payment_commission_percent) if deal.is_repeat_payment else 0.0
    effective_rate = base_rate + repeat_rate
    tooltip = "\n".join(
        (
            "Общая ставка для клиента",
            f"Базовая ставка: {_display_percent(base_rate)}",
            f"Комиссия за переотправку: {_display_percent(repeat_rate)}" if deal.is_repeat_payment else "Комиссия за переотправку: 0,00%",
            f"Итого: {_display_percent(effective_rate)}",
        )
    )
    if deal.is_repeat_payment and repeat_rate:
        return ft.Container(
            width=width,
            alignment=ft.Alignment.CENTER_RIGHT,
            tooltip=_premium_tooltip(tooltip, wait_duration=850),
            content=ft.Container(
                padding=ft.Padding(8, 2, 8, 3),
                border_radius=999,
                bgcolor="#ECFDF5",
                border=ui_theme.border("#A7F3D0"),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            _display_percent(effective_rate),
                            size=CELL_FONT_SIZE,
                            weight=ft.FontWeight.W_800,
                            color="#047857",
                            overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.RIGHT,
                            selectable=False,
                        ),
                        ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=13, color="#059669"),
                    ],
                ),
            ),
        )
    return ft.Container(
        width=width,
        alignment=ft.Alignment.CENTER_RIGHT,
        tooltip=_premium_tooltip(tooltip, wait_duration=850),
        content=_cell(_display_percent(effective_rate), width, True),
    )


def _suspicious_rate_icon(context, deal: Deal, on_deal_saved) -> ft.Control:
    return ft.Container(
        width=22,
        height=22,
        border_radius=8,
        bgcolor="#FEF2F2",
        border=ui_theme.border("#FCA5A5"),
        alignment=ft.Alignment.CENTER,
        tooltip="Курс фиксации совпадает с курсом к USD. Нажмите, чтобы подтянуть курсы ЦБ.",
        ink=True,
        ink_color="#FEE2E2",
        on_click=lambda _: context.page.run_task(_open_rate_correction_dialog, context, deal, on_deal_saved),
        content=ft.Icon(ft.Icons.PRIORITY_HIGH_ROUNDED, size=15, color="#DC2626"),
    )


def _repeat_payment_icon(context, deal: Deal, on_deal_saved) -> ft.Control:
    configured = _repeat_payment_configured(deal)
    return ft.Container(
        width=22,
        height=22,
        border_radius=8,
        bgcolor="#ECFDF5" if configured else "#FFF7ED",
        border=ui_theme.border("#86EFAC" if configured else "#FDBA74"),
        alignment=ft.Alignment.CENTER,
        tooltip=(
            "Повторный платеж настроен. Нажмите, чтобы изменить комиссию и штраф."
            if configured
            else "Повторный платеж. Нажмите, чтобы ввести комиссию за переотправку и штраф."
        ),
        ink=True,
        ink_color="#DCFCE7" if configured else "#FFEDD5",
        on_click=lambda _: _open_repeat_payment_dialog(context, deal, on_deal_saved),
        content=ft.Icon(
            ft.Icons.CHECK_CIRCLE if configured else ft.Icons.REPLAY_CIRCLE_FILLED_OUTLINED,
            size=15,
            color="#16A34A" if configured else "#D97706",
        ),
    )


def _repeat_payment_configured(deal: Deal) -> bool:
    return deal.repeat_payment_commission_percent is not None and deal.repeat_payment_penalty_usd is not None


def _open_repeat_payment_dialog(context, deal: Deal, on_deal_saved) -> None:
    percent_field = ft.TextField(
        label="Процент комиссии за переотправку",
        value=_display_percent(deal.repeat_payment_commission_percent).replace("%", ""),
        suffix=ft.Text("%", size=12, weight=ft.FontWeight.W_700, color=ui_theme.MUTED),
        dense=True,
        filled=True,
        fill_color="#F8FAFC",
        border_color="#D8E2F0",
        focused_border_color=ui_theme.PRIMARY,
        border_radius=12,
    )
    penalty_field = ft.TextField(
        label="Штраф",
        value=_format_number(deal.repeat_payment_penalty_usd, 2) if deal.repeat_payment_penalty_usd is not None else "0,00",
        suffix=ft.Text("USD", size=12, weight=ft.FontWeight.W_700, color=ui_theme.MUTED),
        dense=True,
        filled=True,
        fill_color="#F8FAFC",
        border_color="#D8E2F0",
        focused_border_color=ui_theme.PRIMARY,
        border_radius=12,
    )

    def save(_: ft.ControlEvent | None = None) -> None:
        try:
            updated = replace(
                deal,
                is_repeat_payment=True,
                repeat_payment_commission_percent=_parse_percent_input(percent_field.value),
                repeat_payment_penalty_usd=_parse_money_input(penalty_field.value),
                pnl_client_percent_fee_usd=None,
            )
            context.deals_repository.update(updated)
            context.page.pop_dialog()
            on_deal_saved(updated)
        except Exception as exc:
            context.page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Не удалось сохранить повторный платеж"),
                    content=ft.Text(str(exc)),
                    actions=[ft.TextButton("ОК", on_click=lambda _: context.page.pop_dialog())],
                )
            )

    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=ui_theme.SURFACE,
            barrier_color="#0F172A66",
            title=ft.Row(
                controls=[
                    ft.Container(
                        width=40,
                        height=40,
                        border_radius=12,
                        bgcolor="#EFF6FF",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.REPLAY_CIRCLE_FILLED_OUTLINED, color=ui_theme.PRIMARY, size=22),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Повторный платеж", size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                            ft.Text(f"Сделка {deal.external_deal_id or deal.id or '-'}", size=12, color=ui_theme.MUTED),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Комиссия за переотправку добавится к комиссии клиента %, штраф уменьшит итоговый PnL.",
                            size=12,
                            color=ui_theme.MUTED,
                        ),
                        percent_field,
                        penalty_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
                ui_theme.primary_button("Сохранить", icon=ft.Icons.CHECK, on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _parse_percent_input(value: str | None) -> float:
    text = str(value or "").replace("%", "").replace(" ", "").replace(",", ".").strip()
    if not text:
        return 0.0
    return float(text) / 100


def _parse_money_input(value: str | None) -> float:
    text = str(value or "").replace("USD", "").replace(" ", "").replace(",", ".").strip()
    if not text:
        return 0.0
    return abs(float(text))


def _has_suspicious_equal_usd_rates(deal: Deal) -> bool:
    currency = str(deal.deal_currency or "").strip().upper()
    if not currency or currency in USD_LIKE_CURRENCIES:
        return False
    if deal.client_fix_rate is None or deal.usd_rate is None:
        return False
    fix_rate = float(deal.client_fix_rate)
    usd_rate = float(deal.usd_rate)
    return abs(fix_rate - usd_rate) <= max(0.0001, abs(usd_rate) * 0.000001)


async def _open_rate_correction_dialog(context, deal: Deal, on_deal_saved) -> None:
    rate_date = _parse_optional_date(deal.client_fix_date or deal.request_date or deal.trade_date)
    currency = str(deal.deal_currency or "").strip().upper()
    if not rate_date or not currency:
        _show_rate_correction_error(context, "Не заполнены дата фиксации или валюта сделки.")
        return

    body = ft.Container(
        width=520,
        padding=ft.Padding(4, 4, 4, 4),
        content=ft.Row(
            controls=[
                ft.ProgressRing(width=24, height=24, stroke_width=3, color=ui_theme.PRIMARY),
                ft.Text("Загружаем курсы ЦБ...", color=ui_theme.TEXT, weight=ft.FontWeight.W_600),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=12,
                    bgcolor="#EFF6FF",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CURRENCY_EXCHANGE, size=20, color=ui_theme.PRIMARY),
                ),
                ft.Column(
                    controls=[
                        ft.Text("Проверка курсов", size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                        ft.Text(f"{deal.external_deal_id or deal.id or '-'} · {rate_date}", size=12, color=ui_theme.MUTED),
                    ],
                    spacing=0,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=body,
        actions=[ft.TextButton("Закрыть", on_click=lambda _: context.page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    context.page.show_dialog(dialog)

    try:
        await asyncio.to_thread(context.rates_service.sync_cbr_rates, rate_date)
        usd_rate = await asyncio.to_thread(context.rates_service.get_rate_to_rub, rate_date, "USD", True)
        currency_rate = await asyncio.to_thread(context.rates_service.get_rate_to_rub, rate_date, currency, True)
        cross_rate = _client_cross_rate_from_cbr(currency, currency_rate, usd_rate)
    except Exception as exc:
        body.content = ft.Container(
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=12,
            bgcolor="#FEF2F2",
            border=ui_theme.border("#FCA5A5"),
            content=ft.Text(f"Не удалось загрузить курсы: {exc}", color="#B91C1C", selectable=True),
        )
        context.page.update(dialog)
        return

    body.content = ft.Column(
        controls=[
            _rate_preview_row("Курс валюты сделки", currency, currency_rate),
            _rate_preview_row("Курс к USD", "USD", usd_rate),
            ft.Container(
                padding=ft.Padding(14, 12, 14, 12),
                border_radius=14,
                bgcolor="#F8FAFC",
                border=ui_theme.border("#D8E2F0"),
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, size=20, color=ui_theme.PRIMARY),
                        ft.Text("Кросс-курс с клиентом", weight=ft.FontWeight.W_800, color=ui_theme.TEXT, expand=True),
                        ft.Text(_format_number(cross_rate, 6), weight=ft.FontWeight.W_900, color=ui_theme.PRIMARY),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            ft.Text(
                "При применении эти значения будут записаны в сделку и курсы ЦБ будут сохранены в справочник курсов.",
                size=12,
                color=ui_theme.MUTED,
            ),
        ],
        spacing=10,
        tight=True,
    )

    def apply_rates(_: ft.ControlEvent) -> None:
        updated = replace(
            deal,
            client_fix_rate=currency_rate,
            usd_rate=usd_rate,
            client_cross_rate=cross_rate,
        )
        context.deals_repository.update(updated)
        context.page.pop_dialog()
        on_deal_saved(updated)

    dialog.actions = [
        ft.TextButton("Отклонить", on_click=lambda _: context.page.pop_dialog()),
        ui_theme.primary_button("Применить", icon=ft.Icons.CHECK, on_click=apply_rates),
    ]
    context.page.update(dialog)


def _rate_preview_row(label: str, currency: str, value: float) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(14, 12, 14, 12),
        border_radius=14,
        bgcolor="#FFFFFF",
        border=ui_theme.border("#D8E2F0"),
        content=ft.Row(
            controls=[
                ft.Text(label, weight=ft.FontWeight.W_700, color=ui_theme.TEXT, expand=True),
                ft.Text(currency, weight=ft.FontWeight.W_900, color="#475569"),
                ft.Text(_format_number(value, 6), weight=ft.FontWeight.W_900, color=ui_theme.TEXT),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _client_cross_rate_from_cbr(currency: str, currency_rate: float, usd_rate: float) -> float:
    normalized = str(currency or "").strip().upper()
    if normalized in STRONGER_THAN_USD_CURRENCIES:
        return abs(float(currency_rate) / float(usd_rate))
    return abs(float(usd_rate) / float(currency_rate))


def _is_client_refund(deal: Deal) -> bool:
    return bool(str(deal.client_refund_date or "").strip())


def _show_rate_correction_error(context, message: str) -> None:
    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Нельзя подтянуть курсы"),
            content=ft.Text(message),
            actions=[ft.TextButton("ОК", on_click=lambda _: context.page.pop_dialog())],
        )
    )


def _referral_commission_cell(
    context,
    state: dict[str, Any],
    deal: Deal,
    width: int,
    on_deal_saved,
    wait_duration: int = 250,
) -> ft.Control:
    result = _manual_or_calculated_referral(context, state, deal)
    exception = None if deal.is_repeat_payment else _client_exception_for_deal(context, state, deal)
    is_negative = result.amount_usd is not None and result.amount_usd < 0
    is_manual = deal.pnl_referral_commission_usd is not None and not deal.is_repeat_payment
    bgcolor = "#FEE2E2" if is_negative else "#ECFDF5" if result.ok else "#FFF7ED"
    border_color = "#FCA5A5" if is_negative else "#A7F3D0" if result.ok else "#FDBA74"
    text_color = "#B91C1C" if is_negative else "#047857" if result.ok else "#C2410C"
    value_content = _manual_value_content(result.label, text_color, is_manual)
    if exception is not None:
        value_content = ft.Row(
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                value_content,
                _client_exception_icon(context, deal, exception, on_deal_saved),
            ],
        )
    return ft.Container(
        width=width,
        alignment=ft.Alignment.CENTER_RIGHT,
        tooltip=_premium_tooltip(result.tooltip, wait_duration=wait_duration),
        content=ft.Container(
            padding=ft.Padding(8, 2, 8, 3),
            border_radius=999,
            bgcolor=bgcolor,
            border=ui_theme.border(border_color),
            content=value_content,
        ),
    )


def _client_exception_for_deal(context, state: dict[str, Any], deal: Deal):
    client_name = str(deal.client_name or "").strip()
    deal_date = str(deal.client_fix_date or "").strip()
    if not client_name or not deal_date or not hasattr(context, "client_rate_exceptions_repository"):
        return None
    cache = state.setdefault("client_exception_cache", {})
    cache_key = (client_name.casefold(), deal_date)
    if cache_key not in cache:
        cache[cache_key] = context.client_rate_exceptions_repository.find_active(client_name, deal_date)
    return cache[cache_key]


def _client_exception_icon(context, deal: Deal, exception, on_deal_saved) -> ft.Control:
    configured = deal.pnl_referral_commission_usd is not None
    color = "#047857" if configured else "#D97706"
    bgcolor = "#D1FAE5" if configured else "#FEF3C7"
    icon = ft.Icons.CHECK_CIRCLE_OUTLINE if configured else ft.Icons.EDIT_NOTE_OUTLINED
    tooltip = "\n".join(
        (
            "Клиент-исключение",
            f"Клиент: {exception.client_name}",
            f"Период: {_format_date(exception.date_from)} - {_exception_date_to_text(exception.date_to)}",
            f"Комментарий: {exception.note}",
            "Нажмите, чтобы ввести ручную ставку реферала.",
        )
    )
    return ft.Container(
        width=20,
        height=20,
        border_radius=999,
        bgcolor=bgcolor,
        border=ui_theme.border("#A7F3D0" if configured else "#FCD34D"),
        alignment=ft.Alignment.CENTER,
        tooltip=_premium_tooltip(tooltip, wait_duration=450),
        ink=True,
        on_click=lambda _: _open_client_exception_referral_dialog(context, deal, exception, on_deal_saved),
        content=ft.Icon(icon, size=13, color=color),
    )


def _open_client_exception_referral_dialog(context, deal: Deal, exception, on_deal_saved) -> None:
    value_field = ft.TextField(
        label="Ручная ставка реферала",
        value=_format_number(deal.pnl_referral_commission_usd, 2) if deal.pnl_referral_commission_usd is not None else "",
        suffix=ft.Text("USD", size=12, weight=ft.FontWeight.W_700, color=ui_theme.MUTED),
        dense=True,
        filled=True,
        fill_color="#F8FAFC",
        border_color="#D8E2F0",
        focused_border_color=ui_theme.PRIMARY,
        border_radius=12,
    )

    def save(_: ft.ControlEvent | None = None) -> None:
        try:
            updated = replace(deal, pnl_referral_commission_usd=_parse_signed_usd_input(value_field.value))
            context.deals_repository.update(updated)
            context.page.pop_dialog()
            on_deal_saved(updated)
        except Exception as exc:
            context.page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Не удалось сохранить ставку реферала"),
                    content=ft.Text(str(exc)),
                    actions=[ft.TextButton("ОК", on_click=lambda _: context.page.pop_dialog())],
                )
            )

    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=ui_theme.SURFACE,
            barrier_color="#0F172A66",
            title=ft.Row(
                controls=[
                    ft.Container(
                        width=40,
                        height=40,
                        border_radius=12,
                        bgcolor="#FEF3C7",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.PERSON_SEARCH_OUTLINED, color="#D97706", size=22),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Клиент-исключение", size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                            ft.Text(f"Сделка {deal.external_deal_id or deal.id or '-'}", size=12, color=ui_theme.MUTED),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=440,
                content=ft.Column(
                    controls=[
                        ft.Container(
                            padding=ft.Padding(14, 12, 14, 12),
                            border_radius=14,
                            bgcolor="#F8FAFC",
                            border=ui_theme.border("#D8E2F0"),
                            content=ft.Column(
                                controls=[
                                    ft.Text(exception.client_name, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                                    ft.Text(
                                        f"{_format_date(exception.date_from)} - {_exception_date_to_text(exception.date_to)}",
                                        size=12,
                                        color=ui_theme.MUTED,
                                    ),
                                    ft.Text(exception.note, size=12, color=ui_theme.TEXT),
                                ],
                                spacing=3,
                                tight=True,
                            ),
                        ),
                        value_field,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
                ui_theme.primary_button("Сохранить", icon=ft.Icons.CHECK, on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _parse_signed_usd_input(value: str | None) -> float:
    text = str(value or "").replace("USD", "").replace(" ", "").replace(",", ".").strip()
    if not text:
        return 0.0
    return float(text)


def _exception_date_to_text(value: str | None) -> str:
    return "бессрочно" if not value else _format_date(value)


def _repeat_payment_penalty_cell(deal: Deal, width: int) -> ft.Control:
    value = _repeat_payment_penalty_usd(deal)
    configured = _repeat_payment_configured(deal)
    tooltip = "\n".join(
        (
            "Штраф за переотправку",
            f"Повторный платеж: {'да' if deal.is_repeat_payment else 'нет'}",
            f"Статус настройки: {'заполнено' if configured else 'не заполнено'}",
            f"Штраф увеличивает итоговый PnL на: {_format_number(value, 2)} USD",
        )
    )
    return _usd_tooltip_cell(_format_optional_usd_value(value), width, tooltip, manual=configured)


def _pnl_cell(context, state: dict[str, Any], deal: Deal, width: int) -> ft.Control:
    breakdown = _pnl_breakdown(context, state, deal)
    value = breakdown.pnl
    tooltip = _cached_tooltip(
        state,
        ("tooltip", "__pnl_usd", _deal_pnl_cache_key(deal)),
        lambda: _pnl_tooltip(breakdown),
    )
    if value is None:
        return ft.Container(
            width=width,
            alignment=ft.Alignment.CENTER_RIGHT,
            tooltip=_premium_tooltip(tooltip, wait_duration=850),
            content=_cell("Нет данных", width, True),
        )
    is_negative = value < 0
    is_manual = _has_manual_pnl_override(deal)
    return ft.Container(
        width=width,
        alignment=ft.Alignment.CENTER_RIGHT,
        tooltip=_premium_tooltip(tooltip, wait_duration=850),
        content=ft.Container(
            padding=ft.Padding(8, 2, 8, 3),
            border_radius=999,
            bgcolor="#FEE2E2" if is_negative else "#DCFCE7",
            border=ui_theme.border("#FCA5A5" if is_negative else "#86EFAC"),
            content=_manual_value_content(
                _format_number(value, 2),
                "#B91C1C" if is_negative else "#166534",
                is_manual,
            ),
        ),
    )


def _pnl_tooltip(breakdown: _PnlBreakdown) -> str:
    gross = breakdown.gross
    costs = breakdown.costs
    pnl = breakdown.pnl
    lines = [
        "PnL = Доходы - Расходы",
        "",
        "Доходы:",
        f"Ставка клиента %: {_fmt_usd_component(breakdown.client_percent_fee)}",
        f"Фикс. комиссия: {_fmt_usd_component(breakdown.fixed_commission)}",
        f"SWIFT: {_fmt_usd_component(breakdown.swift)}",
        f"Штраф за переотправку: {_fmt_usd_component(breakdown.repeat_payment_penalty)}",
        f"Доходы всего: {_fmt_usd_component(gross)}",
        "",
        "Расходы:",
        f"Комиссия ПА: {_fmt_usd_component(breakdown.agent_commission)}",
        f"Комиссия за SWIFT ПА: {_fmt_usd_component(breakdown.swift_commission)}",
        f"Ставка реферала: {_fmt_usd_component(breakdown.referral.amount_usd)}",
        f"Расходы всего: {_fmt_usd_component(costs)}",
        "",
        f"Итого PnL: {_fmt_usd_component(pnl)}",
    ]
    if pnl is None:
        lines.append("")
        lines.append("Не хватает данных для полного расчета.")
    return "\n".join(lines)


def _fmt_usd_component(value: float | None) -> str:
    return "Нет данных" if value is None else f"{_format_number(value, 2)} USD"


def _has_manual_pnl_override(deal: Deal) -> bool:
    attrs = [
        "pnl_client_percent_fee_usd",
        "pnl_fixed_commission_usd",
        "pnl_swift_usd",
        "pnl_agent_commission_usd",
        "pnl_swift_commission_usd",
    ]
    if not deal.is_repeat_payment:
        attrs.append("pnl_referral_commission_usd")
    if _is_client_refund(deal):
        attrs = [
            attr
            for attr in attrs
            if attr
            not in {
                "pnl_client_percent_fee_usd",
                "pnl_fixed_commission_usd",
                "pnl_swift_usd",
                "pnl_referral_commission_usd",
            }
        ]
    return any(getattr(deal, attr, None) is not None for attr in attrs)


def _deal_amount_with_usd_tooltip(deal: Deal, width: int) -> ft.Control:
    amount = deal.deal_amount
    currency = (deal.deal_currency or "").upper()
    amount_usd = _usd_amount_value(amount, currency, deal)
    cross_rate = _usd_cross_rate(deal)
    if amount is None:
        tooltip = "Сумма сделки не заполнена."
    elif amount_usd is None:
        tooltip = f"Нет курса для пересчета {currency or 'валюты сделки'} в USD."
    else:
        operation = "не требуется"
        if currency not in USD_LIKE_CURRENCIES and cross_rate:
            operation = "умножение" if _should_multiply_to_usd(currency, cross_rate) else "деление"
        tooltip = "\n".join(
            (
                f"Сумма сделки: {_format_number(amount, 2)} {currency or '-'}",
                f"Эквивалент: {_format_number(amount_usd, 2)} USD",
                f"Кросс-курс: {_format_number(cross_rate, 4) if cross_rate else 'не нужен'}",
                f"Конвертация: {operation}",
            )
        )
    return ft.Container(
        width=width,
        alignment=ft.Alignment.CENTER_RIGHT,
        tooltip=_premium_tooltip(tooltip, wait_duration=850),
        content=_cell(_format_number(amount, 2) if amount is not None else "-", width, True),
    )


def _client_percent_fee_cell(state: dict[str, Any], deal: Deal, width: int) -> ft.Control:
    value = _cached_client_percent_fee_usd(state, deal)
    if _is_client_refund(deal):
        tooltip = "\n".join(
            (
                "Ставка клиента % в USD",
                f"Дата возврата средств клиенту: {_format_date(deal.client_refund_date)}",
                "По возврату клиентская процентная комиссия считается равной 0 USD.",
            )
        )
        return _usd_tooltip_cell(_format_optional_usd_value(value), width, tooltip)
    if deal.pnl_client_percent_fee_usd is not None:
        tooltip = "\n".join(
            (
                "Ставка клиента % введена вручную в USD как финальное значение этой компоненты.",
                f"Ручное значение: {_format_number(abs(float(deal.pnl_client_percent_fee_usd)), 2)} USD",
                "Итоговый PnL пересчитывается от этого значения.",
            )
        )
        return _usd_tooltip_cell(_format_optional_usd_value(value), width, tooltip, manual=True)
    amount_usd = _usd_amount_value(deal.deal_amount, deal.deal_currency, deal)
    rate_percent = _display_percent(_client_rate_fraction(deal.client_rate_percent))
    repeat_percent = _display_percent(_client_rate_fraction(deal.repeat_payment_commission_percent))
    effective_percent = _display_percent(_effective_client_rate_percent(deal))
    base_fee = _base_client_percent_fee_usd(deal)
    repeat_fee = _repeat_payment_commission_usd(deal)
    if amount_usd is None:
        tooltip = "Нет курса для расчета клиентской процентной комиссии в USD."
    else:
        tooltip = "\n".join(
            (
                "Ставка клиента % в USD",
                f"Сумма сделки: {_format_number(deal.deal_amount, 2) if deal.deal_amount is not None else '-'} {(deal.deal_currency or '').upper() or '-'}",
                f"Эквивалент сделки: {_format_number(amount_usd, 2)} USD",
                f"Базовая ставка клиента: {rate_percent}",
                f"Комиссия за переотправку: {repeat_percent}",
                f"Общая ставка: {effective_percent}",
                f"Формула: {_format_number(amount_usd, 2)} USD × ({rate_percent} + {repeat_percent}) = {_format_number(amount_usd, 2)} USD × {effective_percent}",
                f"Базовая комиссия: {_fmt_usd_component(base_fee)}",
                f"Комиссия за переотправку: {_fmt_usd_component(repeat_fee)} ({repeat_percent})",
                f"Итого: {_fmt_usd_component(value)}",
            )
        )
    return _usd_tooltip_cell(_format_optional_usd_value(value), width, tooltip)


def _usd_component_cell(
    context,
    state: dict[str, Any],
    deal: Deal,
    field_name: str | None,
    width: int,
    on_deal_saved,
) -> ft.Control:
    title, amount_attr, currency_attr = USD_COMPONENT_FIELDS[str(field_name)]
    if _is_client_refund(deal) and field_name in {"__fixed_commission_usd", "__swift_usd"}:
        tooltip = "\n".join(
            (
                title,
                f"Дата возврата средств клиенту: {_format_date(deal.client_refund_date)}",
                "По возврату эта клиентская комиссия считается равной 0 USD.",
            )
        )
        return _usd_tooltip_cell(_format_optional_usd_value(0.0), width, tooltip)
    manual_attr = {
        "__fixed_commission_usd": "pnl_fixed_commission_usd",
        "__swift_usd": "pnl_swift_usd",
        "__agent_commission_usd": "pnl_agent_commission_usd",
        "__swift_commission_usd": "pnl_swift_commission_usd",
    }.get(str(field_name))
    manual_value = getattr(deal, manual_attr, None) if manual_attr else None
    if manual_value is not None:
        value = _cached_usd_component_value(context, state, deal, str(field_name))
        tooltip = "\n".join(
            (
                f"{title} введено вручную в USD.",
                f"Ручное значение: {_format_number(value, 2)} USD",
                "Итоговый PnL пересчитывается от этого значения.",
            )
        )
        return _usd_tooltip_cell(_format_optional_usd_value(value), width, tooltip, manual=True)
    amount = getattr(deal, amount_attr, None)
    currency = (getattr(deal, currency_attr, None) or deal.deal_currency or "").upper()
    value = _cached_usd_component_value(context, state, deal, str(field_name))
    if value is None:
        return _missing_usd_rate_cell(context, deal, field_name, title, amount, currency, width, on_deal_saved)
    tooltip = _cached_tooltip(
        state,
        ("tooltip", str(field_name), _deal_pnl_cache_key(deal)),
        lambda: _usd_component_tooltip(context, title, amount, currency, value, deal),
    )
    return _usd_tooltip_cell(_format_optional_usd_value(value), width, tooltip)


def _usd_component_tooltip(context, title: str, amount: float | None, currency: str, value_usd: float | None, deal: Deal) -> str:
    cross_rate = _usd_cross_rate(deal)
    if amount is None or float(amount) == 0:
        return "\n".join((title, "Исходная сумма: 0", "Итого: 0,00 USD"))
    if value_usd is None:
        return f"{title}\nНет курса для пересчета {currency or 'валюты сделки'} в USD."
    operation = "не требуется"
    if currency not in USD_LIKE_CURRENCIES and cross_rate:
        operation = "умножение" if _should_multiply_to_usd(currency, cross_rate) else "деление"
    return "\n".join(
        (
            title,
            f"Исходная сумма: {_format_number(amount, 2)} {currency or '-'}",
            f"Кросс-курс: {_format_number(cross_rate, 4) if cross_rate else 'не нужен'}",
            f"Конвертация: {operation}",
            f"Итого: {_format_number(value_usd, 2)} USD",
        )
    )


def _usd_component_tooltip(context, title: str, amount: float | None, currency: str, value_usd: float | None, deal: Deal) -> str:
    cross_rate = _usd_cross_rate(deal)
    normalized_currency = normalize_rate_currency(currency or "")
    deal_currency = normalize_rate_currency(deal.deal_currency or "")
    if amount is None or float(amount) == 0:
        return "\n".join((title, "Исходная сумма: 0", "Итого: 0,00 USD"))
    if value_usd is None:
        return f"{title}\nНет курса для пересчета {currency or 'валюты'} в USD."
    operation = "не требуется"
    rate_details = ""
    if normalized_currency not in USD_LIKE_CURRENCIES and normalized_currency != deal_currency:
        rate_date = _component_rate_date(deal)
        currency_rate = _preferred_rate_per_unit(context, rate_date, normalized_currency) if rate_date else None
        usd_rate = _preferred_rate_per_unit(context, rate_date, "USD") if rate_date else None
        if currency_rate and usd_rate:
            operation = "курсы справочника"
            rate_details = (
                f"\nКурс {normalized_currency}: {_format_number(currency_rate, 8)} RUB"
                f"\nКурс USD: {_format_number(usd_rate, 4)} RUB"
            )
    elif normalized_currency not in USD_LIKE_CURRENCIES and cross_rate:
        operation = "умножение" if _should_multiply_to_usd(normalized_currency, cross_rate) else "деление"
    return "\n".join(
        (
            title,
            f"Исходная сумма: {_format_number(amount, 2)} {currency or '-'}",
            f"Кросс-курс сделки: {_format_number(cross_rate, 4) if cross_rate else 'не нужен'}",
            f"Конвертация: {operation}{rate_details}",
            f"Итого: {_format_number(value_usd, 2)} USD",
        )
    )


def _missing_usd_rate_cell(
    context,
    deal: Deal,
    field_name: str | None,
    title: str,
    amount: float | None,
    currency: str,
    width: int,
    on_deal_saved,
) -> ft.Control:
    rate_date = _component_rate_date(deal)
    normalized_currency = normalize_rate_currency(currency or "")
    tooltip = "\n".join(
        (
            title,
            f"Исходная сумма: {_format_number(amount, 2) if amount is not None else '-'} {normalized_currency or '-'}",
            f"Дата курса: {rate_date or '-'}",
            "Нет курса валюты или USD в справочнике.",
            "Нажмите на значок, чтобы загрузить курсы ЦБ за эту дату.",
        )
    )
    return ft.Container(
        width=width,
        alignment=ft.Alignment.CENTER_RIGHT,
        tooltip=_premium_tooltip(tooltip, wait_duration=650),
        content=ft.Row(
            width=width,
            spacing=4,
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    "Нет курса",
                    size=CELL_FONT_SIZE,
                    weight=ft.FontWeight.W_800,
                    color="#B45309",
                    overflow=ft.TextOverflow.ELLIPSIS,
                    selectable=False,
                ),
                ft.IconButton(
                    icon=ft.Icons.CURRENCY_EXCHANGE,
                    icon_size=15,
                    tooltip="Загрузить курсы ЦБ",
                    icon_color="#D97706",
                    width=24,
                    height=24,
                    style=ft.ButtonStyle(padding=ft.Padding(0, 0, 0, 0)),
                    on_click=lambda _: context.page.run_task(
                        _open_component_rate_load_dialog,
                        context,
                        deal,
                        field_name,
                        normalized_currency,
                        rate_date,
                        on_deal_saved,
                    ),
                ),
            ],
        ),
    )


async def _open_component_rate_load_dialog(
    context,
    deal: Deal,
    field_name: str | None,
    currency: str,
    rate_date: str | None,
    on_deal_saved,
) -> None:
    if not rate_date or not currency:
        _show_rate_correction_error(context, "Не заполнены дата или валюта для загрузки курса.")
        return
    title = USD_COMPONENT_FIELDS.get(str(field_name), ("Комиссия", "", ""))[0]
    body = ft.Container(
        width=520,
        padding=ft.Padding(4, 4, 4, 4),
        content=ft.Row(
            controls=[
                ft.ProgressRing(width=24, height=24, stroke_width=3, color=ui_theme.PRIMARY),
                ft.Text("Загружаем курсы ЦБ...", color=ui_theme.TEXT, weight=ft.FontWeight.W_600),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ui_theme.SURFACE,
        barrier_color="#0F172A66",
        title=ft.Row(
            controls=[
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=12,
                    bgcolor="#FFF7ED",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CURRENCY_EXCHANGE, size=20, color="#D97706"),
                ),
                ft.Column(
                    controls=[
                        ft.Text("Нет курса для USD-расчета", size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                        ft.Text(f"{deal.external_deal_id or deal.id or '-'} · {title} · {currency} · {rate_date}", size=12, color=ui_theme.MUTED),
                    ],
                    spacing=0,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=body,
        actions=[ft.TextButton("Закрыть", on_click=lambda _: context.page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    context.page.show_dialog(dialog)
    try:
        await asyncio.to_thread(context.rates_service.sync_cbr_rates, rate_date)
        currency_rate = _preferred_rate_per_unit(context, rate_date, currency)
        usd_rate = _preferred_rate_per_unit(context, rate_date, "USD")
        if currency_rate is None or usd_rate is None:
            raise ValueError(_missing_cbr_rate_message(context, currency, rate_date, usd_rate is None))
    except Exception as exc:
        body.content = ft.Container(
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=12,
            bgcolor="#FEF2F2",
            border=ui_theme.border("#FCA5A5"),
            content=ft.Text(_rate_load_error_text(exc), color="#B91C1C", selectable=True),
        )
        context.page.update(dialog)
        return

    body.content = ft.Column(
        controls=[
            _rate_preview_row(f"Курс {currency}", currency, currency_rate),
            _rate_preview_row("Курс USD", "USD", usd_rate),
            ft.Text(
                "Курсы сохранены в справочник. После применения ячейка пересчитается автоматически.",
                size=12,
                color=ui_theme.MUTED,
            ),
        ],
        spacing=10,
        tight=True,
    )

    def apply_loaded_rates(_: ft.ControlEvent) -> None:
        context.page.pop_dialog()
        on_deal_saved(deal)

    dialog.actions = [
        ft.TextButton("Закрыть", on_click=lambda _: context.page.pop_dialog()),
        ui_theme.primary_button("Применить", icon=ft.Icons.CHECK, on_click=apply_loaded_rates),
    ]
    context.page.update(dialog)


def _rate_load_error_text(exc: Exception) -> str:
    return "Не удалось загрузить курсы: " + str(exc)


def _missing_cbr_rate_message(context, currency: str, rate_date: str, usd_missing: bool) -> str:
    normalized_currency = str(currency or "").strip().upper()
    if usd_missing:
        return f"ЦБ не вернул курс USD за {rate_date}."

    suggestions = _similar_currency_codes(context, rate_date, normalized_currency)
    if suggestions:
        return (
            f"Для валюты {normalized_currency} нет курса в ЦБ за {rate_date}. "
            f"Возможно, вы имели в виду: {', '.join(suggestions)}. "
            "Исправьте код валюты в сделке и повторите загрузку."
        )
    return f"Для валюты {normalized_currency} нет курса в ЦБ за {rate_date}."


def _similar_currency_codes(context, rate_date: str, currency: str) -> list[str]:
    try:
        codes = sorted({rate.currency for rate in context.rates_repository.list_by_date(rate_date)})
    except Exception:
        codes = []
    candidates = [code for code in codes if code and code != currency]
    close = get_close_matches(currency, candidates, n=3, cutoff=0.55)
    if close:
        return close
    if len(currency) == 3:
        return [code for code in candidates if sum(1 for a, b in zip(currency, code) if a != b) == 1][:3]
    return []


def _usd_tooltip_cell(label: str, width: int, tooltip: str, manual: bool = False) -> ft.Control:
    return ft.Container(
        width=width,
        alignment=ft.Alignment.CENTER_RIGHT,
        tooltip=_premium_tooltip(tooltip, wait_duration=850),
        content=_manual_plain_cell(label, width) if manual else _cell(label, width, True),
    )


def _manual_plain_cell(label: str, width: int) -> ft.Control:
    return ft.Row(
        width=width,
        spacing=4,
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.EDIT_NOTE_OUTLINED, size=13, color="#B45309"),
            ft.Text(
                label,
                size=CELL_FONT_SIZE,
                weight=ft.FontWeight.W_700,
                color="#92400E",
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.RIGHT,
                selectable=False,
            ),
        ],
    )


def _manual_value_content(label: str, color: str, manual: bool) -> ft.Control:
    if not manual:
        return ft.Text(
            label,
            size=CELL_FONT_SIZE,
            weight=ft.FontWeight.W_700,
            color=color,
            overflow=ft.TextOverflow.ELLIPSIS,
            text_align=ft.TextAlign.RIGHT,
            selectable=False,
        )
    return ft.Row(
        spacing=3,
        tight=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.EDIT_NOTE_OUTLINED, size=13, color="#B45309"),
            ft.Text(
                label,
                size=CELL_FONT_SIZE,
                weight=ft.FontWeight.W_800,
                color=color,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.RIGHT,
                selectable=False,
            ),
        ],
    )


def _display_percent(value: float | int | None) -> str:
    if value is None:
        return "0,00%"
    numeric = float(value)
    display_value = numeric * 100 if abs(numeric) <= 1 else numeric
    return f"{_format_number(display_value, 2)}%"


def _premium_tooltip(message: str, wait_duration: int = 250) -> ft.Tooltip:
    return ft.Tooltip(
        message=message,
        decoration=ft.BoxDecoration(
            bgcolor="#0F172A",
            border_radius=12,
            border=ui_theme.border("#334155"),
            shadows=[ft.BoxShadow(blur_radius=24, color="#02061735", offset=ft.Offset(0, 10))],
        ),
        padding=ft.Padding(12, 10, 12, 10),
        margin=8,
        vertical_offset=16,
        text_style=ft.TextStyle(size=12, color="#F8FAFC", weight=ft.FontWeight.W_500),
        show_duration=9000,
        wait_duration=wait_duration,
    )



def _cell(value: Any, width: int, numeric: bool) -> ft.Text:
    return ft.Text(
        _blank(value),
        width=width,
        size=CELL_FONT_SIZE,
        overflow=ft.TextOverflow.ELLIPSIS,
        text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT,
        selectable=False,
    )



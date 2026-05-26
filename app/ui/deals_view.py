"""Deals registry screen."""

from __future__ import annotations

import asyncio
from datetime import date
import time
from typing import Any

import flet as ft

from app.domain.models import Deal
from app.domain.rate_models import Referral
from app.ui.asset_loader import image_source
from app.ui.deals.constants import COMPUTED_FILTER_COLUMNS, PAGE_SIZE, ROW_HEIGHT
from app.ui.deals.controls import (
    _filters_panel,
    _mode_gradient,
    _pagination_panel,
    _style_filter_dropdown,
    _style_filter_text_field,
    _style_page_input,
    _style_page_size_dropdown,
    _style_registry_dropdown,
    _sync_view_switcher,
    _view_switcher,
)
from app.ui.deals.edit_dialog import _open_edit_dialog
from app.ui.deals.table_view import _column_value, _deals_modes_stack, _replace_visible_columns
from app.ui import theme as ui_theme
from app.services.performance_logger import perf_span, log_perf_event



def create_deals_view(context) -> ft.Control:
    """Create a paginated deals registry with filters and edit actions."""
    context.set_shell_theme("default")
    state: dict[str, Any] = {
        "page": 1,
        "page_size": PAGE_SIZE,
        "sort_by": "trade_date",
        "sort_desc": True,
        "column_filters": {},
        "column_search_filters": {},
        "view_mode": "general",
        "referral_rate_cache": {},
        "usd_component_cache": {},
        "tooltip_cache": {},
        "filter_values_cache": {},
        "active_rate_rules": None,
        "total_rows": None,
        "total_pages": 1,
        "table_scroll_offset": 0.0,
        "table_list_view": None,
        "selected_deal_id": None,
        "selected_deal_key": None,
        "selected_deal_keys": set(),
        "selected_row_control": None,
        "selection_anchor_index": None,
        "selection_modifier_state": {"shift": False, "ctrl": False, "at": 0.0},
        "last_row_click_key": None,
        "last_row_click_at": 0.0,
        "last_scroll_recorded_at": 0.0,
        "mode_table_controls": {},
        "table_list_views": {},
        "mode_column_controls": {},
        "mode_column_keys": {},
        "mode_row_cells_cache": {},
        "row_controls_by_mode": {},
        "active_table_column": None,
        "active_header_container": None,
        "active_body_rows": [],
        "active_columns": (),
        "page_load_token": 0,
    }

    def handle_keyboard_down(event: ft.KeyboardEvent) -> None:
        key = str(getattr(event, "key", "") or "")
        state["selection_modifier_state"] = {
            "shift": bool(getattr(event, "shift", False)) or key.lower().startswith("shift"),
            "ctrl": bool(getattr(event, "ctrl", False)) or key.lower().startswith("control") or key.lower().startswith("ctrl"),
            "at": time.monotonic(),
        }

    def handle_keyboard_up(event: ft.KeyboardEvent) -> None:
        key = str(getattr(event, "key", "") or "").lower()
        current = dict(state.get("selection_modifier_state") or {})
        shift = bool(getattr(event, "shift", False))
        ctrl = bool(getattr(event, "ctrl", False))
        if key.startswith("shift"):
            shift = False
        if key.startswith("control") or key.startswith("ctrl"):
            ctrl = False
        current.update({"shift": shift, "ctrl": ctrl, "at": time.monotonic()})
        state["selection_modifier_state"] = current
    search = ft.TextField(
        hint_text="\u041f\u043e\u0438\u0441\u043a: \u2116, \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440, \u043a\u043b\u0438\u0435\u043d\u0442, \u0441\u0442\u0430\u0442\u0443\u0441",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        dense=True,
    )
    portfolio_filter = ft.Dropdown(
        label="\u0421\u0443\u0431\u0430\u0433\u0435\u043d\u0442\u044b",
        dense=True,
        width=165,
        options=[
            _subagent_dropdown_option(value)
            for value in context.deals_repository.distinct_values("portfolio")
            if value != "Imported"
        ],
    )
    referrals = context.referrals_service.list()
    referral_filter = ft.Dropdown(
        label="\u0420\u0435\u0444\u0435\u0440\u0430\u043b\u044b",
        dense=True,
        width=215,
        menu_height=320,
        menu_width=280,
        enable_filter=True,
        enable_search=True,
        options=[
            _referral_dropdown_option(referral)
            for referral in referrals
        ],
    )
    operation_type_filter = ft.Dropdown(
        label="\u0422\u0438\u043f \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438",
        dense=True,
        width=180,
        options=[
            _operation_type_option("Импорт", "#16A34A"),
            _operation_type_option("Экспорт", "#DC2626"),
            _operation_type_option("USDT (импорт)", "#0D9488"),
            _operation_type_option("USDT (экспорт)", "#7C3AED"),
        ],
    )
    mode_buttons: dict[str, ft.Container] = {}
    view_mode_switch = _view_switcher(mode_buttons, lambda mode: change_view_mode_to(mode), "general")
    sort_by = ft.Dropdown(visible=False, value="trade_date", options=[ft.dropdown.Option(key="trade_date", text="Trade date")])
    sort_desc = ft.IconButton(icon=ft.Icons.SOUTH, tooltip="\u041f\u043e \u0443\u0431\u044b\u0432\u0430\u043d\u0438\u044e")
    _style_filter_text_field(search)
    for control in (portfolio_filter, operation_type_filter, referral_filter):
        _style_registry_dropdown(control)
    sort_desc.icon_color = ui_theme.PRIMARY
    sort_desc.bgcolor = ui_theme.PRIMARY_SOFT
    table_holder = ft.Container(expand=True, opacity=1.0)
    table_holder.animate_opacity = ft.Animation(140, ft.AnimationCurve.EASE_OUT)
    table_holder.animate_offset = ft.Animation(170, ft.AnimationCurve.EASE_OUT)
    pnl_shimmer = ft.Container(
        expand=True,
        visible=False,
        opacity=0.0,
        offset=ft.Offset(-0.45, 0),
        border_radius=22,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=["#FFFFFF00", "#E2E8F033", "#FFFFFF00"],
        ),
        animate_opacity=ft.Animation(360, ft.AnimationCurve.EASE_OUT),
        animate_offset=ft.Animation(420, ft.AnimationCurve.EASE_OUT),
    )
    mode_backdrop = ft.Container(
        expand=True,
        padding=16,
        border_radius=22,
        gradient=_mode_gradient("general"),
        border=ui_theme.border("#E1E8F0"),
        shadow=ft.BoxShadow(blur_radius=26, color="#0F172A14", offset=ft.Offset(0, 10)),
        animate=ft.Animation(360, ft.AnimationCurve.EASE_OUT),
    )
    pager_label = ft.Text(weight=ft.FontWeight.W_600)
    rows_label = ft.Text(color=ui_theme.MUTED)
    page_input = ft.TextField(
        value="1",
        dense=True,
        width=86,
        text_align=ft.TextAlign.CENTER,
        hint_text="в„–",
    )
    page_size_dropdown = ft.Dropdown(
        label="\u0421\u0442\u0440\u043e\u043a",
        value=str(PAGE_SIZE),
        options=[
            ft.dropdown.Option(key="25", text="25"),
            ft.dropdown.Option(key="50", text="50"),
            ft.dropdown.Option(key="100", text="100"),
        ],
    )
    _style_page_input(page_input)
    _style_page_size_dropdown(page_size_dropdown)
    _apply_mode_backdrop_style(mode_backdrop, "general")

    def computed_filter_values_provider(field_name: str, search_value: str | None, limit: int | None = 500) -> list[str]:
        base_filters, base_searches = _split_db_and_computed_filters()
        deals = context.deals_repository.list(
            search=search.value,
            portfolio=portfolio_filter.value,
            referral=referral_filter.value,
            column_filters=base_filters,
            column_search_filters=base_searches,
            included_only=False,
            sort_by="trade_date",
            sort_desc=True,
            limit=100000,
            offset=0,
        )
        values: list[str] = []
        seen: set[str] = set()
        needle = str(search_value or "").strip().casefold()
        for deal in deals:
            if not _matches_operation_type_filter(deal):
                continue
            text = _computed_column_text(field_name, deal)
            if not text or (needle and needle not in text.casefold()):
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(text)
            if limit and len(values) >= limit:
                break
        return values

    state["computed_filter_values_provider"] = computed_filter_values_provider

    def _split_db_and_computed_filters() -> tuple[dict[str, list[str]], dict[str, str]]:
        db_filters = {
            key: value
            for key, value in dict(state["column_filters"]).items()
            if key not in COMPUTED_FILTER_COLUMNS
        }
        db_searches = {
            key: value
            for key, value in dict(state["column_search_filters"]).items()
            if key not in COMPUTED_FILTER_COLUMNS
        }
        return db_filters, db_searches

    def _computed_filters_active() -> bool:
        return bool(operation_type_filter.value) or bool(state.get("suspicious_rates_only")) or any(key in COMPUTED_FILTER_COLUMNS for key in state["column_filters"]) or any(
            key in COMPUTED_FILTER_COLUMNS for key in state["column_search_filters"]
        )

    def _computed_column_text(field_name: str, deal: Deal) -> str:
        return str(_column_value(context, state, field_name, lambda _: "", deal) or "").strip()

    def _matches_computed_filters(deal: Deal) -> bool:
        if not _matches_operation_type_filter(deal):
            return False
        if state.get("suspicious_rates_only") and not _has_suspicious_equal_usd_rates(deal):
            return False
        for field_name, values in state["column_filters"].items():
            if field_name not in COMPUTED_FILTER_COLUMNS:
                continue
            selected = {str(value).casefold() for value in values if str(value)}
            if selected and _computed_column_text(field_name, deal).casefold() not in selected:
                return False
        for field_name, value in state["column_search_filters"].items():
            if field_name not in COMPUTED_FILTER_COLUMNS:
                continue
            needle = str(value or "").strip().casefold()
            if needle and needle not in _computed_column_text(field_name, deal).casefold():
                return False
        return True

    def _computed_sort_key(field_name: str, deal: Deal) -> tuple[int, float | str]:
        text = _computed_column_text(field_name, deal)
        numeric = _parse_display_number(text)
        if numeric is not None:
            return (0, numeric)
        return (1, text.casefold())

    def _matches_operation_type_filter(deal: Deal) -> bool:
        selected = str(operation_type_filter.value or "").strip()
        return not selected or _operation_type_label(deal) == selected

    def _parse_display_number(value: str) -> float | None:
        text = str(value or "").replace("USD", "").replace(" ", "").replace(",", ".").strip()
        try:
            return float(text)
        except ValueError:
            return None

    async def restore_table_scroll(offset: float, reveal: bool = True) -> None:
        await asyncio.sleep(0.04)
        table_list_view = state.get("table_list_view")
        try:
            if table_list_view is not None and offset > 0:
                for _ in range(4):
                    await table_list_view.scroll_to(offset=offset, duration=0)
                    await asyncio.sleep(0.025)
                state["table_scroll_offset"] = max(0.0, float(offset))
        except Exception:
            pass
        finally:
            if reveal:
                table_holder.opacity = 1.0
                context.page.update(table_holder)

    async def animate_in_place_columns(prepared_columns: dict[int, list[ft.Control]]) -> None:
        return

    async def animate_pnl_shimmer() -> None:
        pnl_shimmer.visible = True
        pnl_shimmer.opacity = 0.0
        pnl_shimmer.offset = ft.Offset(-0.55, 0)
        context.page.update(pnl_shimmer)
        await asyncio.sleep(0.02)
        pnl_shimmer.opacity = 0.34
        pnl_shimmer.offset = ft.Offset(0.18, 0)
        context.page.update(pnl_shimmer)
        await asyncio.sleep(0.34)
        pnl_shimmer.opacity = 0.0
        pnl_shimmer.offset = ft.Offset(0.72, 0)
        context.page.update(pnl_shimmer)
        await asyncio.sleep(0.38)
        pnl_shimmer.visible = False
        pnl_shimmer.offset = ft.Offset(-0.45, 0)
        context.page.update(pnl_shimmer)

    def rebuild_mode_content() -> None:
        mode_backdrop.content = ft.Stack(
            controls=[
                ft.Column(
                    controls=[
                        _filters_panel(
                            state=state,
                            search=search,
                            portfolio_filter=portfolio_filter,
                            operation_type_filter=operation_type_filter,
                            referral_filter=referral_filter,
                            sort_by=sort_by,
                            sort_desc=sort_desc,
                            apply_filters=apply_filters,
                            clear_filters=clear_filters,
                            add_deal=open_new_deal_dialog,
                            delete_deal=confirm_delete_selected_deal,
                        ),
                        table_holder,
                        _pagination_panel(
                            state=state,
                            pager_label=pager_label,
                            rows_label=rows_label,
                            page_input=page_input,
                            page_size_dropdown=page_size_dropdown,
                            go_to_page=go_to_page,
                            go_to_entered_page=go_to_entered_page,
                        ),
                    ],
                    expand=True,
                    spacing=14,
                ),
                pnl_shimmer,
            ],
            expand=True,
            fit=ft.StackFit.EXPAND,
        )

    def refresh(
        update: bool = True,
        recount: bool = True,
        preserve_scroll: bool = False,
        partial_update: bool = False,
    ) -> None:
        with perf_span(
            "deals.refresh.total",
            update=update,
            recount=recount,
            partial_update=partial_update,
            mode=state.get("view_mode"),
            page=state.get("page"),
            page_size=state.get("page_size"),
        ):
            scroll_offset = float(state.get("table_scroll_offset") or 0.0) if preserve_scroll else 0.0
            if recount:
                state["page_load_token"] = int(state.get("page_load_token") or 0) + 1
            base_filters, base_searches = _split_db_and_computed_filters()
            has_computed_filters = _computed_filters_active()
            sort_is_computed = str(state["sort_by"]) in COMPUTED_FILTER_COLUMNS
            needs_computed_processing = has_computed_filters or sort_is_computed
            if recount or state.get("total_rows") is None:
                if needs_computed_processing:
                    with perf_span("deals.refresh.db_list_for_computed", sort_by=state["sort_by"]):
                        base_deals = context.deals_repository.list(
                            search=search.value,
                            portfolio=portfolio_filter.value,
                            referral=referral_filter.value,
                            column_filters=base_filters,
                            column_search_filters=base_searches,
                            included_only=False,
                            sort_by="trade_date" if sort_is_computed else str(state["sort_by"]),
                            sort_desc=bool(state["sort_desc"]),
                            limit=100000,
                            offset=0,
                        )
                    with perf_span("deals.refresh.computed_filter", rows=len(base_deals)):
                        filtered_deals = [deal for deal in base_deals if _matches_computed_filters(deal)]
                    state["computed_filtered_deals"] = filtered_deals
                    state["total_rows"] = len(filtered_deals)
                else:
                    state["computed_filtered_deals"] = None
                    with perf_span("deals.refresh.db_count"):
                        state["total_rows"] = context.deals_repository.count(
                            search=search.value,
                            portfolio=portfolio_filter.value,
                            referral=referral_filter.value,
                            column_filters=base_filters,
                            column_search_filters=base_searches,
                            included_only=False,
                        )
            total_rows = int(state.get("total_rows") or 0)
            page_size = _current_page_size()
            total_pages = max(1, (total_rows + page_size - 1) // page_size)
            state["total_pages"] = total_pages
            state["page"] = min(max(1, int(state["page"])), total_pages)
            offset = (int(state["page"]) - 1) * page_size
            if needs_computed_processing:
                with perf_span("deals.refresh.slice_computed", sort_is_computed=sort_is_computed):
                    all_deals = list(state.get("computed_filtered_deals") or [])
                    if sort_is_computed:
                        all_deals.sort(
                            key=lambda deal: _computed_sort_key(str(state["sort_by"]), deal),
                            reverse=bool(state["sort_desc"]),
                        )
                    deals = all_deals[offset : offset + page_size]
            else:
                with perf_span("deals.refresh.db_page_list", limit=page_size, offset=offset, sort_by=state["sort_by"]):
                    deals = context.deals_repository.list(
                        search=search.value,
                        portfolio=portfolio_filter.value,
                        referral=referral_filter.value,
                        column_filters=base_filters,
                        column_search_filters=base_searches,
                        included_only=False,
                        sort_by="trade_date" if sort_is_computed else str(state["sort_by"]),
                        sort_desc=bool(state["sort_desc"]),
                        limit=page_size,
                        offset=offset,
                    )
            state["current_deals"] = deals
            state["pnl_breakdown_cache"] = {}
            state["usd_component_cache"] = {}
            state["tooltip_cache"] = {}

            first_row = offset + 1 if total_rows else 0
            last_row = min(offset + len(deals), total_rows)
            rows_label.value = (
                f"\u0421\u0442\u0440\u043e\u043a\u0438 {first_row}-{last_row} "
                f"\u0438\u0437 {total_rows}"
            )
            pager_label.value = f"\u0421\u0442\u0440. {state['page']} / {total_pages}"
            page_input.value = str(state["page"])
            table_holder.opacity = 1.0
            with perf_span("deals.refresh.build_table", rows=len(deals), mode=state.get("view_mode")):
                table_holder.content = _deals_modes_stack(context, deals, state, sort_by, refresh, update_visible_deal)
            if not preserve_scroll:
                state["table_scroll_offset"] = 0.0
            state["table_list_view"] = (state.get("table_list_views") or {}).get(str(state.get("view_mode") or "general"))
            if update:
                with perf_span("deals.refresh.page_update", partial_update=partial_update):
                    if partial_update:
                        context.page.update(rows_label, pager_label, page_input, table_holder)
                    else:
                        context.page.update()
                if preserve_scroll and scroll_offset > 0:
                    context.page.run_task(restore_table_scroll, scroll_offset)
            log_perf_event(
                "deals.refresh.summary",
                details={
                    "rows": len(deals),
                    "total_rows": total_rows,
                    "page": state["page"],
                    "page_size": page_size,
                    "computed_processing": needs_computed_processing,
                },
            )

    def update_visible_deal(updated: Deal) -> None:
        current_deals = list(state.get("current_deals") or [])
        if updated.id is None or not current_deals:
            refresh(recount=False)
            return
        replaced = False
        next_deals: list[Deal] = []
        for current in current_deals:
            if current.id == updated.id:
                next_deals.append(updated)
                replaced = True
            else:
                next_deals.append(current)
        if not replaced:
            refresh(recount=False)
            return
        state["current_deals"] = next_deals
        state["referral_rate_cache"] = {}
        state["pnl_breakdown_cache"] = {}
        state["usd_component_cache"] = {}
        state["tooltip_cache"] = {}
        state["active_referral_rules_cache"] = {}
        state["mode_row_cells_cache"] = {}
        scroll_offset = float(state.get("table_scroll_offset") or 0.0)
        table_holder.opacity = 1.0
        table_holder.content = _deals_modes_stack(context, next_deals, state, sort_by, refresh, update_visible_deal)
        state["table_list_view"] = (state.get("table_list_views") or {}).get(str(state.get("view_mode") or "general"))
        context.page.update()
        if scroll_offset > 0:
            context.page.run_task(restore_table_scroll, scroll_offset)

    def open_new_deal_dialog(_: ft.ControlEvent | None = None) -> None:
        _open_edit_dialog(context, _new_manual_deal(), on_new_deal_saved)

    def on_new_deal_saved(created: Deal) -> None:
        state["selected_deal_id"] = created.id
        state["selected_deal_key"] = f"id:{created.id}" if created.id is not None else None
        state["selected_deal_keys"] = {state["selected_deal_key"]} if state["selected_deal_key"] else set()
        state["selected_row_control"] = None
        state["referral_rate_cache"] = {}
        state["pnl_breakdown_cache"] = {}
        state["usd_component_cache"] = {}
        state["tooltip_cache"] = {}
        state["active_referral_rules_cache"] = {}
        state["filter_values_cache"] = {}
        state["total_rows"] = None
        refresh(recount=True)

    def confirm_delete_selected_deal(_: ft.ControlEvent | None = None) -> None:
        selected_id = state.get("selected_deal_id")
        if selected_id is None:
            _show_deals_message(context, "Сначала выберите строку в реестре.")
            return
        deal = context.deals_repository.get(int(selected_id))
        if deal is None:
            _show_deals_message(context, "Выбранная строка уже не найдена в базе.")
            refresh(recount=True)
            return

        def delete_confirmed(_: ft.ControlEvent | None = None) -> None:
            context.deals_repository.delete(int(selected_id))
            context.page.pop_dialog()
            state["selected_deal_id"] = None
            state["selected_deal_key"] = None
            state["selected_deal_keys"] = set()
            state["selected_row_control"] = None
            state["referral_rate_cache"] = {}
            state["pnl_breakdown_cache"] = {}
            state["usd_component_cache"] = {}
            state["tooltip_cache"] = {}
            state["active_referral_rules_cache"] = {}
            state["filter_values_cache"] = {}
            state["total_rows"] = None
            refresh(recount=True)

        context.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=ui_theme.SURFACE,
                barrier_color="#0F172A66",
                title=ft.Text("Удалить строку?"),
                content=ft.Text(
                    f"Вы точно хотите удалить?\n\nСделка: {deal.external_deal_id or deal.id or '-'}",
                    selectable=True,
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
                    ft.FilledButton(
                        "Удалить",
                        icon=ft.Icons.DELETE_OUTLINE,
                        bgcolor="#DC2626",
                        color="#FFFFFF",
                        on_click=delete_confirmed,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def apply_filters(_: ft.ControlEvent | None = None) -> None:
        state["sort_by"] = sort_by.value or state["sort_by"] or "trade_date"
        state["page"] = 1
        refresh()

    def change_view_mode(event: ft.ControlEvent) -> None:
        selected = list(getattr(event.control, "selected", None) or ["general"])
        change_view_mode_to(selected[0] if selected else "general")

    def change_view_mode_to(next_mode: str) -> None:
        if state.get("mode_transition_running"):
            return
        context.page.run_task(change_view_mode_to_async, next_mode)

    async def change_view_mode_to_async(next_mode: str) -> None:
        previous_mode = str(state.get("view_mode") or "general")
        if next_mode == previous_mode:
            return
        state["mode_transition_running"] = True
        try:
            started = time.perf_counter()
            scroll_offset = max(0.0, float(state.get("table_scroll_offset") or 0.0))
            state["table_scroll_offset"] = scroll_offset
            state["scroll_restore_offset"] = scroll_offset
            state["suppress_scroll_capture_until"] = time.monotonic() + 0.9
            with perf_span("deals.mode.sync_switcher", previous_mode=previous_mode, next_mode=next_mode):
                _sync_view_switcher(mode_buttons, next_mode)
            state["view_mode"] = next_mode
            context.set_shell_theme(next_mode)
            _apply_mode_backdrop_style(mode_backdrop, next_mode)
            current_deals = list(state.get("current_deals") or [])
            if not current_deals:
                refresh(recount=False, preserve_scroll=True)
                context.page.update(view_mode_switch, mode_backdrop)
                return
            with perf_span("deals.mode.replace_columns", previous_mode=previous_mode, next_mode=next_mode, rows=len(current_deals)):
                _replace_visible_columns(
                    context,
                    state,
                    sort_by,
                    refresh,
                    update_visible_deal,
                    previous_mode,
                    next_mode,
                )
            update_controls: list[ft.Control] = [view_mode_switch]
            header = state.get("active_header_container")
            rows = list(state.get("active_body_rows") or [])
            if isinstance(header, ft.Control):
                update_controls.append(header)
            update_controls.extend(row for row in rows if isinstance(row, ft.Control))
            table = state.get("active_table_column")
            list_view = state.get("table_list_view")
            if isinstance(list_view, ft.Control):
                update_controls.append(list_view)
            if isinstance(table, ft.Control):
                update_controls.append(table)
            with perf_span(
                "deals.mode.targeted_update",
                previous_mode=previous_mode,
                next_mode=next_mode,
                controls=len(update_controls),
                rows=len(rows),
            ):
                context.page.update(*update_controls)
            log_perf_event(
                "deals.mode.summary",
                (time.perf_counter() - started) * 1000,
                {
                    "previous_mode": previous_mode,
                    "next_mode": next_mode,
                    "rows": len(current_deals),
                    "animated_columns": 0,
                },
            )
        finally:
            state["mode_transition_running"] = False

    def toggle_sort(_: ft.ControlEvent) -> None:
        state["sort_desc"] = not bool(state["sort_desc"])
        sort_desc.icon = ft.Icons.SOUTH if state["sort_desc"] else ft.Icons.NORTH
        sort_desc.tooltip = (
            "\u041f\u043e \u0443\u0431\u044b\u0432\u0430\u043d\u0438\u044e"
            if state["sort_desc"]
            else "\u041f\u043e \u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u043d\u0438\u044e"
        )
        refresh(recount=False)

    def clear_filters(_: ft.ControlEvent) -> None:
        search.value = ""
        portfolio_filter.value = None
        operation_type_filter.value = None
        referral_filter.value = None
        state["column_filters"] = {}
        state["column_search_filters"] = {}
        state["suspicious_rates_only"] = False
        state["filter_values_cache"] = {}
        state["total_rows"] = None
        state["computed_filtered_deals"] = None
        state["table_scroll_offset"] = 0.0
        context.page.update(search, portfolio_filter, operation_type_filter, referral_filter)
        refresh(recount=True, preserve_scroll=False, partial_update=True)

    async def load_page_after_feedback(token: int) -> None:
        await asyncio.sleep(0.02)
        if token != state.get("page_load_token"):
            return
        refresh(recount=False, partial_update=True)

    def go_to_page(page: int) -> None:
        total_pages = max(1, int(state.get("total_pages") or 1))
        next_page = min(max(1, int(page)), total_pages)
        if next_page == int(state.get("page") or 1):
            return
        state["page"] = next_page
        state["table_scroll_offset"] = 0.0
        state["page_load_token"] = int(state.get("page_load_token") or 0) + 1
        page_input.value = str(next_page)
        pager_label.value = f"\u0421\u0442\u0440. {next_page} / {total_pages}"
        rows_label.value = (
            f"\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 "
            f"\u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b {next_page}..."
        )
        table_holder.opacity = 0.72
        context.page.update(rows_label, pager_label, page_input, table_holder)
        context.page.run_task(load_page_after_feedback, int(state["page_load_token"]))

    def go_to_entered_page(_: ft.ControlEvent | None = None) -> None:
        try:
            page = int(str(page_input.value or "").strip())
        except ValueError:
            page = int(state["page"])
        go_to_page(min(max(1, page), int(state.get("total_pages") or 1)))

    def change_page_size(_: ft.ControlEvent | None = None) -> None:
        old_size = _current_page_size()
        try:
            new_size = int(str(page_size_dropdown.value or PAGE_SIZE))
        except ValueError:
            new_size = PAGE_SIZE
        if new_size not in {25, 50, 100}:
            new_size = PAGE_SIZE
        if new_size == old_size:
            return
        first_row_index = max(0, (int(state.get("page") or 1) - 1) * old_size)
        state["page_size"] = new_size
        state["page"] = first_row_index // new_size + 1
        state["table_scroll_offset"] = 0.0
        refresh(recount=False)

    def _current_page_size() -> int:
        try:
            page_size = int(state.get("page_size") or PAGE_SIZE)
        except (TypeError, ValueError):
            page_size = PAGE_SIZE
        return page_size if page_size in {25, 50, 100} else PAGE_SIZE

    def force_refresh(_: ft.ControlEvent | None = None) -> None:
        state["filter_values_cache"] = {}
        state["referral_rate_cache"] = {}
        state["pnl_breakdown_cache"] = {}
        state["usd_component_cache"] = {}
        state["tooltip_cache"] = {}
        state["active_referral_rules_cache"] = {}
        state["active_rate_rules"] = None
        state["total_rows"] = None
        refresh(recount=True)

    search.on_submit = apply_filters
    portfolio_filter.on_select = apply_filters
    operation_type_filter.on_select = apply_filters
    referral_filter.on_select = apply_filters
    sort_by.on_select = apply_filters
    sort_desc.on_click = toggle_sort
    page_input.on_submit = go_to_entered_page
    page_size_dropdown.on_select = change_page_size

    rebuild_mode_content()

    root = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("\u0414\u0430\u043d\u043d\u044b\u0435 \u0438\u0437 \u041c\u041f", size=28, weight=ft.FontWeight.W_700),
                        ],
                        spacing=2,
                    ),
                    ft.Container(expand=True),
                    view_mode_switch,
                    ft.IconButton(ft.Icons.REFRESH, tooltip="\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c", on_click=force_refresh),
                ]
            ),
            mode_backdrop,
        ],
        expand=True,
        spacing=14,
    )
    refresh(update=False)
    return ft.KeyboardListener(
        content=root,
        autofocus=True,
        on_key_down=handle_keyboard_down,
        on_key_up=handle_keyboard_up,
    )


def _apply_mode_backdrop_style(backdrop: ft.Container, mode: str) -> None:
    """Apply animated mode styling to the registry working area."""
    backdrop.gradient = _mode_gradient(mode)
    if mode == "pnl":
        backdrop.border = ui_theme.border("#334155")
        backdrop.shadow = ft.BoxShadow(blur_radius=34, color="#02061730", offset=ft.Offset(0, 16))
        return
    backdrop.border = ui_theme.border("#E1E8F0")
    backdrop.shadow = ft.BoxShadow(blur_radius=26, color="#0F172A14", offset=ft.Offset(0, 10))


def _has_suspicious_equal_usd_rates(deal: Deal) -> bool:
    currency = str(deal.deal_currency or "").strip().upper()
    if not currency or currency in {"USD", "USDT", "USDC"}:
        return False
    if deal.client_fix_rate is None or deal.usd_rate is None:
        return False
    fix_rate = float(deal.client_fix_rate)
    usd_rate = float(deal.usd_rate)
    return abs(fix_rate - usd_rate) <= max(0.0001, abs(usd_rate) * 0.000001)


def _operation_type_label(deal: Deal) -> str:
    """Return display operation category used by top registry filter."""
    if _is_usdt_deal(deal):
        return "USDT (экспорт)" if _is_export_deal(deal) else "USDT (импорт)"
    return "Экспорт" if _is_export_deal(deal) else "Импорт"


def _is_usdt_deal(deal: Deal) -> bool:
    return str(deal.deal_currency or "").strip().upper() == "USDT"


def _is_export_deal(deal: Deal) -> bool:
    operation_type = str(deal.operation_type or "").strip().upper()
    if operation_type == "EXPORT":
        return True
    return float(deal.deal_amount or deal.amount_buy or 0.0) < 0


def _new_manual_deal() -> Deal:
    """Create a blank deal object suitable for manual entry."""
    today = date.today().isoformat()
    return Deal(
        trade_date=today,
        value_date=today,
        operation_type="manual",
        counterparty="",
        currency_buy="USD",
        amount_buy=0.0,
        currency_sell="USD",
        amount_sell=0.0,
        rate_fact=0.0,
        commission=0.0,
        portfolio="Manual",
        comment="Ручное добавление",
        request_date=None,
        client_fix_date=None,
        agent_writeoff_date=None,
        client_receive_date=None,
        is_repeat_payment=False,
        is_refund=False,
        customer_article_name="Без банка",
        source_file="Ручной ввод",
        source_sheet="Реестр",
        included_in_calc=True,
    )


def _show_deals_message(context, message: str) -> None:
    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=ui_theme.SURFACE,
            title=ft.Text("Реестр сделок"),
            content=ft.Text(message),
            actions=[ft.TextButton("ОК", on_click=lambda _: context.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _referral_dropdown_option(referral: Referral) -> ft.dropdown.Option:
    """Build a referral dropdown option with a compact logo."""
    return ft.dropdown.Option(
        key=referral.name,
        text=referral.name,
        content=ft.Row(
            controls=[
                _referral_mini_logo(referral),
                ft.Text(
                    referral.name,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=ui_theme.TEXT,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=1,
                    expand=True,
                ),
            ],
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _subagent_dropdown_option(value: str) -> ft.dropdown.Option:
    """Build a subagent dropdown option with a compact visual marker."""
    text = str(value or "").strip()
    letters = "".join(part[:1] for part in text.split()[:2]).upper() or "S"
    return ft.dropdown.Option(
        key=text,
        text=text,
        content=ft.Row(
            controls=[
                ft.Container(
                    width=22,
                    height=22,
                    border_radius=7,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=["#EFF6FF", "#DBEAFE"],
                    ),
                    border=ui_theme.border("#BFDBFE"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(letters, size=9, weight=ft.FontWeight.W_900, color=ui_theme.PRIMARY),
                ),
                ft.Text(
                    text,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=ui_theme.TEXT,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=1,
                    expand=True,
                ),
            ],
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _operation_type_option(label: str, color: str) -> ft.dropdown.Option:
    """Build operation type dropdown option with a colored marker."""
    return ft.dropdown.Option(
        key=label,
        text=label,
        content=ft.Row(
            controls=[
                ft.Container(
                    width=10,
                    height=10,
                    border_radius=999,
                    bgcolor=color,
                    shadow=ft.BoxShadow(blur_radius=8, color=f"{color}55", offset=ft.Offset(0, 2)),
                ),
                ft.Text(
                    label,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=ui_theme.TEXT,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=1,
                    expand=True,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _referral_mini_logo(referral: Referral) -> ft.Control:
    logo_src = image_source(referral.logo_path)
    if logo_src:
        return ft.Container(
            width=22,
            height=22,
            border_radius=6,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            bgcolor="#EFF6FF",
            content=ft.Image(
                src=logo_src,
                width=22,
                height=22,
                fit="cover",
                error_content=_referral_letters_logo(referral),
            ),
        )
    return _referral_letters_logo(referral)


def _referral_letters_logo(referral: Referral) -> ft.Container:
    letters = "".join(part[:1] for part in referral.name.split()[:2]).upper() or "R"
    return ft.Container(
        width=22,
        height=22,
        border_radius=6,
        bgcolor="#EFF6FF",
        alignment=ft.Alignment.CENTER,
        content=ft.Text(letters, size=9, weight=ft.FontWeight.W_800, color=ui_theme.PRIMARY),
    )

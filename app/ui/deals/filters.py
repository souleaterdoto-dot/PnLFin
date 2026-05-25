"""Header filter overlay for the deals registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import flet as ft

from app.domain.enums import DealReviewStatus
from app.ui import theme as ui_theme
from app.ui.deals.controls import _style_filter_text_field
from app.ui.deals.constants import COMPUTED_FILTER_COLUMNS
from app.ui.deals.formatters import _format_date, _format_number, _format_short_date, _parse_optional_date


def _header_filter_items(
    context,
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    label: str,
    field_name: str,
    numeric: bool,
) -> list[ft.PopupMenuItem]:
    """Build legacy popup menu items for a header filter."""
    selected = set(state["column_filters"].get(field_name, []))
    suspicious_only_selected = bool(state.get("suspicious_rates_only")) if field_name == "external_deal_id" else False
    column_search_value = str(state["column_search_filters"].get(field_name, ""))
    values = _cached_distinct_values(
        context,
        state,
        field_name,
        search=column_search_value or None,
        limit=40,
    )

    def sort(direction_desc: bool):
        def handler(_: ft.ControlEvent) -> None:
            state["sort_by"] = field_name
            state["sort_desc"] = direction_desc
            state["page"] = 1
            if _dropdown_has_option(sort_by, field_name):
                sort_by.value = field_name
            refresh(recount=False)

        return handler

    def clear(_: ft.ControlEvent) -> None:
        filters = dict(state["column_filters"])
        searches = dict(state["column_search_filters"])
        filters.pop(field_name, None)
        searches.pop(field_name, None)
        state["column_filters"] = filters
        state["column_search_filters"] = searches
        state["page"] = 1
        refresh()

    def apply_column_search(event: ft.ControlEvent) -> None:
        value = str(event.control.value or "").strip()
        searches = dict(state["column_search_filters"])
        if value:
            searches[field_name] = value
        else:
            searches.pop(field_name, None)
        state["column_search_filters"] = searches
        state["page"] = 1
        refresh()

    def toggle(value: str):
        def handler(_: ft.ControlEvent) -> None:
            filters = dict(state["column_filters"])
            current = set(filters.get(field_name, []))
            if value in current:
                current.remove(value)
            else:
                current.add(value)
            if current:
                filters[field_name] = sorted(current)
            else:
                filters.pop(field_name, None)
            state["column_filters"] = filters
            state["page"] = 1
            refresh()

        return handler

    items: list[ft.PopupMenuItem] = [
        ft.PopupMenuItem(content=f"{label}", height=34, disabled=True),
        ft.PopupMenuItem(
            content=ft.TextField(
                value=column_search_value,
                hint_text="Поиск в колонке, Enter",
                prefix_icon=ft.Icons.SEARCH,
                dense=True,
                width=260,
                on_submit=apply_column_search,
            ),
            height=56,
        ),
        ft.PopupMenuItem(content="Сортировать А-Я / 0-9", icon=ft.Icons.NORTH, on_click=sort(False)),
        ft.PopupMenuItem(content="Сортировать Я-А / 9-0", icon=ft.Icons.SOUTH, on_click=sort(True)),
        ft.PopupMenuItem(content="Сбросить фильтр", icon=ft.Icons.FILTER_ALT_OFF_OUTLINED, on_click=clear),
    ]
    if not values:
        items.append(ft.PopupMenuItem(content="Значений не найдено", height=36, disabled=True))
        return items

    for raw_value in values:
        items.append(
            ft.PopupMenuItem(
                content=_display_filter_value(field_name, raw_value, numeric),
                checked=raw_value in selected,
                on_click=toggle(raw_value),
                height=36,
            )
        )
    return items


def _cached_distinct_values(
    context,
    state: dict[str, Any],
    field_name: str,
    search: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Return cached distinct column values for header filters."""
    cache = state.setdefault("filter_values_cache", {})
    key = (field_name, (search or "").casefold(), limit or 0)
    if key not in cache:
        cache[key] = context.deals_repository.distinct_values(field_name, search=search, limit=limit)
    return list(cache[key])


def _open_header_filter_overlay(
    context,
    state: dict[str, Any],
    sort_by: ft.Dropdown,
    refresh,
    label: str,
    field_name: str,
    numeric: bool,
    position: ft.Offset | None,
    open_date_picker,
    calendar_icon_button,
) -> None:
    """Open the Excel-like header filter overlay."""
    _remove_header_filter_overlays(context.page)
    selected = set(state["column_filters"].get(field_name, []))
    suspicious_only_selected = bool(state.get("suspicious_rates_only")) if field_name == "external_deal_id" else False
    review_status_selected = set(state["column_filters"].get("review_status", [])) if field_name == "client_name" else set()
    overlay_ref: dict[str, ft.Control | None] = {"control": None}
    search = ft.TextField(
        hint_text="Поиск значений",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        width=306,
    )
    if _is_date_field(field_name):
        search.hint_text = "Выберите дату или введите дд.мм.гг"
        search.suffix = calendar_icon_button(
            lambda _: open_date_picker(
                context,
                search,
                on_selected=lambda: load_values(update=True),
                storage_format=False,
            )
        )
    _style_filter_text_field(search)
    selected_count = ft.Text(size=11, color=ui_theme.MUTED)
    values_holder = ft.Container(
        width=334,
        bgcolor=ui_theme.SURFACE,
        content=ft.Container(height=34, bgcolor=ui_theme.SURFACE),
    )
    current_values: list[str] = []
    all_values_selected = False
    show_all_values = False
    expanded_years: set[int] = set()
    expanded_months: set[tuple[int, int]] = set()
    month_names = (
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    )

    def close_overlay() -> None:
        overlay = overlay_ref["control"]
        if overlay and overlay in context.page.overlay:
            context.page.overlay.remove(overlay)
            context.page.update()

    def update_selected_count() -> None:
        selected_count.value = "Выбраны все" if all_values_selected else f"Выбрано: {len(selected)}"

    def is_selected(value: str) -> bool:
        return all_values_selected or value in selected

    def build_values_list(values: list[str]) -> ft.Control:
        nonlocal show_all_values
        if _is_date_field(field_name):
            return build_date_values_tree(values)

        controls: list[ft.Control] = []
        if not values:
            controls.append(
                ft.Container(
                    height=34,
                    bgcolor=ui_theme.SURFACE,
                    border=ui_theme.border("#E2E8F0"),
                    border_radius=10,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("Значений не найдено", color=ui_theme.MUTED),
                )
            )

        visible_values = values if show_all_values else values[:6]
        for raw_value in visible_values:
            value_selected = is_selected(raw_value)

            icon = ft.Icon(
                ft.Icons.CHECK_BOX if value_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                size=16,
                color=ui_theme.PRIMARY if value_selected else ui_theme.MUTED,
            )
            row_container = ft.Container(
                content=ft.Row(
                    controls=[
                        icon,
                        ft.Text(
                            _display_filter_value(field_name, raw_value, numeric),
                            size=12,
                            color=ui_theme.TEXT,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#EFF6FF" if value_selected else ui_theme.SURFACE,
                border=ui_theme.border("#93C5FD" if value_selected else "#E2E8F0"),
                border_radius=9,
                height=31,
                padding=ft.Padding(8, 0, 8, 0),
                ink=True,
                ink_color="#DBEAFE",
            )

            def toggle_value(
                _: ft.ControlEvent,
                value=raw_value,
                all_values=values,
                row=row_container,
                checkbox_icon=icon,
            ) -> None:
                nonlocal all_values_selected
                if all_values_selected:
                    selected.clear()
                    selected.update(item for item in all_values if item)
                    all_values_selected = False
                if value in selected:
                    selected.discard(value)
                else:
                    selected.add(value)
                update_selected_count()
                value_selected_now = value in selected
                checkbox_icon.icon = ft.Icons.CHECK_BOX if value_selected_now else ft.Icons.CHECK_BOX_OUTLINE_BLANK
                checkbox_icon.color = ui_theme.PRIMARY if value_selected_now else ui_theme.MUTED
                row.bgcolor = "#EFF6FF" if value_selected_now else ui_theme.SURFACE
                row.border = ui_theme.border("#93C5FD" if value_selected_now else "#E2E8F0")
                context.page.update(row, selected_count)

            row_container.on_click = toggle_value
            controls.append(row_container)

        if len(values) > len(visible_values):
            controls.append(
                ft.Container(
                    padding=ft.Padding(8, 4, 8, 0),
                    bgcolor=ui_theme.SURFACE,
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                f"\u041f\u043e\u043a\u0430\u0437\u0430\u043d\u043e {len(visible_values)} \u0438\u0437 {len(values)}",
                                size=11,
                                color=ui_theme.MUTED,
                                expand=True,
                            ),
                            ft.TextButton(
                                "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0432\u0441\u0435",
                                height=26,
                                style=ft.ButtonStyle(padding=ft.Padding(8, 0, 8, 0)),
                                on_click=lambda _: load_all_values(values),
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        list_height = 252 if show_all_values and len(values) > 6 else None
        return ft.Container(
            height=list_height,
            padding=ft.Padding(0, 2, 0, 2),
            bgcolor=ui_theme.SURFACE,
            content=ft.Column(
                controls=controls,
                spacing=4,
                tight=not bool(list_height),
                scroll=ft.ScrollMode.AUTO if list_height else None,
            ),
        )

    def load_all_values(values: list[str]) -> None:
        nonlocal show_all_values
        show_all_values = True
        values_holder.content = build_values_list(values)
        context.page.update(values_holder)


    def build_date_values_tree(values: list[str]) -> ft.Control:
        grouped: dict[int, dict[int, list[str]]] = {}
        for raw_value in values:
            parsed = _parse_optional_date(raw_value)
            if not parsed:
                continue
            try:
                parsed_date = datetime.strptime(parsed, "%Y-%m-%d").date()
            except ValueError:
                continue
            grouped.setdefault(parsed_date.year, {}).setdefault(parsed_date.month, []).append(parsed)

        controls: list[ft.Control] = []
        if not grouped:
            controls.append(
                ft.Container(
                    height=34,
                    bgcolor=ui_theme.SURFACE,
                    border=ui_theme.border("#E2E8F0"),
                    border_radius=10,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("Дат не найдено", color=ui_theme.MUTED),
                )
            )

        for year in sorted(grouped):
            year_values = [item for month in grouped[year].values() for item in month]
            controls.append(
                _date_group_row(
                    label=str(year),
                    values=year_values,
                    selected=set(year_values) if all_values_selected else selected,
                    expanded=year in expanded_years,
                    level=0,
                    on_expand=lambda _, value=year: toggle_year(value),
                    on_select=lambda _, items=year_values: toggle_date_group(items, values),
                )
            )
            if year not in expanded_years:
                continue
            for month in sorted(grouped[year]):
                month_values = grouped[year][month]
                month_key = (year, month)
                controls.append(
                    _date_group_row(
                        label=month_names[month - 1],
                        values=month_values,
                        selected=set(month_values) if all_values_selected else selected,
                        expanded=month_key in expanded_months,
                        level=1,
                        on_expand=lambda _, value=month_key: toggle_month(value),
                        on_select=lambda _, items=month_values: toggle_date_group(items, values),
                    )
                )
                if month_key not in expanded_months:
                    continue
                for raw_date in sorted(month_values):
                    controls.append(
                        _date_day_row(
                            raw_date=raw_date,
                            selected=is_selected(raw_date),
                            on_select=lambda _, value=raw_date: toggle_date_value(value, values),
                        )
                    )

        return ft.Container(
            padding=ft.Padding(0, 2, 0, 2),
            bgcolor=ui_theme.SURFACE,
            content=ft.Column(controls=controls, spacing=4, tight=True),
        )

    def toggle_year(year: int) -> None:
        if year in expanded_years:
            expanded_years.remove(year)
        else:
            expanded_years.add(year)
        load_values(update=True)

    def toggle_month(month_key: tuple[int, int]) -> None:
        if month_key in expanded_months:
            expanded_months.remove(month_key)
        else:
            expanded_months.add(month_key)
        load_values(update=True)

    def toggle_date_group(items: list[str], current_values: list[str]) -> None:
        nonlocal all_values_selected
        if all_values_selected:
            selected.clear()
            selected.update(item for item in current_values if item)
            all_values_selected = False
        normalized = {item for item in items if item}
        if normalized and normalized.issubset(selected):
            selected.difference_update(normalized)
        else:
            selected.update(normalized)
        update_selected_count()
        values_holder.content = build_values_list(current_values)
        context.page.update(values_holder, selected_count)

    def toggle_date_value(value: str, current_values: list[str]) -> None:
        nonlocal all_values_selected
        if all_values_selected:
            selected.clear()
            selected.update(item for item in current_values if item)
            all_values_selected = False
        if value in selected:
            selected.discard(value)
        else:
            selected.add(value)
        update_selected_count()
        values_holder.content = build_values_list(current_values)
        context.page.update(values_holder, selected_count)

    def load_values(_: ft.ControlEvent | None = None, update: bool = True) -> None:
        nonlocal current_values, show_all_values
        show_all_values = False
        if field_name in COMPUTED_FILTER_COLUMNS:
            provider = state.get("computed_filter_values_provider")
            values = provider(field_name, search.value, 500) if callable(provider) else []
        else:
            values = context.deals_repository.distinct_values(
                field_name,
                search=_date_search_value(field_name, search.value),
                limit=500,
            )
        current_values = values
        values_holder.content = build_values_list(values)
        update_selected_count()
        if update:
            context.page.update(values_holder, selected_count)

    def apply_filter(_: ft.ControlEvent) -> None:
        nonlocal suspicious_only_selected
        filters = dict(state["column_filters"])
        if all_values_selected:
            filters.pop(field_name, None)
        elif selected:
            filters[field_name] = sorted(selected)
        else:
            filters.pop(field_name, None)
        state["column_filters"] = filters
        if field_name == "client_name":
            if review_status_selected:
                filters["review_status"] = sorted(review_status_selected)
            else:
                filters.pop("review_status", None)
            state["column_filters"] = filters
        if field_name == "external_deal_id":
            state["suspicious_rates_only"] = suspicious_only_selected
        state["page"] = 1
        close_overlay()
        refresh()

    def clear_filter(_: ft.ControlEvent) -> None:
        nonlocal all_values_selected, suspicious_only_selected
        all_values_selected = False
        suspicious_only_selected = False
        review_status_selected.clear()
        selected.clear()
        filters = dict(state["column_filters"])
        filters.pop(field_name, None)
        if field_name == "client_name":
            filters.pop("review_status", None)
        state["column_filters"] = filters
        if field_name == "external_deal_id":
            state["suspicious_rates_only"] = False
        state["page"] = 1
        close_overlay()
        refresh()

    def select_all(_: ft.ControlEvent) -> None:
        nonlocal all_values_selected
        all_values_selected = True
        selected.clear()
        filters = dict(state["column_filters"])
        filters.pop(field_name, None)
        state["column_filters"] = filters
        values_holder.content = build_values_list(current_values)
        update_selected_count()
        context.page.update(values_holder, selected_count)

    def deselect_all(_: ft.ControlEvent) -> None:
        nonlocal all_values_selected
        all_values_selected = False
        selected.clear()
        values_holder.content = build_values_list(current_values)
        update_selected_count()
        context.page.update(values_holder, selected_count)

    def sort(direction_desc: bool) -> None:
        state["sort_by"] = field_name
        state["sort_desc"] = direction_desc
        if _dropdown_has_option(sort_by, field_name):
            sort_by.value = field_name
        close_overlay()
        refresh()

    search.on_change = load_values
    load_values(update=False)
    suspicious_checkbox_icon = ft.Icon(
        ft.Icons.CHECK_BOX if suspicious_only_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
        size=17,
        color="#DC2626" if suspicious_only_selected else ui_theme.MUTED,
    )
    suspicious_filter_row = ft.Container(
        visible=field_name == "external_deal_id",
        height=36,
        padding=ft.Padding(8, 0, 8, 0),
        border_radius=10,
        bgcolor="#FEF2F2" if suspicious_only_selected else "#F8FAFC",
        border=ui_theme.border("#FCA5A5" if suspicious_only_selected else "#E2E8F0"),
        ink=True,
        ink_color="#FEE2E2",
        content=ft.Row(
            controls=[
                suspicious_checkbox_icon,
                ft.Container(
                    width=22,
                    height=22,
                    border_radius=8,
                    bgcolor="#FEF2F2",
                    border=ui_theme.border("#FCA5A5"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.PRIORITY_HIGH_ROUNDED, size=14, color="#DC2626"),
                ),
                ft.Text(
                    "Только сделки с подозрительным курсом",
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=ui_theme.TEXT,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True,
                ),
            ],
            spacing=7,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    def toggle_suspicious_only(_: ft.ControlEvent) -> None:
        nonlocal suspicious_only_selected
        suspicious_only_selected = not suspicious_only_selected
        suspicious_checkbox_icon.icon = ft.Icons.CHECK_BOX if suspicious_only_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        suspicious_checkbox_icon.color = "#DC2626" if suspicious_only_selected else ui_theme.MUTED
        suspicious_filter_row.bgcolor = "#FEF2F2" if suspicious_only_selected else "#F8FAFC"
        suspicious_filter_row.border = ui_theme.border("#FCA5A5" if suspicious_only_selected else "#E2E8F0")
        context.page.update(suspicious_filter_row)

    suspicious_filter_row.on_click = toggle_suspicious_only

    review_verified_icon = ft.Icon(
        ft.Icons.CHECK_BOX if DealReviewStatus.VERIFIED.value in review_status_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
        size=17,
        color="#16A34A" if DealReviewStatus.VERIFIED.value in review_status_selected else ui_theme.MUTED,
    )
    review_question_icon = ft.Icon(
        ft.Icons.CHECK_BOX if DealReviewStatus.QUESTION.value in review_status_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
        size=17,
        color="#D97706" if DealReviewStatus.QUESTION.value in review_status_selected else ui_theme.MUTED,
    )

    def build_review_status_button(status: DealReviewStatus, icon_control: ft.Icon, icon_data: Any, color: str, tooltip: str) -> ft.Container:
        is_active = status.value in review_status_selected
        return ft.Container(
            width=38,
            height=32,
            border_radius=11,
            bgcolor="#ECFDF5" if is_active and status == DealReviewStatus.VERIFIED else ("#FFF7ED" if is_active else "#F8FAFC"),
            border=ui_theme.border("#86EFAC" if is_active and status == DealReviewStatus.VERIFIED else ("#FDBA74" if is_active else "#E2E8F0")),
            ink=True,
            ink_color="#DBEAFE",
            tooltip=tooltip,
            content=ft.Row(
                controls=[
                    icon_control,
                    ft.Icon(icon_data, size=15, color=color),
                ],
                spacing=3,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    review_verified_row = build_review_status_button(
        DealReviewStatus.VERIFIED,
        review_verified_icon,
        ft.Icons.CHECK_CIRCLE,
        "#16A34A",
        "Только проверенные",
    )
    review_question_row = build_review_status_button(
        DealReviewStatus.QUESTION,
        review_question_icon,
        ft.Icons.HELP_OUTLINE,
        "#D97706",
        "Только под вопросом",
    )
    review_status_filter_row = ft.Container(
        visible=field_name == "client_name",
        height=38,
        padding=ft.Padding(7, 3, 7, 3),
        border_radius=12,
        bgcolor="#F8FAFC",
        border=ui_theme.border("#E2E8F0"),
        content=ft.Row(
            controls=[review_verified_row, review_question_row],
            spacing=7,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    def update_review_status_row(row: ft.Container, icon_control: ft.Icon, status: DealReviewStatus) -> None:
        is_active = status.value in review_status_selected
        icon_control.icon = ft.Icons.CHECK_BOX if is_active else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        if status == DealReviewStatus.VERIFIED:
            icon_control.color = "#16A34A" if is_active else ui_theme.MUTED
            row.bgcolor = "#ECFDF5" if is_active else "#F8FAFC"
            row.border = ui_theme.border("#86EFAC" if is_active else "#E2E8F0")
        else:
            icon_control.color = "#D97706" if is_active else ui_theme.MUTED
            row.bgcolor = "#FFF7ED" if is_active else "#F8FAFC"
            row.border = ui_theme.border("#FDBA74" if is_active else "#E2E8F0")

    def toggle_review_status(status: DealReviewStatus):
        def handler(_: ft.ControlEvent) -> None:
            if status.value in review_status_selected:
                review_status_selected.remove(status.value)
            else:
                review_status_selected.add(status.value)
            update_review_status_row(review_verified_row, review_verified_icon, DealReviewStatus.VERIFIED)
            update_review_status_row(review_question_row, review_question_icon, DealReviewStatus.QUESTION)
            context.page.update(review_status_filter_row)

        return handler

    review_verified_row.on_click = toggle_review_status(DealReviewStatus.VERIFIED)
    review_question_row.on_click = toggle_review_status(DealReviewStatus.QUESTION)
    panel = ft.Container(
        width=360,
        padding=12,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border("#D8E2F0"),
        border_radius=14,
        shadow=ft.BoxShadow(blur_radius=30, color="#0F172A22", offset=ft.Offset(0, 14)),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            width=30,
                            height=30,
                            border_radius=10,
                            bgcolor=ui_theme.PRIMARY_SOFT,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.FILTER_ALT_OUTLINED, size=16, color=ui_theme.PRIMARY),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(label, size=13, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                                ft.Text("Фильтр и сортировка", size=10, color=ui_theme.MUTED),
                            ],
                            spacing=0,
                            width=144,
                        ),
                        ft.IconButton(
                            ft.Icons.NORTH,
                            icon_size=15,
                            icon_color=ui_theme.PRIMARY,
                            tooltip="А-Я / 0-9",
                            on_click=lambda _: sort(False),
                            width=30,
                            height=30,
                        ),
                        ft.IconButton(
                            ft.Icons.SOUTH,
                            icon_size=15,
                            icon_color=ui_theme.PRIMARY,
                            tooltip="Я-А / 9-0",
                            on_click=lambda _: sort(True),
                            width=30,
                            height=30,
                        ),
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            icon_size=17,
                            tooltip="Закрыть",
                            on_click=lambda _: close_overlay(),
                            width=30,
                            height=30,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                search,
                suspicious_filter_row,
                review_status_filter_row,
                ft.Container(
                    height=30,
                    padding=ft.Padding(6, 0, 6, 0),
                    border_radius=9,
                    bgcolor="#F8FAFC",
                    border=ui_theme.border("#E2E8F0"),
                    content=ft.Row(
                        controls=[
                            ft.TextButton(
                                "Все",
                                on_click=select_all,
                                height=26,
                                style=ft.ButtonStyle(padding=ft.Padding(8, 0, 8, 0)),
                            ),
                            ft.TextButton(
                                "Снять",
                                on_click=deselect_all,
                                height=26,
                                style=ft.ButtonStyle(padding=ft.Padding(8, 0, 8, 0)),
                            ),
                            ft.Container(expand=True),
                            ft.Container(
                                padding=ft.Padding(8, 3, 8, 3),
                                border_radius=999,
                                bgcolor="#FFFFFF",
                                border=ui_theme.border("#E2E8F0"),
                                content=selected_count,
                            ),
                        ],
                        spacing=3,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                values_holder,
            ],
            spacing=7,
            tight=True,
        ),
    )
    panel.content.controls.append(
        ft.Row(
            controls=[
                ft.TextButton(
                    "Сбросить",
                    on_click=clear_filter,
                    height=34,
                    style=ft.ButtonStyle(padding=ft.Padding(10, 0, 10, 0)),
                ),
                ft.FilledButton(
                    "Применить",
                    icon=ft.Icons.CHECK,
                    height=34,
                    style=ft.ButtonStyle(
                        bgcolor=ui_theme.PRIMARY,
                        color="#FFFFFF",
                        padding=ft.Padding(12, 0, 12, 0),
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    on_click=apply_filter,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        )
    )
    left, top = _filter_overlay_position(context.page, position)
    overlay = ft.Container(panel, left=left, top=top, data="deals_header_filter_overlay")
    overlay_ref["control"] = overlay
    context.page.overlay.append(overlay)
    context.page.update()


def _remove_header_filter_overlays(page: ft.Page) -> None:
    """Remove active header filter overlays from the page."""
    page.overlay[:] = [
        control
        for control in page.overlay
        if getattr(control, "data", None) != "deals_header_filter_overlay"
    ]


def _date_group_row(
    label: str,
    values: list[str],
    selected: set[str],
    expanded: bool,
    level: int,
    on_expand,
    on_select,
) -> ft.Control:
    values_set = {value for value in values if value}
    selected_count = len(values_set.intersection(selected))
    all_selected = bool(values_set) and selected_count == len(values_set)
    partial_selected = selected_count > 0 and not all_selected
    return ft.Container(
        height=31,
        padding=ft.Padding(6 + level * 16, 0, 8, 0),
        border_radius=9,
        bgcolor="#EFF6FF" if all_selected or partial_selected else ui_theme.SURFACE,
        border=ui_theme.border("#93C5FD" if all_selected or partial_selected else "#E2E8F0"),
        content=ft.Row(
            controls=[
                ft.IconButton(
                    ft.Icons.EXPAND_MORE if expanded else ft.Icons.CHEVRON_RIGHT,
                    icon_size=16,
                    icon_color=ui_theme.PRIMARY,
                    tooltip="Развернуть" if not expanded else "Свернуть",
                    on_click=on_expand,
                ),
                ft.Container(
                    width=22,
                    height=22,
                    border_radius=7,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ui_theme.PRIMARY_SOFT if all_selected or partial_selected else ui_theme.SURFACE,
                    border=ui_theme.border("#93C5FD" if all_selected or partial_selected else "#CBD5E1"),
                    ink=True,
                    ink_color="#DBEAFE",
                    on_click=on_select,
                    content=ft.Icon(
                        ft.Icons.CHECK_BOX if all_selected else ft.Icons.INDETERMINATE_CHECK_BOX if partial_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                        size=15,
                        color=ui_theme.PRIMARY if all_selected or partial_selected else ui_theme.MUTED,
                    ),
                ),
                ft.Text(label, size=12, weight=ft.FontWeight.W_700, color=ui_theme.TEXT, expand=True),
                ft.Text(str(len(values_set)), size=11, color=ui_theme.MUTED),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _date_day_row(raw_date: str, selected: bool, on_select) -> ft.Control:
    return ft.Container(
        height=30,
        padding=ft.Padding(42, 0, 8, 0),
        border_radius=9,
        bgcolor="#EFF6FF" if selected else ui_theme.SURFACE,
        border=ui_theme.border("#93C5FD" if selected else "#E2E8F0"),
        ink=True,
        ink_color="#DBEAFE",
        on_click=on_select,
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.CHECK_BOX if selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                    size=15,
                    color=ui_theme.PRIMARY if selected else ui_theme.MUTED,
                ),
                ft.Text(_format_short_date(raw_date), size=12, color=ui_theme.TEXT),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _filter_overlay_position(page: ft.Page, position: ft.Offset | None) -> tuple[float, float]:
    x = float(position.x if position else 240)
    y = float(position.y if position else 160) + 24
    page_width = float(getattr(page, "width", 0) or 0)
    page_height = float(getattr(page, "height", 0) or 0)
    if page_width:
        x = min(max(8, x), max(8, page_width - 370))
    else:
        x = max(8, x)
    if page_height:
        y = min(max(8, y), max(8, page_height - 430))
    return x, max(8, y)


def _display_filter_value(field_name: str, raw_value: str, numeric: bool) -> str:
    if field_name in {"is_repeat_payment", "is_refund"}:
        return "Да" if raw_value == "1" else "Нет"
    if _is_date_field(field_name):
        return _format_date(raw_value)
    if numeric:
        try:
            decimals = 4 if field_name in {"client_fix_rate", "usd_rate", "client_cross_rate"} else 2
            return _format_number(float(raw_value), decimals)
        except ValueError:
            return raw_value
    return raw_value


def _filter_checkbox(control: ft.Control) -> ft.Checkbox | None:
    if isinstance(control, ft.Checkbox):
        return control
    if isinstance(control, ft.Container) and isinstance(control.content, ft.Checkbox):
        return control.content
    return None


def _dropdown_has_option(dropdown: ft.Dropdown, key: str) -> bool:
    return any(option.key == key for option in dropdown.options)


def _is_date_field(field_name: str) -> bool:
    return field_name.endswith("_date") or field_name in {
        "request_date",
        "client_fix_date",
        "agent_writeoff_date",
        "client_receive_date",
        "agent_refund_date",
        "client_refund_date",
    }


def _date_search_value(field_name: str, value: str | None) -> str | None:
    if not _is_date_field(field_name):
        return value
    parsed = _parse_optional_date(value or "")
    return parsed or value

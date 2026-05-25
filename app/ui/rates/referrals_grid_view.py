"""Referral rates landing screen."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import flet as ft

from app.database.connection import APP_DATA_DIR
from app.domain.rate_models import ClientRateException
from app.ui import theme as ui_theme
from app.ui.deals.edit_dialog import _calendar_icon_button, _open_date_picker
from app.ui.deals.formatters import _format_short_date, _parse_optional_date
from app.ui.rates.referral_card import referral_card
from app.ui.rates.referral_detail_view import create_referral_detail_view


def create_referrals_grid_view(context) -> ft.Control:
    """Create referral cards grid."""
    context.referrals_service.sync_from_deals()
    grid_holder = ft.Container(expand=True)
    search = ft.TextField(
        hint_text="Поиск по названию реферала",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )
    _style_field(search)
    status = ft.Text("", color=ui_theme.MUTED, visible=False)
    file_picker = ft.FilePicker()

    def refresh(update: bool = True) -> None:
        referrals = context.referrals_service.list(search=search.value)
        grid_holder.content = _grid_content(context, referrals, open_detail, confirm_delete)
        if update:
            context.page.update()

    def open_detail(referral) -> None:
        fresh = context.referrals_repository.get(referral.id) if referral.id else referral
        context.set_content(
            create_referral_detail_view(
                context,
                fresh or referral,
                lambda: context.set_content(create_referrals_grid_view(context)),
            )
        )

    def add_referral(_: ft.ControlEvent) -> None:
        _open_add_referral_dialog(context, lambda: refresh(True))

    def confirm_delete(referral) -> None:
        _open_delete_referral_dialog(context, referral, lambda: refresh(True))

    async def import_excel(_: ft.ControlEvent) -> None:
        files = await file_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx", "xlsm"],
        )
        if not files or not files[0].path:
            return
        try:
            result = await asyncio.to_thread(context.rate_conditions_excel_service.import_file, files[0].path)
            status.value = (
                "\u0418\u043c\u043f\u043e\u0440\u0442 \u0441\u0442\u0430\u0432\u043e\u043a: "
                f"{result.rows_success} \u0443\u0441\u043f\u0435\u0448\u043d\u043e, "
                f"{result.rows_failed} \u0441 \u043e\u0448\u0438\u0431\u043a\u0430\u043c\u0438."
                + (f" {'; '.join(result.errors[:3])}" if result.errors else "")
            )
            status.color = ui_theme.MUTED if result.rows_failed == 0 else ui_theme.DANGER
            status.visible = True
            refresh(update=False)
            context.page.update()
        except Exception as exc:
            status.value = str(exc)
            status.color = ui_theme.DANGER
            status.visible = True
            context.page.update()

    def show_example(_: ft.ControlEvent) -> None:
        try:
            path = context.rate_conditions_excel_service.create_example_file(
                Path(APP_DATA_DIR) / "rate_conditions_import_example.xlsx"
            )
            os.startfile(path)
        except Exception as exc:
            status.value = str(exc)
            status.color = ui_theme.DANGER
            status.visible = True
            context.page.update()

    def open_client_exceptions(_: ft.ControlEvent) -> None:
        context.set_content(
            create_client_exceptions_view(
                context,
                lambda: context.set_content(create_referrals_grid_view(context)),
            )
        )

    search.on_submit = lambda _: refresh()
    root = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("Ставки", size=30, weight=ft.FontWeight.W_700),
                            ft.Text(
                                "Справочник рефералов, банков и партнеров с ручными условиями ставок.",
                                color=ui_theme.MUTED,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.OutlinedButton(
                        'Клиенты "Исключения"',
                        icon=ft.Icons.PERSON_SEARCH_OUTLINED,
                        on_click=open_client_exceptions,
                    ),
                    ft.OutlinedButton(
                        "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043f\u0440\u0438\u043c\u0435\u0440",
                        icon=ft.Icons.TABLE_VIEW_OUTLINED,
                        on_click=show_example,
                    ),
                    ft.OutlinedButton(
                        "\u0418\u043c\u043f\u043e\u0440\u0442 Excel",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=import_excel,
                    ),
                    ui_theme.primary_button("Добавить реферала", icon=ft.Icons.ADD, on_click=add_referral),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ui_theme.panel(
                ft.Row(
                    controls=[
                        search,
                        ft.IconButton(ft.Icons.REFRESH, tooltip="Обновить", on_click=lambda _: refresh()),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14,
            ),
            status,
            grid_holder,
        ],
        expand=True,
        spacing=14,
    )
    refresh(update=False)
    return root


def _open_client_exceptions_placeholder(context) -> None:
    clients = context.deals_repository.distinct_values("client_name")
    existing_by_name = context.client_rate_exceptions_repository.get_by_client_names(clients)
    for exception in context.client_rate_exceptions_repository.list():
        key = exception.client_name.casefold()
        if key not in existing_by_name:
            existing_by_name[key] = exception
            clients.append(exception.client_name)
    clients = sorted(set(clients), key=lambda value: value.casefold())

    rows: list[tuple[str, ft.TextField, ft.TextField, ft.TextField]] = []
    error = ft.Text("", color=ui_theme.DANGER, visible=False)

    def date_field(label: str, value: str | None) -> ft.TextField:
        field = ft.TextField(
            label=label,
            value="" if not value else _format_short_date(value),
            hint_text="дд.мм.гг",
            dense=True,
            width=112,
        )
        _style_field(field)
        return field

    def note_field(value: str | None) -> ft.TextField:
        field = ft.TextField(
            hint_text="Комментарий / причина исключения",
            value=value or "",
            dense=True,
            expand=True,
        )
        _style_field(field)
        return field

    def row_for_client(client_name: str) -> ft.Control:
        exception = existing_by_name.get(client_name.casefold())
        note = note_field(exception.note if exception else None)
        date_from = date_field("Дата начала", exception.date_from if exception else None)
        date_to = date_field("Дата окончания", exception.date_to if exception else None)
        rows.append((client_name, note, date_from, date_to))
        configured = exception is not None
        return ft.Container(
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=14,
            bgcolor="#FFFFFF" if configured else "#F8FAFC",
            border=ui_theme.border("#BFDBFE" if configured else "#E2E8F0"),
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=190,
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.VERIFIED_OUTLINED if configured else ft.Icons.PERSON_OUTLINE,
                                    size=18,
                                    color=ui_theme.PRIMARY if configured else ui_theme.MUTED,
                                ),
                                ft.Text(
                                    client_name,
                                    size=13,
                                    weight=ft.FontWeight.W_700,
                                    color=ui_theme.TEXT,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    note,
                    date_from,
                    date_to,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def save(_: ft.ControlEvent | None = None) -> None:
        try:
            for client_name, note, date_from, date_to in rows:
                note_value = str(note.value or "").strip()
                from_value = str(date_from.value or "").strip()
                to_value = str(date_to.value or "").strip()
                has_any = bool(note_value or from_value or to_value)
                if not has_any:
                    context.client_rate_exceptions_repository.delete_by_client_name(client_name)
                    continue
                if not note_value or not from_value:
                    raise ValueError(f"Для клиента «{client_name}» заполните комментарий и дату начала.")
                parsed_from = _parse_optional_date(from_value)
                parsed_to = _parse_optional_date(to_value) if to_value else None
                if not parsed_from:
                    raise ValueError(f"Для клиента «{client_name}» даты должны быть в формате дд.мм.гг.")
                if parsed_to and parsed_from > parsed_to:
                    raise ValueError(f"Для клиента «{client_name}» дата начала не может быть позже даты окончания.")
                context.client_rate_exceptions_repository.save(
                    ClientRateException(
                        client_name=client_name,
                        note=note_value,
                        date_from=parsed_from,
                        date_to=parsed_to,
                    )
                )
            context.page.pop_dialog()
        except Exception as exc:
            error.value = str(exc)
            error.visible = True
            context.page.update(error)

    body = (
        ft.Container(
            height=420,
            content=ft.Column(
                controls=[
                    row_for_client(client)
                    for client in clients
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        )
        if clients
        else ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.Text("В реестре пока нет клиентов.", color=ui_theme.MUTED),
        )
    )
    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ui_theme.SURFACE,
        barrier_color="#0F172A66",
        title=ft.Row(
            controls=[
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=12,
                    bgcolor="#EFF6FF",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.PERSON_SEARCH_OUTLINED, size=23, color=ui_theme.PRIMARY),
                ),
                ft.Column(
                    controls=[
                        ft.Text('Клиенты "Исключения"', size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                        ft.Text("Отдельный справочник особых клиентских правил", size=12, color=ui_theme.MUTED),
                    ],
                    spacing=0,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=860,
            padding=ft.Padding(2, 4, 2, 0),
            content=ft.Column(
                controls=[
                    ft.Container(
                        padding=ft.Padding(12, 10, 12, 10),
                        border_radius=12,
                        bgcolor="#F8FAFC",
                        border=ui_theme.border("#D8E2F0"),
                        content=ft.Text(
                            "Заполните строку клиента, если для него ставка реферала должна вводиться вручную в указанный период.",
                            size=13,
                            color=ui_theme.TEXT,
                        ),
                    ),
                    ft.Container(
                        padding=ft.Padding(12, 0, 12, 0),
                        content=ft.Row(
                            controls=[
                                ft.Text("Клиент", width=190, size=11, weight=ft.FontWeight.W_800, color=ui_theme.MUTED),
                                ft.Text("Комментарий", expand=True, size=11, weight=ft.FontWeight.W_800, color=ui_theme.MUTED),
                                ft.Text("Начало", width=112, size=11, weight=ft.FontWeight.W_800, color=ui_theme.MUTED),
                                ft.Text("Окончание", width=112, size=11, weight=ft.FontWeight.W_800, color=ui_theme.MUTED),
                            ],
                            spacing=10,
                        ),
                    ),
                    body,
                    error,
                ],
                spacing=10,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Закрыть", on_click=lambda _: context.page.pop_dialog()),
            ui_theme.primary_button("Сохранить", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    context.page.show_dialog(dialog)


def create_client_exceptions_view(context, on_back) -> ft.Control:
    """Create standalone client exceptions screen with only configured rows."""
    table_holder = ft.Container(expand=True)
    status = ft.Text("", color=ui_theme.MUTED, visible=False)

    def refresh(update: bool = True) -> None:
        exceptions = context.client_rate_exceptions_repository.list()
        table_holder.content = _client_exceptions_table(context, exceptions, refresh)
        if update:
            context.page.update()

    def add(_: ft.ControlEvent | None = None) -> None:
        _open_client_exception_editor(context, None, lambda: refresh(True))

    root = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Назад", on_click=lambda _: on_back()),
                    ft.Column(
                        controls=[
                            ft.Text('Клиенты "Исключения"', size=30, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                            ft.Text(
                                "Только клиенты, для которых ставка реферала вводится вручную в заданном периоде.",
                                color=ui_theme.MUTED,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ui_theme.primary_button("Добавить исключение", icon=ft.Icons.ADD, on_click=add),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            status,
            table_holder,
        ],
        expand=True,
        spacing=14,
    )
    refresh(update=False)
    return root


def _client_exceptions_table(context, exceptions: list[ClientRateException], refresh) -> ft.Control:
    if not exceptions:
        return ui_theme.panel(
            ft.Container(
                padding=60,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    controls=[
                        ft.Container(
                            width=58,
                            height=58,
                            border_radius=18,
                            bgcolor="#EFF6FF",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.PERSON_SEARCH_OUTLINED, size=30, color=ui_theme.PRIMARY),
                        ),
                        ft.Text("Исключений пока нет", size=18, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                        ft.Text(
                            "Добавьте клиента, если для него ставка реферала должна вводиться вручную.",
                            color=ui_theme.MUTED,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=9,
                ),
            ),
            expand=True,
        )

    header = ft.Container(
        padding=ft.Padding(14, 10, 14, 10),
        border_radius=12,
        bgcolor="#F8FBFF",
        border=ui_theme.border("#CFE0F5"),
        content=ft.Row(
            controls=[
                _table_header_text("Клиент", 230),
                _table_header_text("Комментарий", None),
                _table_header_text("Дата начала", 120),
                _table_header_text("Дата окончания", 130),
                ft.Container(width=88),
            ],
            spacing=10,
        ),
    )
    rows = [
        _client_exception_row(context, exception, refresh)
        for exception in exceptions
    ]
    return ui_theme.panel(
        ft.Column(
            controls=[
                header,
                ft.Column(controls=rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            ],
            spacing=8,
            expand=True,
        ),
        padding=8,
        expand=True,
    )


def _table_header_text(label: str, width: int | None) -> ft.Control:
    return ft.Text(
        label,
        width=width,
        expand=width is None,
        size=11,
        weight=ft.FontWeight.W_800,
        color=ui_theme.MUTED,
    )


def _exception_date_to_text(value: str | None) -> str:
    return "Бессрочно" if not value else _format_short_date(value)


def _client_exception_row(context, exception: ClientRateException, refresh) -> ft.Control:
    def edit(_: ft.ControlEvent | None = None) -> None:
        _open_client_exception_editor(context, exception, lambda: refresh(True))

    def delete(_: ft.ControlEvent | None = None) -> None:
        context.client_rate_exceptions_repository.delete_by_client_name(exception.client_name)
        refresh(True)

    return ft.Container(
        padding=ft.Padding(14, 12, 14, 12),
        border_radius=14,
        bgcolor="#FFFFFF",
        border=ui_theme.border("#E2E8F0"),
        shadow=ft.BoxShadow(blur_radius=16, color="#0F172A0D", offset=ft.Offset(0, 5)),
        content=ft.Row(
            controls=[
                ft.Text(exception.client_name, width=230, size=13, weight=ft.FontWeight.W_800, color=ui_theme.TEXT),
                ft.Text(exception.note, expand=True, size=13, color=ui_theme.TEXT, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(_format_short_date(exception.date_from), width=120, size=13, color=ui_theme.TEXT),
                ft.Text(_exception_date_to_text(exception.date_to), width=130, size=13, color=ui_theme.TEXT),
                ft.Row(
                    width=88,
                    spacing=4,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Редактировать", icon_color=ui_theme.PRIMARY, on_click=edit),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Удалить", icon_color=ui_theme.DANGER, on_click=delete),
                    ],
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _open_client_exception_editor(
    context,
    exception: ClientRateException | None,
    on_saved,
) -> None:
    clients = context.deals_repository.distinct_values("client_name")
    current_client = exception.client_name if exception else ""
    if current_client and current_client not in clients:
        clients.append(current_client)
    client = ft.Dropdown(
        label="Клиент",
        value=current_client or None,
        options=[ft.dropdown.Option(key=item, text=item) for item in sorted(clients, key=lambda value: value.casefold())],
        editable=True,
        enable_filter=True,
        enable_search=True,
        menu_height=320,
    )
    note = ft.TextField(label="Комментарий", value=exception.note if exception else "", multiline=True, min_lines=2)
    date_from = ft.TextField(
        label="Дата начала",
        value="" if exception is None else _format_short_date(exception.date_from),
        hint_text="дд.мм.гг",
        suffix=_calendar_icon_button(None),
        expand=True,
    )
    date_to = ft.TextField(
        label="Дата окончания",
        value="" if exception is None or not exception.date_to else _format_short_date(exception.date_to),
        hint_text="пусто = бессрочно",
        suffix=_calendar_icon_button(None),
        expand=True,
    )
    date_from.suffix.on_click = lambda _: _open_date_picker(context, date_from, storage_format=False)
    date_to.suffix.on_click = lambda _: _open_date_picker(context, date_to, storage_format=False)
    error = ft.Text("", color=ui_theme.DANGER, visible=False)
    for field in (note, date_from, date_to):
        _style_field(field)
    client.filled = True
    client.fill_color = "#F8FAFC"
    client.border_color = "#D8E2F0"
    client.focused_border_color = ui_theme.PRIMARY
    client.border_radius = 8

    def save(_: ft.ControlEvent | None = None) -> None:
        try:
            client_name = str(client.value or "").strip()
            note_value = str(note.value or "").strip()
            parsed_from = _parse_optional_date(str(date_from.value or ""))
            to_text = str(date_to.value or "").strip()
            parsed_to = _parse_optional_date(to_text) if to_text else None
            if not client_name:
                raise ValueError("Выберите клиента.")
            if not note_value:
                raise ValueError("Заполните комментарий.")
            if not parsed_from:
                raise ValueError("Заполните дату начала в формате дд.мм.гг.")
            if parsed_to and parsed_from > parsed_to:
                raise ValueError("Дата начала не может быть позже даты окончания.")
            if exception and exception.client_name.casefold() != client_name.casefold():
                context.client_rate_exceptions_repository.delete_by_client_name(exception.client_name)
            context.client_rate_exceptions_repository.save(
                ClientRateException(
                    client_name=client_name,
                    note=note_value,
                    date_from=parsed_from,
                    date_to=parsed_to,
                )
            )
            context.page.pop_dialog()
            on_saved()
        except Exception as exc:
            error.value = str(exc)
            error.visible = True
            context.page.update(error)

    context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=ui_theme.SURFACE,
            barrier_color="#0F172A66",
            title=ft.Text("Исключение клиента" if exception else "Новое исключение"),
            content=ft.Container(
                width=560,
                content=ft.Column(
                    controls=[
                        client,
                        note,
                        ft.Row(controls=[date_from, date_to], spacing=10, expand=True),
                        error,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
                ui_theme.primary_button("Сохранить", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _grid_content(context, referrals, on_click, on_delete) -> ft.Control:
    if not referrals:
        return ui_theme.panel(
            ft.Container(
                padding=50,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=36, color=ui_theme.MUTED),
                        ft.Text("Рефералы не найдены", color=ui_theme.MUTED),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
            ),
            expand=True,
        )
    return ft.Column(
        controls=[
            ft.ResponsiveRow(
                controls=[referral_card(referral, on_click, on_delete) for referral in referrals],
                spacing=14,
                run_spacing=14,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def _open_add_referral_dialog(context, on_saved) -> None:
    name = ft.TextField(label="Название")
    code = ft.TextField(label="Код")
    description = ft.TextField(label="Описание", multiline=True)
    logo_path = ft.TextField(label="Logo path")
    active = ft.Checkbox(label="Активен", value=True)
    for field in (name, code, description, logo_path):
        _style_field(field)

    def save(_: ft.ControlEvent) -> None:
        try:
            context.referrals_service.save(
                name=name.value or "",
                code=code.value or name.value or "",
                description=description.value,
                logo_path=logo_path.value,
                is_active=bool(active.value),
            )
            context.page.pop_dialog()
            on_saved()
        except Exception as exc:
            context.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Добавить реферала"),
        content=ft.Container(
            width=560,
            content=ft.Column([name, code, description, logo_path, active], spacing=12),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: context.page.pop_dialog()),
            ui_theme.primary_button("Сохранить", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
        ],
    )
    context.page.show_dialog(dialog)


def _open_delete_referral_dialog(context, referral, on_deleted) -> None:
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
                ft.Text("Вы точно уверены?", weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=560,
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Это приведет к каскадному удалению всех условий реферала «{referral.name}».",
                        color=ui_theme.TEXT,
                    ),
                    ft.Text(
                        "Реферал также не будет автоматически создан заново из реестра сделок.",
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

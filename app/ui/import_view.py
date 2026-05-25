"""Excel import screen."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import flet as ft

from app.services.import_excel_service import ImportSourceSelectionRequired
from app.ui import theme as ui_theme


def create_import_view(context) -> ft.Control:
    """Create Power Query-safe Excel import workflow."""
    state: dict[str, object] = {"file_path": None, "last_batch_id": None, "loading": False, "loader_started_at": 0.0}
    status = ft.Text(
        "Выберите .xlsx/.xlsm файл. Power Query не обновляется, читается только сохраненный результат.",
        color=ui_theme.MUTED,
    )
    result_panel = ft.Column(spacing=8)
    errors_container = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
    errors_panel = ft.Container(
        visible=False,
        expand=True,
        padding=16,
        border_radius=10,
        bgcolor=ui_theme.SURFACE,
        border=ui_theme.border(),
        shadow=ui_theme.shadow(),
        content=errors_container,
    )
    sheet_dropdown = ft.Dropdown(label="Лист для импорта", visible=False, width=320)
    import_selected_button = ui_theme.primary_button(
        "Импортировать выбранный лист",
        icon=ft.Icons.TABLE_VIEW_OUTLINED,
        visible=False,
    )

    loader_text = ft.Text(
        "\u0421\u043f\u0430\u0441\u0438\u0431\u043e, \u0412\u0430\u0434\u0438\u043c",
        size=22,
        weight=ft.FontWeight.W_800,
        color=ui_theme.PRIMARY,
        opacity=0.0,
        offset=ft.Offset(0, 0.08),
        animate_opacity=ft.Animation(650, ft.AnimationCurve.EASE_IN_OUT),
        animate_offset=ft.Animation(650, ft.AnimationCurve.EASE_IN_OUT),
    )
    loader_cloud = ft.Container(
        width=340,
        padding=ft.Padding(26, 24, 26, 22),
        border_radius=34,
        bgcolor="#FDFEFF",
        border=ui_theme.border("#CFE0F8"),
        shadow=ft.BoxShadow(blur_radius=28, color="#DBEAFE", offset=ft.Offset(0, 14)),
        opacity=0.0,
        scale=ft.Scale(0.96),
        animate_opacity=ft.Animation(520, ft.AnimationCurve.EASE_IN_OUT),
        animate_scale=ft.Animation(520, ft.AnimationCurve.EASE_OUT),
        content=ft.Column(
            controls=[
                ft.Container(
                    width=58,
                    height=58,
                    border_radius=22,
                    bgcolor="#EAF2FF",
                    alignment=ft.Alignment.CENTER,
                    content=ft.ProgressRing(width=34, height=34, stroke_width=3, color=ui_theme.PRIMARY),
                ),
                loader_text,
                ft.Text(
                    "\u0427\u0438\u0442\u0430\u0435\u043c Excel \u0438 "
                    "\u0441\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u043c "
                    "\u0441\u0442\u0440\u043e\u043a\u0438 \u0432 SQLite",
                    size=12,
                    color=ui_theme.MUTED,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            tight=True,
        ),
    )
    loading_overlay = ft.Container(
        visible=False,
        left=0,
        top=0,
        right=0,
        bottom=0,
        bgcolor=None,
        alignment=ft.Alignment.CENTER,
        content=loader_cloud,
    )

    async def animate_loader_text() -> None:
        visible = False
        while state.get("loading"):
            visible = not visible
            loader_text.opacity = 1.0 if visible else 0.45
            loader_text.offset = ft.Offset(0, -0.05 if visible else 0.08)
            try:
                context.page.update(loader_text)
            except Exception:
                return
            await asyncio.sleep(0.7)

    def show_loader() -> None:
        state["loading"] = True
        state["loader_started_at"] = time.monotonic()
        loading_overlay.visible = True
        loader_cloud.opacity = 1.0
        loader_cloud.scale = ft.Scale(1.0)
        loader_text.opacity = 1.0
        loader_text.offset = ft.Offset(0, -0.05)
        context.page.update()
        context.page.run_task(animate_loader_text)

    async def hide_loader() -> None:
        elapsed = time.monotonic() - float(state.get("loader_started_at") or 0.0)
        remaining = 5.0 - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        state["loading"] = False
        loader_text.opacity = 0.0
        loader_text.offset = ft.Offset(0, -0.16)
        loader_cloud.opacity = 0.0
        loader_cloud.scale = ft.Scale(0.98)
        context.page.update()
        await asyncio.sleep(0.65)
        loading_overlay.visible = False
        context.page.update()

    async def run_import(file_path: str, sheet_name: str | None = None):
        def import_sync():
            with context.operation_tracker.track():
                return context.import_excel_service.import_file(file_path, sheet_name)

        return await asyncio.to_thread(import_sync)

    def show_result(result) -> None:
        context.referrals_service.sync_from_deals()
        state["last_batch_id"] = result.import_batch_id
        status.value = "Импорт завершен." if result.status != "failed" else "Импорт не выполнен."
        status.color = ui_theme.MUTED if result.status != "failed" else ft.Colors.RED_500
        result_panel.controls.clear()
        result_panel.controls.extend(
            [
                _result_row("Файл", Path(result.source_file).name),
                _result_row("Лист", result.source_sheet or "-"),
                _result_row("Всего строк", str(result.rows_total)),
                _result_row("Успешно импортировано", str(result.rows_success)),
                _result_row("Строк с ошибками", str(result.rows_failed)),
                _result_row("Статус", result.status),
            ]
        )
        if result.error_message:
            result_panel.controls.append(ft.Text(result.error_message, color=ft.Colors.RED_500))

        _fill_errors(result.errors)
        errors_panel.visible = bool(result.errors)
        sheet_dropdown.visible = False
        import_selected_button.visible = False
        context.page.update()

    def _fill_errors(errors) -> None:
        errors_container.controls.clear()
        if not errors:
            errors_container.controls.append(ft.Text("Ошибок валидации нет.", color=ft.Colors.GREEN_600))
            return
        for error in errors[:300]:
            errors_container.controls.append(
                ft.Text(
                    f"Строка {error.row_number} / {error.field_name}: {error.message}",
                    color=ft.Colors.RED_500,
                    size=13,
                )
            )

    def show_sheet_choice(exc: ImportSourceSelectionRequired) -> None:
        state["file_path"] = exc.file_path
        status.value = "Таблица или лист 'All' не найдены. Выберите лист для импорта."
        status.color = ft.Colors.AMBER_700
        sheet_dropdown.options = [
            ft.dropdown.Option(key=sheet_name, text=sheet_name)
            for sheet_name in exc.available_sheets
        ]
        sheet_dropdown.value = exc.available_sheets[0] if exc.available_sheets else None
        sheet_dropdown.visible = True
        import_selected_button.visible = True
        result_panel.controls.clear()
        errors_panel.visible = False
        context.page.update()

    def show_error(message: str) -> None:
        status.value = message
        status.color = ft.Colors.RED_500
        context.page.update()

    file_picker = ft.FilePicker()

    async def pick_and_import(_: ft.ControlEvent) -> None:
        files = await file_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx", "xlsm"],
        )
        if not files:
            return
        file_path = files[0].path
        if not file_path:
            show_error("Путь к выбранному файлу недоступен.")
            return
        state["file_path"] = file_path
        show_loader()
        await asyncio.sleep(0.05)
        try:
            result = await run_import(file_path)
            show_result(result)
        except ImportSourceSelectionRequired as exc:
            show_sheet_choice(exc)
        except Exception as exc:
            show_error(str(exc))
        finally:
            await hide_loader()

    async def import_selected_sheet(_: ft.ControlEvent) -> None:
        file_path = state.get("file_path")
        if not file_path or not sheet_dropdown.value:
            show_error("Выберите файл и лист для импорта.")
            return
        show_loader()
        await asyncio.sleep(0.05)
        try:
            result = await run_import(str(file_path), sheet_dropdown.value)
            show_result(result)
        except Exception as exc:
            show_error(str(exc))
        finally:
            await hide_loader()

    def show_persisted_errors(_: ft.ControlEvent) -> None:
        batch_id = state.get("last_batch_id")
        if not batch_id:
            errors_panel.visible = True
            context.page.update()
            return
        with context.operation_tracker.track():
            records = context.import_batches_repository.list_errors(int(batch_id), limit=300)
        errors_container.controls.clear()
        if not records:
            errors_container.controls.append(ft.Text("Ошибок валидации нет.", color=ft.Colors.GREEN_600))
        for record in records:
            errors_container.controls.append(
                ft.Text(
                    f"Строка {record.source_row_number} / {record.field_name}: {record.error_message}",
                    color=ft.Colors.RED_500,
                    size=13,
                )
            )
        errors_panel.visible = True
        context.page.update()

    import_selected_button.on_click = import_selected_sheet

    content = ft.Column(
        controls=[
            ft.Text("Import Excel", size=28, weight=ft.FontWeight.W_700),
            ui_theme.panel(
                ft.Column(
                    controls=[
                        status,
                        ft.Row(
                            controls=[
                                ui_theme.primary_button(
                                    "Выбрать файл",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    on_click=pick_and_import,
                                ),
                                ft.OutlinedButton(
                                    "Показать ошибки",
                                    icon=ft.Icons.ERROR_OUTLINE,
                                    on_click=show_persisted_errors,
                                ),
                                ft.OutlinedButton(
                                    "Открыть реестр сделок",
                                    icon=ft.Icons.TABLE_ROWS_OUTLINED,
                                    on_click=lambda _: context.navigate_to(0),
                                ),
                            ],
                            wrap=True,
                        ),
                        ft.Row([sheet_dropdown, import_selected_button], wrap=True),
                    ],
                    spacing=16,
                ),
                padding=24,
            ),
            ui_theme.panel(result_panel),
            errors_panel,
        ],
        expand=True,
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
    )
    return ft.Stack(
        controls=[content, loading_overlay],
        expand=True,
    )


def _result_row(label: str, value: str) -> ft.Control:
    return ft.Row(
        controls=[
            ft.Text(label, width=180, color=ui_theme.MUTED),
            ft.Text(value, selectable=True),
        ],
        spacing=8,
    )

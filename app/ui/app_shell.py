"""Main Flet shell with sidebar navigation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import sys

import flet as ft

from app.repositories.deals_repository import DealsRepository
from app.repositories.client_rate_exceptions_repository import ClientRateExceptionsRepository
from app.repositories.import_batches_repository import ImportBatchesRepository
from app.repositories.rate_conditions_repository import RateConditionsRepository
from app.repositories.rates_repository import RatesRepository
from app.repositories.referrals_repository import ReferralsRepository
from app.repositories.rules_repository import RulesRepository
from app.database.connection import get_connection
from app.services.import_excel_service import ImportExcelService
from app.services.analytics_server_service import AnalyticsServerService
from app.services.operation_tracker import OperationTracker
from app.services.pnl_service import PnlService
from app.services.rate_conditions_service import RateConditionsService
from app.services.rate_conditions_excel_service import RateConditionsExcelService
from app.services.rate_conditions_validation_service import RateConditionsValidationService
from app.services.rate_rules_engine import RateRulesEngine
from app.services.rates_service import RatesService
from app.services.referrals_service import ReferralsService
from app.ui.analytics_view import create_analytics_view
from app.ui.components.mlg_brand_animation import MlgBrandAnimation
from app.ui.deals_view import create_deals_view
from app.ui.import_view import create_import_view
from app.ui.rates.referrals_grid_view import create_referrals_grid_view
from app.ui.rates_view import create_rates_view
from app.ui import theme as ui_theme
from app.database.lock import DatabaseLockError


@dataclass(slots=True)
class AppContext:
    """Shared dependencies for UI views."""

    page: ft.Page
    deals_repository: DealsRepository
    rates_repository: RatesRepository
    rules_repository: RulesRepository
    referrals_repository: ReferralsRepository
    rate_conditions_repository: RateConditionsRepository
    rates_service: RatesService
    pnl_service: PnlService
    import_excel_service: ImportExcelService
    import_batches_repository: ImportBatchesRepository
    client_rate_exceptions_repository: ClientRateExceptionsRepository
    rate_rules_engine: RateRulesEngine
    referrals_service: ReferralsService
    rate_conditions_service: RateConditionsService
    rate_conditions_excel_service: RateConditionsExcelService
    analytics_server_service: AnalyticsServerService
    operation_tracker: OperationTracker
    navigate_to: Callable[[int], None]
    set_content: Callable[[ft.Control], None]
    set_shell_theme: Callable[[str], None]


class AppShell:
    """Application frame with persistent navigation."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        operation_tracker = OperationTracker()
        connection_factory = operation_tracker.wrap_connection_factory(get_connection)
        deals_repository = DealsRepository(connection_factory)
        rates_repository = RatesRepository(connection_factory)
        rules_repository = RulesRepository(connection_factory)
        referrals_repository = ReferralsRepository(connection_factory)
        rate_conditions_repository = RateConditionsRepository(connection_factory)
        client_rate_exceptions_repository = ClientRateExceptionsRepository(connection_factory)
        import_batches_repository = ImportBatchesRepository(connection_factory)
        rates_service = RatesService(rates_repository)
        analytics_server_service = AnalyticsServerService()
        rate_conditions_validation_service = RateConditionsValidationService(rate_conditions_repository)
        rate_conditions_service = RateConditionsService(
            rate_conditions_repository,
            rate_conditions_validation_service,
        )
        self.context = AppContext(
            page=page,
            deals_repository=deals_repository,
            rates_repository=rates_repository,
            rules_repository=rules_repository,
            referrals_repository=referrals_repository,
            rate_conditions_repository=rate_conditions_repository,
            rates_service=rates_service,
            pnl_service=PnlService(deals_repository, rates_service),
            import_excel_service=ImportExcelService(deals_repository, import_batches_repository),
            import_batches_repository=import_batches_repository,
            client_rate_exceptions_repository=client_rate_exceptions_repository,
            rate_rules_engine=RateRulesEngine(referrals_repository, rate_conditions_repository),
            referrals_service=ReferralsService(referrals_repository, deals_repository),
            rate_conditions_service=rate_conditions_service,
            rate_conditions_excel_service=RateConditionsExcelService(referrals_repository, rate_conditions_service),
            analytics_server_service=analytics_server_service,
            operation_tracker=operation_tracker,
            navigate_to=self._navigate_to,
            set_content=self._set_content,
            set_shell_theme=self._set_shell_theme,
        )
        self.content = ft.Container(
            expand=True,
            padding=24,
            bgcolor=ui_theme.APP_BG,
            animate_opacity=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )
        self._selected_nav_index = 0
        self._nav_items: list[ft.Container] = []
        self._transition_token = 0
        self._shell_theme = "default"
        self.sidebar: ft.Container | None = None
        self._brand_card: ft.Container | None = None
        self.navigation = self._create_navigation()
        self._mlg_brand_animation = MlgBrandAnimation(page=page, image_src="assets/app/by_logo_mlg.png")
        self._close_overlay: ft.Control | None = None
        self._close_logo: ft.Container | None = None
        self._brand_overlay: ft.Control | None = None
        self._brand_logo: ft.Container | None = None
        self._brand_animating = False
        self._closing = False

    def build(self) -> ft.Control:
        """Build the full app layout."""
        self._configure_window_close()
        self.content.content = create_deals_view(self.context)
        self.sidebar = ft.Container(
            width=118,
            padding=ft.Padding(14, 18, 14, 18),
            bgcolor="#FFFFFF",
            border=ft.Border(right=ft.BorderSide(1, "#DBEAFE")),
            shadow=None,
            animate=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
            content=self.navigation,
        )
        self._apply_sidebar_theme(update=False)
        return ft.Row(
            controls=[
                self.sidebar,
                self.content,
            ],
            expand=True,
            spacing=0,
        )

    def _create_navigation_legacy(self) -> ft.NavigationRail:
        return ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=88,
            min_extended_width=180,
            group_alignment=-0.9,
            bgcolor=ui_theme.SURFACE,
            indicator_color=ui_theme.PRIMARY_TINT,
            use_indicator=True,
            selected_label_text_style=ft.TextStyle(color=ui_theme.PRIMARY, weight=ft.FontWeight.W_700),
            unselected_label_text_style=ft.TextStyle(color=ui_theme.MUTED),
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.TABLE_ROWS_OUTLINED, selected_icon=ft.Icons.TABLE_ROWS, label="\u0421\u0434\u0435\u043b\u043a\u0438"),
                ft.NavigationRailDestination(icon=ft.Icons.UPLOAD_FILE_OUTLINED, selected_icon=ft.Icons.UPLOAD_FILE, label="\u0412\u044b\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0438\u0437 \u041c\u041f"),
                ft.NavigationRailDestination(icon=ft.Icons.CURRENCY_EXCHANGE_OUTLINED, selected_icon=ft.Icons.CURRENCY_EXCHANGE, label="\u041a\u0443\u0440\u0441\u044b"),
                ft.NavigationRailDestination(icon=ft.Icons.INSIGHTS_OUTLINED, selected_icon=ft.Icons.INSIGHTS, label="\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430"),
                ft.NavigationRailDestination(icon=ft.Icons.RULE_FOLDER_OUTLINED, selected_icon=ft.Icons.RULE_FOLDER, label="Ставки"),
            ],
            on_change=lambda event: self._show_view(event.control.selected_index),
        )

    def _create_navigation(self) -> ft.Column:
        self._nav_items = [
            self._nav_item(0, "Сделки", ft.Icons.TABLE_ROWS_OUTLINED, ft.Icons.TABLE_ROWS, ("#3B82F6", "#2563EB")),
            self._nav_item(1, "Выгрузить", ft.Icons.UPLOAD_FILE_OUTLINED, ft.Icons.UPLOAD_FILE, ("#06B6D4", "#2563EB")),
            self._nav_item(2, "Курсы", ft.Icons.CURRENCY_EXCHANGE_OUTLINED, ft.Icons.CURRENCY_EXCHANGE, ("#10B981", "#2563EB")),
            self._nav_item(3, "Аналитика", ft.Icons.INSIGHTS_OUTLINED, ft.Icons.INSIGHTS, ("#8B5CF6", "#2563EB")),
            self._nav_item(4, "Ставки", ft.Icons.RULE_FOLDER_OUTLINED, ft.Icons.RULE_FOLDER, ("#F59E0B", "#2563EB")),
        ]
        self._update_navigation(update=False)
        self._brand_card = ft.Container(
            width=86,
            height=92,
            border_radius=24,
            alignment=ft.Alignment.CENTER,
            bgcolor="#FFFFFF",
            border=ui_theme.border("#DBEAFE"),
            shadow=ft.BoxShadow(blur_radius=24, color="#2563EB1F", offset=ft.Offset(0, 10)),
            ink=True,
            animate=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _: self.page.run_task(self._mlg_brand_animation.play),
            content=ft.Column(
                controls=[
                    ft.Text("By", size=11, weight=ft.FontWeight.W_800, color=ui_theme.MUTED),
                    ft.Container(
                        width=66,
                        height=58,
                        border_radius=18,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        bgcolor="#F8FAFC",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Image(
                            src="assets/app/by_logo.png",
                            width=64,
                            height=56,
                            fit="contain",
                        ),
                    ),
                ],
                spacing=4,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        return ft.Column(
            controls=[
                self._brand_card,
                ft.Container(height=4),
                *self._nav_items,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

    def _nav_item(
        self,
        index: int,
        label: str,
        icon: str,
        selected_icon: str,
        colors: tuple[str, str],
    ) -> ft.Container:
        icon_holder = ft.Container(width=48, height=48, border_radius=16, alignment=ft.Alignment.CENTER)
        text = ft.Text(label, size=11, text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        return ft.Container(
            data={
                "index": index,
                "icon": icon,
                "selected_icon": selected_icon,
                "colors": colors,
                "icon_holder": icon_holder,
                "label": text,
            },
            width=86,
            padding=ft.Padding(6, 7, 6, 7),
            border_radius=22,
            ink=True,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _: self._show_view(index),
            on_hover=lambda event: self._handle_nav_hover(event, index),
            content=ft.Column(
                controls=[icon_holder, text],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
                tight=True,
            ),
        )

    def _handle_nav_hover(self, event: ft.ControlEvent, index: int) -> None:
        item = self._nav_items[index]
        if index == self._selected_nav_index:
            return
        is_pnl = self._shell_theme == "pnl"
        item.bgcolor = ("#241706" if is_pnl else "#F8FAFC") if event.data == "true" else None
        item.scale = ft.Scale(1.05 if is_pnl else 1.03) if event.data == "true" else ft.Scale(1.0)
        self.page.update(item)

    def _update_navigation(self, update: bool = True) -> None:
        is_pnl = self._shell_theme == "pnl"
        for item in self._nav_items:
            data = item.data
            index = int(data["index"])
            selected = index == self._selected_nav_index
            icon_holder: ft.Container = data["icon_holder"]
            label: ft.Text = data["label"]
            color_start, color_end = data["colors"]
            if is_pnl:
                color_start, color_end = "#F7D982", "#B8791F"
                item.bgcolor = "#241706" if selected else None
                item.shadow = (
                    ft.BoxShadow(blur_radius=28, color="#F4C95D36", offset=ft.Offset(0, 12))
                    if selected
                    else None
                )
            else:
                item.bgcolor = "#F8FAFC" if selected else None
                item.shadow = ft.BoxShadow(blur_radius=22, color="#0F172A12", offset=ft.Offset(0, 10)) if selected else None
            item.scale = ft.Scale(1.0)
            icon_holder.gradient = ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[color_start, color_end, "#5B3510"] if is_pnl else [color_start, color_end],
            ) if selected else None
            icon_holder.bgcolor = None if selected else ("#171009" if is_pnl else "#F8FAFC")
            icon_holder.border = ui_theme.border(
                "#F4D58A" if selected and is_pnl else "#6E4A18" if is_pnl else "#DBEAFE" if selected else "#E2E8F0"
            )
            icon_holder.shadow = (
                ft.BoxShadow(
                    blur_radius=24 if is_pnl else 18,
                    color=("#F4C95D52" if is_pnl else f"{color_end}40"),
                    offset=ft.Offset(0, 9 if is_pnl else 8),
                )
                if selected
                else None
            )
            icon_holder.content = ft.Icon(
                data["selected_icon"] if (selected or is_pnl) else data["icon"],
                color="#130B04" if selected and is_pnl else "#FFFFFF" if selected else "#E8C36B" if is_pnl else ui_theme.MUTED,
                size=27 if selected and is_pnl else 25 if is_pnl else 24,
            )
            label.color = "#F4D58A" if selected and is_pnl else "#D9B45B" if is_pnl else ui_theme.TEXT if selected else ui_theme.MUTED
            label.weight = ft.FontWeight.W_800 if selected else ft.FontWeight.W_600
        if update:
            self.page.update(*self._nav_items)

    def _set_shell_theme(self, mode: str) -> None:
        next_theme = "pnl" if mode == "pnl" else "default"
        if next_theme == self._shell_theme:
            return
        self._shell_theme = next_theme
        self._apply_sidebar_theme(update=False)
        self._update_navigation(update=False)
        controls: list[ft.Control] = [*self._nav_items]
        if self.sidebar is not None:
            controls.append(self.sidebar)
        if self._brand_card is not None:
            controls.append(self._brand_card)
        if controls:
            self.page.update(*controls)

    def _apply_sidebar_theme(self, update: bool = True) -> None:
        is_pnl = self._shell_theme == "pnl"
        if self.sidebar is not None:
            self.sidebar.bgcolor = "#0E0904" if is_pnl else "#FFFFFF"
            self.sidebar.border = ft.Border(right=ft.BorderSide(1, "#B88A35" if is_pnl else "#DBEAFE"))
            self.sidebar.shadow = (
                ft.BoxShadow(blur_radius=34, color="#D6A84F24", offset=ft.Offset(8, 0))
                if is_pnl
                else None
            )
        if self._brand_card is not None:
            self._brand_card.bgcolor = "#171009" if is_pnl else "#FFFFFF"
            self._brand_card.border = ui_theme.border("#B88A35" if is_pnl else "#DBEAFE")
            self._brand_card.shadow = ft.BoxShadow(
                blur_radius=30 if is_pnl else 24,
                color="#F4C95D33" if is_pnl else "#2563EB1F",
                offset=ft.Offset(0, 12 if is_pnl else 10),
            )
            brand_column = self._brand_card.content
            if isinstance(brand_column, ft.Column) and brand_column.controls:
                brand_label = brand_column.controls[0]
                logo_holder = brand_column.controls[1] if len(brand_column.controls) > 1 else None
                if isinstance(brand_label, ft.Text):
                    brand_label.color = "#F4D58A" if is_pnl else ui_theme.MUTED
                if isinstance(logo_holder, ft.Container):
                    logo_holder.bgcolor = "#100B07" if is_pnl else "#F8FAFC"
                    logo_holder.border = ui_theme.border("#6E4A18") if is_pnl else None
        if update:
            controls = [control for control in (self.sidebar, self._brand_card) if control is not None]
            if controls:
                self.page.update(*controls)

    def _navigate_to(self, index: int) -> None:
        self._show_view(index)

    def _show_view(self, index: int) -> None:
        if index == self._selected_nav_index and self.content.content is not None:
            return
        self.page.run_task(self._transition_to_view, index)

    async def _transition_to_view(self, index: int) -> None:
        self._transition_token += 1
        token = self._transition_token
        self._selected_nav_index = index
        if index != 0:
            self._set_shell_theme("default")
        self._update_navigation()
        self.content.opacity = 0.35
        self.content.offset = ft.Offset(0.025, 0)
        self.page.update(self.content)
        await asyncio.sleep(0.07)
        if token != self._transition_token:
            return
        views = [
            create_deals_view,
            create_import_view,
            create_rates_view,
            create_analytics_view,
            create_referrals_grid_view,
        ]
        self.content.content = views[index](self.context)
        self.content.offset = ft.Offset(0, 0)
        self.content.opacity = 1
        self.page.update(self.content)

    def _set_content(self, control: ft.Control) -> None:
        self.content.content = control
        self.page.update()

    async def _show_brand_animation(self) -> None:
        if self._brand_animating:
            return
        self._brand_animating = True
        overlay = self._build_brand_overlay()
        self._brand_overlay = overlay
        self.page.overlay.append(overlay)
        self.page.update()
        await asyncio.sleep(0.08)
        try:
            for scale, opacity, delay in (
                (1.02, 1.0, 0.34),
                (1.08, 1.0, 0.44),
                (1.04, 0.98, 0.34),
                (1.11, 1.0, 0.44),
                (1.06, 1.0, 0.36),
                (1.0, 1.0, 0.38),
            ):
                if self._brand_logo is None:
                    break
                self._brand_logo.scale = ft.Scale(scale)
                self._brand_logo.opacity = opacity
                self.page.update(self._brand_logo)
                await asyncio.sleep(delay)
            await asyncio.sleep(0.55)
            overlay.opacity = 0
            self.page.update(overlay)
            await asyncio.sleep(0.28)
            if overlay in self.page.overlay:
                self.page.overlay.remove(overlay)
                self.page.update()
        finally:
            self._brand_overlay = None
            self._brand_logo = None
            self._brand_animating = False

    def _build_brand_overlay(self) -> ft.Control:
        self._brand_logo = ft.Container(
            width=390,
            height=390,
            border_radius=44,
            alignment=ft.Alignment.CENTER,
            bgcolor="#FFFFFFF2",
            opacity=0.94,
            scale=ft.Scale(0.88),
            animate_scale=ft.Animation(420, ft.AnimationCurve.EASE_IN_OUT),
            animate_opacity=ft.Animation(420, ft.AnimationCurve.EASE_IN_OUT),
            border=ui_theme.border("#DBEAFE"),
            shadow=ft.BoxShadow(blur_radius=72, color="#2563EB33", offset=ft.Offset(0, 26)),
            content=ft.Image(
                src="assets/app/by_logo.png",
                width=330,
                height=330,
                fit="contain",
            ),
        )
        return ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            expand=True,
            opacity=1,
            animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
            bgcolor="#F8FBFFEE",
            alignment=ft.Alignment.CENTER,
            content=ft.Stack(
                controls=[
                    ft.Container(
                        width=760,
                        height=520,
                        border_radius=260,
                        gradient=ft.RadialGradient(
                            center=ft.Alignment.CENTER,
                            radius=0.72,
                            colors=["#BFDBFECC", "#E0F2FE80", "#FFFFFF00"],
                        ),
                    ),
                    ft.Container(
                        width=500,
                        height=500,
                        border_radius=250,
                        border=ft.Border(
                            left=ft.BorderSide(1, "#93C5FD88"),
                            top=ft.BorderSide(1, "#93C5FD88"),
                            right=ft.BorderSide(1, "#93C5FD88"),
                            bottom=ft.BorderSide(1, "#93C5FD88"),
                        ),
                    ),
                    ft.Container(
                        width=610,
                        height=610,
                        border_radius=305,
                        border=ft.Border(
                            left=ft.BorderSide(1, "#DBEAFE80"),
                            top=ft.BorderSide(1, "#DBEAFE80"),
                            right=ft.BorderSide(1, "#DBEAFE80"),
                            bottom=ft.BorderSide(1, "#DBEAFE80"),
                        ),
                    ),
                    self._brand_logo,
                    ft.Container(
                        bottom=76,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Container(
                            padding=ft.Padding(16, 8, 16, 8),
                            border_radius=999,
                            bgcolor="#FFFFFFCC",
                            border=ui_theme.border("#DBEAFE"),
                            shadow=ft.BoxShadow(blur_radius=18, color="#2563EB1F", offset=ft.Offset(0, 8)),
                            content=ft.Text(
                                "By Vadim",
                                size=16,
                                weight=ft.FontWeight.W_800,
                                color=ui_theme.PRIMARY,
                            ),
                        ),
                    ),
                ],
                alignment=ft.Alignment.CENTER,
                width=660,
                height=660,
            ),
        )

    def _configure_window_close(self) -> None:
        """Intercept app close and show a graceful shutdown overlay."""
        if not hasattr(self.page, "window"):
            return
        self.page.window.prevent_close = True
        self.page.window.on_event = self._handle_window_event

    def _handle_window_event(self, event: ft.WindowEvent) -> None:
        if event.type != ft.WindowEventType.CLOSE or self._closing:
            return
        self._closing = True
        self._show_close_overlay()
        self.page.run_task(self._close_when_idle)

    def _show_close_overlay(self) -> None:
        overlay = self._build_close_overlay()
        self._close_overlay = overlay
        self.page.overlay.append(overlay)
        self.page.update()

    def _build_close_overlay(self) -> ft.Control:
        self._close_logo = ft.Container(
            width=68,
            height=68,
            border_radius=22,
            bgcolor="#FFFFFF",
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=28, color="#0F172A24", offset=ft.Offset(0, 12)),
            animate_rotation=ft.Animation(220, ft.AnimationCurve.LINEAR),
            content=ft.Image(
                src="assets/app/closing_logo.png",
                width=50,
                height=50,
                fit="contain",
            ),
        )
        return ft.Container(
            data="app_close_overlay",
            left=0,
            top=0,
            right=0,
            bottom=0,
            expand=True,
            bgcolor="#020617CC",
            alignment=ft.Alignment.CENTER,
            content=ft.Container(
                width=360,
                padding=ft.Padding(26, 28, 26, 26),
                border_radius=24,
                bgcolor="#FFFFFF",
                border=ui_theme.border("#DBEAFE"),
                shadow=ft.BoxShadow(blur_radius=42, color="#02061740", offset=ft.Offset(0, 22)),
                content=ft.Column(
                    controls=[
                        ft.Stack(
                            controls=[
                                ft.ProgressRing(width=88, height=88, stroke_width=3, color=ui_theme.PRIMARY),
                                ft.Container(width=88, height=88, alignment=ft.Alignment.CENTER, content=self._close_logo),
                            ],
                            width=88,
                            height=88,
                        ),
                        ft.Text("Завершаем работу", size=22, weight=ft.FontWeight.W_700, color=ui_theme.TEXT),
                        ft.Text(
                            "Дождитесь окончания активных запросов. Приложение закроется автоматически.",
                            size=13,
                            color=ui_theme.MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    tight=True,
                ),
            ),
        )

    async def _close_when_idle(self) -> None:
        self.page.run_task(self._spin_close_logo)
        try:
            await self.context.operation_tracker.wait_idle(max_wait_seconds=4.0)
            self.context.analytics_server_service.stop()
            self._closing = False
            await asyncio.sleep(0.08)
            self.page.window.prevent_close = False
            try:
                await asyncio.wait_for(self.page.window.destroy(), timeout=1.2)
            except TimeoutError:
                pass
        except RuntimeError as exc:
            if "Session closed" not in str(exc):
                raise
        finally:
            self.context.analytics_server_service.stop()
            self._closing = False
            os._exit(0)

    async def _spin_close_logo(self) -> None:
        angle = 0.0
        while self._closing and self._close_logo is not None:
            angle += 0.18
            self._close_logo.rotate = ft.Rotate(angle=angle)
            try:
                self.page.update(self._close_logo)
            except Exception:
                return
            await asyncio.sleep(0.04)


def run_app() -> None:
    """Run the Flet desktop app."""

    def target(page: ft.Page) -> None:
        _install_asyncio_close_exception_filter()
        page.title = "Finance PnL Analytics"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ui_theme.app_theme()
        page.bgcolor = ui_theme.APP_BG
        page.window_min_width = 1100
        page.window_min_height = 720
        page.padding = 0
        shell = AppShell(page)
        page.add(shell.build())

    ft.app(target=target, assets_dir=str(_assets_root()))


def run_lock_error_app(error: DatabaseLockError) -> None:
    """Show a small blocking window when the local database is already in use."""

    def target(page: ft.Page) -> None:
        _install_asyncio_close_exception_filter()

        async def close_window() -> None:
            await page.window.destroy()

        page.title = "Finance PnL Analytics"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ui_theme.app_theme()
        page.bgcolor = "#EEF4FF"
        page.window_width = 560
        page.window_height = 420
        page.window_resizable = False
        page.padding = 0
        page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(28, 28, 28, 28),
                content=ft.Container(
                    width=480,
                    padding=ft.Padding(28, 28, 28, 26),
                    border_radius=28,
                    bgcolor="#FFFFFF",
                    border=ui_theme.border("#DBEAFE"),
                    shadow=ft.BoxShadow(blur_radius=36, color="#0F172A24", offset=ft.Offset(0, 18)),
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                width=64,
                                height=64,
                                border_radius=22,
                                bgcolor="#EFF6FF",
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCK_OUTLINED, size=34, color=ui_theme.PRIMARY),
                            ),
                            ft.Text(
                                "База уже открыта",
                                size=26,
                                weight=ft.FontWeight.W_800,
                                color=ui_theme.TEXT,
                            ),
                            ft.Text(
                                "Другой экземпляр приложения уже работает с этой SQLite-базой. "
                                "Закройте его и запустите приложение снова.",
                                size=14,
                                color=ui_theme.MUTED,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(
                                padding=ft.Padding(14, 14, 14, 14),
                                border_radius=16,
                                bgcolor="#F8FAFC",
                                border=ui_theme.border("#E2E8F0"),
                                content=ft.Text(
                                    error.owner_info or str(error.lock_path),
                                    size=12,
                                    color="#475569",
                                    selectable=True,
                                ),
                            ),
                            ft.FilledButton(
                                "Закрыть",
                                icon=ft.Icons.CLOSE,
                                style=ft.ButtonStyle(
                                    bgcolor=ui_theme.PRIMARY,
                                    color="#FFFFFF",
                                    shape=ft.RoundedRectangleBorder(radius=14),
                                    padding=ft.Padding(22, 14, 22, 14),
                                ),
                                on_click=lambda _: page.run_task(close_window),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=16,
                        tight=True,
                    ),
                ),
            )
        )

    ft.app(target=target, assets_dir=str(_assets_root()))


def _install_asyncio_close_exception_filter() -> None:
    """Suppress expected Windows Proactor noise when Flet closes its transport."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return
    if getattr(loop, "_finance_pnl_close_filter", False):
        return

    previous_handler = loop.get_exception_handler()

    def handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exception = context.get("exception")
        handle = str(context.get("handle") or "")
        is_transport_close = "_ProactorBasePipeTransport._call_connection_lost" in handle
        is_connection_reset = isinstance(exception, ConnectionResetError) and getattr(exception, "winerror", None) == 10054
        if is_connection_reset and is_transport_close:
            return
        if previous_handler is not None:
            previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handle_exception)
    setattr(loop, "_finance_pnl_close_filter", True)


def _assets_root() -> Path:
    """Return app root for Flet static assets in source and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]

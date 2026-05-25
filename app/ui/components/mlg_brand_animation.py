"""Reusable fullscreen MLG-style brand animation for Flet."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import flet as ft


@dataclass(slots=True)
class MlgBrandAnimation:
    """Run a non-blocking fullscreen avatar animation."""

    page: ft.Page
    image_src: str
    _running: bool = False

    async def play(self) -> None:
        """Show the animation and remove it after it completes."""
        if self._running:
            return
        self._running = True
        scene = _MlgScene(self.image_src)
        overlay = scene.build()
        self.page.overlay.append(overlay)
        self.page.update()
        try:
            await asyncio.sleep(0.04)
            await scene.enter(self.page)
            await scene.reveal_labels(self.page)
            await scene.shake(self.page)
            await scene.exit(self.page)
            if overlay in self.page.overlay:
                self.page.overlay.remove(overlay)
                self.page.update()
        finally:
            self._running = False


class _MlgScene:
    """Internal controls and timeline for the animation."""

    def __init__(self, image_src: str) -> None:
        self.image_src = image_src
        self.overlay: ft.Container | None = None
        self.logo: ft.Container | None = None
        self.glow: ft.Container | None = None
        self.flash: ft.Container | None = None
        self.scanlines: ft.Container | None = None
        self.scene: ft.Stack | None = None
        self.glitch_cyan: ft.Container | None = None
        self.glitch_red: ft.Container | None = None
        self.labels: list[ft.Container] = []

    def build(self) -> ft.Container:
        self.glow = ft.Container(visible=False)
        self.logo = ft.Container(
            width=360,
            height=360,
            alignment=ft.Alignment.CENTER,
            opacity=0.0,
            bgcolor=None,
            scale=ft.Scale(0.28),
            offset=ft.Offset(-1.15, -0.52),
            rotate=ft.Rotate(angle=-0.10),
            animate_scale=ft.Animation(420, ft.AnimationCurve.EASE_OUT_BACK),
            animate_offset=ft.Animation(520, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
            animate_rotation=ft.Animation(105, ft.AnimationCurve.EASE_OUT),
            shadow=None,
            content=ft.Image(src=self.image_src, width=340, height=340, fit="contain"),
        )
        self.glitch_cyan = None
        self.glitch_red = None
        self.flash = None
        self.scanlines = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            opacity=0.0,
            animate_opacity=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                controls=[
                    ft.Container(height=1, bgcolor="#FFFFFF2E"),
                    ft.Container(height=5, bgcolor="#00000000"),
                ]
                * 70,
                spacing=0,
            ),
        )
        self.labels = []
        self.scene = ft.Stack(
            controls=[
                self.glow,
                self.logo,
                *self.labels,
                self.scanlines,
            ],
            alignment=ft.Alignment.CENTER,
            width=900,
            height=680,
            animate_offset=ft.Animation(70, ft.AnimationCurve.EASE_OUT),
        )
        self.overlay = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            expand=True,
            opacity=1.0,
            animate_opacity=ft.Animation(420, ft.AnimationCurve.EASE_OUT),
            bgcolor=None,
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda _: None,
            content=self.scene,
        )
        return self.overlay

    async def enter(self, page: ft.Page) -> None:
        if self.logo is None:
            return
        if self.scanlines is not None:
            self.scanlines.opacity = 0.18
            page.update(self.scanlines)
        self.logo.opacity = 1.0
        self.logo.scale = ft.Scale(1.0)
        self.logo.offset = ft.Offset(0, 0)
        self.logo.rotate = ft.Rotate(angle=0)
        page.update(self.logo)
        await asyncio.sleep(0.28)

    async def reveal_labels(self, page: ft.Page) -> None:
        if not self.labels:
            return
        for label in self.labels:
            label.opacity = 1.0
            label.scale = ft.Scale(1.0)
            label.offset = ft.Offset(0, 0)
            page.update(label)
            await asyncio.sleep(0.16)

    async def shake(self, page: ft.Page) -> None:
        if self.logo is None:
            return
        self.logo.scale = ft.Scale(1.12)
        page.update(self.logo)
        await asyncio.sleep(0.16)
        cycle_steps = [
            (1.18, -0.095, 0.82, 0.052),
            (1.42, 0.130, 0.88, 0.058),
            (1.96, -0.215, 1.02, 0.070),
            (1.58, 0.150, 0.90, 0.060),
        ]
        for cycle_scale, angle, jitter_intensity, impact_strength in cycle_steps:
            self.logo.scale = ft.Scale(cycle_scale)
            self.logo.rotate = ft.Rotate(angle=angle)
            page.update(self.logo)
            await self._glitch_burst(page)
            await self._impact(page, strength=impact_strength)
            await self._micro_jitter(page, intensity=jitter_intensity)
        self.logo.offset = ft.Offset(0, 0)
        self.logo.scale = ft.Scale(1.04)
        self.logo.rotate = ft.Rotate(angle=0)
        page.update(self.logo)
        await self._final_slam(page)
        await self._back_off(page)
        await asyncio.sleep(1.0)

    async def _micro_jitter(self, page: ft.Page, intensity: float = 1.0) -> None:
        if self.logo is None:
            return
        frames = [
            (-0.090, -0.040, 1.26, -0.125),
            (0.086, 0.048, 1.36, 0.135),
            (-0.076, 0.052, 1.24, -0.112),
            (0.082, -0.050, 1.38, 0.122),
            (0.0, 0.0, 1.12, 0.0),
        ]
        for x, y, scale, angle in frames:
            self.logo.offset = ft.Offset(x * intensity, y * intensity)
            self.logo.scale = ft.Scale(scale + (intensity - 1.0) * 0.34)
            self.logo.rotate = ft.Rotate(angle=angle * intensity)
            page.update(self.logo)
            await asyncio.sleep(0.018)

    async def _back_off(self, page: ft.Page) -> None:
        if self.logo is None:
            return
        self.logo.animate_scale = ft.Animation(210, ft.AnimationCurve.EASE_OUT)
        self.logo.animate_offset = ft.Animation(210, ft.AnimationCurve.EASE_OUT)
        self.logo.animate_rotation = ft.Animation(210, ft.AnimationCurve.EASE_OUT)
        self.logo.scale = ft.Scale(0.84)
        self.logo.offset = ft.Offset(0, -0.04)
        self.logo.rotate = ft.Rotate(angle=0)
        page.update(self.logo)
        await asyncio.sleep(0.20)

    async def _escape_move(
        self,
        page: ft.Page,
        offset: ft.Offset,
        scale: float,
        angle: float,
        delay: float,
    ) -> None:
        if self.logo is None:
            return
        self.logo.animate_offset = ft.Animation(145, ft.AnimationCurve.EASE_OUT_CUBIC)
        self.logo.animate_scale = ft.Animation(145, ft.AnimationCurve.EASE_OUT_CUBIC)
        self.logo.animate_rotation = ft.Animation(145, ft.AnimationCurve.EASE_OUT_CUBIC)
        self.logo.offset = offset
        self.logo.scale = ft.Scale(scale)
        self.logo.rotate = ft.Rotate(angle=angle)
        page.update(self.logo)
        await asyncio.sleep(delay)
        self.logo.animate_offset = ft.Animation(48, ft.AnimationCurve.EASE_OUT)
        self.logo.animate_scale = ft.Animation(48, ft.AnimationCurve.EASE_OUT)
        self.logo.animate_rotation = ft.Animation(48, ft.AnimationCurve.EASE_OUT)

    async def _rage_escape(self, page: ft.Page) -> None:
        if self.logo is None:
            return
        attempts = [
            (ft.Offset(-1.70, -0.10), 1.36, -0.260),
            (ft.Offset(1.70, 0.10), 1.40, 0.260),
            (ft.Offset(-1.50, 0.62), 1.34, -0.220),
            (ft.Offset(1.50, -0.62), 1.42, 0.230),
            (ft.Offset(0.00, -1.28), 1.36, -0.180),
            (ft.Offset(0.00, 1.28), 1.44, 0.180),
            (ft.Offset(0.00, 0.00), 1.18, 0.0),
        ]
        for index, (offset, scale, angle) in enumerate(attempts):
            self.logo.animate_offset = ft.Animation(95, ft.AnimationCurve.EASE_OUT_CUBIC)
            self.logo.animate_scale = ft.Animation(95, ft.AnimationCurve.EASE_OUT_CUBIC)
            self.logo.animate_rotation = ft.Animation(95, ft.AnimationCurve.EASE_OUT_CUBIC)
            self.logo.offset = offset
            self.logo.scale = ft.Scale(scale)
            self.logo.rotate = ft.Rotate(angle=angle)
            page.update(self.logo)
            if index in {0, 2, 4}:
                await self._impact(page, strength=0.030)
            await asyncio.sleep(0.100 if index < len(attempts) - 1 else 0.16)

    async def _glitch_burst(self, page: ft.Page) -> None:
        if self.scanlines is None:
            return
        for opacity, delay in [(0.48, 0.022), (0.16, 0.012), (0.56, 0.020), (0.14, 0.010)] * 2:
            self.scanlines.opacity = opacity
            page.update(self.scanlines)
            await asyncio.sleep(delay)

    async def _impact(self, page: ft.Page, strength: float = 0.020) -> None:
        updates: list[ft.Control] = []
        if self.scene is not None:
            self.scene.offset = ft.Offset(strength, -strength * 0.6)
            updates.append(self.scene)
        if updates:
            page.update(*updates)
        await asyncio.sleep(0.034)
        updates = []
        if self.scene is not None:
            self.scene.offset = ft.Offset(-strength * 0.65, strength * 0.4)
            updates.append(self.scene)
        if updates:
            page.update(*updates)
        await asyncio.sleep(0.034)
        if self.scene is not None:
            self.scene.offset = ft.Offset(0, 0)
            page.update(self.scene)

    async def _final_slam(self, page: ft.Page) -> None:
        if self.logo is None:
            return
        self.logo.animate_offset = ft.Animation(70, ft.AnimationCurve.EASE_IN)
        self.logo.animate_scale = ft.Animation(70, ft.AnimationCurve.EASE_IN)
        self.logo.offset = ft.Offset(0, 0.38)
        self.logo.scale = ft.Scale(1.55)
        page.update(self.logo)
        await asyncio.sleep(0.075)
        await self._impact(page, strength=0.050)
        self.logo.animate_offset = ft.Animation(180, ft.AnimationCurve.EASE_OUT_BACK)
        self.logo.animate_scale = ft.Animation(180, ft.AnimationCurve.EASE_OUT_BACK)
        self.logo.offset = ft.Offset(0, 0)
        self.logo.scale = ft.Scale(1.05)
        page.update(self.logo)
        await asyncio.sleep(0.12)

    async def exit(self, page: ft.Page) -> None:
        if self.overlay is None or self.logo is None:
            return
        for label in reversed(self.labels):
            label.opacity = 0.0
            label.scale = ft.Scale(0.94)
            page.update(label)
            await asyncio.sleep(0.035)
        self.logo.scale = ft.Scale(0.34)
        self.logo.offset = ft.Offset(-1.15, -0.52)
        self.logo.opacity = 0.0
        if self.scanlines is not None:
            self.scanlines.opacity = 0.0
            page.update(self.logo, self.scanlines)
        else:
            page.update(self.logo)
        await asyncio.sleep(0.22)
        self.overlay.opacity = 0.0
        page.update(self.overlay)
        await asyncio.sleep(0.16)

    def _ghost(self, tint: str, offset: ft.Offset) -> ft.Container:
        return ft.Container(
            width=360,
            height=360,
            alignment=ft.Alignment.CENTER,
            opacity=0.0,
            offset=offset,
            blend_mode=ft.BlendMode.SCREEN,
            animate_opacity=ft.Animation(60, ft.AnimationCurve.EASE_OUT),
            content=ft.Image(
                src=self.image_src,
                width=340,
                height=340,
                fit="contain",
                color=tint,
                color_blend_mode=ft.BlendMode.SRC_IN,
            ),
        )

    def _label(
        self,
        text: str,
        color: str,
        delay_index: int,
        top: int | None = None,
        right: int | None = None,
        bottom: int | None = None,
        left: int | None = None,
    ) -> ft.Container:
        return ft.Container(
            top=top,
            right=right,
            bottom=bottom,
            left=left,
            opacity=0.0,
            scale=ft.Scale(0.84),
            offset=ft.Offset(0.20 if delay_index % 2 else -0.20, 0.0),
            animate_opacity=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(260, ft.AnimationCurve.EASE_OUT_BACK),
            animate_offset=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
            content=ft.Text(
                text,
                size=24,
                weight=ft.FontWeight.W_900,
                color=color,
            ),
        )

"""Settings screen for rate rules."""

from __future__ import annotations

import flet as ft

from app.domain.models import RateRule


def create_settings_view(context) -> ft.Control:
    """Create rate rules settings screen."""
    table_holder = ft.Container(expand=True)
    name = ft.TextField(label="Rule name", dense=True)
    formula = ft.TextField(label="Rate formula", dense=True, expand=True)
    currency = ft.TextField(label="Currency", dense=True, width=140)
    operation_type = ft.TextField(label="Operation type", dense=True, width=180)
    priority = ft.TextField(label="Priority", value="100", dense=True, width=120)

    def refresh(update: bool = True) -> None:
        table_holder.content = _rules_table(context, context.rules_repository.list(), refresh)
        if update:
            context.page.update()

    def add_rule(_: ft.ControlEvent) -> None:
        try:
            context.rules_repository.add(
                RateRule(
                    rule_name=name.value,
                    rate_formula=formula.value,
                    currency=currency.value.upper() if currency.value else None,
                    operation_type=operation_type.value or None,
                    priority=int(priority.value or 100),
                )
            )
            name.value = ""
            formula.value = ""
            refresh()
        except Exception as exc:
            context.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    root = ft.Column(
        controls=[
            ft.Text("Settings", size=28, weight=ft.FontWeight.W_700),
            ft.Text("Rate rules", size=18, weight=ft.FontWeight.W_700),
            ft.Container(
                padding=16,
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                content=ft.Column(
                    controls=[
                        ft.Row([name, formula], wrap=True),
                        ft.Row(
                            [operation_type, currency, priority, ft.FilledButton("Add rule", icon=ft.Icons.ADD, on_click=add_rule)],
                            wrap=True,
                        ),
                    ],
                    spacing=12,
                ),
            ),
            table_holder,
        ],
        expand=True,
        spacing=16,
    )
    refresh(update=False)
    return root


def _rules_table(context, rules: list[RateRule], refresh) -> ft.Control:
    rows = [
        ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(rule.id or ""))),
                ft.DataCell(ft.Text(rule.rule_name)),
                ft.DataCell(ft.Text(rule.operation_type or "")),
                ft.DataCell(ft.Text(rule.currency or "")),
                ft.DataCell(ft.Text(rule.rate_formula)),
                ft.DataCell(ft.Text(str(rule.priority))),
                ft.DataCell(ft.Text("Yes" if rule.is_active else "No")),
                ft.DataCell(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Delete",
                        on_click=lambda _, item=rule: _delete_rule(context, item, refresh),
                    )
                ),
            ]
        )
        for rule in rules
    ]
    return ft.Row(
        controls=[
            ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Name")),
                    ft.DataColumn(ft.Text("Operation")),
                    ft.DataColumn(ft.Text("Currency")),
                    ft.DataColumn(ft.Text("Formula")),
                    ft.DataColumn(ft.Text("Priority"), numeric=True),
                    ft.DataColumn(ft.Text("Active")),
                    ft.DataColumn(ft.Text("Actions")),
                ],
                rows=rows,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def _delete_rule(context, rule: RateRule, refresh) -> None:
    if rule.id is not None:
        context.rules_repository.delete(rule.id)
        refresh()

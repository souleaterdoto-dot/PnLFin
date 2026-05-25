"""Constants and column definitions for the deals registry UI."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from app.domain.models import Deal
from app.ui.deals.formatters import _format_bool, _format_date, _format_number, _format_percent


PAGE_SIZE = 50
ROW_HEIGHT = 30
HEADER_HEIGHT = 72
CELL_X_PADDING = 6
CELL_FONT_SIZE = 11
HEADER_FONT_SIZE = 10
COLUMN_WIDTH_SCALE = 0.84
MIN_COLUMN_WIDTH = 70
ANIMATED_VISIBLE_ROWS = 50

ColumnGetter = Callable[[Deal], Any]
ColumnSpec = tuple[str, str | None, ColumnGetter, int, bool]


EXCEL_COLUMNS: tuple[ColumnSpec, ...] = (
    ("№ сделки", "external_deal_id", lambda d: d.external_deal_id, 150, False),
    ("Менеджер", "manager", lambda d: d.manager, 130, False),
    ("Повторный платёж (чекбокс)", "is_repeat_payment", lambda d: _format_bool(d.is_repeat_payment), 150, False),
    ("Дата поступления заявки", "request_date", lambda d: _format_date(d.request_date), 145, False),
    ("Дата фиксации с клиентом", "client_fix_date", lambda d: _format_date(d.client_fix_date), 150, False),
    ("Дата списания с баланса ПА", "agent_writeoff_date", lambda d: _format_date(d.agent_writeoff_date), 165, False),
    ("Дата получения клиентом", "client_receive_date", lambda d: _format_date(d.client_receive_date), 165, False),
    ("Возврат (чекбокс)", "is_refund", lambda d: _format_bool(d.is_refund), 130, False),
    ("Дата возврата средств на ПА", "agent_refund_date", lambda d: _format_date(d.agent_refund_date), 170, False),
    ("Дата возврата средств клиенту", "client_refund_date", lambda d: _format_date(d.client_refund_date), 190, False),
    ("Статус платежа", "payment_status", lambda d: d.payment_status, 145, False),
    ("Название клиента", "client_name", lambda d: d.client_name, 180, False),
    ("Статья название (клиент)", "customer_article_name", lambda d: d.customer_article_name, 190, False),
    ("Компания получатель", "receiver_company", lambda d: d.receiver_company, 180, False),
    ("Страна банка получателя", "receiver_bank_country", lambda d: d.receiver_bank_country, 165, False),
    ("Сумма сделки", "deal_amount", lambda d: _format_number(d.deal_amount, 2), 125, True),
    ("Валюта сделки", "deal_currency", lambda d: d.deal_currency, 115, False),
    (
        "Ставка для клиента (%)",
        "client_rate_percent",
        lambda d: _format_percent(abs(float(d.client_rate_percent)) if d.client_rate_percent is not None else None, 2),
        150,
        True,
    ),
    ("Фикс. Комиссия (сумма)", "fixed_commission_amount", lambda d: _format_number(d.fixed_commission_amount, 2), 150, True),
    ("Фикс. Комиссия (валюта)", "fixed_commission_currency", lambda d: d.fixed_commission_currency, 150, False),
    ("SWIFT (сумма)", "swift_amount", lambda d: _format_number(d.swift_amount, 2), 115, True),
    ("SWIFT (валюта)", "swift_currency", lambda d: d.swift_currency, 115, False),
    ("Курс фиксации с клиентом", "client_fix_rate", lambda d: _format_number(d.client_fix_rate, 4), 165, True),
    ("Курс к USD", "usd_rate", lambda d: _format_number(d.usd_rate, 4), 105, True),
    ("Кросс-курс с клиентом", "client_cross_rate", lambda d: _format_number(d.client_cross_rate, 4), 165, True),
    ("Платежный агент", "payment_agent", lambda d: d.payment_agent, 150, False),
    ("Комиссия ПА (сумма)", "agent_commission_amount", lambda d: _format_number(d.agent_commission_amount, 2), 145, True),
    ("Валюта комиссии ПА", "agent_commission_currency", lambda d: d.agent_commission_currency, 145, False),
    ("Комиссия за свифт ПА (сумма)", "swift_commission_amount", lambda d: _format_number(d.swift_commission_amount, 2), 175, True),
    ("Валюта комиссии за свифт ПА", "swift_commission_currency", lambda d: d.swift_commission_currency, 180, False),
)

COLUMN_BY_FIELD: dict[str, ColumnSpec] = {
    field_name: spec for spec in EXCEL_COLUMNS if (field_name := spec[1])
}

BASE_FIELDS = ("external_deal_id", "client_name", "client_fix_date")
PINNED_COLUMN_COUNT = len(BASE_FIELDS)

GENERAL_FIELDS = (
    "manager",
    "is_repeat_payment",
    "request_date",
    "agent_writeoff_date",
    "client_receive_date",
    "is_refund",
    "agent_refund_date",
    "client_refund_date",
    "payment_status",
    "receiver_company",
    "receiver_bank_country",
)

RATES_FIELDS = (
    "deal_amount",
    "deal_currency",
    "client_fix_rate",
    "usd_rate",
    "client_cross_rate",
)

FINANCE_COMMON_FIELDS = (
    "deal_currency",
    "client_rate_percent",
    "payment_agent",
    "customer_article_name",
)

FINANCE_CURRENCY_FIELDS = (
    "deal_amount",
    "deal_currency",
    "client_rate_percent",
    "fixed_commission_amount",
    "fixed_commission_currency",
    "swift_amount",
    "swift_currency",
    "payment_agent",
    "agent_commission_amount",
    "agent_commission_currency",
    "swift_commission_amount",
    "swift_commission_currency",
    "customer_article_name",
)

FINANCE_USD_COMPUTED_COLUMNS: tuple[ColumnSpec, ...] = (
    ("Сумма сделки, USD", "__deal_amount_usd", lambda d: None, 145, True),
    ("Фикс. комиссия, USD", "__fixed_commission_usd", lambda d: None, 150, True),
    ("SWIFT, USD", "__swift_usd", lambda d: None, 120, True),
    ("Комиссия ПА, USD", "__agent_commission_usd", lambda d: None, 150, True),
    ("Комиссия за свифт ПА, USD", "__swift_commission_usd", lambda d: None, 180, True),
)

FINANCE_RATE_COLUMNS: tuple[ColumnSpec, ...] = (
    ("Ставка реферала, USD", "__referral_rate", lambda d: None, 165, True),
)

PNL_COMPUTED_COLUMNS: tuple[ColumnSpec, ...] = (
    ("Сумма сделки", "deal_amount", lambda d: _format_number(d.deal_amount, 2), 125, True),
    ("Валюта сделки", "deal_currency", lambda d: d.deal_currency, 115, False),
    ("Комиссия клиента %, USD", "__client_percent_fee_usd", lambda d: None, 170, True),
    ("Фикс. комиссия, USD", "__fixed_commission_usd", lambda d: None, 150, True),
    ("SWIFT, USD", "__swift_usd", lambda d: None, 120, True),
    ("Комиссия ПА, USD", "__agent_commission_usd", lambda d: None, 150, True),
    ("Комиссия за SWIFT ПА, USD", "__swift_commission_usd", lambda d: None, 185, True),
    ("Ставка реферала, USD", "__referral_rate", lambda d: None, 165, True),
    ("Штраф за переотправку, USD", "__repeat_payment_penalty_usd", lambda d: None, 175, True),
    ("PnL, USD", "__pnl_usd", lambda d: None, 145, True),
)
COMPUTED_FILTER_COLUMNS = {
    "__deal_amount_usd",
    "__fixed_commission_usd",
    "__swift_usd",
    "__agent_commission_usd",
    "__swift_commission_usd",
    "__client_percent_fee_usd",
    "__repeat_payment_penalty_usd",
    "__referral_rate",
    "__pnl_usd",
}

EDIT_FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("external_deal_id", "№ сделки", "text"),
    ("manager", "Менеджер", "text"),
    ("is_repeat_payment", "Повторный платёж", "bool"),
    ("request_date", "Дата поступления заявки", "date"),
    ("client_fix_date", "Дата фиксации с клиентом", "date"),
    ("agent_writeoff_date", "Дата списания с баланса ПА", "date"),
    ("client_receive_date", "Дата получения клиентом", "date"),
    ("is_refund", "Возврат", "bool"),
    ("agent_refund_date", "Дата возврата средств на ПА", "date"),
    ("client_refund_date", "Дата возврата средств клиенту", "date"),
    ("payment_status", "Статус платежа", "text"),
    ("client_name", "Название клиента", "text"),
    ("customer_article_name", "Статья название (клиент)", "text"),
    ("receiver_company", "Компания получатель", "text"),
    ("receiver_bank_country", "Страна банка получателя", "text"),
    ("deal_amount", "Сумма сделки", "float"),
    ("deal_currency", "Валюта сделки", "upper"),
    ("client_rate_percent", "Ставка для клиента (%)", "percent"),
    ("fixed_commission_amount", "Фикс. Комиссия (сумма)", "float"),
    ("fixed_commission_currency", "Фикс. Комиссия (валюта)", "upper"),
    ("swift_amount", "SWIFT (сумма)", "float"),
    ("swift_currency", "SWIFT (валюта)", "upper"),
    ("client_fix_rate", "Курс фиксации с клиентом", "float"),
    ("usd_rate", "Курс к USD", "float"),
    ("client_cross_rate", "Кросс-курс с клиентом", "float"),
    ("payment_agent", "Платежный агент", "text"),
    ("agent_commission_amount", "Комиссия ПА (сумма)", "float"),
    ("agent_commission_currency", "Валюта комиссии ПА", "upper"),
    ("swift_commission_amount", "Комиссия за свифт ПА (сумма)", "float"),
    ("swift_commission_currency", "Валюта комиссии за свифт ПА", "upper"),
)

SYSTEM_FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("trade_date", "Trade date", "date_required"),
    ("value_date", "Value date", "date_required"),
    ("operation_type", "Operation type", "text_required"),
    ("counterparty", "Counterparty", "text_required"),
    ("currency_buy", "Currency buy", "upper_required"),
    ("amount_buy", "Amount buy", "float_required"),
    ("currency_sell", "Currency sell", "upper_required"),
    ("amount_sell", "Amount sell", "float_required"),
    ("rate_fact", "Rate fact", "float_required"),
    ("commission", "Commission", "float_required"),
    ("portfolio", "Portfolio", "text_required"),
    ("comment", "Comment", "text"),
)

EDIT_GENERAL_FIELDS = (
    "external_deal_id",
    "manager",
    "request_date",
    "client_fix_date",
    "agent_writeoff_date",
    "client_receive_date",
    "agent_refund_date",
    "client_refund_date",
    "payment_status",
    "client_name",
    "receiver_company",
    "receiver_bank_country",
)

EDIT_RATES_FIELDS = (
    "deal_amount",
    "deal_currency",
    "client_fix_rate",
    "usd_rate",
    "client_cross_rate",
)

EDIT_FINANCE_FIELDS = (
    "client_rate_percent",
    "fixed_commission_amount",
    "fixed_commission_currency",
    "swift_amount",
    "swift_currency",
    "payment_agent",
    "agent_commission_amount",
    "agent_commission_currency",
    "swift_commission_amount",
    "swift_commission_currency",
    "customer_article_name",
)

VIEW_MODES = ("general", "rates", "finance_usd", "finance_currency", "pnl", "all")

MODE_THEMES = {
    "general": {
        "label": "Общий",
        "icon": ft.Icons.VIEW_AGENDA_OUTLINED,
        "accent": "#3B6EA8",
        "soft": "#EEF6FF",
        "tint": "#D7E8FA",
        "gradient": ("#EFF7FF", "#CFE7FF", "#FFFFFF"),
    },
    "rates": {
        "label": "Курсы",
        "icon": ft.Icons.CURRENCY_EXCHANGE_OUTLINED,
        "accent": "#3F8F74",
        "soft": "#F0FAF6",
        "tint": "#D8EFE7",
        "shadow": "#2563EB",
        "gradient": ("#EEFFF7", "#C9F0DF", "#FFFFFF"),
    },
    "finance_usd": {
        "label": "Финансы USD",
        "icon": ft.Icons.INSIGHTS_OUTLINED,
        "accent": "#7A6AA8",
        "soft": "#F5F2FB",
        "tint": "#E8E1F5",
        "gradient": ("#F8F3FF", "#DED2F4", "#FFFFFF"),
    },
    "finance_currency": {
        "label": "Финансы валюта",
        "icon": ft.Icons.PAYMENTS_OUTLINED,
        "accent": "#B8744A",
        "soft": "#FFF6EE",
        "tint": "#F4E2D3",
        "gradient": ("#FFF6EE", "#F8D9BF", "#FFFFFF"),
    },
    "pnl": {
        "label": "PnL",
        "icon": ft.Icons.SSID_CHART_OUTLINED,
        "accent": "#D6A84F",
        "soft": "#1E1710",
        "tint": "#B88A35",
        "shadow": "#D6A84F",
        "gradient": ("#0B0F19", "#15110D", "#1F2937", "#111827"),
    },
    "all": {
        "label": "Все",
        "icon": ft.Icons.TABLE_VIEW_OUTLINED,
        "accent": "#64748B",
        "soft": "#F4F7FA",
        "tint": "#E3EAF2",
        "gradient": ("#F8FAFC", "#DDE6F0", "#FFFFFF"),
    },
}

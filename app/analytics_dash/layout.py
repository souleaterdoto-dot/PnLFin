"""Dash layout for the local analytics dashboard."""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from app.analytics_dash.styles import (
    ACCENT_BRIGHT,
    HAIRLINE,
    HAIRLINE_STRONG,
    MUTED,
    NEGATIVE,
    POSITIVE,
    SURFACE,
    SURFACE_ELEV,
    TEXT,
    TEXT_DIM,
    COLORS,
    HERO_STYLE,
    PAGE_STYLE,
    REFERRAL_CARD_STYLE,
    REFERRAL_FILTER_STYLE,
    REFERRAL_GRID_STYLE,
    TAB_STYLE,
)


def create_layout(initial_state: dict[str, Any]) -> html.Div:
    """Create the dashboard layout with one PnL chart per referral."""
    options = initial_state.get("options", {})
    referrals = initial_state.get("referrals") or [{"name": name} for name in options.get("referral", [])]
    partners = options.get("payment_agent", [])
    return html.Div(
        style=PAGE_STYLE,
        children=[
            _hero(referrals),
            _global_filters(options),
            dcc.Tabs(
                id="analytics-tabs",
                value="pnl-referrals",
                style=TAB_STYLE,
                parent_style={"margin": "0"},
                content_style={"padding": "0"},
                children=[
                    dcc.Tab(
                        label="Рефералы",
                        value="pnl-referrals",
                        style=_tab_item_style(active=False),
                        selected_style=_tab_item_style(active=True),
                        children=[
                            html.Div(
                                style={"marginTop": "16px"},
                                children=_referral_cards(initial_state, options, referrals),
                            )
                        ],
                    ),
                    dcc.Tab(
                        label="Клиенты",
                        value="clients",
                        style=_tab_item_style(active=False),
                        selected_style=_tab_item_style(active=True),
                        children=[
                            html.Div(
                                style={"marginTop": "16px"},
                                children=_clients_view(referrals),
                            )
                        ],
                    ),
                    dcc.Tab(
                        label="\u041f\u0430\u0440\u0442\u043d\u0435\u0440\u044b",
                        value="partners",
                        style=_tab_item_style(active=False),
                        selected_style=_tab_item_style(active=True),
                        children=[
                            html.Div(
                                style={"marginTop": "16px"},
                                children=_partner_cards(initial_state, options, partners),
                            )
                        ],
                    ),
                    dcc.Tab(
                        label="\u041e\u0431\u043e\u0440\u043e\u0442\u044b",
                        value="turnover",
                        style=_tab_item_style(active=False),
                        selected_style=_tab_item_style(active=True),
                        children=[
                            html.Div(
                                style={"marginTop": "16px"},
                                children=_turnover_view(initial_state, options),
                            )
                        ],
                    ),
                    dcc.Tab(
                        label="Рентабельность",
                        value="roi",
                        style=_tab_item_style(active=False),
                        selected_style=_tab_item_style(active=True),
                        children=[
                            html.Div(
                                style={"marginTop": "16px"},
                                children=_roi_view(initial_state, options),
                            )
                        ],
                    ),
                ],
            ),
        ],
    )


def _global_filters(options: dict[str, list[str]]) -> html.Div:
    operation_options = options.get("operation_type", [])
    return html.Div(
        style={
            "background": SURFACE,
            "border": f"1px solid {HAIRLINE}",
            "borderRadius": "18px",
            "boxShadow": "0 14px 34px #0F1F3D12",
            "padding": "16px",
            "marginBottom": "16px",
            "display": "flex",
            "alignItems": "stretch",
            "justifyContent": "space-between",
            "gap": "18px",
            "flexWrap": "wrap",
        },
        children=[
            html.Div(
                style={"minWidth": "210px", "padding": "4px 4px 4px 0"},
                children=[
                    html.Div(
                        "Общий фильтр",
                        style={
                            "fontSize": "10px",
                            "fontWeight": "700",
                            "letterSpacing": "1.2px",
                            "color": ACCENT_BRIGHT,
                            "textTransform": "uppercase",
                        },
                    ),
                    html.Div(
                        "Единые настройки для всех графиков на странице",
                        style={"fontSize": "12px", "color": TEXT_DIM, "marginTop": "4px", "lineHeight": "16px"},
                    ),
                ]
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
                    "gap": "10px",
                    "alignItems": "stretch",
                    "justifyContent": "end",
                    "flex": "1 1 720px",
                },
                children=[
                    _global_filter_group(
                        "Визуализация",
                        dcc.RadioItems(
                            id="analytics-chart-kind",
                            value="bar",
                            options=[
                                {"label": "Гистограммы", "value": "bar"},
                                {"label": "Графики", "value": "line"},
                                {"label": "Диаграммы", "value": "pie"},
                            ],
                            inline=True,
                            inputStyle=_global_radio_input_style(),
                            labelClassName="analytics-operation-radio-label",
                            className="analytics-operation-radio analytics-chart-kind-radio",
                        ),
                    ),
                    _global_filter_group(
                        "Расчет",
                        dcc.RadioItems(
                            id="analytics-chart-view-mode",
                            value="breakdown",
                            options=[
                                {"label": "Доходы/расходы", "value": "breakdown"},
                                {"label": "PnL", "value": "pnl"},
                            ],
                            inline=True,
                            inputStyle=_global_radio_input_style(),
                            labelClassName="analytics-operation-radio-label",
                            className="analytics-operation-radio analytics-chart-kind-radio",
                        ),
                    ),
                    _global_filter_group(
                        "Валюта расчета",
                        dcc.RadioItems(
                            id="analytics-currency-mode",
                            value="usd",
                            options=[
                                {"label": "USD", "value": "usd"},
                                {"label": "Валюта сделки", "value": "currency"},
                            ],
                            inline=True,
                            inputStyle=_global_radio_input_style(),
                            labelClassName="analytics-operation-radio-label",
                            className="analytics-operation-radio analytics-chart-kind-radio",
                        ),
                    ),
                    _global_filter_group(
                        "Тип операции",
                        dcc.RadioItems(
                            id="analytics-operation-type-filter",
                            value="",
                            options=[{"label": "Все", "value": ""}]
                            + [{"label": value, "value": value} for value in operation_options],
                            inline=True,
                            inputStyle=_global_radio_input_style(),
                            labelClassName="analytics-operation-radio-label",
                            className="analytics-operation-radio",
                        ),
                    ),
                ],
            ),
        ],
    )


def _global_filter_group(title: str, control: Any) -> html.Div:
    return html.Div(
        style={
            "background": SURFACE_ELEV,
            "border": f"1px solid {HAIRLINE}",
            "borderRadius": "14px",
            "padding": "10px 11px 11px",
            "boxShadow": "inset 0 1px 0 #FFFFFF",
        },
        children=[
            html.Div(
                title,
                style={
                    "fontSize": "9px",
                    "fontWeight": "700",
                    "letterSpacing": "0.9px",
                    "textTransform": "uppercase",
                    "color": MUTED,
                    "margin": "0 0 7px 2px",
                },
            ),
            control,
        ],
    )


def _global_radio_input_style() -> dict[str, str]:
    return {
        "accentColor": ACCENT_BRIGHT,
        "width": "12px",
        "height": "12px",
        "margin": "0 6px 0 0",
    }


def _hero(referrals: list[dict[str, Any]]) -> html.Div:
    count = len(referrals)
    return html.Div(
        style=HERO_STYLE,
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "18px"},
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                "ЛОКАЛЬНЫЙ DASH / PLOTLY",
                                style={
                                    "fontSize": "10px",
                                    "fontWeight": "600",
                                    "color": ACCENT_BRIGHT,
                                    "textTransform": "uppercase",
                                    "letterSpacing": "1.2px",
                                },
                            ),
                            html.H1(
                                "\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 PnL",
                                style={"margin": "5px 0 6px", "fontSize": "28px", "fontWeight": "600", "color": TEXT},
                            ),
                            html.Div(
                                "PnL по каждому рефералу · фильтры и графики независимы",
                                style={"fontSize": "13px", "color": TEXT_DIM, "maxWidth": "720px"},
                            ),
                        ]
                    ),
                    html.Div(
                        style={
                            "minWidth": "184px",
                            "padding": "12px 16px",
                            "borderRadius": "12px",
                            "background": SURFACE,
                            "border": f"1px solid {HAIRLINE_STRONG}",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "flex-end",
                            "gap": "10px",
                        },
                        children=[
                            html.Div(
                                style={
                                    "width": "8px",
                                    "height": "8px",
                                    "borderRadius": "999px",
                                    "background": ACCENT_BRIGHT,
                                    "boxShadow": f"0 0 8px {ACCENT_BRIGHT}",
                                },
                            ),
                            html.Div(
                                children=[
                                    html.Div(str(count), style={"fontSize": "20px", "fontWeight": "600", "color": TEXT, "lineHeight": "20px"}),
                                    html.Div("активных рефералов", style={"fontSize": "11px", "fontWeight": "400", "color": MUTED}),
                                ]
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


def _tab_item_style(active: bool) -> dict[str, str]:
    base = {
        "border": "0",
        "borderBottom": f"1px solid {'transparent'}",
        "borderRadius": "0",
        "padding": "12px 14px",
        "fontWeight": "400",
        "fontSize": "13px",
        "background": "transparent",
        "boxShadow": "none",
    }
    if active:
        return {
            **base,
            "color": TEXT,
            "fontWeight": "500",
            "borderBottom": f"1px solid {ACCENT_BRIGHT}",
            "boxShadow": f"0 8px 8px -8px {ACCENT_BRIGHT}",
        }
    return {**base, "color": MUTED}


def _referral_cards(initial_state: dict[str, Any], options: dict[str, list[str]], referrals: list[dict[str, Any]]) -> html.Div:
    if not referrals:
        return html.Div(
            style=REFERRAL_CARD_STYLE,
            children=[
                html.H3("\u041d\u0435\u0442 \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u043e\u0432", style={"margin": "0 0 6px", "fontSize": "18px"}),
                html.Div(
                    "\u0412 \u0440\u0435\u0435\u0441\u0442\u0440\u0435 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0441\u0434\u0435\u043b\u043e\u043a \u0441 \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u0430\u043c\u0438.",
                    style={"color": COLORS["muted"], "fontSize": "13px"},
                ),
            ],
        )
    return html.Div(
        style=REFERRAL_GRID_STYLE,
        children=[_referral_card(initial_state, options, referral) for referral in referrals],
    )


def _partner_cards(initial_state: dict[str, Any], options: dict[str, list[str]], partners: list[str]) -> html.Div:
    if not partners:
        return html.Div(
            style={**REFERRAL_CARD_STYLE, "padding": "18px"},
            children=[
                html.H3("\u041d\u0435\u0442 \u043f\u0430\u0440\u0442\u043d\u0435\u0440\u043e\u0432", style={"margin": "0 0 6px", "fontSize": "18px"}),
                html.Div(
                    "\u0412 \u0440\u0435\u0435\u0441\u0442\u0440\u0435 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0441\u0434\u0435\u043b\u043e\u043a \u0441 \u043f\u043b\u0430\u0442\u0435\u0436\u043d\u044b\u043c\u0438 \u0430\u0433\u0435\u043d\u0442\u0430\u043c\u0438.",
                    style={"color": COLORS["muted"], "fontSize": "13px"},
                ),
            ],
        )
    return html.Div(
        style=REFERRAL_GRID_STYLE,
        children=[_partner_card(initial_state, options, partner) for partner in partners],
    )


def _clients_view(referrals: list[dict[str, Any]]) -> html.Div:
    first_referral = str(referrals[0].get("name") or "") if referrals else ""
    return html.Div(
        className="analytics-card",
        style={**REFERRAL_CARD_STYLE, "minHeight": "560px"},
        children=[
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "flex-start",
                    "gap": "18px",
                    "paddingBottom": "16px",
                    "borderBottom": f"1px solid {HAIRLINE}",
                },
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                "Клиенты",
                                style={"fontSize": "10px", "fontWeight": "600", "letterSpacing": "1.2px", "color": ACCENT_BRIGHT, "textTransform": "uppercase"},
                            ),
                            html.H3(
                                "Топ клиентов по выбранному рефералу",
                                style={"margin": "4px 0 5px", "fontSize": "22px", "fontWeight": "600", "color": TEXT},
                            ),
                            html.Div(
                                "Первые 9 клиентов показываются отдельно, все остальные собираются в карточку «Остальные».",
                                style={"fontSize": "13px", "color": TEXT_DIM},
                            ),
                        ]
                    ),
                    html.Div(
                        id="clients-selected-referral-title",
                        children=first_referral or "Нет рефералов",
                        style={
                            "padding": "10px 14px",
                            "borderRadius": "12px",
                            "background": SURFACE_ELEV,
                            "border": f"1px solid {HAIRLINE_STRONG}",
                            "fontSize": "13px",
                            "fontWeight": "600",
                            "color": ACCENT_BRIGHT,
                            "maxWidth": "260px",
                            "whiteSpace": "nowrap",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                        },
                    ),
                ],
            ),
            html.Div(
                style={"paddingTop": "16px"},
                children=[
                    _clients_referral_picker(referrals, first_referral),
                    html.Div(id="clients-top-grid", className="analytics-clients-grid", style={"marginTop": "16px"}),
                    _client_detail_modal(),
                ],
            ),
        ],
    )


def _client_detail_modal() -> html.Div:
    return html.Div(
        id="client-detail-modal",
        className="analytics-modal-backdrop",
        style={"display": "none"},
        children=[
            html.Div(
                className="analytics-modal-card",
                children=[
                    html.Button("×", id="client-detail-close", n_clicks=0, className="analytics-modal-close"),
                    html.Div(id="client-detail-modal-body"),
                ],
            )
        ],
    )


def _clients_referral_picker(referrals: list[dict[str, Any]], value: str) -> html.Div:
    if not referrals:
        return html.Div(
            children=[
                dcc.RadioItems(id="clients-referral-select", value="", options=[], style={"display": "none"}),
                html.Div(
                    "В реестре пока нет рефералов.",
                    style={"padding": "18px", "borderRadius": "14px", "background": SURFACE_ELEV, "color": TEXT_DIM},
                ),
            ],
        )
    return html.Div(
        children=[
            html.Div(
                "Рефералы",
                style={"fontSize": "11px", "fontWeight": "700", "color": MUTED, "textTransform": "uppercase", "letterSpacing": "0.8px", "marginBottom": "10px"},
            ),
            dcc.RadioItems(
                id="clients-referral-select",
                value=value,
                options=[
                    {
                        "label": _client_referral_option_label(referral),
                        "value": str(referral.get("name") or ""),
                    }
                    for referral in referrals
                ],
                inline=True,
                inputStyle={
                    "accentColor": ACCENT_BRIGHT,
                    "width": "11px",
                    "height": "11px",
                    "margin": "0 6px 0 0",
                },
                labelClassName="analytics-client-referral-label",
                className="analytics-client-referrals",
            ),
        ]
    )


def _client_referral_option_label(referral: dict[str, Any]) -> html.Div:
    name = str(referral.get("name") or "")
    logo_url = referral.get("logo_url")
    return html.Div(
        className="analytics-client-referral-card-inner",
        children=[
            _referral_logo(name, logo_url, size=34),
            html.Div(
                style={"minWidth": 0},
                children=[
                    html.Div(
                        name,
                        title=name,
                        style={
                            "fontSize": "13px",
                            "fontWeight": "700",
                            "color": TEXT,
                            "lineHeight": "16px",
                            "overflow": "hidden",
                            "display": "-webkit-box",
                            "WebkitLineClamp": "2",
                            "WebkitBoxOrient": "vertical",
                            "textOverflow": "ellipsis",
                        },
                    ),
                    html.Div(
                        "реферал",
                        style={"fontSize": "10px", "fontWeight": "600", "color": MUTED, "textTransform": "uppercase", "letterSpacing": "0.5px", "marginTop": "2px"},
                    ),
                ],
            ),
        ],
    )


def _turnover_view(initial_state: dict[str, Any], options: dict[str, list[str]]) -> html.Div:
    return html.Div(
        className="analytics-card",
        style={**REFERRAL_CARD_STYLE, "minHeight": "620px"},
        children=[
            html.Div(
                style={
                    "paddingBottom": "16px",
                    "borderBottom": f"1px solid {HAIRLINE}",
                    "display": "flex",
                    "justifyContent": "space-between",
                    "gap": "16px",
                    "alignItems": "center",
                },
                children=[
                    html.Div(
                        children=[
                            html.Div("\u041e\u0431\u043e\u0440\u043e\u0442\u044b", style={"color": MUTED, "fontSize": "11px", "fontWeight": "500", "textTransform": "uppercase", "letterSpacing": "0.6px"}),
                            html.H3("\u0414\u0438\u043d\u0430\u043c\u0438\u043a\u0430 \u043e\u0431\u043e\u0440\u043e\u0442\u043e\u0432 \u043f\u043e \u0434\u0430\u0442\u0430\u043c", style={"margin": "3px 0 0", "fontSize": "20px", "fontWeight": "600", "color": TEXT}),
                        ]
                    ),
                    dcc.RadioItems(
                        id="turnover-mode",
                        value="usd",
                        options=[
                            {"label": "\u0412 USD", "value": "usd"},
                            {"label": "\u0412 \u0432\u0430\u043b\u044e\u0442\u0435", "value": "currency"},
                        ],
                        inline=True,
                        inputStyle={"marginRight": "6px"},
                        labelStyle={
                            "padding": "8px 12px",
                            "borderRadius": "999px",
                            "background": SURFACE_ELEV,
                            "border": f"1px solid {HAIRLINE}",
                            "marginLeft": "8px",
                            "fontWeight": "500",
                            "fontSize": "13px",
                            "color": TEXT_DIM,
                        },
                        style={"display": "none"},
                    ),
                ],
            ),
            html.Div(
                style={"padding": "16px 0 0"},
                children=[
                    html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "1.2fr repeat(6, minmax(120px, 1fr))",
                            "gap": "10px",
                            "alignItems": "end",
                            "marginBottom": "12px",
                        },
                        children=[
                            _date_range_pill(
                                "turnover-date-range",
                                initial_state.get("min_date"),
                                initial_state.get("max_date"),
                                initial_state.get("min_date"),
                                initial_state.get("max_date"),
                            ),
                            _dropdown("turnover-currency-filter", "\u0412\u0430\u043b\u044e\u0442\u0430", options.get("currency", [])),
                            _dropdown("turnover-referral-filter", "\u0420\u0435\u0444\u0435\u0440\u0430\u043b", options.get("referral", [])),
                            _dropdown("turnover-payment-agent-filter", "\u041f\u0430\u0440\u0442\u043d\u0435\u0440", options.get("payment_agent", [])),
                            _dropdown("turnover-manager-filter", "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440", options.get("manager", [])),
                            _dropdown("turnover-status-filter", "\u0421\u0442\u0430\u0442\u0443\u0441", options.get("status", [])),
                            _dropdown("turnover-operation-type-filter", "Тип", options.get("operation_type", [])),
                        ],
                    ),
                    dcc.Graph(
                        id="turnover-by-date",
                        config={"displayModeBar": "hover", "displaylogo": False},
                        style={"height": "470px"},
                    ),
                ],
            ),
        ],
    )


def _roi_view(initial_state: dict[str, Any], options: dict[str, list[str]]) -> html.Div:
    return html.Div(
        className="analytics-card",
        style={**REFERRAL_CARD_STYLE, "minHeight": "620px"},
        children=[
            html.Div(
                style={
                    "paddingBottom": "16px",
                    "borderBottom": f"1px solid {HAIRLINE}",
                    "display": "flex",
                    "justifyContent": "space-between",
                    "gap": "16px",
                    "alignItems": "center",
                },
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                "Рентабельность",
                                style={"color": ACCENT_BRIGHT, "fontSize": "10px", "fontWeight": "600", "textTransform": "uppercase", "letterSpacing": "1.2px"},
                            ),
                            html.H3(
                                "Рентабельность по PnL",
                                style={"margin": "4px 0 5px", "fontSize": "22px", "fontWeight": "600", "color": TEXT},
                            ),
                            html.Div(
                                "Рентабельность = PnL / оборот USD · переключение между рефералами и партнёрами",
                                style={"fontSize": "13px", "color": TEXT_DIM},
                            ),
                        ]
                    ),
                    dcc.RadioItems(
                        id="roi-dimension-mode",
                        value="referral",
                        options=[
                            {"label": "Рефералы", "value": "referral"},
                            {"label": "Партнёры", "value": "partner"},
                        ],
                        inline=True,
                        inputStyle={
                            "accentColor": ACCENT_BRIGHT,
                            "width": "12px",
                            "height": "12px",
                            "margin": "0 6px 0 0",
                        },
                        labelClassName="analytics-operation-radio-label",
                        className="analytics-operation-radio",
                    ),
                ],
            ),
            html.Div(
                style={"padding": "16px 0 0"},
                children=[
                    html.Div(id="roi-kpis", className="analytics-roi-kpis", style={"marginBottom": "14px"}),
                    html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "1.2fr repeat(6, minmax(120px, 1fr))",
                            "gap": "10px",
                            "alignItems": "end",
                            "marginBottom": "12px",
                        },
                        children=[
                            _date_range_pill(
                                "roi-date-range",
                                initial_state.get("min_date"),
                                initial_state.get("max_date"),
                                initial_state.get("min_date"),
                                initial_state.get("max_date"),
                            ),
                            _dropdown("roi-currency-filter", "Валюта", options.get("currency", [])),
                            _dropdown("roi-referral-filter", "Реферал", options.get("referral", [])),
                            _dropdown("roi-payment-agent-filter", "Партнёр", options.get("payment_agent", [])),
                            _dropdown("roi-manager-filter", "Менеджер", options.get("manager", [])),
                            _dropdown("roi-status-filter", "Статус", options.get("status", [])),
                            _dropdown("roi-operation-type-filter", "Тип", options.get("operation_type", [])),
                        ],
                    ),
                    dcc.Graph(
                        id="roi-by-dimension",
                        config={"displayModeBar": "hover", "displaylogo": False},
                        style={"height": "470px"},
                    ),
                ],
            ),
        ],
    )


def _referral_card(initial_state: dict[str, Any], options: dict[str, list[str]], referral: dict[str, Any]) -> html.Div:
    referral_name = str(referral.get("name") or "")
    component_key = referral_name
    logo_url = referral.get("logo_url")
    return _series_card(
        title=referral_name,
        kind="реферал",
        logo_url=logo_url,
        logo_key=referral_name,
        store=dcc.Store(id={"type": "referral-name", "referral": component_key}, data=referral_name),
        mode_id={"type": "referral-pnl-mode", "referral": component_key},
        sublabel_id={"type": "referral-sub-label", "referral": component_key},
        total_id={"type": "referral-total-pnl", "referral": component_key},
        delta_id={"type": "referral-delta-line", "referral": component_key},
        date_id={"type": "date-range", "referral": component_key},
        graph_id={"type": "referral-pnl-by-date", "referral": component_key},
        deals_id={"type": "referral-deals-count", "referral": component_key},
        avg_id={"type": "referral-avg-pnl", "referral": component_key},
        avg_style_id={"type": "referral-avg-pnl-style", "referral": component_key},
        win_id={"type": "referral-win-rate", "referral": component_key},
        chart_unit_id={"type": "referral-chart-unit", "referral": component_key},
        chart_view_mode_id={"type": "referral-chart-view-mode", "referral": component_key},
        min_date=initial_state.get("min_date"),
        max_date=initial_state.get("max_date"),
        start_date=initial_state.get("min_date"),
        end_date=initial_state.get("max_date"),
        dropdowns=[
            _dropdown({"type": "currency-filter", "referral": component_key}, "\u0412\u0430\u043b\u044e\u0442\u0430", options.get("currency", [])),
            _dropdown({"type": "payment-agent-filter", "referral": component_key}, "\u041f\u0430\u0440\u0442\u043d\u0435\u0440", options.get("payment_agent", [])),
            _dropdown({"type": "manager-filter", "referral": component_key}, "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440", options.get("manager", [])),
            _dropdown({"type": "status-filter", "referral": component_key}, "\u0421\u0442\u0430\u0442\u0443\u0441", options.get("status", [])),
            _dropdown({"type": "operation-type-filter", "referral": component_key}, "Тип", options.get("operation_type", [])),
        ],
    )


def _partner_card(initial_state: dict[str, Any], options: dict[str, list[str]], partner: str) -> html.Div:
    partner_name = str(partner or "")
    component_key = partner_name
    return _series_card(
        title=partner_name,
        kind="партнер",
        logo_url=None,
        logo_key=partner_name,
        store=dcc.Store(id={"type": "partner-name", "partner": component_key}, data=partner_name),
        mode_id={"type": "partner-pnl-mode", "partner": component_key},
        sublabel_id={"type": "partner-sub-label", "partner": component_key},
        total_id={"type": "partner-total-pnl", "partner": component_key},
        delta_id={"type": "partner-delta-line", "partner": component_key},
        date_id={"type": "partner-date-range", "partner": component_key},
        graph_id={"type": "partner-pnl-by-date", "partner": component_key},
        deals_id={"type": "partner-deals-count", "partner": component_key},
        avg_id={"type": "partner-avg-pnl", "partner": component_key},
        avg_style_id={"type": "partner-avg-pnl-style", "partner": component_key},
        win_id={"type": "partner-win-rate", "partner": component_key},
        chart_unit_id={"type": "partner-chart-unit", "partner": component_key},
        chart_view_mode_id={"type": "partner-chart-view-mode", "partner": component_key},
        min_date=initial_state.get("min_date"),
        max_date=initial_state.get("max_date"),
        start_date=initial_state.get("min_date"),
        end_date=initial_state.get("max_date"),
        dropdowns=[
            _dropdown({"type": "partner-currency-filter", "partner": component_key}, "\u0412\u0430\u043b\u044e\u0442\u0430", options.get("currency", [])),
            _dropdown({"type": "partner-referral-filter", "partner": component_key}, "\u0420\u0435\u0444\u0435\u0440\u0430\u043b", options.get("referral", [])),
            _dropdown({"type": "partner-manager-filter", "partner": component_key}, "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440", options.get("manager", [])),
            _dropdown({"type": "partner-status-filter", "partner": component_key}, "\u0421\u0442\u0430\u0442\u0443\u0441", options.get("status", [])),
            _dropdown({"type": "partner-operation-type-filter", "partner": component_key}, "Тип", options.get("operation_type", [])),
        ],
    )


def _series_card(
    *,
    title: str,
    kind: str,
    logo_url: str | None,
    logo_key: str,
    store,
    mode_id: Any,
    sublabel_id: Any,
    total_id: Any,
    delta_id: Any,
    date_id: Any,
    graph_id: Any,
    deals_id: Any,
    avg_id: Any,
    avg_style_id: Any,
    win_id: Any,
    chart_unit_id: Any,
    chart_view_mode_id: Any,
    min_date: str | None,
    max_date: str | None,
    start_date: str | None,
    end_date: str | None,
    dropdowns: list[html.Div],
) -> html.Div:
    return html.Div(
        className="analytics-card",
        style=REFERRAL_CARD_STYLE,
        children=[
            store,
            _card_header(title, kind, logo_url, logo_key, mode_id, sublabel_id, total_id, delta_id),
            html.Div(
                style={"paddingTop": "14px"},
                children=[
                    _filters_bar(date_id, min_date, max_date, start_date, end_date, dropdowns),
                    _micro_metrics(deals_id, avg_id, avg_style_id, win_id),
                    _chart_title(chart_unit_id, chart_view_mode_id),
                    dcc.Graph(
                        id=graph_id,
                        config={"displayModeBar": "hover", "displaylogo": False},
                        style={"height": "330px"},
                    ),
                ],
            ),
        ],
    )


def _card_header(
    title: str,
    kind: str,
    logo_url: str | None,
    logo_key: str,
    mode_id: Any,
    sublabel_id: Any,
    total_id: Any,
    delta_id: Any,
) -> html.Div:
    return html.Div(
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "14px"},
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "10px", "minWidth": 0},
                        children=[
                            _referral_logo(logo_key, logo_url, size=36),
                            html.Div(
                                style={"minWidth": 0},
                                children=[
                                    html.Div(
                                        title,
                                        style={
                                            "fontSize": "16px",
                                            "fontWeight": "600",
                                            "color": TEXT,
                                            "whiteSpace": "nowrap",
                                            "overflow": "hidden",
                                            "textOverflow": "ellipsis",
                                        },
                                    ),
                                    html.Div(
                                        id=sublabel_id,
                                        children=f"USD · {kind}",
                                        style={"fontSize": "11px", "fontWeight": "400", "color": MUTED, "marginTop": "2px"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "16px", "flex": "0 0 auto"},
                        children=[
                            _mode_switch(mode_id),
                            html.Div(
                                style={"textAlign": "right"},
                                children=[
                                    html.Div(
                                        id=total_id,
                                        children="+$0",
                                        style={
                                            "fontSize": "24px",
                                            "fontWeight": "300",
                                            "lineHeight": "26px",
                                            "color": TEXT,
                                            "fontFamily": "'JetBrains Mono', 'SF Mono', monospace",
                                        },
                                    ),
                                    html.Div(
                                        id=delta_id,
                                        children="▲ 0.0% к пред. периоду",
                                        style={"fontSize": "11px", "fontWeight": "500", "color": POSITIVE, "marginTop": "4px"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(style={"height": "1px", "background": HAIRLINE, "marginTop": "16px"}),
        ],
    )


def _mode_switch(component_id: Any) -> dcc.RadioItems:
    return dcc.RadioItems(
        id=component_id,
        value="usd",
        options=[
            {"label": "USD", "value": "usd"},
            {"label": "Валюта", "value": "currency"},
        ],
        inline=True,
        inputStyle={"marginRight": "5px"},
        labelStyle={
            "padding": "6px 9px",
            "borderRadius": "999px",
            "border": f"1px solid {HAIRLINE}",
            "marginLeft": "6px",
            "fontWeight": "500",
            "fontSize": "11px",
            "color": TEXT_DIM,
            "background": SURFACE_ELEV,
        },
        style={"display": "none"},
    )


def _filters_bar(
    date_id: Any,
    min_date: str | None,
    max_date: str | None,
    start_date: str | None,
    end_date: str | None,
    dropdowns: list[html.Div],
) -> html.Div:
    return html.Div(
        style=REFERRAL_FILTER_STYLE,
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px"},
                children=[
                    html.Div(
                        style={"display": "flex", "gap": "8px", "alignItems": "center", "flexWrap": "wrap"},
                        children=[
                            _filter_chip("Все валюты"),
                            _filter_chip("Все партнёры"),
                            _filter_chip("Все менеджеры"),
                            _filter_chip("Все статусы"),
                            _filter_chip("Все типы"),
                            html.Details(
                                className="analytics-filter-details",
                                children=[
                                    html.Summary("⚙ Фильтры", className="analytics-filter-summary", style=_filter_chip_style(accent=True)),
                                    html.Div(className="analytics-hidden-filters", children=dropdowns),
                                ],
                            ),
                        ],
                    ),
                    _date_range_pill(date_id, min_date, max_date, start_date, end_date),
                ],
            ),
        ],
    )


def _filter_chip(text: str) -> html.Div:
    return html.Div(text, className="analytics-chip", style=_filter_chip_style())


def _filter_chip_style(accent: bool = False) -> dict[str, str]:
    return {
        "borderRadius": "999px",
        "border": f"1px solid {HAIRLINE_STRONG if accent else HAIRLINE}",
        "padding": "6px 10px",
        "fontSize": "11px",
        "fontWeight": "500" if accent else "400",
        "color": ACCENT_BRIGHT if accent else TEXT_DIM,
        "cursor": "pointer" if accent else "default",
        "display": "inline-flex",
        "alignItems": "center",
        "height": "28px",
    }


def _date_range_pill(
    component_id: Any,
    min_date: str | None,
    max_date: str | None,
    start_date: str | None,
    end_date: str | None,
) -> html.Div:
    return html.Div(
        className="analytics-date-pill",
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "10px",
            "background": SURFACE,
            "border": f"1px solid {HAIRLINE_STRONG}",
            "borderRadius": "14px",
            "padding": "9px 12px",
            "flex": "0 0 auto",
            "height": "42px",
            "boxShadow": "0 8px 24px #0F1F3D14",
        },
        children=[
            _calendar_icon(),
            _date_input(_date_input_id(component_id, "from"), start_date, "С"),
            html.Div("→", style={"fontSize": "12px", "color": MUTED, "fontWeight": "700"}),
            _date_input(_date_input_id(component_id, "to"), end_date, "По"),
        ],
    )


def _date_input_id(component_id: Any, boundary: str) -> Any:
    if isinstance(component_id, dict):
        result = dict(component_id)
        current_type = str(result.get("type") or "date-range")
        result["type"] = current_type.replace("date-range", f"date-{boundary}")
        return result
    return str(component_id).replace("date-range", f"date-{boundary}")


def _date_input(component_id: Any, value: str | None, label: str) -> html.Div:
    return html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "5px"},
        children=[
            html.Span(label, style={"fontSize": "10px", "fontWeight": "700", "color": MUTED}),
            dcc.Input(
                id=component_id,
                type="date",
                value=value,
                className="analytics-date-input",
                style={
                    "height": "28px",
                    "width": "124px",
                    "border": f"1px solid {HAIRLINE}",
                    "borderRadius": "9px",
                    "background": SURFACE_ELEV,
                    "color": TEXT,
                    "fontSize": "11px",
                    "fontWeight": "600",
                    "fontFamily": "'JetBrains Mono', 'SF Mono', monospace",
                    "padding": "0 7px",
                    "outline": "none",
                },
            ),
        ],
    )


def _calendar_icon() -> html.Div:
    return html.Div(
        style={
            "width": "22px",
            "height": "22px",
            "borderRadius": "4px",
            "border": f"1px solid {ACCENT_BRIGHT}",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "flex": "0 0 auto",
            "boxShadow": f"0 0 8px {ACCENT_BRIGHT}",
        },
        children=[
            html.Div(style={"height": "6px", "background": ACCENT_BRIGHT}),
            html.Div(
                style={
                    "flex": "1",
                    "background": SURFACE_ELEV,
                    "display": "grid",
                    "gridTemplateColumns": "repeat(2, 1fr)",
                    "gap": "2px",
                    "padding": "3px",
                },
                children=[
                    html.Div(style={"background": HAIRLINE_STRONG, "borderRadius": "2px"}),
                    html.Div(style={"background": HAIRLINE_STRONG, "borderRadius": "2px"}),
                    html.Div(style={"background": HAIRLINE_STRONG, "borderRadius": "2px"}),
                    html.Div(style={"background": ACCENT_BRIGHT, "borderRadius": "2px"}),
                ],
            ),
        ],
    )


def _micro_metrics(deals_id: Any, avg_id: Any, avg_style_id: Any, win_id: Any) -> html.Div:
    return html.Div(
        style={
            "background": SURFACE_ELEV,
            "borderRadius": "10px",
            "padding": "12px 16px",
            "display": "flex",
            "alignItems": "center",
            "gap": "16px",
            "marginBottom": "12px",
        },
        children=[
            _metric_block("ВСЕГО СДЕЛОК", deals_id, "0"),
            _metric_divider(),
            _metric_block("СРЕДНИЙ PNL/ДЕНЬ", avg_id, "$0", value_style_id=avg_style_id),
            _metric_divider(),
            _metric_block("WIN RATE", win_id, "0%", value_color=POSITIVE),
        ],
    )


def _metric_block(label: str, component_id: Any, value: str, value_color: str = TEXT, value_style_id: Any | None = None) -> html.Div:
    return html.Div(
        style={"flex": "1", "minWidth": 0},
        children=[
            html.Div(
                label,
                style={
                    "fontSize": "9px",
                    "fontWeight": "500",
                    "letterSpacing": "0.8px",
                    "textTransform": "uppercase",
                    "color": MUTED,
                    "marginBottom": "5px",
                },
            ),
            html.Div(
                id=component_id,
                children=value,
                style={
                    "fontSize": "14px",
                    "fontWeight": "500",
                    "color": value_color,
                    "fontFamily": "'JetBrains Mono', 'SF Mono', monospace",
                },
            ),
            html.Div(id=value_style_id, style={"display": "none"}) if value_style_id else None,
        ],
    )


def _metric_divider() -> html.Div:
    return html.Div(style={"width": "1px", "height": "24px", "background": HAIRLINE, "flex": "0 0 auto"})


def _chart_title(unit_id: Any, view_mode_id: Any) -> html.Div:
    return html.Div(
        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px", "margin": "2px 0 8px"},
        children=[
            html.Div(
                "PnL по датам",
                style={
                    "fontSize": "12px",
                    "fontWeight": "500",
                    "color": MUTED,
                    "letterSpacing": "0.6px",
                    "textTransform": "uppercase",
                },
            ),
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "10px"},
                children=[
                    dcc.RadioItems(
                        id=view_mode_id,
                        value="breakdown",
                        options=[
                            {"label": "Доходы/расходы", "value": "breakdown"},
                            {"label": "PnL", "value": "pnl"},
                        ],
                        inline=True,
                        inputStyle={
                            "accentColor": ACCENT_BRIGHT,
                            "width": "11px",
                            "height": "11px",
                            "margin": "0 5px 0 0",
                        },
                        labelClassName="analytics-chart-mode-label",
                        className="analytics-chart-mode",
                        style={"display": "none"},
                    ),
                    html.Div(
                        id=unit_id,
                        children="USD",
                        style={"fontSize": "10px", "color": MUTED, "fontFamily": "'JetBrains Mono', 'SF Mono', monospace"},
                    ),
                ],
            ),
        ],
    )


def _referral_logo(name: str, logo_url: str | None, size: int = 36) -> html.Div:
    if logo_url:
        return html.Div(
            style={
                "width": f"{size}px",
                "height": f"{size}px",
                "borderRadius": "10px",
                "background": SURFACE,
                "border": f"1px solid {HAIRLINE}",
                "display": "grid",
                "placeItems": "center",
                "overflow": "hidden",
                "flex": "0 0 auto",
            },
            children=html.Img(
                src=logo_url,
                style={"width": "100%", "height": "100%", "objectFit": "cover"},
            ),
        )
    letters = "".join(part[:1] for part in name.split()[:2]).upper() or "R"
    return html.Div(
        style={
            "width": f"{size}px",
            "height": f"{size}px",
            "borderRadius": "10px",
            "background": SURFACE_ELEV,
            "border": f"1px solid {HAIRLINE}",
            "display": "grid",
            "placeItems": "center",
            "color": ACCENT_BRIGHT,
            "fontWeight": "600",
            "fontSize": "13px",
            "flex": "0 0 auto",
        },
        children=letters,
    )


def _dropdown(component_id: Any, label: str, values: list[str]) -> html.Div:
    return html.Div(
        className="analytics-dropdown-shell",
        children=[
            html.Label(label, style={"display": "block", "fontSize": "11px", "fontWeight": "500", "marginBottom": "5px"}),
            dcc.Dropdown(
                id=component_id,
                options=[{"label": value, "value": value} for value in values],
                multi=True,
                placeholder="\u0412\u0441\u0435",
                style={"fontSize": "12px", "color": TEXT_DIM},
            ),
        ]
    )

"""Dash callbacks for local analytics."""

from __future__ import annotations

from dash import ALL, Input, MATCH, Output, State, ctx, dcc, html

from app.analytics_dash import charts
from app.analytics_dash.data_provider import AnalyticsDataProvider
from app.analytics_dash.styles import ACCENT_BRIGHT, HAIRLINE, HAIRLINE_STRONG, MUTED, NEGATIVE, POSITIVE, SURFACE, SURFACE_ELEV, TEXT, TEXT_DIM


def register_callbacks(app, data_provider: AnalyticsDataProvider) -> None:
    """Register dashboard callbacks."""

    @app.callback(
        Output({"type": "referral-pnl-by-date", "referral": MATCH}, "figure"),
        Output({"type": "referral-total-pnl", "referral": MATCH}, "children"),
        Output({"type": "referral-delta-line", "referral": MATCH}, "children"),
        Output({"type": "referral-delta-line", "referral": MATCH}, "style"),
        Output({"type": "referral-sub-label", "referral": MATCH}, "children"),
        Output({"type": "referral-deals-count", "referral": MATCH}, "children"),
        Output({"type": "referral-avg-pnl", "referral": MATCH}, "children"),
        Output({"type": "referral-avg-pnl", "referral": MATCH}, "style"),
        Output({"type": "referral-win-rate", "referral": MATCH}, "children"),
        Output({"type": "referral-chart-unit", "referral": MATCH}, "children"),
        Input("analytics-operation-type-filter", "value"),
        Input("analytics-chart-kind", "value"),
        Input("analytics-chart-view-mode", "value"),
        Input("analytics-currency-mode", "value"),
        Input({"type": "date-from", "referral": MATCH}, "value"),
        Input({"type": "date-to", "referral": MATCH}, "value"),
        Input({"type": "currency-filter", "referral": MATCH}, "value"),
        Input({"type": "payment-agent-filter", "referral": MATCH}, "value"),
        Input({"type": "manager-filter", "referral": MATCH}, "value"),
        Input({"type": "status-filter", "referral": MATCH}, "value"),
        Input({"type": "operation-type-filter", "referral": MATCH}, "value"),
        State({"type": "referral-name", "referral": MATCH}, "data"),
    )
    def update_referral_pnl_by_date(global_operation_types, chart_kind, chart_view_mode, mode, start_date, end_date, currencies, payment_agents, managers, statuses, operation_types, referral):
        filters = {
            "start_date": start_date,
            "end_date": end_date,
            "currency": currencies or [],
            "operation_type": _merge_filter_values(global_operation_types, operation_types),
            "referral": [referral] if referral else [],
            "payment_agent": payment_agents or [],
            "manager": managers or [],
            "status": statuses or [],
        }
        payload = data_provider.get_dashboard_data(filters)
        data_key = "pnl_by_date" if mode == "usd" else "pnl_by_date_currency"
        series = payload[data_key]
        return (
            charts.pnl_by_date_figure(series, height=330, mode=mode or "usd", view_mode=chart_view_mode or "breakdown", chart_kind=chart_kind or "bar"),
            *_series_card_metrics(series, mode or "usd", "реферал"),
        )

    @app.callback(
        Output("clients-selected-referral-title", "children"),
        Output("clients-top-grid", "children"),
        Input("analytics-operation-type-filter", "value"),
        Input("clients-referral-select", "value"),
    )
    def update_clients_by_referral(global_operation_types, referral):
        if not referral:
            return "Нет рефералов", [_empty_clients_message("Выберите реферала, чтобы увидеть топ клиентов.")]
        payload = data_provider.get_dashboard_data(
            {
                "referral": [referral],
                "operation_type": _merge_filter_values(global_operation_types, []),
            }
        )
        return referral, _client_cards(payload.get("top_clients"))

    @app.callback(
        Output("client-detail-modal", "style"),
        Output("client-detail-modal-body", "children"),
        Input({"type": "client-card-open", "client": ALL}, "n_clicks"),
        Input("client-detail-close", "n_clicks"),
        State("clients-referral-select", "value"),
        State("analytics-operation-type-filter", "value"),
        State("analytics-chart-kind", "value"),
        State("analytics-chart-view-mode", "value"),
        State("analytics-currency-mode", "value"),
        prevent_initial_call=True,
    )
    def update_client_detail_modal(client_clicks, close_clicks, referral, global_operation_types, chart_kind, chart_view_mode, currency_mode):
        triggered = ctx.triggered_id
        if triggered == "client-detail-close":
            return _hidden_modal_style(), []
        if not any(int(clicks or 0) > 0 for clicks in (client_clicks or [])):
            return _hidden_modal_style(), []
        if not isinstance(triggered, dict) or triggered.get("type") != "client-card-open":
            return _hidden_modal_style(), []
        client = str(triggered.get("client") or "")
        if not client or not referral:
            return _hidden_modal_style(), []
        base_filters = {
            "referral": [referral],
            "operation_type": _merge_filter_values(global_operation_types, []),
        }
        title_client = client
        if client == "Остальные":
            top_payload = data_provider.get_dashboard_data(base_filters)
            top_clients = top_payload.get("top_clients")
            top_names = []
            if top_clients is not None and not top_clients.empty:
                top_names = [str(value) for value in top_clients["client"].tolist() if str(value) != "Остальные"]
            filters = {**base_filters, "client_exclude": top_names}
        else:
            filters = {**base_filters, "client": [client]}
        payload = data_provider.get_dashboard_data(filters)
        return _visible_modal_style(), _client_detail_body(
            title_client,
            referral,
            payload,
            chart_kind or "bar",
            chart_view_mode or "pnl",
            currency_mode or "usd",
        )

    @app.callback(
        Output({"type": "partner-pnl-by-date", "partner": MATCH}, "figure"),
        Output({"type": "partner-total-pnl", "partner": MATCH}, "children"),
        Output({"type": "partner-delta-line", "partner": MATCH}, "children"),
        Output({"type": "partner-delta-line", "partner": MATCH}, "style"),
        Output({"type": "partner-sub-label", "partner": MATCH}, "children"),
        Output({"type": "partner-deals-count", "partner": MATCH}, "children"),
        Output({"type": "partner-avg-pnl", "partner": MATCH}, "children"),
        Output({"type": "partner-avg-pnl", "partner": MATCH}, "style"),
        Output({"type": "partner-win-rate", "partner": MATCH}, "children"),
        Output({"type": "partner-chart-unit", "partner": MATCH}, "children"),
        Input("analytics-operation-type-filter", "value"),
        Input("analytics-chart-kind", "value"),
        Input("analytics-chart-view-mode", "value"),
        Input("analytics-currency-mode", "value"),
        Input({"type": "partner-date-from", "partner": MATCH}, "value"),
        Input({"type": "partner-date-to", "partner": MATCH}, "value"),
        Input({"type": "partner-currency-filter", "partner": MATCH}, "value"),
        Input({"type": "partner-referral-filter", "partner": MATCH}, "value"),
        Input({"type": "partner-manager-filter", "partner": MATCH}, "value"),
        Input({"type": "partner-status-filter", "partner": MATCH}, "value"),
        Input({"type": "partner-operation-type-filter", "partner": MATCH}, "value"),
        State({"type": "partner-name", "partner": MATCH}, "data"),
    )
    def update_partner_pnl_by_date(global_operation_types, chart_kind, chart_view_mode, mode, start_date, end_date, currencies, referrals, managers, statuses, operation_types, partner):
        filters = {
            "start_date": start_date,
            "end_date": end_date,
            "currency": currencies or [],
            "operation_type": _merge_filter_values(global_operation_types, operation_types),
            "referral": referrals or [],
            "payment_agent": [partner] if partner else [],
            "manager": managers or [],
            "status": statuses or [],
        }
        payload = data_provider.get_dashboard_data(filters)
        data_key = "pnl_by_date" if mode == "usd" else "pnl_by_date_currency"
        series = payload[data_key]
        return (
            charts.pnl_by_date_figure(series, height=330, mode=mode or "usd", view_mode=chart_view_mode or "breakdown", chart_kind=chart_kind or "bar"),
            *_series_card_metrics(series, mode or "usd", "партнер"),
        )

    @app.callback(
        Output("turnover-by-date", "figure"),
        Input("analytics-operation-type-filter", "value"),
        Input("analytics-chart-kind", "value"),
        Input("analytics-currency-mode", "value"),
        Input("turnover-date-from", "value"),
        Input("turnover-date-to", "value"),
        Input("turnover-currency-filter", "value"),
        Input("turnover-referral-filter", "value"),
        Input("turnover-payment-agent-filter", "value"),
        Input("turnover-manager-filter", "value"),
        Input("turnover-status-filter", "value"),
        Input("turnover-operation-type-filter", "value"),
    )
    def update_turnover_by_date(global_operation_types, chart_kind, mode, start_date, end_date, currencies, referrals, payment_agents, managers, statuses, operation_types):
        filters = {
            "start_date": start_date,
            "end_date": end_date,
            "currency": currencies or [],
            "operation_type": _merge_filter_values(global_operation_types, operation_types),
            "referral": referrals or [],
            "payment_agent": payment_agents or [],
            "manager": managers or [],
            "status": statuses or [],
        }
        payload = data_provider.get_dashboard_data(filters)
        data_key = "turnover_by_date_usd" if mode == "usd" else "turnover_by_date_currency"
        return charts.turnover_by_date_figure(payload[data_key], mode=mode or "usd", height=470, chart_kind=chart_kind or "bar")

    @app.callback(
        Output("roi-by-dimension", "figure"),
        Output("roi-kpis", "children"),
        Input("analytics-operation-type-filter", "value"),
        Input("analytics-chart-kind", "value"),
        Input("roi-dimension-mode", "value"),
        Input("roi-date-from", "value"),
        Input("roi-date-to", "value"),
        Input("roi-currency-filter", "value"),
        Input("roi-referral-filter", "value"),
        Input("roi-payment-agent-filter", "value"),
        Input("roi-manager-filter", "value"),
        Input("roi-status-filter", "value"),
        Input("roi-operation-type-filter", "value"),
    )
    def update_roi(global_operation_types, chart_kind, dimension, start_date, end_date, currencies, referrals, payment_agents, managers, statuses, operation_types):
        filters = {
            "start_date": start_date,
            "end_date": end_date,
            "currency": currencies or [],
            "operation_type": _merge_filter_values(global_operation_types, operation_types),
            "referral": referrals or [],
            "payment_agent": payment_agents or [],
            "manager": managers or [],
            "status": statuses or [],
        }
        payload = data_provider.get_dashboard_data(filters)
        selected_dimension = dimension or "referral"
        data_key = "roi_by_referral" if selected_dimension == "referral" else "roi_by_partner"
        series = payload[data_key]
        return charts.roi_by_dimension_figure(series, dimension=selected_dimension, height=470, chart_kind=chart_kind or "bar"), _roi_kpi_cards(series)


def _merge_filter_values(global_values, local_values) -> list[str]:
    global_list = _as_list(global_values)
    local_list = _as_list(local_values)
    if global_list and local_list:
        local_set = {value.casefold() for value in local_list}
        return [value for value in global_list if value.casefold() in local_set]
    return global_list or local_list


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _client_cards(clients) -> list[html.Div]:
    if clients is None or clients.empty:
        return [_empty_clients_message("По выбранному рефералу пока нет клиентов.")]
    cards: list[html.Div] = []
    for index, row in enumerate(clients.to_dict("records"), start=1):
        is_other = str(row.get("client") or "") == "Остальные"
        pnl = float(row.get("pnl") or 0.0)
        cards.append(
            html.Div(
                id={"type": "client-card-open", "client": str(row.get("client") or "Без клиента")},
                n_clicks=0,
                className="analytics-client-card",
                style={
                    "minHeight": "132px",
                    "padding": "14px",
                    "borderRadius": "16px",
                    "background": SURFACE if not is_other else SURFACE_ELEV,
                    "border": f"1px solid {HAIRLINE_STRONG if is_other else HAIRLINE}",
                    "boxShadow": "0 8px 24px #0F1F3D10",
                    "display": "flex",
                    "flexDirection": "column",
                    "justifyContent": "space-between",
                    "gap": "10px",
                },
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "8px"},
                        children=[
                            html.Div(
                                f"#{index}",
                                style={
                                    "fontSize": "11px",
                                    "fontWeight": "600",
                                    "color": ACCENT_BRIGHT,
                                    "padding": "4px 8px",
                                    "borderRadius": "999px",
                                    "background": "#2E6FD41A",
                                },
                            ),
                            html.Div(
                                f"{int(row.get('deals_count') or 0)} сделок",
                                style={"fontSize": "11px", "color": MUTED, "fontFamily": "'JetBrains Mono', 'SF Mono', monospace"},
                            ),
                        ],
                    ),
                    html.Div(
                        str(row.get("client") or "Без клиента"),
                        title=str(row.get("client") or "Без клиента"),
                        style={
                            "fontSize": "14px",
                            "fontWeight": "600",
                            "color": TEXT,
                            "lineHeight": "18px",
                            "minHeight": "36px",
                            "overflow": "hidden",
                            "display": "-webkit-box",
                            "WebkitLineClamp": "2",
                            "WebkitBoxOrient": "vertical",
                        },
                    ),
                    html.Div(
                        children=[
                            html.Div(
                                _format_money_value(pnl, "usd"),
                                style={
                                    "fontSize": "16px",
                                    "fontWeight": "600",
                                    "color": ACCENT_BRIGHT if pnl >= 0 else NEGATIVE,
                                    "fontFamily": "'JetBrains Mono', 'SF Mono', monospace",
                                },
                            ),
                            html.Div(
                                f"Оборот ${float(row.get('volume_usd') or 0.0):,.2f}".replace(",", " "),
                                style={"fontSize": "11px", "color": TEXT_DIM, "marginTop": "3px"},
                            ),
                        ],
                    ),
                ],
            )
        )
    return cards


def _empty_clients_message(text: str) -> html.Div:
    return html.Div(
        text,
        style={
            "gridColumn": "1 / -1",
            "padding": "22px",
            "borderRadius": "16px",
            "background": SURFACE_ELEV,
            "border": f"1px solid {HAIRLINE}",
            "color": TEXT_DIM,
            "fontSize": "13px",
        },
    )


def _visible_modal_style() -> dict[str, str]:
    return {"display": "flex"}


def _hidden_modal_style() -> dict[str, str]:
    return {"display": "none"}


def _client_detail_body(client: str, referral: str, payload, chart_kind: str, chart_view_mode: str = "pnl", currency_mode: str = "usd"):
    series = payload.get("pnl_by_date" if currency_mode == "usd" else "pnl_by_date_currency")
    rows_count = int(payload.get("rows_count") or 0)
    total = float(series["pnl"].sum()) if series is not None and not series.empty and "pnl" in series.columns else 0.0
    volume = float(series["volume_usd"].sum()) if series is not None and not series.empty and "volume_usd" in series.columns else 0.0
    win_rate = _win_rate(series) if series is not None else 0.0
    figure = charts.pnl_by_date_figure(series, height=420, mode=currency_mode, view_mode=chart_view_mode, chart_kind=chart_kind)
    return html.Div(
        children=[
            html.Div(
                style={"paddingRight": "44px", "marginBottom": "16px"},
                children=[
                    html.Div(
                        referral,
                        style={"fontSize": "11px", "fontWeight": "600", "letterSpacing": "1px", "textTransform": "uppercase", "color": ACCENT_BRIGHT},
                    ),
                    html.H3(client, style={"margin": "5px 0 6px", "fontSize": "24px", "fontWeight": "600", "color": TEXT}),
                    html.Div("PnL по датам по выбранному клиенту", style={"fontSize": "13px", "color": TEXT_DIM}),
                ],
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "repeat(4, minmax(140px, 1fr))", "gap": "10px", "marginBottom": "14px"},
                children=[
                    _roi_kpi_card("PnL", _format_money_value(total, "usd"), ACCENT_BRIGHT if total >= 0 else NEGATIVE),
                    _roi_kpi_card("Оборот", f"${volume:,.2f}".replace(",", " "), TEXT),
                    _roi_kpi_card("Сделок", f"{rows_count:,}".replace(",", " "), TEXT),
                    _roi_kpi_card("Win rate", f"{win_rate:.2f}%", ACCENT_BRIGHT if win_rate >= 50 else NEGATIVE),
                ],
            ),
            dcc.Graph(
                figure=figure,
                config={"displayModeBar": "hover", "displaylogo": False},
                style={"height": "430px"},
            ),
        ]
    )


def _roi_kpi_cards(series) -> list[html.Div]:
    if series is None or series.empty:
        return [
            _roi_kpi_card("Средняя рентабельность", "0.00%", ACCENT_BRIGHT),
            _roi_kpi_card("Лучшая рентабельность", "0.00%", ACCENT_BRIGHT),
            _roi_kpi_card("PnL", "$0.00", ACCENT_BRIGHT),
            _roi_kpi_card("Оборот", "$0.00", TEXT),
        ]
    total_pnl = float(series["pnl"].sum()) if "pnl" in series.columns else 0.0
    total_volume = float(series["volume_usd"].sum()) if "volume_usd" in series.columns else 0.0
    weighted_roi = total_pnl / total_volume * 100 if total_volume else 0.0
    best_roi = float(series["roi"].max()) if "roi" in series.columns else 0.0
    return [
        _roi_kpi_card("Средняя рентабельность", f"{weighted_roi:,.2f}%".replace(",", " "), ACCENT_BRIGHT if weighted_roi >= 0 else NEGATIVE),
        _roi_kpi_card("Лучшая рентабельность", f"{best_roi:,.2f}%".replace(",", " "), ACCENT_BRIGHT if best_roi >= 0 else NEGATIVE),
        _roi_kpi_card("PnL", _format_money_value(total_pnl, "usd"), ACCENT_BRIGHT if total_pnl >= 0 else NEGATIVE),
        _roi_kpi_card("Оборот", f"${total_volume:,.2f}".replace(",", " "), TEXT),
    ]


def _roi_kpi_card(label: str, value: str, color: str) -> html.Div:
    return html.Div(
        style={
            "padding": "12px 14px",
            "borderRadius": "14px",
            "background": SURFACE_ELEV,
            "border": f"1px solid {HAIRLINE}",
            "minHeight": "74px",
        },
        children=[
            html.Div(
                label,
                style={"fontSize": "9px", "fontWeight": "600", "letterSpacing": "0.8px", "textTransform": "uppercase", "color": MUTED, "marginBottom": "7px"},
            ),
            html.Div(
                value,
                style={"fontSize": "18px", "fontWeight": "600", "color": color, "fontFamily": "'JetBrains Mono', 'SF Mono', monospace"},
            ),
        ],
    )


def _series_card_metrics(series, mode: str, kind: str):
    total = float(series["pnl"].sum()) if not series.empty and "pnl" in series.columns else 0.0
    rows_count = int(series["deals_count"].sum()) if not series.empty and "deals_count" in series.columns else 0
    days_count = int(series["date"].nunique()) if not series.empty and "date" in series.columns else 0
    avg = total / days_count if days_count else 0.0
    win_rate = _win_rate(series)
    delta = _delta_percent(series)
    delta_positive = delta >= 0
    unit = "USD" if mode == "usd" else "Валюта"
    delta_style = _metric_text_style(POSITIVE if delta_positive else NEGATIVE, size=11)
    avg_style = _metric_text_style(ACCENT_BRIGHT if avg >= 0 else NEGATIVE, size=14)
    arrow = "▲" if delta_positive else "▼"
    return (
        _format_money_value(total, mode),
        f"{arrow} {abs(delta):.1f}% к первой половине",
        delta_style,
        f"{unit} · {kind}",
        f"{rows_count:,}".replace(",", " "),
        _format_money_value(avg, mode),
        avg_style,
        f"{win_rate:.0f}%",
        unit,
    )


def _metric_text_style(color: str, size: int) -> dict[str, str]:
    return {
        "fontSize": f"{size}px",
        "fontWeight": "500",
        "color": color,
        "fontFamily": "'JetBrains Mono', 'SF Mono', monospace",
    }


def _format_money_value(value: float, mode: str) -> str:
    sign = "+" if value >= 0 else "−"
    absolute = abs(float(value))
    number = f"{absolute:,.2f}".replace(",", " ")
    prefix = "$" if mode == "usd" else ""
    return f"{sign}{prefix}{number}"


def _win_rate(series) -> float:
    if series.empty:
        return 0.0
    if "winning_deals_count" in series.columns and "deals_count" in series.columns:
        total = int(series["deals_count"].sum())
        if not total:
            return 0.0
        winners = int(series["winning_deals_count"].sum())
        return winners / total * 100
    if "pnl" not in series.columns:
        return 0.0
    total = len(series)
    if not total:
        return 0.0
    winners = int((series["pnl"] >= 0).sum())
    return winners / total * 100


def _delta_percent(series) -> float:
    if series.empty or "pnl" not in series.columns or len(series) < 2:
        return 0.0
    values = series.sort_values("date")["pnl"].astype(float).tolist()
    midpoint = max(1, len(values) // 2)
    previous = sum(values[:midpoint])
    current = sum(values[midpoint:])
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return (current - previous) / abs(previous) * 100

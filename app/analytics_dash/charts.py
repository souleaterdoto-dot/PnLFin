"""Plotly chart builders for the local analytics dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.analytics_dash.styles import CHART_TEMPLATE, COLORS


def pnl_by_date_figure(
    data: pd.DataFrame,
    height: int = 340,
    mode: str = "usd",
    view_mode: str = "breakdown",
    chart_kind: str = "bar",
) -> go.Figure:
    """Build PnL by date histogram with detailed hover information."""
    is_usd = mode == "usd"
    title = "PnL по датам"
    if data.empty:
        return _empty_figure(title)
    chart_data = data.copy()
    chart_data["date"] = pd.to_datetime(chart_data["date"], errors="coerce")
    chart_data = chart_data.dropna(subset=["date"]).sort_values("date")
    if chart_data.empty:
        return _empty_figure(title)

    for column in (
        "gross_income",
        "total_costs",
        "client_percent_fee",
        "fixed_commission",
        "swift_income",
        "agent_commission",
        "swift_agent_commission",
        "referral_commission",
        "repeat_penalty",
        "deals_count",
        "volume_usd" if is_usd else "volume",
    ):
        if column not in chart_data.columns:
            chart_data[column] = 0.0

    chart_data["date_label"] = chart_data["date"].dt.strftime("%d.%m.%Y")
    volume_column = "volume_usd" if is_usd else "volume"
    unit_label = "USD" if is_usd else "\u0432 \u0432\u0430\u043b\u044e\u0442\u0435"

    if view_mode == "pnl":
        return _pnl_net_by_date_figure(chart_data, height, is_usd, unit_label, volume_column, chart_kind)
    if chart_kind == "pie":
        return _pnl_breakdown_pie_figure(chart_data, height, is_usd, unit_label, volume_column)

    figure = go.Figure()
    custom_columns = [
        "date_label",
        "pnl",
        "gross_income",
        "total_costs",
        "client_percent_fee",
        "fixed_commission",
        "swift_income",
        "agent_commission",
        "swift_agent_commission",
        "referral_commission",
        "repeat_penalty",
        "deals_count",
        volume_column,
    ]

    if not is_usd and "currency" in chart_data.columns:
        for currency in sorted(chart_data["currency"].dropna().astype(str).unique()):
            currency_data = chart_data[chart_data["currency"].astype(str) == currency]
            custom_columns_with_currency = ["currency", *custom_columns]
            figure.add_trace(
                _timeline_trace(
                    chart_kind,
                    x=currency_data["date"],
                    y=currency_data["gross_income"],
                    name=f"{currency} доходы",
                    legendgroup=currency,
                    offsetgroup=currency,
                    mode="lines+markers" if chart_kind == "line" else None,
                    marker_color=COLORS["primary"],
                    line={"color": COLORS["primary"], "width": 3} if chart_kind == "line" else None,
                    opacity=0.86,
                    marker_line={"color": COLORS["surface"], "width": 1},
                    marker={"cornerradius": 3},
                    customdata=currency_data[custom_columns_with_currency],
                    hovertemplate=_pnl_stack_hover_template(unit_label, has_currency=True),
                )
            )
            figure.add_trace(
                _timeline_trace(
                    chart_kind,
                    x=currency_data["date"],
                    y=-currency_data["total_costs"],
                    name=f"{currency} расходы",
                    legendgroup=currency,
                    offsetgroup=currency,
                    mode="lines+markers" if chart_kind == "line" else None,
                    marker_color=COLORS["danger"],
                    line={"color": COLORS["danger"], "width": 3} if chart_kind == "line" else None,
                    opacity=0.76,
                    marker_line={"color": COLORS["surface"], "width": 1},
                    marker={"cornerradius": 3},
                    customdata=currency_data[custom_columns_with_currency],
                    hovertemplate=_pnl_stack_hover_template(unit_label, has_currency=True),
                )
            )
    else:
        figure.add_trace(
            _timeline_trace(
                chart_kind,
                x=chart_data["date"],
                y=chart_data["gross_income"],
                name="Доходы",
                mode="lines+markers" if chart_kind == "line" else None,
                marker_color=COLORS["primary"],
                line={"color": COLORS["primary"], "width": 3} if chart_kind == "line" else None,
                opacity=0.88,
                marker_line={"color": COLORS["surface"], "width": 1},
                marker={"cornerradius": 3},
                customdata=chart_data[custom_columns],
                hovertemplate=_pnl_stack_hover_template(unit_label),
            )
        )
        figure.add_trace(
            _timeline_trace(
                chart_kind,
                x=chart_data["date"],
                y=-chart_data["total_costs"],
                name="Расходы",
                mode="lines+markers" if chart_kind == "line" else None,
                marker_color=COLORS["danger"],
                line={"color": COLORS["danger"], "width": 3} if chart_kind == "line" else None,
                opacity=0.78,
                marker_line={"color": COLORS["surface"], "width": 1},
                marker={"cornerradius": 3},
                customdata=chart_data[custom_columns],
                hovertemplate=_pnl_stack_hover_template(unit_label),
            )
        )

    figure.add_hline(y=0, line_width=1, line_dash="dash", line_color=COLORS["muted"])
    figure.update_layout(
        barmode="relative",
        bargap=0.42,
        height=height,
        showlegend=True,
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"size": 10, "color": COLORS["muted"]}},
    )
    return _style_pnl_figure(figure, title, is_usd=is_usd)


def _timeline_trace(chart_kind: str, **kwargs):
    color = kwargs.pop("marker_color", COLORS["primary"])
    line = kwargs.pop("line", None)
    kwargs.pop("mode", None)
    marker_line = kwargs.pop("marker_line", None)
    marker = kwargs.pop("marker", None)
    opacity = kwargs.pop("opacity", None)
    if chart_kind == "line":
        kwargs.pop("offsetgroup", None)
        line_color = color if isinstance(color, str) else COLORS["primary"]
        return go.Scatter(
            **kwargs,
            mode="lines+markers",
            line=line or {"color": line_color, "width": 3},
            marker={"color": color, "size": 7},
            opacity=opacity,
        )
    return go.Bar(
        **kwargs,
        marker_color=color,
        marker_line=marker_line,
        marker=marker,
        opacity=opacity,
    )


def _pnl_breakdown_pie_figure(chart_data: pd.DataFrame, height: int, is_usd: bool, unit_label: str, volume_column: str) -> go.Figure:
    income = float(chart_data["gross_income"].sum())
    costs = float(chart_data["total_costs"].sum())
    pnl = income - costs
    figure = go.Figure(
        go.Pie(
            labels=["\u0414\u043e\u0445\u043e\u0434\u044b", "\u0420\u0430\u0441\u0445\u043e\u0434\u044b"],
            values=[abs(income), abs(costs)],
            hole=0.58,
            marker={"colors": [COLORS["primary"], COLORS["danger"]]},
            customdata=[[pnl, int(chart_data["deals_count"].sum()), float(chart_data[volume_column].sum())]] * 2,
            hovertemplate=(
                "<b>%{label}</b><br>"
                "\u0421\u0443\u043c\u043c\u0430: %{value:,.2f} " + unit_label + "<br>"
                "PnL: %{customdata[0]:,.2f} " + unit_label + "<br>"
                "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[1]:,.0f}<br>"
                "\u041e\u0431\u043e\u0440\u043e\u0442: %{customdata[2]:,.2f} " + unit_label +
                "<extra></extra>"
            ),
        )
    )
    figure.update_layout(height=height, showlegend=True)
    return _style_figure(figure, "\u0414\u043e\u0445\u043e\u0434\u044b / \u0440\u0430\u0441\u0445\u043e\u0434\u044b")


def _pnl_net_pie_figure(chart_data: pd.DataFrame, height: int, is_usd: bool, unit_label: str, volume_column: str) -> go.Figure:
    positive = float(chart_data.loc[chart_data["pnl"] >= 0, "pnl"].sum())
    negative = abs(float(chart_data.loc[chart_data["pnl"] < 0, "pnl"].sum()))
    if positive == 0 and negative == 0:
        return _empty_figure("PnL")
    figure = go.Figure(
        go.Pie(
            labels=["\u041f\u0440\u0438\u0431\u044b\u043b\u044c", "\u0423\u0431\u044b\u0442\u043a\u0438"],
            values=[positive, negative],
            hole=0.58,
            marker={"colors": [COLORS["primary"], COLORS["danger"]]},
            customdata=[[int(chart_data["deals_count"].sum()), float(chart_data[volume_column].sum())]] * 2,
            hovertemplate=(
                "<b>%{label}</b><br>"
                "\u0421\u0443\u043c\u043c\u0430: %{value:,.2f} " + unit_label + "<br>"
                "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[0]:,.0f}<br>"
                "\u041e\u0431\u043e\u0440\u043e\u0442: %{customdata[1]:,.2f} " + unit_label +
                "<extra></extra>"
            ),
        )
    )
    figure.update_layout(height=height, showlegend=True)
    return _style_figure(figure, "PnL")


def _pnl_net_by_date_figure(chart_data: pd.DataFrame, height: int, is_usd: bool, unit_label: str, volume_column: str, chart_kind: str = "bar") -> go.Figure:
    if chart_kind == "pie":
        return _pnl_net_pie_figure(chart_data, height, is_usd, unit_label, volume_column)
    figure = go.Figure()
    custom_columns = [
        "date_label",
        "pnl",
        "gross_income",
        "total_costs",
        "client_percent_fee",
        "fixed_commission",
        "swift_income",
        "agent_commission",
        "swift_agent_commission",
        "referral_commission",
        "repeat_penalty",
        "deals_count",
        volume_column,
    ]
    if not is_usd and "currency" in chart_data.columns:
        for currency in sorted(chart_data["currency"].dropna().astype(str).unique()):
            currency_data = chart_data[chart_data["currency"].astype(str) == currency]
            custom_columns_with_currency = ["currency", *custom_columns]
            figure.add_trace(
                _timeline_trace(
                    chart_kind,
                    x=currency_data["date"],
                    y=currency_data["pnl"],
                    name=currency,
                    marker_color=COLORS["primary"],
                    opacity=0.86,
                    marker_line={"color": COLORS["surface"], "width": 1},
                    marker={"cornerradius": 3},
                    customdata=currency_data[custom_columns_with_currency],
                    hovertemplate=_pnl_net_hover_template(unit_label, has_currency=True),
                )
            )
    else:
        figure.add_trace(
            _timeline_trace(
                chart_kind,
                x=chart_data["date"],
                y=chart_data["pnl"],
                name="PnL",
                marker_color=[COLORS["primary"] if value >= 0 else COLORS["danger"] for value in chart_data["pnl"]],
                opacity=0.88,
                marker_line={"color": COLORS["surface"], "width": 1},
                marker={"cornerradius": 3},
                customdata=chart_data[custom_columns],
                hovertemplate=_pnl_net_hover_template(unit_label),
            )
        )
    figure.add_hline(y=0, line_width=1, line_dash="dash", line_color=COLORS["muted"])
    figure.update_layout(
        barmode="group",
        bargap=0.46,
        height=height,
        showlegend=not is_usd,
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"size": 10, "color": COLORS["muted"]}},
    )
    return _style_pnl_figure(figure, "PnL по датам", is_usd=is_usd)


def pnl_by_currency_figure(data: pd.DataFrame) -> go.Figure:
    """Build PnL by currency bar chart."""
    title = "PnL \u043f\u043e \u0432\u0430\u043b\u044e\u0442\u0430\u043c"
    if data.empty:
        return _empty_figure(title)
    figure = px.bar(data, x="currency", y="pnl", template=CHART_TEMPLATE, color="pnl", color_continuous_scale=[COLORS["surface_alt"], COLORS["primary"]])
    return _style_figure(figure, title, "\u0412\u0430\u043b\u044e\u0442\u0430", "PnL, USD")


def pnl_by_manager_figure(data: pd.DataFrame) -> go.Figure:
    """Build PnL by manager horizontal bar chart."""
    return _pnl_horizontal_bar(data, "manager", "PnL \u043f\u043e \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430\u043c")


def pnl_by_partner_figure(data: pd.DataFrame) -> go.Figure:
    """Build PnL by payment partner horizontal bar chart."""
    return _pnl_horizontal_bar(data, "partner", "PnL \u043f\u043e \u043f\u0430\u0440\u0442\u043d\u0435\u0440\u0430\u043c")


def volume_by_date_figure(data: pd.DataFrame) -> go.Figure:
    """Build volume by date bar chart."""
    title = "\u041e\u0431\u044a\u0435\u043c \u043f\u043e \u0434\u0430\u0442\u0430\u043c"
    if data.empty:
        return _empty_figure(title)
    figure = px.bar(data, x="date", y="volume", template=CHART_TEMPLATE)
    figure.update_traces(marker_color=COLORS["primary"])
    return _style_figure(figure, title, "\u0414\u0430\u0442\u0430", "\u041e\u0431\u044a\u0435\u043c")


def turnover_by_date_figure(data: pd.DataFrame, mode: str = "usd", height: int = 460, chart_kind: str = "bar") -> go.Figure:
    """Build turnover by date chart in USD or native deal currencies."""
    is_usd = mode == "usd"
    title = "\u041e\u0431\u043e\u0440\u043e\u0442\u044b \u0432 USD" if is_usd else "\u041e\u0431\u043e\u0440\u043e\u0442\u044b \u0432 \u0432\u0430\u043b\u044e\u0442\u0435"
    if data.empty:
        return _empty_figure(title)
    chart_data = data.copy()
    chart_data["date"] = pd.to_datetime(chart_data["date"], errors="coerce")
    chart_data = chart_data.dropna(subset=["date"]).sort_values("date")
    if chart_data.empty:
        return _empty_figure(title)
    chart_data["date_label"] = chart_data["date"].dt.strftime("%d.%m.%Y")
    if "deals_count" not in chart_data.columns:
        chart_data["deals_count"] = 0
    if chart_kind == "pie":
        return _turnover_pie_figure(chart_data, is_usd, title, height)

    if is_usd:
        figure = go.Figure()
        figure.add_trace(
            _timeline_trace(
                chart_kind,
                x=chart_data["date"],
                y=chart_data["turnover"],
                name="\u041e\u0431\u043e\u0440\u043e\u0442",
                marker_color=COLORS["primary"],
                line={"color": COLORS["primary"], "width": 3},
                opacity=0.86,
                marker_line={"color": COLORS["surface"], "width": 1},
                customdata=chart_data[["date_label", "deals_count"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "\u041e\u0431\u043e\u0440\u043e\u0442: %{y:,.2f} USD<br>"
                    "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[1]:,.0f}"
                    "<extra></extra>"
                ),
            )
        )
        y_title = "\u041e\u0431\u043e\u0440\u043e\u0442, USD"
    else:
        chart_factory = px.line if chart_kind == "line" else px.bar
        figure = chart_factory(
            chart_data,
            x="date",
            y="turnover",
            color="currency",
            template=CHART_TEMPLATE,
            custom_data=["date_label", "currency", "deals_count"],
            **({} if chart_kind == "line" else {"barmode": "group"}),
        )
        trace_style = {
            "opacity": 0.86,
            "hovertemplate": (
                "<b>%{customdata[0]}</b><br>"
                "\u0412\u0430\u043b\u044e\u0442\u0430: %{customdata[1]}<br>"
                "\u041e\u0431\u043e\u0440\u043e\u0442: %{y:,.2f}<br>"
                "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[2]:,.0f}"
                "<extra></extra>"
            ),
        }
        if chart_kind == "line":
            trace_style["mode"] = "lines+markers"
        else:
            trace_style["marker_line"] = {"color": COLORS["surface"], "width": 1}
        figure.update_traces(**trace_style)
        y_title = "\u041e\u0431\u043e\u0440\u043e\u0442 \u0432 \u0432\u0430\u043b\u044e\u0442\u0435"
    figure.update_layout(height=height, bargap=0.22, legend_title_text="")
    return _style_figure(figure, title, "\u0414\u0430\u0442\u0430", y_title)


def _turnover_pie_figure(chart_data: pd.DataFrame, is_usd: bool, title: str, height: int) -> go.Figure:
    if is_usd:
        grouped = chart_data.groupby("date_label", as_index=False).agg(turnover=("turnover", "sum"), deals_count=("deals_count", "sum"))
        labels = grouped["date_label"]
    else:
        grouped = chart_data.groupby("currency", as_index=False).agg(turnover=("turnover", "sum"), deals_count=("deals_count", "sum"))
        labels = grouped["currency"]
    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=grouped["turnover"],
            hole=0.58,
            marker={"colors": [COLORS["primary"], COLORS["primary_dark"], COLORS["success"], COLORS["danger"], COLORS["muted"]]},
            customdata=grouped[["deals_count"]],
            hovertemplate="<b>%{label}</b><br>\u041e\u0431\u043e\u0440\u043e\u0442: %{value:,.2f}<br>\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[0]:,.0f}<extra></extra>",
        )
    )
    figure.update_layout(height=height, showlegend=True)
    return _style_figure(figure, title)


def roi_by_dimension_figure(data: pd.DataFrame, dimension: str = "referral", height: int = 470, chart_kind: str = "bar") -> go.Figure:
    """Build profitability ranking by referrals or partners."""
    label_column = "referral" if dimension == "referral" else "partner"
    title = "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u043f\u043e \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u0430\u043c" if dimension == "referral" else "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u043f\u043e \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u0430\u043c"
    if data.empty or label_column not in data.columns:
        return _empty_figure(title)
    chart_data = data.copy().sort_values("roi", ascending=True).tail(24)
    chart_data["label"] = chart_data[label_column].fillna("\u0411\u0435\u0437 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u044f").astype(str)

    if chart_kind == "pie":
        figure = go.Figure(
            go.Pie(
                labels=chart_data["label"],
                values=chart_data["roi"].abs(),
                hole=0.58,
                marker={"colors": [COLORS["primary"], COLORS["primary_dark"], COLORS["success"], COLORS["danger"], COLORS["muted"]]},
                customdata=chart_data[["roi", "pnl", "volume_usd", "deals_count"]],
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c: %{customdata[0]:.2f}%<br>"
                    "PnL: $%{customdata[1]:,.2f}<br>"
                    "\u041e\u0431\u043e\u0440\u043e\u0442: $%{customdata[2]:,.2f}<br>"
                    "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[3]:,.0f}"
                    "<extra></extra>"
                ),
            )
        )
        figure.update_layout(height=height, showlegend=True)
        return _style_figure(figure, title)

    if chart_kind == "line":
        chart_data = chart_data.sort_values("roi", ascending=False).reset_index(drop=True)
        figure = go.Figure(
            go.Scatter(
                x=chart_data["label"],
                y=chart_data["roi"],
                mode="lines+markers",
                line={"color": COLORS["primary"], "width": 3},
                marker={"color": [COLORS["primary"] if value >= 0 else COLORS["danger"] for value in chart_data["roi"]], "size": 8},
                customdata=chart_data[["pnl", "volume_usd", "deals_count"]],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c: %{y:.2f}%<br>"
                    "PnL: $%{customdata[0]:,.2f}<br>"
                    "\u041e\u0431\u043e\u0440\u043e\u0442: $%{customdata[1]:,.2f}<br>"
                    "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[2]:,.0f}"
                    "<extra></extra>"
                ),
            )
        )
        figure.add_hline(y=0, line_width=1, line_dash="dash", line_color=COLORS["muted"])
        figure.update_layout(height=height, showlegend=False)
        styled = _style_figure(figure, title, "", "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c, %")
        styled.update_yaxes(ticksuffix="%", tickformat=",.2f")
        return styled

    figure = go.Figure(
        go.Bar(
            x=chart_data["roi"],
            y=chart_data["label"],
            orientation="h",
            marker_color=[COLORS["primary"] if value >= 0 else COLORS["danger"] for value in chart_data["roi"]],
            opacity=0.88,
            marker_line={"color": COLORS["surface"], "width": 1},
            customdata=chart_data[["pnl", "volume_usd", "deals_count"]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c: %{x:.2f}%<br>"
                "PnL: $%{customdata[0]:,.2f}<br>"
                "\u041e\u0431\u043e\u0440\u043e\u0442: $%{customdata[1]:,.2f}<br>"
                "\u0421\u0434\u0435\u043b\u043e\u043a: %{customdata[2]:,.0f}"
                "<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=0, line_width=1, line_dash="dash", line_color=COLORS["muted"])
    figure.update_layout(height=height, bargap=0.28, showlegend=False)
    styled = _style_figure(figure, title, "\u0420\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c, %", "")
    styled.update_xaxes(ticksuffix="%", tickformat=",.2f")
    styled.update_yaxes(tickfont={"size": 11, "color": COLORS["text_dim"]})
    return styled

def _pnl_stack_hover_template(unit_label: str, has_currency: bool = False) -> str:
    offset = 1 if has_currency else 0
    currency_line = "\u0412\u0430\u043b\u044e\u0442\u0430: %{customdata[0]}<br>" if has_currency else ""
    return (
        f"<b>%{{customdata[{offset}]}}</b><br>"
        f"{currency_line}"
        f"\u0414\u043e\u0445\u043e\u0434\u044b: %{{customdata[{offset + 2}]:,.2f}} {unit_label}<br>"
        f"\u0420\u0430\u0441\u0445\u043e\u0434\u044b: −%{{customdata[{offset + 3}]:,.2f}} {unit_label}<br>"
        f"<b>PnL: %{{customdata[{offset + 1}]:,.2f}} {unit_label}</b><br>"
        "<br>"
        f"\u0421\u0442\u0430\u0432\u043a\u0430 \u043a\u043b\u0438\u0435\u043d\u0442\u0430 %: %{{customdata[{offset + 4}]:,.2f}} {unit_label}<br>"
        f"\u0424\u0438\u043a\u0441. \u043a\u043e\u043c\u0438\u0441\u0441\u0438\u044f: %{{customdata[{offset + 5}]:,.2f}} {unit_label}<br>"
        f"SWIFT: %{{customdata[{offset + 6}]:,.2f}} {unit_label}<br>"
        f"\u041a\u043e\u043c\u0438\u0441\u0441\u0438\u044f \u041f\u0410: %{{customdata[{offset + 7}]:,.2f}} {unit_label}<br>"
        f"SWIFT \u041f\u0410: %{{customdata[{offset + 8}]:,.2f}} {unit_label}<br>"
        f"\u0421\u0442\u0430\u0432\u043a\u0430 \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u0430: %{{customdata[{offset + 9}]:,.2f}} {unit_label}<br>"
        f"\u0428\u0442\u0440\u0430\u0444: %{{customdata[{offset + 10}]:,.2f}} {unit_label}<br>"
        "<br>"
        f"\u0421\u0434\u0435\u043b\u043e\u043a: %{{customdata[{offset + 11}]:,.0f}}<br>"
        f"\u041e\u0431\u044a\u0435\u043c: %{{customdata[{offset + 12}]:,.2f}} {unit_label}"
        "<extra></extra>"
    )


def _pnl_net_hover_template(unit_label: str, has_currency: bool = False) -> str:
    offset = 1 if has_currency else 0
    currency_line = "\u0412\u0430\u043b\u044e\u0442\u0430: %{customdata[0]}<br>" if has_currency else ""
    return (
        f"<b>%{{customdata[{offset}]}}</b><br>"
        f"{currency_line}"
        f"<b>PnL: %{{y:,.2f}} {unit_label}</b><br>"
        f"\u0414\u043e\u0445\u043e\u0434\u044b: %{{customdata[{offset + 2}]:,.2f}} {unit_label}<br>"
        f"\u0420\u0430\u0441\u0445\u043e\u0434\u044b: %{{customdata[{offset + 3}]:,.2f}} {unit_label}<br>"
        "<br>"
        f"\u0421\u0442\u0430\u0432\u043a\u0430 \u043a\u043b\u0438\u0435\u043d\u0442\u0430 %: %{{customdata[{offset + 4}]:,.2f}} {unit_label}<br>"
        f"\u0424\u0438\u043a\u0441. \u043a\u043e\u043c\u0438\u0441\u0441\u0438\u044f: %{{customdata[{offset + 5}]:,.2f}} {unit_label}<br>"
        f"SWIFT: %{{customdata[{offset + 6}]:,.2f}} {unit_label}<br>"
        f"\u041a\u043e\u043c\u0438\u0441\u0441\u0438\u044f \u041f\u0410: %{{customdata[{offset + 7}]:,.2f}} {unit_label}<br>"
        f"SWIFT \u041f\u0410: %{{customdata[{offset + 8}]:,.2f}} {unit_label}<br>"
        f"\u0421\u0442\u0430\u0432\u043a\u0430 \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u0430: %{{customdata[{offset + 9}]:,.2f}} {unit_label}<br>"
        f"\u0428\u0442\u0440\u0430\u0444: %{{customdata[{offset + 10}]:,.2f}} {unit_label}<br>"
        "<br>"
        f"\u0421\u0434\u0435\u043b\u043e\u043a: %{{customdata[{offset + 11}]:,.0f}}<br>"
        f"\u041e\u0431\u044a\u0435\u043c: %{{customdata[{offset + 12}]:,.2f}} {unit_label}"
        "<extra></extra>"
    )


def deals_by_status_figure(data: pd.DataFrame) -> go.Figure:
    """Build donut chart for operations by payment status."""
    title = "\u0421\u0434\u0435\u043b\u043a\u0438 \u043f\u043e \u0441\u0442\u0430\u0442\u0443\u0441\u0430\u043c"
    if data.empty:
        return _empty_figure(title)
    figure = px.pie(
        data,
        names="status",
        values="count",
        hole=0.58,
        template=CHART_TEMPLATE,
        color_discrete_sequence=[COLORS["primary"], COLORS["primary_dark"], COLORS["success"], COLORS["danger"], COLORS["muted"]],
    )
    figure.update_traces(textposition="inside", textinfo="percent+label")
    return _style_figure(figure, title)


def pnl_by_referral_figure(data: pd.DataFrame) -> go.Figure:
    """Build treemap for PnL by referral."""
    title = "PnL \u043f\u043e \u0440\u0435\u0444\u0435\u0440\u0430\u043b\u0430\u043c"
    if data.empty:
        return _empty_figure(title)
    chart_data = data.copy()
    chart_data["size"] = chart_data["pnl"].abs()
    chart_data = chart_data[chart_data["size"] > 0]
    if chart_data.empty:
        return _empty_figure(title)
    figure = px.treemap(
        chart_data,
        path=["referral"],
        values="size",
        color="pnl",
        color_continuous_scale=[COLORS["surface_alt"], COLORS["primary"]],
        hover_data={"pnl": ":,.0f", "size": False},
    )
    return _style_figure(figure, title)


def pnl_waterfall_figure(data: pd.DataFrame) -> go.Figure:
    """Build waterfall chart for PnL components."""
    title = "\u041a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u044b PnL"
    if data.empty:
        return _empty_figure(title)
    figure = go.Figure(
        go.Waterfall(
            x=data["component"],
            y=data["value"],
            measure=data["measure"],
            connector={"line": {"color": COLORS["muted"]}},
            increasing={"marker": {"color": COLORS["success"]}},
            decreasing={"marker": {"color": COLORS["danger"]}},
            totals={"marker": {"color": COLORS["primary"]}},
        )
    )
    return _style_figure(figure, title, "", "USD")


def _pnl_horizontal_bar(data: pd.DataFrame, label_column: str, title: str) -> go.Figure:
    if data.empty:
        return _empty_figure(title)
    chart_data = data.sort_values("pnl", ascending=True).tail(20)
    figure = px.bar(
        chart_data,
        x="pnl",
        y=label_column,
        orientation="h",
        template=CHART_TEMPLATE,
        color="pnl",
        color_continuous_scale=[COLORS["surface_alt"], COLORS["primary"]],
    )
    return _style_figure(figure, title, "PnL, USD", "")


def _style_figure(figure: go.Figure, title: str, x_title: str | None = None, y_title: str | None = None) -> go.Figure:
    figure.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left", "font": {"size": 17, "color": COLORS["text"]}},
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        margin={"l": 42, "r": 22, "t": 58, "b": 42},
        font={"family": "Inter, Segoe UI, Arial", "color": COLORS["text"]},
        xaxis_title=x_title,
        yaxis_title=y_title,
        hovermode="x unified",
        hoverlabel={
            "bgcolor": COLORS["text"],
            "font": {"color": COLORS["surface"], "family": "Inter, Segoe UI, Arial"},
            "bordercolor": COLORS["text"],
        },
    )
    figure.update_xaxes(showgrid=False, zeroline=False)
    figure.update_yaxes(gridcolor=COLORS["surface_alt"], zeroline=False)
    return figure


def _style_pnl_figure(figure: go.Figure, title: str, is_usd: bool) -> go.Figure:
    figure = _style_figure(figure, "", None, None)
    figure.update_layout(
        title=None,
        margin={"l": 38, "r": 18, "t": 12, "b": 34},
        hovermode="closest",
    )
    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        tickformat="%d.%m",
        tickfont={"size": 10, "color": COLORS["muted"]},
        title=None,
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor=COLORS["surface_alt"],
        gridwidth=1,
        zeroline=False,
        tickformat=",.0f",
        tickprefix="$" if is_usd else "",
        tickfont={"size": 10, "color": COLORS["muted"]},
        title=None,
    )
    return figure


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text="\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16, "color": COLORS["muted"]},
    )
    return _style_figure(figure, title)

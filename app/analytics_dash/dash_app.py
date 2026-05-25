"""Dash app factory for local Plotly analytics."""

from __future__ import annotations

from pathlib import Path
import sys

from dash import Dash
from flask import abort, send_from_directory

from app.analytics_dash.callbacks import register_callbacks
from app.analytics_dash.data_provider import AnalyticsDataProvider
from app.analytics_dash.layout import create_layout
from app.analytics_dash.styles import CUSTOM_CSS


def create_dash_app(db_path: Path) -> Dash:
    """Create and configure the local Dash application."""
    data_provider = AnalyticsDataProvider(db_path)
    app = Dash(
        __name__,
        title="Finance PnL Analytics",
        suppress_callback_exceptions=True,
        update_title=None,
    )
    app.index_string = _index_string()
    app.layout = create_layout(data_provider.get_initial_state())
    _register_asset_route(app)
    register_callbacks(app, data_provider)
    return app


def _index_string() -> str:
    return f"""<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>{CUSTOM_CSS}</style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>"""


def _register_asset_route(app: Dash) -> None:
    """Serve bundled app assets for the local Dash page only."""
    root = Path(getattr(sys, "_MEIPASS", Path.cwd())).resolve()
    assets_root = (root / "assets").resolve()

    @app.server.route("/local-assets/<path:asset_path>")
    def local_asset(asset_path: str):
        candidate = (assets_root / asset_path).resolve()
        if not str(candidate).startswith(str(assets_root)) or not candidate.exists():
            abort(404)
        return send_from_directory(assets_root, asset_path)

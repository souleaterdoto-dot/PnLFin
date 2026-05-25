"""Local Dash server lifecycle management."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from app.database.connection import DEFAULT_DB_PATH


@dataclass(frozen=True, slots=True)
class AnalyticsServerStatus:
    """Current local analytics server state."""

    is_running: bool
    url: str | None = None
    error_message: str | None = None


LOCAL_ANALYTICS_HOST = "127.0.0.1"


class AnalyticsServerService:
    """Start and stop a single local Dash server instance."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, host: str = LOCAL_ANALYTICS_HOST, default_port: int = 8050) -> None:
        self._db_path = Path(db_path)
        self._host = LOCAL_ANALYTICS_HOST
        self._public_host = LOCAL_ANALYTICS_HOST
        self._default_port = default_port
        self._lock = threading.Lock()
        self._server = None
        self._thread: threading.Thread | None = None
        self._url: str | None = None
        self._error_message: str | None = None

    @property
    def url(self) -> str | None:
        """Return current dashboard URL if the server is running."""
        return self._url

    def ensure_started(self) -> AnalyticsServerStatus:
        """Start the Dash server once and return its status."""
        with self._lock:
            if self._server is not None and self._thread is not None and self._thread.is_alive():
                return AnalyticsServerStatus(is_running=True, url=self._url)

            try:
                from werkzeug.serving import make_server

                from app.analytics_dash.dash_app import create_dash_app
            except Exception as exc:
                self._error_message = (
                    "Dash/Plotly не установлены. Установите зависимости из requirements.txt "
                    f"и перезапустите приложение. Детали: {exc}"
                )
                return AnalyticsServerStatus(is_running=False, error_message=self._error_message)

            try:
                port = self._find_free_port(self._default_port)
                dash_app = create_dash_app(self._db_path)
                self._server = make_server(self._host, port, dash_app.server, threaded=True)
                self._url = f"http://{self._public_host}:{port}"
                self._thread = threading.Thread(
                    target=self._server.serve_forever,
                    name="FinancePnLAnalyticsDash",
                    daemon=True,
                )
                self._thread.start()
                if not self._wait_until_ready(self._url):
                    raise RuntimeError("Dash server did not respond in time")
            except Exception as exc:
                self._server = None
                self._thread = None
                self._url = None
                self._error_message = f"Не удалось запустить локальную аналитику: {exc}"
                return AnalyticsServerStatus(is_running=False, error_message=self._error_message)

            self._error_message = None
            return AnalyticsServerStatus(is_running=True, url=self._url)

    def stop(self) -> None:
        """Stop the local Dash server if it was started."""
        with self._lock:
            if self._server is None:
                return
            try:
                self._server.shutdown()
            finally:
                if self._thread is not None:
                    self._thread.join(timeout=1.5)
                self._server = None
                self._thread = None
                self._url = None

    def _find_free_port(self, start_port: int) -> int:
        port = start_port
        while port < start_port + 100:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((self._host, port))
                except OSError:
                    port += 1
                    continue
                return port
        raise RuntimeError("No free localhost port found for analytics dashboard")

    @staticmethod
    def _wait_until_ready(url: str) -> bool:
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            try:
                with urlopen(url, timeout=0.4) as response:
                    return response.status < 500
            except Exception:
                time.sleep(0.08)
        return False

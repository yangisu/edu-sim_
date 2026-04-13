from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(204, {})

    def do_GET(self) -> None:  # noqa: N802
        self._send_json(
            200,
            {
                "ok": True,
                "service": "EvalBuddy API",
                "time_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if status != 204:
            self.wfile.write(body)

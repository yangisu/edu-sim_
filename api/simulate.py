from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

from index import _run_simulation


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(204, {})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json_body()
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"error": "invalid_json", "message": str(exc)})
            return

        try:
            report = _run_simulation(payload)
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"error": "simulation_failed", "message": str(exc)})
            return
        self._send_json(200, {"ok": True, "report": report})

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

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

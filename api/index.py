from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from edu_sim.orchestrator import WorkflowService  # noqa: E402
from edu_sim.repository import Repository  # noqa: E402
from edu_sim.student_profile_factory import (  # noqa: E402
    create_specific_student_row,
    create_synthetic_students,
    parse_student_row,
)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(204, {})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html", "/web/index.html"}:
            self._send_text(200, _load_web_index(), content_type="text/html; charset=utf-8")
            return
        if path in {"/favicon.ico", "/favicon.png"}:
            self._send_json(204, {})
            return
        if path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "EvalBuddy API",
                    "time_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            return
        if path == "/api/sample-payload":
            self._send_json(200, _sample_payload())
            return
        if not path.startswith("/api/"):
            self._send_text(200, _load_web_index(), content_type="text/html; charset=utf-8")
            return
        self._send_json(404, {"error": "not_found", "message": f"unknown path: {path}"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/simulate":
            self._send_json(404, {"error": "not_found", "message": f"unknown path: {path}"})
            return

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

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
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

    def _send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if status != 204:
            self.wfile.write(body)


def _run_simulation(payload: dict[str, Any]) -> dict[str, Any]:
    lecture_title = str(payload.get("lecture_title", "교육 평가")).strip() or "교육 평가"
    lecture_content = str(payload.get("lecture_content", "")).strip()
    lecture_package = payload.get("lecture_package")
    if lecture_package is not None and not isinstance(lecture_package, dict):
        raise ValueError("lecture_package must be an object")

    if lecture_package and not lecture_content:
        lecture_content = _merge_package_text(lecture_package)
    if not lecture_content:
        raise ValueError("lecture_content or lecture_package is required")

    students = _build_students(payload)
    if not students:
        raise ValueError("students or student_generator is required")

    config = payload.get("config", {})
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    config = dict(config)

    if "llm_api_key" not in config:
        env_key = os.getenv("OPENAI_API_KEY", "").strip()
        if env_key:
            config["llm_api_key"] = env_key

    db_path = os.getenv("EVALBUDDY_STORE_FILE", str(Path(tempfile.gettempdir()) / "edu_sim_store.json"))
    repo = Repository(db_path=db_path)
    service = WorkflowService(repository=repo)
    return service.run(
        lecture_title=lecture_title,
        lecture_content=lecture_content,
        students=students,
        config=config,
        lecture_package=lecture_package if isinstance(lecture_package, dict) else None,
    )


def _merge_package_text(package: dict[str, Any]) -> str:
    transcript = str(package.get("transcript", "")).strip()
    materials = package.get("materials", [])
    material_texts: list[str] = []
    if isinstance(materials, list):
        for item in materials:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    material_texts.append(text)
            elif isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    material_texts.append(text)
    return "\n".join([transcript] + material_texts).strip()


def _build_students(payload: dict[str, Any]) -> list[Any]:
    explicit = payload.get("students", [])
    if isinstance(explicit, list) and explicit:
        return [parse_student_row(row) for row in explicit if isinstance(row, dict)]

    generator = payload.get("student_generator", {})
    if not isinstance(generator, dict):
        return []
    mode = str(generator.get("mode", "synthetic")).strip().lower()
    if mode == "specific":
        row = create_specific_student_row(
            student_id=str(generator.get("student_id", "stu_specific_001")),
            name=str(generator.get("name", "특정 학생")),
            knowledge_level_100=float(generator.get("knowledge_level_100", 55.0)),
            intelligence_level_100=float(generator.get("intelligence_level_100", 55.0)),
            level=(str(generator.get("level", "")).strip() or None),
            strengths=_to_list(generator.get("strengths")),
            weaknesses=_to_list(generator.get("weaknesses")),
        )
        return [parse_student_row(row)]

    rows = create_synthetic_students(
        count=max(1, int(generator.get("count", 20))),
        base_knowledge_level_100=float(generator.get("knowledge_level_100", 50.0)),
        base_intelligence_level_100=float(generator.get("intelligence_level_100", 55.0)),
        knowledge_spread=float(generator.get("knowledge_spread", 8.0)),
        intelligence_spread=float(generator.get("intelligence_spread", 8.0)),
        prefix=str(generator.get("prefix", "sim_student")),
        seed=int(generator.get("seed", 42)),
    )
    return [parse_student_row(row) for row in rows]


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _sample_payload() -> dict[str, Any]:
    return {
        "lecture_title": "파이썬 데이터 분석 입문",
        "lecture_content": "판다스를 사용해 결측치를 처리하고 집계를 수행합니다.",
        "student_generator": {
            "mode": "synthetic",
            "count": 25,
            "knowledge_level_100": 45,
            "intelligence_level_100": 55,
        },
        "config": {
            "lecture_quality": 0.8,
            "lecture_difficulty": 0.5,
            "max_objectives": 5,
            "interview_mode": "rule",
        },
    }


def _load_web_index() -> str:
    html_file = ROOT / "web" / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<html><body><h1>EvalBuddy</h1><p>web/index.html not found</p></body></html>"

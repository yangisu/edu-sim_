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


BACKGROUND_KNOWLEDGE_LEVELS: dict[str, dict[str, Any]] = {
    "no_prereq": {
        "label": "강의 이해에 필요한 배경지식을 학습하지 않은 상태",
        "score_100": 22.0,
    },
    "partial_prereq": {
        "label": "강의 이해에 필요한 배경지식을 약간 학습한 상태",
        "score_100": 45.0,
    },
    "complete_prereq": {
        "label": "강의 이해에 필요한 배경지식을 모두 학습한 상태",
        "score_100": 70.0,
    },
    "already_understand_topic": {
        "label": "강의 내용을 이미 이해하고 있는 상태",
        "score_100": 90.0,
    },
}

UNDERSTANDING_LEVELS: dict[str, dict[str, Any]] = {
    "needs_extra_time_and_explanation": {
        "label": "설명한 내용을 이해시키기 위해 추가 시간 및 부가설명이 필요함",
        "score_100": 35.0,
    },
    "needs_time_only": {
        "label": "부가설명은 불필요하지만 약간의 시간이 필요함",
        "score_100": 60.0,
    },
    "understands_immediately": {
        "label": "시간 및 추가 설명이 필요하지 않음",
        "score_100": 85.0,
    },
}

LECTURE_QUALITY_LEVELS: dict[str, dict[str, Any]] = {
    "low_structure": {
        "label": "핵심 개념 전달이 불명확하고 예시/정리가 부족함",
        "score_01": 0.45,
    },
    "basic_structure": {
        "label": "핵심 개념은 전달되나 설명 구조와 예시가 제한적임",
        "score_01": 0.62,
    },
    "clear_with_examples": {
        "label": "핵심 개념, 예시, 정리가 명확하게 연결됨",
        "score_01": 0.80,
    },
    "highly_effective": {
        "label": "학습목표-설명-예시-정리 흐름이 매우 우수함",
        "score_01": 0.93,
    },
}

LECTURE_DIFFICULTY_LEVELS: dict[str, dict[str, Any]] = {
    "easy_for_average": {
        "label": "평균적인 수준의 학생에게 쉬운 강의",
        "score_01": 0.35,
    },
    "appropriate_for_average": {
        "label": "평균적인 수준의 학생에게 적정한 강의",
        "score_01": 0.50,
    },
    "hard_for_average": {
        "label": "평균적인 수준의 학생에게 다소 어려운 강의",
        "score_01": 0.68,
    },
    "very_hard_for_average": {
        "label": "평균적인 수준의 학생에게 매우 어려운 강의",
        "score_01": 0.82,
    },
}

VARIABILITY_SPREAD_LEVELS: dict[str, float] = {
    "low": 5.0,
    "medium": 8.0,
    "high": 12.0,
}


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
        if path in {"/api/sample", "/api/sample-payload"}:
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
    _normalize_config(config)

    if "llm_api_key" not in config:
        env_key = os.getenv("OPENAI_API_KEY", "").strip()
        if env_key:
            config["llm_api_key"] = env_key

    model_path = str(config.get("student_model_path", "")).strip()
    if not model_path:
        auto_model = _resolve_default_student_model_path()
        if auto_model:
            config["student_model_path"] = auto_model

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


def _normalize_config(config: dict[str, Any]) -> None:
    quality_state, quality_score = _resolve_state_or_numeric(
        raw=config.get("lecture_quality_state", config.get("lecture_quality")),
        mapping=LECTURE_QUALITY_LEVELS,
        score_key="score_01",
        default_state="clear_with_examples",
        min_value=0.0,
        max_value=1.0,
    )
    difficulty_state, difficulty_score = _resolve_state_or_numeric(
        raw=config.get("lecture_difficulty_state", config.get("lecture_difficulty")),
        mapping=LECTURE_DIFFICULTY_LEVELS,
        score_key="score_01",
        default_state="appropriate_for_average",
        min_value=0.0,
        max_value=1.0,
    )
    config["lecture_quality_state"] = quality_state
    config["lecture_difficulty_state"] = difficulty_state
    config["lecture_quality"] = round(quality_score, 4)
    config["lecture_difficulty"] = round(difficulty_score, 4)


def _build_students(payload: dict[str, Any]) -> list[Any]:
    explicit = payload.get("students", [])
    if isinstance(explicit, list) and explicit:
        return [parse_student_row(row) for row in explicit if isinstance(row, dict)]

    generator = payload.get("student_generator", {})
    if not isinstance(generator, dict):
        return []

    mode = str(generator.get("mode", "synthetic")).strip().lower()
    if mode == "specific":
        knowledge_state, knowledge_score = _resolve_state_or_numeric(
            raw=generator.get("background_knowledge_state", generator.get("knowledge_level_100")),
            mapping=BACKGROUND_KNOWLEDGE_LEVELS,
            score_key="score_100",
            default_state="partial_prereq",
            min_value=0.0,
            max_value=100.0,
        )
        understanding_state, understanding_score = _resolve_state_or_numeric(
            raw=generator.get("understanding_state", generator.get("intelligence_level_100")),
            mapping=UNDERSTANDING_LEVELS,
            score_key="score_100",
            default_state="needs_time_only",
            min_value=0.0,
            max_value=100.0,
        )
        row = create_specific_student_row(
            student_id=str(generator.get("student_id", "stu_specific_001")),
            name=str(generator.get("name", "특정 학생")),
            knowledge_level_100=knowledge_score,
            intelligence_level_100=understanding_score,
            level=(str(generator.get("level", "")).strip() or None),
            strengths=_to_list(generator.get("strengths")),
            weaknesses=_to_list(generator.get("weaknesses")),
        )
        row["traits"] = {
            **(row.get("traits") or {}),
            "background_knowledge_state": knowledge_state,
            "understanding_state": understanding_state,
        }
        return [parse_student_row(row)]

    knowledge_state, knowledge_score = _resolve_state_or_numeric(
        raw=generator.get("background_knowledge_state", generator.get("knowledge_level_100")),
        mapping=BACKGROUND_KNOWLEDGE_LEVELS,
        score_key="score_100",
        default_state="partial_prereq",
        min_value=0.0,
        max_value=100.0,
    )
    understanding_state, understanding_score = _resolve_state_or_numeric(
        raw=generator.get("understanding_state", generator.get("intelligence_level_100")),
        mapping=UNDERSTANDING_LEVELS,
        score_key="score_100",
        default_state="needs_time_only",
        min_value=0.0,
        max_value=100.0,
    )
    spread = _resolve_variability_spread(generator)
    rows = create_synthetic_students(
        count=max(1, int(generator.get("count", 20))),
        base_knowledge_level_100=knowledge_score,
        base_intelligence_level_100=understanding_score,
        knowledge_spread=spread,
        intelligence_spread=spread,
        prefix=str(generator.get("prefix", "sim_student")),
        seed=int(generator.get("seed", 42)),
    )
    parsed = [parse_student_row(row) for row in rows]
    for student in parsed:
        student.traits["background_knowledge_state"] = knowledge_state
        student.traits["understanding_state"] = understanding_state
    return parsed


def _resolve_variability_spread(generator: dict[str, Any]) -> float:
    numeric = generator.get("knowledge_spread")
    if numeric is not None:
        try:
            return max(0.0, float(numeric))
        except (TypeError, ValueError):
            pass
    state = str(generator.get("variability_state", "medium")).strip().lower()
    return float(VARIABILITY_SPREAD_LEVELS.get(state, 8.0))


def _resolve_state_or_numeric(
    raw: Any,
    mapping: dict[str, dict[str, Any]],
    score_key: str,
    default_state: str,
    min_value: float,
    max_value: float,
) -> tuple[str, float]:
    if raw is None:
        item = mapping[default_state]
        return default_state, float(item[score_key])

    if isinstance(raw, (int, float)):
        value = max(min_value, min(max_value, float(raw)))
        return "custom_numeric", value

    raw_str = str(raw).strip()
    if not raw_str:
        item = mapping[default_state]
        return default_state, float(item[score_key])
    if raw_str in mapping:
        return raw_str, float(mapping[raw_str][score_key])

    # allow number-like string
    try:
        value = max(min_value, min(max_value, float(raw_str)))
        return "custom_numeric", value
    except ValueError:
        item = mapping[default_state]
        return default_state, float(item[score_key])


def _resolve_default_student_model_path() -> str | None:
    env_path = os.getenv("STUDENT_MODEL_PATH", "").strip()
    if env_path and Path(env_path).exists():
        return env_path
    candidates = [
        ROOT / "ml_models" / "student_sim_model.json",
        ROOT / "saved_models" / "student_sim_model.json",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


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
            "background_knowledge_state": "partial_prereq",
            "understanding_state": "needs_time_only",
            "variability_state": "medium",
        },
        "config": {
            "lecture_quality_state": "clear_with_examples",
            "lecture_difficulty_state": "appropriate_for_average",
            "max_objectives": 5,
            "interview_mode": "rule",
        },
    }


def _load_web_index() -> str:
    html_file = ROOT / "web" / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<html><body><h1>EvalBuddy</h1><p>web/index.html not found</p></body></html>"

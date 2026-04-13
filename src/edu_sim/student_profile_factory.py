from __future__ import annotations

import random
from typing import Any

from .models import StudentProfile


def clamp01(value: float) -> float:
    return max(0.0, min(value, 1.0))


def clamp100(value: float) -> float:
    return max(0.0, min(value, 100.0))


def infer_level_from_knowledge(knowledge_level_100: float) -> str:
    if knowledge_level_100 < 40:
        return "beginner"
    if knowledge_level_100 < 70:
        return "intermediate"
    return "advanced"


def build_traits_from_quant_levels(
    knowledge_level_100: float,
    intelligence_level_100: float,
    trait_overrides: dict[str, Any] | None = None,
) -> dict[str, float]:
    k = clamp100(float(knowledge_level_100))
    iq = clamp100(float(intelligence_level_100))
    k01 = k / 100.0
    iq01 = iq / 100.0

    traits = {
        "prior_knowledge": round(clamp01(0.15 + 0.8 * k01), 4),
        "focus": round(clamp01(0.2 + 0.65 * iq01), 4),
        "curiosity": round(clamp01(0.25 + 0.55 * iq01), 4),
        "adaptability": round(clamp01(0.2 + 0.6 * iq01), 4),
        "anxiety": round(clamp01(0.75 - 0.6 * iq01), 4),
        "knowledge_level_100": round(k, 2),
        "intelligence_level_100": round(iq, 2),
    }
    if trait_overrides:
        for key, value in trait_overrides.items():
            if isinstance(value, (int, float)):
                traits[key] = float(value)
    return traits


def parse_student_row(row: dict[str, Any]) -> StudentProfile:
    mode = str(row.get("mode", "specific")).strip() or "specific"
    sid = str(row.get("id", "")).strip()
    name = str(row.get("name", "")).strip()
    if not sid:
        raise ValueError("student row requires 'id'")
    if not name:
        raise ValueError("student row requires 'name'")

    strengths = row.get("strengths", [])
    weaknesses = row.get("weaknesses", [])
    strengths = strengths if isinstance(strengths, list) else []
    weaknesses = weaknesses if isinstance(weaknesses, list) else []

    traits_raw = row.get("traits", {})
    traits = dict(traits_raw) if isinstance(traits_raw, dict) else {}

    has_quant = "knowledge_level_100" in row or "intelligence_level_100" in row
    if has_quant:
        knowledge = float(row.get("knowledge_level_100", traits.get("knowledge_level_100", 50.0)))
        intelligence = float(row.get("intelligence_level_100", traits.get("intelligence_level_100", 50.0)))
        quant_traits = build_traits_from_quant_levels(knowledge, intelligence, trait_overrides=traits)
        traits = {**traits, **quant_traits}
    level = str(row.get("level", "")).strip()
    if not level:
        if "knowledge_level_100" in traits:
            level = infer_level_from_knowledge(float(traits["knowledge_level_100"]))
        else:
            level = "intermediate"

    traits["student_mode"] = mode
    return StudentProfile(
        id=sid,
        name=name,
        level=level,
        traits=traits,
        strengths=[str(x) for x in strengths],
        weaknesses=[str(x) for x in weaknesses],
    )


def create_specific_student_row(
    student_id: str,
    name: str,
    knowledge_level_100: float,
    intelligence_level_100: float,
    level: str | None = None,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
) -> dict[str, Any]:
    k = clamp100(float(knowledge_level_100))
    iq = clamp100(float(intelligence_level_100))
    return {
        "id": student_id,
        "name": name,
        "mode": "specific",
        "level": level or infer_level_from_knowledge(k),
        "knowledge_level_100": round(k, 2),
        "intelligence_level_100": round(iq, 2),
        "traits": {},
        "strengths": strengths or [],
        "weaknesses": weaknesses or [],
    }


def create_synthetic_students(
    count: int,
    base_knowledge_level_100: float,
    base_intelligence_level_100: float,
    knowledge_spread: float = 8.0,
    intelligence_spread: float = 8.0,
    prefix: str = "sim_student",
    seed: int = 42,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for i in range(count):
        k = clamp100(base_knowledge_level_100 + rng.uniform(-knowledge_spread, knowledge_spread))
        iq = clamp100(base_intelligence_level_100 + rng.uniform(-intelligence_spread, intelligence_spread))
        rows.append(
            {
                "id": f"{prefix}_{i+1:03d}",
                "name": f"가상학생_{i+1:03d}",
                "mode": "synthetic",
                "level": infer_level_from_knowledge(k),
                "knowledge_level_100": round(k, 2),
                "intelligence_level_100": round(iq, 2),
                "traits": {},
                "strengths": [],
                "weaknesses": [],
            }
        )
    return rows


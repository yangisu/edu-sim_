from __future__ import annotations

import json
import os
from typing import Any

from .assessment_policy import clamp, score_to_band, weighted_axis_score_100
from .models import CriterionEvaluation, InterviewResult, RubricCriterion, StudentProfile, StudentSimulationResult


class LlmInterviewEngine:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for llm interview mode") from exc

        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise RuntimeError("OPENAI_API_KEY is missing")

        self.client = OpenAI(api_key=resolved_key)
        self.model = model

    def evaluate(
        self,
        student: StudentProfile,
        simulation: StudentSimulationResult,
        criteria: list[RubricCriterion],
        lecture_title: str,
    ) -> InterviewResult:
        progress_map = {x.objective_id: x for x in simulation.objective_progress}
        prompt = self._build_prompt(student, simulation, criteria, lecture_title)
        raw = self._ask_json(prompt)
        parsed = self._normalize_payload(raw, criteria)

        weighted_total = 0.0
        evaluations: list[CriterionEvaluation] = []
        for criterion in criteria:
            item = parsed.get(criterion.id, {})
            axis = item.get("axis_scores", {})
            axis_scores = {
                "concept_accuracy": round(clamp(float(axis.get("concept_accuracy", 2.0)), 0.0, 4.0), 2),
                "procedure_execution": round(clamp(float(axis.get("procedure_execution", 2.0)), 0.0, 4.0), 2),
                "case_application": round(clamp(float(axis.get("case_application", 2.0)), 0.0, 4.0), 2),
                "evidence_based_explanation": round(
                    clamp(float(axis.get("evidence_based_explanation", 2.0)), 0.0, 4.0),
                    2,
                ),
            }
            score_100 = weighted_axis_score_100(axis_scores)
            score_5 = round(1.0 + (score_100 / 100.0) * 4.0, 2)
            level = score_to_band(score_100).label
            confidence = round(clamp(float(item.get("confidence", 0.6)), 0.0, 1.0), 2)
            comment = str(item.get("comment", "")).strip()
            if not comment:
                objective = progress_map.get(criterion.objective_id)
                comment = self._fallback_comment(score_100, criterion.metric, objective.post_score if objective else 0.0)

            evaluations.append(
                CriterionEvaluation(
                    criterion_id=criterion.id,
                    score_5_scale=score_5,
                    score_100=score_100,
                    axis_scores=axis_scores,
                    proficiency_level=level,
                    confidence=confidence,
                    comment=comment,
                )
            )
            weighted_total += score_100 * criterion.weight

        total_score = round(weighted_total, 2)
        total_level = score_to_band(total_score).label
        return InterviewResult(
            student_id=student.id,
            total_score_100=total_score,
            proficiency_level=total_level,
            evaluations=evaluations,
        )

    def _ask_json(self, prompt: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict education interviewer. "
                        "Score each criterion with objective evidence and output JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def _build_prompt(
        self,
        student: StudentProfile,
        simulation: StudentSimulationResult,
        criteria: list[RubricCriterion],
        lecture_title: str,
    ) -> str:
        obj_rows = []
        for p in simulation.objective_progress:
            obj_rows.append(
                {
                    "objective_id": p.objective_id,
                    "pre": p.pre_score,
                    "post": p.post_score,
                    "gain": round(p.gain, 2),
                }
            )
        criteria_rows = [
            {
                "criterion_id": c.id,
                "objective_id": c.objective_id,
                "metric": c.metric,
                "weight": c.weight,
            }
            for c in criteria
        ]
        return (
            f"lecture_title: {lecture_title}\n"
            f"student: {student.name} ({student.id})\n"
            f"student_level: {student.level}\n"
            f"student_traits: {json.dumps(student.traits, ensure_ascii=False)}\n"
            f"objective_progress: {json.dumps(obj_rows, ensure_ascii=False)}\n"
            f"criteria: {json.dumps(criteria_rows, ensure_ascii=False)}\n\n"
            "Return JSON with this schema:\n"
            "{"
            "\"evaluations\": ["
            "{"
            "\"criterion_id\": \"RC-1\","
            "\"axis_scores\": {"
            "\"concept_accuracy\": 0-4,"
            "\"procedure_execution\": 0-4,"
            "\"case_application\": 0-4,"
            "\"evidence_based_explanation\": 0-4"
            "},"
            "\"confidence\": 0-1,"
            "\"comment\": \"short evidence-based note\""
            "}"
            "]"
            "}\n"
            "Include every criterion exactly once."
        )

    @staticmethod
    def _normalize_payload(raw: dict[str, Any], criteria: list[RubricCriterion]) -> dict[str, dict[str, Any]]:
        evaluations = raw.get("evaluations", [])
        table: dict[str, dict[str, Any]] = {}
        if isinstance(evaluations, list):
            for item in evaluations:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("criterion_id", "")).strip()
                if cid:
                    table[cid] = item

        # fill missing ids with neutral defaults
        for c in criteria:
            if c.id not in table:
                table[c.id] = {
                    "criterion_id": c.id,
                    "axis_scores": {
                        "concept_accuracy": 2.0,
                        "procedure_execution": 2.0,
                        "case_application": 2.0,
                        "evidence_based_explanation": 2.0,
                    },
                    "confidence": 0.5,
                    "comment": "llm output missing; neutral fallback applied",
                }
        return table

    @staticmethod
    def _fallback_comment(score_100: float, metric: str, post_score: float) -> str:
        return f"자동평가 보정: score={score_100:.2f}, post={post_score:.2f}, metric={metric}"


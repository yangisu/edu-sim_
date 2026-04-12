from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .lecture_package import LecturePackageParser
from .models import LearningObjective

_STOPWORDS = {
    "그리고",
    "또한",
    "합니다",
    "대한",
    "위한",
    "수업",
    "강의",
    "내용",
    "이해",
    "평가",
    "학생",
    "교육",
    "사용",
    "한다",
    "있는",
}


def _normalize_line(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", text)
    return [tok for tok in tokens if tok not in _STOPWORDS]


class LectureEngine:
    """강의 텍스트/패키지에서 학습 목표를 추출한다."""

    def extract_objectives(self, lecture_content: str, max_objectives: int = 5) -> list[LearningObjective]:
        lines = [_normalize_line(line) for line in lecture_content.splitlines()]
        lines = [line for line in lines if len(line) >= 8]

        if not lines:
            lines = [seg.strip() for seg in re.split(r"[.!?\n]", lecture_content) if len(seg.strip()) >= 8]

        deduped: list[str] = []
        seen: set[str] = set()
        for line in lines:
            key = line.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(line)

        selected = deduped[:max_objectives] if deduped else ["핵심 개념을 설명하고 실제 사례에 적용할 수 있다."]
        objectives = [
            LearningObjective(
                id=f"OBJ-{i}",
                description=desc,
                keywords=self._extract_keywords(desc, lecture_content),
                weight=1.0,
            )
            for i, desc in enumerate(selected, start=1)
        ]
        return self._rebalance_weights(objectives)

    def extract_objectives_from_package(
        self,
        package_raw: dict[str, Any],
        max_objectives: int = 5,
    ) -> list[LearningObjective]:
        package = LecturePackageParser.parse(package_raw)
        merged_text = package.merged_text or package.transcript

        auto_objectives = self.extract_objectives(merged_text, max_objectives=max_objectives)
        manual_objectives = self._build_manual_objectives(package.instructor_objectives, merged_text)

        merged: list[LearningObjective] = []
        seen_desc: set[str] = set()
        for obj in manual_objectives + auto_objectives:
            key = obj.description.strip().lower()
            if not key or key in seen_desc:
                continue
            seen_desc.add(key)
            merged.append(obj)
            if len(merged) >= max_objectives:
                break

        renumbered = [
            LearningObjective(
                id=f"OBJ-{i}",
                description=obj.description,
                keywords=obj.keywords,
                weight=obj.weight,
            )
            for i, obj in enumerate(merged, start=1)
        ]
        return self._rebalance_weights(renumbered)

    def _build_manual_objectives(
        self,
        instructor_objectives: list[dict[str, Any]],
        full_text: str,
    ) -> list[LearningObjective]:
        results: list[LearningObjective] = []
        for i, row in enumerate(instructor_objectives, start=1):
            desc = str(row.get("description", "")).strip()
            if not desc:
                continue

            keywords_raw = row.get("keywords", [])
            keywords = [str(k).strip() for k in keywords_raw] if isinstance(keywords_raw, list) else []
            if not keywords:
                keywords = self._extract_keywords(desc, full_text)

            weight = row.get("weight", 1.0)
            try:
                numeric_weight = float(weight) if weight is not None else 1.0
            except (TypeError, ValueError):
                numeric_weight = 1.0

            results.append(
                LearningObjective(
                    id=f"MANUAL-{i}",
                    description=desc,
                    keywords=keywords,
                    weight=max(0.0, numeric_weight),
                )
            )
        return results

    def _extract_keywords(self, objective_text: str, full_text: str, top_k: int = 5) -> list[str]:
        base_tokens = _tokenize(objective_text)
        if len(base_tokens) >= top_k:
            return base_tokens[:top_k]

        counter = Counter(_tokenize(f"{objective_text} {full_text}"))
        for token in base_tokens:
            counter[token] += 2

        ranked = [tok for tok, _ in counter.most_common(top_k)]
        return ranked if ranked else ["개념", "설명", "적용"]

    @staticmethod
    def _rebalance_weights(objectives: list[LearningObjective]) -> list[LearningObjective]:
        if not objectives:
            return objectives

        raw_sum = sum(max(0.0, obj.weight) for obj in objectives)
        if raw_sum <= 0:
            equal = round(1.0 / len(objectives), 4)
            return [
                LearningObjective(
                    id=obj.id,
                    description=obj.description,
                    keywords=obj.keywords,
                    weight=equal,
                )
                for obj in objectives
            ]

        normalized: list[LearningObjective] = []
        for obj in objectives:
            normalized.append(
                LearningObjective(
                    id=obj.id,
                    description=obj.description,
                    keywords=obj.keywords,
                    weight=round(max(0.0, obj.weight) / raw_sum, 4),
                )
            )
        return normalized


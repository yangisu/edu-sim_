from __future__ import annotations

import re
from collections import Counter

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
    """강의 텍스트에서 학습 목표를 뽑아내는 MVP 엔진."""

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

        selected = deduped[:max_objectives] if deduped else ["핵심 개념을 설명하고 사례에 적용할 수 있다."]
        weight = round(1.0 / len(selected), 4)

        objectives: list[LearningObjective] = []
        for i, desc in enumerate(selected, start=1):
            keywords = self._extract_keywords(desc, lecture_content)
            objectives.append(
                LearningObjective(
                    id=f"OBJ-{i}",
                    description=desc,
                    keywords=keywords,
                    weight=weight,
                )
            )
        return objectives

    def _extract_keywords(self, objective_text: str, full_text: str, top_k: int = 5) -> list[str]:
        base_tokens = _tokenize(objective_text)
        if len(base_tokens) >= top_k:
            return base_tokens[:top_k]

        counter = Counter(_tokenize(f"{objective_text} {full_text}"))
        for token in base_tokens:
            counter[token] += 2

        ranked = [tok for tok, _ in counter.most_common(top_k)]
        return ranked if ranked else ["개념", "설명", "적용"]


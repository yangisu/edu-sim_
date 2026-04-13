from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class StudentSimModelArtifact:
    feature_names: list[str]
    pre_intercept: float
    pre_weights: list[float]
    gain_intercept: float
    gain_weights: list[float]
    l2: float
    num_samples: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": self.feature_names,
            "pre_intercept": self.pre_intercept,
            "pre_weights": self.pre_weights,
            "gain_intercept": self.gain_intercept,
            "gain_weights": self.gain_weights,
            "l2": self.l2,
            "num_samples": self.num_samples,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StudentSimModelArtifact":
        return cls(
            feature_names=[str(x) for x in raw["feature_names"]],
            pre_intercept=float(raw["pre_intercept"]),
            pre_weights=[float(x) for x in raw["pre_weights"]],
            gain_intercept=float(raw["gain_intercept"]),
            gain_weights=[float(x) for x in raw["gain_weights"]],
            l2=float(raw.get("l2", 1.0)),
            num_samples=int(raw.get("num_samples", 0)),
        )


FEATURE_NAMES = [
    "knowledge_level_100",
    "intelligence_level_100",
    "prior_knowledge",
    "focus",
    "curiosity",
    "adaptability",
    "anxiety",
    "lecture_quality",
    "lecture_difficulty",
    "objective_keyword_count",
    "objective_text_len",
    "strengths_count",
    "weaknesses_count",
]


def train_student_sim_model(
    train_file: str | Path,
    output_model_file: str | Path,
    l2: float = 1.0,
) -> StudentSimModelArtifact:
    rows = _load_rows(train_file)
    if len(rows) < 8:
        raise SystemExit("training file must contain at least 8 rows")

    x = np.asarray([_feature_vector(r) for r in rows], dtype=np.float64)
    y_pre = np.asarray([float(r["pre_score"]) for r in rows], dtype=np.float64)
    y_gain = np.asarray([float(r["post_score"]) - float(r["pre_score"]) for r in rows], dtype=np.float64)

    pre_intercept, pre_weights = _ridge_fit(x, y_pre, l2=l2)
    gain_intercept, gain_weights = _ridge_fit(x, y_gain, l2=l2)

    artifact = StudentSimModelArtifact(
        feature_names=FEATURE_NAMES,
        pre_intercept=float(pre_intercept),
        pre_weights=[float(v) for v in pre_weights],
        gain_intercept=float(gain_intercept),
        gain_weights=[float(v) for v in gain_weights],
        l2=float(l2),
        num_samples=len(rows),
    )
    path = Path(output_model_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def load_student_sim_model(model_file: str | Path) -> StudentSimModelArtifact:
    raw = json.loads(Path(model_file).read_text(encoding="utf-8"))
    return StudentSimModelArtifact.from_dict(raw)


def _load_rows(train_file: str | Path) -> list[dict[str, Any]]:
    path = Path(train_file)
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    raise SystemExit("train file must be json array or jsonl")


def _feature_vector(row: dict[str, Any]) -> list[float]:
    return [
        _to_float(row.get("knowledge_level_100", 50.0)),
        _to_float(row.get("intelligence_level_100", 50.0)),
        _to_float(row.get("prior_knowledge", 0.5)),
        _to_float(row.get("focus", 0.5)),
        _to_float(row.get("curiosity", 0.5)),
        _to_float(row.get("adaptability", 0.5)),
        _to_float(row.get("anxiety", 0.3)),
        _to_float(row.get("lecture_quality", 0.8)),
        _to_float(row.get("lecture_difficulty", 0.5)),
        _to_float(row.get("objective_keyword_count", 3.0)),
        _to_float(row.get("objective_text_len", 50.0)),
        _to_float(row.get("strengths_count", 0.0)),
        _to_float(row.get("weaknesses_count", 0.0)),
    ]


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ridge_fit(x: np.ndarray, y: np.ndarray, l2: float) -> tuple[float, np.ndarray]:
    n, p = x.shape
    x_aug = np.concatenate([np.ones((n, 1)), x], axis=1)
    reg = np.eye(p + 1)
    reg[0, 0] = 0.0
    theta = np.linalg.solve(x_aug.T @ x_aug + l2 * reg, x_aug.T @ y)
    return float(theta[0]), theta[1:]


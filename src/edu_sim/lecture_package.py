from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LecturePackage:
    transcript: str
    materials: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    instructor_objectives: list[dict[str, Any]] = field(default_factory=list)

    @property
    def merged_text(self) -> str:
        blocks = [self.transcript.strip()] if self.transcript.strip() else []
        for material in self.materials:
            if material.strip():
                blocks.append(material.strip())
        return "\n".join(blocks).strip()


class LecturePackageParser:
    @staticmethod
    def parse(raw: dict[str, Any]) -> LecturePackage:
        transcript = str(raw.get("transcript", "")).strip()
        materials = LecturePackageParser._parse_materials(raw.get("materials", []))
        metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata", {}), dict) else {}
        instructor_objectives = LecturePackageParser._parse_instructor_objectives(
            raw.get("instructor_objectives", [])
        )
        return LecturePackage(
            transcript=transcript,
            materials=materials,
            metadata=metadata,
            instructor_objectives=instructor_objectives,
        )

    @staticmethod
    def _parse_materials(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list):
            return []

        texts: list[str] = []
        for item in value:
            if isinstance(item, str):
                texts.append(item)
                continue
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    texts.append(text)
        return texts

    @staticmethod
    def _parse_instructor_objectives(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        parsed: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                desc = item.strip()
                if desc:
                    parsed.append({"description": desc, "keywords": [], "weight": None})
                continue
            if isinstance(item, dict):
                desc = str(item.get("description", "")).strip()
                if not desc:
                    continue
                keywords_raw = item.get("keywords", [])
                keywords = [str(k).strip() for k in keywords_raw] if isinstance(keywords_raw, list) else []
                weight = item.get("weight", None)
                parsed.append({"description": desc, "keywords": keywords, "weight": weight})
        return parsed


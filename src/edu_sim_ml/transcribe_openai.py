from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def transcribe_missing_rows_with_openai(
    manifest_file: str | Path,
    output_file: str | Path,
    model: str,
    api_key: str | None = None,
) -> None:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("openai package is required. install with: pip install openai") from exc

    client = OpenAI(api_key=api_key)
    input_path = Path(manifest_file)
    rows: list[dict[str, Any]] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))

    for row in rows:
        if str(row.get("transcript", "")).strip():
            continue
        audio_path = Path(str(row["audio_path"]))
        if not audio_path.exists():
            continue
        with audio_path.open("rb") as f:
            response = client.audio.transcriptions.create(model=model, file=f)
        text = response if isinstance(response, str) else getattr(response, "text", "")
        row["transcript"] = str(text).strip()

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


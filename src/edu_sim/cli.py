from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import StudentProfile
from .orchestrator import WorkflowService
from .repository import Repository


def _load_students(path: Path) -> list[StudentProfile]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    students: list[StudentProfile] = []
    for row in raw:
        students.append(
            StudentProfile(
                id=row["id"],
                name=row["name"],
                level=row["level"],
                traits=row.get("traits", {}),
                strengths=row.get("strengths", []),
                weaknesses=row.get("weaknesses", []),
            )
        )
    return students


def _run_pipeline(
    lecture_title: str,
    lecture_content: str,
    students: list[StudentProfile],
    db_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    repo = Repository(db_path=db_path)
    service = WorkflowService(repository=repo)
    return service.run(
        lecture_title=lecture_title,
        lecture_content=lecture_content,
        students=students,
        config=config,
    )


def _default_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[2]
    lecture = project_root / "sample_data" / "lecture.txt"
    students = project_root / "sample_data" / "students.json"
    return lecture, students


def _print_summary(report: dict[str, Any]) -> None:
    print(f"run_id: {report['run_id']}")
    print(f"lecture: {report['lecture']['title']} (objectives={report['lecture']['objective_count']})")
    print("group summary:")
    for level, summary in report["group_summary"].items():
        print(
            f"  - {level}: pre={summary['pre_avg']}, post={summary['post_avg']}, "
            f"gain={summary['gain_avg']}, interview={summary['interview_avg']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="edu_sim MVP CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_demo = sub.add_parser("run-demo", help="sample_data 기준으로 데모 실행")
    run_demo.add_argument("--db-path", default="edu_sim_store.json")
    run_demo.add_argument("--output", default="")

    run = sub.add_parser("run", help="강의/학생 파일로 실행")
    run.add_argument("--lecture-file", required=True)
    run.add_argument("--students-file", required=True)
    run.add_argument("--lecture-title", default="사용자 강의")
    run.add_argument("--db-path", default="edu_sim_store.json")
    run.add_argument("--output", default="")
    run.add_argument("--lecture-quality", type=float, default=0.8)
    run.add_argument("--lecture-difficulty", type=float, default=0.5)
    run.add_argument("--max-objectives", type=int, default=5)

    show = sub.add_parser("show-run", help="기존 run_id 결과 조회")
    show.add_argument("--run-id", required=True)
    show.add_argument("--db-path", default="edu_sim_store.json")

    args = parser.parse_args()

    if args.command == "run-demo":
        lecture_file, students_file = _default_paths()
        lecture_content = lecture_file.read_text(encoding="utf-8")
        students = _load_students(students_file)
        report = _run_pipeline(
            lecture_title="Python 데이터 분석 입문",
            lecture_content=lecture_content,
            students=students,
            db_path=Path(args.db_path),
            config={"lecture_quality": 0.8, "lecture_difficulty": 0.45, "max_objectives": 5},
        )
        _print_summary(report)
        if args.output:
            Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"saved: {args.output}")
        return

    if args.command == "run":
        lecture_content = Path(args.lecture_file).read_text(encoding="utf-8")
        students = _load_students(Path(args.students_file))
        report = _run_pipeline(
            lecture_title=args.lecture_title,
            lecture_content=lecture_content,
            students=students,
            db_path=Path(args.db_path),
            config={
                "lecture_quality": args.lecture_quality,
                "lecture_difficulty": args.lecture_difficulty,
                "max_objectives": args.max_objectives,
            },
        )
        _print_summary(report)
        if args.output:
            Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"saved: {args.output}")
        return

    if args.command == "show-run":
        repo = Repository(db_path=Path(args.db_path))
        report = repo.get_report(args.run_id)
        if report is None:
            raise SystemExit(f"run_id '{args.run_id}' not found")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()

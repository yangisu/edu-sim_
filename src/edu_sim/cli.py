from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import StudentProfile
from .orchestrator import WorkflowService
from .plan_service import InstructorPlanService, PlanValidationError
from .repository import Repository
from .student_profile_factory import (
    create_specific_student_row,
    create_synthetic_students,
    parse_student_row,
)


def _load_students(path: Path) -> list[StudentProfile]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [parse_student_row(row) for row in raw]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_pipeline(
    lecture_title: str,
    lecture_content: str,
    students: list[StudentProfile],
    db_path: Path,
    config: dict[str, Any],
    lecture_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = Repository(db_path=db_path)
    service = WorkflowService(repository=repo)
    return service.run(
        lecture_title=lecture_title,
        lecture_content=lecture_content,
        students=students,
        config=config,
        lecture_package=lecture_package,
    )


def _default_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[2]
    lecture = project_root / "sample_data" / "lecture.txt"
    students = project_root / "sample_data" / "students.json"
    return lecture, students


def _build_lecture_input(args: argparse.Namespace) -> tuple[str, dict[str, Any] | None]:
    if getattr(args, "lecture_package_file", ""):
        package = _load_json(Path(args.lecture_package_file))
        transcript = str(package.get("transcript", "")).strip()
        materials = package.get("materials", [])
        material_texts: list[str] = []
        if isinstance(materials, list):
            for item in materials:
                if isinstance(item, str):
                    material_texts.append(item)
                elif isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                    if text:
                        material_texts.append(text)
        merged = "\n".join([transcript] + material_texts).strip()
        return merged, package

    lecture_content = Path(args.lecture_file).read_text(encoding="utf-8")
    return lecture_content, None


def _print_summary(report: dict[str, Any]) -> None:
    print(f"run_id: {report['run_id']}")
    print(f"lecture: {report['lecture']['title']} (objectives={report['lecture']['objective_count']})")
    print(f"input_format: {report['lecture']['input_format']}")
    print(f"student_simulator_engine: {report.get('student_simulator_engine', 'rule')}")
    print(f"interview_engine_used: {report.get('interview_engine_used', 'rule')}")
    print("group summary:")
    for level, summary in report["group_summary"].items():
        print(
            f"  - {level}: pre={summary['pre_avg']}, post={summary['post_avg']}, "
            f"gain={summary['gain_avg']}, interview={summary['interview_avg']}"
        )


def _require_lecture_source(args: argparse.Namespace) -> None:
    has_text = bool(getattr(args, "lecture_file", ""))
    has_package = bool(getattr(args, "lecture_package_file", ""))
    if has_text == has_package:
        raise SystemExit("exactly one of --lecture-file or --lecture-package-file is required")


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="edu_sim CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_demo = sub.add_parser("run-demo", help="sample_data로 데모 실행")
    run_demo.add_argument("--db-path", default="edu_sim_store.json")
    run_demo.add_argument("--output", default="")

    run = sub.add_parser("run", help="강의/학생 파일 또는 lecture package로 실행")
    run.add_argument("--lecture-file", default="")
    run.add_argument("--lecture-package-file", default="")
    run.add_argument("--students-file", required=True)
    run.add_argument("--lecture-title", default="사용자 강의")
    run.add_argument("--db-path", default="edu_sim_store.json")
    run.add_argument("--output", default="")
    run.add_argument("--lecture-quality", type=float, default=0.8)
    run.add_argument("--lecture-difficulty", type=float, default=0.5)
    run.add_argument("--max-objectives", type=int, default=5)
    run.add_argument("--approved-plan-id", default="")
    run.add_argument("--student-model-path", default="")
    run.add_argument("--interview-mode", choices=["rule", "llm"], default="rule")
    run.add_argument("--llm-model", default="gpt-4o-mini")
    run.add_argument("--llm-api-key", default="")

    draft_plan = sub.add_parser("draft-plan", help="강의에서 objective/rubric 초안 생성")
    draft_plan.add_argument("--lecture-file", default="")
    draft_plan.add_argument("--lecture-package-file", default="")
    draft_plan.add_argument("--lecture-title", default="사용자 강의")
    draft_plan.add_argument("--db-path", default="edu_sim_store.json")
    draft_plan.add_argument("--output", default="plan_draft.json")
    draft_plan.add_argument("--max-objectives", type=int, default=5)

    approve_plan = sub.add_parser("approve-plan", help="수정한 plan JSON 검증 후 승인")
    approve_plan.add_argument("--plan-file", required=True)
    approve_plan.add_argument("--db-path", default="edu_sim_store.json")
    approve_plan.add_argument("--approved-by", default="instructor")
    approve_plan.add_argument("--approval-notes", default="")
    approve_plan.add_argument("--output", default="")

    show_plan = sub.add_parser("show-plan", help="plan 조회")
    show_plan.add_argument("--plan-id", required=True)
    show_plan.add_argument("--db-path", default="edu_sim_store.json")

    show_run = sub.add_parser("show-run", help="run 결과 조회")
    show_run.add_argument("--run-id", required=True)
    show_run.add_argument("--db-path", default="edu_sim_store.json")

    make_specific = sub.add_parser("make-specific-student", help="특정 학생 시뮬레이션용 프로필 생성")
    make_specific.add_argument("--student-id", required=True)
    make_specific.add_argument("--name", required=True)
    make_specific.add_argument("--knowledge-level", type=float, required=True)
    make_specific.add_argument("--intelligence-level", type=float, required=True)
    make_specific.add_argument("--level", default="")
    make_specific.add_argument("--strengths", default="")
    make_specific.add_argument("--weaknesses", default="")
    make_specific.add_argument("--output", required=True)

    make_synthetic = sub.add_parser("make-synthetic-students", help="정량 수준 기반 가상 학생 집합 생성")
    make_synthetic.add_argument("--count", type=int, required=True)
    make_synthetic.add_argument("--knowledge-level", type=float, required=True)
    make_synthetic.add_argument("--intelligence-level", type=float, required=True)
    make_synthetic.add_argument("--knowledge-spread", type=float, default=8.0)
    make_synthetic.add_argument("--intelligence-spread", type=float, default=8.0)
    make_synthetic.add_argument("--prefix", default="sim_student")
    make_synthetic.add_argument("--seed", type=int, default=42)
    make_synthetic.add_argument("--output", required=True)

    args = parser.parse_args()

    if args.command == "make-specific-student":
        row = create_specific_student_row(
            student_id=args.student_id,
            name=args.name,
            knowledge_level_100=args.knowledge_level,
            intelligence_level_100=args.intelligence_level,
            level=(args.level or None),
            strengths=_split_csv(args.strengths),
            weaknesses=_split_csv(args.weaknesses),
        )
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([row], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved: {out}")
        return

    if args.command == "make-synthetic-students":
        rows = create_synthetic_students(
            count=args.count,
            base_knowledge_level_100=args.knowledge_level,
            base_intelligence_level_100=args.intelligence_level,
            knowledge_spread=args.knowledge_spread,
            intelligence_spread=args.intelligence_spread,
            prefix=args.prefix,
            seed=args.seed,
        )
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved: {out}")
        return

    if args.command == "draft-plan":
        _require_lecture_source(args)
        repo = Repository(db_path=Path(args.db_path))
        planner = InstructorPlanService(repository=repo)
        lecture_content, lecture_package = _build_lecture_input(args)
        if lecture_package:
            plan = planner.draft_plan_from_package(
                lecture_title=args.lecture_title,
                package_raw=lecture_package,
                max_objectives=args.max_objectives,
            )
        else:
            plan = planner.draft_plan(
                lecture_title=args.lecture_title,
                lecture_content=lecture_content,
                max_objectives=args.max_objectives,
            )
        out = Path(args.output)
        _save_json(out, plan)
        print(f"plan_id: {plan['plan_id']}")
        print(f"status: {plan['status']}")
        print(f"saved: {out}")
        print("next: edit the file, then run approve-plan")
        return

    if args.command == "approve-plan":
        repo = Repository(db_path=Path(args.db_path))
        planner = InstructorPlanService(repository=repo)
        plan = _load_json(Path(args.plan_file))
        try:
            approved = planner.approve_plan(
                plan=plan,
                approved_by=args.approved_by,
                approval_notes=args.approval_notes,
            )
        except PlanValidationError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"plan_id: {approved['plan_id']}")
        print(f"status: {approved['status']}")
        print(f"approved_by: {approved['approved_by']}")
        if args.output:
            out = Path(args.output)
            _save_json(out, approved)
            print(f"saved: {out}")
        return

    if args.command == "show-plan":
        repo = Repository(db_path=Path(args.db_path))
        plan = repo.get_lecture_plan(args.plan_id)
        if plan is None:
            raise SystemExit(f"plan_id '{args.plan_id}' not found")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

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
            out = Path(args.output)
            _save_json(out, report)
            print(f"saved: {out}")
        return

    if args.command == "run":
        _require_lecture_source(args)
        lecture_content, lecture_package = _build_lecture_input(args)
        students = _load_students(Path(args.students_file))
        config: dict[str, Any] = {
            "lecture_quality": args.lecture_quality,
            "lecture_difficulty": args.lecture_difficulty,
            "max_objectives": args.max_objectives,
            "interview_mode": args.interview_mode,
            "llm_model": args.llm_model,
        }
        if args.llm_api_key:
            config["llm_api_key"] = args.llm_api_key
        if args.approved_plan_id:
            config["approved_plan_id"] = args.approved_plan_id
        if args.student_model_path:
            config["student_model_path"] = args.student_model_path

        report = _run_pipeline(
            lecture_title=args.lecture_title,
            lecture_content=lecture_content,
            students=students,
            db_path=Path(args.db_path),
            config=config,
            lecture_package=lecture_package,
        )
        _print_summary(report)
        if args.output:
            out = Path(args.output)
            _save_json(out, report)
            print(f"saved: {out}")
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


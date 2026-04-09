# edu_sim MVP

강사의 수업 내용을 기반으로,
1) 학생 역할 AI를 수준별/개인별로 시뮬레이션하고
2) AI 면접관 방식으로 교육 결과를 정량 검증하는
프로젝트의 최소 기능 제품(MVP)입니다.

## 1. MVP에서 실제 동작하는 것

- 강의 텍스트 입력
- 강의 목표(learning objectives) 자동 추출
- 수준별 학생(초급/중급/고급) + 개인 특성 기반 사전/사후 이해도 시뮬레이션
- 강의 목표 기반 정량 평가 기준(Rubric) 생성
- AI 면접 점수(100점) 계산
- 그룹/개인 리포트 생성 및 JSON 저장소 저장

## 2. 코드 연결 구조

```text
CLI (src/edu_sim/cli.py)
  -> WorkflowService (src/edu_sim/orchestrator.py)
      -> LectureEngine (학습목표 추출)
      -> StudentSimulator (사전/사후 이해도 시뮬레이션)
      -> RubricEngine (정량 평가 기준 생성)
      -> InterviewEngine (면접 점수화)
      -> Repository (JSON 저장/조회)
```

핵심 연결 키는 `run_id`입니다.
하나의 실행(run) 안에서 시뮬레이션 점수, rubric, 면접 결과, 최종 리포트가 모두 연결 저장됩니다.

## 3. 실행 방법

실행 전 한 번 `src` 경로를 Python path에 추가합니다.

PowerShell:

```powershell
$env:PYTHONPATH = "src"
```

### 3-1. 데모 실행

```bash
python -m edu_sim.cli run-demo --db-path edu_sim_store.json --output result.json
```

입력 파일:
- `sample_data/lecture.txt`
- `sample_data/students.json`

### 3-2. 사용자 파일로 실행

```bash
python -m edu_sim.cli run \
  --lecture-file sample_data/lecture.txt \
  --students-file sample_data/students.json \
  --lecture-title "맞춤형 수업" \
  --lecture-quality 0.85 \
  --lecture-difficulty 0.45 \
  --max-objectives 5 \
  --db-path edu_sim_store.json \
  --output result.json
```

### 3-3. 기존 실행 결과 조회

```bash
python -m edu_sim.cli show-run --run-id <run_id> --db-path edu_sim_store.json
```

## 4. students.json 스키마

```json
[
  {
    "id": "stu_001",
    "name": "민수",
    "level": "beginner",
    "traits": {
      "focus": 0.52,
      "curiosity": 0.68,
      "prior_knowledge": 0.31,
      "anxiety": 0.44,
      "adaptability": 0.58
    },
    "strengths": ["시각화"],
    "weaknesses": ["인과관계"]
  }
]
```

## 5. 테스트

```bash
python -m pytest -q
```

## 6. 확장 포인트 (다음 단계)

- 실제 LLM 연동(OpenAI 등)으로 면접 답변 생성/채점 고도화
- 강사 입력 인터페이스(Web/API) 추가
- 실데이터(시험/설문)와 시뮬레이션 점수 보정(calibration)
- 학생 개인 디지털 트윈(장기 학습 기록 기반) 모델링

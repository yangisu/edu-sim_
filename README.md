# edu_sim MVP

강의 데이터를 기반으로 학생 시뮬레이션과 교육 효과 검증을 수행하는 MVP입니다.

## 핵심 기능

- 학생 수준/특성 기반 사전-사후 이해도 시뮬레이션
- AI 면접형 평가 점수(100점) 산출
- 행동 기반 성취수준 분류
- 강사 승인 워크플로우(초안 생성 -> 수정 -> 승인 -> 승인본 실행)
- 표준 lecture package 입력 지원

## lecture 입력 포맷

### 1) 텍스트 강의

`--lecture-file`로 일반 텍스트를 입력합니다.

### 2) 표준 lecture package (권장)

`--lecture-package-file`로 JSON 패키지를 입력합니다.

필드:
- `transcript` (필수): STT 텍스트
- `materials` (선택): 교안 텍스트 배열(문자열 또는 `{type,text}` 객체)
- `metadata` (선택): 과목/난이도/시간/선수지식
- `instructor_objectives` (선택): 강사 작성 학습목표 초안

샘플: [lecture_package.json](D:/KIT/edu_sim/sample_data/lecture_package.json)

## 정량 평가 기준

면접 점수는 각 기준(criterion)마다 아래 4축을 0~4로 계산한 후 가중합합니다.

- 개념 정확성: 30
- 절차 수행력: 30
- 사례 적용력: 25
- 근거 기반 설명력: 15

성취수준(100점 기준):
- 0~39: 입문 미도달
- 40~59: 기초
- 60~79: 적용
- 80~100: 숙련

## 실행 전 설정

> **요구사항: Python 3.11 이상**
> `@dataclass(slots=True)` 등 3.11+ 전용 기능을 사용합니다. `pyproject.toml`의 `requires-python = ">=3.11"` 조건을 확인하세요.

PowerShell:

```powershell
$env:PYTHONPATH = "src"
```

## 실행 방법

### 데모

```bash
python -m edu_sim.cli run-demo --db-path edu_sim_store.json --output result.json
```

### 텍스트 강의로 실행

```bash
python -m edu_sim.cli run \
  --lecture-file sample_data/lecture.txt \
  --students-file sample_data/students.json \
  --lecture-title "텍스트 강의" \
  --db-path edu_sim_store.json \
  --output result_text.json
```

### lecture package로 실행

```bash
python -m edu_sim.cli run \
  --lecture-package-file sample_data/lecture_package.json \
  --students-file sample_data/students.json \
  --lecture-title "패키지 강의" \
  --db-path edu_sim_store.json \
  --output result_package.json
```

### 강사 승인 워크플로우

1) 초안 생성

```bash
python -m edu_sim.cli draft-plan \
  --lecture-package-file sample_data/lecture_package.json \
  --lecture-title "승인 대상 강의" \
  --db-path edu_sim_store.json \
  --output plan_draft.json
```

2) `plan_draft.json` 수정(강사 검토)

3) 승인

```bash
python -m edu_sim.cli approve-plan \
  --plan-file plan_draft.json \
  --approved-by "instructor_kim" \
  --approval-notes "1차 승인" \
  --db-path edu_sim_store.json
```

4) 승인 플랜으로 실행

```bash
python -m edu_sim.cli run \
  --lecture-package-file sample_data/lecture_package.json \
  --students-file sample_data/students.json \
  --lecture-title "승인 적용 실행" \
  --approved-plan-id <plan_id> \
  --db-path edu_sim_store.json \
  --output result_approved.json
```

### 결과 조회

```bash
python -m edu_sim.cli show-run --run-id <run_id> --db-path edu_sim_store.json
python -m edu_sim.cli show-plan --plan-id <plan_id> --db-path edu_sim_store.json
```

## 테스트

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```


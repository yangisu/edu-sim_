# EvalBuddy (`edu_sim`)

강의 내용을 입력하면 학생 시뮬레이터와 AI 면접 평가를 통해 교육 효과를 정량적으로 예측하는 프로젝트입니다.

## 핵심 구성

- `src/edu_sim`: 실행 엔진 (강의 목표 추출, 학생 시뮬레이션, 면접 평가, 리포트 생성)
- `src/edu_sim_ml`: 데이터/모델 파이프라인
  - AI-Hub 데이터 로더
  - lecture package 생성기
  - Whisper ASR 학습
  - 학생 시뮬레이터 학습
  - 면접관 LLM 파인튜닝 데이터/잡 생성
- `api/index.py`: Vercel Python API (웹 백엔드)
- `web/index.html`: EvalBuddy 웹 UI (프론트엔드)

## 빠른 시작 (로컬)

> **요구사항: Python 3.11 이상**
> `@dataclass(slots=True)` 등 3.11+ 전용 기능을 사용합니다. `pyproject.toml`의 `requires-python = ">=3.11"` 조건을 확인하세요.

PowerShell:

```powershell
$env:PYTHONPATH = "src"
```

데모 실행:

```powershell
python -m edu_sim.cli run-demo --db-path edu_sim_store.json --output result.json
```

## 학생 시뮬레이터 학습/저장

1) 학습셋 생성

```powershell
python -m edu_sim_ml.cli build-student-trainset `
  --store-file "edu_sim_store.json" `
  --output-file "ml_data/student_sim_train.jsonl"
```

2) 모델 학습

```powershell
python -m edu_sim_ml.cli train-student-simulator `
  --train-file "ml_data/student_sim_train.jsonl" `
  --output-model "ml_models/student_sim_model.json"
```

3) 실행 시 적용

```powershell
python -m edu_sim.cli run `
  --lecture-file "sample_data/lecture.txt" `
  --students-file "sample_data/students_synthetic.json" `
  --student-model-path "ml_models/student_sim_model.json" `
  --lecture-title "trained student simulator run" `
  --output "result_trained_student_model.json"
```

## 면접관 LLM 파인튜닝 파이프라인

1) 파인튜닝용 chat JSONL 생성

```powershell
python -m edu_sim_ml.cli build-interviewer-ft `
  --store-file "edu_sim_store.json" `
  --train-output "ml_data/interviewer_ft_train.jsonl" `
  --valid-output "ml_data/interviewer_ft_valid.jsonl"
```

2) OpenAI 파인튜닝 잡 생성

```powershell
$env:OPENAI_API_KEY = "<YOUR_KEY>"

python -m edu_sim_ml.cli train-interviewer-ft-openai `
  --train-file "ml_data/interviewer_ft_train.jsonl" `
  --valid-file "ml_data/interviewer_ft_valid.jsonl" `
  --base-model "gpt-4o-mini-2024-07-18" `
  --suffix "evalbuddy-interviewer" `
  --output-info "ml_models/interviewer_ft_job.json"
```

`ml_models/interviewer_ft_job.json`에 `fine_tune_job_id`, 업로드 파일 ID가 저장됩니다.

## AI-Hub 데이터 처리

샘플 경로: `D:\KIT\edu_sim\Sample\Sample`

manifest 생성:

```powershell
python -m edu_sim_ml.cli build-manifest `
  --dataset-root "D:\KIT\edu_sim\Sample\Sample" `
  --output "ml_data/manifest.jsonl"
```

lecture package 변환:

```powershell
python -m edu_sim_ml.cli build-lecture-packages `
  --dataset-root "D:\KIT\edu_sim\Sample\Sample" `
  --output-dir "ml_data/lecture_packages"
```

## 웹 + Vercel 배포

`vercel.json`은 아래를 이미 설정합니다.

- `/api/*` -> `api/index.py`
- 나머지 경로 -> `web/index.html`

필수 환경변수(LLM 면접 모드 사용 시):

- `OPENAI_API_KEY`

배포:

```powershell
vercel
vercel --prod
```

## 테스트

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

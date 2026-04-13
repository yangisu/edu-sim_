# ML Pipeline Guide

## Dataset

- root: `D:\KIT\edu_sim\Sample\Sample`
- source audio: `01.*` directory
- label json: `02.*` directory

`src/edu_sim_ml/aihub_loader.py`는 다음을 처리합니다:
- 번호 prefix 기반으로 `01.*`, `02.*` 자동 탐색
- JSON 인코딩 fallback (`utf-8`, `utf-8-sig`, `cp949`, `euc-kr`)

## Commands

PowerShell:

```powershell
$env:PYTHONPATH = "src"
```

### 1) manifest 생성

```powershell
python -m edu_sim_ml.cli build-manifest `
  --dataset-root "D:\KIT\edu_sim\Sample\Sample" `
  --output "ml_data/manifest.jsonl"
```

### 2) lecture package 변환

```powershell
python -m edu_sim_ml.cli build-lecture-packages `
  --dataset-root "D:\KIT\edu_sim\Sample\Sample" `
  --output-dir "ml_data/lecture_packages"
```

### 3) (선택) OpenAI STT 보완

```powershell
python -m edu_sim_ml.cli stt-openai `
  --manifest-file "ml_data/manifest.jsonl" `
  --output-file "ml_data/manifest_filled.jsonl" `
  --model "<transcription-model>"
```

### 4) Whisper 학습

```powershell
python -m edu_sim_ml.cli train-whisper-lora `
  --manifest-file "ml_data/manifest.jsonl" `
  --output-dir "saved_models/whisper_ko_tiny_ft_run1" `
  --model-name "openai/whisper-small" `
  --epochs 1 `
  --batch-size 2 `
  --eval-batch-size 2 `
  --learning-rate 1e-4
```

### 5) 학생 시뮬레이터 학습

```powershell
python -m edu_sim_ml.cli build-student-trainset `
  --store-file "edu_sim_store.json" `
  --output-file "ml_data/student_sim_train.jsonl"

python -m edu_sim_ml.cli train-student-simulator `
  --train-file "ml_data/student_sim_train.jsonl" `
  --output-model "ml_models/student_sim_model.json"
```

### 6) 면접관 LLM 파인튜닝

```powershell
python -m edu_sim_ml.cli build-interviewer-ft `
  --store-file "edu_sim_store.json" `
  --train-output "ml_data/interviewer_ft_train.jsonl" `
  --valid-output "ml_data/interviewer_ft_valid.jsonl"

python -m edu_sim_ml.cli train-interviewer-ft-openai `
  --train-file "ml_data/interviewer_ft_train.jsonl" `
  --valid-file "ml_data/interviewer_ft_valid.jsonl" `
  --base-model "gpt-4o-mini-2024-07-18" `
  --suffix "evalbuddy-interviewer" `
  --output-info "ml_models/interviewer_ft_job.json"
```

## Runtime integration

학습 모델 적용 실행:

```powershell
python -m edu_sim.cli run `
  --lecture-package-file "ml_data/lecture_packages/C14782.lecture_package.json" `
  --students-file "sample_data/students_synthetic.json" `
  --student-model-path "ml_models/student_sim_model.json" `
  --interview-mode "rule" `
  --output "result_from_package.json"
```

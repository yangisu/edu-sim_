# AI Models in EvalBuddy

## 1) 학생 시뮬레이터

### A. 규칙 기반 모델
- 파일: `src/edu_sim/student_simulator.py`
- 입력: 학생 특성 + 강의 난이도/품질 + 목표별 텍스트
- 출력: 목표별 `pre/post` 점수

### B. 학습 기반 모델(저장형)
- 학습 코드: `src/edu_sim_ml/student_sim_trainer.py`
- 로딩/추론: `src/edu_sim/student_trained_model.py`
- 산출물: `ml_models/student_sim_model.json`

학습 데이터 필드:
- feature: `knowledge_level_100`, `intelligence_level_100`, `prior_knowledge`, `focus`, `curiosity`, `adaptability`, `anxiety`, `lecture_quality`, `lecture_difficulty`, `objective_keyword_count`, `objective_text_len`, `strengths_count`, `weaknesses_count`
- label: `pre_score`, `post_score`

## 2) AI 면접관

### A. 규칙 기반 평가 엔진
- 파일: `src/edu_sim/interview_engine.py`
- 4축 점수(0~4) -> 100점 환산

### B. LLM 기반 평가 엔진
- 파일: `src/edu_sim/llm_interview_engine.py`
- 설정: `interview_mode=llm`
- LLM 실패 시 자동으로 규칙 엔진으로 fallback

### C. LLM 파인튜닝 파이프라인
- 데이터셋 생성: `src/edu_sim_ml/interviewer_finetune.py`
- CLI:
  - `build-interviewer-ft`
  - `train-interviewer-ft-openai`
- 산출물:
  - `ml_data/interviewer_ft_train.jsonl`
  - `ml_data/interviewer_ft_valid.jsonl`
  - `ml_models/interviewer_ft_job.json` (job id, file id 저장)

## 3) 실행 시 모델 선택

`python -m edu_sim.cli run`에서:
- `--student-model-path`: 학습형 학생 모델 사용
- `--interview-mode rule|llm`: 면접 엔진 선택
- `--llm-model`: LLM 모델명 지정

웹 API(`api/index.py`)에서도 동일하게 `config`로 전달 가능합니다.

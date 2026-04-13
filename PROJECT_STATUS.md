# Project Status (Latest Branch)

기준일: 2026-04-13

## 프로젝트 목표

EvalBuddy는 강의 입력 후 다음 두 가지를 수행합니다.

1. 학생 시뮬레이션  
- 특정 학생 프로필 기반 시뮬레이션  
- 특정 수준(지식/지능)의 가상 그룹 시뮬레이션

2. 교육 효과 검증  
- 사전/사후 이해도 변화 추정  
- AI 면접 평가를 통한 성취 수준 정량화

## 현재 구현 범위

### 완료
- 강의 입력
  - plain text
  - `lecture_package`(transcript/materials/metadata)
- 학생 시뮬레이션
  - 규칙 기반 엔진
  - 학습 기반 엔진(`student_model_path` 로드)
- AI 면접 평가
  - 규칙 기반 엔진
  - LLM 기반 엔진 + 실패 시 rule fallback
- ML 파이프라인
  - AI-Hub 데이터 로더
  - lecture_package 변환
  - Whisper 학습 코드
  - 학생 시뮬레이터 학습/저장
  - 면접관 LLM 파인튜닝 데이터셋 생성 + FT job 생성
- 웹/배포
  - `api/index.py` Vercel Python API
  - `web/index.html` 프론트엔드
  - `vercel.json` 라우팅 설정

### 진행 중/운영 단계에서 필요한 것
- 면접관 LLM의 실제 파인튜닝 완료 및 검증
- 인간 평가자 라벨 기반 캘리브레이션(현재 데이터셋은 기존 평가 로그 중심)
- 성능 모니터링 대시보드 및 운영 리포트 자동화

## 모델 산출물 위치

- ASR 모델(예시): `saved_models/whisper_ko_tiny_ft_run1`
- 학생 시뮬레이터 모델: `ml_models/student_sim_model.json`
- 면접관 FT job 메타: `ml_models/interviewer_ft_job.json`

## 웹 API 요약

- `GET /api/health`
- `GET /api/sample-payload`
- `POST /api/simulate`

`/api/simulate`는 CLI와 같은 `WorkflowService`를 직접 사용합니다.

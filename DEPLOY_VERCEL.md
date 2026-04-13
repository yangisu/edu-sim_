# Vercel Deployment Guide

## 1) 준비

프로젝트 루트:

`D:\KIT\edu_sim`

`vercel.json` 기준 라우팅:
- `/api/*` -> `api/index.py`
- `/*` -> `web/index.html`

## 2) 환경변수

Vercel Project Settings -> Environment Variables:

- `OPENAI_API_KEY` (선택, `interview_mode=llm`에서 필요)
- `EVALBUDDY_STORE_FILE` (선택, 기본값은 시스템 temp 경로)

## 3) 배포

```powershell
vercel
vercel --prod
```

## 4) 확인

- `GET /api/health`
- 웹 페이지에서 시뮬레이션 실행
- LLM 모드 사용 시 `interview_mode=llm`으로 테스트

## 5) 주의사항

- Whisper/대형 모델 학습은 로컬 또는 GPU 환경에서 수행하고,
  웹 서비스에는 경량 추론 산출물(JSON 모델 등)만 연결하는 것을 권장합니다.
- 서버리스 환경은 영구 저장소가 아니므로, 운영 로그/리포트는 외부 DB 연동이 필요합니다.

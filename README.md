# Desktop Edge Vision Inspection Station

라즈베리파이 5 기반 탁상형 엣지 비전 검사 스테이션 (Monorepo)

## 아키텍처

```
[Raspberry Pi 5]  ──POST JSON──▶  [Spring Boot Server]  ──REST API──▶  [React Dashboard]
  웹캠 + YOLO                         MySQL DB                            Vite + Tailwind
```

## 디렉토리 구조

```
AiCapstoneV2/
├── edge/          # 라즈베리파이 5 엣지 디바이스 (Python 3.11)
├── backend/       # 중앙 서버 (Java 17 / Spring Boot 3.x)
└── frontend/      # 웹 대시보드 (React 18 / Vite / Tailwind CSS)
```

## 실행 순서

1. `backend/` → Spring Boot 서버 기동 (포트 8080)
2. `edge/` → Python FastAPI 기동 (포트 8000), 검사 루프 시작
3. `frontend/` → `npm run dev` (포트 5173)

## 주요 기능

- PCB 피듀셜 마크 정렬 검사 (YOLOv8n)
- 단선(Trace Open) / 까짐(Metal Damage) 결함 탐지
- 실시간 불량 알람 (GPIO 부저 / LED)
- 중앙 서버 검사 이력 저장 및 React 대시보드 시각화

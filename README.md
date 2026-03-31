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
├── docs/          # 📚 설치 및 실행 가이드 문서
├── edge/          # 라즈베리파이 5 엣지 디바이스 (Python 3.11)
├── backend/       # 중앙 서버 (Java 17 / Spring Boot 3.x)
└── frontend/      # 웹 대시보드 (React 18 / Vite / Tailwind CSS)
```

## 📚 문서 목록

| 문서 | 내용 |
|---|---|
| [01. 프로젝트 구조](docs/01_프로젝트_구조.md) | 전체 아키텍처, 디렉토리 구조, API 목록 |
| [02. Windows 설치/실행](docs/02_Windows_설치_실행.md) | Java/Maven/Node 설치, Spring Boot + React 실행 |
| [03. 라즈베리파이 설정](docs/03_라즈베리파이_설정.md) | SSH 접속, 카메라/GPIO 설정, systemd 자동 시작 |
| [04. GitHub 워크플로우](docs/04_GitHub_워크플로우.md) | 맥북 ↔ 집 PC 코드 동기화 방법 |
| [05. 데이터셋 학습 파이프라인](docs/05_데이터셋_학습_파이프라인.md) | CVAT 라벨링 → Colab 학습 → 가중치 적용 |

## 빠른 시작

### 1. 코드 다운로드
```bash
git clone https://github.com/newUser12312321/AiCapstoneV2.git
cd AiCapstoneV2
```

### 2. Spring Boot 백엔드 (Windows)
```powershell
cd backend
mvn spring-boot:run   # :8080
```

### 3. React 프론트엔드 (Windows)
```powershell
cd frontend
npm install && npm run dev   # :5173
```

### 4. Python 엣지 (라즈베리파이 SSH)
```bash
cd edge
source .venv/bin/activate
python main.py   # :8000
```

## 기술 스택

| 레이어 | 기술 |
|---|---|
| Edge (라즈베리파이) | Python 3.11, FastAPI, OpenCV, YOLOv8n, gpiozero |
| Backend (Windows) | Java 17, Spring Boot 3.x, MySQL, Spring Data JPA |
| Frontend (Windows) | React 18, Vite, Tailwind CSS, Recharts, React Query |

## 주요 기능

- PCB 피듀셜 마크 정렬 검사 (YOLOv8n)
- 단선(Trace Open) / 까짐(Metal Damage) 결함 탐지
- 실시간 불량 알람 (GPIO 부저 / LED)
- 중앙 서버 검사 이력 저장 및 React 대시보드 시각화

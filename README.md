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

> **처음 시작한다면 [00. 빠른 시작](docs/00_빠른시작.md)부터 읽으세요.**

| 문서 | 내용 | 읽어야 할 때 |
|---|---|---|
| [00. 빠른 시작](docs/00_빠른시작.md) | 전체 흐름 1페이지 요약, 매일 실행 순서 | **처음 시작할 때** |
| [01. 프로젝트 구조](docs/01_프로젝트_구조.md) | 전체 아키텍처, 디렉토리 구조, API 목록 | 구조 파악할 때 |
| [02. Windows 설치/실행](docs/02_Windows_설치_실행.md) | Java/Maven/Node/MySQL 설치, 실행 방법 | PC 세팅할 때 |
| [03. 라즈베리파이 설정](docs/03_라즈베리파이_설정.md) | SSH 접속, 카메라/GPIO, systemd 자동 시작 | 라즈베리파이 세팅할 때 |
| [04. GitHub 워크플로우](docs/04_GitHub_워크플로우.md) | 코드 동기화 (맥북 ↔ 집 PC) | 코드 수정/배포할 때 |
| [05. 데이터셋 & 학습](docs/05_데이터셋_학습_파이프라인.md) | CVAT 라벨링 → Colab 학습 → 가중치 적용 | AI 모델 만들 때 |
| [06. 하드웨어 준비물](docs/06_하드웨어_준비물.md) | 부품 목록, GPIO 배선 다이어그램, 웹캠 설정 | 부품 구매/배선할 때 |
| [07. 통합 테스트](docs/07_통합테스트_체크리스트.md) | 단계별 동작 확인 체크리스트 | 전체 검증할 때 |
| [08. 트러블슈팅](docs/08_트러블슈팅.md) | 자주 발생하는 오류 및 해결 방법 | **오류가 생겼을 때** |
| [09. 결함 데이터 합성](docs/09_결함_데이터_합성_방법.md) | 실제 불량 기판 없이 학습 데이터 만드는 4가지 방법 | 데이터셋 부족할 때 |
| [10. 시연 가이드](docs/10_시연_가이드.md) | 발표·시연 순서, 더미/실제 검사 시나리오, Q&A 대비 | **발표·시연할 때** |

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

## Docker로 팀 개발 환경 실행 (권장)

아래 구성은 `mysql + backend + edge + frontend`를 한 번에 실행한다.

### 팀원용 1분 실행 체크리스트

- [ ] Docker Desktop 설치 후 실행 (`Engine running` 상태 확인)
- [ ] 프로젝트 clone 후 루트 폴더 이동 (`AiCapstoneV2`)
- [ ] 아래 명령 실행:

```bash
docker compose up --build
```

- [ ] 브라우저 접속: `http://localhost:5173`
- [ ] 대시보드에서 **로컬 이미지 업로드로 검사** 버튼으로 테스트

문제 발생 시 빠른 확인:

- [ ] 포트 충돌 확인 (`5173`, `8080`, `8000`, `3306`)
- [ ] 로그 확인: `docker compose logs -f`

```bash
docker compose up --build
```

- 프론트엔드: `http://localhost:5173`
- 백엔드 API: `http://localhost:8080`
- 엣지 FastAPI: `http://localhost:8000`
- MySQL: `localhost:3306`

중지:

```bash
docker compose down
```

데이터까지 초기화:

```bash
docker compose down -v
```

### 참고

- 프론트엔드는 Vite 프록시를 사용한다.
  - `/api` -> `VITE_API_PROXY_TARGET` (기본 `http://localhost:8080`)
  - `/edge`, `/captures` -> `VITE_EDGE_CAPTURE_URL`
- Docker 실행 시 `VITE_API_PROXY_TARGET`은 자동으로 `http://backend:8080`을 사용한다.
- Docker 실행 시 `VITE_EDGE_CAPTURE_URL`은 자동으로 `http://edge:8000`을 사용한다.
- 대시보드에서 "로컬 이미지 업로드로 검사" 기능을 사용하면 웹캠 없이도 검사 파이프라인을 테스트할 수 있다.

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

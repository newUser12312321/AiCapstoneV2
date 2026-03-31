# 04. GitHub 워크플로우 (맥북 ↔ 집 PC 코드 동기화)

## 기본 워크플로우

```
맥북에서 코드 수정
    │
    ▼
git add . && git commit -m "설명" && git push
    │
    ▼
GitHub 원격 저장소 (https://github.com/newUser12312321/AiCapstoneV2)
    │
    ▼
집 Windows PC에서 git pull
    │
    ▼
Spring Boot 재시작 / React 자동 반영
```

---

## 맥북에서 코드 수정 후 업로드

```bash
cd /Users/user/Documents/AiCapstoneV2

# 변경된 파일 확인
git status

# 모든 변경사항 스테이징
git add .

# 커밋 (변경 내용을 간결하게 작성)
git commit -m "feat: 대시보드 차트 컴포넌트 수정"

# GitHub에 업로드
git push origin main
```

### 커밋 메시지 규칙 (권장)

| 접두사 | 용도 | 예시 |
|---|---|---|
| `feat:` | 새 기능 추가 | `feat: YOLO 결함 탐지 로직 추가` |
| `fix:` | 버그 수정 | `fix: 통계 API null 오류 수정` |
| `update:` | 기능 수정/개선 | `update: 대시보드 차트 스타일 변경` |
| `docs:` | 문서 작업 | `docs: 설치 가이드 업데이트` |
| `refactor:` | 코드 구조 개선 | `refactor: 검사 서비스 로직 정리` |

---

## 집 Windows PC에서 최신 코드 받기

```powershell
cd C:\Projects\AiCapstoneV2

# 최신 코드 가져오기
git pull origin main

# 변경 내용 확인
git log --oneline -5
```

### 각 파트별 재시작 여부

| 변경된 파일 | 재시작 필요 여부 |
|---|---|
| `backend/` Java 파일 | Spring Boot 재시작 필요 (`Ctrl+C` 후 `mvn spring-boot:run`) |
| `frontend/src/` 파일 | Vite HMR 자동 반영 (재시작 불필요) |
| `frontend/package.json` | `npm install` 후 재시작 필요 |
| `edge/` Python 파일 | SSH로 라즈베리파이에서 재시작 필요 |

---

## 라즈베리파이 코드 업데이트

```powershell
# Windows에서 SSH 접속
ssh pi@192.168.0.25
```

```bash
# 라즈베리파이에서
cd ~/inspection

# 최신 코드 받기
git pull origin main

# FastAPI 서버 재시작
sudo systemctl restart inspection-edge

# 재시작 확인
sudo systemctl status inspection-edge
```

---

## 브랜치 전략 (팀 작업 시)

```bash
# 새 기능 개발 시 브랜치 생성
git checkout -b feature/yolo-defect-detection

# 작업 후 커밋
git add .
git commit -m "feat: YOLO 결함 탐지 2단계 파이프라인 구현"

# GitHub에 브랜치 푸시
git push origin feature/yolo-defect-detection

# 작업 완료 후 main에 병합
git checkout main
git merge feature/yolo-defect-detection
git push origin main
```

---

## 유용한 Git 명령어 모음

```bash
# 변경 내용 확인
git status
git diff

# 커밋 이력 확인
git log --oneline -10

# 특정 파일만 되돌리기
git checkout -- backend/src/main/resources/application.yml

# 마지막 커밋 취소 (코드는 유지)
git reset --soft HEAD~1

# 원격 저장소 최신 상태 확인 (다운로드 없이)
git fetch origin

# 충돌 발생 시 현재 브랜치 상태로 강제 유지
git checkout --ours <충돌파일>
```

---

## GitHub 저장소 정보

- **URL:** https://github.com/newUser12312321/AiCapstoneV2
- **기본 브랜치:** main
- **접근:** Public

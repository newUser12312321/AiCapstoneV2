# 02. Windows 데스크탑 설치 및 실행 가이드

## 사전 요구사항 설치

PowerShell을 **관리자 권한**으로 열고 순서대로 실행

```powershell
# Git
winget install Git.Git

# Java 17
winget install Microsoft.OpenJDK.17

# Maven
winget install Apache.Maven

# Node.js LTS
winget install OpenJS.NodeJS.LTS

# MySQL 8.0
winget install Oracle.MySQL
```

PowerShell 재시작 후 설치 확인:

```powershell
git --version    # git version 2.x
java --version   # openjdk 17.x
mvn --version    # Apache Maven 3.x
node --version   # v20.x
mysql --version  # mysql  Ver 8.x
```

---

## 1단계 — 코드 다운로드

```powershell
cd C:\
mkdir Projects
cd Projects
git clone https://github.com/newUser12312321/AiCapstoneV2.git
cd AiCapstoneV2
```

---

## 2단계 — MySQL 데이터베이스 초기화

```powershell
# MySQL 접속 (설치 시 설정한 root 비밀번호 입력)
mysql -u root -p
```

MySQL 프롬프트에서:

```sql
CREATE DATABASE inspection_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

SHOW DATABASES;  -- inspection_db 확인 후
EXIT;
```

---

## 3단계 — Spring Boot 설정 파일 수정

`backend/src/main/resources/application.yml` 열기:

```powershell
notepad C:\Projects\AiCapstoneV2\backend\src\main\resources\application.yml
```

수정 항목:

```yaml
spring:
  datasource:
    username: root
    password: 여기에_MySQL_비밀번호_입력   # ← 실제 비밀번호로 변경
```

---

## 4단계 — Windows 방화벽 포트 허용

라즈베리파이에서 Windows로 POST 전송이 가능하도록 포트를 열어줍니다.

```powershell
# PowerShell 관리자 권한 실행
netsh advfirewall firewall add rule `
  name="SpringBoot-8080" `
  dir=in action=allow `
  protocol=TCP localport=8080
```

---

## 5단계 — 실행 (터미널 3개)

Windows Terminal에서 탭 3개를 열어 각각 실행합니다.

### 탭 1 — Spring Boot 백엔드

```powershell
cd C:\Projects\AiCapstoneV2\backend
mvn spring-boot:run
```

정상 기동 확인:
```
Started InspectionApplication in 3.x seconds
Tomcat started on port(s): 8080
```

브라우저 확인: http://localhost:8080/api/inspections → `[]` 반환되면 정상

### 탭 2 — React 프론트엔드

```powershell
cd C:\Projects\AiCapstoneV2\frontend
npm install        # 최초 1회만
npm run dev
```

정상 기동 확인:
```
VITE v5.x  ready in 500ms
➜  Local:   http://localhost:5173/
```

브라우저 확인: http://localhost:5173

### 탭 3 — 라즈베리파이 SSH 접속

```powershell
# 라즈베리파이 IP 주소로 접속 (실제 IP로 변경)
ssh pi@192.168.0.25

# 라즈베리파이 안에서 실행
cd ~/inspection/edge
source .venv/bin/activate
python main.py
```

---

## 동작 확인 순서

```powershell
# 1. 라즈베리파이 FastAPI 서버 확인
curl http://192.168.0.25:8000/edge/health

# 2. 더미 데이터 전송 테스트 (Spring Boot 실행 중이어야 함)
curl -X POST http://192.168.0.25:8000/edge/inspect/dummy

# 3. DB 저장 확인
curl http://localhost:8080/api/inspections

# 4. 브라우저에서 대시보드 확인
# http://localhost:5173
```

---

## 자주 발생하는 오류

| 오류 메시지 | 원인 | 해결 방법 |
|---|---|---|
| `command not found: mvn` | Maven 미설치 | `winget install Apache.Maven` |
| `Access denied for user 'root'` | DB 비밀번호 불일치 | `application.yml` 비밀번호 수정 |
| `Connection refused :8080` | Spring Boot 미실행 | `mvn spring-boot:run` 실행 |
| `Connection refused :3306` | MySQL 미실행 | MySQL 서비스 시작 |
| `vite: @/ 경로 not found` | 경로 별칭 미설정 | `vite.config.ts` alias 확인 |
| 포트 8080 응답 없음 | Windows 방화벽 차단 | 방화벽 포트 허용 명령 실행 |

---

## Windows IP 주소 확인 방법

라즈베리파이의 `.env` 파일에 Windows IP를 입력해야 합니다.

```powershell
ipconfig | findstr "IPv4"
# → IPv4 주소 . . . . . . . . . . : 192.168.0.10  (이 주소를 메모)
```

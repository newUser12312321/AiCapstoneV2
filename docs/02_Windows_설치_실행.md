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

# MySQL Server (msstore 인증서 오류 방지용 source 고정)
winget install --id Oracle.MySQL --source winget --accept-package-agreements --accept-source-agreements
```

PowerShell 재시작 후 설치 확인:

```powershell
git --version    # git version 2.x
java --version   # openjdk 17.x
mvn --version    # Apache Maven 3.x
node --version   # v20.x
mysql --version  # mysql  Ver 8.x
```

> `winget` 실행 중 `msstore` 인증서 오류(`0x8a15005e`)가 나면:
>
> ```powershell
> winget source reset --force
> winget source update
> winget install --id Oracle.MySQL --source winget --accept-package-agreements --accept-source-agreements
> ```

### MySQL CLI 확인 (중요)

설치 후 `mysql --version`이 실패하면 `PATH` 미반영 상태입니다.

```powershell
# 직접 경로 실행 확인
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" --version

# PATH 영구 등록 (관리자 PowerShell)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\MySQL\MySQL Server 8.4\bin", "Machine")
```

PowerShell을 완전히 닫고 새로 열어:

```powershell
mysql --version
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

## 2단계 — MySQL 서비스 확인 + 데이터베이스 초기화

먼저 서비스가 실행 중인지 확인:

```powershell
net start MySQL84
```

> `서비스 이름이 잘못되었습니다`가 나오면 설치가 꼬였을 수 있으니
> [08_트러블슈팅.md](08_트러블슈팅.md)의 `MySQL84 서비스를 시작할 수 없습니다` 항목을 먼저 수행하세요.

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

## 3단계 — Spring Boot DB 비밀번호 설정

`backend/src/main/resources/application.yml` 열기:

```powershell
notepad C:\Projects\AiCapstoneV2\backend\src\main\resources\application.yml
```

프로젝트는 `DB_PASSWORD` 환경변수를 우선 사용합니다.

```yaml
spring:
  datasource:
    password: ${DB_PASSWORD:your_password}
```

두 가지 방법 중 하나를 선택:

### 방법 A (권장) — 환경변수 사용

백엔드 실행 전 같은 터미널에서:

```powershell
$env:DB_PASSWORD="여기에_MySQL_root_비밀번호"
```

### 방법 B — application.yml 기본값 직접 수정

`your_password`를 실제 비밀번호로 바꿉니다.

```yaml
spring:
  datasource:
    username: root
    password: ${DB_PASSWORD:여기에_MySQL_비밀번호_입력}
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
$env:DB_PASSWORD="여기에_MySQL_root_비밀번호"   # 방법 A 선택 시
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
➜  Local:   http://localhost:5173/  (또는 5174 등 다른 포트)
```

브라우저 확인: Vite가 출력한 `Local` 주소로 접속

### 탭 3 — 라즈베리파이 SSH 접속

```powershell
# 라즈베리파이 IP 주소로 접속 (실제 IP로 변경)
ssh pi@192.168.0.25

# 라즈베리파이 안에서 실행
cd ~/inspection/edge
source .venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 동작 확인 순서

> PowerShell에서는 `curl -X` 대신 `iwr -Method POST`를 사용합니다.

```powershell
# 1. 라즈베리파이 FastAPI 서버 확인
iwr http://192.168.0.25:8000/edge/health

# 2. 더미 데이터 전송 테스트 (Spring Boot 실행 중이어야 함)
iwr -Method POST http://192.168.0.25:8000/edge/inspect/dummy

# 3. DB 저장 확인
iwr http://localhost:8080/api/inspections

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

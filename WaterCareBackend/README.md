# WaterCare Backend

Android 고객·방문기사 앱과 연결하는 Django REST Framework 백엔드 starter다.

## 1. Windows 첫 실행

```powershell
cd WaterCareBackend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

브라우저에서 `http://127.0.0.1:8000/api/health/`를 열어 다음 응답을 확인한다.

```json
{"status":"ok","service":"watercare-backend"}
```

## 2. Android Emulator 연결

Android 프로젝트 `local.properties`:

```properties
BACKEND_BASE_URL=http://10.0.2.2:8000/
```

에뮬레이터에서 개발 PC의 localhost는 `10.0.2.2`로 접근한다.

## 3. 주요 API

| 기능 | Method | URL |
|---|---|---|
| 상태 확인 | GET | `/api/health/` |
| 회원가입 | POST | `/api/auth/register/` |
| JWT 로그인 | POST | `/api/auth/token/` |
| 내 정보 | GET | `/api/auth/me/` |
| 제품 | GET/POST | `/api/products/` |
| 문의 | GET/POST | `/api/inquiries/` |
| 증상 제출 | POST | `/api/inquiries/{id}/submit_symptom/` |
| 사진 업로드 | POST | `/api/inquiries/{id}/upload_image/` |
| 사진 분석 샘플 | POST | `/api/inquiries/{id}/analyze_image/` |
| 방문 목록 | GET/POST | `/api/visits/` |
| 기사 출발 | POST | `/api/visits/{id}/depart/` |
| 기사 위치 전송 | POST | `/api/visits/{id}/location/` |
| 고객 위치 조회 | GET | `/api/visits/{id}/tracking/` |
| 점검 시작 | POST | `/api/visits/{id}/start/` |
| 방문 완료 | POST | `/api/visits/{id}/complete/` |

## 4. PostgreSQL 전환

처음에는 SQLite로 실행한다. PostgreSQL로 바꿀 때:

```powershell
docker compose up -d
```

`.env`:

```env
DATABASE_ENGINE=postgres
DATABASE_NAME=watercare
DATABASE_USER=watercare
DATABASE_PASSWORD=watercare
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
```

그다음 다시 `python manage.py migrate`를 실행한다.

## 5. 현재 AI 기능

`analyze_image`는 연결 확인을 위한 샘플 규칙 응답이다. 실제 멀티모달 AI와 RAG는 다음 단계에서 `AI service` 또는 별도 모듈로 교체한다.

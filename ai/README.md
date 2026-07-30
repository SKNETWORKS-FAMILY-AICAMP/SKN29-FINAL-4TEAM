# WaterCare AI/RAG

## 재현 가능한 실행 환경

- 검증 Python: `3.10.20`
- PostgreSQL과 `vector` 확장
- `AI_VECTOR_DSN`: pgvector 연결 문자열. 설정하지 않으면 Local 모드는 안전 분류와 근거 없음 정책까지만 실행한다.
- 의존성 Manifest: `ai/pyproject.toml`의 정확한 버전 고정 목록
- AI 계약 버전: `1.1.0`

```powershell
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pip install -e ai
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8000
```

Base URL은 `http://127.0.0.1:8000`, Health Check는 `GET /health`, 분석
API는 `POST /api/v1/ai/analyze?mode=mock|local`이다. Backend의
`AI_SERVICE_BASE_URL`도 Port `8000`으로 맞춰야 한다. `inquiry_id`는 Backend
내부 정수 PK가 아닌 공개 업무 식별자를 사용한다.

요청 Body의 `correlation_id`는 선택적 `X-Correlation-ID` Header와 같아야
하며 모든 성공·오류 응답 Header에 반환된다. `ai_request_id`와
`state_version`도 요청·응답에서 보존한다.

## 검증

```powershell
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest ai/tests/unit/
```

Runtime은 `ai/configs/retry_policy.yaml`을 시작 시 검증하고 전체 30초,
AI 내부 최대 1회, Backend 자동 재시도 0회 정책을 강제한다. Timeout은
`AI-TIMEOUT-01`/HTTP 504로 반환하며 재시도를 통해 30초 한도를 연장하지
않는다.

Local 검색은 `BAAI/bge-m3`의 1024차원 정규화 임베딩과 pgvector Cosine Exact Search(`<=>`)를 사용한다. 제품 코드·D세대·공식 검증·고객 안내 허용 조건은 유사도 계산 전 SQL에서 제한한다. 모델 파일과 DB가 준비되지 않은 환경에서는 자동으로 하드코딩 검색으로 대체하지 않고 근거 없음 상담 경로를 반환한다.

## 실제 pgvector 적재·검증

검증 모델 Revision은
`5617a9f61b028005a4858fdac845db406aefb181`, Vector 차원은 `1024`,
검색 방식은 ANN을 사용하지 않는 Cosine Exact Search다. 실제 연결 문자열은
명령 인수나 Git에 남기지 않고 `AI_VECTOR_DSN`으로 전달한다.

```powershell
$env:AI_VECTOR_DSN='<격리 PostgreSQL DSN>'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'

C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m ai.scripts.build_vector_index
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m ai.scripts.verify_pgvector_runtime
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -v
```

`build_vector_index`는 `CREATE EXTENSION vector`, `vector(1024)` Table 생성,
승인 청크 임베딩 및 청크 ID 기준 UPSERT, 행 수·Hash Manifest 검증을 수행한다.
`verify_pgvector_runtime`은 실제 Top-5 평가, 금지 모델·세대·미검증·사용 금지
Fixture의 SQL 필터 누출, 잘못된 Vector 차원 거부를 확인한다.

2026-07-30 격리 검증 결과는
`ai/evaluation/reports/pgvector_verification.json`에 기록되어 있다. 이 DDL은
격리 실증용이며 팀 공용 Backend DB 반영에는 DB 담당자의 정식 Migration
검토가 필요하다.

# WaterCare AI/RAG

## 재현 가능한 실행 환경

- 검증 Python: `3.10.20`
- PostgreSQL과 `vector` 확장
- 의존성 Manifest: `ai/requirements.lock`, `ai/requirements.txt`, `ai/pyproject.toml`
- AI 계약 버전: `1.1.0`

저장소 Root에서 개인 PC 절대 경로 없이 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ai\requirements.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
```

Base URL은 `http://127.0.0.1:8001`, Health Check는 `GET /health`, 분석
API는 `POST /api/v1/ai/analyze?mode=mock|local`이다. Backend의
`AI_SERVICE_BASE_URL`도 Port `8001`로 맞춘다. `inquiry_id`는 Backend가
발급한 Public UUID를 사용하며 내부 정수 PK나 업무 코드를 전달하지 않는다.

요청 Body의 `correlation_id`는 선택적 `X-Correlation-ID` Header와 같아야
하며 모든 성공·오류 응답 Header에 반환된다. `ai_request_id`와
`state_version`도 요청·응답에서 보존한다.

## Timeout·Retry·로그

Runtime은 `ai/configs/retry_policy.yaml`을 시작 시 검증한다.

- 전체 HTTP Timeout: 30초
- AI 내부 재시도 상한: 1회
- 현재 Retry Loop: 비활성화, 실제 재시도 0회
- Backend 자동 재시도: 0회

Timeout은 `AI-TIMEOUT-01`/HTTP 504로 반환한다. 취소 신호를 작업 Thread의
파이프라인 단계 경계에 전달하고, pgvector 연결·SQL에는 별도 하위 Timeout을
적용한다. 구조화 로그에는 `correlation_id`, `ai_request_id`,
`state_version`, Stage, 실제 `retry_count`, latency와 오류 코드만 남기며
고객 원문·Prompt·Secret·개인정보는 기록하지 않는다.

## 단위 검증

```powershell
.\.venv\Scripts\python.exe -m pytest ai\tests\unit
```

## RAG 실행 기준

Local 검색은 `BAAI/bge-m3`의 1024차원 정규화 임베딩과 pgvector Cosine
Exact Search(`<=>`)를 사용한다. `WPUJAC104DWH`·D세대·공식 검증·고객 안내
허용 조건을 유사도 계산 전에 제한한다. 미지원 모델·세대와 미검증 FAQ 단독
근거 요구는 임베딩과 DB Query 전에 차단한다.

검증 모델 Revision은
`5617a9f61b028005a4858fdac845db406aefb181`이다. 실제 연결 문자열은 Git에
남기지 않고 `AI_VECTOR_DSN`으로 전달한다.

## 기존 Schema에 청크 UPSERT

`build_vector_index`는 `CREATE EXTENSION`이나 `CREATE TABLE`을 실행하지
않는다. 팀 DB에서는 DB 담당자의 Migration으로 Schema가 준비된 후에만
승인 청크를 UPSERT한다. 결과는 DB 전체 행 수가 아니라 이번 배치의 청크 ID
범위로 검증한다.

```powershell
$env:AI_VECTOR_DSN='<PostgreSQL DSN>'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'
.\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
```

## Disposable pgvector 실증

Schema 초기화와 검증 Fixture는 DB 이름에 `verify`, `test`, `tmp`,
`disposable` 중 하나가 포함되고 명시적 확인값이 있을 때만 실행한다.

```powershell
$env:AI_VECTOR_DSN='<격리 PostgreSQL DSN>'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'
$env:AI_VECTOR_DISPOSABLE_CONFIRM='DISPOSABLE_ONLY'

.\.venv\Scripts\python.exe -m ai.scripts.initialize_disposable_vector_schema
.\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
.\.venv\Scripts\python.exe -m ai.scripts.verify_pgvector_runtime
.\.venv\Scripts\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -v
```

검증 보고서는 실제 pgvector Query와 검색 전 정책 차단 Case를 분리한다.
금지 Fixture는 한 Transaction에서 확인한 후 Rollback하며 공유 DB 식별 Guard를
통과하지 못하면 삽입 전에 중단한다. 팀 공용 DB Schema는 반드시 Backend/DB
담당자의 정식 Migration으로 반영한다.

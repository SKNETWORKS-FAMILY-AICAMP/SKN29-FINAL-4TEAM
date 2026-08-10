# WaterBridge AI/RAG

## 재현 가능한 실행 환경

- 검증 Python: `3.13.13`
- PostgreSQL과 `vector` 확장
- 의존성 Manifest: `ai/requirements.lock`, `ai/requirements.txt`, `ai/pyproject.toml`
- AI 계약 버전: `3.0.0`

Backend와 AI는 Python 버전만 `3.13.13`으로 통일하고 가상환경과 의존성은
분리한다. Backend는 `backend/.venv`, AI는 `ai/.venv`를 사용한다. 한쪽
환경에 다른 서비스의 패키지를 설치하지 않는다.

저장소 Root에서 개인 PC 절대 경로 없이 실행한다. 먼저 현재 Python이
정확히 `3.13.13`인지 확인한 뒤 AI 전용 가상환경을 생성한다.

```powershell
python --version
# 기대값: Python 3.13.13

python -m venv ai\.venv
.\ai\.venv\Scripts\python.exe --version
.\ai\.venv\Scripts\python.exe -m pip install --upgrade pip
.\ai\.venv\Scripts\python.exe -m pip install -r ai\requirements.lock
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
```

기존 `ai/.venv`의 Python 버전이 다르면 그 환경을 그대로 재사용하지 않고
Python `3.13.13`으로 다시 생성한다. 가상환경 디렉토리는 Git에 포함하지
않으며 다른 팀원에게 복사하지 않는다.

`ai/requirements.lock`은 Python 3.13.13·Windows x86-64 개발/테스트용이며
Hash를 포함하지 않는다. Linux Container 배포 시에는 대상 Image에서 별도
Lock을 생성하고 설치·테스트를 다시 검증한다.

Base URL은 `http://127.0.0.1:8001`, Health Check는 `GET /health`, 분석
API는 `POST /api/v1/ai/analyze?mode=mock|local`이다. `mock`은 계약 연결용
정적 응답이고 검색을 실행하지 않는다. `local`의 일반·주의 입력은 실제
Vector Store 검색을 요구한다. `local`에서 Vector Store가 설정되지 않은
상태를 정상 검색 0건으로 대체하지 않는다. Backend의
`AI_SERVICE_BASE_URL`도 Port `8001`로 맞춘다. `inquiry_id`는 Backend가
발급한 Public UUID를 사용하며 내부 정수 PK나 업무 코드를 전달하지 않는다.

요청 Body의 `correlation_id`는 UUID이며 선택적 `X-Correlation-ID` Header와 같아야
하며 모든 성공·오류 응답 Header에 반환된다. `ai_request_id`와
`state_version`도 요청·응답에서 보존한다.

## Timeout·Retry·로그

Runtime은 `ai/configs/retry_policy.yaml`을 시작 시 검증한다.

- 전체 HTTP Timeout: 30초
- AI 내부 재시도 상한: 1회
- 현재 Retry Loop: 검색 Provider의 일시적 연결·Timeout 오류에 한해 활성화
- 재시도 Backoff: 0.5초, 검색 Stage 5초와 전체 30초 예산 안에서만 실행
- Backend 자동 재시도: 0회

설정 누락, 잘못된 Provider 결과, Schema·정책 오류와 위험 규칙 분기는
재시도하지 않는다. 첫 검색 실패 후 두 번째 시도를 실제 시작한 경우에만
성공·오류 응답과 구조화 로그의 `retry_count`를 `1`로 기록한다.

Timeout은 `AI-TIMEOUT-01`/HTTP 504로 반환한다. 취소 신호를 작업 Thread의
파이프라인 단계 경계에 전달하고, pgvector 연결·SQL에는 별도 하위 Timeout을
적용한다. 구조화 로그에는 `correlation_id`, `ai_request_id`,
`state_version`, Stage, 실제 `retry_count`, latency와 오류 코드만 남기며
고객 원문·Prompt·Secret·개인정보는 기록하지 않는다.

Local Embedding은 Python Thread 안에서 실행되므로 이미 시작된 Torch 연산을
강제로 종료하지 않는다. HTTP Timeout 뒤에는 취소 Token으로 다음 Stage와
DB 진입을 차단하고, 해당 Thread가 실제 종료될 때까지 작업 Slot을 점유한다.
동시에 실행할 수 있는 Local 분석 Worker는 `AI_MAX_IN_FLIGHT_WORKERS`로
제한하며 기본값은 `2`, 허용 범위는 `1~32`다. PostgreSQL 연결과 SQL은
각각 5초 Timeout을 별도로 적용한다.

## 단위 검증

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit
```

## Backend↔AI 결정적 Fixture

F01~F12 입력·기대값·책임 경계는 다음 Manifest를 사용한다.

```text
ai/evaluation/datasets/backend_integration/fixture_manifest.json
```

AI 소유 구간의 in-process HTTP Adapter 검증:

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_backend_integration_fixtures.py -q
```

이 검증은 장애·Timeout을 결정적으로 재현하는 단위 HTTP Gate다. 실제 Uvicorn,
pgvector, Backend 저장을 모두 통과한 공동 E2E 증거로 사용하지 않는다. F11
stale `state_version` 차단은 Backend 소유이며, F12의 답변·거절 저장과 버전
증가는 Backend와 공동 검증한다.

위험 응답은 자연어 `detected_risks`와 별개로 계약 `3.0.0`의 필수 필드
`safety_assessment.matched_safety_rule_ids`에 안정적인 규칙 ID를 반환한다.
Backend는 이 ID를 자연어에서 재추론하지 않고 State Event Guard에 직접 사용한다.

공식 근거의 AI 원천 식별자와 실행 재현 값은 다음 Manifest를 사용한다.

```text
ai/configs/canonical_evidence_identity.json
ai/configs/runtime_identity.json
```

첫 번째 Manifest는 승인 청크 7개의 `chunk_id`와 원문·페이지·Source Hash를
고정한다. Backend `DocumentChunk.public_id`는 Backend·Database 소유이므로 AI가
생성하지 않으며, Backend가 이 Manifest를 기준으로 Crosswalk를 완성해야 한다.
두 번째 Manifest의 실행 식별값은 고객 공개 응답에 추가하지 않고 Backend 환경
설정과 `AIRun` 감사 레코드로 전달·저장한다.

## 상담 요약 결정론적 기준선

`ai/app/generation/consultation_summary/`는 외부 LLM 없이 실행 가능한 상담사
검토용 요약 Fallback 기준선이다. 고객 진술과 전달된 상담 기록만 요약하고,
명시적 위험 신호는 기존 `SafetyRuleLoader`의 규칙으로 우선 표시한다. 확정 진단,
Backend 상태 변경, 방문 필요 여부의 자동 확정은 수행하지 않는다.

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_consultation_summary.py -q
```

이 Generator가 존재한다는 이유로 `Consultation Summary Agent`나 실제 LLM
연동 완료로 표시하지 않는다. Agent Runtime Routing·Handoff와 실제 Provider는
별도 Gate다.

## RAG 실행 기준

Local 검색은 `BAAI/bge-m3`의 1024차원 정규화 임베딩과 pgvector Cosine
Exact Search(`<=>`)를 사용한다. `WPUJAC104DWH`·D세대·공식 검증·고객 안내
허용 조건을 유사도 계산 전에 제한한다. 미지원 모델·세대와 미검증 FAQ 단독
근거 요구는 임베딩과 DB Query 전에 차단한다.

검색 결과와 장애는 다음처럼 분리한다.

| 상황 | HTTP·응답 | 재시도 |
| --- | --- | --- |
| 정상 검색·근거 있음 | `200`, `SUCCEEDED` | 불필요 |
| 정상 검색·근거 0건 | `200`, `FALLBACK`, `RETRIEVING` | 불필요, 상담 전환 |
| Vector Store 필수 설정 누락 | `503`, `AI-FAILED-01`, `RETRIEVING` | `false` |
| 설정된 검색 Provider 일시 오류 후 복구 | `200`, 결과 상태 유지, `retry_count=1` | 내부 1회 완료 |
| 설정된 검색 Provider 일시 오류 2회 | `503`, `AI-FAILED-01`, `RETRIEVING`, `retry_count=1` | 내부 1회 소진, `true` |
| 비일시적 검색 결과·검증 오류 | `503`, `AI-FAILED-01`, `RETRIEVING`, `retry_count=0` | 내부 재시도 없음 |
| 검색·Pipeline Timeout | `504`, `AI-TIMEOUT-01`, 실제 실패 Stage | `true` |

위험 입력은 안전 규칙이 검색보다 우선하므로 Vector Store가 없더라도 검색을
건너뛰고 `TOTAL_STOP` 등 안전 안내를 반환할 수 있다. 운영 Health·Readiness와
Backend 공개 `evidence_status`·저장 방식은 별도 통합 계약에서 확정한다.

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
.\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
```

## Disposable pgvector 실증

Schema 초기화와 검증 Fixture는 DB 이름에 `verify`, `test`, `tmp`,
`disposable` 중 하나가 포함되고 명시적 확인값이 있을 때만 실행한다.

```powershell
$env:AI_VECTOR_DSN='<격리 PostgreSQL DSN>'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'
$env:AI_VECTOR_DISPOSABLE_CONFIRM='DISPOSABLE_ONLY'

.\ai\.venv\Scripts\python.exe -m ai.scripts.initialize_disposable_vector_schema
.\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_pgvector_runtime
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -v
```

검증 보고서는 실제 pgvector Query와 검색 전 정책 차단 Case를 분리한다.
금지 Fixture는 한 Transaction에서 확인한 후 Rollback하며 공유 DB 식별 Guard를
통과하지 못하면 삽입 전에 중단한다. 팀 공용 DB Schema는 반드시 Backend/DB
담당자의 정식 Migration으로 반영한다.

# WaterBridge AI/RAG

## 재현 가능한 실행 환경

- 검증 Python: `3.13.13`
- PostgreSQL과 `vector` 확장
- 환경 설치 SSOT: `ai/requirements.lock`
- 직접 의존성 선언·정합성 대상: `ai/requirements.txt`, `ai/pyproject.toml`
- AI 계약 버전: `4.0.0`

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

위 `ai/requirements.lock` 설치가 AI 개발·테스트 실행 환경의 공식 SSOT다. AI는
저장소 Root에서 `ai.app`을 소스로 직접 Import하는 Monorepo Source Runtime이며,
현재 배포 가능한 Python Package나 Wheel로 제공하지 않는다. 따라서 다음 명령은
공식 설치·실행 방식이 아니며 지원하지 않는다.

```powershell
pip install ai
pip install .\ai
pip install -e .\ai
```

`ai/pyproject.toml`은 프로젝트 Metadata, 직접 의존성 정합성, Pytest 설정을
관리하지만 setuptools Package 배포 계약은 아니다. 실행·Import·Test 명령은
반드시 저장소 Root에서 수행한다. 저장소 밖 작업 경로에서 `import ai.app.main`을
지원하려면 별도의 Package Layout 전환과 Wheel·Editable 설치 검증을 선행해야
한다.

기존 `ai/.venv`의 Python 버전이 다르면 그 환경을 그대로 재사용하지 않고
Python `3.13.13`으로 다시 생성한다. 가상환경 디렉토리는 Git에 포함하지
않으며 다른 팀원에게 복사하지 않는다.

`ai/requirements.lock`은 Python 3.13.13·Windows x86-64 개발/테스트용이며
Hash를 포함하지 않는다. GitHub Actions의 Ubuntu 24.04 x86_64·CPython
3.13.13·CPU-only Gate 후보는 `ai/requirements-linux.lock`을 사용한다. 두 Lock은
대상 OS가 다르므로 서로 대체하지 않는다.

Linux CI Lock은 저장소 Root에서 다음과 같이 생성·검증한다. 생성과 검증은 서로
다른 새 Container에서 실행되며, `torch==2.13.0+cpu`는 PyTorch 공식 CPU Wheel
Index에서 설치한다.

```powershell
docker build --file ai/docker/linux-lock/Dockerfile --tag waterbridge-ai-linux-lock:py31313-ubuntu2404 .
docker run --rm --volume "${PWD}:/workspace" waterbridge-ai-linux-lock:py31313-ubuntu2404
docker run --rm --volume "${PWD}:/workspace" --tmpfs /workspace/ai/tests/.linux-pytest-root --env PYTHONPYCACHEPREFIX=/tmp/pycache waterbridge-ai-linux-lock:py31313-ubuntu2404 python ai/scripts/verify_linux_ci_lock.py
```

생성 입력은 `ai/requirements-linux.in`, 결과는 `ai/requirements-linux.lock`이다.
Resolver pip은 `26.1.2`로 고정한다. 이 Lock은 GitHub Actions Required Gate를 위한
CI 후보이며, Package Hash는 포함하지 않는다. 운영 Container 공용 여부는 EC2
OS·Architecture와 AI Base Image가 확정된 뒤 별도로 판정한다.

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

위험 응답은 자연어 `detected_risks`와 별개로 계약 `4.0.0`의 필수 필드
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

## 증상 구조화·Follow-up LLM Runtime

`OPENAI_API_KEY`가 설정되면 `PipelineRouter`가 두 전용
Responses API Client를 구성한다. 증상 구조화는
`symptom_structuring/v1`, 질문 표현은 `followup_question/v1`의 ACTIVE
Prompt와 `ai/configs/model_profiles.yaml`의 해당 Task Profile을 사용한다.

증상 LLM의 권한은 기존 `StructuredSymptom` DTO 생성으로 제한한다. 허용된
`symptom_type`·출수 종류, 확인된 오류 코드, 선택 증상 및 이전 문진 답변을
검증한 뒤에만 결과를 채택한다. Timeout, Provider 오류, invalid JSON, Schema
위반, 미지원 값은 기존 `SymptomNormalizer` 기반 결과로 복귀한다. Safety는
이후 기존 Rule/A2A 단계에서 별도로 판정하며 LLM 출력으로 변경하지 않는다.

Follow-up은 `MissingFieldChecker`가 결정한 target field의 집합·순서와 기존
question ID·선택지를 유지하고 질문 문구만 LLM 후보로 교체한다. 빈 문구,
target field 변경·중복, Schema 위반, Provider 실패 시 기존 고정 질문을 그대로
사용한다. `DuplicateQuestionGuard`와 Evidence Applicability 질문 경계도 유지한다.

다음 Span은 고객 원문·Prompt·연락처를 Attribute에 기록하지 않고 모델,
Prompt Version, 검증 결과와 fallback 여부만 기록한다.

```text
waterbridge.symptom_structuring.llm
waterbridge.symptom_structuring.validate
waterbridge.symptom_structuring.fallback
waterbridge.followup.generate
waterbridge.followup.validate
waterbridge.followup.fallback
```

외부 Provider가 없는 Unit/PR CI에서는 Client를 주입하지 않거나 Fake Client를
사용하며 기존 Rule·고정 질문 fallback을 결정적으로 검증한다.

## 고객 안내 LLM Runtime

`mode=local`의 일반·주의 증상에서 공식 Evidence가 발견된 경우에만 OpenAI
`gpt-4.1-mini`를 호출한다. LLM Structured Output은 내부
`GuidanceGenerationResult`의 `message`, `next_actions` 두 필드로 제한한다.
Safety 판정, 사용 안내 상태, 제한 기능, Evidence와 요청 추적 식별자는 기존
Rule·Runtime이 조립한다. Fallback 원인은 공개 Backend↔AI 계약 `4.0.0`의
안정 코드로만 노출하고 내부 Harness 상세는 공개하지 않는다.

위험 입력은 Safety Rule이 먼저 처리하고, 근거 없음은 기존
`PENDING_CONSULTATION` Fallback을 사용하므로 두 경로 모두 LLM을 호출하지
않는다. 생성 결과는 금지 표현·행동 Validator를 통과해야 하며 안전 위반 시
결정적 안내로 복귀한다. Provider Schema 오류·거부·구성 오류는 정상 성공으로
감추지 않고 `503`으로 반환한다. Provider Timeout은 내부 최대 1회 재시도 후
`504 AI-TIMEOUT-01`, `failure_stage=GENERATING`으로 반환하며 이후 상담 전환은
Backend 책임이다.

실행 환경에는 값 자체를 Git·문서·로그에 남기지 않고 다음 이름으로 주입한다.

```text
OPENAI_API_KEY
AI_LLM_MODEL=gpt-4.1-mini
AI_VECTOR_DSN
AI_EMBEDDING_REVISION
```

실제 Provider 호출이 없는 Fake Client 단위 테스트는 구조·안전 경계 증거이며
실제 LLM 호출 PASS로 보고하지 않는다.

## 3-Agent 후보 Runtime

기본 `local` 실행은 계속 `SingleRAGPipeline`이다. 6주차 후보 Runtime은 같은
공개 계약 `4.0.0`을 유지하면서 `Symptom Analysis`, `Evidence Analysis`,
`Care Decision` 역할과 Supervisor Handoff를 내부에서 실행한다.

```powershell
# 안정 기준선
$env:AI_PIPELINE_RUNTIME='single_rag'

# 후보 Runtime을 명시적으로 검증하는 Process에서만 사용
$env:AI_PIPELINE_RUNTIME='multi_agent'
```

지원하지 않는 값은 Single RAG로 묵시적 복귀하지 않고 HTTP 503 구성 실패로
종료한다. `multi_agent` 설정은 운영 채택을 의미하지 않는다. Agent 단위·Routing,
Single RAG 비교, 실제 pgvector·OpenAI·Backend HTTP와 고객 질문→답변→재검색 E2E가
같은 Commit에서 통과하기 전에는 기본값을 변경하지 않는다.

정보 부족과 공식 근거 부재는 분리한다. 검색 근거가 부족하고 답변 가능한 추가
질문이 있으면 `SUCCEEDED` 질문 결과로 고객 입력을 기다린다. 질문이 남지 않았는데
공식 Evidence가 0건이면 기존 `NO_EVIDENCE` Fallback을 적용한다. Agent Handoff
Metadata는 고객 공개 응답에 포함하지 않으며 고객 원문·Prompt·Evidence 본문·Secret을
기록하지 않는다.

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

물맛·냄새 증상은 `흙맛`, `흙 냄새`, `토양 냄새`를 포함해
`물맛/냄새 이상`으로 정규화한다. 이 증상은 Vector 유사도 상위 후보를 그대로 생성
단계에 넘기지 않고 Canonical `topic_code=symptom_taste_odor`와 일치하는 공식 근거만
선별한다. 팀 DB Readonly View가 `topic_code`를 직접 제공하지 않는 현재 계약에서는
고정 Canonical `chunk_id` 매핑으로 주제를 복원하며, 매핑되지 않은 후보는 맛·냄새
안내 근거로 사용하지 않는다.

맛·냄새 공식 근거의 적용 조건을 확인하기 위해 발생 시점, 대상 출수 종류, 기존 조치와
전용 적용조건 문진이 모두 확인되기 전에는 임베딩·DB 검색·LLM 생성을 실행하지 않는다.
전용 문진은 `10일 이내 부재`, `10일 이상 부재`, `장시간 미사용`, `부적합 장소 설치`,
`해당 없음`, `확인 불가`만 고정 코드로 수용한다. 자유 답변 원문은 Provider에 보내지
않고, `10일 이내 부재`의 비식별 고정 요약만 생성 입력에 포함한다.

현재 Canonical 근거에서 고객 자가안내로 허용하는 분기는 `10일 이내 부재`뿐이다.
나머지 적용조건·해당 없음·확인 불가는 검색 후 부적합 근거를 제거하고 LLM을 호출하지
않으며 기존 `NO_EVIDENCE` Fallback으로 상담 경로를 사용한다. 조건 미응답은
`SUCCEEDED`, 추가 질문, `PENDING_CONSULTATION`으로 고객 답변을 기다린다.

위험 입력은 안전 규칙이 검색보다 우선하므로 Vector Store가 없더라도 검색을
건너뛰고 `TOTAL_STOP` 등 안전 안내를 반환할 수 있다. 운영 Health·Readiness와
Backend 공개 `evidence_status`·저장 방식은 별도 통합 계약에서 확정한다.

검증 모델 Revision은
`5617a9f61b028005a4858fdac845db406aefb181`이다. 실제 연결 문자열은 Git에
남기지 않고 `AI_VECTOR_DSN`으로 전달한다.

`AI_VECTOR_DSN`이 설정된 Process는 Uvicorn 시작 단계에서 고정 Revision의
Embedding 모델을 로드하고 비민감 고정 문자열로 첫 Encode까지 완료한다. 이후
요청은 같은 검색 서비스를 공유하며 Warmup은 Process당 한 번만 실행한다. 따라서
최초 시작은 모델 초기화만큼 늦어질 수 있지만 이 시간은 요청별 30초 Timeout에
포함되지 않는다. Lifespan은 Warmup 완료 후에만 요청 처리를 시작하고 Warmup 실패는
애플리케이션 시작 실패로 드러낸다. `/health` 성공은 모델 로드·첫 Encode Warmup
완료를 뜻하지만 실제 pgvector Query와 팀 DB 준비 완료까지 보장하는 Readiness
판정은 아니다.

### 보호 DB 오류와 배포 로그 경계

`PgVectorStore`의 검색·행 수 확인·적재·Disposable Schema 초기화는 모두
`ProtectedDatabaseOperationError` 경계를 사용한다. `psycopg` Driver 메시지와 원본
예외 Context는 API·구조화 로그·Traceback 수집기로 전달하지 않으며 고정된 비민감
메시지만 상위 Retrieval 경계로 보낸다.

재시도 여부는 Driver 메시지를 파싱하지 않고 SQLSTATE와 안전한 `retryable` 속성으로
판정한다. 연결·일시적 자원·Statement Timeout은 기존 계약대로 최대 1회 재시도하고,
인증·권한·Schema·데이터·무결성 오류는 재시도하지 않는다. Assertion, 입력 검증과
계약 불일치는 보호 DB 오류로 숨기지 않는다.

배포 환경은 다음 항목을 함께 적용한다.

- `DJANGO_DEBUG`나 AI Server Debug Traceback을 운영에서 활성화하지 않는다.
- DSN은 Process Secret으로만 주입하고 명령행 인자·로그 Field로 전달하지 않는다.
- Sentry·APM·Cloud Log Agent가 Driver Span을 직접 수집한다면 해당 제품의 Secret
  Redaction 또는 `before_send` Filter를 별도로 활성화한다.
- HTTP 응답·stdout·stderr의 Sentinel 검증과 실제 Readonly pgvector 정상 검색을 모두
  통과해야 배포 DB 오류 경계를 PASS로 판정한다.

## 팀 DB 읽기 전용 Runtime

팀 DB의 공식 Evidence·Embedding 적재, Crosswalk 적용과 View 게시 책임은
Backend·Database 영역에 있다. AI 최소 권한 Role은
`backend_ai_rag_chunks_v1` View만 `SELECT`하며 `build_vector_index`로 팀 DB에
쓰지 않는다. 기본 `mvp` Profile은 승인 7건을 유지한다. 3모델 53건은 Backend
Importer·Crosswalk·Readonly View 검증과 실제 `index_manifest_3model.json` 확보 후
`AI_RAG_RUNTIME_PROFILE=three_model_integration`을 명시한 통합검증 Process에서만
선택한다. 이 Profile은 Public Runtime 활성화를 의미하지 않는다. 실제 Secret 값은
명령·문서·로그에 남기지 않는다.

```powershell
$env:OPENAI_API_KEY='<Secret>'
$env:AI_LLM_MODEL='gpt-4.1-mini'
$env:AI_VECTOR_DSN='<최소 권한 읽기 전용 DSN>'
$env:AI_VECTOR_TABLE_NAME='backend_ai_rag_chunks_v1'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'
$env:AI_RAG_RUNTIME_PROFILE='mvp'
$env:AI_PIPELINE_RUNTIME='multi_agent'
$env:AI_RETRIEVAL_TRANSPORT='direct'
$env:AI_EVIDENCE_ENVIRONMENT_ID='TEAM_DB_STAGING'
$env:AI_MODEL_PROVIDER='openai'
$env:AI_MODEL_NAME='gpt-4.1-mini'
$env:AI_PROMPT_VERSION='customer_guidance/v3'

.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\integration\test_pgvector_runtime.py -v

.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_local_runtime

.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test `
  --base-url http://127.0.0.1:8001 `
  --mode local `
  --expected-result-status SUCCEEDED `
  --expected-failure-stage NONE `
  --expected-evidence-id RAG-WPUJAC104DWH-LOW-FLOW-001 `
  --minimum-evidence-count 1 `
  --require-verified-evidence `
  --expected-guidance-message '출수량이 적으면 조리수 또는 다른 수전을 동시에 사용하는지 확인하고 조리수 사용을 멈춘 뒤 출수합니다. 필터 교체 주기를 확인해 필터를 교체하고, 교체 후에도 출수량이 적으면 고객상담센터에 연락합니다. 순간 온수 출수는 냉수와 정수보다 느릴 수 있고 설치 지역 수압이 약해도 출수 속도가 느릴 수 있습니다.'
```

3모델 공식 통합검증에서는 위 환경을 주입한 같은 Process에 다음 설정을 추가한다.
환경변수에는 임의 Manifest 경로를 받지 않으며, 허용된 Profile 이름이 고정 경로와
정책을 함께 선택한다.

```powershell
$env:AI_RAG_RUNTIME_PROFILE='three_model_integration'

.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_three_model_readonly_runtime
.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_local_runtime
```

`three_model_integration`은 `ai/configs/index_manifest_3model.json`, Index Version
`2.0.0`, Child 53건과 모델별 15/19/19, 정확 판매코드 정책을 함께 검증한다. 공식
Importer에 사용된 Manifest의 출처와 Hash를 확인할 수 없으면 파일을 임의 생성하지
않고 Runtime 검증을 중단한다.

팀 DB 통합 테스트는 환경변수 미주입 시 `SKIP`하지 않고 실패한다. 대상 객체가
정확히 `backend_ai_rag_chunks_v1` View인지, 현재 Role은 SELECT만 가능하고
INSERT·UPDATE·DELETE·TRUNCATE 권한이 없는지 확인한다. 또한 Transaction
Read-only, public Schema CREATE 금지와 Backend 원본 사용자·Chunk·Embedding·
Crosswalk Table의 SELECT/DML 금지까지 검증한다.

`verify_local_runtime`은 Clean Worktree와 Python `3.13.13`에서만 증거를 생성하고,
선택 Profile의 전체 Canonical Identity를 먼저 검증한다.
기본 `mvp`는 7건 범위를, `three_model_integration`은 Child 53건과 3개 판매코드를
확인한 뒤 모델별 대표 정상 Case로 실제 Retriever·Provider를 실행한다. 반환된
Evidence가 해당 판매코드의 Canonical ID 집합에만 속하는지, Prompt Version과 Token
사용 증거가 있는지도 확인한다. 7/53은 Canonical 파일의 기대 수이며 DB 전체 행 수가
아니다. DB cardinality·Readonly 권한, Harness·HITL·Consultation Handoff,
Backend 저장과 Web/Mobile 소비는 이 Gate에서 `NOT_VERIFIED_BY_THIS_GATE` 또는
`OWNER_EVIDENCE_REQUIRED`로 분리한다. Secret·DSN·질의·Evidence ID·본문은 출력하지
않고 반환 ID 집합은 SHA-256으로만 남긴다. `OPENAI_BASE_URL`이 공식 기본 Endpoint와
다르면 URL을 노출하지 않고 이 Gate를 fail-closed로 종료한다. 정제된 JSON에는
`integrity.payload_sha256`을 포함하되, 실제 저장 파일의 SHA-256은 별도로 계산한다.
Backend 통합 Process에도 위 세 AIRun 환경변수를 같은 배포 설정에서 주입하고,
E2E에서는 저장된 AIRun 값이 `openai`, `gpt-4.1-mini`,
`customer_guidance/v3`인지 반드시 대조한다. 이 대조 전에는 Backend 수직 Gate를
PASS로 판정하지 않는다.

마지막 명령은 HTTP 200만으로 PASS하지 않는다. `SUCCEEDED`, 실패 단계 없음,
예상 승인 Chunk, 공식 HTTPS URL과 페이지 식별자, 고정 입력에서 Prompt v2가
추출해야 하는 승인 Evidence 원문까지 모두 확인하므로 `FALLBACK` 200이나
결정적 Fallback 문구는 Local Runtime Gate PASS가 아니다. 실제 모델명·Token은
Backend AIRun과 AI 구조화 LLM 사용 로그를 같은 Correlation ID로 별도 대조한다.

`build_vector_index`는 아래 Disposable 검증 DB에서만 AI가 직접 적재하는 경로로
유지한다. 팀 DB에서 View 조회 권한과 적재 권한을 혼합하지 않는다.

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

### 3모델 `rag-expansion` Candidate

3모델 확장 데이터는 공식 Runtime 입력이 아니라 `INGEST_CANDIDATE`다. 먼저 DB와
Embedding을 사용하지 않는 Preflight로 Child 53건, Evidence Group 43건, 평가 Case
50건과 `exact_sales_code` 선필터 계약을 확인한다.

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.evaluate_rag_expansion_pgvector --preflight-only
```

실제 Candidate 적재·평가는 운영 `ai_rag_chunks`와 분리된
`ai_rag_chunks_expansion_candidate` Table 및 식별 가능한 Disposable DB에서만
허용한다. Manifest와 Vector 비포함 평가 보고서는 Git 제외 경로인
`.runtime/rag-expansion/`에 생성된다.

```powershell
$env:AI_VECTOR_TABLE_NAME='ai_rag_chunks_expansion_candidate'
$env:AI_VECTOR_DISPOSABLE_CONFIRM='DISPOSABLE_ONLY'

.\ai\.venv\Scripts\python.exe -m ai.scripts.initialize_disposable_vector_schema
.\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index --profile rag-expansion
.\ai\.venv\Scripts\python.exe -m ai.scripts.evaluate_rag_expansion_pgvector
```

검색 전 모델 Capability Gate는 `ai/configs/model_capabilities.yaml`을 사용한다.
등록되지 않은 정확 판매코드와 IAC425·IAC606의 명시적 조작부 불일치를 임베딩·
pgvector 전에 차단한다. 일반적인 `물`, `출수`, `버튼` 단어만으로는 차단하지
않으며 적용 Rule ID와 차단 사유, 검색 실행 여부를 평가 보고서에 남긴다.

2026-08-19 Disposable Candidate 실행에서는 53행·1024차원·3개 판매코드·43개
Evidence Group 적재를 확인했다. 정상 43건은 판매코드가 일치하는 검증 Evidence
Group을 Top-5에서 찾았고 부정 7건은 모두 검색 전 No Evidence로 처리됐다. 총
`50/50`, 교차 모델 Hit 0건, Parent 직접 Hit 0건, 미검증 Evidence Hit 0건이다.
이 결과는 `rag-expansion` Candidate 검색 성능 PASS이며 Backend·Public API 계약
확장이 끝나지 않았으므로 IAC425·IAC606 Runtime 활성 상태는 `NOT_APPROVED`다.

### Backend Context MCP Transport

`AI_RETRIEVAL_TRANSPORT=mcp`에서는 Pipeline이 검색 전에 Backend의 읽기 전용
Inquiry Context API를 MCP Tool로 조회한다. Secret은 Tool 인자가 아니라 현재 AI
Process 환경에서 MCP subprocess로만 전달한다.

- `lookup_product_context`: 구독의 `ProductModel.model_code`, 제품 유형과 지원 기능 조회
- `get_inquiry_context`: 문의 상태·버전, 고객 증상과 이전 문진 답변 조회
- `search_official_evidence`: 조회된 정확 판매코드를 변경하지 않고 공식 근거 검색
- `health_check`: MCP Server 기동 상태 확인

필수 환경변수 이름은 `AI_BACKEND_BASE_URL`, `AI_HANDOFF_INTERNAL_TOKEN`,
`AI_RETRIEVAL_TRANSPORT`다. Timeout은 `AI_BACKEND_CONTEXT_TIMEOUT_SECONDS`와
`AI_MCP_CONTEXT_TIMEOUT_SECONDS`로 제한한다. Context의 Inquiry·Correlation·상태
버전 또는 제품코드가 호출 요청과 다르면 검색과 Provider 호출 전에 중단한다.
근거가 없거나 MCP가 실제 다른 모델의 근거를 반환해도 Guidance에 전달하지 않고
Harness 상담 경로로 fail-closed한다.

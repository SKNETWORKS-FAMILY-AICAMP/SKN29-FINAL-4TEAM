# 이동윤 → 최지용: Backend↔AI 선행 제공물 및 Metadata 결정 요청 v0.1

> 작성일: 2026-08-10 KST  
> 작성자: 이동윤 — AI·RAG  
> 수신자: 최지용 — Backend·Database  
> 범위: Backend↔AI 최소 수직 연동 P0·P1 선행 제공물

## 0. 최지용에게 보낼 회신

아래 블록은 요청 문서의 `2.1 AI 실행 환경`, `2.2 AI 계약 정합성`,
`2.4 결정적 fixture` 순서에 맞춘 전송용 회신이다.

```text
sender=이동윤
receiver=최지용
reply_scope=BACKEND_AI_VERTICAL_INTEGRATION_AI_PREREQUISITES

python_version=3.13.13
dependency_manifest=ai/requirements.lock
install_command=.\ai\.venv\Scripts\python.exe -m pip install -r ai\requirements.lock
ai_mode=mock | local
config_paths=ai/configs/retry_policy.yaml, ai/configs/retrieval_policy.yaml, ai/configs/safety_rules.yaml, ai/configs/index_manifest.json
required_environment_variable_names=mock:NONE | local_general_or_caution:AI_VECTOR_DSN,AI_EMBEDDING_REVISION | local_danger_rule_only:NONE
optional_environment_variable_names=AI_MAX_IN_FLIGHT_WORKERS,AI_LOG_LEVEL
start_command=.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
health_url=http://127.0.0.1:8001/health
analysis_endpoint=POST /api/v1/ai/analyze?mode=mock|local
db_seed_or_reset_command=mock:NOT_REQUIRED | local_disposable:.\ai\.venv\Scripts\python.exe -m ai.scripts.initialize_disposable_vector_schema THEN .\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index

contract_version=2.0.0
correlation_id=UUID
header_body_rule=X-Correlation-ID Header와 Body correlation_id 일치
header_body_mismatch=HTTP 400, AI-VALIDATION-01, retryable=false
non_uuid_direct_request=HTTP 422, AI-VALIDATION-01, correlation_id=null, retryable=false
ai_request_id=Backend 발급, 동일 논리 요청 재전송 시 재사용
state_version=호출 시작 시점 값을 성공·Fallback·오류에 Echo
previous_answers=question_id와 answer_text 전달, 답변·명시적 거절 질문 반복 차단
no_evidence=HTTP 200, status=FALLBACK, failure_stage=RETRIEVING, evidence_references=[]
ai_internal_retry=최대 1회
backend_retry=0회

environment_manifest=ai/configs/backend_integration_environment.json
fixture_manifest=ai/evaluation/datasets/backend_integration/fixture_manifest.json
fixture_command=.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\test_backend_integration_fixtures.py -q
fixture_result=12 passed: Manifest 1개 + F01~F10·F12 AI 구간 11개
unit_test_command=.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
unit_test_result=115 passed, 3 warnings
mock_smoke=PASS: health, analyze HTTP 200, UUID Header·Body Echo

f11_owner=Backend: 최신 state_version 재검증과 stale 결과 미적용
f12_joint_boundary=AI: previous_answers 반영·질문 비반복 | Backend: 답변·거절 저장·버전 증가
metadata_contract=CHANGE_REQUEST_PENDING: execution_metadata 필드·필수 여부 Backend 검토 필요
team_db=NOT_STARTED: Local·격리 DB 공동 E2E 뒤 Backend Migration 기준 진행

overall_status=AI_PREREQUISITES_READY_FOR_BACKEND_REVIEW
next_step=Backend 계약 2.0.0 소비 확인 후 동일 환경 Mock 공동 E2E
```

## 1. 현재 결과

- `correlation_id`를 모든 AI 요청·응답·오류 계약에서 UUID로 제한했다.
- 입력 범위를 좁히는 변경이므로 AI 계약 버전을 `2.0.0`으로 갱신했다.
- Header와 Body에 서로 다른 유효 UUID가 오면 HTTP 400
  `AI-VALIDATION-01`을 반환한다.
- Body의 `correlation_id`가 비UUID이면 HTTP 422를 반환하며, 유효하지 않은
  값을 오류 Body나 Header에 Echo하지 않고 `correlation_id=null`로 반환한다.
- Python `3.13.13` AI 가상환경에서 단위 테스트 `103 passed`를 확인했다.
- Uvicorn을 실제 실행한 Mock smoke에서 health·analyze·Header/Body 추적을
  확인했다.
- F01~F10과 F12 AI 구간의 결정적 in-process HTTP Fixture를 검증했다.

## 2. 동일 실행환경 Manifest

기계 판독 가능한 기준 파일:

```text
ai/configs/backend_integration_environment.json
```

핵심 실행값:

```text
python_version=3.13.13
dependency_manifest=ai/requirements.lock
install_command=.\ai\.venv\Scripts\python.exe -m pip install -r ai\requirements.lock
ai_mode=mock | local
start_command=.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
health_url=http://127.0.0.1:8001/health
analysis_endpoint=POST http://127.0.0.1:8001/api/v1/ai/analyze?mode={mock|local}
db_seed_or_reset_command(mock)=NOT_REQUIRED
```

Mock 필수 환경변수는 없다. Local의 일반·주의 입력이 실제 RAG 검색을
수행하려면 다음 이름이 모두 필요하다.

```text
AI_VECTOR_DSN
AI_EMBEDDING_REVISION
```

선택 환경변수:

```text
AI_MAX_IN_FLIGHT_WORKERS
AI_LOG_LEVEL
```

실제 Secret과 DSN 값은 이 문서와 실행 로그에 기록하지 않는다. `/health`는
Liveness이며 Local RAG Readiness 성공 증거로 확대하지 않는다.

Mock smoke 명령:

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test `
  --base-url http://127.0.0.1:8001 `
  --mode mock
```

## 3. 현재 응답에서 바로 저장 가능한 필드

| Backend 저장 요구 | 현재 AI 필드 | 상태 |
|---|---|---|
| 계약 성공·Fallback | `status` | 제공 중 |
| 실패 단계 | `failure_stage` | 제공 중 |
| AI 내부 재시도 횟수 | `retry_count` | 제공 중 |
| 오류 코드·재시도 가능 여부 | `error.code`, `error.retryable` | 제공 중 |
| canonical evidence chunk | `evidence_references[].chunk_id` | 제공 중 |
| 문서·페이지 | `document_title`, `document_version`, `page`, `page_refs` | 제공 중 |
| 검증 상태 | `verification_status` | 제공 중 |
| 유사도 | `similarity_score` | 제공 중 |

`EvidenceReference`는 Backend의 최종 `EvidenceCardDTO`가 아니라 검색 후보
identity다.

## 4. 추가 계약 결정 요청

다음 값은 내부 `PipelineContext` 또는 설정에는 있으나 현재 공개 analyze
응답 계약에는 없다.

추가 계약 결정이 필요한 핵심 이유는 Backend가 저장하겠다고 한 실행 Metadata가 현재 HTTP 응답에 없기 때문입니다. 임의로 필드를 추가하면 Backend가 요구한 “UUID 외 계약 변경 사전 확인” 조건을 위반합니다.

| 요청 Metadata | 현재 상태 | 결정 필요 사항 |
|---|---|---|
| model provider/name/revision | 공개 응답 미제공 | 외부 LLM 미사용 기준 표현과 필수 여부 |
| pipeline/prompt version | 내부 기본값만 존재 | 실제 Runtime Registry 연결 방식 |
| contract version | Schema에만 존재 | 응답 Body 저장 필요 여부 |
| retrieval top-k·threshold | 설정 파일에 존재 | 실행 Snapshot 반환 여부 |
| embedding model/revision | 환경·Manifest에 존재 | 응답 Body 반환 여부 |
| index version·chunk set hash | Index Manifest에 존재 | AIRun 저장 범위 |
| 제품·세대 scope | 검색 Metadata에 부분 존재 | Evidence별 필수 필드 여부 |

AI 제안은 analyze 응답에 `execution_metadata`를 추가하여 실제 실행 Snapshot만
반환하는 것이다. 단, 이는 `correlation_id` UUID 변경과 별도인 추가 계약
변경이므로 Backend의 필드 목록·예시 검토 전에는 구현하지 않는다.

회신 요청:

```text
reviewer=최지용
review_scope=AI_EXECUTION_METADATA_CONTRACT

execution_metadata_container=ACCEPT | CHANGE_REQUEST
model_identity_fields=<필드 목록 | NOT_REQUIRED>
pipeline_contract_fields=<필드 목록 | NOT_REQUIRED>
retrieval_snapshot_fields=<필드 목록 | NOT_REQUIRED>
evidence_scope_fields=<필드 목록 | NOT_REQUIRED>
required_optional_rule=<필드별 규칙>
decision=<ACCEPT | CHANGE_REQUEST | DEFER>
```

## 5. 다음 공동 작업

1. Backend가 계약 `2.0.0`의 UUID Mapper 소비 가능 여부를 확인한다.
2. 양측이 동일 Manifest로 Mock HTTP를 재현한다.
3. Backend는 다음 Fixture Manifest로 AI 소유 구간을 재현한다.

   ```text
   ai/evaluation/datasets/backend_integration/fixture_manifest.json
   ```

4. 실제 pgvector 환경에서 F01·F02 Local HTTP를 재검증한다.
5. Backend는 F11 stale 차단과 F12 저장·버전 증가 구간을 구현한다.
6. 추가 Metadata는 위 회신 뒤 별도 계약 변경으로 반영한다.

Fixture 단위 Gate 명령과 현재 결과:

```text
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\test_backend_integration_fixtures.py -q
12 passed
```

위 `12 passed`는 Manifest 검증 1개와 AI 소유 구간 11개다. F11 Backend stale
차단이나 실제 팀 DB·Backend 저장 E2E를 통과했다는 의미가 아니다.

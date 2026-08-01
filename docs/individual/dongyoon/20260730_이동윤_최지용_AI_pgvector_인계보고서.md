# 이동윤 → 최지용 AI 계약·Runtime·pgvector 인계보고서

> **SUPERSEDED**: 이 문서의 AI `8000`, 개인 Conda 절대경로,
> `PENDING_COMMIT`은 작성 당시 이력이며 현재 실행 기준이 아니다. 최신 기준은
> [10.1-A 2차 보완 회신](20260730_이동윤_최지용_10_1_A_2차_보완_회신.md)과
> [AI README](../../../ai/README.md)를 따른다.

> 기준일: 2026-07-30
>
> 발신: 이동윤(AI·RAG)
>
> 수신: 최지용(Backend·DB·API 계약)
>
> 현재 판정: `AI_HANDOFF_READY_COMMIT_PENDING`
>
> 목적: AI 계약 1.1.0을 기준으로 Backend AI Adapter를 구현하고, 격리
> pgvector 실증 결과를 팀 PostgreSQL `5432`의 정식 Django Migration으로
> 편입하기 위한 입력과 완료 기준을 전달한다.

---

## 1. 한 줄 인계

AI 요청·응답 계약과 Runtime 정합화, 실제 PostgreSQL/pgvector 적재·검색
검증은 완료했다. 최지용에게는 팀 DB의 정식 Extension·Model·Migration과
Backend AI Client·Mapper·오류·Fallback·추적 구현을 요청한다.

현재 변경은 아직 Commit 전이므로 최종 40자리 AI Commit SHA는 후속
회신해야 한다. 이 문서의 검증 기준 Base Commit은
`e5cc511189b54060dfafde9215b2cb0799b1bf7a`이고 Branch는 `dongyoon`이다.

---

## 2. 역할 경계

| 구분 | 이동윤 | 최지용 |
| --- | --- | --- |
| `ai/**` Runtime·RAG·검증 | 주관 | 소비·교차검토 |
| `contracts/ai/**` | 주관 | Backend 소비 관점 검토 |
| `backend/integrations/ai/**` | 계약 검토 | 주관 |
| 팀 DB `5432` Django Model·Migration | Vector 요구사항 제공 | 주관 |
| pgvector 적재·검색 재검증 | 주관 | DB 연결·Migration 지원 |
| 업무 상태·권한·EvidenceCard 저장 | 변경하지 않음 | 주관 |

AI는 증상 구조화·안전 평가·사용 안내 제안·EvidenceReference를 반환한다.
업무 상태 전환, 권한 판단, 최종 EvidenceCard 조립 및 DB 저장은 Backend가
담당한다.

---

## 3. AI 계약 1.1.0 인계

계약 원본:

- [`contracts/ai/README.md`](../../../contracts/ai/README.md)
- [`contracts/ai/CHANGELOG.md`](../../../contracts/ai/CHANGELOG.md)
- [`SymptomAnalysisRequest.schema.json`](../../../contracts/ai/requests/SymptomAnalysisRequest.schema.json)
- [`SymptomAnalysisResponse.schema.json`](../../../contracts/ai/responses/SymptomAnalysisResponse.schema.json)
- [`AIErrorResponse.schema.json`](../../../contracts/ai/common/AIErrorResponse.schema.json)

### 3.1 공통 추적·멱등·상태 버전

요청과 응답의 최상위에서 다음 값을 보존한다.

| 필드 | 규칙 |
| --- | --- |
| `inquiry_id` | 내부 정수 PK가 아닌 공개 업무 식별자 |
| `correlation_id` | Backend → AI → 응답·오류·Header·Log에서 동일 값 사용 |
| `ai_request_id` | Backend가 발급하는 AI 호출 멱등 식별자 |
| `state_version` | AI 호출 시작 시점 버전을 전달하고 AI가 변경 없이 Echo |
| `status` | `SUCCEEDED` 또는 `FALLBACK` |
| `failure_stage` | 공통 AI Stage 코드 또는 `null` |
| `retry_count` | 실제 AI 내부 재시도 횟수, `0..1` |

공개 응답에 별도 `trace_context`, `model_metadata`, `processing_traces`를
중복 노출하지 않는다. Backend는 늦게 도착한 결과의 `state_version`을
현재 문의 버전과 비교한 뒤 적용 여부를 결정한다.

### 3.2 오류 계약

| 오류 코드 | HTTP | retryable | 대표 Stage |
| --- | ---: | --- | --- |
| `AI-VALIDATION-01` | 400 또는 422 | false | `STRUCTURING` |
| `AI-FAILED-01` | 503 | true | `FAILED` |
| `AI-TIMEOUT-01` | 504 | true | `CANCELLED` |

오류 응답에도 확인 가능한 식별자를 보존하며 원문 입력, Prompt, Stack Trace,
Secret, 개인정보는 포함하지 않는다.

### 3.3 Backend Adapter에 요청하는 규칙

- Body `correlation_id`와 선택적 `X-Correlation-ID` Header를 동일하게 전달한다.
- 동일 논리 요청을 재전송할 때 같은 `ai_request_id`를 재사용한다.
- Backend 자동 재시도는 0회로 유지한다.
- AI의 504 또는 호출 실패를 임의 정상 응답으로 변환하지 않는다.
- 근거 없음 `FALLBACK`은 `PENDING_CONSULTATION` 제안으로 소비하되 Backend
  상태 전환 Guard를 우회하지 않는다.
- AI 응답으로 문의 상태·권한·최종 EvidenceCard를 직접 확정하지 않는다.

---

## 4. 재현 가능한 AI Runtime

```text
ai_branch=dongyoon
ai_commit_sha=PENDING_COMMIT
base_commit=e5cc511189b54060dfafde9215b2cb0799b1bf7a
python_version=3.10.20
dependency_manifest=ai/pyproject.toml
service_base_url=http://127.0.0.1:8000
health_url=http://127.0.0.1:8000/health
analysis_endpoint=POST /api/v1/ai/analyze?mode=mock|local
request_schema_version=1.1.0
response_schema_version=1.1.0
overall_timeout_seconds=30
ai_internal_max_retry_count=1
backend_retry_count=0
```

실행 명령:

```powershell
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m uvicorn `
  ai.app.main:app --host 127.0.0.1 --port 8000
```

단위 테스트:

```powershell
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest ai/tests/unit/
```

최종 결과:

```text
41 passed, 3 warnings
```

실제 HTTP Smoke 결과:

```text
GET /health -> 200, status=ok
POST /api/v1/ai/analyze?mode=local -> 200
X-Correlation-ID=corr-smoke-001
risk_level=danger
usage_guidance_status=TOTAL_STOP
state_version=1
ai_request_id=ai-req-smoke-001
```

---

## 5. 실제 pgvector 검증 결과

증거 원본:

- [`index_manifest.json`](../../../ai/configs/index_manifest.json)
- [`pgvector_verification.json`](../../../ai/evaluation/reports/pgvector_verification.json)
- [`build_vector_index.py`](../../../ai/scripts/build_vector_index.py)
- [`verify_pgvector_runtime.py`](../../../ai/scripts/verify_pgvector_runtime.py)
- [`test_pgvector_runtime.py`](../../../ai/tests/integration/test_pgvector_runtime.py)

### 5.1 검증 환경

기존 팀 DB와 분리된 `pgvector/pgvector:pg16` 컨테이너에서 검증했다.

```text
container=watercare-pgvector-verify-20260730
host=127.0.0.1
host_port=55432
container_port=5432
database=watercare_ai_verify
postgresql=16.14
pgvector=0.8.6
embedding_model=BAAI/bge-m3
embedding_revision=5617a9f61b028005a4858fdac845db406aefb181
dimension=1024
search=cosine_exact_search
ann_used=false
top_k=5
score_threshold=0.4
```

검증 컨테이너는 삭제하지 않고 중지했으며 팀 DB·Volume과 공유하지 않는다.

### 5.2 데이터·Hash

```text
approved_chunk_count=7
stored_row_count=7
distinct_chunk_id_count=7
chunk_set_sha256=175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958
source_sha256=0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C
```

적재는 `chunk_id` 기준 `ON CONFLICT ... DO UPDATE`이며 동일 청크 집합을
두 번 실행한 뒤에도 총 7행을 유지했다.

### 5.3 검색·필터 검증

```text
evaluation_cases=12
passed=12
failed=0
mean_positive_recall_at_5=1.0
mean_positive_mrr=0.8857142857142858
forbidden_hit_count=0
sql_filter_fixture_count=4
sql_filter_leaked_fixture_count=0
invalid_dimension_rejected=true
actual_pgvector_integration_test=1 passed
```

실제 SQL은 다음 조건을 Vector 유사도 순위 계산 전에 강제한다.

```sql
WHERE model_code = %s
  AND product_generation = %s
  AND verification_status = 'official_verified'
  AND allowed_use = TRUE
```

그 뒤 `1 - (embedding <=> query_vector)` Cosine 유사도, Threshold `0.4`,
Top-5, `chunk_id` Tie-break를 적용한다. 미검증·사용 금지·잘못된 세대·
잘못된 모델 Fixture는 실제 DB에서 유사도 1.0으로 삽입해도 결과에 나오지
않았다. `vector(1024)` Column에 3차원 Vector를 삽입하는 시도도 DB에서
거부됐다.

### 5.4 검색 품질 해석

7개 양성 Case의 정답은 모두 Top-5에 포함됐다. 다만 누수 Case의 정답이
5위여서 평균 MRR은 약 `0.8857`이다. MVP Recall@5 Gate는 통과했지만,
향후 위험 질의의 Top-1 순위 개선은 별도 품질 개선 항목이다.

---

## 6. 최지용 요청 — 팀 DB `5432` 정식 Migration

격리 DDL을 팀 DB에 직접 복사 적용하지 말고 Backend Django Model과 정식
Migration으로 편입해 달라.

필수 요구사항:

1. PostgreSQL `vector` Extension을 Migration으로 활성화한다.
2. Vector Column은 `vector(1024)`로 고정한다.
3. `chunk_id`는 고유 키 또는 Primary Key로 보장한다.
4. 다음 검색 필터 Column을 물리 Column으로 유지한다.
   - `model_code`
   - `product_generation`
   - `verification_status`
   - `allowed_use`
5. `source_hash`는 64자리 SHA-256 형식을 검증한다.
6. 문서·페이지·버전·공식 URL·안전 행동 Metadata를 보존한다.
7. AI 적재 계정의 최소 INSERT·UPDATE·SELECT 권한과 Backend 조회 권한을
   확정한다.
8. Migration 전 Backup, 적용 후 Restore 가능성, Rollback 절차를 문서화한다.
9. T-005의 지식·RAG·AI 추적 Table 상태와 충돌 여부를 확인한다.
10. 기존 팀 DB 기본 데이터와 격리 검증 Import 경로를 혼용하지 않는다.

격리 실증 DDL과 UPSERT 구현은
[`vector_store.py`](../../../ai/app/integrations/vector_store/vector_store.py)의
`initialize_schema()`와 `upsert()`를 입력 자료로 사용한다.

---

## 7. 팀 DB Migration 이후 공동 재검증

최지용이 Migration을 병합한 뒤 이동윤과 함께 다음 순서로 검증한다.

```text
1. 팀 DB Backup·Migration 적용
2. vector Extension 및 vector(1024) Column 확인
3. AI_VECTOR_DSN을 팀 DB 연결로 설정
4. 승인 청크 7개 UPSERT
5. 동일 적재 재실행 후 7행 유지 확인
6. 실제 평가 12개 Top-5 실행
7. SQL 금지 Fixture 누출 0건 확인
8. Backend AI Adapter 호출·오류·Timeout·correlation_id E2E
9. state_version stale 결과 차단 확인
10. EvidenceReference 저장·조회 확인
```

AI 측 실행 명령:

```powershell
$env:AI_VECTOR_DSN='<팀 DB용 보안 DSN>'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'

C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m ai.scripts.build_vector_index
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m ai.scripts.verify_pgvector_runtime
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest `
  ai\tests\integration\test_pgvector_runtime.py -v
```

실제 DSN·Password는 Git, 보고서, 명령 이력에 기록하지 않는다.

---

## 8. 최지용 요청 — Backend AI Adapter

계약 1.1.0을 기준으로 다음 구현을 요청한다.

- AI HTTP Client와 30초 호출 한도
- Request Mapper와 Response Schema Validator
- `X-Correlation-ID`·Body `correlation_id` 일치 전파
- `ai_request_id` 멱등 처리
- `state_version` Echo 보존 및 stale 결과 차단
- `AI-VALIDATION-01`, `AI-FAILED-01`, `AI-TIMEOUT-01` 오류 Mapping
- `FALLBACK`·근거 없음의 상담 전환 제안 처리
- Backend 자동 재시도 0회
- AI 결과가 상태·권한·최종 EvidenceCard를 직접 변경하지 않도록 Guard

계약 병합 전 임의 필드명이나 별도 오류 코드를 생성하지 않는다.

---

## 9. 남은 공통 결정

| 항목 | 현재 상태 | 요청 대상 |
| --- | --- | --- |
| 최종 AI Commit SHA | `PENDING_COMMIT` | 이동윤 |
| 팀 DB pgvector Migration | 미반영 | 최지용 |
| Backend AI Client·Mapper | Placeholder | 최지용 |
| `AI-VALIDATION-01`, `AI-TIMEOUT-01` 공통 Registry 편입 | 검토 필요 | 최지용·PM |
| `official_verified`, `team_verified` 공통 코드 편입 | 검토 필요 | 계약 담당·PM |
| 팀 DB pgvector 재검증 | Migration 이후 | 이동윤·최지용 |
| Backend-AI 대표 E2E | 미수행 | 이동윤·최지용 |

공유 Conda 환경의 `pip check`는 프로젝트 외 Jupyter/PyMuPDF 누락과
설치된 `langchain 1.3.4` 대 `langgraph 1.2.2` 요구 버전 차이 때문에
실패한다. AI 단위·pgvector 통합 테스트는 통과했지만 독립 가상환경 또는
팀 의존성 버전 결정은 별도 재현성 Gate다.

---

## 10. 최지용 회신 요청 양식

```text
[최지용 회신]
base_ai_contract_version:
received_ai_commit_sha:
backend_branch / commit_sha:
pgvector_extension_migration:
rag_chunk_model_migration:
ai_client_mapper_status:
error_mapping_status:
state_version / ai_request_id guard:
team_db_reverification_schedule:
backend_ai_e2e_result:
remaining_blocker:
```

---

## 11. 완료 판정 기준

- [x] AI 계약 1.1.0과 Runtime 공개 모델 정합화
- [x] 정상·위험·근거 없음·Schema 오류·Timeout 예시 제공
- [x] AI Timeout·오류·추적·멱등 필드 Runtime 검증
- [x] 격리 PostgreSQL/pgvector 실제 7개 청크 적재
- [x] 실제 평가 12/12 및 금지 혼입 0건
- [x] AI 단위 41개와 실제 pgvector 통합 테스트 통과
- [ ] 이동윤 최종 Commit·Push·40자리 SHA 회신
- [ ] 최지용 팀 DB Extension·Model·Migration 구현
- [ ] 공통 오류·검증 상태 Registry 승인
- [ ] 팀 DB에서 동일 pgvector 검증 재실행
- [ ] Backend AI Adapter와 대표 E2E 통과

위 미완료 항목이 끝나기 전에는 전체 Backend-AI 통합을 완료로 판정하지
않는다.

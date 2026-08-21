# AI Context 신규 Fixture 로컬 검증 및 인계

> 작성일: 2026-08-21 KST
> 작성자: 최지용(Backend·Database)
> 기준 SHA: `9ba2b3f6aecf733ad9c601e9ca5d3c90e7d9153b`

## 1. 목적

고정 Inquiry를 되돌리지 않고, 고유 `run_id`마다 공식 JAC104 판매코드를
가진 새 Inquiry를 만들어 Backend Context API를 반복 검증한다.

이번 작업은 Backend·로컬 PostgreSQL에만 한정했다. AI Pipeline·MCP·Data
원본·Web·Mobile·RDS·F02 정책은 수정하지 않았다.

## 2. 격리 환경

```text
database=waterbridge_team_integration
postgresql=16.14
pgvector=0.8.6
local_port=55435
existing_local_port_55433=UNTOUCHED
rds=NOT_USED
visits.0005=NOT_APPLIED_P1_HOLD
```

- 새 표준 Volume과 PostgreSQL Container를 사용했다.
- 승인 Migration 90개를 적용하고 예상 밖 Migration 0개를 확인했다.
- `visits.0004`는 적용됐고 `visits.0005`는 적용하지 않았다.
- Migration 후 Provisioning을 다시 실행해 Role 권한을 정합화했다.

## 3. 공식 합성데이터 준비

`import_synthetic_handoff --profile db-smoke` 공식 Importer를 사용했다.

| 단계 | 결과 |
| --- | --- |
| Dry-run | 37 source, 31 created 후보, 6 projected, 충돌 0 |
| 최초 Apply | 31 created, 6 projected, updated 0 |
| Replay | 31 unchanged, 6 projected, created 0, updated 0 |

공식 JAC104 제품 `WPUJAC104DWH`와 활성 합성 구독 6건이 준비됐다. 고정
`DEMO-INQ-002`는 완료 상태 그대로 보존했으며 신규 실행 건으로 재사용하지 않았다.

## 4. 구현

추가 명령:

```text
backend/apps/inquiries/management/commands/
create_ai_context_e2e_fixture.py
```

명령의 경계는 다음과 같다.

- 1~64자 안전한 `run_id`만 허용한다.
- 공식 `db-smoke`의 `SUB-SYN-0001` 활성 합성 구독만 읽는다.
- 제품은 활성·MVP 지원 `WPUJAC104DWH`와 정확히 일치해야 한다.
- 실제 `InquiryService.create`를 통해 DRAFT 문의와 LOW_FLOW 증상을 만든다.
- PostgreSQL 쓰기에는 `--confirm-database`가 반드시 필요하다.
- 같은 `run_id`는 중복 생성 없이 Replay한다.
- 이미 소비된 실행 건은 되돌리지 않고 새 `run_id`를 요구한다.
- 공개 JSON에는 Secret·DSN·고객 개인정보를 포함하지 않는다.

실행 예시:

```powershell
python manage.py create_ai_context_e2e_fixture `
  --run-id <NEW_RUN_ID> `
  --apply `
  --confirm-database waterbridge_team_integration `
  --json
```

## 5. 자체 검증

표적 테스트:

```text
17 passed / 0 failed
```

포함 범위:

- 신규 생성·동일 run Replay·서로 다른 run 독립 생성
- 소비된 문의 재사용 차단
- 잘못된 run_id·누락/오류 JAC104 의존성 차단
- Context API 200·403·404·422 계약 회귀

실제 로컬 Context API 결과:

```text
backend_health=200
valid_context=200
missing_token=403
wrong_token=403
missing_inquiry=404
missing_correlation=422
unknown_query=422
correlation_match=true
database_write_count_zero=true
forbidden_field_exposure=false
```

조회 전후 DB 수치는 동일했다.

```text
inquiries=7
transitions=1
idempotency_records=1
ai_runs=0
```

## 6. 신규 로컬 Fixture

```text
run_id=ai-context-20260821-jiyong-r1
inquiry_id=c66a2ac4-9c13-4f97-88a6-c4b3edc63c72
model_code=WPUJAC104DWH
status=DRAFT
state_version=1
allowed_actions=SUBMIT_SYMPTOM,CANCEL_INQUIRY
fixture_readiness=READY_FOR_CONTEXT_E2E
```

동일 `run_id` 재실행은 `created=false`로 확인했다.

## 7. Readonly·Evidence 경계

AI Readonly Role은 다음 경계를 통과했다.

```text
connection=PASS
readonly_view_select=PASS
readonly_base_table_select=DENY_PASS
pgvector_version=0.8.6
```

다만 Evidence를 임의 적재하지 않았기 때문에 Readiness는 `BLOCKED`다.

```text
active_verified_crosswalk=0/7
baseline_embedding_identity=0/7
crosswalk_page_links=0/8
backend_ai_rag_view_rows=0/7
```

이는 Context API 또는 Fixture 실패가 아니라, AI/Data 담당자의 승인된 Evidence
적재와 실제 MCP·Provider 실행이 아직 남았다는 의미다.

## 8. 인계 기준

- `AI_BACKEND_BASE_URL`은 QA가 접근 가능한 실행환경 주소로 별도 확정한다.
- `AI_HANDOFF_INTERNAL_TOKEN`은 보호 환경에 주입하고 보안 채널로만 공유한다.
- 이번 로컬 토큰은 일회성 메모리 값이었으며 검증 후 폐기했다.
- `127.0.0.1:18000` Backend는 자체 검증 후 종료했으므로 외부 QA 주소가 아니다.
- AI 담당자는 본인이 관리하는 `AI_VECTOR_DSN`과 RETRIEVING 제한시간을 제공한다.
- 김은진(QA)은 같은 `inquiry_id`·`correlation_id`의 Context→MCP→Harness 증거를
  확인하고, Evidence 미적재 구간을 PASS로 확대하지 않는다.

## 9. 최종 판정

```text
backend_context_fixture=IMPLEMENTED_LOCAL
backend_context_contract=PASS
local_postgresql_fixture=READY
context_read_only_db_change=0
ai_readonly_policy=PASS
baseline_evidence_readiness=BLOCKED_NOT_IMPORTED
actual_context_mcp_provider_e2e=NOT_RUN
overall=BACKEND_DB_SCOPE_COMPLETE_OWNER_HANDOFF_REQUIRED
```

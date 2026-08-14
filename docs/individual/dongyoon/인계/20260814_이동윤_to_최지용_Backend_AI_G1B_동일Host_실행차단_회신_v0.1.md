# 이동윤 → 최지용: Backend↔AI G1-B 동일 Host 실행차단 회신 v0.1

> 작성일: 2026-08-14
>
> 요청서: `20260814_최지용_to_이동윤_Backend_AI_G1B_비동기연동_최우선_실행회신요청_v0.2 (1).md`
>
> 실행 Checkout: `dongyoon@237a9b525f64670e1afef4fbc9fa1db2545a3aa5`
>
> 판정: `BLOCKED_AT_BACKEND_PRESTART_MIGRATION_GATE`
>
> 유지 상태: AI Runtime `127.0.0.1:8001` 실행 유지

## 1. 결론

동일 Checkout의 별도 PowerShell에서 Runtime Role을 정상 주입했고 Django System Check와
요청서의 G1-B Readiness Audit은 통과했다. 그러나 Backend 기동 전 전체 Migration
Check에서 19개 미적용 Migration이 확인돼 Exit 1로 중단했다.

요청서가 Migration 미적용 시 임의 Migration·Import·SQL 없이 중단하도록 명시했으므로
Backend를 기동하지 않았고 새 Inquiry·Submit·Replay도 실행하지 않았다. AI Runtime은
종료하지 않고 Health HTTP 200 상태로 유지했다.

기존 동일 Host 1차 준비 ACK는 AI Endpoint 준비 상태에는 유효하지만, Backend 실행
가능 ACK로는 이번 Migration 결과에 의해 대체된다.

## 2. 5절 Backend 동일 Host 준비 ACK

```ini
executor=이동윤
execution_host=SAME_HOST_AI_BACKEND
backend_execution_commit=237a9b525f64670e1afef4fbc9fa1db2545a3aa5
backend_runtime_role=LOADED
backend_database=waterbridge_team_integration
evidence_0011=APPLIED
readiness_audit=READY
readiness_exit=0
django_system_check=PASS
django_system_check_exit=0
full_migration_check=BLOCKED
full_migration_check_exit=1
unapplied_migration_count=19
backend_health=FAIL_NOT_STARTED
ai_health=HTTP_200
blocker=FULL_DJANGO_SCHEMA_HAS_19_UNAPPLIED_MIGRATIONS;BACKEND_START_AND_G1B_NOT_ALLOWED_BY_REQUEST_STOP_CONDITION
```

## 3. Readiness `READY`와 실제 차단의 차이

G1-B Readiness Audit이 확인한 Evidence 필수 Migration은 모두 적용돼 있다.

```ini
evidence.0009_ai_chunk_crosswalk=APPLIED
evidence.0010_backend_ai_rag_chunks_view=APPLIED
evidence.0011_cast_chunk_embedding_vector_dimensions=APPLIED
crosswalk=7/7
page_links=8
readonly_view_rows=7
ai_readonly_policy_safe=PASS
readiness_blockers=0
```

그러나 이 Audit은 전체 Django 앱의 Migration 정합성을 검사하지 않는다. 별도
`manage.py migrate --check --plan`에서 다음 19개가 미적용으로 확인됐다.

```text
admin.0001_initial
admin.0002_logentry_remove_auto_add
admin.0003_logentry_add_action_flag_choices
audit.0005_airun_analyze_symptom_task
common_codes.0001_initial
common_codes.0002_common_code
consultations.0002_consultation_runtime_fields
inquiries.0009_guidanceitem
inquiries.0010_customeractionresult
inquiries.0011_split_followup_question_metadata_and_answers
inquiries.0012_alter_inquiry_options
inquiries.0013_inquiry_priority_code
questionnaires.0001_initial
questionnaires.0002_postgresql_inquiry_subscription_fk
sessions.0001_initial
visits.0005_replace_visit_result_assignment_fk
workflow.0003_backfill_legacy_changed_at
workflow.0004_align_contract_status_history
workflow.0005_status_history_contract_names_indexes
```

특히 현재 Backend Model이 사용하는 `support_inquiry.priority_code`는
`inquiries.0013`에 포함된다. 이전 합성 Seed에서도 이 Column 미존재가 실제
`ProgrammingError`로 재현됐으므로 Readiness `READY`만으로 Backend G1-B 실행 가능을
판정하면 안 된다.

## 4. 두 Health와 Process 상태

```ini
ai_listening=YES
ai_base_url=http://127.0.0.1:8001
ai_health=HTTP_200
ai_config_loaded=true
backend_listening=NO
backend_base_url=http://127.0.0.1:8000
backend_health=NOT_RUN_BACKEND_NOT_STARTED
```

AI Runtime은 요청대로 유지했다. Backend는 Migration 중단 조건 이후 실행하지 않았으므로
8000번 Port를 열지 않았다.

## 5. 7절 실제 실행 증거

```ini
backend_execution_commit=237a9b525f64670e1afef4fbc9fa1db2545a3aa5
ai_execution_commit=237a9b525f64670e1afef4fbc9fa1db2545a3aa5
inquiry_id=NOT_CREATED
correlation_id=NOT_CREATED
submitted_at=NOT_RUN
backend_http_status=NOT_RUN
backend_result_status=BLOCKED_PRESTART
analysis_started=NOT_RUN
llm_guidance_completed=NOT_RUN
analysis_completed=NOT_RUN
actual_provider=NOT_RUN
actual_model=NOT_RUN
actual_pgvector_query=NOT_RUN
retrieval_source=NOT_RUN
verified_evidence_count=NOT_RUN
expected_evidence_hit=NOT_RUN
schema_validation=NOT_RUN
guidance_only=NOT_RUN
token_usage_present=NOT_RUN
airun_count=NOT_RUN
assessment_count=NOT_RUN
guidance_count=NOT_RUN
evidence_link_count=NOT_RUN
state_version_consistent=NOT_RUN
replay_additional_ai_call_count=NOT_RUN
replay_additional_business_record_count=NOT_RUN
g1b_result=BLOCKED
failure_stage=BACKEND_PRESTART_MIGRATION_GATE
blocker=FULL_DJANGO_SCHEMA_HAS_19_UNAPPLIED_MIGRATIONS
evidence_path=docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_Backend_AI_G1B_동일Host_실행차단_회신_v0.1.md
```

실제 Backend Submit이 없으므로 이전 AI 단독 OpenAI·pgvector 결과를 이번 7절 실행 증거로
재사용하지 않았다.

## 6. 수행하지 않은 변경

```ini
new_database_created=NO
new_role_created=NO
migration_applied=NO
import_executed=NO
manual_sql_executed=NO
lan_or_public_exposure=NO
firewall_changed=NO
qa_live_participation=NO
ai_runtime_stopped=NO
```

Secret·DSN·Password·고객 원문·Vector는 출력하거나 문서에 기록하지 않았다.

## 7. 다음 조치 요청

전체 19개 Migration을 현재 `waterbridge_team_integration` DB에 적용할지, 모든 Migration이
적용된 기존 QA 통합 DB·Volume을 동일 Checkout Runtime에서 사용할지는 Backend·DB
담당자가 결정해야 한다. 이동윤은 임의 적용하지 않는다.

```ini
next_owner=최지용_Backend_DB
decision_needed=APPLY_19_MIGRATIONS_TO_CURRENT_DB_OR_SELECT_FULLY_MIGRATED_QA_DATABASE
resume_condition=FULL_MIGRATION_CHECK_EXIT_0;READINESS_READY;AI_HEALTH_200;BACKEND_HEALTH_200
```

재개 조건을 충족하면 새 합성 Inquiry → Submit → AIRun·Assessment·Guidance·EvidenceLink
저장 → 동일 요청 Replay 순서로 다시 시작한다.

# 이동윤 → 최지용: AI RAG Customer Guidance G1-A·G1-B 실연결 진행 회신 v0.1

> 작성일: 2026-08-14
>
> 요청서: `20260814_최지용_to_이동윤_AI_RAG_CustomerGuidance_G1A_G1B_실연결요청_v0.1.md`
>
> 현재 판정: `G1A_FINAL_BASELINE_PASS / G1B_JOINT_BLOCKED_PENDING_DB_MIGRATION_APPROVAL`
>
> 비공개 항목: Secret·DSN·Password·Raw 원문·Vector·Prompt 본문

## 1. 요청 회신 양식

```ini
reviewer=이동윤
phase_b_local_g1a=ACCEPTED
main_sha=a43fd2d6f27243935a5d92fed349cb3e19e8bd13
ai_commit_sha=2119a4bdbf1d7c56501b0c0db81f659cb3b641bb
main_sync=PASS
ai_health=PASS
runtime_mode=ACTUAL
backend_host_reachable=PASS
model_provider=OpenAI
model_name=gpt-4.1-mini-2025-04-14
prompt_version=customer_guidance/v2
pgvector_readonly=PASS
schema_validation=PASS
guidance_only=PASS
no_evidence=NOT_RUN
danger_total_stop=NOT_RUN
http_504_injected=PHASE_B_ACCEPTED
correlation_id=NOT_RUN_BACKEND_JOINT
backend_airun_saved=NOT_RUN
backend_guidance_saved=NOT_RUN
backend_evidence_saved=NOT_RUN
g1a_final_baseline=PASS
g1b_joint_result=BLOCKED
blocker=19_PENDING_MIGRATIONS_REQUIRE_EXPLICIT_APPROVAL;BACKEND_JOINT_SUBMIT_NOT_RUN;EXTERNAL_BACKEND_HOST_REACHABILITY_NOT_RUN
```

`backend_host_reachable=PASS`는 이동윤 Host 내부 `127.0.0.1` 기준이다. 최지용 PC 등
다른 Host에서의 접근은 방화벽·공동 실행시간·접속 주소 합의 전이므로 별도
`NOT_RUN`이다.

## 2. 최종 main 동기화 결과

- 이동윤 고유 회신 문서는 `dongyoon@b516c06`에 먼저 보존했다.
- 새 브랜치를 만들지 않고 `main@a43fd2d6f27243935a5d92fed349cb3e19e8bd13`을
  `dongyoon`에 병합했다.
- 현재 실행 Commit은 `2119a4bdbf1d7c56501b0c0db81f659cb3b641bb`이다.
- `a43fd2d...`는 현재 실행 Commit의 조상이다.
- 최종 main 대비 AI 구현, `contracts/ai/**`, Canonical Identity·Manifest·승인
  RAG 입력의 차이는 0건이다.
- 현재 별도 사용자 작업인 `.gitignore` 수정과 `artifacts/modeling-evaluation/`은
  이번 작업에서 변경·삭제·커밋하지 않았다.

```ini
main_sync=PASS
merge_conflict=NONE
ai_contract_canonical_conflict=NONE
new_branch_created=NO
```

## 3. 최종 코드 회귀·Runtime 결과

### 3.1 Backend·계약 표적 회귀

```ini
result=123 passed,3 skipped
exit_code=0
skipped_scope=POSTGRESQL_SPECIFIC_ASSERTIONS_NOT_ENABLED_IN_UNIT_PROCESS
actual_backend_joint_e2e=NOT_PROVEN_BY_THIS_TEST
```

검증 범위에는 Customer Guidance 공개 Projection, G1-B Readiness, Canonical Import,
`ChunkEmbedding` 모델, OpenAPI Inquiry 계약과 Contract Validator가 포함됐다.

### 3.2 AI 단위·Schema와 실제 pgvector

환경 주입 없는 첫 실행은 AI 단위·계약 `49 passed` 후 pgvector 1건이
`AI_VECTOR_DSN_MISSING`으로 fail-closed 했다. 보호 Loader를 같은 Process에 적용해
재실행한 실제 pgvector 결과는 다음과 같다.

```ini
ai_unit_and_contract=49 passed,2 warnings
actual_pgvector=1 passed in 10.61s
readiness_audit=READY
readiness_blockers=0
view_rows=7
view_distinct_chunk_ids=7
crosswalk=7/7
page_links=8
ai_role_policy_safe=PASS
```

### 3.3 실제 OpenAI

최종 main 동기화 후 보호 Loader로 실제 Runtime Verifier를 다시 실행했다.

```ini
result=PASS
analysis_status=SUCCEEDED
failure_stage=null
model_name=gpt-4.1-mini-2025-04-14
prompt_version=customer_guidance/v2
tokens_used=1180
expected_evidence_id=RAG-WPUJAC104DWH-LOW-FLOW-001
```

현재 실제 AI Runtime은 이동윤 Host의 `127.0.0.1:8001`에서 실행 중이며 `/health`는
HTTP 200이다. `0.0.0.0` 바인딩이나 Windows 방화벽 변경은 수행하지 않았다.

## 4. DB Migration 적용 결과와 G1-B 차단 근거

최종 main에서 추가된 Backend pgvector Constraint 수정 Migration
`evidence.0011_cast_chunk_embedding_vector_dimensions`는 적용했고, Role 권한도 현재
Schema 기준으로 재조정했다. 이후 Readiness Audit과 실제 AI pgvector를 다시
통과했다.

그러나 공식 합성 고객·구독 준비 중 다음 DB Schema drift가 실제로 발생했다.

```text
column support_inquiry.priority_code does not exist
```

전체 Migration Plan을 확인한 결과 Inquiry·Workflow·Consultation·Audit 등을 포함한
19개 Migration이 추가로 미적용 상태다. 전체 적용은 여러 앱의 Schema·기존 데이터를
변경하므로 사용자 명시 승인 없이 실행하지 않았다.

전체 Migration 적용 전 복구용 DB Backup은 다음 위치에 생성했다.

```ini
backup_path=.runtime/g1b/20260814-main-a43/waterbridge-pre-a43-migrations.dump
backup_format=PostgreSQL_CUSTOM
backup_bytes=388272
backup_sha256=596b4e3698b681543785a5ebc34e2801640391ed76ac259e46320e5d01ec8a75
backup_git_commit=NO
```

Backup은 DB 내용을 포함하므로 최지용에게 전달하거나 Git에 올리지 않는다. 복구용으로
이동윤 Host에만 보존한다.

## 5. 아직 실행하지 않은 G1-B 항목

Migration 적용 전에는 Backend Model과 DB가 불일치하므로 새 Inquiry를 강제로 만들거나
기존 Inquiry·실패한 Submit Key를 재사용하지 않는다.

```ini
new_inquiry=NOT_RUN_SCHEMA_DRIFT
new_idempotency_key=NOT_CREATED
backend_submit_to_actual_ai=NOT_RUN
request_response_log_correlation=NOT_RUN_BACKEND_JOINT
airun_persistence=NOT_RUN
assessment_persistence=NOT_RUN
guidance_persistence=NOT_RUN
evidence_persistence=NOT_RUN
idempotency_replay=NOT_RUN
customer_guidance_get_200=NOT_RUN
```

기존 Backend 실제 소켓 통합 테스트는 내부에서 `AI_SERVICE_MODE=mock`을 강제하므로
이번 실제 G1-B PASS 근거로 사용하지 않았다.

## 6. NO_EVIDENCE·DANGER와 정책 경계

- Happy Path 실제 G1-B가 아직 실행되지 않았으므로 NO_EVIDENCE와 DANGER도 선행
  실행하지 않았다.
- 기존 주입형 Pipeline Stage Timeout HTTP 504는 요청서에서
  `PHASE_B_ACCEPTED`로 수용했으므로 반복하지 않았다.
- 실제 Provider 네트워크 Timeout은 요청서 기준 Happy Path 선행조건이 아니며
  `NOT_RUN`을 유지한다.
- 공식 원문 공개·재배포는 계속 `HOLD`다.

## 7. 재개 조건과 다음 순서

다음 승인 수신 후 중단 지점부터 계속한다.

```ini
required_approval=APPLY_ALL_19_PENDING_MIGRATIONS_TO_DONGYOON_HOST_DB
```

승인 후 실행 순서는 다음과 같다.

1. 이동윤 Host DB에 전체 미적용 Migration 적용
2. Provisioning 재실행과 Readiness·Role·pgvector 재검증
3. 공식 Seed로 새 Inquiry·새 Idempotency Key·Correlation ID 생성
4. Backend Submit → 실제 AI OpenAI·pgvector 호출
5. AIRun·Assessment·Guidance·Evidence 저장 확인
6. 동일 Submit Replay의 AI 추가 호출·중복 저장 차단 확인
7. 고객 Guidance GET 200과 비공개 필드 미노출 확인
8. 요청·응답·AI Log·Backend Log·DB Correlation 일치 확인
9. Happy Path 완료 후 NO_EVIDENCE·DANGER 실행 여부 판정

## 8. 참고 문서

기존 두 회신문서는 이번 진행 회신에 근거만 제공하며 다시 전달할 필수 첨부가 아니다.

- `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_AI_G1A_PhaseB_로컬기술재현_실행결과_회신_v0.1.md`
- `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_Backend_pgvector_vector_dims_unknown_Django사전검증경고_재현회신_v0.1.md`

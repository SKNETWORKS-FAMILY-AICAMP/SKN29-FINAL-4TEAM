# 이동윤 → 최지용: AI 3모델 Canonical Identity·Runtime 준비 회신 v0.1

## 1. 확인 기준

- 최신 `main` 및 작업 기준 SHA: `49ca9ba3641d97d1ec0f93f657cf4ec388dc9e25`
- Backend 3모델 계약·구독 Runtime 변경의 `main` 병합: 확인
- 대상 판매코드: `WPUJAC104DWH`, `WPUIAC425SNW`, `WPUIAC606SNW`
- 이 회신은 AI 준비 결과이며, 공식 3모델 pgvector 적재 완료나 공동 E2E PASS를 의미하지 않는다.

## 2. AI 준비 결과

3모델 검색 Child 53건의 Canonical Identity를 고정했다. 모델별 구성은
`WPUJAC104DWH` 15건, `WPUIAC425SNW` 19건, `WPUIAC606SNW` 19건이며,
`chunk_id` 오름차순·NFC Validate-only·Source 및 Chunk SHA-256·페이지·문서·판매코드·
세대를 함께 검증한다. 전체 Chunk Set SHA-256은
`5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304`다.
Vector와 원문 본문은 Identity 자료에 포함하지 않았다.

신규 두 모델의 검색 정책은 준비했지만 활성 Runtime 정책과 분리했다. 준비 정책은
정확 판매코드 선필터, 모델별 세대 제한, 미지원 모델 배제와 교차 모델 Fallback 금지를
포함한다. 공식 적재·Crosswalk·Backend QA가 끝나기 전까지 현재 활성 Runtime은
`WPUJAC104DWH`만 허용한다.

Backend가 전달한 `model_code`는 AI Retrieval Query의 `model_code`로 변경 없이
전달하며, 세대만 별도 Registry에서 조회하도록 수정했다. `WPUIAC425SNW`는
`IAC425`, `WPUIAC606SNW`는 `IAC606` 세대로 해석하지만 판매코드 자체를 Alias나
다른 값으로 바꾸지 않는다.

## 3. 공식 pgvector 적재 경계와 실행 순서

공식 적재 대상은 Canonical Identity에 포함된 Child 53건이며 Parent는 직접 검색
대상이 아니다. Embedding 기준은 `BAAI/bge-m3`, 고정 Revision, 1024차원,
FLOAT32, Exact Search이고 Backend가 제공하는 읽기 전용 View
`backend_ai_rag_chunks_v1`를 AI가 `SELECT_ONLY`로 사용한다.

실행 순서는 다음과 같다.

1. AI Canonical Identity와 적재 기대값의 stale 여부를 검사한다.
2. Backend·Database 담당자가 공식 SourceDocument·Page·Child·Embedding을 원자적으로
   적재한다.
3. Backend가 53건 Identity와 실제 Index Manifest를 대상으로 Evidence Crosswalk를
   Dry-run한 뒤 적용한다.
4. 읽기 전용 View에서 모델별 `15/19/19`, 전체 53건을 확인한다.
5. AI Readonly Role을 보호 Loader로 Process에 주입한 뒤 50개 평가 Case를 실행한다.
6. 정상 43/43, 부정 No Evidence 7/7, 교차 모델·Parent 직접 반환·미검증 근거 각
   0건일 때만 공동 E2E 준비 상태로 전환한다.

현재 Backend 공식 Evidence Importer와 Crosswalk 명령은 7건에 고정되어 있어 53건을
적용할 수 없다. 또한 실제 3모델 Index Manifest도 아직 생성되지 않았다. 이 두 항목은
Backend·Database 담당 변경과 공식 적재 결과가 필요한 Blocker다. AI는 팀 DB에 직접
쓰기나 수동 SQL을 실행하지 않는다.

AI 담당 실행 명령은 다음과 같다. 보호 Loader와 검증기는 반드시 같은 PowerShell
Process에서 실행한다.

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.export_three_model_canonical_identity --check

$loaded = . .\scripts\deployment\import_team_integration_env.ps1 -Role AI
$loaded | Select-Object status, role, ai_readonly_dsn, secret_values_printed

.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_three_model_readonly_runtime
```

두 번째 검증 명령은 공식 53건 Index Manifest와 Readonly View가 준비되지 않으면
고정 Reason Code와 `HOLD`만 반환하며 DSN·접속 세부정보를 출력하지 않는다. 현재는
Backend 53건 Importer·Crosswalk 실행 명령이 존재하지 않으므로 임의의 수동 SQL이나
기존 7건 명령으로 우회하지 않는다.

## 4. 현재 검증 증거

- Canonical Identity 생성물 stale 검사: PASS, 53건
- 3모델 Handoff Preflight: READY, Child 53·Evidence Group 43·Case 50
- AI 표적 테스트: `59 passed`
- Backend 판매코드 매핑 표적 테스트: `3 passed`
- AI 전체 회귀: `332 passed`, `2 failed`, `5 warnings`, `7 subtests passed`
  - `F02` No Evidence Fixture는 최신 Harness가 검색을 1회 재시도한 실제 결과와
    기존 기대값 0회가 불일치한다.
  - 기존 개인정보 마스킹 테스트는 미등록 판매코드를 넣고 Provider 호출을
    기대하지만, 최신 제품 Runtime Guard가 Provider 전에 Fail-closed한다.
  - 두 항목은 이번 3모델 Identity·검색 필터 변경의 표적 테스트에는 영향이 없지만,
    Retry 정책과 테스트 기대값을 담당자와 합의하기 전 전체 회귀 PASS로 표시하지 않는다.
- AI Readonly Role 주입: PASS, Secret 출력 없음
- 공식 View 실측: `WPUJAC104DWH=7`, 신규 두 모델 0건
- 공식 View 기반 3모델 50 Case: NOT_RUN
- Readonly 검증 실패 출력의 Secret·DSN 세부정보 차단: PASS
- Disposable Candidate 이력: 50/50, 교차 모델 0건. 공식 팀 DB 결과로 사용하지 않음

## 5. 회신 상태

```ini
canonical_identity=FIXED_FOR_BACKEND_MAPPING
canonical_chunk_count=53
canonical_model_counts=WPUJAC104DWH:15,WPUIAC425SNW:19,WPUIAC606SNW:19
search_policy=PREPARED_NOT_ACTIVE
backend_model_code_passthrough=PASS
pgvector_ingest_target=READY
pgvector_official_ingest=BLOCKED
crosswalk_material=AVAILABLE
crosswalk_apply=BLOCKED_BACKEND_COMMAND_FIXED_AT_7
readonly_view_current=WPUJAC104DWH:7,WPUIAC425SNW:0,WPUIAC606SNW:0
cross_model_candidate_evaluation=PASS_0_HITS
cross_model_official_readonly_evaluation=NOT_RUN
backend_qa_pass=PENDING_CONFIRMATION
ai_targeted_regression=PASS
ai_full_regression=HOLD_2_PREEXISTING_CONTRACT_EXPECTATION_FAILURES
joint_e2e=HOLD
joint_e2e_blocker=OFFICIAL_53_IMPORT_AND_CROSSWALK_AND_READONLY_50_CASE_PASS_AND_FULL_REGRESSION_RECONCILIATION
```

Backend Evidence Importer·Crosswalk의 53건 확장과 김은진 Backend QA PASS가 확인되면,
최신 `main`에서 AI Readonly 50 Case를 다시 실행한 뒤 최지용 담당자와
`구독 → 문의 → AI → 해당 모델 Evidence` 공동 E2E를 진행할 수 있다.

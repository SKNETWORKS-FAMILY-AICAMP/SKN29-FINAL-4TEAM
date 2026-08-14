# 2026-08-14 Mobile 전체 요청 실행 결과

- 담당자: 양정현
- 실행 범위: 작업요청서 4~7
- Backend·Web·AI 코드 대리 수정: 없음
- Guidance·Evidence Fake 성공 생성: 없음

## 기준선 / Mobile Gate

- main_sha: `61720b379803cb39655cdb99049e6d006e1c359d`
- tested_mobile_base_sha: `61720b379803cb39655cdb99049e6d006e1c359d`
- sync_result: `PASS`
- repositories_compile_fix: `PASS`
- e2e_customer_code: `DEMO-CUSTOMER-001`
- launcher_jvm_17: `PASS`
- unit_test: `PASS`
- customer_build: `PASS`
- technician_build: `PASS`

## Section 5 - 고객 Mobile → Backend → PostgreSQL Smoke

- environment_id: `LOCAL_SAME_PC_POSTGRESQL_8011`
- backend_runtime_sha: `61720b379803cb39655cdb99049e6d006e1c359d`
- backend_base_url: `http://127.0.0.1:8011/`
- db_backend: `POSTGRESQL`
- migration_status: `UP_TO_DATE`
- customer_code: `DEMO-CUSTOMER-001`
- product_model: `WPUJAC104DWH`
- active_subscription_id: `d0a62011-3b89-5d39-8cd4-4c1d8c365101`
- inquiry_id: `7490c636-9d7b-427a-be8c-ed0dbc30a2b3`
- status: `QUESTIONNAIRE_IN_PROGRESS`
- state_version: `2`
- allowed_actions: `CANCEL_INQUIRY`
- create_correlation_id: `f268e464-ea7a-4006-b3cc-5aa2257388cd`
- submit_correlation_id: `9b66d840-0853-4b66-b9e2-c850c3992cbf`
- snapshot_correlation_id: `cf749a23-622d-45de-81b6-4fe402bd8303`
- PostgreSQL persistence: `PASS`
- customer_shared_smoke: `PASS`
- handoff_source: `LOCAL_VERIFIED_SAME_PC`

이 결과는 같은 PC에서 현재 Git 기준 Django Runtime과 실제 PostgreSQL을 연결해 검증한 결과입니다.
Backend Owner가 별도 TEAM_INTEGRATION 환경을 인계하면 같은 시나리오를 해당 환경에서 다시 실행합니다.

## Section 6 - 실제 AI

- guidance_runtime: `GUIDANCE_ROUTE_UNAVAILABLE`
- result: `BLOCKED_EXPECTED_NO_FAKE`
- Fake Guidance/Evidence: `DISABLED`

## Section 7 - 방문기사 경계

- actual_device_model: `SM-F721N`
- actual_device_market_name: ``
- android_api: `36`
- customer_install: `PASS`
- customer_basic_launch: `PASS`
- technician_install: `PASS`
- technician_login: `PASS`
- technician_remote: `BLOCKED_AS_EXPECTED`
- requested_customer_device: `NOT_RUN_REQUIRED_GALAXY_S26_ULTRA_ACTUAL_DEVICE_SM-F721N`
- requested_tablet_device: `NOT_RUN_REQUIRED_GALAXY_TAB_S9_FE_PLUS_ACTUAL_DEVICE_SM-F721N`

## 판정

- MOBILE_LATEST_MAIN_READY: `PASS`
- MOBILE_BACKEND_POSTGRESQL_SMOKE_PASS: `PASS_LOCAL_SAME_PC`
- TECHNICIAN_VISIT_REMOTE_BLOCKED: `PASS`
- FULL_E2E_NOT_CLAIMED: `TRUE`

## 외부 의존성

- 실제 AI Guidance customer route 인계 전에는 Section 6 전체 PASS를 주장하지 않음
- Galaxy S26 Ultra / Galaxy Tab S9 FE+ 지정 실기기가 연결되지 않았다면 해당 하드웨어 검증은 별도 진행 필요
- 팀 공통 Backend environment_id를 별도로 인계받으면 동일 Smoke 재실행

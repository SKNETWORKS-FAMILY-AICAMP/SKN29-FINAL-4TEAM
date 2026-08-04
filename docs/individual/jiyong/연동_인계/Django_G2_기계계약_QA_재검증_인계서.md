# G2 기계 계약 수정 반영·QA 재검증 인계서

## 1. 인계 정보

| 항목 | 값 |
| --- | --- |
| 전달자 | 최지용 Backend·DB |
| 검증자 | 김은진 Data·QA |
| 최종 Gate 승인자 | 윤승혁 PM·State |
| 대상 Branch | `jiyong` |
| 정책 기준 | 윤승혁 PM 회신, 2026-08-04 14:43 KST |
| 승인 기준 Commit | `NOT_REQUIRED` — PM 회신 원문을 정책 기준으로 사용 |
| 검증 Commit | 이 파일이 포함된 원격 `jiyong` HEAD 전체 SHA; 전달 메시지에서 별도 제공 |
| Manifest | `docs/handoffs/g2_contract_manifest_20260804.json` |
| 문서 상태 | `QA_REVALIDATION_REQUEST` |

이번 요청은 기존 DEC를 다시 논의하는 요청이 아니다. PM이 승인한 방향을 G2 OpenAPI·DTO·State·Guard·Projection으로 정확히 옮겼는지 동일 Commit에서 재검증하는 요청이다.

## 2. 현재 Gate

```text
machine_contract_start_allowed=true
contract_test_passed=false
runtime_implementation_start_allowed=false
consumer_integration_start_allowed=false
overall_gate=CONDITIONAL_OPEN
```

김은진의 독립 재검증이 끝나기 전에는 Backend Runtime·DB Migration·Web·Mobile 연결을 시작하지 않는다.

## 3. 범위

### 포함

- DEC-001: 목록 → 상세 → 상담 → 방문 순서와 독립 Gate
- DEC-002: 담당 상담사 문의 목록·상세
- DEC-003: 상담 시작·명시 저장·요약 확정·상담 완료
- DEC-004: 방문 검토·필요·불필요·date-only 일정·확정
- DEC-005: `allowed_actions`, `state_version`, 멱등, 409 Wire
- DEC-007: 역할·현재 배정 기반 최소 합성 Projection
- DEC-009: 같은 탭 15분 Draft 정책·이탈 경고·서버 자동저장 제외

### 제외

- DEC-006 운영 Dashboard: P1 유지
- DEC-008 Evidence: Web·AI 도메인 결정 전 HOLD
- 서버 Draft·주기적 자동저장: P1 또는 별도 DEC
- Runtime Route·View·Serializer·DB Model·Migration
- Web·Mobile 실제 소비자 연결

## 4. 이전 QA 실패에 대한 수정

| Case | 이전 판정 | 수정 내용 | 재검증 기대 |
| --- | --- | --- | --- |
| `G2-P01` | `permission_projection=FAIL` | 비담당 객체 404 은닉, 역할·현재 배정 조건, `is_synthetic=true`, PII·DEC-008 제외 | PASS |
| `G2-V02` | `date_only_dec009_scope=FAIL` 중 date-only | `preferred_date`·`confirmed_date`만 사용, 담당 상담사 Guard 추가, 합성 기사 ID 통일 | PASS |
| `G2-D01` | Web 구현 부재로 FAIL | 기계 정책은 G2에서 검증하고 실제 Web TTL·이탈 경고는 소비자 Gate 이후로 분리 | `DEFERRED_NOT_G2_FAILURE` |

`영구 검증 DB Migration 미적용`은 G2 계약 Blocker가 아니다. PM의 Runtime Gate가 열린 뒤 최지용 구현 범위로 이동한다.

## 5. B01~B08 처리

| ID | 처리 | 상태 |
| --- | --- | --- |
| B01 | 별도 팀 공통 SHA 대신 Push된 단일 G2 Commit을 검증 기준으로 사용 | 해소 |
| B02 | 상담 결과 4종과 완료 가능 Code를 Registry·DTO·Guard에 정렬 | PM Merge 승인 후보 |
| B03 | 방문 검토·불필요 사유 Code Set을 DTO·Guard와 정렬 | PM Merge 승인 후보 |
| B04 | 기사 인계 필드를 제품·증상·조치·위험·우선점검·상담사 결론으로 고정 | PM Merge 승인 후보 |
| B05 | 상담 문자열 최대 길이를 Schema에 명시 | 해소 |
| B06 | 방문 datetime Guard를 date-only Guard로 교체 | 해소 |
| B07 | 문의 상태 13개·Workflow Action 23개·우선순위 4개 Registry 작성 | 해소 |
| B08 | 방문 일정·확정에 담당 상담사 Guard 추가, Wire 기사 ID를 `synthetic_technician_id`로 통일 | 해소 |

B02~B04는 최지용의 단일 제안이다. 김은진은 구조·교차 일치 여부를 검증하고, 윤승혁은 QA 결과와 함께 업무 의미를 최종 확인한다.

## 6. 핵심 전달물

| 영역 | 기준 파일 | 검증 내용 |
| --- | --- | --- |
| Operation | `contracts/api/openapi.yaml` | 총 21개, G2 신규 11개, 신규 Runtime은 모두 `NOT_IMPLEMENTED` |
| Crosswalk | `contracts/api/g2-operation-crosswalk.yaml` | DEC·Method·Path·DTO·Event·Rule·권한 일치 |
| 오류 | `contracts/api/g2-error-matrix.yaml` | 역할 403, 미존재·비배정 404, 두 종류 409 분리 |
| 조회 DTO | `contracts/api/components/schemas/inquiry/` | 목록·상세 최소 합성 Projection, Evidence 제외 |
| 상담 DTO | `contracts/api/components/schemas/consultation/` | 명시 저장·AI 초안·수정본·확정본 분리 |
| 방문 DTO | `contracts/api/components/schemas/visit/` | date-only·합성 기사·구조화 Handoff |
| State | `contracts/state-machine/transition-rules.yaml` | G2 Action과 담당 상담사 Guard |
| Guard | `contracts/state-machine/transition-guards.yaml` | 404 은닉·date-only·합성 기사·Code 검증 |
| Projection | `contracts/state-machine/role-permissions.yaml` | 역할·배정·Allowlist·실제 PII 금지 |
| DEC-009 | `contracts/state-machine/consultation-draft-policy.yaml` | 같은 탭 15분·이탈 경고·서버 저장 제외·Web 후속 |
| Code | `contracts/codes/` | 상태·Action·우선순위·상담 결과·방문 사유 |
| Test | `backend/tests/api/test_g2_machine_contract.py` | G2-P01·V02·D01 및 Crosswalk 정적 검증 |

정확한 파일 목록과 SHA-256은 Manifest를 기준으로 한다.

## 7. 김은진 재검증 요청

1. 전달받은 전체 SHA와 원격 `jiyong` HEAD가 같은지 확인한다.
2. Manifest 파일 목록·SHA-256을 확인한다.
3. OpenAPI의 외부 `$ref`, `operationId` 중복, 신규 11개 Operation을 확인한다.
4. Crosswalk의 DTO·State Event·Rule·역할·배정 Guard를 확인한다.
5. 비담당 객체 404와 잘못된 역할 403이 섞이지 않았는지 확인한다.
6. 목록·상세·방문 예시에 실제 개인정보와 DEC-008 Evidence가 없는지 확인한다.
7. 방문 요청에 datetime·Client 입력 `schedule_status`·실제 기사 ID가 없는지 확인한다.
8. DEC-009 정책에 같은 탭 15분·`beforeunload`와 서버 Draft·자동저장 제외가 함께 고정됐는지 확인한다.
9. 신규 Runtime·DB·Migration·Web 파일이 수정되지 않았는지 확인한다.
10. 아래 명령을 동일 Commit에서 독립 재현한다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q tests/api/test_g2_machine_contract.py tests/api/test_openapi_inquiry_contract.py tests/api/test_openapi_runtime_coverage.py tests/unit/accounts/test_auth_contracts.py
```

## 8. 판정 기준

- `PASS`: 구조·참조·Crosswalk·Guard·Projection·제외 범위·Test가 모두 일치
- `FAIL`: 동일 Commit에서 재현 가능한 계약 오류가 존재
- `HOLD`: B02~B04 업무 의미처럼 PM 결정 없이는 판정할 수 없는 항목만 존재
- Web Runtime 미구현만으로 G2를 FAIL 처리하지 않는다.
- 과거 Test 수치를 재사용하지 않고 전달 Commit에서 직접 실행한 결과만 기록한다.

## 9. 회신 형식

```text
reviewer=김은진
reviewed_at=
policy_baseline=윤승혁 PM 2026-08-04 14:43 KST 회신
approved_baseline_commit=NOT_REQUIRED
reviewed_contract_commit=
review_environment=

openapi_dto_crosswalk=PASS|FAIL|HOLD
state_guard_error=PASS|FAIL|HOLD
permission_projection=PASS|FAIL|HOLD
date_only_contract=PASS|FAIL|HOLD
dec009_contract_scope=PASS|FAIL|HOLD
dec009_web_runtime_status=DEFERRED_NOT_G2_FAILURE
example_manifest_integrity=PASS|FAIL|HOLD
contract_test_passed=true|false
runtime_gate_recommendation=ALLOW|HOLD

failed_case_ids=
remaining_blockers=
evidence_paths=
```

## 10. 회신 이후 전달 경로

```text
최지용 G2 계약 수정·Push
→ 김은진 동일 Commit 독립 재검증
→ 최지용이 QA 회신과 미해결 항목 취합
→ 윤승혁이 B02~B04 및 Runtime Gate 최종 판단
→ 허용된 경우 최지용 Backend Runtime·DB 구현
→ Backend 검증 후 한예나 Web·양정현 Mobile 소비자 인계
```

김은진은 PM에게 직접 정책 승인을 다시 요청할 필요가 없다. 먼저 최지용에게 위 형식으로 회신하고, 최지용이 계약 변경·QA 증적을 한 묶음으로 PM에게 전달한다.

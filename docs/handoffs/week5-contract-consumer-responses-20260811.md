# 2026-08-11 Web·Mobile 계약 소비 회신 접수

> PM 기준 Commit: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 현재 재검증 후보: `main@4ac79e6227ce271252054b1e986d6ee24eefce4a`
> 접수자: 윤승혁
> 목적: 외부 전달 회신을 3.3 소비자 검토 증거로 정규화

## 1. Mobile — 양정현

| 항목 | 접수 내용 |
|---|---|
| 기준 Branch | `jeonghyun` |
| 구현 Commit | `9336e9c22fa8963115e5f0e27e67868e32f40625` |
| 현재 main 포함 | YES |
| 계약 소비 | DTO·UiState·`allowed_actions`·`state_version`·Date·Error·Remote/Mock 경계 PASS |
| 검증 | Core·Customer·Technician Unit, Connected Test, APK·AndroidTest APK, `verify-build.bat`, 실단말 설치 PASS |
| 잔여 제한 | Guidance·Follow-up·Technician Visit Backend Route 대기, 미제공 기능은 fail-closed |
| PM 판정 | **APPROVE** |

Backend Route 대기는 Mobile이 계약과 다르게 소비한 결함이 아니다. Remote 실패를 Fixture 성공으로 바꾸지 않고 기능을 닫아 두므로 3.3 Mobile 소비자 ACK로 인정한다. 전체 P0 Feature Complete 판정과는 분리한다.

## 2. Web — 한예나

| 항목 | 접수 내용 |
|---|---|
| 기준 Branch | `yena` |
| 기재 Commit | `454339a4e5b3` |
| 현재 main 포함 | 확인 불가 — 로컬 Git Object 없음, 현행 `origin/yena@11f0950...`도 main 미포함 |
| 계약 소비 | 상태·Version·`allowed_actions`·Date·403/404/409·Remote/Mock 경계 PASS |
| 제한 | 422 필드 매핑 미확인, 신규 Action 화이트리스트 갱신 필요, Mock/Remote CI 분리 필요 |
| 보고된 검증 | Remote 표적 34 Test, Mock 전체 142 Test, Lint·TypeScript·Build PASS |
| PM 판정 | **CONTENT_APPROVED · CURRENT_BASELINE_ACK_PENDING** |

현재 `ApiError.details`는 자유 형식이고 `FieldError` Schema에는 필드 구조가 확정돼 있지 않다. 따라서 현행 계약 기준으로 422 메시지·Correlation ID를 보존하면 소비 가능하며, 필드별 Form 매핑은 FieldError 계약 확정 후 의무화한다.

신규 `allowed_actions`는 계약 Registry 변경과 Web 화이트리스트 변경을 같은 변경 창에서 검토한다. Web 반영 전에는 신규 Action을 노출하지 않는 fail-closed 동작을 유지한다.

Mock 전체 회귀와 Remote 계약 표적 Test의 CI 분리는 3.4 CI 운영 협의에 포함한다.

기재 Commit의 전체 SHA·Push 또는 main 병합을 확인하기 전에는 3.3 Web ACK 수치에 포함하지 않는다.

## 3. QA — 김은진

| 항목 | 접수 내용 |
|---|---|
| 기준 Commit | `92b0674cd1a3376a2c058715cd5ef32222125755` |
| Contract Test | 12 PASS |
| 5주차 Action Contract | 4 PASS |
| 대표 Fixture | 4 PASS |
| 대표 E2E | 17/17 PASS |
| Crosswalk | 23 Action PASS |
| 생성물 Drift | NONE |
| QA 판정 | `PASS_FOR_CONTRACT_AND_DATA_CONSUMER` |
| 잔여 제한 | Runtime 소비 여부는 각 Runtime Owner 확인 필요 |
| PM 판정 | **APPROVE** |

Runtime Owner 확인 대기는 Backend·AI·Web·Mobile의 실제 소비 판정 경계이며, 김은진의 Contract·Data·Fixture·Drift 검토 완료를 무효화하지 않는다. 따라서 3.3 QA 소비자 ACK로 인정한다.

## 4. Backend — 최지용

| 항목 | 접수 내용 |
|---|---|
| 기준 Commit | `92b0674cd1a3376a2c058715cd5ef32222125755` |
| 정적 Gate | Crosswalk `12/7/0/4`, Contract 12 PASS |
| Backend 표적 | 133 PASS, PostgreSQL 전용 3 Skip |
| 불일치 1 | `CANCEL_INQUIRY`가 고객 DRAFT만 구현돼 승인 역할·상태보다 좁음 |
| 불일치 2 | `allowed_actions`가 Visit·Transition·Domain Guard와 Runtime availability를 평가하지 않음 |
| 담당자 판정 | `CHANGE_REQUEST` |
| PM 판정 | **CHANGE_REQUEST** |

PM은 승인 계약 유지와 `DYNAMIC_GUARD_AND_RUNTIME_FILTER`를 결정했다. 수정·표적 회귀·PostgreSQL 독립 QA 전까지 Backend ACK로 계산하지 않는다.

## 5. 현재 취합 결과

```text
mobile=APPROVE_NO_AREA_DIFF
web=CONTENT_APPROVED_CURRENT_BASELINE_ACK_PENDING
qa=REVALIDATION_REQUIRED_AFTER_CONTRACT_RUNTIME_CHANGE
backend=FIX_APPLIED_CONTRACT_FOLLOWUP_AND_QA_PENDING
consumer_ack=1/5
remaining_reviewers=최지용-followup,김은진-revalidation,이동윤,한예나-current-baseline
```

## 6. Backend 수정·검증 회신 v0.4

| 항목 | 접수 내용 |
|---|---|
| Runtime 수정 | `e290fe3d43ae5adf2a6ab758cbf2e19922046cd1` |
| 작성자 후보 | `83f737326de75a6015a606c0050eaa81d1f67a4f` |
| 현재 main 포함 | YES — 현재 `main@4ac79e6`의 조상 |
| 원래 불일치 | 취소 역할·상태 확대, 동적 Guard·Runtime Filter Resolver 적용 |
| 작성자 검증 | 표적 128/5 Skip, 전체 993/19 Skip, PostgreSQL Row Lock 5·취소 25 PASS |
| 원격 검증 | Contract CI·Data CI PASS |
| PM 판정 | **AUTHOR_FIX_ACCEPTED · CONTRACT_FOLLOWUP_AND_INDEPENDENT_QA_PENDING** |

계약 Owner는 `submitSymptom`의 Commit 이후 AI 경계 명시, `updateVisitSchedule`의 `TR-INQ-028` 포함, 고객 Snapshot 동적 `allowed_actions` 포함을 결정했다. API 계약·Backend 후속 적용과 김은진 독립 QA 전까지 Backend ACK로 계산하지 않는다.

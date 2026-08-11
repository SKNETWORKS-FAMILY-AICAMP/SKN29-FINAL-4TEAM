# 2026-08-11 Web·Mobile 계약 소비 회신 접수

> PM 기준 Commit: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
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

## 4. 현재 취합 결과

```text
mobile=APPROVE
web=CONTENT_APPROVED_CURRENT_BASELINE_ACK_PENDING
qa=APPROVE
consumer_ack=2/5
remaining_reviewers=최지용, 이동윤, 한예나-current-baseline
```

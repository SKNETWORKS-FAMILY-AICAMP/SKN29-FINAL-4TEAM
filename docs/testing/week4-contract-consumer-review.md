# 4주차 계약 소비자 정합성 검토

> 검토 기준 Commit: `852f877ec06bf48711497cc8f57744097e7871db`  
> 계약 Version: `1.0.0`  
> 검토일: **2026-08-07 KST**  
> 종합 판정: **계약 Code 정합 / Runtime 통합 및 담당자 승인 대기**

## 1. 검토 기준

- 상태 원천: `contracts/state-machine/inquiry-states.yaml`
- Action 원천: `contracts/codes/workflow-actions.yaml`
- Event·Operation 원천: `contracts/state-machine/inquiry-events.yaml`, `allowed-actions.yaml`
- 구현 분류 원천: `contracts/api/action-operation-crosswalk.yaml`
- 검증 원칙: 전체 계약과 승인된 부분집합을 구분하고 Mock·문자열 DTO·실제 Runtime을 같은 완료 상태로 취급하지 않는다.

## 2. 자동 계약 Gate

| Gate | 결과 | 검증 수량 |
|---|---|---|
| Code Registry | PASS | Registry 28개, 상태 13개, Action 23개, 외부 역할 4개, 방문 상태 7개 |
| OpenAPI | PASS | YAML 101개, Local Ref 303개, Path 22개, Operation 23개 |
| Example | PASS | API JSON 34개 전부 OpenAPI에서 참조, 통합 예시 5개 |
| Action Crosswalk | PASS | Runtime 2, OpenAPI 9, Contract-only 2, Deferred 10 |
| Contract Test | PASS | 정상·Drift 방지 Test 7개 |

## 3. 소비자별 검토 결과

| 소비자·담당자 | 확인한 코드 | 계약 대조 결과 | 경계 | 판정 |
|---|---|---|---|---|
| Backend·최지용 | `backend/apps/workflow/**`, `backend/apps/inquiries/**` | `Inquiry.Status` 13개가 계약 상태 13개와 정확히 일치한다. Engine과 `AllowedActionResolver`는 YAML Event·Guard·Action Catalog를 직접 읽어 23개 원천을 재사용한다. | 실제 Action Runtime은 `SUBMIT_SYMPTOM`, `CANCEL_INQUIRY` 2개이며 상담·방문 Runtime은 없음 | `ALIGNED_WITH_RUNTIME_LIMITATION` |
| Web·한예나 | `workflow-action/**`, `consultation/**` | `CounselorStatus`는 계약 상태 13개와 화면 Fallback용 `UNKNOWN`으로 구성된다. `CounselorActionCode` 11개와 Mock Operation ID가 모두 승인 Registry·Crosswalk 값과 일치한다. | 11개는 승인된 부분집합이며 상담·방문 Repository는 Mock이다. `RESUME_CONSULTATION`, `FINALIZE_INQUIRY` 등 Deferred Action도 Mock에서만 사용한다. | `ALIGNED_MOCK_ONLY` |
| Mobile·양정현 | `mobile/core/**/InquiryModels.kt`, Customer Intake | `AllowedAction` DTO는 계약 필드 6개를 수용한다. `InquiryActionLabels` 4개가 모두 승인 Action이며 임의 Action은 없다. | 상태와 Action Code가 문자열 DTO이고 Intake 4개만 명시적으로 지원한다. `REQUEST_CONSULTATION`은 현재 Contract-only·Fixture 경계이며 최신 Build는 별도 차단 상태다. | `ALIGNED_PARTIAL` |
| AI·이동윤 | `ai/app/orchestration/**`, `ai/app/interfaces/http/**` | 위험도·근거 없음·사용 안내 정책과 `state_version`은 응답에 유지된다. AI 로그의 `analysis_started/completed/failed`는 관측 Event이며 State Machine Event가 아니다. | `PRODUCT_VALIDATION_FAILED`, `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE`를 Backend Event로 매핑·저장하는 실제 연결이 없다. AI가 직접 상태를 변경하지 않는 책임 경계는 준수한다. | `POLICY_ALIGNED_INTEGRATION_BLOCKED` |
| QA·김은진 | `scripts/contracts/**`, `tests/contract/**`, Data CI | Registry·OpenAPI·Example·Crosswalk Drift를 CI에서 차단한다. | Backend·AI·Web·Mobile 담당자의 실제 Test·PR 승인 증거는 별도 회신이 필요하다. | `GATE_VERIFIED_OWNER_REVIEW_PENDING` |

## 4. Code 집합 판정

| 대상 | 계약 전체 | 소비자 선언 | 결과 |
|---|---:|---:|---|
| Backend Inquiry 상태 | 13 | 13 | 정확히 일치 |
| Backend 외부 Action 원천 | 23 | YAML 직접 소비 | 정확히 일치 |
| Web 상담사 상태 | 13 | 13 + `UNKNOWN` | 계약 상태 일치, UI Sentinel 승인 예외 |
| Web 상담사 Action | 23 | 11 | 승인된 부분집합, 임의 Code 0 |
| Mobile Intake Action | 23 | 4 | 승인된 부분집합, 임의 Code 0 |
| AI 자동 State Machine Event | 4 | 0 | Backend 매핑 미구현 |

`UNKNOWN`은 Web 내부 표시 Fallback이며 Backend 요청이나 계약 Code로 전송하지 않는 조건으로 허용한다. Web·Mobile 부분집합은 구현 범위를 나타내며 전체 Action 구현 완료를 뜻하지 않는다.

## 5. 후속 조치 및 담당자 증거

| ID | 담당자 | 요청할 증거 | 연결 Blocker | 상태 |
|---|---|---|---|---|
| `CCR-BE-01` | 최지용 | 현재 Commit의 Backend 계약 Test·Migration 결과와 Runtime Action 목록 | `W4-BLK-005`, `W4-BLK-011` | 대기 |
| `CCR-AI-01` | 이동윤·최지용 | AI 결과 4분기와 State Machine Event 매핑표, HTTP·DB 저장 E2E | `W4-BLK-010`, `W4-BLK-012` | 대기 |
| `CCR-WEB-01` | 한예나 | 11개 Action Type·Operation ID Test와 Mock/Remote 경계 확인 | `W4-BLK-011` | 정적 검토 완료, 담당자 회신 대기 |
| `CCR-MOB-01` | 양정현 | Intake Action 4개 DTO·409 복구 Test와 최신 Gradle Build 결과 | `W4-BLK-007` | 정적 검토 완료, 담당자 회신 대기 |
| `CCR-QA-01` | 김은진 | GitHub Actions 계약 Gate 결과와 담당자별 Test·PR 링크 | - | Push/PR 실행 대기 |

## 6. 결론

- 상태·Action Registry와 소비자 코드 사이에서 승인되지 않은 Code는 발견되지 않았다.
- Action 23개 전체 분류와 자동 Contract Gate가 `852f877...`에 포함되어 `W4-BLK-013` 해제 조건을 충족한다.
- Backend 상담·방문, Backend–AI 수직 연결, Web Remote Adapter, Mobile 최신 Build는 별도 Runtime 차단으로 유지한다.
- 따라서 3.2의 **기계 계약 기준선은 폐쇄**했으며, 최종 완료 표시는 담당자별 Test·PR 회신을 받은 뒤 `OWNER_REVIEW_PENDING`을 해제한다.

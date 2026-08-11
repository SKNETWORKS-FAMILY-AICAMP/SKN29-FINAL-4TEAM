# 5주차 E2E Action 구현 인계

> 결정 원본: `docs/decisions/week5-e2e-action-decision.md`  
> 상태: **OWNER_APPLIED · CONTRACT_QA_VERIFIED**
> 원칙: 현행 WBS 날짜를 유지하며 PM 결정, 주관 담당자 계약 적용, Runtime 완료를 구분한다.
> 용도: **PM 내부 진행 관리용 — 팀원 전달 불필요**

## 1. 문서 사용 방법

이 문서는 전체 담당자와 순서를 보여주는 Index다. 실제 적용·검증 담당자는 아래 개별 요청서를 사용한다.

1. 최지용이 `week5-e2e-action-backend-contract-apply-request.md`에 따라 API·Code·Crosswalk를 적용한다.
2. 최지용이 적용 Commit SHA와 Validator 결과를 회신한다.
3. 김은진이 그 Commit을 기준으로 `week5-e2e-action-contract-qa-request.md`를 수행한다.
4. 윤승혁이 두 회신을 확인한 뒤 3.2 완료 여부를 판정한다.

| 순서 | 문서 | 수신자 | 현재 상태 |
|---:|---|---|---|
| 1 | `docs/handoffs/week5-e2e-action-backend-contract-apply-request.md` | 최지용 | 적용 완료 |
| 2 | `docs/handoffs/week5-e2e-action-contract-qa-request.md` | 김은진 | Contract Gate 검증 완료 |
| 3 | 이 Index와 PM 결정서 | 윤승혁 | 3.2 완료 판정 |

한예나·양정현·이동윤을 포함한 실제 소비자 검토는 3.3에서 현재 기준 Commit으로 요청한다.

## 2. 전체 담당자 Matrix

| 담당자 | 구현·검토 범위 | WBS·목표일 | 완료 증거 |
|---|---|---|---|
| 최지용 | `contracts/api/**`와 `contracts/codes/**`에 8개 Operation·Schema·Crosswalk·코드 Binding을 검토·적용한 뒤 URL·Serializer·Service·Transaction·RBAC·멱등성·409 구현 | `T-026/T-035/T-036/T-043/T-044/T-055`, 각 WBS 날짜 | OpenAPI/Crosswalk Validator, Backend API·Unit·PostgreSQL Test |
| 이동윤 | 추가 답변 후 AI 재평가, `SAFE_GUIDANCE_READY` 결과 Schema·Safety·Evidence 제공. AI가 State를 직접 변경하지 않음 | `T-026` 및 AI 연동 일정 | AI Schema·Routing·Safety·Fallback Test |
| 한예나 | 상담사 Web에서 `allowed_actions` 기반 상담 시작·재개·최종 완료 노출, 409 시 서버 상태 재조회 | Web 소비 일정 | Test·Lint·Build·Remote Smoke |
| 양정현 | 고객 추가 답변·상담 요청·해결/미해결 피드백, 기사 방문 시작·완료 DTO/UiState/행동 연결 | `T-035`~`T-037`, `T-042`~`T-043` | Mobile Unit/UI Test·Build·Remote 결과 |
| 김은진 | 주관할 `tests/**`에서 8개 Operation Contract Test, 정상 14단계·미해결 2단계 Fixture, 권한·Version·멱등성·409 회귀를 검토·적용 | 계약 변경 즉시 및 `T-047/T-050/T-051` | 같은 SHA의 명령·Exit Code·QA Report |
| 윤승혁 | PM Decision·State Example·Changelog 정합성, 담당자 적용 회신 수집과 3.3 Baseline 판정 | 3.2 즉시, 3.3 후속 | 담당자 적용 Commit·Contract Gate·소비자 검토표 |

## 3. 구현 공통 조건

1. 최지용의 API·Code 적용과 김은진의 Contract QA가 완료돼 3.2를 완료 처리했다.
2. `x-runtime-status: NOT_IMPLEMENTED`는 Source와 Test 증거가 모두 확보된 뒤에만 갱신한다.
3. Client가 다음 State를 보내거나 자체 계산하지 않는다.
4. 모든 쓰기는 `Idempotency-Key`, `X-Correlation-ID`, `state_version`을 사용한다.
5. 403·404 객체 은닉, 409 Version/멱등 충돌, 422 Payload/Guard 실패 의미를 약화하지 않는다.
6. 정상 14단계와 미해결 보조 시나리오를 혼합해 PASS로 기록하지 않는다.

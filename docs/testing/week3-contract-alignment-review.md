# 3주차 계약 정합성 검토표

> 검토일: 2026-07-29  
> 검토 책임: 윤승혁(PM·기술 통합)  
> 관련 업무: `윤승혁_3주차_업무_지침서.md` 3.3, 3.6  
> 계약 기준선: State Machine `v1.0.0 / TEAM_APPROVED`  
> 문서 상태: 1차 검토 완료·담당자 조치 대기
> 담당자 전달용 요청서: [`../handoffs/week3-contract-alignment-action-requests.md`](../handoffs/week3-contract-alignment-action-requests.md)

## 1. 목적

Backend, AI, Web, Mobile, Data·QA가 확정된 State Machine 계약과 공통 필드·코드를 동일하게 사용하는지 확인한다. 불일치를 발견한 경우 PM이 구현을 대신 수정하지 않고, 주관 담당자에게 수정 범위와 검증 기준을 배정한다.

이 문서는 검토 결과와 후속 조치를 기록한다. 상태·이벤트·권한·허용 행동의 기계 판독 기준은 `contracts/**`를 단일 기준본으로 사용한다.

## 2. 검토 기준

### 2.1 기준 문서와 계약

- `docs/weekly-task/윤승혁_3주차_업무_지침서.md`
- `docs/planning/md/팀원별 관할 영역 v2.md`
- `docs/architecture/프로젝트 디렉토리 구조 v2.md`
- `contracts/state-machine/**`
- `contracts/ai/**`
- `contracts/api/**`
- `contracts/codes/**`
- `contracts/error-codes/**`

### 2.2 판정 기준

| 판정 | 의미 |
|---|---|
| 충족 | 확정 계약과 구현이 일치하고 실행 또는 테스트 증거가 존재함 |
| 부분 충족 | 일부 계약은 반영됐지만 미연결·불일치·검증 공백이 남음 |
| Mock 검증 완료 | 계약 기반 Mock 동작과 테스트는 있으나 실제 API 연동이 남음 |
| 미충족 | 핵심 상태·이벤트·필드 또는 처리 방식이 확정 계약과 다름 |
| 확인 불가 | 실행 환경이나 증거가 없어 코드만으로 최종 판정할 수 없음 |

## 3. 종합 판정

| 담당자 | 영역 | 판정 | 현재 분류 | 핵심 사유 |
|---|---|---|---|---|
| 최지용 | Backend | 부분 충족 | 연동 확인·다음 주 인계 | 엔진·Guard·409·멱등성 기반은 있으나 실제 적용이 문의 생성·취소에 한정됨 |
| 이동윤 | AI | 부분 충족 | 오류 수정·연동 확인 | 위험·근거 없음 정책은 있으나 AI 응답 Schema와 Runtime DTO가 다르고 Backend 이벤트 연결이 없음 |
| 한예나 | Web | Mock 검증 완료 | 연동 확인 | `allowed_actions`, `state_version`, 409 Mock 처리는 있으나 실제 API 미연동 및 일부 타입 누락 |
| 양정현 | Mobile | 미충족 | 오류 수정 | 계약에 없는 상태·이벤트를 사용하고 `state_version`, `allowed_actions`, 409 처리가 없음 |
| 김은진 | Data·QA | 부분 충족 | 오류 수정 | 대표 14단계 데이터는 있으나 계약 해시, Manifest, 과거 리포트 및 최상위 테스트가 미정합 |

현재 상태만으로는 전체 서비스의 계약 이행 완료 또는 4주차 통합 준비 완료로 판정하지 않는다.

## 4. 담당자별 상세 검토

### 4.1 최지용 — Backend

#### 충족 사항

- `backend/apps/inquiries/models/inquiry.py`에 계약의 Inquiry 상태 13개가 정의되어 있다.
- `backend/apps/workflow/engine/state_machine.py`가 YAML 계약을 사용해 결정적 전이와 종료 상태를 검사한다.
- `backend/apps/workflow/engine/guard_evaluator.py`에 역할, 인증, `state_version`, `Idempotency-Key`, 도메인 Guard 검사가 있다.
- `backend/apps/workflow/services/idempotency_service.py`가 동일 키의 다른 요청 및 처리 중 요청을 409로 거부한다.
- 문의 생성·취소 API에 소유자 권한, 상태 버전, 전이 이력, 멱등성 및 `allowed_actions` 처리가 있다.
- Backend 단위·API 테스트에 상태 전이, Guard, 멱등성 및 409 계약 검증 항목이 존재한다.

#### 불일치·미구현

- `backend/apps/inquiries/services/inquiry_transition_service.py`는 설명 문자열만 있고 범용 전이 실행 로직이 없다.
- 문의 생성·취소 Service가 범용 `StateMachine`과 `GuardEvaluator`를 공통 경로로 호출하지 않고 별도 로직을 사용한다.
- `backend/apps/consultations/services/consultation_service.py`와 상담 API가 Stub 상태다.
- `backend/apps/visits/services/visit_transition_service.py`와 방문 API가 Stub 상태다.
- 대표 14단계 흐름 중 문의 생성·취소 외 상담·방문·완료 전이가 Runtime에 연결되지 않았다.

#### 요청 작업과 완료 조건

| 요청 작업 | 완료 조건 | 상태 |
|---|---|---|
| 공통 Inquiry 전이 Service 구현 | 엔진→Guard→행 저장→이력→허용 행동 계산이 하나의 트랜잭션으로 수행됨 | 연동 확인 |
| 상담·방문 행동별 Endpoint 연결 | 대표 14단계 이벤트가 계약의 `operation_id` 및 전이 규칙과 연결됨 | 다음 주 인계 |
| 409 응답 통일 | 최신 상태, `current_state_version`, `allowed_actions`를 모든 상태 변경 API가 동일하게 반환함 | 연동 확인 |
| 대표 흐름 API 테스트 | 정상·권한·상태 충돌·중복 요청을 포함한 실행 증거가 존재함 | 검토 대기 전 필수 |

### 4.2 이동윤 — AI

#### 충족 사항

- `ai/app/safety/usage_guidance_classifier.py`가 공식 근거 없음에서 `PENDING_CONSULTATION`을 반환한다.
- 위험도가 `DANGER`이면 `TOTAL_STOP`을 우선하고 `NORMAL` 반환을 방지한다.
- `GENERAL`, `CAUTION`, `DANGER` 위험도와 사용 안내 상태 네 가지가 AI 계약에 정의되어 있다.

#### 불일치·미구현

- `contracts/ai/responses/SymptomAnalysisResponse.schema.json`은 `inquiry_id`, `correlation_id`를 최상위 필드로 요구한다.
- 실제 `ai/app/schemas/pipeline.py`는 두 값을 `trace_context` 안에 넣고, 계약에 없는 `model_metadata`, `processing_traces`를 반환한다.
- 응답 계약이 `additionalProperties: false`이므로 현재 Runtime 응답과 JSON Schema가 일치하지 않는다.
- `backend/apps/inquiries/services/inquiry_ai_service.py`가 Stub이어서 AI 결과를 `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE` 이벤트로 변환하지 않는다.
- `ai/app/safety/no_evidence_policy.py`는 별도 실행 구현 없이 설명 문자열만 존재한다. 실제 정책은 `UsageGuidanceClassifier`에 포함되어 있다.

#### 요청 작업과 완료 조건

| 요청 작업 | 완료 조건 | 상태 |
|---|---|---|
| AI 응답 DTO와 JSON Schema 정합화 | 실제 응답이 확정 Schema 검증을 통과함 | 오류 수정 |
| AI 결과→Backend 이벤트 매핑 협의 | 정상·위험·근거 없음 결과와 세 자동 이벤트의 결정표가 기록됨 | 연동 확인 |
| Backend Mapper 공동 검증 | AI가 상태를 직접 변경하지 않고 Backend가 Guard 후 이벤트를 실행함 | 연동 확인 |
| 대표 결과 테스트 | 정상·위험·근거 없음 응답과 금지 행동이 자동 검증됨 | 검토 대기 전 필수 |

### 4.3 한예나 — Web

#### 충족 사항

- 상담 행동 버튼은 상태에서 임의 계산하지 않고 응답의 `allowedActions`로 표시한다.
- 상태 변경 요청에 현재 `state_version`과 멱등성·추적 식별자를 포함한다.
- 409 Mock 응답에서 최신 상태 버전과 허용 행동을 반영한다.
- 충돌 후 입력을 유지하고 자동 재시도하지 않는다.
- `allowed_actions` 버튼 노출, 409 처리 및 공통 오류 분류 테스트가 존재한다.

#### 불일치·미구현

- 상담 행동은 `web/src/features/consultation/api/consultationMockApi.ts`를 사용하며 실제 Backend API와 연결되지 않았다.
- 상담 모델의 사용 안내 상태에 `PENDING_CONSULTATION`이 없다.
- 상담 화면 상태 타입이 전체 Inquiry 상태를 포괄하지 않는다.
- Web 위험도 타입은 대문자이지만 AI JSON Schema의 위험도 값은 소문자다. Backend 공개 API의 최종 표현과 Mapper 책임을 확정해야 한다.

#### 요청 작업과 완료 조건

| 요청 작업 | 완료 조건 | 상태 |
|---|---|---|
| 실제 Backend API Adapter 연결 | Mock과 실제 API의 요청·응답 차이가 제거됨 | 연동 확인 |
| 상태·사용 안내 타입 보강 | 공개 API가 반환하는 모든 화면 대상 상태를 안전하게 처리함 | 오류 수정 |
| 응답 Mapper 확정 | snake_case 응답과 화면 모델 변환 규칙이 테스트됨 | 연동 확인 |
| 실제 409 통합 테스트 | 입력 유지, 최신 버전·허용 행동 반영, 무자동 재시도가 검증됨 | 검토 대기 전 필수 |

### 4.4 양정현 — Mobile

#### 충족 사항

- `StateFlow` 기반으로 고객 문의 화면 상태를 보관하는 기본 구조가 있다.
- 일부 계약 상태인 `DRAFT`, `QUESTIONNAIRE_IN_PROGRESS`, `VISIT_REVIEW_PENDING`, `VISIT_SCHEDULED`, `COMPLETION_PENDING`, `RESOLVED`, `CANCELLED`가 존재한다.

#### 불일치·미구현

- `mobile/core/.../Models.kt`가 계약에 없는 `ERROR_CONFIRMED` 상태를 사용한다.
- `AI_GUIDANCE`, `CONSULTATION_REQUIRED`, `CONSULTATION_IN_PROGRESS`, `VISIT_SCHEDULING`, `REVISIT_REQUIRED`, `REOPENED`가 누락됐다.
- `ConfirmError`, `RequestVisit`, `CompleteVisit` 등 자체 이벤트가 확정 계약 이벤트와 다르다.
- `RequestVisit`가 상담·방문 검토 단계를 건너뛰고 `VISIT_SCHEDULED`로 직접 전환한다.
- Inquiry 모델에 `state_version`과 `allowed_actions`가 없다.
- 409 최신 상태 반영, 입력 유지 및 상태 전이 단위 테스트를 확인하지 못했다.

#### 요청 작업과 완료 조건

| 요청 작업 | 완료 조건 | 상태 |
|---|---|---|
| 상태·이벤트 코드 교체 | Mobile DTO와 Enum이 State Machine v1.0.0 코드만 사용함 | 오류 수정 |
| 로컬 전이 책임 축소 | 화면 행동은 Backend의 `allowed_actions`를 기준으로 결정함 | 오류 수정 |
| `state_version`·409 처리 | 충돌 시 최신 상태를 반영하고 사용자 입력을 유지함 | 오류 수정 |
| Mobile 계약 테스트 | 정상·위험·근거 없음·409 흐름의 단위 또는 UI 테스트가 존재함 | 검토 대기 전 필수 |

### 4.5 김은진 — Data·QA

#### 충족 사항

- `data/config/e2e/representative_case.json`이 대표 시나리오의 14개 이벤트와 최종 `state_version=14`를 정의한다.
- 합성 Workflow, 상태 이력, 감사 이벤트, 상담·방문·후속 확인 데이터가 대표 흐름을 표현한다.
- 계약 소스 해시와 대표 E2E 불변 조건을 검사하는 Data 테스트가 존재한다.

#### 불일치·미구현

- `data/config/workflow/service_contract_mapping.json`의 State Machine 계약 해시 4개가 v1.0.0 파일과 다르다.
- 같은 매핑 파일이 현재 확정된 종료·재개 및 제품 검증 실패 정책을 여전히 `blocked_decisions`로 기록한다.
- 대표 E2E 검증이 Dataset Manifest 건수 불일치로 실패한다.
- `data/processed/validation/step4/representative_e2e_fixture_report.json`은 과거 12단계 결과를 현재 결과처럼 보관한다.
- 최상위 `tests/contract/state-machine/**`와 `tests/e2e/**`에는 실제 테스트가 없고 `.gitkeep`만 있다.

#### 실행 결과

실행 명령:

```text
python -m unittest data.tools.tests.test_service_contract_mapping data.tools.tests.test_representative_e2e
```

결과: 총 11개 중 9개 통과, 2개 실패

1. State Machine 계약 소스 해시 4개 불일치
2. 대표 E2E Dataset Manifest 건수 불일치

#### 요청 작업과 완료 조건

| 요청 작업 | 완료 조건 | 상태 |
|---|---|---|
| 계약 해시·Crosswalk 반영 | 계약 소스 해시와 결정 상태가 v1.0.0 기준으로 갱신됨 | 오류 수정 |
| Manifest·리포트 재생성 | 대표 흐름이 14단계·최종 버전 14로 일관되게 보고됨 | 오류 수정 |
| Data 테스트 재실행 | 현재 실패한 2개 테스트가 통과함 | 검토 대기 전 필수 |
| 최상위 계약·E2E 테스트 연결 | `tests/contract/**`, `tests/e2e/**`에서 CI 실행 가능한 검증이 존재함 | 다음 주 인계 |

## 5. 수정·병합 권장 순서

1. 김은진: 계약 해시, Crosswalk 소비 정보, Manifest와 14단계 리포트 갱신
2. 이동윤·최지용: AI 응답 계약과 Backend 자동 이벤트 매핑 확정
3. 최지용: 공통 전이 Service 및 상담·방문 Runtime 연결
4. 한예나·양정현: 확정 Backend 공개 응답에 맞춘 Web·Mobile 타입과 실제 API 연동
5. 김은진: 계약·통합·E2E 회귀 테스트 실행 및 결과 기록

계약 변경이 필요한 경우 구현 변경보다 계약 변경을 먼저 검토한다. Web·Mobile은 Backend API가 확정되기 전에 임의 상태 전이 규칙을 추가하지 않는다.

## 6. 재검토 체크리스트

- [ ] Backend 대표 14단계 전이의 Runtime 연결 증거가 있다.
- [ ] 역할·담당자·`state_version`·멱등성 Guard가 행동별 API에서 동일하게 적용된다.
- [ ] 모든 상태 충돌 응답이 최신 상태·버전·허용 행동을 반환한다.
- [ ] AI 실제 응답이 JSON Schema 검증을 통과한다.
- [ ] 위험·근거 없음 결과가 Backend 자동 이벤트로 안전하게 연결된다.
- [ ] Web이 실제 API의 `allowed_actions`만으로 행동 버튼을 표시한다.
- [ ] Mobile이 계약에 없는 상태·이벤트를 사용하지 않는다.
- [ ] Data 계약 해시와 Manifest가 최신 기준본과 일치한다.
- [ ] 대표 E2E가 14단계·최종 `RESOLVED`·`state_version=14`로 통과한다.
- [ ] 최상위 계약·통합·E2E 테스트 또는 동등한 CI 증거가 존재한다.
- [ ] 미완료 항목마다 담당자와 처리 예정 시점이 기록되어 있다.

## 7. 검증 범위와 제한

- Backend는 저장소에 가상환경이 없고 현재 Python 환경에 `PyYAML`·`pytest`가 없어 테스트를 실행하지 못했다. 판정은 소스와 테스트 코드 존재 여부를 기준으로 했다.
- Web은 `node_modules`가 없어 Vitest를 실행하지 못했다. 판정은 구현과 테스트 코드 정적 검토를 기준으로 했다.
- Mobile은 Gradle Wrapper가 있으나 이번 검토에서는 Build·테스트를 실행하지 않았다. 상태·이벤트·DTO 소스를 정적으로 검토했다.
- Data 테스트는 실제 실행했으며 11개 중 2개 실패를 재현했다.

## 8. PM 최종 판정

State Machine 계약 자체는 `v1.0.0 / TEAM_APPROVED`로 확정되었다. 그러나 계약 확정은 각 서비스의 구현 완료를 의미하지 않는다.

현재 3.3 업무는 **1차 정합성 검토와 불일치 식별까지 완료**된 상태다. 담당자 수정, 실행 증거 제출 및 재검토가 끝난 뒤에만 3.3 완료와 4주차 통합 진입을 승인한다.

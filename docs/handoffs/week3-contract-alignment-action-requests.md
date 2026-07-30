# 3주차 계약 불일치 수정 요청서

> 작성일: 2026-07-29  
> 요청자: 윤승혁(PM·기술 통합)  
> 관련 업무: `윤승혁_3주차_업무_지침서.md` 3.3  
> 기준선: State Machine `v1.0.0 / TEAM_APPROVED`  
> 상세 근거: [`../testing/week3-contract-alignment-review.md`](../testing/week3-contract-alignment-review.md)

## 먼저 읽어주세요

이번 요청의 목적은 **새 기능을 추가하는 것**이 아니라, 확정된 계약과 각 영역의 DTO·Enum·Mock·예시가 같은 의미와 형식을 사용하도록 맞추는 것입니다.

- 기준은 `contracts/**`입니다. 계약 자체를 바꿔야 한다고 판단되면 먼저 윤승혁에게 변경안을 알려주세요.
- 다른 담당자의 소스는 직접 수정하지 말고, 필요한 변경 내용을 회신의 `PM 결정 필요`에 적어주세요.
- 실제 API 연동 완료, 전체 Runtime 구현, 전체 E2E 통과는 이번 3.3 요청의 완료 조건이 아닙니다.
- 변경 후에는 수정 파일과 확인 결과를 아래 회신 양식으로 남겨주세요.

## 1분 요약

| 담당자 | 이번에 맞출 내용 | 목표일 |
|---|---|---|
| 최지용 / Backend | API의 빈 Workflow Schema와 성공·409 응답 필드 정의 | 2026-07-31 |
| 이동윤 / AI | JSON Schema와 Runtime DTO의 응답 구조·Enum 통일 | 2026-07-31 |
| 한예나 / Web | 위험도·이용 상태·Mock을 확정 계약과 통일 | 2026-07-30 |
| 양정현 / Mobile | 서버 상태·이벤트 DTO와 행동 기준을 확정 계약과 통일 | 2026-07-31 |
| 김은진 / Data·QA | 계약 해시·결정 사항·Fixture 보고서 갱신 | 2026-07-30 |

각 담당자는 자신의 항목만 확인하면 됩니다.

---

## 최지용 / Backend

### 한 줄 요청

Workflow 성공 응답과 409 충돌 응답의 필드 형태가 OpenAPI, 예시, Serializer에서 서로 같도록 정리해주세요.

### 왜 필요한가

`AllowedAction.yaml`과 `StateTransitionResult.yaml`의 속성이 비어 있어 Web·Mobile이 API 계약만 보고 응답 DTO를 확정하기 어렵습니다. 또한 성공 응답의 `allowed_actions`는 행동 객체인데, 409 응답에서는 행동 코드 문자열 배열을 사용하므로 두 형식의 차이를 계약에 명확히 남겨야 합니다.

### 이번 요청에서 할 일

1. `contracts/api/components/schemas/workflow/AllowedAction.yaml`에 다음 필드를 실제 응답과 맞춰 정의해주세요: `code`, `label`, `operation_id`, `style`, `requires_confirmation`, `confirmation_message`.
2. `contracts/api/components/schemas/workflow/StateTransitionResult.yaml`에 상태, `state_version`, `allowed_actions` 등 공통 성공 응답 필드와 필수·nullable 정책을 정의해주세요.
3. 성공 응답의 행동 객체 배열과 `WorkflowConflictDetails.yaml`의 행동 코드 배열을 이름이나 설명으로 명확히 구분해주세요.
4. OpenAPI Schema, 대표 성공·409 예시, Backend Serializer 및 오류 응답의 필드명과 타입이 같은지 확인해주세요.

### 이번 요청에 포함되지 않는 일

- 상담·방문 Endpoint의 전체 Runtime 구현
- 대표 14단계 흐름의 실제 실행 완료
- Web·Mobile의 실제 API 연동

### 완료로 인정할 증거

- 변경한 Schema·예시·Serializer 파일 목록
- OpenAPI 또는 관련 계약 검증 결과
- 성공 응답과 409 응답 예시 각 1건
- 다른 영역의 결정이 필요한 사항이 있다면 그 내용

---

## 이동윤 / AI

### 한 줄 요청

AI 분석 응답의 JSON Schema와 Runtime Pydantic DTO가 동일한 구조와 Enum을 사용하도록 맞춰주세요.

### 왜 필요한가

현재 계약은 `inquiry_id`, `correlation_id`를 최상위 필드로 요구하지만 Runtime DTO는 `trace_context` 안에 두고 있습니다. Runtime에만 있는 `model_metadata`, `processing_traces`도 있어 소비자가 어느 구조를 따라야 하는지 불분명합니다.

### 이번 요청에서 할 일

1. `contracts/ai/schemas/SymptomAnalysisResponse.schema.json`과 Runtime `SymptomAnalysisResult` 중 사용할 단일 응답 구조를 제안하고 윤승혁의 확인 후 통일해주세요.
2. `inquiry_id`, `correlation_id`, `trace_context`, `model_metadata`, `processing_traces`의 위치와 필수·nullable 정책을 동일하게 맞춰주세요.
3. 위험도 값(`general`, `caution`, `danger`)과 이용 상태 코드의 대소문자·허용값을 계약과 DTO·예시에서 통일해주세요.
4. 일반, 위험, 근거 없음, 오류 응답의 대표 예시가 최종 Schema를 통과하는지 확인해주세요.
5. AI 결과가 어떤 State Machine 내부 이벤트로 전달되는지는 매핑 표 또는 인터페이스 정의로 남겨주세요.

### 이번 요청에 포함되지 않는 일

- Backend Event 처리기의 실제 연결 구현
- 전체 AI 파이프라인 또는 전체 E2E 완성
- 확정 계약을 승인 없이 직접 변경하는 일

### 완료로 인정할 증거

- 최종 응답 구조를 선택한 이유와 변경 파일 목록
- JSON Schema/Pydantic 검증 또는 관련 단위 테스트 결과
- 일반·위험·근거 없음 예시
- Backend와 추가 합의가 필요한 이벤트 매핑 항목

---

## 한예나 / Web

### 한 줄 요청

Web의 위험도·이용 상태 타입과 Mock 응답을 확정 API·AI 계약에 맞춰주세요.

### 왜 필요한가

Web 위험도는 대문자 값을 사용하지만 AI 계약은 소문자 값을 사용하고, 이용 상태에는 `PENDING_CONSULTATION`이 빠져 있습니다. `allowed_actions`, `state_version`, 409 처리의 기본 구조는 이미 갖춰져 있으므로 이번에는 경계 DTO와 Mock의 남은 차이만 정리하면 됩니다.

### 이번 요청에서 할 일

1. `PENDING_CONSULTATION`을 Web 이용 상태 타입과 관련 표시·Mock에 반영해주세요.
2. 위험도 대소문자를 계약과 동일하게 사용하거나, API 경계에서 변환한다면 매핑 위치와 규칙을 명확히 남겨주세요.
3. API DTO와 Mock의 필드명·Enum·nullable 정책이 Backend 공개 Schema와 같은지 확인해주세요.
4. 계약에 없는 상태를 수신할 때의 안전한 표시 방식을 확인해주세요. 화면 범위에 필요하지 않은 모든 상태를 UI에 새로 추가할 필요는 없습니다.

### 이번 요청에 포함되지 않는 일

- 실제 Backend API 연동 완료
- 모든 서버 상태에 전용 화면을 만드는 일
- 전체 Web E2E 완료

### 완료로 인정할 증거

- 변경한 타입·Mapper·Mock 파일 목록
- 관련 타입 검사 또는 단위 테스트 결과와 실행 기준 브랜치·커밋
- `PENDING_CONSULTATION`, 위험도, 409 Mock 예시
- Backend Schema 때문에 막힌 항목이 있다면 그 내용

---

## 양정현 / Mobile

### 한 줄 요청

Mobile의 서버 상태·이벤트 DTO를 확정 State Machine 계약과 맞추고, 사용 가능한 행동은 `allowed_actions`를 기준으로 표현해주세요.

### 왜 필요한가

현재 Mobile에는 계약에 없는 `ERROR_CONFIRMED`와 자체 이벤트가 있고, 확정 계약의 일부 상태가 누락되어 있습니다. 이 상태로는 서버 응답을 정확히 역직렬화하거나 Web과 같은 행동 기준을 사용하기 어렵습니다.

### 이번 요청에서 할 일

1. 서버 상태 DTO에서 `ERROR_CONFIRMED`를 제거하거나 로컬 UI 전용 타입으로 분리하고, 누락된 계약 상태를 반영해주세요.
2. `ConfirmError`, `RequestVisit`, `CompleteVisit` 같은 자체 이벤트를 서버 공개 이벤트와 매핑하거나 로컬 전용으로 분리해주세요. 직접 `VISIT_SCHEDULED`로 건너뛰는 로직은 계약 흐름과 맞는지 확인해주세요.
3. 공개 DTO에 `state_version`, `allowed_actions`, 409 충돌 상세 구조를 반영해주세요.
4. 버튼 노출·활성화가 상태 하드코딩이 아니라 `allowed_actions`를 우선하도록 UiState/Mapper 기준을 정리해주세요.
5. 대표 응답을 DTO로 변환하는 매핑 테스트를 추가하거나 갱신해주세요.

### 이번 요청에 포함되지 않는 일

- 실제 Backend API 연동 완료
- 모든 화면과 전체 앱 흐름 구현
- 전체 Mobile E2E 완료

### 완료로 인정할 증거

- 변경한 DTO·Enum·Mapper·Mock·테스트 파일 목록
- 관련 컴파일 또는 단위 테스트 결과
- 정상 응답과 409 응답의 Mobile 변환 예시
- Backend 공개 Schema 때문에 막힌 항목이 있다면 그 내용

---

## 김은진 / Data·QA

### 한 줄 요청

확정 계약을 기준으로 계약 해시, Crosswalk 결정 사항, 대표 Fixture와 생성 보고서를 다시 동기화해주세요.

### 왜 필요한가

`service_contract_mapping.json`의 State Machine 관련 해시가 현재 계약과 다르고, PM Crosswalk에서 이미 결정된 재개·제품 검증 규칙이 미결정 항목으로 남아 있습니다. 대표 Fixture는 14개 이벤트를 사용하지만 이전 생성 보고서에는 12단계 기록도 남아 있습니다.

### 이번 요청에서 할 일

1. State Machine 기준 파일의 현재 해시를 `service_contract_mapping.json`과 Manifest에 반영해주세요.
2. 다음 결정 사항을 확정 Crosswalk와 동일하게 갱신해주세요.
   - 종료 상태에서 같은 문의를 직접 재개하지 않음
   - `CUSTOMER_REPORTED_UNRESOLVED`: `COMPLETION_PENDING` → `REOPENED`
   - `PRODUCT_VALIDATION_FAILED` → `CONSULTATION_REQUIRED`
3. 대표 14이벤트 Fixture를 기준으로 Manifest와 생성·검증 보고서를 다시 생성해주세요.
4. 오래된 12단계 설명이 최신 결과처럼 보이지 않도록 갱신하거나 이력임을 표시해주세요.
5. Data 계약 테스트를 다시 실행하고 실패가 남으면 원인과 담당 영역을 구분해주세요.

### 이번 요청에 포함되지 않는 일

- 최상위 `tests/contract/**`, `tests/e2e/**`에 새 테스트 체계를 만드는 일
- 모든 영역의 전체 E2E 완료
- 다른 담당자의 계약 또는 Runtime 소스를 대신 수정하는 일

### 완료로 인정할 증거

- 변경한 Mapping·Manifest·Fixture·보고서 파일 목록
- 계약 해시 확인 결과
- Data 계약 테스트 결과
- 다른 담당자의 수정 대기 때문에 남은 실패 항목

---

## 처리 순서와 의존성

- 김은진의 해시·보고서 갱신과 한예나의 알려진 Enum 수정은 바로 진행할 수 있습니다.
- 최지용의 공개 API Schema가 확정되면 한예나와 양정현이 경계 DTO를 최종 확인합니다.
- 이동윤의 응답 구조 또는 이벤트 매핑에 계약 변경이 필요하면 구현 전에 윤승혁이 승인 여부를 결정합니다.
- 담당자 회신을 받은 뒤 윤승혁이 상세 검토표의 상태를 갱신하고 3.3 완료 여부를 판정합니다.

## 회신 양식

아래 내용을 복사해 회신해주세요.

```text
[담당자]
[상태] 완료 / 협의 필요 / 차단
[변경 파일]
-

[확인 명령·결과]
-

[남은 차이]
- 없음 / 내용 기재

[PM 결정 필요]
- 없음 / 내용 기재
```


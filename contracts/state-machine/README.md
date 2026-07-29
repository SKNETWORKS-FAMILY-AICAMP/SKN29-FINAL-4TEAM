# Inquiry State Machine 계약

> 채택 기준: `v1.0.0` · `TEAM_APPROVED` · 2026-07-29

## 1. 목적

이 디렉터리는 문의 상태, 이벤트, 전이, Guard, 허용 행동, 역할 권한, 완료 및 동시성 정책의 공통 기준이다.

Backend가 상태 전이의 최종 권위를 가지며, Web·Mobile·AI·QA는 이 계약을 기준으로 구현한다.
클라이언트와 AI는 다음 상태를 직접 지정하거나 DB 상태를 직접 변경하지 않는다.

## 2. 파일 구성

| 파일 | 역할 |
|---|---|
| `inquiry-states.yaml` | 문의 상태와 종료 상태 정의 |
| `inquiry-events.yaml` | 사용자·담당자·시스템 이벤트 정의 |
| `transition-rules.yaml` | 현재 상태와 이벤트에 따른 다음 상태 정의 |
| `transition-guards.yaml` | 역할·소유권·담당자·입력·안전·완료 조건 |
| `allowed-actions.yaml` | 상태·역할별 외부 노출 행동 정의 |
| `role-permissions.yaml` | 역할별 이벤트와 리소스 접근 범위 |
| `completion-policy.yaml` | 자가조치·상담·방문 완료와 재개 정책 |
| `concurrency-policy.yaml` | state_version, 멱등성, 트랜잭션과 충돌 처리 |
| `data-state-crosswalk.yaml` | Data 기존 상태와 Inquiry·Visit 계약 간 변환 기준 |
| `diagrams/inquiry-state-machine.mmd` | Mermaid 상태 흐름도 |

대표 상태 전이 예시는 `examples/`의 흐름별 YAML 7종에서 관리한다.
`representative-e2e.yaml`은 `SYN-JAC104-002`의 14단계 공식 기준이며,
상태 버전 충돌 예시는 `../examples/state-conflict.json`에서 관리한다.

## 3. 구현 활용

### Backend

- Django 상태 Enum과 이벤트 Enum을 계약 코드와 동일하게 작성한다.
- 행동별 API는 이벤트를 생성하고 State Machine Service가 전이와 Guard를 평가한다.
- `allowed_actions`는 Backend가 계산하여 응답한다.
- 상태 변경·Visit 변경·이력 저장·버전 증가는 하나의 트랜잭션에서 처리한다.

### Web·Mobile

- 상태만 보고 버튼을 독자적으로 계산하지 않는다.
- API가 반환한 `allowed_actions`만 노출한다.
- 쓰기 요청에 `state_version`과 `Idempotency-Key`를 포함한다.
- `409 STATE_VERSION_CONFLICT` 발생 시 최신 상태와 행동 목록으로 갱신한다.

### AI

- AI는 DB 상태를 직접 변경하지 않는다.
- 검증된 결과를 `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE`,
  `PRODUCT_VALIDATION_FAILED` 중 하나의 내부 이벤트 후보로 Backend에 전달한다.
- Backend가 상태·버전·Guard를 다시 검증한 뒤 전이를 수행한다.

### QA

다음 명령으로 계약 간 참조와 핵심 불변 조건을 검증한다.

```bash
python scripts/contracts/validate_state_machine.py
```

## 4. 변경 절차

1. 계약 변경 협의
2. 관련 YAML을 함께 수정
3. `contracts/CHANGELOG.md` 기록
4. 검증 스크립트 통과
5. 계약 PR 병합
6. Backend·Web·Mobile·AI 구현 PR 반영

상태나 이벤트를 코드에서 먼저 임의 변경해서는 안 된다.

## 5. 현재 결정 사항

- 이 계약의 최초 채택 버전은 `1.0.0`이며 승인 상태는 `TEAM_APPROVED`이다.
- Data의 기존 상태 표현은 `data-state-crosswalk.yaml`을 통해서만 변환한다.
- `VISIT_REVIEW_PENDING`에는 `VISIT_NEEDED`와 `VISIT_NOT_NEEDED` 두 분기가 존재한다.
- 방문 불필요 확정 시 `COMPLETION_PENDING`으로 이동한다.
- 상담·방문 완료는 고객 해결 확인과 마지막 처리 담당자의 `FINALIZE_INQUIRY`를 거쳐야 한다.
- `RESOLVED`, `CANCELLED`는 종료 상태이며 같은 문의에서 다시 전이하지 않는다.

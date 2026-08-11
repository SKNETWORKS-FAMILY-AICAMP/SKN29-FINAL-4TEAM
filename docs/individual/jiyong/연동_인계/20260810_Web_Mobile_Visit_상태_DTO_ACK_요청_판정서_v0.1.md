# Web·Mobile Visit 상태·DTO ACK 요청·판정서 v0.1

## 0. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-08-10 KST |
| 작성자 | 최지용 — Backend·DB |
| 수신자 | 한예나 — Web, 양정현 — Mobile |
| 검토자 | 김은진 — Data·QA |
| 최종 결정권자 | 윤승혁 — PM |
| 기준 `main` | `c6848a9ec170db37bdf10a0b46e860ef5677b072` |
| Mobile 후보 | `origin/jeonghyun@eb78910ce1b82a8d0fc3dd53dd5e9c43eb3b19f1` |
| 범위 | Visit 상태·date-only 일정·기사 식별자·인계 DTO |
| 현재 판정 | `BACKEND_BASELINE_PRESENTED / CONSUMER_ACK_REQUIRED / PM_DECISION_REQUIRED` |

이 문서는 Web·Mobile 코드를 수정하라는 구현 지시서가 아니다. 두 소비자가 동일한 Backend 계약을 사용하는지 확인하고, PM 결정 전에 차이를 고정하기 위한 ACK 요청서다.

> 2026-08-10 실행 보강: 현재 `main` 계약·Runtime 회귀와 Web 관련 단위
> 테스트는 통과했지만, 한예나·양정현의 사람 회신은 아직 수신하지 않았다.
> 따라서 `CONSUMER_ACK_REQUIRED` 상태는 유지한다.

## 1. 한 문장 결론

Web·Mobile은 canonical Visit 상태 7개와 date-only 일정 계약을 사용한다. `COORDINATING`, `WAITING_COMPLETION`은 canonical Visit 상태가 아니며, 특히 `WAITING_COMPLETION`을 `COMPLETED`로 변환하는 것은 금지한다.

## 2. Source of Truth 우선순위

충돌 시 다음 순서를 따른다.

1. `contracts/codes/visit-statuses.yaml`
2. `contracts/api/components/schemas/visit/VisitSchedule.yaml`
3. `contracts/api/components/schemas/visit/VisitDetail.yaml`
4. `contracts/api/components/schemas/visit/VisitHandoff.yaml`
5. Backend Runtime Serializer·Test
6. Web·Mobile DTO·Mapper
7. Mock·Fixture 표시 값

Mock이나 화면 Label이 계약 상태를 새로 만들 수 없다.

## 3. Canonical Visit 상태

허용 상태는 다음 7개다.

| Visit 상태 | 의미 |
|---|---|
| `ASSIGNING` | 기사 배정 중 |
| `SCHEDULING` | 일정 조율 중 |
| `CONFIRMED` | 방문 확정 |
| `IN_PROGRESS` | 방문 진행 중 |
| `COMPLETED` | 방문 완료 |
| `FOLLOW_UP_REQUIRED` | 후속·재방문 필요 |
| `CANCELLED` | 방문 취소 |

다음 값은 Visit 상태로 전송하거나 저장하지 않는다.

| 값 | 판정 | 처리 |
|---|---|---|
| `COORDINATING` | `NON_CANONICAL` | 실제 계약에서는 `SCHEDULING` 사용 |
| `WAITING_COMPLETION` | `NON_CANONICAL` | `COMPLETED`로 변환 금지, 알 수 없는 Legacy 값으로 처리 |
| `VISIT_SCHEDULING` | Inquiry 상태 | Visit 상태와 혼합 금지 |
| `VISIT_SCHEDULED` | Inquiry 상태 | Visit 상태와 혼합 금지 |
| `COMPLETION_PENDING` | Inquiry 상태 | Visit `COMPLETED`와 동일시 금지 |

`WAITING_COMPLETION`은 완료가 아니다. Mapper가 이를 `COMPLETED`로 바꾸면 미완료 방문을 완료로 표시하고 후속 Action을 잘못 활성화할 수 있다.

## 4. Canonical 일정 DTO

Backend 기준 `VisitSchedule`은 다음 구조다.

```json
{
  "preferred_date": "2026-08-12",
  "confirmed_date": "2026-08-13",
  "schedule_status": "CONFIRMED",
  "synthetic_technician_id": "00000000-0000-4000-8000-000000000001"
}
```

| 필드 | 계약 |
|---|---|
| `preferred_date` | `YYYY-MM-DD` 또는 `null` |
| `confirmed_date` | `YYYY-MM-DD` 또는 `null` |
| `schedule_status` | canonical Visit 상태 7개 중 하나 |
| `synthetic_technician_id` | 합성 기사 Public UUID 또는 `null` |

시간대가 포함된 `scheduledAt` 하나로 두 날짜를 합치지 않는다. Web·Mobile 내부 camelCase는 허용하지만 API JSON은 snake_case 계약을 유지한다.

## 5. 현재 상세·인계 DTO 판정

### 5.1 `VisitDetail`

현재 계약은 일정과 기사 정보를 중첩한다.

```json
{
  "visit_id": "uuid",
  "inquiry_id": "uuid",
  "schedule": {
    "preferred_date": null,
    "confirmed_date": "2026-08-13",
    "schedule_status": "CONFIRMED",
    "synthetic_technician_id": "uuid"
  },
  "technician": {
    "is_synthetic": true,
    "technician_id": "uuid",
    "display_name": "합성 기사",
    "phone": "합성 연락처"
  }
}
```

기사 Visit 목록·상세 GET Runtime은 아직 확정·구현되지 않았다. 따라서 Web·Mobile이 위 상세 계약 또는 소비자 제안 Flat DTO를 기사 Remote 응답으로 임의 확정하면 안 된다.

### 5.2 `VisitHandoff`

기사 인계 후보 필드는 다음과 같다.

```text
product_summary
symptom_summary
action_summary
risk_summary
priority_check_items
consultant_final
```

현재 `VisitHandoff`의 상태는 `G2_PROPOSED_PM_MERGE_APPROVAL`이다. Backend 내부 저장·상담사 Visit 생성 입력에 존재하더라도 기사 공개 목록·상세 Projection으로 승인됐다는 뜻은 아니다.

내부 AI Metadata, 검색 점수, Vector/Chunk 식별자, 원문 전체, 실제 개인정보는 공개 Handoff에 추가하지 않는다.

## 6. 현재 구현 대조

### 6.1 Web `main`

현재 Web의 `visitWriteRepository`는 상담사용 쓰기 경계를 준비했다.

- 방문 검토
- Visit 생성
- 일정 저장
- 방문 확정
- date-only 변환
- `VisitHandoffDto`

이는 기사 Visit 목록·상세 Remote Adapter가 구현됐다는 뜻이 아니다.

### 6.2 Mobile `main`

현재 `main`의 Technician 앱은 실제 로그인 뒤에도 `FakeTechnicianVisitRepository`를 사용한다. Fixture에는 `COORDINATING`이 있고 표시 Mapper에는 `WAITING_COMPLETION`이 남아 있다.

### 6.3 Mobile 후보

`origin/jeonghyun@eb78910`은 실제 로그인 경로를 `BlockedTechnicianVisitRepository`로 바꾸고 Offline Preview에서만 Fake를 사용한다.

이 후보는 Remote/Fake 경계를 고치지만 Legacy 상태를 canonical 값으로 정리하지는 않는다. 따라서 병합과 상태 ACK를 구분한다.

## 7. Backend·DB 잠정 판정

| 항목 | 판정 |
|---|---|
| canonical 상태 7개 | `ACCEPT` |
| 날짜 `YYYY-MM-DD`·null | `ACCEPT` |
| Inquiry 상태와 Visit 상태 분리 | `REQUIRED` |
| `COORDINATING`을 API 값으로 사용 | `REJECT` |
| `WAITING_COMPLETION`을 API 값으로 사용 | `REJECT` |
| `WAITING_COMPLETION → COMPLETED` | `PROHIBITED` |
| `synthetic_technician_id` | 합성 기사 Public UUID로 `ACCEPT` |
| 기사 목록·상세 Route | `DECISION_REQUIRED` |
| 기사 공개 Handoff Projection | `PM_APPROVAL_REQUIRED` |
| Mobile fail-closed 후보 | 별도 문서 기준 `APPROVE_WITH_CONDITIONS` |

## 8. 한예나 Web ACK 요청

다음을 확인해 달라.

1. Web API JSON에서 `preferred_date`, `confirmed_date`, `schedule_status`, `synthetic_technician_id`를 사용한다.
2. 날짜는 `YYYY-MM-DD` 또는 `null`로 처리한다.
3. canonical Visit 상태 7개만 소비한다.
4. Inquiry 상태와 Visit 상태를 별도 Type으로 유지한다.
5. `WAITING_COMPLETION`을 `COMPLETED`로 변환하지 않는다.
6. 미지의 Visit 상태는 완료로 추정하지 않고 오류·알 수 없음으로 처리한다.
7. `VisitHandoff` 공개 범위가 PM 승인되기 전 기사 화면에 임의 필드를 추가하지 않는다.
8. 기사 목록·상세 Runtime 확정 전 Mock을 Remote 성공으로 자동 전환하지 않는다.

Web 회신 형식:

```text
sender=한예나
receiver=최지용
scope=VISIT_STATUS_DTO_ACK

date_only_fields=ACK | CHANGE_REQUEST
canonical_visit_statuses=ACK | CHANGE_REQUEST
inquiry_visit_status_separation=ACK | CHANGE_REQUEST
waiting_completion_to_completed=PROHIBITED_ACK | CHANGE_REQUEST
unknown_status_fail_closed=ACK | CHANGE_REQUEST
visit_handoff_public_boundary=ACK_PENDING_PM | CHANGE_REQUEST
technician_read_mock_fallback=DISABLED_ACK | CHANGE_REQUEST
notes=<추가 의견>
```

## 9. 양정현 Mobile ACK 요청

다음을 확인해 달라.

1. Remote DTO는 canonical Visit 상태 7개만 사용한다.
2. Fixture의 `COORDINATING`은 계약 확정 시 `SCHEDULING`으로 정렬한다.
3. `WAITING_COMPLETION`은 제거하거나 알 수 없는 Legacy 값으로 처리하며 `COMPLETED`로 변환하지 않는다.
4. `scheduledAt` 단일 문자열을 API 계약으로 요구하지 않고 `preferred_date`·`confirmed_date`를 별도 Mapping한다.
5. 실제 로그인·Remote에서는 `BlockedTechnicianVisitRepository`, 사용자 선택 Offline Preview에서만 Fake를 사용한다.
6. 기사 목록·상세 Route와 Response가 확정되기 전 임의 Endpoint·DTO를 Production 코드에 추가하지 않는다.
7. Inquiry Version과 Visit Version이 필요한 쓰기 계약에서는 두 값을 합치지 않는다.

Mobile 회신 형식:

```text
sender=양정현
receiver=최지용
scope=VISIT_STATUS_DTO_ACK

date_only_mapping=ACK | CHANGE_REQUEST
canonical_visit_statuses=ACK | CHANGE_REQUEST
coordinating_to_scheduling=ACK | CHANGE_REQUEST
waiting_completion_to_completed=PROHIBITED_ACK | CHANGE_REQUEST
unknown_status_fail_closed=ACK | CHANGE_REQUEST
remote_fixture_boundary=ACK | CHANGE_REQUEST
technician_read_contract_wait=ACK | CHANGE_REQUEST
dual_version_separation=ACK | CHANGE_REQUEST
notes=<추가 의견>
```

## 10. 김은진 Data·QA 검증 요청

ACK 취합 후 다음을 검증한다.

- Code Registry와 Web·Mobile Enum의 집합 일치
- Legacy 상태가 Remote 성공으로 노출되지 않음
- `WAITING_COMPLETION → COMPLETED` 변환 부재
- date-only 형식과 null 경계
- 합성 기사 Public UUID와 내부 PK 비노출
- Inquiry 상태와 Visit 상태 혼합 부재
- Fake/Remote 자동 전환 부재
- 기사 목록·상세 계약 확정 후 본인 배정·동일 404 Test 가능성

QA 회신 형식:

```text
sender=김은진
receiver=최지용,윤승혁
scope=VISIT_STATUS_DTO_QA

registry_alignment=PASS | FAIL | NOT_RUN
legacy_status_exposure=PASS | FAIL | NOT_RUN
waiting_completion_conversion_absent=PASS | FAIL | NOT_RUN
date_only_boundary=PASS | FAIL | NOT_RUN
identifier_privacy=PASS | FAIL | NOT_RUN
fake_remote_boundary=PASS | FAIL | NOT_RUN
remaining_blockers=<없으면 NONE>
evidence=<명령·결과·경로>
```

## 11. 윤승혁 PM 결정 요청

다음을 최종 결정해 달라.

1. canonical Visit 상태·date-only 계약을 Web·Mobile 공통 기준으로 승인할지
2. 기사 목록·상세 Route와 Operation을 어느 WBS Slice에서 확정할지
3. `VisitHandoff` 6개 필드를 기사 공개 Projection에 포함할지
4. 기사 목록·상세 Response에서 `schedule` 중첩을 유지할지
5. Mobile fail-closed 후보의 `main` 병합과 계약 ACK를 독립 Gate로 진행할지

PM 회신 형식:

```text
sender=윤승혁
receiver=최지용,한예나,양정현,김은진
scope=VISIT_STATUS_DTO_DECISION

canonical_visit_statuses=APPROVE | CHANGE_REQUEST
date_only_schedule=APPROVE | CHANGE_REQUEST
waiting_completion_to_completed=PROHIBITED
technician_read_route=APPROVE_PROPOSAL | HOLD | CHANGE_REQUEST
visit_handoff_public_projection=APPROVE | HOLD | CHANGE_REQUEST
visit_detail_shape=NESTED | FLAT_PROPOSAL_REVIEW | CHANGE_REQUEST
mobile_fail_closed_merge=APPROVE_SEPARATELY | HOLD | CHANGE_REQUEST
contract_owner_apply=APPROVE | HOLD
notes=<결정 근거>
```

## 12. 선후 관계

다음 순서가 도미노 변경을 최소화한다.

```text
Mobile fail-closed PM 병합
→ Web·Mobile ACK 회신
→ Data·QA 정합성 검토
→ PM 상태·DTO·공개 범위 결정
→ Backend OpenAPI·Example·Contract Test 적용
→ 기사 Visit 목록·상세 Runtime 구현
→ 합성 기사·배정 Visit Fixture와 PostgreSQL Smoke
→ Web·Mobile Remote Adapter·Galaxy 검증
```

fail-closed 병합은 안전 조치이므로 ACK 취합 전에 진행할 수 있다. 반대로 기사 실제 Runtime과 소비자 Remote 활성화는 ACK·PM 결정 전에 시작하지 않는다.

## 13. 최종 전달 상태

```text
canonical_visit_status_source=contracts/codes/visit-statuses.yaml
canonical_visit_status_count=7
date_only_schedule=CONFIRMED
waiting_completion_status=NON_CANONICAL
waiting_completion_to_completed=PROHIBITED
current_main_technician_repository=FAKE_IN_REMOTE_PATH
mobile_candidate_remote_behavior=FAIL_CLOSED
web_technician_read_adapter=NOT_IMPLEMENTED
backend_technician_read_runtime=NOT_IMPLEMENTED
visit_handoff_public_projection=PM_APPROVAL_REQUIRED
web_ack=REQUESTED
mobile_ack=REQUESTED
qa_review=WAITING_ACK
pm_decision=REQUESTED
```

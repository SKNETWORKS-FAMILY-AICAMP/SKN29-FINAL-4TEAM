# Technician Visit GET 목록·상세 계약 결정안

> - 작성일: 2026-08-10 KST
> - 작성자: 최지용(Backend·DB)
> - 기준 저장소: `SKN29-FINAL-4TEAM`
> - 기준선: `origin/main@c6848a9ec170db37bdf10a0b46e860ef5677b072`
> - 상태: `PROPOSED / PM_DECISION_REQUIRED / NO_IMPLEMENTATION`
> 소비자: 양정현(Mobile), 한예나(Web), 김은진(Data·QA)

## 1. 문서 목적과 비범위

기사에게 배정된 Visit 목록·상세 GET 2개의 기계 계약을 만들기 전에,
PM이 결정해야 할 최소 항목을 한 번에 제안한다.

이 문서는 다음을 변경하거나 완료로 선언하지 않는다.

- `contracts/api/**` OpenAPI·Schema·Example
- Backend Route·View·Serializer·Service·Repository
- Migration·Seed·Importer·Synthetic Fixture
- Web·Mobile DTO·Remote Repository
- Contract Test·Runtime Test·PostgreSQL Smoke

PM 승인 전 상태는 `DESIGN_PROPOSED`이며 Runtime 착수 승인이 아니다.

## 2. 현재 기준선에서 확인된 사실

| 항목 | 현재 사실 | 판정 |
| --- | --- | --- |
| 사람용 API 문서 | `API-TECH-001/002`가 `/api/v1/technician/visits*`로 등록됨 | `DESIGN_BACKLOG` |
| OpenAPI | 기사 Visit 목록·상세 GET Path 없음 | `NOT_DEFINED` |
| Backend Route | 방문 검토·생성·일정·확정 쓰기 Path만 있음 | `GET_MISSING` |
| Backend 조회 계층 | 기사 목록·상세 View·응답 Serializer·Service·Repository 없음 | `RUNTIME_MISSING` |
| 기존 Visit DTO | `VisitDetail`은 `visit_id`, `inquiry_id`, `schedule`, `technician` 중첩 구조 | 재사용 가능 |
| VisitHandoff | 6개 공개 후보 필드가 있으나 상태가 `G2_PROPOSED_PM_MERGE_APPROVAL` | PM 결정 필요 |
| Mobile | `TechnicianVisitRepository` 인터페이스와 Fake 구현 사용 | Backend 대기 |
| Web | 방문 쓰기 Adapter는 있으나 기사 GET 소비 범위는 아님 | 별도 범위 |

근거:

- `docs/api/waterbridge_api_specification.md:332-340`
- `backend/apps/visits/api/urls.py:14-40`
- `backend/apps/visits/api/views.py:22-105`
- `backend/apps/visits/api/serializers.py:51-106`
- `backend/apps/visits/services/visit_service.py:353-395`
- `backend/apps/visits/repositories/visit_repository.py:16-170`
- `contracts/api/components/schemas/visit/VisitDetail.yaml`
- `contracts/api/components/schemas/visit/VisitSchedule.yaml`
- `contracts/api/components/schemas/visit/VisitHandoff.yaml`

## 3. 추천 Route·operationId

| 구분 | Method·Path | operationId | 권한 |
| --- | --- | --- | --- |
| 배정 Visit 목록 | `GET /api/v1/technician/visits` | `getTechnicianVisitList` | 본인에게 배정된 Visit의 `TECHNICIAN` |
| 배정 Visit 상세 | `GET /api/v1/technician/visits/{visit_id}` | `getTechnicianVisitDetail` | 해당 Visit에 배정된 동일 `TECHNICIAN` |

추천 이유:

- 사람용 API 문서의 `API-TECH-001/002` Path를 유지한다.
- 상담사 조회의 `getConsultantInquiryList/Detail` 명명과 맞춘다.
- 기사 ID를 Query나 Path로 받지 않고 JWT Actor로 범위를 고정한다.

## 4. 목록 Query·Paging 추천안

허용 Query만 전달하고 알 수 없는 Query는 `422`로 거부한다.

| Query | 형식·기본값 | 의미 |
| --- | --- | --- |
| `status` | 상태 코드, 반복 가능 | Visit 상태 다중 필터 |
| `from` | `YYYY-MM-DD`, 선택 | 유효 일정일의 시작일, 포함 |
| `to` | `YYYY-MM-DD`, 선택 | 유효 일정일의 종료일, 포함 |
| `sort` | `SCHEDULE_ASC` 기본 | `SCHEDULE_ASC`, `SCHEDULE_DESC`, `UPDATED_DESC` |
| `page` | 정수, 기본 `1`, 최소 `1` | 1부터 시작하는 Page |
| `size` | 정수, 기본 `20`, `1..100` | Page 크기 |

유효 일정일은 `confirmed_date ?? preferred_date`로 계산한다.
두 날짜가 모두 `null`이면 날짜 필터 적용 시 제외하고, 날짜 미적용 목록에는
포함한다. 일정 정렬에서 날짜 `null`은 마지막에 둔다.

`status_counts`는 Actor·날짜 조건을 적용한 뒤 `status` 필터를 적용하기 전
값으로 계산한다. 범위를 넓힐 수 있는 `technician_id`, 고객명·전화번호 검색,
주소 검색은 P0 Query에서 제외한다.

추천 목록 Wrapper:

```json
{
  "success": true,
  "data": {
    "items": [],
    "page_info": {"page": 1, "size": 20, "total": 0},
    "status_counts": {"SCHEDULING": 0, "CONFIRMED": 0}
  },
  "error": null,
  "metadata": {"correlation_id": "<uuid>"}
}
```

범위를 벗어난 Page는 오류 대신 빈 `items`와 실제 `total`을 포함한 `200`을
반환한다.

## 5. 중첩 DTO 추천안

기존 `VisitDetail`의 `schedule`, `technician` 중첩 구조를 유지하고,
최상위에 임의로 날짜·기사·인계 필드를 펼치지 않는다.

### 5.1 목록 Item

```json
{
  "visit_id": "<visit-public-uuid>",
  "inquiry_id": "<inquiry-public-uuid>",
  "visit_code": "VIS-SYN-0001",
  "versions": {
    "visit_state_version": 2,
    "inquiry_state_version": 8
  },
  "schedule": {
    "preferred_date": "2026-08-12",
    "confirmed_date": "2026-08-13",
    "schedule_status": "CONFIRMED",
    "synthetic_technician_id": "<actor-public-uuid>"
  },
  "handoff_summary": {
    "product_summary": "합성 제품 요약",
    "symptom_summary": "합성 증상 요약",
    "handoff_ready": true
  },
  "updated_at": "2026-08-10T14:00:00+09:00"
}
```

목록에는 조치·위험·상담 최종문 전체를 반복하지 않는다.

### 5.2 상세 Data

```json
{
  "visit": {
    "visit_id": "<visit-public-uuid>",
    "inquiry_id": "<inquiry-public-uuid>",
    "visit_code": "VIS-SYN-0001",
    "versions": {
      "visit_state_version": 2,
      "inquiry_state_version": 8
    },
    "schedule": {
      "preferred_date": "2026-08-12",
      "confirmed_date": "2026-08-13",
      "schedule_status": "CONFIRMED",
      "synthetic_technician_id": "<actor-public-uuid>"
    },
    "technician": {
      "is_synthetic": true,
      "technician_id": "<actor-public-uuid>",
      "display_name": "합성 기사"
    },
    "handoff": {
      "product_summary": "합성 제품 요약",
      "symptom_summary": "합성 증상 요약",
      "action_summary": "고객 조치 요약",
      "risk_summary": "안전 안내 요약",
      "priority_check_items": ["우선 점검 1"],
      "consultant_final": "상담사 최종 확인 내용"
    }
  }
}
```

## 6. VisitHandoff 공개 범위 추천안

상세에 공개할 값은 최신 `CONFIRMED` HandoffReport의 다음 6개로 제한한다.

- `product_summary`
- `symptom_summary`
- `action_summary`
- `risk_summary`
- `priority_check_items`
- `consultant_final`

다음 값은 공개하지 않는다.

- `evidence_summary`, `ai_draft`, `generated_by_ai_run_id`
- 내부 DB PK·원본 Prompt·Model Metadata·검증 내부 결과
- 고객 문의 원문 전체, 계약번호, Serial, 고객 내부 ID
- 다른 상담사·기사의 내부 식별자

확정 인계가 없으면 다른 테이블이나 Mock에서 값을 조합하지 않는다.

- 목록: `handoff_ready=false`까지만 표시
- 상세: `409 VISIT-HANDOFF-01`로 안전하게 중단

## 7. Null·상태 규칙 추천안

| 필드 | Null 규칙 |
| --- | --- |
| `preferred_date` | 고객 희망일 미입력 시 `null` |
| `confirmed_date` | 방문 확정 전 `null`; `CONFIRMED` 이상이면 non-null |
| `schedule_status` | 항상 non-null, Backend Visit 상태 그대로 사용 |
| `synthetic_technician_id` | 기사 전용 GET 성공 응답에서는 non-null이며 Actor UUID와 동일 |
| `technician` | 기사 전용 GET 성공 응답에서는 non-null |
| `handoff_summary` | 목록에서 항상 존재, `handoff_ready`로 준비 상태 표시 |
| `handoff` | 상세 `200`에서는 non-null; 미확정이면 `409` |
| `priority_check_items` | 상세 `200`에서 1개 이상 |

기사 미배정 `ASSIGNING` Visit은 기사 전용 목록·상세에 나타나지 않는다.
`SCHEDULING`은 `confirmed_date=null`일 수 있다. `CONFIRMED`,
`IN_PROGRESS`, `COMPLETED`, `FOLLOW_UP_REQUIRED`는 확정일이 필요하다.

## 8. Privacy·객체 권한 추천안

- JWT Actor는 활성 `TECHNICIAN`이어야 한다.
- Repository 첫 조건을 `technician=actor`로 고정한 뒤 필터를 적용한다.
- 상세의 형식 오류·미존재 UUID, 다른 기사 배정, 미배정, 비활성·비합성 범위는 모두
  본문과 Code가 같은 `404`로 은닉한다.
- 인증 없음·만료는 `401`, 인증됐으나 역할이 다르면 `403`이다.
- P0 응답에 고객명·전화번호·주소는 포함하지 않는다.
- 실제 출동에 고객 연락처·주소가 필요하면 별도 `customer_contact` Projection과
  접근 감사 정책을 PM·Data·QA가 승인한 뒤 확장한다.
- 합성 데이터라도 실제 개인정보와 같은 최소노출 정책을 적용한다.

## 9. Visit·Inquiry Version 추천안

조회 응답은 다음 두 값을 명시적으로 분리한다.

```json
{
  "versions": {
    "visit_state_version": 2,
    "inquiry_state_version": 8
  }
}
```

- `visit_state_version`: Visit 일정·작업 상태의 낙관적 잠금 기준
- `inquiry_state_version`: 전체 문의 State Machine 전이 기준
- GET은 값을 변경하지 않으며 `Idempotency-Key`를 요구하지 않는다.
- 후속 `startVisit`, `completeVisit` 등 쓰기는 두 Version을 모두 검증한다.
- Version 불일치는 `409 STATE-CONFLICT-01` 계열로 처리한다.

## 10. 오류·Correlation 추천안

| HTTP | 추천 의미 |
| --- | --- |
| `200` | 목록·상세 조회 성공 |
| `401` | Token 없음·만료·유효하지 않음 |
| `403` | 인증 사용자가 `TECHNICIAN` 역할이 아님 |
| `404` | 미존재·다른 기사 배정·미배정·비공개 객체의 동일 응답 |
| `409` | 확정 Handoff 부재 또는 읽기 불가능한 상태 정합성 |
| `422` | 허용하지 않은 Query, 잘못된 날짜·Enum·Paging |
| `500` | 내부 오류, 민감 DB·Stack 정보 비노출 |

- 유효한 요청 `X-Correlation-ID` UUID는 이어 쓰고, 없거나 잘못되면 새 UUID를
  발급한다.
- 응답 Header `X-Correlation-ID`, `metadata.correlation_id`, Backend JSON
  Log의 `correlation_id`는 동일해야 한다.
- GET에는 `Idempotency-Key`를 사용하지 않는다.
- 다른 기사 객체인지 알 수 있는 오류 Message·Detail은 반환하지 않는다.

## 11. Synthetic Fixture Blocker

현재 Fixture를 공동 Runtime 완료 증거로 사용할 수 없다.

1. `db-smoke` Visit은 1건이며 이미 `COMPLETED` 상태다.
2. `db-full` Visit 4건은 `TEC-001/002`에 배정돼 있다.
3. Demo Login 계정 `DEMO-TECHNICIAN-001`에는 배정 Visit이 없다.
4. `TEC-001/002`는 현 Demo Login Allowlist와 Prefix를 통과하지 못한다.
5. 기존 Visit Fixture에는 `preferred_date`, `confirmed_date`, Handoff 6개가 없다.
6. Importer도 새 Date-only·HandoffReport 필드를 적재하지 않는다.
7. 기존 `scheduled_at` 일부는 시작·완료보다 늦어 `confirmed_date`로 임의 변환할
   수 없다.

승인 후 김은진(Data·QA)과 최소 다음 사례를 추가·검증해야 한다.

- `DEMO-TECHNICIAN-001`에 배정된 `SCHEDULING` 1건
- 같은 계정에 배정된 `CONFIRMED` 1건
- 다른 합성 기사에게 배정된 same-404 확인용 1건
- `preferred_date`, `confirmed_date`, 최신 `CONFIRMED` HandoffReport
- 공개 Inquiry·Visit·Technician UUID와 양쪽 Version
- 빈 PostgreSQL Import·Replay·Hash·Manifest 재검증

Fixture 수정·DB Import는 이 제안서 승인과 Data Owner 협의 전 시작하지 않는다.

## 12. PM 결정 요청

PM은 각 항목을 `APPROVE`, `CHANGE_REQUEST`, `HOLD` 중 하나로 회신한다.

| ID | 단일 결정권자 | 결정 대상 | 추천안 |
| --- | --- | --- | --- |
| `TVGET-D01` | 윤승혁(PM) | Route·operationId | 3절 승인 |
| `TVGET-D02` | 윤승혁(PM) | 목록 Query·Paging·정렬 | 4절 승인 |
| `TVGET-D03` | 윤승혁(PM) | 기존 중첩 DTO 확장 | 5절 승인 |
| `TVGET-D04` | 윤승혁(PM) | Handoff 공개 6개·미확정 처리 | 6절 승인 |
| `TVGET-D05` | 윤승혁(PM) | Null·상태 조건 | 7절 승인 |
| `TVGET-D06` | 윤승혁(PM) | P0 개인정보 비노출 | 8절 승인 |
| `TVGET-D07` | 윤승혁(PM) | 배정 기사·same-404 권한 | 8절 승인 |
| `TVGET-D08` | 윤승혁(PM) | Visit·Inquiry Version 동시 공개 | 9절 승인 |
| `TVGET-D09` | 윤승혁(PM) | 오류·Correlation | 10절 승인 |
| `TVGET-D10` | 윤승혁(PM) | Synthetic Fixture 정렬 착수 | 11절 승인 후 김은진 검증 |

회신 형식:

```text
TVGET-D01=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D02=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D03=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D04=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D05=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D06=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D07=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D08=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D09=<APPROVE | CHANGE_REQUEST | HOLD>
TVGET-D10=<APPROVE | CHANGE_REQUEST | HOLD>
change_detail=<변경 항목이 있을 때만 작성>
```

## 13. 승인 후 담당자별 순서

1. 윤승혁: `TVGET-D01..D10` 최종 결정
2. 최지용: OpenAPI Path·Schema·Example·Crosswalk 제안 반영
3. 김은진: Contract Test와 Fixture 검증 가능성 확인
4. 최지용: Contract Test 통과 후 Route → View → Response Serializer → Service →
   Repository 순서로 Runtime 구현
5. 김은진·최지용: PostgreSQL Import·권한·same-404·Null·Paging Smoke
6. 양정현: 확정 DTO로 Mobile Remote Repository·Mapper 연결
7. 한예나: 공통 Visit DTO를 소비하는 Web 범위가 있으면 별도 확인

## 14. 완료 Gate

다음 항목이 모두 같은 Commit에서 확인될 때만 `CONSUMER_READY`다.

- PM 결정과 OpenAPI 기계 계약 일치
- Contract Validator·Contract Test PASS
- Backend GET 2개 URL·권한·조회 계층 존재
- 로그인 가능한 Demo 기사와 실제 배정 Fixture 존재
- PostgreSQL 목록·상세 `200`, 다른 기사 객체 동일 `404`
- Date-only·Null·Version·Handoff 공개범위 PASS
- 응답 Header·Wrapper·Log Correlation 일치
- Mobile Remote DTO·Mapper·Unit Test PASS

그 전까지 상태는 `BACKEND_CONTRACT_REQUIRED` 또는
`SHARED_RUNTIME_WAITING`으로 유지한다.

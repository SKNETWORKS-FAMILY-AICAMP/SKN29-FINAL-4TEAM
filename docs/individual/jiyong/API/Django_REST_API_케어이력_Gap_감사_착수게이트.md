# Django REST API 케어 이력 Gap 감사·착수 Gate

- 작성일: 2026-08-10 KST
- 담당: 최지용 — Backend·DB
- 대상: `T-019` 케어 관리
- 감사 기준: 최신 `origin/main 57326cf`
- 판정: `GAP_AUDIT_ONLY / PM_DECISION_REQUIRED / RUNTIME_BLOCKED`

> 이 문서는 `57326cf` 기준의 정적 감사 결과다. 이후 main이 바뀌면
> WBS·계약·Runtime을 다시 대조해야 하며, 이 문서 자체는 WBS 상태
> 변경·Runtime 구현·Migration 승인을 의미하지 않는다.

## 1. 결론

T-019는 **데이터 계층은 준비됐고 공개 API 계층은 비어 있는 상태**다.

- `CareRecord` Model, Migration 2개, Code, Demo Seed와 단위 Test 파일은 있다.
- Care API Path와 DTO는 빈 placeholder다.
- URL·Serializer·View·Repository·Service는 실행 Runtime이 아니다.
- T-018 고객 본인 구독 GET 2개는 구현됐지만, 구독 등록·수정 write는
  계약되지 않았다.
- PM이 아래 9개 결정을 회신하기 전에는 공개 Care Runtime과 새
  Migration을 구현하지 않는다.

## 2. 범위

이번 감사에 포함:

- 고객 제품·구독 기준 케어 이력 목록·상세·등록 후보
- Care Type·Status·Result Code
- 고객 본인 범위와 역할별 접근
- 날짜·구독 상태·중복·멱등 Gap
- AI가 최근 케어 이력을 읽는 Service 경계

포함하지 않음:

- `T-020` 다음 케어 예정일 계산·갱신
- 방문기사 배정·방문 완료 Runtime
- 운영·공유 DB Migration 적용
- PM 승인 전 Endpoint·DTO·RBAC 구현

기준 문서:

- [WBS](../../../planning/md/WBS.md)
- [요구사항정의서](../../../planning/md/요구사항정의서.md)
- [T-018 Runtime 가이드](Django_REST_API_구독_제품조회_Runtime_구현_검증_가이드.md)
- [T-019 Fail-closed Auditor](../../../../scripts/contracts/audit_overdue_backend_runtime_gates.py)

## 3. 현재 상태

| 영역 | 상태 | 근거·판정 |
| --- | --- | --- |
| Care Model | 구현 | [CareRecord](../../../../backend/apps/care/models/care_history.py) |
| Migration | 구현 | [0001](../../../../backend/apps/care/migrations/0001_initial.py), [0002](../../../../backend/apps/care/migrations/0002_add_imported_care_fields.py) |
| Code | 구현 | [Type](../../../../contracts/codes/care-types.yaml), [Status](../../../../contracts/codes/care-statuses.yaml), [Result](../../../../contracts/codes/care-results.yaml) |
| Demo Seed | 구현 | [Seed](../../../../backend/apps/care/management/commands/seed_demo_care_records.py), API 증거는 아님 |
| Care Path | placeholder | [care.yaml](../../../../contracts/api/paths/care.yaml)은 비어 있음 |
| 응답 DTO | placeholder | [CareHistoryItem](../../../../contracts/api/components/schemas/care/CareHistoryItem.yaml)은 비어 있음 |
| URL·View·Serializer | placeholder | [URL](../../../../backend/apps/care/api/urls.py), [View](../../../../backend/apps/care/api/views.py), [Serializer](../../../../backend/apps/care/api/serializers.py) |
| Repository·Service | placeholder | [Repository](../../../../backend/apps/care/repositories/care_history_repository.py), [Service](../../../../backend/apps/care/services/care_history_service.py) |
| OpenAPI·Django 등록 | 미구현 | Care Route 참조·include 없음 |
| RBAC·Example·API Test | 미구현 | 전용 파일·폴더 없음 |

Model·Code·Seed Test 파일이 있다는 사실은 공개 API Runtime 완료 증거가 아니다.

## 4. T-018 선행조건

현재 구현된 읽기 Slice:

- `GET /api/v1/me/subscriptions`
- `GET /api/v1/me/subscriptions/{subscription_id}`

[T-018 계약](../../../../contracts/api/paths/products.yaml)과
Subscription Route·Permission·Repository·Service·Test가 이 두 GET에
대응한다. 그러나 상품 선택, 구독 등록·수정 POST/PUT/PATCH는 없다.

PM 결정이 필요한 지점:

- T-018 write 완료 뒤에만 T-019를 시작할지
- 이미 존재하는 ACTIVE 구독의 케어 이력만 예외적으로 허용할지

결정 전에는 T-018 read 완료를 T-018 전체 완료로 확대하지 않는다.

## 5. 구현 Gap

| Gap | 현재 문제 | 승인 후 필요한 결과 |
| --- | --- | --- |
| Endpoint | 목록·상세·등록 Path·Method 미정 | OpenAPI Operation 확정 |
| DTO | 요청·응답·Query·Error Schema 없음 | 공개 Allowlist와 Example |
| RBAC | 전용 Permission·Object Filter 없음 | 역할·소유권·Hidden 404 |
| Write 정책 | Lifecycle·날짜·Source·Performer 규칙 없음 | Service Guard |
| 중복·멱등 | 업무 Key와 Replay 규칙 없음 | 제약 또는 Idempotency 계약 |
| Test | API·IDOR·write·PG 동시성 증거 없음 | Contract/API/PG Test |
| AI 소비 | 최근 이력 공용 Interface 없음 | 입력·출력·오류 계약 |

추가 관찰:

- `inquiry + visit` 중복 방지 제약은 확인되지 않았다.
- 카트리지 교체·살균을 현재 Code에 어떻게 대응할지 미정이다.
- Demo Product `DEMO-PMD-001`과 T-018 공개 대상
  `WPUJAC104DWH`가 달라 기존 Seed를 공개 E2E 증거로 볼 수 없다.
- `next_care_on` 계산·변경은 T-020이므로 이번 구현에 섞지 않는다.

## 6. Fail-closed Gate

현재 차단 사유:

- `T018_WRITE_SCOPE_NOT_CONTRACTED`
- `CARE_API_CONTRACT_EMPTY`
- `CARE_RUNTIME_STUBS_ONLY`

PM 회신 전 허용:

- `CONTRACT_GAP_INVENTORY`
- `FAIL_CLOSED_READINESS_TESTS`
- `IMPLEMENTED_ROUTE_REGRESSION`
- `EVIDENCE_DOCUMENTATION`

차단 중 금지:

- `PUBLIC_CARE_ENDPOINT_IMPLEMENTATION`
- `NEXT_CARE_DATE_CALCULATION`
- `PUBLIC_QUESTIONNAIRE_ENDPOINT_IMPLEMENTATION`
- `DATABASE_MIGRATION_FOR_BLOCKED_RUNTIME`

## 7. PM 결정 요청 9개

| 번호 | 결정할 내용 |
| ---: | --- |
| 1 | T-018 write 필수 선행 여부 또는 기존 ACTIVE 구독 예외 |
| 2 | 목록·상세·등록의 Path·Method와 구독 하위 중첩 여부 |
| 3 | CUSTOMER·CONSULTANT·OPERATOR·TECHNICIAN read/write 범위 |
| 4 | Request·Response Allowlist, UUID, Query·정렬·페이지·오류 |
| 5 | 생성 Lifecycle, 날짜 조합, Source·Performer 규칙 |
| 6 | 카트리지·살균의 기존 Code 매핑 또는 새 Code |
| 7 | Dedupe·Idempotency Key와 FR-030 중복방지 담당 Task |
| 8 | T-019/T-020 경계와 `next_care_on` 비계산 원칙 |
| 9 | `WPUJAC104DWH` Fixture와 AI 최근이력 Interface |

## 8. 승인 후 작업 순서

1. PM 결정과 담당자를 문서·이슈에 고정한다.
2. Code와 OpenAPI Path·Schema·Error·Example을 확정한다.
3. 빈 계약과 잘못된 권한을 실패시키는 Contract Test를 먼저 작성한다.
4. Permission→Repository→Service→Serializer→View→Route 순으로 구현한다.
5. 계약상 필요할 때만 새 Forward Migration을 작성한다.
6. 목록·상세·등록, 날짜, 구독 상태, IDOR, 중복·재전송을 검증한다.
7. AI 최근이력 Service를 검증하고 김은진 독립 QA를 요청한다.

완료 판정에는 OpenAPI와 Django Route, 실제 Service·Repository,
PostgreSQL 검증, 독립 QA가 모두 필요하다. 이 문서는 테스트·Migration·Seed를
실행하지 않은 정적 감사 문서다.

# 구독·제품·케어 이력 API 구현 가이드

> 관련 업무: 구독·제품 조회와 관리 이력
> 관련 WBS: T-018, T-019, T-020
> 소비자: Customer Mobile·상담사 Web

## 1. 기능 범위

- 고객 본인 구독 목록·상세
- 합성 제품 구독 등록·수정
- 완료된 케어 이력 목록·상세
- 승인된 셀프 케어 결과 저장
- 다음 케어일 계산·재산정과 변경 이력

## 2. 주요 경로

- `backend/apps/subscriptions/**`
- `backend/apps/care/**`
- `backend/apps/care/services/care_cycle_rule_registry.py`
- `backend/apps/catalog/**`
- `contracts/api/paths/products.yaml`
- `contracts/api/paths/care.yaml`
- `backend/tests/api/test_t018_*`
- `backend/tests/api/test_t019_*`
- `backend/tests/unit/care/test_care_cycle_rule_registry.py`
- `backend/tests/integration/test_t020_care_schedule_postgresql.py`

## 3. 권한·데이터 경계

- 고객은 본인 구독·케어 기록만 조회한다.
- 외부 입력은 승인된 합성 제품과 공개 UUID만 허용한다.
- 제품 활성·MVP 지원 여부를 저장 전에 검증한다.
- 내부 가격·원가·고객 식별정보를 Projection에 포함하지 않는다.
- 조회는 Side Effect 없이 수행한다.

## 4. 쓰기·멱등·동시성

동일 고객 Profile과 Subscription을 먼저 잠근 뒤 멱등 레코드를 확인한다.

| 요청 | 기대 결과 |
| --- | --- |
| 동일 Key·동일 Payload | 저장 1회, 동일 Resource Replay |
| 동일 Key·다른 Payload | 409, 패자 Payload 미반영 |
| 서로 다른 Key·중복 활성 제품 | 정확히 1건만 생성 |
| 저장 실패 | 구독·케어·멱등 원장 전체 Rollback |

T-019 셀프 케어 등록은 고객 Profile과 본인 `ACTIVE` 지원 구독을 같은
Transaction에서 잠근다. 같은 Key의 동시 요청은 저장 1건과 Replay 1건,
같은 Key의 다른 Payload는 승자 1건과 409, 서로 다른 Key는 각 케어 이력을
잃지 않고 저장해야 한다.

## 5. 다음 케어일

공식 제품·관리 규칙의 `model`, `care_type`, `interval`, `source`, `version`을
사용한다. 복수 필터 주기를 임의로 한 날짜로 합치지 않는다. 규칙이 확정되지
않으면 계산 결과를 운영 기준으로 승격하지 않는다.

`ApprovedCareCycleRuleRegistry`는 검증·승인된 Entry만 입력받는 내부
Adapter다. 다음 세 값이 완전히 일치할 때만 `CareCycleRule`을 반환한다.

```text
(product_model_code, management_type_code, care_type_code)
```

- 운영 Rule은 `backend/apps/care/policies/approved_care_cycle_rules_v1.json`에
  출처 Identity와 함께 저장하고 Loader가 Fail-closed로 읽는다.
- 같은 Scope의 중복 Entry는 초기화 단계에서 거부한다.
- 모델·관리방식·케어유형이 다르거나 Entry가 없으면 `None`을 반환한다.
- `None`이면 `CONFIRMATION_REQUIRED`, `next_care_on=null`, DB Write 0건이다.
- Exact Match만 기존 월말·윤년·최근 완료 이력 계산기로 전달한다.
- Subscription Row Lock을 잡은 상태에서 Lookup·재산정을 수행한다.

2026-08-18 PM 결정으로 P0 운영 Rule은 다음 한 건만 활성화한다.

```text
WPUJAC104DWH + SELF_MANAGED + FILTER_REPLACEMENT = 4개월
기준일 = 최근 일반 FILTER_REPLACEMENT 완료일, 없으면 구독 시작일
효력일 = 2026-08-18
사용량·수질 = 자동 단축하지 않고 안내만 제공
```

근거는 `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P031`의 Page Text·원본
SHA-256이다. 같은 페이지의 12개월 2단계 필터는 원문에서 삭제하지 않지만,
P0 대표 일정에는 사용하지 않는다. `WPUIAC425SNW`, `WPUIAC606SNW`는 제품
확장 후보일 뿐 모델별 공식 관리 주기가 검증되지 않아 Rule을 등록하지 않는다.

## 6. T-019 검증 Matrix

| Case | 기대 결과 |
| --- | --- |
| PostgreSQL 동시 동일 Key·동일 Payload | `201·201`, 저장 1건, Replay 1건 |
| PostgreSQL 동시 동일 Key·다른 Payload | `201·409`, 승자 Payload만 저장 |
| PostgreSQL 동시 서로 다른 Key | `201·201`, 케어·멱등 원장 각 2건 |
| 타인·비활성·미지원·미존재 구독 쓰기 | 동일 `404`, 저장·멱등 원장 0건 |
| 멱등 응답 저장 직전 실패 주입 | `500`, 케어·멱등 원장 전체 Rollback |
| 내부 예외 문자열 | 공통 오류 응답에 비노출 |

동시성 Case는 각 Thread의 DB Connection을 분리하고 고객 Profile Row Lock
진입점에서 Barrier로 실제 경합시킨다.

## 7. 재현

저장소의 `backend` 디렉터리에서 기본 계약·Runtime 회귀를 실행한다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests\api\test_t019_care_history_contract.py `
  tests\api\test_t019_care_history_runtime.py
```

PostgreSQL 검증은 공유 통합 DB나 RDS 업무 DB가 아닌 폐기 가능한 독립
PostgreSQL과 테스트 DB 생성 권한을 사용한다. 비밀값은 출력하지 않는다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  --ds=config.settings.local `
  tests\api\test_t019_care_history_contract.py `
  tests\api\test_t019_care_history_runtime.py
```

성공 조건은 `21 passed / 0 skipped / 0 failed`와 실제
`connection.vendor=postgresql`이다. 지속 DB에 `migrate --noinput`을
실행하지 않으며 `visits.0005`의 P1 HOLD를 변경하지 않는다.

## 8. 2026-08-17 작성자 검증

- 기준: `main@012f97bae9e85165fdc6a81b6ae7c6db74aa9bd3`
- 변경: T-019 Runtime 테스트와 이 대표 개발문서
- 변경 없음: 생산 Runtime·Schema·Migration·공개 API·State Machine·Data
- T-019 계약·Runtime: `18 passed / 3 skipped / 0 failed`
- T-018·T-019·Care 연관 회귀: `81 passed / 9 skipped / 0 failed`
- 전체 Backend: `1234 passed / 33 skipped / 0 failed`
- Django System Check: Issue 0
- Migration drift: No changes detected
- PostgreSQL 작성자 실행: 로컬 Docker 권한 차단으로 `NOT_RUN`

T-019 Skip 3건은 PostgreSQL Row Lock 전용 Case다. 이를 PASS로 승격하지
않고 김은진 독립 QA Gate로 유지한다.

## 9. 2026-08-17 독립 PostgreSQL QA

- 검증자: 김은진
- 검증 SHA: `ee8b30bdd25429fbba1f3972d08e9be90b301ac0`
- PostgreSQL: `16.14 (Debian 16.14-1.pgdg12+1)`
- 결과: `21 passed / 0 skipped / 0 failed (24.90s)`
- Blocker: 없음

회신 결과는 7장의 PostgreSQL 성공 조건과 일치한다. 따라서 T-019 독립
PostgreSQL QA Gate는 `PASS`로 판정한다. 소비자 연결과 WBS 완료는 기존
PM 결정에 따라 별도 승인을 유지한다.

## 10. 2026-08-17 T-020 Registry·PostgreSQL 검증

- Registry·계산·계약 표적: `17 passed / 1 PostgreSQL 전용 skipped`
- Care·T-018·T-019 연관 회귀: `56 passed / 4 PostgreSQL 전용 skipped`
- PostgreSQL 16 임시 DB 동시 재산정: `PASS`
- 동시 결과: 신규 일정 1건, Replay 1건, 열린 일정 총 1건
- Django System Check·Migration drift: 별도 누적 Gate에서 재확인
- Schema·Migration·공개 API 변경: 없음

임시 DB에는 필요한 의존 Migration과 `visits.0001`까지만 적용했다.
`visits.0005`는 미적용 상태를 확인했고 검증 후 임시 DB를 제거했다.

Registry 골격과 PostgreSQL 작성자 검증은 완료했지만 공식 Rule Dataset과 운영
변경 승인, 독립 QA, 고객 DTO 소비는 외부 Gate다.

## 11. 2026-08-19 T-020 승인 Rule Runtime 구현

### 구현 결과

- 승인 JSON은 Schema·Status·효력일·Exact Scope·출처 SHA를 엄격히 검증한다.
- 승인 전 날짜, 알 수 없는 필드, 비정상 Hash·주기·계약 값은 Fail-closed다.
- `SELF_MANAGED` 구독 생성 시 최근 교체 이력 또는 시작일에서 4개월을 계산한다.
- 고객이 필터 교체를 완료하면 이전 공식 예약을 취소하고 새 예약 1건을 만든다.
- `VISIT_CARE`로 변경하면 기존 공식 예약만 취소하고 `next_care_on`을 동기화한다.
- 동일 멱등 요청은 예약을 추가 생성하지 않으며 응답 날짜도 동일하게 Replay한다.
- 기존 구독 일괄 소급 재산정 Command는 만들지 않았다.
- DB Schema·Migration·공개 API·State Machine·`data/**`는 변경하지 않았다.

### 작성자 검증

| 검증 | 결과 |
| --- | --- |
| Loader·T-018·T-019·T-020 표적 | `55 passed / 9 PG-only skipped` |
| Care·T-018·T-019 연관 회귀 | `97 passed / 10 PG-only skipped` |
| PostgreSQL 16·pgvector 0.8.6 폐기 DB | `43 passed / 0 skipped` |
| Django System Check | Issue 0 |
| Migration drift | No changes detected |
| Diff whitespace | PASS |

PostgreSQL은 공유 DB가 아닌 폐기 컨테이너에서 실행했다. P1 HOLD인
`visits.0005`를 적용하지 않기 위해 Test Schema 생성 모드를 사용했고, 검증 후
컨테이너를 제거했다.

전체 Backend 실행은 `1296 passed / 34 skipped / 5 failed`였다. 실패 5건은
현재 HEAD의 `data/synthetic/fixtures/products.json`이 3건인데 기존
`EXPECTED_FULL_COUNTS["products"]`가 1건인 합성 인계 Importer 기준선
불일치다. 이번 T-020 변경에는 `operations/**`와 `data/synthetic/**`가 없으므로
별도 Baseline 이슈로 분리하며 T-020 PASS로 숨기지 않는다.

### 남은 Gate

- 김은진의 동일 정책값 PostgreSQL/RDS 독립 재검증
- PM의 T-020 WBS 완료 판정
- P1: 4개월·12개월 부품별 일정, 추가 모델별 공식 주기, 공식 사용량 보정식
- T-020 완료 후 T-021 `CARE_PRECHECK` 착수

## 12. 판정

계약·권한·IDOR·멱등·Rollback·PostgreSQL 동시성과 Projection 비노출이
통과하면 구현 완료다. T-020 작성자 Runtime은 완료했으며 독립 QA와 PM WBS
판정만 별도 Gate로 유지한다.

```text
T019_RUNTIME_IMPLEMENTATION=UNCHANGED_EXISTING
T019_AUTHOR_QA_PACKAGE=READY
T019_SQLITE_REGRESSION=PASS
T019_POSTGRESQL_AUTHOR_RUN=NOT_RUN_LOCAL_DOCKER_UNAVAILABLE
T019_POSTGRESQL_INDEPENDENT_QA=PASS
T019_QA_SHA=ee8b30bdd25429fbba1f3972d08e9be90b301ac0
T019_QA_RESULT=21_PASSED_0_SKIPPED_0_FAILED
T019_QA_BLOCKER=NONE
T019_CONSUMER_CONNECTION=PENDING_PM_APPROVAL
T019_WBS_COMPLETION=PENDING_PM
T020_PM_POLICY=APPROVED_2026_08_18
T020_APPROVED_SCOPE=WPUJAC104DWH_SELF_MANAGED_FILTER_REPLACEMENT_4_MONTHS
T020_AUTHOR_RUNTIME=PASS
T020_POSTGRESQL_AUTHOR_RUN=43_PASSED_0_SKIPPED
T020_INDEPENDENT_QA=PENDING
T020_WBS_COMPLETION=PENDING_PM
```

독립 QA 통과는 소비자 연결 또는 윤승혁(PM)의 WBS 완료 승인을 대체하지 않는다.

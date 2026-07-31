# T-005 Wave 6A `support_customer_action_result` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 범위: 고객 자가조치 결과 1개 테이블

## 1. 결과 요약

GuidanceItem 단계에 대해 고객 또는 상담사가 제출한 수행 시도를
append-only 행으로 저장하는 `support_customer_action_result`를 구현했다.
기존
[`customer_action_result.py`](../../../../../backend/apps/inquiries/models/customer_action_result.py)는
“자가조치 수행 여부·증상 변화 Model”이라는 출처 설명만 있고 Django
Model 선언이 없는 빈 stub이었다. 해당 파일을 활성 Model로 완성하고,
기존 `inquiries.0009`는 수정하지 않은 채 새 번호
[`inquiries.0010`](../../../../../backend/apps/inquiries/migrations/0010_customeractionresult.py)으로
직렬 추가했다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Inquiries Migration drift | 통과, `No changes detected` |
| SQLite 집중 테스트 | `14 passed` |
| SQLite 빈 DB `0009→0010→0009→0010` | 전 단계 통과 |
| Inquiry·T-022·T-023 회귀 | `140 passed` |
| T-005 readiness·schema 회귀 | `43 passed` |
| PostgreSQL 집중 테스트 | `14 passed` |
| PostgreSQL Catalog | 11컬럼, bigint PK/FK, UUID, CHECK·UNIQUE·Index 확인 |
| PostgreSQL valid/invalid·PROTECT | 전 항목 통과 |
| PostgreSQL `0010→0009→0010` | 테이블 제거·재생성 통과 |
| 임시 검증 자원 | SQLite 파일·격리 PostgreSQL DB 제거 확인 |

## 2. 기준과 구현 경계

| 우선 | 기준 | 이번 적용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | 한 테이블 Wave, 번호 Migration, 작업 직후 검증, 상대경로 인계 |
| 2 | [식별자 ADR 0010](../../../../adr/0010-t005-three-layer-identifier-bridge.md) | 내부 bigint PK·FK와 공개 UUID 분리 |
| 3 | [멱등성 ADR 0011](../../../../adr/0011-t005-status-history-idempotency-scope.md) | 요청 replay 원장과 도메인 결과 행의 책임 분리 |
| 4 | [Physical Contract v1.2](../../../../database/t-005/t005_physical_contract_v1.2.json) | 최신 식별자·canonical code 공통 정책 |
| 5 | [테이블사전](../../../../database/watercare_table_dictionary.md) | 필드, 시도·멱등 UNIQUE, GuidanceItem 조회 Index, append-only 정책 |
| 6 | [`contracts/codes`](../../../../../contracts/codes/) | `ACTION_RESULT` canonical YAML 부재 확인 |

역사 계약의 UUID `id`, UUID `guidance_item_id`, UUID `submitted_by_id`는
현행 식별자 정책에 따라 내부 bigint로 구현했다. 외부 식별에는 unique
UUID `public_id`를 추가했다. 따라서 역사 10개 필드에 `public_id`가
추가되어 실제 테이블은 11개 컬럼이다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [CustomerActionResult Model](../../../../../backend/apps/inquiries/models/customer_action_result.py) | 식별자, 부모·제출자 FK, 시도·멱등·문자열 구조 무결성 |
| [Inquiries Model export](../../../../../backend/apps/inquiries/models/__init__.py) | Runtime registry에 `CustomerActionResult` 공개 |
| [Inquiries 0010 Migration](../../../../../backend/apps/inquiries/migrations/0010_customeractionresult.py) | `0009_guidanceitem` 직렬 의존, 테이블·제약·Index 생성 |
| [집중 테스트](../../../../../backend/tests/unit/inquiries/test_customer_action_result_model.py) | SQLite/PostgreSQL 무결성·PROTECT·Catalog·왕복 검증 |
| [부모 GuidanceItem 구현서](t005_wave_3c_support_guidance_item_implementation.md) | `support_guidance_item` 식별자와 open `GUIDANCE_ACTION` 경계 |
| [Readiness 회귀](../../../../../backend/tests/unit/database/test_t005_implementation_readiness.py) | 과거 placeholder 가정을 실제 Model 감지로 갱신 |

## 4. Runtime 필드

| 필드 | 물리 구현 | 무결성·기본값 |
| --- | --- | --- |
| `id` | `BigAutoField`, PK | 내부 식별자 |
| `public_id` | UUID | 자동 생성, UNIQUE, 수정 불가 |
| `guidance_item_id` | bigint FK | `support_guidance_item.id`, `PROTECT` |
| `attempt_no` | positive smallint | 기본 1, `> 0` |
| `result_code` | `varchar(40)` | 필수 open code, 비공백 |
| `result_text` | nullable text | 선택 결과 설명 |
| `performed_at` | nullable timestamptz | 의미 계약 승인 전 nullable |
| `customer_comment` | nullable text | 선택 고객 의견 |
| `submitted_by_id` | bigint FK | `accounts_user.id`, `PROTECT` |
| `idempotency_key` | `varchar(128)` | 필수 비공백, 전역 UNIQUE |
| `created_at` | timestamptz | 자동 생성 |

역사 계약에는 `updated_at`이 없고 결과 행은 append-only 시도 이력이므로
공통 `TimestampedModel`을 상속하지 않았다. Model에 `created_at`만
명시해 계약에 없는 수정시각 컬럼을 추가하지 않았다.

## 5. 구조적 DB 무결성

| 제약·Index | 역할 |
| --- | --- |
| `ux_action_result_attempt` | 같은 GuidanceItem의 `attempt_no` 중복 차단 |
| `ux_action_result_idempotency` | 동일 Idempotency-Key 중복 결과 차단 |
| `ck_action_result_attempt` | `attempt_no <= 0` 차단 |
| `ck_action_result_code_nonempty` | 빈 문자열·공백문자 전용 결과 코드 차단 |
| `ck_action_result_idem_nonempty` | 빈 문자열·공백문자 전용 멱등키 차단 |
| `ix_action_result_guidance_item` | `(guidance_item_id, created_at)` 시도 이력 조회 |
| GuidanceItem FK | 존재하는 단계만 참조, 부모 ORM 삭제 차단 |
| SubmittedBy FK | 존재하는 계정만 참조, 제출자 ORM 삭제 차단 |

FK 자동 단독 Index는 `db_index=False`로 만들지 않았다.
`guidance_item_id` 조회는 명시적 시각 Index와 시도 UNIQUE의 선두 컬럼이
지원한다. `submitted_by_id` 단독 Index는 활성 계약 목록에 없으므로
발명하지 않았다.

PostgreSQL Catalog에서 다음을 확인했다.

```text
11 columns
3 explicit structural CHECK constraints
2 application FK constraints
2 domain UNIQUE constraints
5 indexes including PK/public UUID/attempt/idempotency/history lookup
```

## 6. 미승인 코드와 보류 정책

### 6.1 `ACTION_RESULT`

Design Draft에는 `RESOLVED`, `IMPROVED`, `UNCHANGED`, `WORSE`,
`NOT_PERFORMED` 후보가 있지만 이를 확정한 canonical YAML은 없다.
따라서 다음 두 CHECK와 TextChoices를 설치하지 않았다.

```text
ck_support_customer_action_result_result_code_allowed
ck_action_result_performed
```

두 번째 CHECK도 `NOT_PERFORMED`의 의미를 전제로 하므로 단순 구조
CHECK가 아니다. 코드 계약 승인 전 이를 설치하면 미래 open code를
거부하거나 `performed_at` 의미를 잘못 강제할 수 있다.

현재는 미래 코드 `FUTURE_ACTION_RESULT`와 nullable `performed_at`이
저장되며, `result_code` 자체가 비어 있는 경우만 DB가 차단한다.

후속 적용 조건:

1. `contracts/codes/action-results.yaml` OWNER 승인
2. 각 코드의 `performed_at` 필수·금지 의미 승인
3. 기존 open code 탐색·정규화 Data Migration
4. TextChoices, allowed CHECK, 의미 CHECK, API·Seed 회귀를 같은 Wave에 적용

### 6.2 append-only

`policy_action_result_append_only`는 Application Policy다. 이번 Wave는
Model `save()`·`delete()` override나 사용자 정의 DB trigger를 만들지
않았다. 이러한 부분 구현은 QuerySet update, bulk operation, raw SQL을
막지 못한다.

집중 테스트는 SQLite와 PostgreSQL에서 사용자 정의 trigger 부재를
확인한다. 운영 적용 시에는 다음을 함께 구성해야 한다.

- API·Service는 결과 정정을 UPDATE가 아닌 새 `attempt_no` INSERT로 처리
- 운영 DB Role에서 해당 테이블 UPDATE·DELETE 권한 미부여
- 관리자 명령·Importer도 append-only 경로 사용
- 시도 생성과 Idempotency-Key 판정을 한 트랜잭션에서 처리
- 위반 권한·동시 요청 통합 테스트

### 6.3 제출자 역할

계약 설명은 고객 직접 제출 또는 상담사 대리 입력을 허용하지만 역할·대리
입력 사유의 저장 위치는 별도 Audit 정책이다. DB FK는 계정 존재만
보장한다. 허용 역할, 대리 입력 사유, 감사 이벤트는 API·Audit 담당자가
정식 계약을 승인한 후 Service에서 검증해야 한다.

## 7. 멱등성 책임

`idempotency_key`는 결과 테이블에서 UNIQUE이므로 같은 제출 Key가 서로
다른 GuidanceItem에 재사용돼도 DB가 차단한다. HTTP replay·payload hash
충돌의 응답 재사용은 별도
[`WorkflowIdempotencyRecord`](../../../../../backend/apps/workflow/models/idempotency_record.py)가
담당한다.

권장 처리 순서:

```text
HTTP Idempotency-Key 수신
  → workflow request ledger에서 replay/payload 충돌 판정
  → 신규 요청이면 CustomerActionResult INSERT
  → 같은 transaction에서 결과와 응답 ledger 완료
```

이 구분은 도메인 결과 UNIQUE가 HTTP 응답 replay 구현 전체를 대신한다는
오해를 방지한다.

## 8. Migration·DB 반복 검증

Migration 순서는 다음과 같다.

```text
inquiries.0008_guidance
  └─ inquiries.0009_guidanceitem
       └─ inquiries.0010_customeractionresult
```

### SQLite

별도 빈 SQLite 파일에서 `0009→0010→0009→0010`을 실행했다.
첫 적용에서 테이블이 생성되고 rollback에서 제거되며 재적용에서 동일하게
복원됐다. 집중 테스트 14개는 식별자, open code, nonblank, 시도·멱등
UNIQUE, PROTECT, Catalog, trigger 부재와 Migration 왕복을 검증했다.

### PostgreSQL

격리 PostgreSQL DB에서 `0009→0010`, `0010→0009→0010`을 실제
실행했다. 동일 집중 테스트 14개를 PostgreSQL backend에서 재실행해
유효 행, 비공백 위반, 0 시도, 중복 시도, 전역 멱등키 중복, 부모 삭제,
Catalog와 rollback을 검증했다.

검증 후 임시 SQLite 파일과 격리 PostgreSQL DB를 제거하고 부재를
확인했다.

## 9. 작업→검증 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | stub·식별자·테이블사전·code YAML 대조 | 구현/보류 분리 | 한 테이블 범위 확정 |
| 2 | Model·export 작성 | Django check | 0 issues |
| 3 | 번호 Migration 0010 작성 | drift 검사 | 변경 없음 |
| 4 | 집중 테스트 작성 | SQLite | `14 passed` |
| 5 | 빈 SQLite 정·역방향 | `0009→0010→0009→0010` | 통과 |
| 6 | Inquiry·API 회귀 | 단위+T-022+T-023 | `140 passed` |
| 7 | PostgreSQL 적용·Catalog·집중 테스트 | 실제 PG backend | `14 passed` |
| 8 | PostgreSQL rollback·reapply | `0010→0009→0010` | 통과 |
| 9 | Readiness·Schema 회귀 | stale placeholder 기대 수정 후 재실행 | `43 passed` |
| 10 | check·drift·compile·link | 정적·문서 검사 | 전부 통과 |

## 10. 협업 인계

| 역할 | 인계 내용 |
| --- | --- |
| Backend | append-only Service와 request-ledger 연계 트랜잭션 구현 |
| API | 외부 식별자는 `public_id`, 멱등키는 승인된 Header 계약으로 전달 |
| PM·Code Owner | `ACTION_RESULT` 값과 `performed_at` 의미 canonical YAML 승인 |
| Audit | 고객 직접 제출·상담사 대리 입력 actor와 사유를 AuditEvent 계약에 연결 |
| DBA·운영 | INSERT 전용 Role 권한, UPDATE·DELETE 거부 정책 적용 |
| QA | 동시 멱등 요청, 시도 순번 경쟁, raw/bulk 우회, 부모 삭제 회귀 유지 |
| Data·Importer | 기존 open code 정규화 전 allowed CHECK를 선행 배포하지 않음 |

이번 Wave는 `support_customer_action_result` 한 테이블의 Runtime 구현을
완료한 것이다. T-005 전체 완료, API·Serializer·정식 Importer·Seed,
ACTION_RESULT 코드 승인 또는 운영 권한 배포를 포함하지 않는다.

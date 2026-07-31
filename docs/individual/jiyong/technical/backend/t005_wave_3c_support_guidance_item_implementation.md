# T-005 Wave 3C `support_guidance_item` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 범위: 고객 안내 단계 1개 테이블

## 1. 결과 요약

고객 안내 한 버전의 안전한 조치 단계를 순서대로 저장하는
`support_guidance_item`을 `inquiries` App에 구현했다. 선행
[`support_guidance`](t005_wave_2g_support_guidance_implementation.md)의
`inquiries.0008`은 수정하지 않고, 새 번호
[`inquiries.0009`](../../../../../backend/apps/inquiries/migrations/0009_guidanceitem.py)로
직렬 추가했다.

식별자는 내부 `BigAutoField id`와 외부 unique UUID `public_id`로
분리했다. 부모 Guidance는 내부 bigint FK와 Django `PROTECT`로 연결했고,
단계 번호·필수 문자열·부모별 순서 중복처럼 코드 집합과 무관한 구조적
무결성만 데이터베이스에 적용했다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Inquiries Migration drift | 통과, `No changes detected` |
| SQLite 집중 테스트 | `13 passed` |
| SQLite 빈 DB `0008→0009→0008→0009` | 전 단계 통과 |
| Inquiry·T-022·T-023 회귀 | `126 passed` |
| T-005 readiness 회귀 | `6 passed` |
| PostgreSQL 집중 테스트 | `13 passed` |
| PostgreSQL Catalog | 10컬럼, bigint PK/FK, UUID, CHECK·UNIQUE 확인 |
| PostgreSQL 유효·위반 쓰기 | open code 저장 및 비공백·순서·중복 위반 차단 |
| PostgreSQL 부모 삭제 | ORM `ProtectedError` 차단 |
| PostgreSQL `0009→0008→0009` | 테이블 제거·재생성 통과 |
| 임시 검증 자원 | SQLite 파일·격리 PostgreSQL DB 제거 확인 |

## 2. 구현 기준과 충돌 해소

| 우선 | 기준 | 이번 적용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | 한 테이블 Wave, 번호 Migration, 작업 직후 검증, 상대경로 인계 |
| 2 | [식별자 ADR 0010](../../../../adr/0010-t005-three-layer-identifier-bridge.md) | 내부 bigint PK·FK와 공개 UUID 분리 |
| 3 | [Physical Contract v1.2](../../../../database/t-005/t005_physical_contract_v1.2.json) | 최신 식별자·canonical code 우선 정책 |
| 4 | [테이블사전](../../../../database/watercare_table_dictionary.md) | Guidance 단계 필드, 순서 UNIQUE, 구조 CHECK, 승인 후 불변 정책 후보 |
| 5 | [`contracts/codes`](../../../../../contracts/codes/) | `GUIDANCE_ACTION` canonical YAML 부재 확인 |

역사 Snapshot은 UUID `id`와 UUID `guidance_id`를 제시하지만 ADR 0010의
현행 식별자 정책에 따라 내부 PK/FK를 bigint로 전환하고 `public_id`를
추가했다.

테이블사전은 `CHECK`, `CLEAN`, `RESET`, `RESTRICT_USE`,
`CONTACT_SUPPORT` 후보를 제시하지만 이를 확정하는 `GUIDANCE_ACTION`
OWNER_BASELINE YAML은 없다. 따라서 후보 집합을 TextChoices나 allowed
CHECK로 발명하지 않았다. `action_type_code`는 필수 open `CharField`로
두고 공백 전용 값만 구조 CHECK로 막았다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [GuidanceItem Model](../../../../../backend/apps/inquiries/models/guidance_item.py) | 필드, FK, default, UNIQUE와 구조 CHECK |
| [Inquiries Model export](../../../../../backend/apps/inquiries/models/__init__.py) | Runtime registry에 `GuidanceItem` 공개 |
| [Inquiries 0009 Migration](../../../../../backend/apps/inquiries/migrations/0009_guidanceitem.py) | `0008_guidance` 직렬 의존, 테이블·제약 생성 |
| [집중 테스트](../../../../../backend/tests/unit/inquiries/test_guidance_item_model.py) | SQLite/PostgreSQL 공용 무결성·PROTECT·왕복 검증 |
| [부모 Guidance Model](../../../../../backend/apps/inquiries/models/guidance.py) | 버전형 Guidance 부모와 open review 상태 |

선행
[`0008_guidance.py`](../../../../../backend/apps/inquiries/migrations/0008_guidance.py)는
적용 이력을 보존하기 위해 수정하지 않았다.

## 4. Runtime 필드

| 필드 | 물리 구현 | 무결성·기본값 |
| --- | --- | --- |
| `id` | `BigAutoField`, PK | 내부 조인 식별자 |
| `public_id` | UUID | 자동 생성, UNIQUE, 수정 불가 |
| `guidance_id` | bigint FK | `support_guidance.id`, `PROTECT` |
| `step_no` | positive smallint | 필수, `> 0` |
| `action_type_code` | `varchar(40)` | 필수 open code, 비공백 |
| `instruction_text` | text | 필수, 비공백 |
| `caution_text` | nullable text | 선택 주의사항 |
| `requires_confirmation` | boolean | 기본 `true` |
| `created_at` | timestamptz | 자동 생성 |
| `updated_at` | timestamptz | 자동 갱신 |

## 5. DB 무결성

| 제약 | 역할 |
| --- | --- |
| `ux_guidance_item_step` | 같은 Guidance 안에서 `step_no` 중복 차단 |
| `ck_guidance_item_step` | `step_no <= 0` 차단 |
| `ck_guidance_action_nonempty` | 빈 문자열과 공백문자 전용 action code 차단 |
| `ck_guidance_item_instruction` | 빈 문자열과 공백문자 전용 안내문 차단 |
| FK `guidance_id` | 존재하는 Guidance만 참조, 부모 삭제 제한 |

PostgreSQL Catalog에서 확인한 Index는 PK, `public_id` UNIQUE,
`ux_guidance_item_step` 세 개다. `guidance_id` 조회는 복합 UNIQUE의
선두 컬럼으로 지원되므로 중복 단독 FK Index는 `db_index=False`로 만들지
않았다.

`PositiveSmallIntegerField`가 만드는 `step_no >= 0` 보조 CHECK와 명시적
`step_no > 0` CHECK가 함께 존재한다. 실제 허용 범위는 더 엄격한 명시
CHECK가 결정한다.

## 6. 의도적으로 보류한 계약

### 6.1 `GUIDANCE_ACTION` allowed code

다음 제약은 설치하지 않았다.

```text
ck_support_guidance_item_action_type_code_allowed
```

현재 후보값은 Design Draft이며 canonical YAML이 아니다. 집중 테스트는
`FUTURE_GUIDANCE_ACTION`을 실제 저장해 open code 경계를 고정하고,
공백값만 DB가 차단하는지 검증한다.

후속 적용 조건:

1. `contracts/codes/guidance-actions.yaml`의 OWNER 승인
2. API·AI 응답과 DB 저장값 Mapping 승인
3. 기존 open code 탐색·정규화 Data Migration
4. Model TextChoices, DB allowed CHECK, Seed, 회귀 테스트를 같은 Wave에 반영

### 6.2 승인된 Guidance의 항목 불변성

테이블사전의 `policy_guidance_item_approved_immutable`은 부모 Guidance가
`APPROVED`이면 항목 UPDATE·DELETE를 금지하는 Application Policy다.
하지만 부모의 `GUIDANCE_REVIEW_STATUS` canonical YAML도 아직 없으므로
`APPROVED` 리터럴에 의존하는 DB trigger를 만들지 않았다.

집중 테스트는 `support_guidance_item`에 사용자 정의 trigger가 없음을
SQLite와 PostgreSQL에서 확인한다. 이는 승인 안내 변경을 허용한다는
제품 결정이 아니다. 외부 수정 API는 계약 승인 전 공개하지 않고, 승인
후에는 다음 항목을 함께 구현해야 한다.

- Service 트랜잭션 안에서 부모 상태와 권한 확인
- 승인본 수정 대신 새 `guidance_version` 생성
- QuerySet bulk update·raw SQL·관리 명령 우회 차단
- 동시 수정과 승인 경쟁조건 통합 테스트
- 운영 DB UPDATE/DELETE 권한 정책

## 7. Migration과 반복 검증

Migration 순서는 다음과 같다.

```text
inquiries.0007_inquiryqa
  └─ inquiries.0008_guidance
       └─ inquiries.0009_guidanceitem
```

### SQLite

별도 빈 SQLite 파일에서 다음 순서를 실행했다.

```text
0008 → 0009 → 0008 → 0009
```

첫 `0009`에서 테이블이 생성되고 rollback에서 제거되며 reapply에서
동일하게 복원됐다. 집중 테스트 13개는 식별자, default, open code,
비공백, `step_no`, UNIQUE, PROTECT, trigger 부재, Catalog와 Migration
왕복을 검증했다. 검증용 SQLite 파일은 완료 후 제거했다.

### PostgreSQL

격리 PostgreSQL DB에서도 `0008→0009`, `0009→0008→0009`를 실제
실행했다. 동일 집중 테스트 13개를 PostgreSQL backend에서 재실행했다.

Catalog 확인 결과:

```text
10 columns
id bigint
public_id uuid
guidance_id bigint
step_no smallint
requires_confirmation boolean NOT NULL
3 explicit structural CHECK constraints
1 guidance+step UNIQUE constraint
1 guidance FK
3 indexes including PK/UUID/step UNIQUE
```

유효 미래 action code와 `requires_confirmation=false`는 저장됐고,
비공백 위반, 0 단계, 같은 부모의 단계 중복은 `IntegrityError`로
차단됐다. Guidance ORM 삭제는 `ProtectedError`로 차단됐다.
검증 완료 후 전용 격리 PostgreSQL DB를 제거하고 부재를 확인했다.

## 8. 작업→검증 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 계약·부모 0008·canonical code 대조 | 구현/보류 경계 분리 | 한 테이블 범위 확정 |
| 2 | Model·export 작성 | Django check | 0 issues |
| 3 | 번호 Migration 0009 작성 | drift 검사 | 변경 없음 |
| 4 | 구조·open code·PROTECT 테스트 추가 | SQLite 집중 | `13 passed` |
| 5 | 빈 SQLite 정·역방향 | `0008→0009→0008→0009` | 통과 |
| 6 | Inquiry·API 회귀 | 단위+T-022+T-023 | `126 passed` |
| 7 | PostgreSQL 적용·Catalog·집중 테스트 | 실제 PG backend | `13 passed` |
| 8 | PostgreSQL rollback·reapply | `0009→0008→0009` | 통과 |
| 9 | Readiness·check·drift·compile | 회귀·정적 검사 | 전부 통과 |

## 9. 협업 인계

| 역할 | 인계 내용 |
| --- | --- |
| Backend | 항목 생성·수정 Service에서 부모 Guidance 버전과 권한 확인 |
| API | 외부에는 `public_id`를 사용하고 내부 bigint `id`를 노출하지 않음 |
| AI | UsageGuidance 응답의 단계 배열을 DB 필드로 Mapping하는 Adapter 계약 필요 |
| PM·Code Owner | `GUIDANCE_ACTION` 값·의미·전이 및 review 상태 canonical YAML 승인 |
| QA | 같은 Guidance의 순서 중복, 공백값, 부모 삭제, 승인 경쟁조건 검증 유지 |
| 운영·DBA | 상태 계약 승인 전 APPROVED 기반 trigger를 임의 추가하지 않음 |
| 다음 Wave | `support_customer_action_result`는 GuidanceItem PK/FK와 ACTION_RESULT 계약을 먼저 대조한 뒤 별도 Migration으로 구현 |

이번 Wave는 `support_guidance_item` 한 테이블의 Runtime 구현을 완료한
것이며 T-005 전체 완료 선언, API·Serializer·Importer·Seed 또는
`support_customer_action_result` 구현을 포함하지 않는다.

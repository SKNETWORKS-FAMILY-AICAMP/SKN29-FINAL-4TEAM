# Django 계정 PK·UUID·JWT 전환 및 롤백 가이드

> 기준일: 2026-07-30
> 구현 책임: 최지용
> 협업 검증: 김은진(Database·Migration·Seed·QA), 윤승혁(PM·병합 Gate)
> 현재 상태: 구현·작성자 PostgreSQL 검증 완료
> 내부 상태 코드: `IMPLEMENTED_AND_AUTHOR_POSTGRESQL_VERIFIED`
> 독립 완료 Gate: 비작성자의 fresh·populated PostgreSQL 재현과 PM 리뷰
> 적용 원칙: `작업 → 즉시 검증 → 다음 작업`

## 1. 결론과 범위

이 전환 Gate는 Accounts의 과도기 문자열 기본키를 내부 자동 증가 정수
기본키로 전환하고, JWT 사용자 식별자를 공개 UUID 하나로 고정한다.

| 항목 | 전환 전 | 전환 후 |
| --- | --- | --- |
| `accounts_user.id` | `varchar(48)` 문자열 PK | `bigint` 자동 증가 내부 PK |
| `customers_customer_profile.id` | `varchar(48)` 문자열 PK | `bigint` 자동 증가 내부 PK |
| 과거 문자열 ID | PK와 JWT subject로 사용 가능 | `legacy_id`에 보존, API·JWT 식별자로 사용 금지 |
| 공개 사용자 식별자 | `public_id`가 있으나 legacy PK fallback 존재 | `public_id` UUID만 JWT subject로 허용 |
| 업무·시연 코드 | PK와 혼용 가능 | `DEMO-*`·`SYN-*` 전용 업무 필드로 분리 |
| 기존 FK·M2M | 문자열 User/Profile PK 참조 | 같은 관계를 정수 FK로 보존 |

이 작업만으로 T-005 전체가 완료되는 것은 아니다. 다른 계약 테이블,
Seed·Importer 전체 흐름, 최종 PostgreSQL·계약 감사 Gate는 별도 Wave의
완료 증거가 필요하다.

## 2. 적용 기준과 단일 원본

| 구분 | 기준 |
| --- | --- |
| T-005 활성 설계 | [T-005 데이터 설계 패키지](../../../database/t-005/README.md) |
| 물리 스키마 정책 | [Physical Contract v1.2](../../../database/t-005/t005_physical_contract_v1.2.json) |
| 테이블 설명 | [WaterBridge 테이블 명세](../../../database/waterbridge_table_dictionary.md) |
| DB 구현·인계 절차 | [T-005 데이터베이스 스키마 변경 실행 가이드](../데이터베이스/Django_PostgreSQL_스키마_변경_가이드.md) |
| Backend 실행 | [Backend README](../../../../backend/README.md) |
| JWT 설정 | [Django 공통 설정](../../../../backend/config/settings/base.py) |

적용한 핵심 규칙은 다음과 같다.

- 주요 업무 테이블은 내부 자동 증가 정수 PK와 외부 공개 UUID를
  분리한다.
- PostgreSQL 스키마 변경은 수동 SQL이 아니라 Django Migration으로
  재현한다.
- Migration·Model·Runtime 테스트가 모두 확인되기 전에는 완료로
  판정하지 않는다.
- 문서의 링크는 저장소 안 상대경로만 사용하며 개인 PC 경로와
  비밀값을 기록하지 않는다.

## 3. 구현 파일

| 경로 | 변경 내용 |
| --- | --- |
| [User Model](../../../../backend/apps/accounts/models/user.py) | `id`를 `BigAutoField`로 변경하고 nullable·unique `legacy_id` 추가 |
| [CustomerProfile Model](../../../../backend/apps/accounts/models/customer_profile.py) | `id`를 `BigAutoField`로 변경하고 nullable·unique `legacy_id` 추가 |
| [Accounts 0003 Migration](../../../../backend/apps/accounts/migrations/0003_promote_integer_primary_keys.py) | 기존 PK·FK·M2M 무손실 변환, 시퀀스·orphan 검증 |
| [Account Repository](../../../../backend/apps/accounts/repositories/account_repository.py) | UUID가 아닌 JWT subject 즉시 거부, PK fallback 제거 |
| [Authentication Service](../../../../backend/apps/accounts/services/authentication_service.py) | 검증된 UUID subject 기준 Refresh 폐기 의미 명확화 |
| [JWT Authentication](../../../../backend/common/authentication/jwt_authentication.py) | Repository의 UUID-only 사용자 조회 사용 |
| [Accounts Model 테스트](../../../../backend/tests/unit/accounts/test_models.py) | 내부 정수 PK와 `legacy_id` 기본값 검증 |
| [Accounts Auth API 테스트](../../../../backend/tests/unit/accounts/test_auth_api.py) | legacy Access·Refresh 거부와 ORM PK fallback 미호출 검증 |
| [T-017 Readiness 테스트](../../../../backend/tests/unit/accounts/test_t017_readiness.py) | Accounts Migration 개수를 3개로 갱신 |

정수 PK 전환으로 문자열 PK를 직접 주입하던 Inquiry·Consultation·Visit·
Care·Audit·Workflow·Subscription 관련 테스트 Fixture도 자동 정수 PK를
사용하도록 정리했다.

## 4. 최종 식별자 계약

### 4.1 User

| 계층 | 필드 | 용도 | 외부 노출 |
| --- | --- | --- | --- |
| 내부 PK | `accounts_user.id bigint` | ORM 관계·Join·내부 저장 | 금지 |
| 공개 ID | `accounts_user.public_id uuid` | JWT `sub`, API 사용자 식별 | 허용 |
| 과거 ID | `accounts_user.legacy_id varchar(48)` | 전환 추적·감사·문제 분석 | 금지 |
| 업무 ID | `username`, `employee_no` 등 | 로그인 별칭·직원 업무 코드 | 계약별 허용 |

### 4.2 CustomerProfile

| 계층 | 필드 | 용도 | 외부 노출 |
| --- | --- | --- | --- |
| 내부 PK | `customers_customer_profile.id bigint` | 구독 FK·내부 Join | 금지 |
| 공개 ID | `customers_customer_profile.public_id uuid` | 공개 고객 프로필 식별 | 허용 |
| 과거 ID | `customers_customer_profile.legacy_id varchar(48)` | 전환 추적·감사 | 금지 |
| 업무 ID | `customer_no` | 합성 고객 업무 코드 | 계약별 허용 |

신규 User·CustomerProfile은 `legacy_id=NULL`로 생성한다. 이 필드는
0003 이전 문자열 PK를 보존하기 위한 것이며 신규 업무 ID 발급 필드가
아니다.

## 5. `accounts.0003` 변환 알고리즘

Migration은 `atomic=True`를 유지한다. 한 단계라도 실패하면 PK·FK·M2M
변환 전체가 같은 트랜잭션에서 롤백된다.

| 순서 | 처리 | 검증·차단 |
| ---: | --- | --- |
| 1 | User·CustomerProfile에 nullable·unique `legacy_id` 추가 | 기존 행 추가 시 즉시 NOT NULL을 요구하지 않음 |
| 2 | 기존 PK를 문자열 오름차순으로 정렬해 `1..N` 정수 매핑 생성 | 빈 ID, 중복 ID, 이미 숫자인 ID가 있으면 중단 |
| 3 | 기존 PK를 각 행의 `legacy_id`로 복사 | 기존 문자열 추적 키 보존 |
| 4 | User의 모든 inbound FK 제약을 탐색 | hidden 자동 M2M FK도 포함 |
| 5 | `groups`, `user_permissions` through row의 `user_id`를 제자리 변환 | through table과 행을 삭제하지 않음 |
| 6 | User inbound FK 값과 User PK를 같은 매핑으로 변환 | FK와 부모 PK의 대응 유지 |
| 7 | CustomerProfile inbound FK 값과 Profile PK를 같은 방식으로 변환 | Subscription 고객 관계 유지 |
| 8 | PostgreSQL deferred FK event를 `SET CONSTRAINTS ALL IMMEDIATE`로 검증·소진 | pending trigger event가 남은 상태의 DDL 차단 예방 |
| 9 | Django `AlterField`로 User PK와 모든 관련 FK를 `bigint`로 변경 | Django가 FK를 재생성 |
| 10 | Django `AlterField`로 Profile PK와 관련 FK를 `bigint`로 변경 | Subscription FK 포함 |
| 11 | 모든 inbound FK의 orphan 여부 확인 | orphan 1건 이상이면 Migration 실패 |
| 12 | User·Profile 시퀀스를 현재 최대 PK 뒤로 재설정 | 다음 INSERT의 PK 충돌 방지 |

매핑은 기존 문자열 값 자체에서 숫자를 추출하지 않는다. 정렬된 기존
ID 집합을 기준으로 결정적으로 부여하므로 `DEMO-*`, `SYN-*`,
`USR-<UUID_HEX>`가 함께 있어도 같은 입력에서는 같은 결과가 나온다.
외부 소비자는 이 내부 숫자에 의존하면 안 된다.

## 6. PostgreSQL P0 발견과 수정

실제 PostgreSQL 검증에서 SQLite만으로는 드러나지 않는 두 문제가
발견되었다.

| P0 | 증상 | 원인 | 최종 수정 | 재검증 |
| --- | --- | --- | --- | --- |
| 1 | fresh DB의 User `AlterField`에서 `accounts_user_groups` `UndefinedTable` | 0003이 자동 M2M table을 먼저 삭제했지만 Django는 User PK 변경 시 hidden reverse FK를 따라 해당 table의 `user_id` 타입을 변경함 | M2M table을 삭제하지 않고 행을 제자리 remap. hidden M2M FK까지 constraint drop 대상에 포함 | fresh PostgreSQL 전체 Migration 통과, 두 M2M `user_id bigint`, FK 4개 확인 |
| 2 | populated DB의 `support_inquiry` FK 타입 변경에서 `pending trigger events` | deferred FK UPDATE event가 같은 atomic transaction의 후속 DDL 전에 남아 있었음 | remap 검증 후 `SET CONSTRAINTS ALL IMMEDIATE`로 event를 검증·소진 | `initiated_by_id`, `assigned_user_id`가 있는 populated PostgreSQL 전환 통과 |

`atomic=False`로 낮추거나 중간 Commit을 허용하지 않았다. 원자성을
유지한 상태에서 FK event를 먼저 검증한 뒤 DDL을 수행한다.

## 7. 변환 대상 FK·M2M

### 7.1 0003 적용 시점에 실제로 remap되는 User FK

| 참조 테이블 | 컬럼 | 관계 |
| --- | --- | --- |
| `customers_customer_profile` | `user_id` | 고객 프로필의 사용자 |
| `customers_customer_profile` | `deleted_by_id` | 논리 삭제 수행자 |
| `support_inquiry` | `initiated_by_id` | 문의 시작 사용자 |
| `support_inquiry` | `assigned_user_id` | 문의 배정 사용자 |
| `support_consultation` | `consultant_id` | 상담사 |
| `field_service_visit` | `technician_id` | 방문기사 |
| `subscriptions_care_record` | `performed_by_id` | 케어 수행자 |
| `workflow_idempotency_record` | `actor_id` | 멱등 요청 수행자 |
| `workflow_transition_history` | `actor_id` | 상태 전이 수행자 |
| `audit_event` | `actor_id` | 감사 이벤트 수행자 |
| `token_blacklist_outstandingtoken` | `user_id` | Refresh Token 소유자 |

### 7.2 CustomerProfile FK

| 참조 테이블 | 컬럼 | 관계 |
| --- | --- | --- |
| `subscriptions_customer_subscription` | `customer_id` | 구독 소유 고객 프로필 |

### 7.3 자동 M2M

| Through table | 변환 컬럼 | 보존 대상 |
| --- | --- | --- |
| `accounts_user_groups` | `user_id` | User↔Group 행 전체 |
| `accounts_user_user_permissions` | `user_id` | User↔Permission 행 전체 |

`knowledge_ingestion_batch.started_by_id`와
`field_service_visit_result.submitted_by_id`처럼 0003 이후 Migration에서
생성되는 FK는 이미 변경된 `accounts_user.id bigint`를 기준으로 생성된다.
따라서 0003의 데이터 remap 대상은 아니지만 최종 Runtime에서는 정수
FK다.

## 8. UUID-only JWT 전환

[Account Repository](../../../../backend/apps/accounts/repositories/account_repository.py)는
subject를 `UUID`로 파싱하지 못하면 ORM 조회 없이 `None`을 반환한다.
`find_active_by_id()` 이름의 호환 alias도 같은 UUID-only 동작만 수행한다.

| Token `sub` | 결과 |
| --- | --- |
| 유효한 `public_id` UUID, 활성 사용자, 역할 일치 | 인증 성공 |
| `DEMO-USR-*`, `SYN-USR-*`, 과거 `USR-*` 문자열 | 즉시 401 |
| 형식은 UUID지만 존재하지 않거나 비활성 사용자 | 401 |
| UUID 사용자는 존재하지만 Token 역할이 현재 역할과 다름 | 401 |

### 8.1 운영 세션 강제 만료

legacy 문자열 subject로 발급된 Access·Refresh Token은 서명이 유효하고
자연 만료 전이어도 이 변경 적용 즉시 사용할 수 없다. 이는 fallback
제거의 의도된 보안 동작이다.

| 대상 | 운영 조치 |
| --- | --- |
| Web·Mobile | 저장된 Access·Refresh Token을 삭제하고 로그인 화면으로 이동 |
| Backend | legacy subject를 다시 허용하는 임시 fallback을 추가하지 않음 |
| 사용자 안내 | 배포 시점에 “세션 갱신을 위해 다시 로그인” 안내 |
| Refresh blacklist | legacy Refresh는 사용자 UUID 확인 전에 거부되므로 재발급 불가 |
| 정상 UUID 세션 | 사용자 활성 상태와 역할이 유지되면 기존 규칙대로 사용 가능 |

배포 전 Web·Mobile 담당자에게 강제 재로그인 조건을 전달해야 한다.
클라이언트가 401을 무한 Refresh 재시도로 처리하지 않도록 Refresh 1회
실패 후 로컬 세션을 제거해야 한다.

## 9. 작성자 검증 결과

### 9.1 자동 테스트

| 검증 | 최종 결과 |
| --- | --- |
| `makemigrations accounts --check --dry-run` | PASS, Accounts drift 0 |
| Accounts·JWT·T-017·Workflow 집중 회귀 | `43 passed` |
| Inquiry·Consultation·Visit·Care·Audit·Workflow 영향 회귀 | `83 passed` |

### 9.2 SQLite

| 시나리오 | 입력 | 결과 |
| --- | --- | --- |
| fresh 전체 Migration | 빈 격리 SQLite | 전체 Migration PASS, User·Profile `INTEGER`, FK 위반 0 |
| populated 전환 | 문자열 User 2, Profile 1, Inquiry FK 2, Group M2M, Subscription | `legacy_id`·FK·M2M 보존, 신규 sequence 정상, FK 위반 0 |

### 9.3 PostgreSQL 16.14

검증용 격리 DB만 생성하고 기존 `watercare` DB는 변경하지 않았다. 검증
후 작성자가 만든 격리 DB는 삭제했다.

| 시나리오 | 입력·확인 | 결과 |
| --- | --- | --- |
| fresh 전체 Migration | 빈 DB에서 latest까지 적용 | PASS |
| fresh 물리 타입 | User·Profile PK, 두 M2M `user_id` | 모두 `bigint` |
| fresh M2M 제약 | Group·Permission through table FK | FK 4개 |
| populated 기본 관계 | 문자열 User·Profile, Subscription, Blacklist, Group·Permission | 전부 보존 |
| populated Inquiry | `initiated_by_id`, `assigned_user_id`가 있는 문의 | pending trigger 없이 PASS |
| populated 신규 INSERT | 전환 후 User·Profile 추가 | 최대 기존 PK 다음 값 발급 |
| populated 후 latest | 0003 이후 전체 Migration과 `migrate --check` | PASS |

검증 데이터에는 실제 개인정보·Token·비밀값을 사용하지 않았다.

## 10. 독립 재현 Gate

작성자 검증과 별개로 비작성자가 같은 Commit에서 다음 두 경로를
독립 재현해야 팀 완료 증거가 된다.

| 우선순위 | 역할(담당자) | 재현 | 필수 증거 |
| ---: | --- | --- | --- |
| P0 | Data·QA(김은진 또는 지정 검증자) | 빈 격리 PostgreSQL 전체 Migration | 명령 Exit code, 0003 PASS, 최종 `bigint` 타입 |
| P0 | Data·QA(김은진 또는 지정 검증자) | pre-0003 문자열 PK·Inquiry FK·M2M 행을 넣은 populated 전환 | legacy ID·FK·M2M 보존 결과, 신규 sequence |
| P0 | PM·병합 Gate(윤승혁) | Migration·JWT breaking change 리뷰 | 승인 PR 또는 결정 기록 |
| P1 | Web·Mobile 담당 | legacy Token 401 처리와 재로그인 | Refresh loop 0, 로그인 복귀 확인 |

독립 populated 검증에서는 0003 이후 Model을 pre-0003 Schema에 직접
사용하면 안 된다. `MigrationExecutor`의 historical app state를 사용해
문자열 PK 행을 만든 뒤 0003을 적용해야 한다.

## 11. 배포 순서

| 순서 | 작업 | 중단 조건 |
| ---: | --- | --- |
| 1 | 대상 Commit과 전체 변경 범위 고정 | 다른 Migration이 계속 변경 중이면 중단 |
| 2 | Backend·Importer·Job Writer 중지 | Accounts 관련 write가 남아 있으면 중단 |
| 3 | PostgreSQL 백업과 복구 가능 여부 확인 | 검증된 백업이 없으면 중단 |
| 4 | `migrate --plan` 검토 | 0003 순서·의존성이 예상과 다르면 중단 |
| 5 | Migration 적용 | 오류 시 서비스 재기동 금지 |
| 6 | `migrate --check`, FK·M2M·sequence Smoke | 하나라도 실패하면 서비스 개방 금지 |
| 7 | Backend 기동과 UUID 로그인 Smoke | legacy fallback이 보이면 중단 |
| 8 | Web·Mobile 강제 재로그인 확인 | Refresh 무한 반복 시 배포 완료 금지 |

기존 DB에 적용할 때는 Migration 실행 중 write를 허용하지 않는다.
PK와 여러 FK를 한 트랜잭션에서 바꾸므로 짧은 점검 시간과 명시적
서비스 중지가 필요하다.

## 12. Rollback 원칙

0003의 핵심 `RunPython`에는 단순 reverse가 없다. 다음 이유로
`migrate accounts 0002`를 안전한 롤백 명령으로 제공할 수 없다.

| 이유 | 위험 |
| --- | --- |
| 전환 후 신규 행은 `legacy_id=NULL` | 문자열 PK를 복원할 값이 없음 |
| 전환 후 FK·M2M 행이 추가·변경될 수 있음 | 과거 문자열 매핑으로 완전 복원 불가 |
| PostgreSQL identity·sequence가 새 PK를 발급 | 과거 ID 공간과 일대일 대응하지 않음 |
| 여러 도메인 FK와 hidden M2M FK가 함께 변경됨 | 일부 table만 reverse하면 orphan·타입 불일치 발생 |
| legacy JWT fallback도 동시에 제거됨 | DB만 되돌리거나 코드만 되돌리면 인증 계약이 어긋남 |

### 12.1 허용하는 복구 방식

| 시점 | 복구 방식 |
| --- | --- |
| 배포 전 검증 실패 | atomic rollback 확인 후 원인 수정, 같은 DB에 수동 보정 금지 |
| 운영 반영 직후 치명적 실패 | 서비스 중지 후 **Migration 전 전체 DB 백업**과 대응 코드 버전을 함께 복원 |
| 이미 새 데이터가 유입된 뒤 | 데이터 영향 분석 후 새 Forward Migration 작성 |
| PM `main` 병합 후 | 기존 0003 수정·삭제 금지, 후속 Migration으로 수정 |

이전 애플리케이션 이미지만 되돌리고 정수 PK DB를 그대로 두는 방식은
허용하지 않는다. 이전 코드는 문자열 PK를 기대하므로 코드와 DB를 같은
시점으로 복원해야 한다.

## 13. 인계 사항

| 역할(담당자) | 전달 내용 | 다음 행동 | 완료 증거 |
| --- | --- | --- | --- |
| Data·QA(김은진) | 0003 알고리즘, FK·M2M 목록, fresh·populated 검증 기준 | 독립 PostgreSQL 재현과 전체 QA | 실행 로그·타입·보존 결과 |
| PM·병합 Gate(윤승혁) | 내부 PK breaking change, 비가역 Rollback, JWT 세션 만료 | 리뷰·병합·배포 시점 결정 | 승인 기록과 기준 SHA |
| Web(한예나) | Web legacy Token 401 처리 | Token 제거 후 로그인 복귀 | Refresh loop 없는 화면 검증 |
| Mobile(양정현) | Mobile legacy Token 401 처리 | Token 제거 후 로그인 복귀 | 재로그인 동작 검증 |
| 데이터·Importer 담당 | Accounts PK를 외부 업무 ID로 사용 금지 | `public_id`·업무 코드를 기준으로 Upsert | 정수 PK 직접 의존 0건 |

외부 계약에는 내부 `id`를 추가하지 않는다. `legacy_id`도 전환 추적용
내부 필드이므로 Serializer·JWT·로그에 새로 노출하지 않는다.

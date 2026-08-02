# ADR 0010: T-005 3계층 식별자와 Auth 전환

> 기계 상태: `OWNER_BASELINE_ACCEPTED`
>
> 현재 해석: `ACTIVE_IMPLEMENTED` — 전환 브리지 완료, 공식 검토 Gate 대기
>
> 결정일: 2026-07-28
>
> 초기 결정 책임: Backend·Database 담당(T-005)
>
> 적용 범위: `T005_PRIMARY_KEY_POLICY`
>
> 선행 결정: [ADR 0008](0008-t005-data-contract-decisions.md)
>
> 결정 당시 계약:
> [Physical Contract v1.1](../database/t-005/t005_physical_contract_v1.1.json)
>
> 현재 활성 계약:
> [Physical Contract v1.3](../database/t-005/t005_physical_contract_v1.3.json)

## 1. 배경

공통 개발 규칙은 주요 업무 테이블의 식별자를 세 계층으로 분리한다.

1. 데이터베이스 내부 조인용 자동 증가 정수 PK
2. 외부 API·JWT용 `public_id` UUID
3. `DEMO-*`, `SYN-*`와 같은 업무·시연 코드

ADR 0008의 최초 `T005_PRIMARY_KEY_POLICY`는 세 책임을 하나의 최대
48자 문자열 PK로 합쳤다. Accounts와 JWT가 이 문자열을 사용하던
상태에서 PK 타입을 즉시 바꾸면 Django Auth·SimpleJWT blacklist
참조와 기존 Token을 함께 깨뜨릴 수 있어 단계적 전환을 결정했다.

## 2. 결정

ADR 0008의 여섯 결정 중 `T005_PRIMARY_KEY_POLICY`만 다음 값으로
대체한다.

`INTERNAL_BIGINT_PK_PUBLIC_UUID_BUSINESS_CODE`

- 주요 업무 테이블의 `id`는 `BigAutoField`를 사용한다.
- 외부 API와 JWT에는 내부 `id`를 노출하지 않고 UUID `public_id`를
  사용한다.
- 사람이 읽거나 Seed에서 재사용하는 값은 `inquiry_code`,
  `customer_no`, `username` 등 별도 업무 필드에 둔다.
- `DEMO-*`, `SYN-*` 값은 PK로 새로 발급하지 않는다.
- 내부 FK는 내부 정수 PK를 참조한다.
- 기존 문자열 값은 `legacy_id`에 반입 호환 목적으로만 보존하며
  Public 응답이나 JWT subject로 사용하지 않는다.

ADR 0008의 사용 안내, 방문 일정, 코드 집합, Enum·Seed 결정은 계속
유효하다.

## 3. 결정 당시 전환 계획

전환은 다음 순서로 설계됐다.

1. `accounts_user`와 `customers_customer_profile`에
   `public_id UUID UNIQUE NOT NULL`을 additive Migration으로 추가한다.
2. 신규 JWT `sub`와 로그인·`/me` 응답 ID를 `public_id`로 전환한다.
3. 기존 문자열 `sub`는 Refresh 최대 수명 동안 Backend 조회 경계에서만
   한시적으로 허용한다.
4. 업무 코드 기준 Seed Upsert로 PK 직접 주입을 제거한다.
5. 참조 FK를 검증한 뒤 문자열 PK를 `BigAutoField`로 전환한다.
6. 전환 검증 후 Legacy JWT fallback을 제거한다.

이 절은 당시의 안전한 전환 순서를 보존한다. 현재 Runtime이 여전히
브리지 단계라는 뜻은 아니다.

## 4. 현재 구현 결과

| 항목 | 현재 상태 | 근거 |
| --- | --- | --- |
| `accounts_user.id` | `BigAutoField` | [User Model](../../backend/apps/accounts/models/user.py) |
| `customers_customer_profile.id` | `BigAutoField` | [CustomerProfile Model](../../backend/apps/accounts/models/customer_profile.py) |
| 외부 식별자 | 두 Model 모두 `public_id` UUID | Model·Physical Contract v1.3 |
| Legacy 문자열 | nullable `legacy_id`, 반입 호환 전용 | Model·Migration |
| JWT `sub` | `public_id` UUID | [Django 설정](../../backend/config/settings/base.py)·[AccountRepository](../../backend/apps/accounts/repositories/account_repository.py) |
| Legacy JWT fallback | 제거됨(`false`) | Physical Contract v1.3·Auth 회귀 |
| 전환 Migration | 적용 가능한 단계형 PK 전환 | [0003 Migration](../../backend/apps/accounts/migrations/0003_promote_integer_primary_keys.py) |

활성 계약의 `compatibility_bridge.status`는 `COMPLETE`다. 기술 구현은
완료됐지만 비작성자 독립 재현·외부 검토·PM 계약 승인은 별도 공식
완료 Gate로 남는다.

## 5. 호환성과 제외 범위

- 역할 코드는 `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR`를
  유지한다.
- JWT 알고리즘, 설정 기반 Access·Refresh TTL, rotation과 blacklist
  정책은 이 결정으로 바꾸지 않는다.
- `legacy_id`는 재발급·API 노출·JWT fallback 용도가 아니라 과거
  데이터 반입 추적용이다.
- 역사 Snapshot인 `watercare_schema_v3.json`과 기존 ERD는 수정하지
  않는다.
- `contracts/state-machine/**`는 이 결정의 수정 범위가 아니다.

## 6. 검증

- 신규 Access·Refresh JWT `sub`가 UUID인지 확인한다.
- Legacy 문자열 `sub` Access·Refresh가 거부되는지 확인한다.
- 내부 PK와 `legacy_id`가 Public 응답에 노출되지 않는지 확인한다.
- 역할 변경과 비활성 사용자 재검증이 유지되는지 확인한다.
- Demo Seed와 데이터 Import를 두 번 실행해 중복이 없는지 확인한다.
- 빈 PostgreSQL에서 전체 Migration과 Model·Migration parity를
  검증한다.

대표 회귀:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\accounts\test_auth_api.py -q -p no:cacheprovider
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\database\test_t005_schema_validator.py -q -p no:cacheprovider
```

## 7. 변경 원칙

식별자 정책을 다시 바꾸면 새 ADR과 additive Migration으로 이력을
남긴다. 내부 PK·공개 UUID·업무 코드 중 어느 계층을 바꾸는지 명시하고
Auth, API Schema, Seed·Importer와 PostgreSQL 재현을 함께 검증한다.

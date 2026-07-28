# ADR 0010 — T-005 3계층 식별자와 Auth 호환 브리지

- 상태: `OWNER_BASELINE_ACCEPTED`
- 결정일: `2026-07-28`
- 결정자: 최지용
- 적용 범위: `T005_PRIMARY_KEY_POLICY`
- 선행 문서: [ADR 0008](0008-t005-data-contract-decisions.md)
- 구현 계약: [T-005 Physical Contract v1.1](../database/t-005/t005_physical_contract_v1.1.json)

## 1. 배경

상위 공통 개발 규칙은 주요 업무 테이블에 다음 세 식별자를 분리하도록
정한다.

1. 데이터베이스 내부 조인용 자동 증가 정수 PK
2. 외부 API용 `public_id` UUID
3. `DEMO-*`, `SYN-*` 등의 업무·시연 코드

ADR 0008의 `T005_PRIMARY_KEY_POLICY`는 세 값을 하나의 최대 48자 문자열
PK로 합쳤다. 실제 Accounts 구현과 JWT `sub`도 이 문자열 PK를 사용하고
있으므로, 즉시 PK 타입을 바꾸면 기존 Access·Refresh Token과
SimpleJWT blacklist 원장의 참조가 동시에 깨질 수 있다.

## 2. 결정

ADR 0008의 여섯 결정 중 `T005_PRIMARY_KEY_POLICY`만 다음 값으로
대체한다.

`INTERNAL_BIGINT_PK_PUBLIC_UUID_BUSINESS_CODE`

- 신규 주요 업무 테이블의 `id`는 `BigAutoField`를 사용한다.
- 외부 API에는 내부 `id`를 노출하지 않고 UUID `public_id`를 사용한다.
- 사람이 읽거나 Seed에서 재사용하는 값은 `inquiry_code`,
  `customer_no`, `username` 등 별도 필드에 둔다.
- `DEMO-*`, `SYN-*` 값은 PK로 새로 발급하지 않는다.
- 내부 FK는 원칙적으로 내부 정수 PK를 참조한다.

ADR 0008의 사용 안내, 방문 일정, 코드 집합, Enum·Seed 결정은 그대로
유효하다.

## 3. Accounts 전환 브리지

기존 `accounts_user.id`와 `customers_customer_profile.id`의 문자열 PK는
이번 Migration에서 제거하거나 타입을 변경하지 않는다.

1. 두 테이블에 `public_id UUID UNIQUE NOT NULL`을 additive Migration으로
   추가한다.
2. 신규 JWT의 `sub`에는 `User.public_id`를 기록한다.
3. 전환 전에 발급된 문자열 `sub`는 Refresh Token 최대 수명인 7일 동안
   Backend 조회 경계에서만 fallback으로 허용한다.
4. `/me`와 로그인 응답의 사용자 `id`에는 `public_id`를 직렬화한다.
5. Demo Seed는 `User.username`과 `CustomerProfile.customer_no`로
   Upsert하며 PK 값을 직접 주입하지 않는다.

문자열 PK는 이 브리지 기간에 외부로 노출하지 않는 legacy 내부 키다.
브리지는 정수 PK 전환 완료를 의미하지 않는다.

## 4. 완료 게이트

다음 항목이 남아 있는 동안 T-005 식별자 Runtime은 완료로 표시하지
않는다.

- `accounts_user.id`의 자동 증가 정수 PK 전환
- `customers_customer_profile.id`의 자동 증가 정수 PK 전환
- Accounts를 참조하는 Django Auth·SimpleJWT FK의 Migration 검증
- legacy 문자열 JWT `sub` fallback 제거
- 빈 PostgreSQL Migration과 Seed 2회 재실행 검증

Physical Contract의 OWNER 설계 기준선 확정과 위 Runtime 완료 게이트는
서로 다른 상태다.

## 5. 호환성과 제외 범위

- 역할 코드는 `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR`를
  유지한다.
- JWT 알고리즘, Access 60분, Refresh 최초 발급 기준 7일, rotation과
  blacklist 정책은 바꾸지 않는다.
- 역사 Snapshot인 `watercare_schema_v3.json`과 기존 ERD는 수정하지
  않는다.
- `contracts/state-machine/**`는 이 결정의 수정 범위가 아니다.
- Accounts 문자열 PK의 완전한 교체는 별도 후속 Migration으로 수행한다.

## 6. 검증

- 새 JWT `sub`가 UUID인지 확인한다.
- legacy 문자열 `sub` Access·Refresh Token이 브리지에서 동작하는지
  확인한다.
- 역할 변경과 비활성 사용자 재검증이 기존과 동일하게 유지되는지
  확인한다.
- Demo Seed를 두 번 실행해 계정·프로필 중복이 없는지 확인한다.
- T-005 검증 결과에 `three_layer_identifier_runtime_complete` 미완료
  게이트가 명시되는지 확인한다.

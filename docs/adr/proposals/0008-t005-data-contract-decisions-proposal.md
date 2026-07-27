# ADR 제안 0008: T-005 데이터 계약 결정 패킷 (보관본)

> status: `SUPERSEDED`
> 작성일: 2026-07-25
> OWNER: 최지용
> 대상 WBS: `T-005`
> 대체일: 2026-07-26
> 현재 기준: [`ADR 0008: T-005 데이터 계약 OWNER 기준선`](../0008-t005-data-contract-decisions.md)

> **보관 안내**
> 아래 `PENDING`, 승인표와 승인 후 순서는 2026-07-25 당시 검토 이력이다.
> 현재 구현 착수나 ERD·테이블 명세·API 명세 작성의 차단 조건으로
> 사용하지 않는다. 최지용 OWNER 기준선은 위 ADR 0008과
> `t005_physical_contract_v1.0.json`에서 이미 확정됐다.

## 1. 목적

T-005 데이터 설계의 구조 검증은 완료됐지만 물리 계약과 공통 코드에는 여섯 개의 결정이 남아 있다. 이 문서는 선택지, OWNER 권고안, 영향 파일과 승인란을 한곳에 모아 팀 검토를 빠르게 하기 위한 제안서다.

이 문서의 권고는 확정값이 아니다. 승인란이 채워지고 상태가 별도 승인 ADR에서 `ACCEPTED`로 변경되기 전에는 Django Model·Migration·PostgreSQL 스키마·공통 Enum을 생성하거나 확정하지 않는다.

## 2. 기준 자료

별도 표기가 없는 경로는 `SKN29-FINAL-4TEAM/` 저장소 루트 기준이다.

- `docs/planning/md/WBS.md`
- `docs/database/t-005/README.md`
- `docs/database/t-005/t005_logical_contract_v0.2.json`
- `docs/database/t-005/watercare_schema_v3.json`
- `contracts/codes/usage-guidance-statuses.yaml`
- `contracts/codes/visit-statuses.yaml`
- [공통 개발 규칙](<../../planning/md/공통 개발 규칙.md>)

## 3. 결정 요약

| ID | 선택지 | OWNER 권고 후보 | 승인 상태 |
| --- | --- | --- | --- |
| `T005_PRIMARY_KEY_POLICY` | 도메인형 문자열 ID 중앙 발급 / 호출자 제공 후 검증 / UUID 유지와 외부 표시 ID 병행 | 공통 규칙에 맞춘 도메인형 문자열 ID와 단일 발급 컴포넌트를 우선 검토하되 접두사·길이·충돌 정책은 팀 결정 | `PENDING` |
| `T005_USAGE_GUIDANCE_PHYSICAL_MAPPING` | canonical 필드로 rename / legacy 필드 유지 후 매핑 / 전환 기간 dual field | 신규 물리 계약은 `usage_guidance_status`를 canonical로 사용하고 v3 Snapshot은 이력으로 보존하는 안을 우선 검토 | `PENDING` |
| `T005_USAGE_GUIDANCE_CODESET` | `NORMAL` / `USE_ALLOWED` / canonical-legacy 매핑 유지 | 화면 계약의 `NORMAL`을 canonical 후보로 두고 `USE_ALLOWED`를 legacy 입력 매핑으로만 처리하는 안을 우선 검토 | `PENDING` |
| `T005_VISIT_STORAGE_MAPPING` | 날짜 3필드 분리 / 기존 시작·종료 DateTime 유지 / 두 구조 병행 | `preferred_date`, `confirmed_date`, `schedule_status`를 업무 필드로 분리하고 상세 작업 시간은 별도 필드로 두는 안을 우선 검토 | `PENDING` |
| `T005_VISIT_STATUS_CODESET` | `FOLLOW_UP_REQUIRED` 포함 / 후속 여부 별도 속성·이벤트 / 기존 6개 유지 | 화면에서 후속 방문을 독립 상태로 처리해야 하는지 State Machine과 함께 검토한 뒤 포함 여부를 결정 | `PENDING` |
| `T005_ENUM_SEED_POLICY` | 애플리케이션 상수+스크립트 / DB Enum+Fixture / 코드 테이블+Upsert | MVP 변경 비용을 고려해 애플리케이션 Enum과 재실행 안전한 Seed 스크립트를 우선 비교하되 공통 규칙의 보류 상태를 유지 | `PENDING` |

## 4. 결정별 검토 상세

### 4.1 `T005_PRIMARY_KEY_POLICY`

검토 질문:

- 사용자·제품·문의·방문별 접두사를 어떤 문서에서 관리할 것인가?
- ID를 Backend 한곳에서 발급할지, Seed 입력도 허용할지?
- 동시 발급 충돌과 재시도 시 동일 ID 보장은 어떻게 처리할지?
- 기존 UUID Snapshot은 이력으로만 보존할지, 내부 키로 병행할지?

영향 파일:

- `docs/database/t-005/t005_logical_contract_v0.2.json`
- `backend/common/validators/identifiers.py`
- `backend/apps/*/models/*.py`
- `contracts/api/components/schemas/`
- `data/synthetic/`
- 신규 Django Migration

### 4.2 `T005_USAGE_GUIDANCE_PHYSICAL_MAPPING`

검토 질문:

- `support_inquiry.usage_guidance_code`를 rename할지 신규 필드를 만들지?
- `support_symptom_assessment`에도 동일 canonical 이름을 적용할지?
- legacy 데이터 변환과 rollback 기준은 무엇인지?

영향 파일:

- `docs/database/t-005/watercare_schema_v3.json`은 이력으로 보존
- 신규 물리 스키마 명세
- `backend/apps/inquiries/models/`
- `contracts/codes/usage-guidance-statuses.yaml`
- `contracts/api/`
- `contracts/ai/`

### 4.3 `T005_USAGE_GUIDANCE_CODESET`

검토 질문:

- 고객 화면, API, AI Schema와 DB가 사용할 단일 canonical 값은 무엇인지?
- legacy 값이 들어오면 거부할지 canonical 값으로 변환할지?
- 네 가지 사용 안내 시나리오의 인수 기준과 고객 문구가 같은 의미인지?

영향 파일:

- `contracts/codes/usage-guidance-statuses.yaml`
- `contracts/codes/allowed-use.yaml`
- `contracts/api/`
- `contracts/ai/`
- `tests/contract/`
- 합성 문의·인수 데이터

### 4.4 `T005_VISIT_STORAGE_MAPPING`

검토 질문:

- `preferred_date`와 `confirmed_date`를 날짜로 저장할지 시간대가 있는 시각으로 저장할지?
- 기존 `scheduled_start_at`, `scheduled_end_at`은 실제 작업 창으로 별도 유지할지?
- 일정 변경 이력의 원본과 현재값을 각각 어디에 저장할지?

영향 파일:

- 신규 물리 스키마 명세
- `backend/apps/visits/models/`
- `contracts/api/paths/visits.yaml`
- `contracts/state-machine/`
- `data/synthetic/`
- 방문 일정 계약 테스트

### 4.5 `T005_VISIT_STATUS_CODESET`

검토 질문:

- `FOLLOW_UP_REQUIRED`가 방문 자체 상태인지, 문의 상태인지, 별도 후속 조치 플래그인지?
- `VISIT_COMPLETED` 이후 후속 방문이 필요하면 어떤 이벤트로 전이할지?
- 화면·API·State Machine의 allowed action이 같은 상태표를 사용하는지?

영향 파일:

- `contracts/codes/visit-statuses.yaml`
- `contracts/state-machine/`
- `backend/apps/visits/`
- `backend/apps/workflow/`
- `tests/contract/state-machine/`
- 화면·API 명세

### 4.6 `T005_ENUM_SEED_POLICY`

검토 질문:

- 변경 빈도와 DB 자체 검증 강도 중 어느 쪽을 우선할지?
- Seed는 누가 어떤 명령으로 실행하고 같은 키를 어떻게 Upsert할지?
- 운영 코드 변경과 데이터 코드 변경을 같은 PR에서 처리할지?

영향 파일:

- `contracts/codes/`
- `backend/common/utils/enum.py`
- `scripts/database/seed_demo_data.py`
- `data/synthetic/`
- 신규 Django Migration 또는 코드 테이블
- Seed 재실행 계약 테스트

## 5. 승인 기록

| 역할 | 담당자 | 상태 | 승인값·의견 | 확인일 |
| --- | --- | --- | --- | --- |
| PM·기술 통합 | 윤승혁 | `PENDING` |  |  |
| T-005 OWNER | 최지용 | `PROPOSED` |  | 2026-07-25 |
| 데이터·QA·DevOps | 김은진 | `PENDING` |  |  |
| AI·RAG 영향 검토 | 이동윤 | `PENDING` |  |  |
| 화면 계약 영향 검토 | 화면 담당자 | `PENDING` |  |  |

## 6. 승인 후 실행 순서

1. 여섯 결정의 승인값과 결정 이유를 승인 ADR에 기록한다.
2. `manifest.json`과 논리 계약의 상태를 승인 결과와 함께 갱신한다.
3. ERD 후속본, 코드 계약, API·AI Schema를 같은 이름과 값으로 동기화한다.
4. Django Model과 Migration을 생성한다.
5. 승인된 PostgreSQL에서 Migration과 schema diff를 검증한다.
6. T-006·T-007·T-013 수신자에게 변경 diff와 재검증 명령을 다시 인계한다.

## 7. 제안 상태 검증

승인 전 정상 상태는 다음과 같다.

```powershell
python .\scripts\database\validate_t005_schema.py
python .\scripts\database\validate_t005_schema.py --require-wbs-complete
```

- 기본 구조 검증: exit code `0`
- 엄격 완료 검사: 여섯 결정이 남아 있으므로 exit code `2`

루트 `tests/**`는 김은진 주관 QA 경로다. 2026-07-26 관할 정정에 따라 최지용이 추가했던 T-005 계약 테스트는 철회했으며, 현재 제안 상태 검증은 최지용 주관 `scripts/database/**` 검증기의 두 모드만 사용한다.

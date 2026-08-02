# ADR 0008: T-005 데이터 계약 기준선

> 기계 상태: `OWNER_BASELINE_ACCEPTED`
>
> 현재 해석: `PARTIALLY_SUPERSEDED` — 기본키 정책은
> [ADR 0010](0010-t005-three-layer-identifier-bridge.md)이 대체하며,
> 나머지 다섯 결정은 활성 계약에 반영돼 있다.
>
> 결정일: 2026-07-26
>
> 초기 결정 책임: Backend·Database 담당(T-005)
>
> 공식 완료 경계: 작성자 기술 검증 완료, 비작성자 독립 재현·외부 소비
> 검토·PM 계약 승인 대기
>
> 대상 WBS: `T-005`

`OWNER_BASELINE_ACCEPTED`는 기존 검증기와 계약 이력을 위한 기계
상태값이다. 이 값만으로 팀의 공식 WBS 완료나 모든 소비자 검토 완료를
뜻하지 않는다.

## 1. 결정과 현재 상태

| 결정 ID | 현재 기준 | 상태 |
| --- | --- | --- |
| `T005_PRIMARY_KEY_POLICY` | 내부 `BigAutoField` PK·외부 `public_id` UUID·업무 코드를 분리 | **ADR 0010이 대체** |
| `T005_USAGE_GUIDANCE_PHYSICAL_MAPPING` | 신규 물리 필드는 `usage_guidance_status`, `usage_guidance_code`는 반입 별칭으로만 사용 | 활성 |
| `T005_USAGE_GUIDANCE_CODESET` | `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`; `USE_ALLOWED`는 반입 별칭 | 활성 |
| `T005_VISIT_STORAGE_MAPPING` | `preferred_date`, `confirmed_date`, `schedule_status`, `synthetic_technician_id`를 분리 저장 | 활성 |
| `T005_VISIT_STATUS_CODESET` | `FOLLOW_UP_REQUIRED`를 포함한 7개 방문 일정 상태 | 활성 |
| `T005_ENUM_SEED_POLICY` | 계약 YAML → Django `TextChoices` → 멱등 Upsert Seed | 활성 |

현재 선택값의 기계 판독 원천은
[Decision Register v0.3](../database/t-005/t005_decision_register_v0.3.json)과
[Physical Contract v1.3](../database/t-005/t005_physical_contract_v1.3.json)이다.
이 ADR은 최초 결정의 이유와 대체 관계를 설명한다.

## 2. 결정 이유

- WBS·화면·API·AI가 같은 canonical 필드와 코드값을 소비하게 한다.
- ERD v3는 과거 Snapshot으로 보존하고 현행 물리 계약에서 차이를
  명시해 변경 이력을 추적한다.
- 내부 조인 키, 외부 공개 식별자, 사람이 읽는 업무 코드를 분리해
  데이터베이스 최적화와 API 안전성을 함께 확보한다.
- 고객 희망일과 확정일을 분리해 아직 확정되지 않은 시간대 정책과
  독립적으로 저장한다.
- 코드 계약과 Django Enum의 자동 일치 검증으로 서비스 간 값 불일치를
  차단한다.
- 합성 Seed는 업무 코드 기준 Upsert로 반복 실행해도 중복되지 않게 한다.

## 3. 적용 범위

- 활성 데이터베이스 진입점:
  [T-005 데이터베이스 설계·구현 기준](../database/t-005/README.md)
- 활성 식별자 결정:
  [ADR 0010](0010-t005-three-layer-identifier-bridge.md)
- 활성 상태 이력·멱등성 결정:
  [ADR 0011](0011-t005-status-history-idempotency-scope.md)
- 기계 코드 계약:
  [사용 안내 상태](../../contracts/codes/usage-guidance-statuses.yaml),
  [방문 일정 상태](../../contracts/codes/visit-statuses.yaml)
- Django Model·Migration·Seed는 활성 계약의 이름·타입·코드값을
  사용한다.
- 상태 전이 이벤트·Guard·다음 상태는 `contracts/state-machine/**`의
  별도 책임이며 이 ADR이 임의로 변경하지 않는다.

## 4. 대안과 제외

- 하나의 문자열 PK에 내부 조인·API 노출·업무 코드 책임을 모두
  부여하는 방식은 ADR 0010에서 폐기했다.
- `usage_guidance_code`와 `usage_guidance_status`의 dual-write는
  두 개의 원장을 만들기 때문에 제외했다.
- 방문 희망일·확정일과 실제 작업 시간창을 하나의 DateTime 쌍으로
  표현하는 방식은 업무 의미가 달라 제외했다.
- DB Enum과 수동 INSERT Seed는 변경·재실행 비용 때문에 MVP
  기준선에서 제외했다.

## 5. 구현·검증 상태

Physical Contract v1.3은 32개 계약 테이블, 3계층 식별자,
상태 이력 무결성, 멱등성 책임 분리와 PostgreSQL 검증 결과를 반영한다.
현재 구현 Gate는 `TECHNICALLY_COMPLETE_REVIEW_PENDING`이며, 기술
미구현 항목과 공식 완료 검토 항목을 구분한다.

저장소 루트에서 다음 명령으로 구조와 계약 정합성을 확인한다.

```powershell
backend\.venv\Scripts\python.exe scripts\database\validate_t005_schema.py
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\database\test_t005_schema_validator.py -q -p no:cacheprovider
```

`--require-wbs-complete` 검사는 비작성자 독립 재현·외부 검토 등 완료
증거까지 요구한다. 해당 Gate가 남아 있는 동안 exit code `2`는 계약
오류가 아니라 공식 완료 조건이 충족되지 않았다는 뜻이다.

## 6. 변경 원칙

후속 변경은 기존 ADR이나 적용된 Migration을 삭제·재작성하지 않는다.
새 ADR에서 대체 범위와 이유를 기록하고, 활성 계약·Model·Migration·Seed·
계약 테스트를 같은 변경 단위로 갱신한다.

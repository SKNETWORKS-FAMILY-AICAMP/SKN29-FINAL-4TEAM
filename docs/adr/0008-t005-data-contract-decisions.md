# ADR 0008: T-005 데이터 계약 OWNER 기준선

> 상태: `OWNER_BASELINE_ACCEPTED`
> 결정일: 2026-07-26
> 결정자: 최지용(T-005 OWNER)
> 비작성자 완료 검토: 증거 미기록 — 구현 착수의 선행 조건이 아님
> 대상 WBS: `T-005`

## 1. 결정

T-005 주담당 산출물을 후속 구현의 기준선으로 먼저 제공하기 위해 다음
여섯 항목을 OWNER 기준선으로 채택한다. 이 상태는 최지용 담당 구현에
즉시 사용할 수 있다는 뜻이며, PM의 공식 WBS 완료 판정이나 작성자 외
리뷰 완료를 뜻하지 않는다.

| 결정 ID | 채택 기준 |
| --- | --- |
| `T005_PRIMARY_KEY_POLICY` | 일반 ID는 `<ENTITY>-<UUID4_HEX_32>`, 합성 Seed는 `DEMO/SYN-<ENTITY>-<순번>`인 최대 48자 도메인 문자열 |
| `T005_USAGE_GUIDANCE_PHYSICAL_MAPPING` | 신규 물리 필드는 `usage_guidance_status`; legacy `usage_guidance_code` dual-write 금지 |
| `T005_USAGE_GUIDANCE_CODESET` | `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`; `USE_ALLOWED`는 import 별칭 |
| `T005_VISIT_STORAGE_MAPPING` | `preferred_date`, `confirmed_date`, `schedule_status`, `synthetic_technician_id`를 분리 저장 |
| `T005_VISIT_STATUS_CODESET` | `FOLLOW_UP_REQUIRED`를 포함한 7개 방문 일정 상태 |
| `T005_ENUM_SEED_POLICY` | 계약 YAML → Django `TextChoices`; 합성 Seed는 검증된 고정 ID로 Upsert |

## 2. 이유

- WBS와 화면 설계에 이미 명시된 canonical 필드와 코드명을 그대로
  사용하면 Web·Mobile·AI가 같은 이름을 소비할 수 있다.
- ERD v3는 해시가 고정된 과거 Snapshot이므로 수정하지 않고 새 물리
  계약으로 차이를 명시하는 편이 추적 가능하다.
- 일반 ID에는 UUID4의 충돌 내성을 사용하고, 합성 데이터만 고정 순번을
  허용하면 운영 발급과 재실행 가능한 Demo Seed를 분리할 수 있다.
- 날짜 필드는 아직 미정인 시간대 정책과 독립적으로 저장할 수 있다.
- 코드 계약과 Django Enum을 분리하되 자동 일치 검증을 두면 DB Enum
  변경 비용 없이 서비스 간 값 불일치를 차단할 수 있다.

## 3. 영향

- 기준 물리 계약:
  `docs/database/t-005/t005_physical_contract_v1.0.json`
- 기계 코드 계약:
  `contracts/codes/usage-guidance-statuses.yaml`,
  `contracts/codes/visit-statuses.yaml`
- Django Model·Migration은 이 기준선을 사용한다.
- `contracts/state-machine/**`의 전이 규칙은 윤승혁(PM) 관할이므로
  이번 ADR에서 수정하지 않는다.
- 실제 PostgreSQL 적용과 schema diff는 실행 환경이 제공된 뒤 별도
  증거로 남긴다.

## 4. 대안과 제외

- v3 UUID PK를 그대로 유지하는 안은 공통 도메인 문자열 ID 원칙과
  충돌해 제외했다.
- `usage_guidance_code`와 `usage_guidance_status` dual-write는
  신규 DB에서 불필요한 두 원장을 만들기 때문에 제외했다.
- 방문 일정의 날짜와 작업 시간창을 하나의 DateTime 쌍으로 표현하는
  안은 고객 희망일·확정일 의미를 잃으므로 제외했다.
- DB Enum과 수동 INSERT Seed는 변경·재실행 비용 때문에 MVP 기준선에서
  제외했다.

## 5. 검증 및 인계

```powershell
python .\scripts\database\validate_t005_schema.py
python .\scripts\database\validate_t005_schema.py --require-wbs-complete
python -m pytest .\backend\tests\unit\database\test_t005_schema_validator.py -q
```

세 검증을 통과한 기준선은 T-017 사용자·권한 Model과 T-006 AI 공통
스키마 정합화의 입력으로 공유한다. 팀 리뷰에서 이상이 확인되면 이 ADR을
삭제하지 않고 후속 ADR과 Migration으로 변경 이력을 남긴다.

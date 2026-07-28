# T-005 WaterCare 데이터 설계 기준선

> Snapshot 기준일: 2026-07-25 · 상태 갱신일: 2026-07-27
> 담당: 최지용
> WBS 해석: OWNER 설계 기준선 확정, Runtime 완료율은 재실행 증거로 별도 판정
> 저장소 판정: OWNER 설계 기준선 확정·Django Runtime 구현 진행

## 1. 목적

WaterCare ERD v3.0.0을 저장소 안에서 재현 가능하게 검토하기 위한
기준선이다. 원본 Snapshot을 수정하지 않고 동일한 파일 내용을
snake_case 이름으로 보존했으며 `manifest.json`에 SHA-256을 기록했다.

이 디렉터리의 v3 파일은 당시 설계 Snapshot이고, 현재 구현 기준은
[`ADR 0008`](../../adr/0008-t005-data-contract-decisions.md)과
[`t005_physical_contract_v1.0.json`](t005_physical_contract_v1.0.json)이다.
Django Model·Migration과 PostgreSQL 완료 여부는 별도 Runtime 증거로
판정한다.

## 2. 포함 파일

| 파일 | 역할 |
| --- | --- |
| `watercare_schema_v3.json` | 32개 테이블·526개 컬럼의 기계 검증용 스키마 |
| `watercare_erd_v3.mmd` | Mermaid ERD 원본 |
| `watercare_erd_v3.png` | 팀 공유용 정적 ERD |
| `watercare_schema_sqlite_v3.sql` | PostgreSQL 명세를 변환한 SQLite 호환 검증 스키마 |
| `watercare_erd_validation_v3.md` | 원본 v3 교차검증 결과 |
| `manifest.json` | 버전·개수·파일 해시·차단 결정 목록 |

## 3. 확인된 구조

| 항목 | 결과 |
| --- | ---: |
| 테이블 | 32 |
| 컬럼 | 526 |
| 물리 FK | 85 |
| 논리 공통코드 참조 | 57 |
| 원본 HTML 자동 테스트 | Snapshot 작성 당시 5건 통과 |
| Snapshot 해시·FK 검증 | 통과 |

`support_inquiry`에는 현재 담당자, 사용 안내, 제한 기능, 고객 행동 필요 여부가 포함돼 있다. `knowledge_evidence_link`와 `support_guidance`에는 판단 근거를 연결할 구조가 존재한다.

## 4. Legacy Snapshot 차이와 현재 OWNER 해법

아래 항목은 v3 Snapshot과 현재 기준선의 차이를 추적하는 역사 기록이다.
최지용 OWNER 기준선은 이미 확정됐으며 구현 착수 승인 대기 항목이 아니다.

| ID | Legacy Snapshot 차이 | 현재 OWNER 해법 |
| --- | --- | --- |
| `T005_PRIMARY_KEY_POLICY` | Snapshot의 주요 PK는 UUID다. | `<ENTITY>-<UUID4_HEX_32>` 도메인 문자열 ID를 사용한다. |
| `T005_USAGE_GUIDANCE_PHYSICAL_MAPPING` | WBS에서 canonical 이름은 `usage_guidance_status`로 확정됐지만 ERD v3에는 `usage_guidance_code`가 남아 있다. | v0.2 논리 계약에 확정 이름을 반영하고, v3 물리 Snapshot은 변경 이력으로 보존 |
| `T005_USAGE_GUIDANCE_CODESET` | 화면은 일반 사용 가능을 `NORMAL`, ERD v3는 `USE_ALLOWED`로 표현한다. | `NORMAL`을 표준으로 사용하고 legacy `USE_ALLOWED`를 import 시 변환한다. |
| `T005_VISIT_STORAGE_MAPPING` | 화면과 v3의 일정 필드 구조가 다르다. | `preferred_date`, `confirmed_date`, `schedule_status`, `synthetic_technician_id`를 분리 저장한다. |
| `T005_VISIT_STATUS_CODESET` | 화면 상태표에는 `FOLLOW_UP_REQUIRED`가 있으나 ERD v3에는 없다. | `FOLLOW_UP_REQUIRED`를 포함한 7개 방문 상태를 사용한다. |
| `T005_ENUM_SEED_POLICY` | v3에는 Enum·Seed 운영 방식이 확정되지 않았다. | 계약 YAML과 Django `TextChoices`를 맞추고 합성 Seed는 `update_or_create`로 재실행 가능하게 한다. |

`t005_logical_contract_v0.2.json`에는 WBS에서 확정된 공통 사용 안내 필드, 방문 일정 논리 필드와 위험도 코드를 별도 기록했다. 기존 v3 Snapshot은 당시 설계 이력으로 유지한다.

따라서 Snapshot과 v0.2 논리 계약은 구조·차이 추적에 사용하고, 신규
구현은 ADR 0008과 물리 계약 v1.0을 사용한다. 명세 기준선 확정과
Django·PostgreSQL Runtime 완료 판정은 분리한다.

## 5. 검증 명령

저장소 루트에서 실행한다.

```powershell
python .\scripts\database\validate_t005_schema.py
```

구조 오류가 없으면 기본 검증은 성공한다. WBS 완료 증거까지 검사하려면
다음 명령을 사용한다.

```powershell
python .\scripts\database\validate_t005_schema.py --require-wbs-complete
```

엄격 검사의 exit code는 미정 결정 6건이 아니라 현재 Runtime·PostgreSQL·
Seed·작성자 외 리뷰 증거에 따라 판정한다.

검증 출력은 `OWNER_BASELINE_CONFIRMED`와 `confirmation_status:
CONFIRMED`로 설계 기준선 확정을 표시한다. 구현 후 완료 증거는
`non_author_review`로 기록하며, 기존 `team_review` 입력은 과거 증거
JSON 호환 alias로만 읽는다. 어느 이름도 명세 작성 허가를 뜻하지 않고,
구현 결과의 소비자 호환성·실행 재현·비작성자 PR 품질을 확인한다.

## 6. 구현·검증 순서

1. ADR 0008과 물리 계약 v1.0을 해당 Wave의 구현 입력으로 고정한다.
2. Django Model·Migration을 한 Wave만 구현한다.
3. `makemigrations --check --dry-run`과 빈 PostgreSQL Migration을
   즉시 검증한다.
4. PK·FK·UNIQUE·CHECK·Index와 Seed 참조를 검증한다.
5. API Serializer·예시와 정합성을 확인한 뒤 다음 Wave로 이동한다.
6. 소비자 호환성·재현 검토와 비작성자 PR 리뷰는 구현 결과에 대해
   수행한다. 이는 작업 착수 승인이 아니다.

## 7. 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.1 | 2026-07-25 | ERD v3 Snapshot, 해시·FK 검증과 네 차단 항목 기록 |
| v0.2 | 2026-07-25 | 확정된 `usage_guidance_status`와 방문 일정 논리 필드를 별도 계약으로 누적하고 코드값·물리 매핑 충돌을 분리 |
| v0.3 | 2026-07-25 | 과거 Manifest의 stale 차단 ID 4개를 실제 gap ID 6개로 정합화하고, Manifest와 검증기 gap 목록의 자동 일치 검사를 추가 |

> [!NOTE]
> 아래 v0.3~v0.6의 `PENDING`, exit code와 테스트 수는 OWNER 기준선
> 확정 전 실행 이력이다. 현재 결정·Runtime·완료 판정으로 재사용하지
> 않으며, 현재 Branch는 이 문서의 활성 기준 파일과 재실행 결과로
> 판정한다.

## 8. 2026-07-25 v0.3 누적 정정

v0.1 변경 이력의 “네 차단 항목”은 당시 Manifest 상태를 설명하는 과거
기록으로 보존한다. v0.3 당시 유효했던 여섯 ID는 현재 Manifest에서도
`legacy_snapshot_gaps` 정합성용으로 유지한다. 이는 현재 OWNER 차단
항목이 아니며, 활성 OWNER 기준선의 `gaps`는 0개다.

- 결정 제안서: [ADR 제안 0008](<../../adr/proposals/0008-t005-data-contract-decisions-proposal.md>)
- 기본 구조 검증: exit code `0`
- 엄격 완료 검사: 당시 OWNER 결정 입력 전 여섯 gap이 남아 있어 exit
  code `2`

제안서는 현재 `SUPERSEDED` 보관본이다. 활성 구현 기준은
`OWNER_BASELINE_ACCEPTED` 상태의 ADR 0008과 물리 계약 v1.0이다.

## 9. 2026-07-26 관할 정정

루트 `tests/**`는 김은진 주관 QA 경로이므로 최지용이 추가했던 T-005 계약 테스트는 철회했다. 8장의 `4 passed`는 당시 실행 이력으로만 읽으며 현재 증거로 사용하지 않는다. `scripts/database/**`는 최지용 주관 경로이므로 기본 검증 `exit 0`과 엄격 완료 게이트 `exit 2`를 현재 재현 기준으로 유지한다.

## 10. 2026-07-26 v0.4 구현 준비도 검증 보강

기존 논리 계약의 `decisions_required`에는 Manifest에 존재하는
`T005_USAGE_GUIDANCE_PHYSICAL_MAPPING`이 누락돼 있었다. 결정값을
추가한 것이 아니라 누락된 결정 질문을 `PENDING` 상태로 복원했다.
이제 Manifest, 논리 계약, 실제 계산 gap의 여섯 ID가 모두 정확히
일치해야 기본 검증이 통과한다.

| 보강 항목 | v0.4 작성 당시 결과 |
| --- | --- |
| Manifest·논리 계약 결정 ID | 정확히 6개, 중복·누락 없음 |
| 계산 gap·Manifest ID | 정확히 6개, 중복·누락 없음 |
| Snapshot 기본 검증 | exit `0` |
| 엄격 완료 게이트 | exit `2`, 6개 결정 대기 |
| 변조·누락·중복·FK 회귀 테스트 | `9 passed` |
| Django 구현 준비도 | `NOT_READY` |

구현 준비도 감사는 App 골격이 있는지와 실제 Model·Migration·등록
상태를 구분한다. 당시 App 골격은 12개였지만 업무 Model 클래스,
번호 Migration, 등록된 프로젝트 App·Model은 모두 0개다. 따라서
`makemigrations --check --dry-run`의 `No changes detected`는 T-005
구현 완료 증거가 아니다.

```powershell
python .\scripts\database\validate_t005_schema.py
python .\scripts\database\validate_t005_schema.py --require-wbs-complete
python .\scripts\database\audit_t005_implementation_readiness.py
python -m pytest .\backend\tests\unit\database\test_t005_schema_validator.py -q
```

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.4 | 2026-07-26 | 누락 결정 질문 복원, 세 목록 정확 일치 검증, 9개 회귀 테스트와 구현 준비도 감사 추가 |

## 11. 2026-07-26 v0.5 결정 등록부 보강

여섯 미정 항목의 회신을 문장으로만 전달받아 누락하지 않도록
`t005_decision_register_v0.1.json`을 추가했다. 이 파일은 immutable
Snapshot의 일부가 아니라 결정값·결정자·근거·반영 기한을 받는
가변 입력 문서다. 당시 여섯 항목은 모두 `PENDING`이며 선택값을
임의로 넣지 않았다.

`ACCEPTED`로 바꾸려면 다음 다섯 필드가 모두 필요하다.

- `selected_option`
- `decided_by`
- `decided_at`
- `rationale`
- `effective_from`

검증기는 등록부 ID가 Manifest의 여섯 blocker와 정확히 일치하는지,
중복·미등록 상태가 없는지, `ACCEPTED` 결정의 추적 필드가 모두
채워졌는지 검사한다. `ACCEPTED` 기록만으로 strict 검사가 통과하지는
않는다. ERD와
논리·물리 계약까지 결정대로 바뀌어 실제 gap이 없어져야 한다.

| 검증 항목 | v0.5 작성 당시 결과 |
| --- | --- |
| 결정 등록부 ID | 6개, Manifest와 일치 |
| `ACCEPTED` 결정 | 0개 |
| 등록부 유효성 | `true` |
| T-005 대상 회귀 | `12 passed` |
| 기본 구조 검증 | exit `0` |
| 엄격 완료 게이트 | exit `2`, 실제 gap 6개 |
| Django 구현 준비도 | `NOT_READY` |

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.5 | 2026-07-26 | 결정 등록부와 결정 추적 필드 검증, 등록부 변이 테스트를 추가하고 회귀 테스트를 12건으로 확대 |

## 12. 2026-07-26 v0.6 결정 이력·등록부 헤더 재검증

v0.5 이후 작성자 외 교차검토에서 등록부의 최상위 `version`·`status`
변조와 `REJECTED`·`DEFERRED` 이력 누락 가능성을 추가 확인했다. 기존
내용은 당시 이력으로 보존하고 다음 검증을 v0.6 작성 시점 기준으로
삼았다.

- 등록부 버전은 `0.1`만 유효하다.
- 최상위 상태는 여섯 개별 결정 상태를 집계한 값과 같아야 한다.
- `ACCEPTED`는 선택값·결정자·결정 시각·근거·반영일이 모두 필요하다.
- `REJECTED`·`DEFERRED`도 결정자·결정 시각·근거 없이는 유효하지 않다.
- 당시 `PENDING` 결정에는 임의의 선택값이나 결정자를 넣지 않는다.

| 재검증 | v0.6 작성 당시 결과 |
| --- | --- |
| T-005 대상 회귀 | `17 passed` |
| 전체 백엔드 회귀 | `101 passed` |
| 기본 구조 검증 | exit `0`, 등록부 `valid=true` |
| 엄격 완료 게이트 | exit `2`, 실제 gap 6개 |
| `ACCEPTED` 결정 | 0/6 |
| Django 구현 준비도 | `NOT_READY` |

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.6 | 2026-07-26 | 등록부 버전·집계 상태와 반려·보류 결정 이력 검증을 추가하고 대상 17건·전체 101건을 재검증 |

## 13. 2026-07-26 v0.7 OWNER 물리 계약 기준선

최지용이 T-005 주담당 산출물을 먼저 완성하고 팀에 공유한다는 실행
원칙에 따라, 기존 ERD v3 Snapshot은 이력으로 보존하고 구현 입력을
별도 기준선으로 확정했다.

- 결정 등록부:
  [`t005_decision_register_v0.1.json`](<t005_decision_register_v0.1.json>)
- 물리 계약:
  [`t005_physical_contract_v1.0.json`](<t005_physical_contract_v1.0.json>)
- 결정 근거:
  [`ADR-0008`](<../../adr/0008-t005-data-contract-decisions.md>)

| 결정 | OWNER 기준선 |
| --- | --- |
| PK | `<ENTITY>-<UUID4_HEX_32>`, 합성 Seed만 `DEMO/SYN` 순번 |
| 사용 안내 필드 | `usage_guidance_status` |
| 사용 안내 코드 | `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION` |
| legacy 반입 | `USE_ALLOWED`를 `NORMAL`로 변환, dual-write 금지 |
| 방문 일정 | `preferred_date`, `confirmed_date`, `schedule_status`, `synthetic_technician_id` |
| 방문 상태 | `FOLLOW_UP_REQUIRED`를 포함한 7개 |
| Enum·Seed | 계약 YAML↔`TextChoices` 일치, 합성 Seed `update_or_create` |

### 작업·검증 반복

| 회차 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 결정 6건을 `T005_OWNER_BASELINE`으로 기록 | 결정 추적 필드·집계 상태 검사 | 6/6 `ACCEPTED` |
| 2 | 불변 Snapshot과 별도 물리 override 작성 | Snapshot 해시·override 참조 검사 | 유효 |
| 3 | 코드 YAML·Inquiry/Visit API Schema 동기화 | T-005 대상 테스트 | `19 passed` |
| 4 | OWNER 물리 계약까지 strict 판정 확장 | 기본·strict CLI | exit `0` / exit `0` |

`legacy_snapshot_gaps` 6개는 과거 Snapshot과 현재 요구의 차이를
추적하기 위해 그대로 남긴다. 현재 OWNER 기준선 판정은 별도
`owner_baseline_gaps` 0개를 사용한다.

아래 테스트 수와 exit code는 v0.7 작성 당시 실행 스냅샷이다.

| v0.7 작성 당시 판정 | 결과 |
| --- | --- |
| T-005 대상 | `19 passed` |
| 기본 구조 검증 | exit `0` |
| strict 완료 게이트 | exit `0` |
| OWNER 기준선 gap | 0개 |
| 공식 WBS 상태 | `진행 중`, PM 상태 반영 전 |

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.7 | 2026-07-26 | 결정 6건·물리 계약·표준 코드·API Schema를 OWNER 기준선으로 확정하고 대상 19건·strict exit 0을 검증 |

## 2026-07-27 v0.8 — WBS 완료 증거 입력

위 v0.7 strict는 OWNER 기준선 내부 정합성의 과거 기록이다. 현재
`--require-wbs-complete`는 다음 5개 외부 완료 증거가 없으면 exit
code 2를 반환한다.

1. 구현 결과의 소비 호환성·재현 검토
2. Django Model·Migration parity
3. 실제 PostgreSQL Migration
4. PostgreSQL Seed 2회 멱등성
5. 작성자 외 리뷰

위 항목은 WBS 최종 완료·공유·PR 품질 게이트이며 최지용의 명세 작성이나
구현 착수 승인이 아니다. 게이트를 코드의 고정 `False`나 bare boolean으로 두지 않고, 비밀값
없는 증거 JSON을 `--completion-evidence <상대경로>`로 받는다. 각
기록에는 status, 실행 command, 검증자, 기록 시각을 포함하고
PostgreSQL 기록에는 vendor를 명시한다. 최지용의 자기 승인은 외부
리뷰로 인정하지 않는다.

```powershell
python .\scripts\database\validate_t005_schema.py `
  --completion-evidence .\docs\handoffs\<완료-증거파일>.json `
  --require-wbs-complete
```

증거 파일에는 비밀번호·DSN·Token·개인정보를 넣지 않는다.

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.8 | 2026-07-27 | 리뷰·Model/Migration·실제 PostgreSQL·Seed 2회 증거 입력을 추가해 영구 고정 게이트 제거 |

## 2026-07-27 v0.9 — 실제 Runtime 검증만 PG·Parity 증거로 인정

v0.8의 completion JSON 입력은 팀 리뷰·Seed·외부 리뷰 이력을 전달하는
용도로 계속 사용한다. 다만 JSON에
`django_model_migration_parity=VERIFIED` 또는
`postgresql_migration=VERIFIED` 문자열을 적는 것만으로는
Model·Migration parity와 PostgreSQL 게이트를 통과할 수 없다.

두 게이트의 권위 증거는 `--verify-postgresql`이 실제로 실행한 다음
결과뿐이다.

1. `DJANGO_SETTINGS_MODULE=config.settings.local`을 강제한다.
2. PostgreSQL 읽기 전용 연결 검사를 실행한다.
3. 연결 성공 여부와 무관하게
   `makemigrations --check --dry-run --settings=config.settings.local`을
   실행한다.
4. PostgreSQL 연결이 성공한 경우에만
   `migrate --check --noinput --settings=config.settings.local`을
   실행한다.

따라서 completion JSON은 실제 Runtime 검증 결과를 대신하거나
덮어쓸 수 없다. JSON 구조가 잘못되거나 중첩 값의 타입이 올바르지
않으면 해당 증거는 안전하게 미충족으로 판정한다.

```powershell
python .\scripts\database\validate_t005_schema.py `
  --completion-evidence .\docs\handoffs\<완료-증거파일>.json `
  --verify-postgresql `
  --require-wbs-complete
```

### v0.9 작성 당시 실행 결과

| 항목 | 2026-07-27 결과 |
| --- | --- |
| PostgreSQL 연결 | `NOT_CONFIGURED` |
| Django Model·Migration parity | `FAILED` |
| PostgreSQL `migrate --check` | `NOT_RUN` |
| completion gap | 5개 |
| 대상 회귀 | T-005·T-017 집중 테스트 `35 passed` |

당시 5개 completion gap은 소비 호환성 검토, Django Model·Migration parity,
실제 PostgreSQL Migration, PostgreSQL Seed 2회 멱등성, 작성자 외
리뷰였다. 당시 환경에서는 PostgreSQL 연결과 local settings 필수
환경변수가 준비되지 않았으므로 PG·parity 완료로 기록하지 않았다.

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.9 | 2026-07-27 | JSON 자기신고형 PG·parity 통과를 차단하고 실제 local-settings 검증 결과만 완료 게이트에 반영 |

## 2026-07-27 v1.0 — 계약 테이블과 Django 구현 매핑 감사

`scripts/database/audit_t005_implementation_readiness.py`가 32개 계약
테이블을 다음 세 단계로 나누어 감사하도록 보강됐다.

1. 실제 Django Model 클래스 선언
2. Django App 등록 후 Model 인식
3. 번호가 있는 Django Migration의 테이블 생성

Docstring만 있는 Model 골격은 구현으로 계산하지 않는다. 계약에 없는
Model·Migration도 별도 항목으로 보고하며, 실제 비밀값은 출력하지
않고 PostgreSQL 필수 키의 구성 여부만 확인한다.

| 구현 매핑 | v1.0 작성 당시 결과 |
| --- | ---: |
| 계약 테이블 | 32개 |
| Model 선언·등록·Migration 모두 확인 | 2개 |
| 확인된 테이블 | `accounts_user`, `customers_customer_profile` |
| Model 미구현 | 30개 |
| Migration 미구현 | 30개 |

이 v1.0 실행 당시 상태는 `NOT_READY`였다. 당시에는 나머지 30개
Model·Migration, Docker Compose, PostgreSQL 환경이 남아 있었다.
현재 상태는 Migration 검증 보고서와 같은 Commit에서 실행한 준비도
감사 결과를 우선한다.

```powershell
python .\scripts\database\audit_t005_implementation_readiness.py
python .\scripts\database\audit_t005_implementation_readiness.py `
  --require-ready
```

v1.0 작성 당시 Database 단위 테스트는 `36 passed`, strict 실행은
exit `2`였다. 현재 Branch 판정에는 이 수치를 재사용하지 않는다.

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v1.0 | 2026-07-27 | 32개 계약 테이블과 Model 선언·App 등록·Migration을 항목별로 대조하는 구현 매핑 감사와 회귀 테스트 추가 |

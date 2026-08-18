# T-005 데이터베이스 설계·구현 기준

> 기준일: 2026-08-10
>
> 담당: 최지용
>
> 현재 상태: `TECHNICALLY_READY_REVIEW_PENDING`
>
> 실행 기준: PostgreSQL `waterbridge` 데이터베이스의 `public` Schema

## 1. 문서 역할

이 디렉터리는 T-005 데이터베이스 계약과 기계 검증 자료의 진입점이다.
현재 구현에 반복 적용할 절차, 특정 시점의 실행 증거와 과거 Wave 이력은
개인 개발문서에서 역할별로 분리한다.

| 역할 | 단일 기준 |
| --- | --- |
| 기계 판독 계약 | 이 디렉터리의 Logical·Decision·Physical Contract |
| 현재 스키마 변경 절차 | [데이터베이스 Schema·Migration 구현 가이드](../../individual/jiyong/데이터베이스/데이터베이스_스키마_마이그레이션_구현_가이드.md) |
| 현재 Seed·Importer 재현 절차 | [합성데이터 Seed·Importer 검증 가이드](../../individual/jiyong/데이터베이스/합성데이터_시드_Importer_검증_가이드.md) |
| 사람이 읽는 전체 테이블 설명 | [WaterBridge 테이블 명세](../waterbridge_table_dictionary.md) |

문서와 Runtime이 다르면 ADR·활성 계약·Django Model·Migration·실제
PostgreSQL 검증 결과를 순서대로 대조한다. 과거 Snapshot의 수치나
파일 존재만으로 구현 완료를 판정하지 않는다.

## 2. 현재 Runtime 판정

| 항목 | 2026-07-31 결과 |
| --- | --- |
| 계약 테이블 | 32개 |
| Model·App Registry·Migration | **32/32** |
| T-005 Auditor | `READY`, blocker 0 |
| 승인된 계약 외 지원 Runtime | 5개 (`support_followup_answer` 포함) |
| Accounts 식별자 | 내부 BigInt PK·공개 UUID·업무 코드 분리 |
| JWT subject | 공개 UUID만 허용, Legacy 문자열 fallback 제거 |
| PostgreSQL | `waterbridge.public`, PostgreSQL 16.14 |
| Active 범위 | 13개 테이블·총 369행 |
| Target-only 범위 | 19개 테이블·각 0행 |
| 빈 PostgreSQL | 전체 Migration·5종 Seed 2회·367건 Import 2회 PASS |
| 전체 회귀 | SQLite `740 passed, 11 skipped`, PostgreSQL `751 passed` |
| Data QA | 67 tests, 대표 E2E 17/17, 오류·경고 0 |
| 공식 완료 | 비작성자 독립 재현·외부 소비 검토·PM 승인 대기 |

Active 13은 현재 데이터가 있는 범위다. Target-only 19개 테이블도
물리 계약과 Migration에 포함되므로 삭제하거나 별도 축소 Schema로
분리하지 않는다.

## 3. 활성 계약

현재 구현 입력은 다음 자료다.

1. [ADR 0010: 3계층 식별자](../../adr/0010-t005-three-layer-identifier-bridge.md)
2. [ADR 0011: 상태 이력·멱등성](../../adr/0011-t005-status-history-idempotency-scope.md)
3. [`t005_logical_contract_v0.3.json`](t005_logical_contract_v0.3.json)
4. [`t005_decision_register_v0.3.json`](t005_decision_register_v0.3.json)
5. [`t005_physical_contract_v1.3.json`](t005_physical_contract_v1.3.json)

이전 버전과 v3 ERD는 당시 결정과 차이를 추적하는 역사 자료다. 현재
계약을 덮어쓰지 않으며 이름을 바꾸거나 삭제하지 않는다.

## 4. 포함 파일

| 파일군 | 역할 |
| --- | --- |
| `manifest.json` | Snapshot 버전·개수·파일 해시 |
| `watercare_schema_v3.json` | 32개 테이블·526개 컬럼의 기계 검증용 스키마 |
| `watercare_erd_v3.mmd` | Mermaid ERD 원본 |
| `watercare_erd_v3.png` | 팀 공유용 정적 ERD |
| `watercare_schema_sqlite_v3.sql` | SQLite 호환 구조 검증 스키마 |
| `watercare_erd_validation_v3.md` | ERD·Schema 교차검증 결과 |
| `t005_logical_contract_v0.2~v0.3.json` | 논리 계약 이력과 활성본 |
| `t005_decision_register_v0.1~v0.3.json` | 결정 등록 이력과 활성본 |
| `t005_physical_contract_v1.0~v1.3.json` | 물리 계약 이력과 활성본 |
| `t005_local_technical_completion_evidence_20260730.json` | 작성자 로컬 기술 완료 증거 |
| `t005_author_isolated_reproduction_evidence_20260731.json` | 작성자 격리 재현 증거 |

기본 Snapshot 구조는 테이블 32개, 컬럼 526개, 물리 FK 85개, 논리
공통코드 참조 57개다.

## 5. 핵심 설계 결정

| 주제 | 현재 기준 |
| --- | --- |
| 식별자 | 내부 자동 증가 정수 PK, 외부 공개 UUID, 업무 코드를 분리 |
| Schema 변경 | Django Migration만 사용하고 적용된 Migration을 수정하지 않음 |
| 공통코드 | 계약 YAML·Django `TextChoices`·멱등 Seed를 일치시킴 |
| 상태 이력 | 요청 멱등성 원장과 Aggregate 상태 이력의 책임을 분리 |
| 합성 데이터 | `data/synthetic/fixtures/**`를 원본으로 사용하고 Upsert·Replay 검증 |
| Vector | pgvector `vector(1024)`와 Exact Search 사용, ANN Index는 미적용 |
| 삭제 | 계약 테이블과 감사 이력은 임의 삭제하지 않음 |

Legacy `usage_guidance_code`는 import 별칭으로만 취급하고 현행 필드는
`usage_guidance_status`를 사용한다. 방문 일정은
`preferred_date`, `confirmed_date`, `schedule_status`를 분리하며
방문 상태에는 `FOLLOW_UP_REQUIRED`를 포함한다.

## 6. 검증 명령

저장소 루트에서 실행한다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python .\scripts\database\validate_t005_schema.py
& $python .\scripts\database\audit_t005_implementation_readiness.py --require-ready
& $python .\backend\manage.py makemigrations --check --dry-run
```

실제 PostgreSQL 연결까지 검사할 때만 환경 변수를 확인한 뒤 다음 명령을
추가한다.

```powershell
& $python .\scripts\database\validate_t005_schema.py --verify-postgresql
```

`--require-wbs-complete`는 공식 완료 Evidence까지 검사한다. 작성자 로컬
기술 완료만으로 비작성자 리뷰나 PM 승인을 대신 기록하지 않는다.

## 7. 변경·검증 순서

1. 활성 ADR·Logical·Decision·Physical Contract를 구현 입력으로 고정한다.
2. 한 작업 단위의 Model·Migration만 변경한다.
3. `makemigrations --check --dry-run`과 빈 PostgreSQL Migration을 즉시
   검증한다.
4. PK·FK·UNIQUE·CHECK·Index와 계약 코드·Seed를 검증한다.
5. Seed와 격리 Importer는 두 번 실행해 두 번째 실행의 비의도 신규 생성을
   허용하지 않는다.
6. API Serializer·OpenAPI·예시와 식별자 의미를 대조한다.
7. 집중 테스트 후 SQLite·PostgreSQL·Data 회귀를 실행한다.
8. 실행 증거와 변경 이력을 갱신한 뒤 비작성자에게 재현을 요청한다.

기본 `waterbridge`에는 합성 Handoff Importer를 실행하지 않는다.
Importer는 새 빈 격리 DB에서 Migration 후 실행·Replay하고 검증 뒤
격리 DB를 제거한다.

## 8. 완료 경계

현재 `32/32`와 Auditor `READY`는 작성자 환경의 기술 검증 결과다.
공식 T-005 완료에는 다음 증거가 모두 필요하다.

- 동일 후보 SHA의 비작성자 독립 PostgreSQL 재현
- 내부 PK·공개 UUID·업무 코드와 UUID-only JWT 계약 검토
- Web·Mobile·AI 소비 호환성 확인
- PM의 완료 승인과 `main` 병합 SHA

후보 SHA나 활성 계약이 바뀌면 빈 PostgreSQL·Seed·Importer·전체 회귀를
같은 SHA에서 다시 실행한다.

## 9. 이력 관리

과거 v0.1~v1.6 서술과 Wave별 세부 실행 기록은 Git history에 보존한다.
현재 Model·Migration 변경은
[데이터베이스 Schema·Migration 구현 가이드](../../individual/jiyong/데이터베이스/데이터베이스_스키마_마이그레이션_구현_가이드.md)를 따르며,
이 README에는 현재 계약·검증 방법·완료 경계만 유지한다.

정확한 과거 원문은 Git 이력에서 확인하며, 이전 계약 JSON·ERD·Evidence
파일은 감사 추적을 위해 그대로 보존한다.

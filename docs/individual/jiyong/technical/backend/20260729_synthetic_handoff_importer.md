# 합성 데이터 정식 적재기 개발·인계서

- 작성일: 2026-07-29
- 담당 영역: Backend·Database
- 대상 협업자: Data/QA, Backend, PM
- 구현 상태: SQLite 자동화와 빈 격리 PostgreSQL smoke/full 검증 완료
- 제외 범위: 기본 `watercare` DB Import, 운영·개인정보 데이터 적재

> 후속 통합 검증(2026-07-29): 아래의 PostgreSQL 미검증 표기는
> Importer 구현 단계 당시의 범위를 설명한다. 이후 동일 코드로 격리
> PostgreSQL의 smoke 37건·full 367건, dry-run rollback 및 재실행
> 멱등성을 확인했다. 최종 근거는 [PostgreSQL 합성 Handoff Runtime 검증·인계서](../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md)다.
> 현재 설치·Migration·Seed의 단일 원본은
> [Django·PostgreSQL 공유 패키지 인계서 v1.3](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)이다.
> 실제 고객·운영 데이터와 기본 `watercare` DB Import는 여전히 범위
> 밖이다.

## 1. 목적과 완료 범위

`data/synthetic/fixtures`의 승인 합성 데이터 367건을 Backend 도메인
모델에 원자적으로 적재하는 Django 관리 명령을 구현했다. 원본 fixture의
정수 `id`는 실행 중 관계 해석에만 사용하고 DB 식별자로 저장하지 않는다.
공개 UUID를 먼저 조회하고 업무 키를 보조 검증해 서로 다른 레코드로
해석되면 전체 작업을 중단한다.

이번 작업의 완료 범위는 다음과 같다.

1. 정확히 37건인 `db-smoke`와 367건인 `db-full` 적재 프로필
2. 모든 쓰기와 사후 검증을 하나의 DB 트랜잭션으로 묶은 적재 서비스
3. 도메인·배치·원장 행 쓰기를 롤백하는 `--dry-run`
4. 공개 UUID 우선·업무 키 교차 확인·불변 관계 충돌 차단
5. 변경 필드만 갱신하고 같은 입력 재실행 시 생성·수정 0건을 보장하는
   반복 안전성
6. 모든 원본 행의 결과와 원본/대상 UUID·업무 키·행 SHA-256을 기록하는
   배치 원장
7. 문의·방문 최종 상태와 전이 이력, 전이 이력과 감사 이벤트의 전수 검증
8. Django 관리 명령과 SQLite 통합 테스트

도메인 모델과 Migration의 선행 구현 내용은
[합성 데이터 도메인 스키마·Migration 개발 인계서](20260729_synthetic_domain_schema_migration.md)를
참조한다.

## 2. 구현 산출물

| 계층 | 파일 | 역할 |
|---|---|---|
| 설정 | [base.py](../../../../../backend/config/settings/base.py) | `OperationsConfig` 등록 |
| 앱 | [apps.py](../../../../../backend/apps/operations/apps.py) | Operations 앱 설정 |
| 원장 모델 | [synthetic_import_ledger.py](../../../../../backend/apps/operations/models/synthetic_import_ledger.py) | 배치·원본 행별 적재 결과와 provenance 저장 |
| Migration | [0001_initial.py](../../../../../backend/apps/operations/migrations/0001_initial.py) | 원장 테이블, 제약, 인덱스 생성 |
| Repository | [operations_repository.py](../../../../../backend/apps/operations/repositories/operations_repository.py) | 공개 UUID/업무 키 해석, 충돌 검출, `full_clean()`, 변경 필드 저장, 원장 기록 |
| Service | [operations_service.py](../../../../../backend/apps/operations/services/operations_service.py) | fixture 로딩·closure 선택·순차 적재·사후 검증·트랜잭션 제어 |
| CLI | [import_synthetic_handoff.py](../../../../../backend/apps/operations/management/commands/import_synthetic_handoff.py) | `smoke`, `full`, `--dry-run` 실행과 단일 JSON 결과 출력 |
| 통합 테스트 | [test_synthetic_handoff_import.py](../../../../../backend/tests/integration/operations/test_synthetic_handoff_import.py) | 무기록 dry-run, 반복 안전성, 전수 적재, 충돌 롤백 검증 |

fixture·Crosswalk·Data QA 코드는 이 Backend 적재기 작업에서 수정하지
않는다. 적재기는 현재 파일의 값과 버전을 읽어 소비하며, 원본 변경 책임은
Data/QA 관할에 남는다.

## 3. 처리 순서와 트랜잭션 경계

적재 순서는 FK 의존성을 따라 고정했다.

```text
users
→ customer_profiles
→ products
→ customer_products(PROJECTED)
→ subscriptions
→ inquiries + representative symptoms
→ consultations
→ visits
→ followup_confirmations
→ care_histories
→ inquiry_status_histories
→ audit_events
→ 사후 검증
→ batch/item ledger
→ commit 또는 dry-run rollback
```

`customer_products`는 별도 Backend 테이블을 만들지 않고
`CustomerSubscription`의 원본 고객제품 UUID·일련번호·설치일·설치 주소로
투영한다. 원장에서는 해당 행을 `PROJECTED`로 기록해 367개 입력 중 누락된
행이 없도록 했다.

모든 단계는 `transaction.atomic()` 안에서 실행한다. 모델 검증, FK 관계,
식별자 충돌, source closure, 집계 상태, 감사 이력 중 하나라도 실패하면
도메인 레코드와 원장 모두 롤백된다. `--dry-run`도 동일한 쓰기·검증 경로를
끝까지 실행한 뒤 의도적으로 트랜잭션을 롤백한다.

PostgreSQL Sequence는 일반 테이블 행과 같은 방식으로 트랜잭션
롤백되지 않을 수 있다. 따라서 dry-run 후 도메인·배치·원장 행이 0건인
것은 보장하지만, 자동 증가 Sequence 값까지 실행 전과 같다고 보장하지
않는다. 이 이유만으로도 dry-run은 기존 데이터를 가진 기본 DB가 아니라
폐기 가능한 새 빈 격리 DB에서 수행한다.

## 4. 프로필과 완료 기준

| 프로필 | 원본 행 | 신규 빈 DB 1차 예상 | 변경 없는 2차 예상 | 추가 검증 |
|---|---:|---|---|---|
| `db-smoke` | 37 | `CREATED 31`, `PROJECTED 6` | `CREATED 0`, `UPDATED 0`, `UNCHANGED 31`, `PROJECTED 6` | 고객제품 투영 6건 |
| `db-full` | 367 | `CREATED 355`, `PROJECTED 12` | `CREATED 0`, `UPDATED 0`, `UNCHANGED 355`, `PROJECTED 12` | 투영 12건, 집계 26건, 감사↔이력 125건 |

`smoke`와 `full`은 각각 `db-smoke`, `db-full`의 CLI 별칭이다. Smoke는
`SYN-JAC104-001`부터 `SYN-JAC104-006`까지의 시나리오와 필요한
사용자·고객·제품·구독·상담·방문 closure만 선택한다.

## 5. 식별자·갱신·시간 정책

| 항목 | 적용 정책 | 오류 방지 효과 |
|---|---|---|
| 조회 순서 | 공개 UUID 우선 조회 후 업무 키 결과와 교차 확인 | 같은 업무 키가 다른 UUID에 붙는 silent merge 방지 |
| 불변 값 | 업무 키와 원본 소유·연결 관계는 기존 행과 다르면 즉시 충돌 | 문의·구독·상담·방문이 다른 aggregate에 재연결되는 오류 방지 |
| 갱신 | 비교 결과가 다른 필드만 `update_fields`로 저장 | 불필요한 쓰기와 `updated_at` 변동 방지 |
| 모델 검증 | 신규·변경 레코드에 `full_clean()` 실행 | 역할·상태·필드 조합 검증 우회 방지 |
| 원본 정수 ID | 메모리 관계 맵의 임시 키로만 사용 | fixture 로컬 PK와 Backend PK의 결합 방지 |
| 원본 시간 | source에 있는 시각만 보존하고 없는 완료 시각은 생성하지 않음 | 추정 시각이 감사 근거로 저장되는 오류 방지 |
| 사용자 비밀번호 | 모든 합성 사용자는 사용 불가 비밀번호로 저장 | fixture 기반 공개 로그인·공통 비밀번호 노출 방지 |
| 직원 번호 | 고객은 `NULL`, 직원 역할은 합성 사용자 번호 사용 | 사용자 역할별 DB 제약 충족 |

문의의 대표 증상은 문의 공개 UUID에 대한 UUID v5로 결정적으로 생성한다.
구조화 payload에는 배정자의 공개 UUID만 넣으며 fixture 정수 FK는 넣지
않는다.

## 6. 적재 원장과 provenance

각 실제 실행은 `SyntheticImportBatch` 한 건과 source 행 수만큼의
`SyntheticImportItem`을 저장한다.

| 원장 값 | 의미 |
|---|---|
| `dataset_version` | `data/config/pipeline.json`의 현재 데이터셋 버전 |
| `mapping_version` | `data/config/handoff/backend_import_crosswalk.json`의 현재 매핑 버전 |
| `fixture_set_sha256` | 12개 fixture 배열을 정규 JSON으로 직렬화한 뒤 고정 순서로 계산한 세트 SHA-256 |
| `source_dataset`, `source_public_id`, `source_business_key` | 원본 행 추적 정보 |
| `source_sha256` | 원본 행의 정규 JSON SHA-256 |
| `action` | `CREATED`, `UPDATED`, `UNCHANGED`, `PROJECTED` |
| `target_model`, `target_public_id`, `target_business_key` | 적재·투영 대상 추적 정보 |

배치에는 프로필별 정확한 source count와 네 action 합계가 source count와
같아야 한다는 DB 제약을 둔다. Dry-run 원장은 도메인 쓰기와 함께
롤백되므로 성공 결과 JSON의 batch 식별자는 `null`이다.

## 7. 실행 가이드

아래 명령은 저장소의 `backend` 디렉터리에서 실행한다. 실행 전
[v1.3 매뉴얼](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)에
따라 새 빈 격리 PostgreSQL DB를 만들고 `POSTGRES_DB`가 `watercare`가
아닌지 확인한다. 기본 `watercare`에서는 아래 실제 Import뿐 아니라
`--dry-run`도 실행하지 않는다.

```powershell
$env:POSTGRES_DB = 'watercare_synthetic_isolated_<yyyymmdd>'
if ($env:POSTGRES_DB -eq 'watercare') {
    throw '합성 Importer는 기본 watercare DB에서 실행할 수 없습니다.'
}

.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate --noinput

.\.venv\Scripts\python.exe manage.py import_synthetic_handoff --profile smoke --dry-run
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff --profile smoke
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff --profile full --dry-run
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff --profile full
```

안전한 적용 순서는 다음과 같다.

1. `check`와 `migrate`가 통과하는지 확인한다.
2. `smoke --dry-run`의 source count가 37인지 확인한다.
3. 실제 `smoke`를 두 번 실행하고 2차 결과의 생성·수정이 모두 0인지
   확인한다.
4. `full --dry-run`의 source count 367, aggregate 26,
   audit-history 125를 확인한다.
5. 실제 `full`을 실행한다.
6. 같은 `full`을 한 번 더 실행하고 생성·수정 0을 확인한다.

명령은 성공 시 한 줄짜리 JSON 문서 하나만 출력한다. `CommandError`가
발생하면 일부 적재를 성공으로 간주하지 말고 원본 식별자·관계·코드 값을
수정한 뒤 dry-run부터 다시 시작한다.

현재 기본 `watercare`의 `SYN-CUSTOMER-001` 관련 기존 레코드는 canonical
fixture와 공개 UUID가 다르다. 따라서 그 DB에서 importer dry-run을
실행하면 `public UUID mismatch`로 실패하는 것이 예상 결과다. 이 충돌을
자동 병합하거나 기존 UUID를 fixture 값으로 바꾸지 않는다. 기본 DB의
Migration·Demo Seed 검증과 합성 Import 검증은 서로 다른 절차다.

## 8. 검증 결과

다음 표는 Importer 구현 단계에서
[SQLite 테스트 설정](../../../../../backend/config/settings/test.py)을
사용한 선행 검증 기록이다. 아래 수치는 후속 PostgreSQL 실측으로
덮어쓰지 않는다.

| 검증 단계 | 결과 |
|---|---|
| Python 정적 컴파일 | 통과 |
| Django `check` | 오류 0건 |
| Operations Migration drift | `No changes detected` |
| 빈 SQLite `migrate` | 전체 Migration 적용 성공 |
| Smoke dry-run | 37건 처리 후 사용자·배치·원장 0건 |
| Smoke 실제 1차/2차 | `31 CREATED + 6 PROJECTED` / `0 UPDATED + 31 UNCHANGED + 6 PROJECTED` |
| Full 실제 1차/2차 | `355 CREATED + 12 PROJECTED` / `0 UPDATED + 355 UNCHANGED + 12 PROJECTED` |
| Full 물리 레코드 | 사용자 16, 고객 12, 제품 1, 구독 12, 문의 22, 증상 22, 상담 12, 방문 4, 후속 확인 1, 케어 25, 이력 125, 감사 125 |
| 적재기 집중 테스트 | 4개 통과 |
| 관련 도메인 회귀 묶음 | 57개 통과 |
| diff whitespace·라인 길이 | 이상 없음 |

집중 테스트는 다음을 자동 확인한다.

- 빈 DB dry-run과 기존 dirty row dry-run 모두 쓰기 0건
- CLI stdout이 중복되지 않은 단일 JSON 문서
- Smoke 1차·2차 반복 안전성과 dirty 필드 1건만 복구
- Full source 원장 367건과 데이터셋별 정확한 행 수
- 모든 합성 사용자의 unusable password와 역할별 직원 번호
- source timestamp 보존과 문의 채널 미추정
- 문의·방문 최종 상태/버전과 최신 이력 일치
- 감사 이벤트 125건과 연결 이력의 이벤트·행위자·버전·키·시각 일치
- 공개 UUID와 업무 키 충돌 시 전체 롤백

위 SQLite 단계만으로는 PostgreSQL 적용 성공을 의미하지 않는다. 이후
별도의 빈 격리 PostgreSQL 16.14에서 Migration, smoke/full dry-run,
1차 실제 적재와 재실행을 검증했다. 해당 실측은
[Runtime 검증서](../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md)에
누적되어 있다.

반면 기본 `watercare`에는 합성 관련 기존 9개 Migration과
`workflow.0003`을 적용하고 기존 행 수 보존, Workflow `changed_at`
11건 보정, Demo Seed 2회 비의도 중복 0을 확인했지만 importer는
실행하지 않았다. 기본 DB의 importer dry-run은 UUID mismatch로 예상
실패하며, 성공 검증 대상으로 사용하지 않는다.

## 9. 협업 인계

| 담당 | 확인할 내용 | 완료 기준 |
|---|---|---|
| 김은진(Data/QA) | fixture 12종, pipeline/Crosswalk 버전, 해시·코드 계약이 적재기 입력과 같은지 검토 | Data QA 통과 후 `full --dry-run` 367건 |
| 최지용(Backend/DB) | Migration 적용, 충돌 오류 분석, 원장·도메인 수 검토 | 새 빈 격리 DB에서 smoke/full 2차 생성·수정 0건 |
| 윤승혁(PM/Workflow) | 문의·방문 상태와 125개 전이·감사 이벤트가 승인 상태 계약과 같은지 검토 | aggregate 26·audit-history 125 검증 |
| 팀 QA | PostgreSQL 재현과 실패 롤백, API가 적재 데이터 조회·권한 규칙을 지키는지 검증 | PostgreSQL 증적과 API E2E 결과 확보 |

### 변경 시 주의사항

1. fixture 행·Crosswalk를 Backend에서 임의 수정하지 않는다.
2. fixture가 추가되면 프로필별 정확한 count, closure, 원장 DB 제약,
   테스트 기대값을 하나의 변경으로 검토한다.
3. 업무 키나 공개 UUID 정책을 완화해 충돌 행을 자동 병합하지 않는다.
4. `bulk_create()`처럼 모델 검증을 우회하는 경로로 바꾸지 않는다.
5. 운영 데이터나 개인정보를 이 합성 전용 명령에 섞지 않는다.
6. `DB_FULL_VERIFIED`는 검증한 빈 격리 DB와 합성 367행 범위에만
   사용하며 운영 적재 완료로 확장하지 않는다.
7. 기본 `watercare`에서는 importer와 `--dry-run`을 모두 금지한다.
   UUID mismatch는 데이터 경계가 작동한 예상 실패이며 우회하지 않는다.
8. dry-run 후 도메인·배치·원장 행이 롤백돼도 PostgreSQL Sequence가
   실행 전 값으로 돌아갔다고 가정하지 않는다.

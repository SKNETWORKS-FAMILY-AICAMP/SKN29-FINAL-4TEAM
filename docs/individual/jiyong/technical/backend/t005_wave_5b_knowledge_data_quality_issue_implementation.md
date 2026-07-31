# T-005 Wave 5B `knowledge_data_quality_issue` 구현·검증·인계 보고서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 담당: 최지용  
> 상태: `LOCAL_VERIFIED`  
> 구현 범위: 지식 데이터 품질 이슈 1개 테이블

## 1. 결과 요약

지식 수집·파싱·페이지·청크 처리 과정에서 발견한 품질 이슈를 보존하는
`knowledge_data_quality_issue` 테이블을 Django Runtime Model과 번호
Migration으로 구현했다.

테이블 사전의 UUID `id` 초안을 현재 식별자 전환 원칙에 맞춰 내부
`BigAutoField id`와 외부 공개용 unique UUID `public_id`로 분리했다.
`ingestion_batch`는 선택적인 실행 문맥이며, 실제 품질 이슈 대상은
`document`, `page`, `chunk` 중 정확히 하나만 허용한다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Evidence Migration drift | 통과, `No changes detected` |
| SQLite 집중 테스트 | `25 passed, 1 skipped` |
| PostgreSQL 16 집중 테스트 | `26 passed` |
| Evidence 전체 단위 회귀 | `94 passed, 6 skipped` |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `0006 → 0005 → 0006` | 테이블 제거·복원 통과 |
| 빈 PostgreSQL 16 전체 Migration | 통과 |
| PostgreSQL catalog | bigint·UUID 타입, CHECK 3개, 명세 Index 4개 확인 |
| PostgreSQL 유효·무효 데이터 | 대상·JSON object·해결 묶음 규칙 통과 |
| PostgreSQL 부모 보호 | 선택 FK 5종의 `PROTECT` 확인 |
| PostgreSQL `0006 → 0005 → 0006` | 테이블 제거·복원 통과 |
| 검증 임시 자원 | SQLite 파일 및 PostgreSQL 전용 DB 제거 완료 |

위 결과는 이 테이블의 Model·Migration·DB 구조 범위에 대한 완료
증거다. importer, 품질 탐지 서비스, API, 운영 Seed 및 T-005 전체
완료를 의미하지는 않는다.

## 2. 기준 문서와 적용 순서

| 우선순위 | 기준 | 적용 내용 |
| ---: | --- | --- |
| 1 | 저장소 외부 `Daily_Process/지침서` 최신본 | DB 담당 경계, 작업 후 즉시 검증, 기존 Migration 불변, 협업 인계 |
| 2 | [식별자 ADR 0010](../../../../adr/0010-t005-three-layer-identifier-bridge.md) | 내부 bigint PK와 공개 UUID 분리 |
| 3 | [Physical Contract v1.2](../../../../database/t-005/t005_physical_contract_v1.2.json) | 최신 식별자·FK 물리 규칙 |
| 4 | [테이블 사전](../../../../database/watercare_table_dictionary.md) | 필드, 관계, 구조 제약 및 조회 Index 초안 |
| 5 | 현재 Runtime Model·Migration graph | `accounts.0003`, `evidence.0005` 이후 순서 고정 |

저장소 외부 지침서는 팀원이 Git pull한 환경에서 열 수 없는 절대경로이므로
이 문서에는 로컬 경로 하이퍼링크를 넣지 않았다.

## 3. 구현 산출물

| 산출물 | 역할 |
| --- | --- |
| [DataQualityIssue Model](../../../../../backend/apps/evidence/models/data_quality_issue.py) | 필드, 관계, Model validation, DB CHECK 및 Index 선언 |
| [Evidence Model export](../../../../../backend/apps/evidence/models/__init__.py) | Django Runtime registry에 `DataQualityIssue` 공개 |
| [evidence.0006 Migration](../../../../../backend/apps/evidence/migrations/0006_dataqualityissue.py) | 테이블·FK·CHECK·Index 생성 |
| [집중 단위 테스트](../../../../../backend/tests/unit/evidence/test_data_quality_issue_model.py) | 구조·유효/무효 데이터·PROTECT·PostgreSQL catalog 검증 |
| [선행 DocumentChunk Model](../../../../../backend/apps/evidence/models/document_chunk.py) | 청크 대상 FK와 JSON object DB expression 제공 |
| [선행 evidence.0005](../../../../../backend/apps/evidence/migrations/0005_documentchunk.py) | 직전 Migration 기준선 |

선행 `evidence.0005_documentchunk.py`는 수정하지 않았다. 이번 변경은
새 `evidence.0006_dataqualityissue.py`로만 이어 붙였다.

## 4. Runtime 필드

테이블 사전의 18개 초안 필드는 식별자 분리로 Runtime에서 19개
로컬 필드가 된다.

| 구분 | 필드 | 구현·무결성 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK |
| 공개 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 수정 불가 |
| 수집 문맥 | `ingestion_batch_id` | nullable bigint FK, `PROTECT` |
| 품질 대상 | `document_id` | nullable bigint FK, `PROTECT` |
| 품질 대상 | `page_id` | nullable bigint FK, `PROTECT` |
| 품질 대상 | `chunk_id` | nullable bigint FK, `PROTECT` |
| 이슈 분류 | `issue_type_code` | 필수 open code, `varchar(40)` |
| 검증 규칙 | `validation_rule_code` | nullable `varchar(80)` |
| 검증기 버전 | `validator_version` | nullable `varchar(50)` |
| 심각도 | `severity_code` | 필수 open code, 기본값 `ERROR` |
| 이슈 내용 | `issue_message` | 필수 text |
| 상세 자료 | `details` | 필수 JSON object, 기본값 `{}` |
| 처리 상태 | `status_code` | 필수 open code, 기본값 `OPEN` |
| 탐지 시각 | `detected_at` | 현재 시각 기본값 |
| 해결 담당 | `resolved_by_id` | nullable User bigint FK, `PROTECT` |
| 해결 시각 | `resolved_at` | nullable |
| 해결 내용 | `resolution_note` | nullable text |
| 감사 시각 | `created_at`, `updated_at` | 자동 생성·갱신 |

## 5. DB 제약조건

| 이름 | 강제 규칙 |
| --- | --- |
| `ck_quality_issue_target` | `document`, `page`, `chunk` 중 정확히 하나만 설정 |
| `ck_quality_issue_resolution_bundle` | `resolved_by`, `resolved_at`, `resolution_note`를 모두 설정하거나 모두 NULL |
| `ck_quality_issue_details_object` | `details`는 JSON array·scalar가 아닌 object |

`ingestion_batch_id`는 품질 대상 수 계산에서 제외한다. 한 이슈가 특정
수집 배치에서 탐지되었더라도 실제 대상은 문서·페이지·청크 중 하나여야
하기 때문이다.

해결 필드 묶음은 현재 `status_code` 값과 독립적이다. 따라서 구조적으로는
`OPEN` 상태에 완성된 해결 묶음을 저장하거나 `RESOLVED` 상태에 해결 묶음
없이 저장할 수 있다. 이는 상태 수명주기가 확정되지 않은 상황에서
미승인 정책을 DB에 선반영하지 않기 위한 의도적인 경계다.

## 6. Index

| 이름 | 컬럼·조건 | 용도 |
| --- | --- | --- |
| `ix_quality_issue_open` | `(severity_code, detected_at)` WHERE `status_code IN ('OPEN','IN_REVIEW')` | 미처리·검토 중 이슈 우선 조회 |
| `ix_quality_issue_document` | `(document_id, page_id)` | 문서 범위 이슈 조회 |
| `ix_quality_issue_page` | `(page_id)` | 페이지별 이슈 조회 |
| `ix_quality_issue_chunk` | `(chunk_id)` | 청크별 이슈 조회 |

`ix_quality_issue_open`의 `OPEN`, `IN_REVIEW`는 조회 최적화 조건일 뿐
허용 상태 집합을 정의하지 않는다. 다른 상태 코드의 저장은 차단하지
않는다.

FK 필드에는 Django 자동 단일 Index가 중복 생성되지 않도록
`db_index=False`를 적용하고, 명세에 있는 네 Index만 명시적으로 관리한다.

## 7. 코드 집합과 상태 정책 보류

테이블 사전에는 다음 후보 값과 허용값 CHECK가 설계 제안으로 적혀 있다.

| 코드 그룹 | 사전 후보 | 이번 구현 |
| --- | --- | --- |
| `QUALITY_ISSUE_TYPE` | `MISSING_METADATA`, `HASH_MISMATCH` 등 | open `CharField` |
| `SEVERITY` | `INFO`, `WARNING`, `ERROR`, `CRITICAL` | open `CharField`, 기본값만 `ERROR` |
| `ISSUE_STATUS` | `OPEN`, `IN_REVIEW`, `RESOLVED`, `WAIVED` | open `CharField`, 기본값만 `OPEN` |

현재 [canonical code 계약 폴더](../../../../../contracts/codes)에는 위 세
그룹 YAML이 없다. 따라서 다음 항목은 구현하지 않았다.

- `TextChoices`
- 허용값 `CHECK`
- `RESOLVED`·`WAIVED`에 종속된 해결 필드 규칙
- 상태 전이 규칙

후보 값을 먼저 고정하면 데이터·QA 담당자의 승인된 코드가 달라질 때
교정 Migration과 기존 데이터 정규화가 연쇄 발생한다. 세 YAML이 승인되면
같은 변경 단위에서 TextChoices, DB CHECK, common-code Seed 및
producer/consumer parity 테스트를 함께 추가해야 한다.

## 8. Migration 순서와 rollback

직접 의존 순서는 다음과 같다.

```text
accounts.0003_promote_integer_primary_keys
evidence.0005_documentchunk
  └─ evidence.0006_dataqualityissue
```

SQLite와 PostgreSQL 16에서 각각 다음 절차를 실행했다.

```text
빈 DB 전체 migrate
knowledge_data_quality_issue 존재와 0006 적용 기록 확인
evidence.0005로 rollback
테이블 부재와 0006 기록 제거 확인
evidence.0006 재적용
테이블 존재와 0006 기록 복원 확인
```

두 DB 모두 동일하게 통과했다. PostgreSQL에서는 재적용 뒤 집중 테스트를
통해 물리 타입, CHECK, 부분 Index와 FK `PROTECT`까지 확인했다.

## 9. 작업 → 즉시 검증 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·Physical v1.2·사전·현재 `0005` 비교 | 필드·관계·정책 보류 분리 | 구현 범위 확정 |
| 2 | Model 및 Runtime export 추가 | Django check | 0 issues |
| 3 | 번호 Migration `evidence.0006` 추가 | Migration drift | 0 |
| 4 | 구조·유효/무효·보호 테스트 추가 | SQLite 집중 테스트 | `25 passed, 1 skipped` |
| 5 | 빈 SQLite 전체 Migration | 테이블·적용 기록 확인 | 통과 |
| 6 | SQLite rollback·reapply | 제거·복원 확인 | 통과 |
| 7 | 빈 PostgreSQL 16 전체 Migration | `evidence.0006` 적용 | 통과 |
| 8 | PostgreSQL 집중 테스트 | catalog·데이터·PROTECT | `26 passed` |
| 9 | PostgreSQL rollback·reapply | 제거·복원 확인 | 통과 |
| 10 | Evidence 전체 회귀 | 기존 Evidence 모델 영향 확인 | `94 passed, 6 skipped` |
| 11 | Django check·Evidence drift 재검증 | 0 issues·No changes | 통과 |
| 12 | 임시 자원 정리 | 파일·전용 DB 부재 확인 | 통과 |

SQLite 빈 DB 1차 실행에서는 존재하지 않는 임시 상위 디렉터리를 지정해
`unable to open database file`이 발생했다. 모델이나 Migration 오류가
아니었으며, 프로젝트에 이미 존재하는 `.runtime` 임시 경로로 바꾼 뒤
동일 절차 전체가 통과했다. 검증 완료 후 해당 파일은 제거했다.

## 10. 전체 회귀와 동시 작업 경계

Wave 5B Evidence 회귀가 통과한 뒤 전체 백엔드 테스트를 실행하던 시점에
공유 작업트리의 다음 Wave 6A `CustomerActionResult`가 Runtime Model
export와 `inquiries.0010` 작성 사이의 중간 상태였다.

그 결과 전체 테스트용 SQLite DB에는 `support_customer_action_result`
테이블이 없는데 Runtime 삭제 수집기는 해당 모델을 조회했고, User 부모
삭제를 검사하는 여러 앱에서 같은 `no such table` 오류가 연쇄 발생했다.
당시 전체 결과는 `662 passed, 11 failed, 9 skipped`였다.

실패 11건 중 10건은 동일한 미생성 테이블 조회이며, 1건은 readiness
테스트가 아직 해당 파일을 placeholder로 기대한 항목이다. Wave 5B의
대상·JSON·해결 묶음·catalog 검사는 SQLite와 PostgreSQL 격리 환경에서
모두 통과했으므로 이 스냅샷은 Wave 5B 결함으로 분류하지 않는다.

Wave 6A의 Model·Migration·readiness 정합화가 끝난 후 루트 통합 작업에서
전체 백엔드 회귀를 다시 실행해야 한다. 공유 작업트리의 다른 Wave 파일은
이번 작업에서 수정하지 않았다.

## 11. 재현 명령

저장소 루트 기준 집중 Gate:

```powershell
& .\backend\.venv\Scripts\python.exe `
    .\backend\manage.py check

& .\backend\.venv\Scripts\python.exe `
    .\backend\manage.py makemigrations evidence --check --dry-run

& .\backend\.venv\Scripts\python.exe -m pytest `
    .\backend\tests\unit\evidence\test_data_quality_issue_model.py -q

& .\backend\.venv\Scripts\python.exe -m pytest `
    .\backend\tests\unit\evidence -q
```

PostgreSQL 검증은 운영·공용 개발 DB가 아닌 빈 격리 DB에서 실행한다.

```powershell
$env:POSTGRES_DB = "<isolated-empty-database>"

& .\backend\.venv\Scripts\python.exe `
    .\backend\manage.py migrate --noinput `
    --settings=config.settings.base

& .\backend\.venv\Scripts\python.exe -m pytest `
    .\backend\tests\unit\evidence\test_data_quality_issue_model.py `
    -q --ds=config.settings.base

& .\backend\.venv\Scripts\python.exe `
    .\backend\manage.py migrate evidence 0005 --noinput `
    --settings=config.settings.base

& .\backend\.venv\Scripts\python.exe `
    .\backend\manage.py migrate evidence 0006 --noinput `
    --settings=config.settings.base
```

공용 DB에서 rollback 명령을 직접 실행하면 안 된다.

## 12. 협업 인계

| 주체 | 인계 내용 |
| --- | --- |
| 최지용·DB 담당 | `evidence.0006`, 세 CHECK, 네 Index, FK 이름과 기존 `0005` 불변 유지 |
| 윤승혁·PM | 세 코드 그룹 YAML 값·버전·소유자와 상태 수명주기 승인 |
| 김은진·데이터/QA | 이슈 importer가 `details` object와 정확히 한 대상 규칙을 지키는지 fixture 제공 |
| 이동윤·AI/RAG | 파싱·청크·검색 품질 탐지 결과를 document/page/chunk 중 한 단계에 귀속 |
| Backend 서비스 담당 | 해결 필드 세 개를 한 transaction에서 설정·해제하고 승인 전 상태 종속 로직을 추가하지 않음 |
| 통합 담당 | Wave 6A 안정화 후 전체 backend 회귀 및 중앙 T-005 readiness 갱신 |

## 13. 잔여 작업과 비범위

- `QUALITY_ISSUE_TYPE`, `SEVERITY`, `ISSUE_STATUS` canonical YAML 승인
- 승인된 코드의 TextChoices·DB CHECK·Seed parity 구현
- 이슈 탐지·해결 상태 전이 Service와 권한 정책
- 정식 importer와 367건 운영 적재 연동
- Data QA 결과에서 이슈 레코드를 생성하는 transaction
- 조회·해결 API 및 운영 화면
- 알림·재검증·감사 이벤트 연동
- Wave 6A 안정화 후 전체 backend 회귀 재실행
- 중앙 T-005 readiness와 WBS 완료 판단

## 14. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·`evidence.0006`·제약·Index·SQLite/PostgreSQL·rollback·회귀·동시 작업 경계·협업 인계 기록 |

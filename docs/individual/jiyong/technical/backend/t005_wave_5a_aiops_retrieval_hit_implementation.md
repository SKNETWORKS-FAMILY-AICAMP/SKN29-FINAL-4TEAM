# T-005 Wave 5A `aiops_retrieval_hit` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 범위: AI 검색 결과 1개 테이블

## 1. 결과 요약

검색 실행별 후보 문서 청크의 순위, 네 종류 점수, 적용성 검토 상태와
실제 답변 선택 여부를 보존하는 `aiops_retrieval_hit`를 Audit 앱의
Django Runtime Model과 번호 Migration으로 구현했다.

역사 테이블사전의 14개 논리 필드를 보존하고 식별자 ADR에 따라 내부
`BigAutoField id`와 외부 공개용 unique UUID `public_id`를 분리했다.
AIRetrievalRun과 DocumentChunk는 현재 Runtime bigint PK를 참조하므로
실제 테이블은 15개 컬럼이다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | test·local 설정 모두 통과, 0 issues |
| Audit·Evidence Migration drift | 통과, `No changes detected` |
| 신규 집중 테스트 | `18 passed` |
| Audit·Evidence 전체 단위 회귀 | `159 passed, 6 skipped` |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `audit.0004 → 0003 → 0004` | 테이블·제약·Index 제거와 복원 통과 |
| 빈 PostgreSQL 전체 Migration | 통과 |
| PostgreSQL 물리 Catalog | 15컬럼, `numeric(10,6)` 4개, Index 8개 확인 |
| PostgreSQL 유효 쓰기 | Exact vector·open selected 상태·보류 reason 정책 통과 |
| PostgreSQL 위반 쓰기 | DB 위반 9종 차단 |
| PostgreSQL 부모 보호 | RetrievalRun·DocumentChunk 직접 DELETE 2종 차단 |
| PostgreSQL `audit.0004 → 0003 → 0004` | 테이블 부재 후 동일 Catalog 복원 |
| 임시 검증 자원 | SQLite 파일·검증 스크립트 제거, PostgreSQL DB 부재 확인 |

이 결과는 `aiops_retrieval_hit` 한 테이블의 구현·로컬 DB 검증 결과이다.
검색 Service, RetrievalRun terminal 전환, EvidenceLink, API, 운영 적재와
중앙 T-005 readiness는 이번 Wave에서 수정하거나 완료로 선언하지 않았다.

## 2. 기준 문서 적용 순서

| 우선 | 기준 | 이번 구현의 적용 내용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | Backend·DB 담당 경계, 작업 후 즉시 검증, Exact Search와 ANN 제외 |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 bigint PK, 공개 UUID, 내부 bigint FK |
| 3 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 최신 식별자·canonical code 정책 |
| 4 | [테이블사전](<../../../../database/watercare_table_dictionary.md#30-aiops_retrieval_hit--rag-검색-결과>) | 14개 역사 필드, 점수·순위·선택·후속 복합키 설계 |
| 5 | [과거 Schema v3](<../../../../database/t-005/watercare_schema_v3.json>) | 역사 초안과의 차이 확인 |
| 6 | [공통 개발 규칙](<../../../../planning/md/공통 개발 규칙.md>) | MVP Cosine Exact Search, HNSW·IVFFlat 미사용, Top-5 |

Physical Contract v1.2에는 `aiops_retrieval_hit` 개별 override가 없고,
`EVIDENCE_APPLICABILITY`는 standard code나 canonical YAML로 승인되지
않았다. 따라서 식별자 공통 정책은 최신 계약을 따르고 나머지 구조는
테이블사전을 사용하되, 미승인 상태값에 의존하는 규칙은 분리했다.

## 3. 계약 비교와 결정

| 항목 | 역사·현재 자료 | 이번 구현 | 판단 이유 |
| --- | --- | --- | --- |
| 기본 PK | 테이블사전 UUID `id` | bigint 자동 증가 `id` | ADR 0010이 최신 확정 결정 |
| 공개 식별자 | 별도 필드 없음 | unique UUID `public_id` | 외부 식별자와 내부 조인 분리 |
| 부모 FK | 역사 UUID | bigint PROTECT 2개 | 현재 부모 Runtime PK와 일치 |
| 점수 타입 | `numeric(10,6)` 4개 | Decimal 10,6 4개 | 정밀도·후속 확장 보존 |
| 점수 필수성 | 네 점수 중 하나 이상 | 코드 비의존 DB CHECK | 점수 없는 후보 차단 |
| 현재 검색 | vector 기반 Exact Search | 기본 검증 Fixture는 vector만 기록 | Hybrid·reranker를 운영 기본으로 오인하지 않음 |
| 순위 | run별 양의 순번 | `rank_no>0`, run+rank UNIQUE | Top-K 결과의 결정적 순서 |
| 청크 중복 | run 안에서 청크 1회 | run+chunk UNIQUE | 같은 후보 중복 저장 차단 |
| 적용성 코드 | 후보 4개 제안 | 필수 open `CharField`, 기본 PENDING | canonical YAML 부재 |
| 선택 묶음 | 선택이면 APPLICABLE+시각 | boolean·시각 쌍만 DB 강제 | APPLICABLE 미승인 의존 제거 |
| 적용성 사유 | PARTIAL·NOT_APPLICABLE이면 필수 | 보류 | 두 코드와 의미 미승인 |
| 후속 근거 FK | id+chunk, id+run+chunk 필요 | 복합 UNIQUE 2개 | EvidenceLink 복합 참조 후보키 |

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [AIRetrievalHit Model](<../../../../../backend/apps/audit/models/retrieval_hit.py>) | 필드, 점수·순위·선택 CHECK, open code, Index |
| [Audit Model export](<../../../../../backend/apps/audit/models/__init__.py>) | Django Runtime Model registry에 `AIRetrievalHit` 공개 |
| [Audit 0004 Migration](<../../../../../backend/apps/audit/migrations/0004_airetrievalhit.py>) | 테이블·FK·UNIQUE·CHECK·부분 Index 생성 |
| [집중 단위 테스트](<../../../../../backend/tests/unit/audit/test_retrieval_hit_model.py>) | 식별자·정밀도·open code·DB 위반·보류 정책·PROTECT 검증 |
| [부모 RetrievalRun Model](<../../../../../backend/apps/audit/models/retrieval_run.py>) | 검색 실행 부모와 현재 Exact Search 설정 |
| [부모 DocumentChunk Model](<../../../../../backend/apps/evidence/models/document_chunk.py>) | 공식 문서 청크 부모와 FTS 구조 |
| [RetrievalRun 구현서](<t005_wave_2a_aiops_retrieval_run_implementation.md>) | 선행 `audit.0003` 구현·검증·인계 |
| [DocumentChunk 구현서](<t005_wave_4a_knowledge_document_chunk_implementation.md>) | 선행 `evidence.0005` 구현·검증·인계 |

이번 Wave는 선행 `evidence.0005_documentchunk.py`를 수정하지 않았다.

## 5. Runtime 필드

| 구분 | 필드 | 구현·무결성 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK |
| 공개 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 수정 불가 |
| 검색 실행 | `retrieval_run_id` | `aiops_retrieval_run.id`, bigint, PROTECT |
| 후보 청크 | `chunk_id` | `knowledge_document_chunk.id`, bigint, PROTECT |
| 순위 | `rank_no` | smallint, 0 이하 금지, run별 UNIQUE |
| Vector 점수 | `vector_score` | nullable `numeric(10,6)` |
| Keyword 점수 | `keyword_score` | nullable `numeric(10,6)` |
| Hybrid 점수 | `hybrid_score` | nullable `numeric(10,6)` |
| Rerank 점수 | `rerank_score` | nullable `numeric(10,6)` |
| 적용성 | `applicability_status_code` | 필수 open code, 기본 PENDING, 비공백 CHECK |
| 적용성 사유 | `applicability_reason` | nullable text |
| 답변 선택 | `selected_for_answer` | boolean, 기본 false |
| 선택시각 | `selected_at` | nullable timestamptz, 선택 boolean과 쌍 |
| 감사시각 | `created_at`, `updated_at` | 자동 생성·갱신 |

## 6. DB 제약과 Index

| 이름 | 역할 |
| --- | --- |
| `ux_retrieval_hit_rank` | 같은 검색 실행의 순위 중복 차단 |
| `ux_retrieval_hit_chunk` | 같은 검색 실행의 청크 중복 차단 |
| `ux_retrieval_hit_id_chunk` | 후속 `id+chunk` 복합 FK 후보키 |
| `ux_retrieval_hit_id_run_chunk` | 후속 EvidenceLink의 `id+run+chunk` 후보키 |
| `ck_retrieval_hit_rank` | 0 이하 순위 차단 |
| `ck_retrieval_hit_score` | 네 점수가 모두 NULL인 후보 차단 |
| `ck_retrieval_hit_selected` | 선택 boolean과 선택시각의 불완전 조합 차단 |
| `ck_retrieval_hit_applicability_nonempty` | 빈 문자열·공백문자 전용 적용성 코드 차단 |
| `ix_retrieval_hit_selected` | 선택된 결과를 run·rank 순으로 조회하는 부분 Index |
| `ix_retrieval_hit_chunk` | 특정 청크가 검색된 실행 역추적 |

`retrieval_run_id`와 `chunk_id`는 `db_index=False`로 두고 명세에 있는
UNIQUE·명시 Index만 사용했다. PostgreSQL Catalog의 실제 Index는
PK·public UUID UNIQUE까지 포함해 8개이다.

```text
aiops_retrieval_hit_pkey
aiops_retrieval_hit_public_id_key
ux_retrieval_hit_rank
ux_retrieval_hit_chunk
ux_retrieval_hit_id_chunk
ux_retrieval_hit_id_run_chunk
ix_retrieval_hit_selected
ix_retrieval_hit_chunk
```

## 7. Decimal 정밀도와 Exact Search 경계

네 점수는 모두 `DecimalField(max_digits=10, decimal_places=6)`이며
PostgreSQL에서 `numeric(10,6)`으로 생성됨을 확인했다.

| 값 | PostgreSQL 결과 |
| --- | --- |
| `0.875000` | 저장 통과 |
| `9999.999999` | 저장 통과 |
| `10000.000000` | 정밀도 초과로 `DataError` 차단 |
| 네 점수 모두 NULL | `ck_retrieval_hit_score`로 차단 |

현재 MVP producer는 Cosine Exact Search의 `vector_score`를 기록하고
`hybrid_score`, `rerank_score`를 NULL로 둔다. DB는 역사 확장 필드를
보존하고 네 점수 중 하나 이상만 요구하므로 향후 승인된 Profile을 별도
Migration 없이 기록할 수 있다.

이번 Wave는 HNSW·IVFFlat Index, Hybrid 가중치, reranker 기본값을
추가하지 않았다. 네 필드를 DB에서 모두 허용한다는 사실은 Hybrid나
reranker가 현재 운영 승인됐다는 의미가 아니다.

## 8. 적용성 코드와 보류 정책

`contracts/codes`에 EVIDENCE_APPLICABILITY canonical YAML이 없으므로
다음 후보값은 TextChoices나 허용값 CHECK로 고정하지 않았다.

```text
PENDING
APPLICABLE
PARTIAL
NOT_APPLICABLE
```

따라서 다음 계약은 의도적으로 설치하지 않았다.

```text
ck_aiops_retrieval_hit_applicability_status_code_allowed
ck_retrieval_hit_applicability_reason
selected_for_answer -> applicability_status_code='APPLICABLE'
```

현재 `ck_retrieval_hit_selected`는 다음 구조만 강제한다.

```text
selected_for_answer=true  <-> selected_at IS NOT NULL
selected_for_answer=false <-> selected_at IS NULL
```

집중·PostgreSQL 테스트는 미래 상태에서도 선택+시각 저장이 가능하고,
PARTIAL 후보가 사유 없이 저장되는 현재 보류 경계를 명시적으로 확인한다.
이는 해당 업무 흐름이 안전하다는 뜻이 아니라, 미승인 코드 의미를 DB에
먼저 고정하지 않았다는 뜻이다.

YAML 승인 시에는 허용값, 상태 전이, PARTIAL·NOT_APPLICABLE 사유,
APPLICABLE 선택 의존을 같은 버전에서 추가하고 기존 데이터 정규화
Migration을 먼저 실행해야 한다.

## 9. 보류한 Application Policy

| 정책 | 이번 Wave 상태 | 후속 구현 위치 |
| --- | --- | --- |
| active 청크·RAG 적격 페이지·APPROVED 문서·검증 모델 범위 | 보류 | Retrieval QuerySet·Service 통합 |
| RetrievalRun terminal 전환과 Hit 선택 원자성 | 보류 | Django transaction Service |
| `selected_for_answer` 건수와 `top_k` 일치 | 보류 | RetrievalRun·Hit 통합 테스트 |
| EvidenceLink는 선택·적용 가능한 Hit만 참조 | 보류 | EvidenceLink Model·Service |
| Top-5 정답 포함·오염 0 평가 | 테이블 범위 밖 | AI/RAG 평가 Gate |

이 정책들은 여러 행·부모 상태·문서 계층을 함께 조회해야 하므로 단일
행 CHECK로 구현할 수 없다. raw SQL 저장이나 `QuerySet.update()`에도
자동 적용되지 않으므로 Service·Importer의 명시 검증이 필요하다.

## 10. Migration 순서와 rollback

직접 의존성은 다음 두 개이다.

```text
audit.0003_airetrievalrun
evidence.0005_documentchunk
  └─ audit.0004_airetrievalhit
```

SQLite와 PostgreSQL에서 모두 다음 순서를 실행했다.

```text
전체 빈 DB migrate
audit.0004 적용 상태 Catalog 확인
audit.0003으로 rollback
aiops_retrieval_hit 부재 확인
audit.0004 재적용
동일 Catalog 복원 확인
```

## 11. 작업→검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·Physical v1.2·테이블사전·부모 Model 대조 | 필드·키·적용/보류 정책 분리 | 1개 테이블 범위 확정 |
| 2 | Model·export 구현 | Django test check | 0 issues |
| 3 | 번호 Migration `audit.0004` 작성 | Audit migration drift | 0 |
| 4 | 식별자·점수·순위·선택·open code 테스트 | 집중 테스트 | `18 passed` |
| 5 | 빈 SQLite 전체 Migration | 15컬럼·7 Index·8 명시 제약 Catalog | 통과 |
| 6 | SQLite rollback → reapply | 테이블 부재 후 동일 Catalog 복원 | 통과 |
| 7 | 빈 PostgreSQL 전체 Migration | 15컬럼·Decimal 10,6·8 Index Catalog | 통과 |
| 8 | PostgreSQL 유효 쓰기 3유형 | Exact vector·미래 선택상태·보류 reason | 통과 |
| 9 | PostgreSQL 위반 쓰기 9유형 | 순위·점수·UNIQUE·선택·코드·정밀도 | 모두 차단 |
| 10 | 두 부모 직접 DELETE | DB FK의 ON DELETE 보호 | 2종 차단 |
| 11 | PostgreSQL rollback → reapply | 테이블 부재 후 동일 Catalog 복원 | 통과 |
| 12 | Audit·Evidence 전체 회귀 | 두 테스트 디렉터리 | `159 passed, 6 skipped` |
| 13 | 두 설정 check·두 앱 drift | 0 issues·No changes detected | 통과 |
| 14 | 임시 자원 정리 | SQLite·스크립트·`pg_database` 조회 | 모두 부재 |

6개 skip은 SQLite 회귀 실행에서 PostgreSQL 전용 Catalog 검사를
의도적으로 건너뛴 결과이다. 이번 테이블의 PostgreSQL Catalog·데이터
검증은 별도 격리 DB에서 실제 수행했다.

## 12. 검증 중 발견한 병렬 작업 영향

첫 PostgreSQL 위반 검증에서 `10000.000000`은 예상대로 DB에서
차단됐지만 psycopg가 이를 `IntegrityError`가 아니라 `DataError`로
분류했다. 검증 도구가 두 예외를 모두 정상 위반으로 집계하도록 교정하고
격리 DB를 flush한 뒤 전체 Gate를 다시 실행했다.

두 번째 실행의 ORM 부모 삭제에서는 병렬 Evidence Wave가
`DataQualityIssue`를 Runtime에 export한 시점과 `evidence.0006` 생성
시점 사이에 삭제 수집기가 아직 없는 테이블을 조회했다. Wave 5A의
두 FK를 실제 PostgreSQL DELETE로 직접 검사해 모두 차단되는 것을 먼저
확인했고, 이후 생성된 `evidence.0006`을 임시 DB에 적용한 뒤 global
`migrate --check`도 통과했다.

이 과정에서 Evidence Model이나 `evidence.0005`는 수정하지 않았다.

## 13. 재현 명령

저장소 루트 기준 집중·회귀 Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    check --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations audit evidence --check --dry-run `
    --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\audit\test_retrieval_hit_model.py -q
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\audit `
    backend\tests\unit\evidence -q
```

PostgreSQL Gate는 기존 개발 DB가 아닌 새 빈 격리 DB에서 실행한다.

```powershell
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate audit 0003 --noinput `
    --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate audit 0004 --noinput `
    --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --check --settings=config.settings.local
```

운영·공용 개발 DB를 대상으로 rollback 명령을 실행하면 안 된다.

## 14. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | `audit.0004`, 두 직접 의존성, 명시 제약·Index 이름과 복합 UNIQUE 유지 |
| PM·계약 담당 | EVIDENCE_APPLICABILITY YAML 값·버전·소유자·전이 승인 |
| AI/RAG 담당 | 현재 vector 기반 Exact Search 점수, 결정적 rank, Top-5 실행 문맥 제공 |
| Service 담당 | terminal 전환·Hit 생성·적용성 확정·선택을 한 transaction으로 처리 |
| EvidenceLink 담당 | `id+run+chunk` 후보키를 사용하고 자동 근거의 선택·적용성 정책 검증 |
| 데이터·Importer 담당 | open code를 후보값으로 임의 정규화하지 말고 Decimal·rank·score 규칙 적용 |
| QA 담당 | PostgreSQL numeric overflow, 부분 Index, UNIQUE, 두 부모 FK를 독립 재현 |
| 통합 담당 | RetrievalRun·Hit·EvidenceLink와 실제 Exact Search 결과를 연결한 후 중앙 Gate 갱신 |

## 15. 잔여 위험과 제외 범위

- EVIDENCE_APPLICABILITY canonical YAML과 상태 전이가 아직 없다.
- 적용성 사유, APPLICABLE 선택 의존, terminal 선택 transaction은
  의도적으로 보류되어 있다.
- 현재 DB는 미래 Hybrid·Rerank 점수를 저장할 수 있지만 해당 검색
  Profile이 운영 승인됐다는 의미는 아니다.
- active 청크·RAG 적격 페이지·문서 승인·제품 모델 범위는 Retrieval
  QuerySet에서 함께 검증해야 한다.
- RetrievalRun `top_k`와 Hit 수·rank 범위의 통합 정책이 필요하다.
- EvidenceLink, 검색 API, 정식 Importer, 운영 데이터와 Seed는 이번
  Wave 범위가 아니다.
- 중앙 T-005 readiness는 병렬 Wave 종료 후 통합 검증에서 갱신해야
  하며 이번 변경에는 포함하지 않았다.
- 따라서 이 문서는 해당 테이블 단위 구현 완료를 증명하며 T-005 전체
  완료 선언이 아니다.

## 16. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·audit.0004·Decimal·open code·SQLite/PostgreSQL·rollback·회귀 검증 및 협업 인계 |

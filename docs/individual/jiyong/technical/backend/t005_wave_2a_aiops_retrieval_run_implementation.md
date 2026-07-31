# T-005 Wave 2A `aiops_retrieval_run` 구현·검증 인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_VERIFIED`  
> 구현 단위: Wave 2A, 테이블 1개

## 1. 결과

`aiops_retrieval_run`을 Django Runtime Model과 번호 Migration으로
구현했다. 검색 질의, 필터, 임베딩·검색 설정, Top-K, 실행 상태,
지연 시간, 근거 없음·실패 사유를 AI 실행 단위로 재현할 수 있다.

| 검증 항목 | 결과 |
| --- | --- |
| Django test settings system check | 통과, 0 issues |
| Audit migration drift | 통과, `No changes detected` |
| Audit 회귀 테스트 | 통과, `47 passed` |
| 신규 집중 테스트 | 통과, `22 passed` |
| SQLite Migration 왕복 | 적용 → 롤백 → 재적용 통과 |
| PostgreSQL 빈 DB Migration 왕복 | 적용 → 롤백 → 재적용 통과 |
| PostgreSQL 물리 카탈로그 | CHECK 11개, FK 3개, 복합 컨텍스트 FK 확인 |
| 임시 검증 DB 정리 | `ABSENT` 확인 |
| T-005 전체 완료 선언 | 하지 않음. 이 문서는 Wave 2A만 판정 |

## 2. 기준 문서와 충돌 해소

현재 지침서, 저장소의 확정 ADR, Physical Contract v1.2와 공개 테이블
사전을 우선하고, `watercare_schema_v3.json`은 과거 초안 비교용으로만
사용했다.

| 우선순위 | 기준 | 이번 작업의 적용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | Exact Search, ANN 제외, `BAAI/bge-m3` 원본 1024차원, Top-5 |
| 2 | [ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 `bigint` PK + 공개 UUID + 내부 FK는 정수 ID |
| 3 | [ADR 0011](<../../../../adr/0011-t005-status-history-idempotency-scope.md>) | 상태 이력 범위를 침범하지 않고 검색 실행 자체의 생명주기만 저장 |
| 4 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 현재 식별자·관계·물리 타입 기준 |
| 5 | [공개 테이블 사전](<../../../../database/watercare_table_dictionary.md#29-aiops_retrieval_run--rag-검색-실행>) | 필드, 인덱스, CHECK, 복합 FK 기준 |
| 6 | [과거 Schema v3](<../../../../database/t-005/watercare_schema_v3.json>) | 충돌 발견용 역사 자료 |

| 비교 항목 | 과거·초안 | 현재 적용 | 판단 이유 |
| --- | --- | --- | --- |
| 기본 PK | Schema v3의 UUID PK | `BigAutoField id` | ADR 0010이 더 최신이고 확정된 식별자 정책 |
| 공개 식별자 | 별도 필드 없음 | `UUIDField public_id`, UNIQUE | API 노출과 내부 조인을 분리 |
| 내부 FK | UUID 참조 | `ai_run_id`, `inquiry_id` bigint | ADR 0010의 내부 FK 정책 |
| `top_k` 기본값 | Schema v3은 10, 테이블 사전은 운영 기본값 미확정 | 애플리케이션 기본값 5 | 현재 공통 개발 규칙이 Top-5를 명시 |
| 검색 방식 | 확장 후보에 Hybrid·ANN 포함 | MVP Exact Search | 현재 지침서에서 HNSW·IVFFlat 제외 |
| 거리함수 | COSINE 목표, L2·INNER_PRODUCT 후보 | 허용 코드는 3종, 실제 실행 전에는 NULL 허용 | 실행 기록은 확장 호환성을 보존하되 임의 기본값을 만들지 않음 |
| Embedding 정보 | 각 필드가 개별 nullable | 모델·버전·거리함수 3개가 모두 NULL 또는 모두 값 존재 | 재현 불가능한 부분 기록 차단 |
| 성공 결과 건수 | Hit와 함께 검증하는 Application Policy | 이번 Wave에서 보류 | `aiops_retrieval_hit`이 아직 구현 범위 밖 |

`top_k=5`는 DB server default가 아니라 Django 모델 기본값이다. DB는
`1 <= top_k <= 100`만 강제한다. 따라서 importer나 raw SQL은 값을
명시해야 하며, 현재 서비스 정책의 Top-5를 바꾸려면 지침·계약·모델·
테스트를 같은 변경 단위로 갱신해야 한다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [AIRetrievalRun Model](<../../../../../backend/apps/audit/models/retrieval_run.py>) | 필드, 상태·거리 코드, CHECK, Index, 부모 문맥 검증 |
| [Audit Model export](<../../../../../backend/apps/audit/models/__init__.py>) | Django Runtime Model registry에 공개 |
| [Audit 0003 Migration](<../../../../../backend/apps/audit/migrations/0003_airetrievalrun.py>) | 테이블과 PostgreSQL·SQLite 복합 문맥 무결성 생성 |
| [집중 테스트](<../../../../../backend/tests/unit/audit/test_retrieval_run_model.py>) | 정상 저장, DB 거부, 트리거, 삭제 보호, 양 DB Migration SQL 검증 |
| [선행 AIRun 문서](<t005_wave_1c_aiops_ai_run_implementation.md>) | 부모 실행 테이블의 구현·생명주기 계약 |

Migration 순서는 다음과 같다.

```text
audit.0001_initial
  -> audit.0002_airun
  -> audit.0003_airetrievalrun
```

`audit.0003`은 `inquiries.0005_inquiry_ux_inquiry_id_subscription`도
의존한다.

## 4. 필드 구현

| 구분 | 필드 | 구현·제약 |
| --- | --- | --- |
| 식별자 | `id` | `BigAutoField`, PK |
| 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 수정 불가 |
| 부모 문맥 | `ai_run_id` | `aiops_ai_run.id`, `PROTECT` |
| 부모 문맥 | `inquiry_id` | `support_inquiry.id`, `PROTECT` |
| 질의 | `query_text` | 검색 시점 질의 원문 |
| 질의 | `query_sha256` | 소문자 SHA-256 64자리 |
| 필터 | `filter_payload` | JSON object만 허용 |
| 검색 설정 | `retrieval_config_version` | 검색 설정 버전 필수 |
| 검색 설정 | `retrieval_config` | JSON object snapshot |
| 임베딩 | `embedding_model` | 실제 벡터 검색 미수행 시 NULL 가능 |
| 임베딩 | `embedding_model_version` | 모델 버전, 3필드 묶음 규칙 적용 |
| 임베딩 | `distance_metric_code` | `COSINE`, `L2`, `INNER_PRODUCT` 또는 NULL |
| 검색 | `top_k` | 기본 5, DB 허용 범위 1~100 |
| 검색 | `reranker_name` | MVP Exact Search에서는 NULL 가능 |
| 생명주기 | `status_code` | QUEUED, RUNNING, SUCCEEDED, NO_EVIDENCE, FAILED |
| 생명주기 | `started_at` | 시작 시각 |
| 생명주기 | `completed_at` | 완료 시각, 시작 시각 이후 |
| 성능 | `latency_ms` | NULL 또는 0 이상 |
| 근거 없음 | `no_evidence_reason` | NO_EVIDENCE이면 필수 |
| 실패 | `error_code` | FAILED이면 필수 |
| 실패 | `error_message` | FAILED이면 필수 |
| 추적 | `correlation_id` | 부모 `AIRun`의 값과 동일 |
| 감사 | `created_at` | 공통 `TimestampedModel`, 자동 생성 |
| 감사 | `updated_at` | 공통 `TimestampedModel`, 자동 갱신 |

## 5. 생명주기와 DB 차단 규칙

| 상태 | `started_at` | `completed_at` | 추가 필수값 |
| --- | --- | --- | --- |
| QUEUED | NULL | NULL | 없음 |
| RUNNING | 값 있음 | NULL | 없음 |
| SUCCEEDED | 값 있음 | 값 있음 | 완료 시각은 시작 이후 |
| NO_EVIDENCE | 값 있음 | 값 있음 | `no_evidence_reason` |
| FAILED | 값 있음 | 값 있음 | `error_code`, `error_message` |

| 제약 | 차단하는 문제 |
| --- | --- |
| `ux_retrieval_id_ai_inquiry` | 후속 근거 테이블이 사용할 복합 참조 후보 보장 |
| `fk_retrieval_ai_run_context` | 검색 실행의 AI 실행·문의·Correlation 혼합 저장 |
| `ck_retrieval_top_k` | 0 이하 또는 100 초과 검색 수 |
| `ck_retrieval_terminal` | 상태와 시작·완료 시각의 생명주기 모순 |
| `ck_retrieval_time_order` | 완료 시각이 시작 시각보다 빠른 기록 |
| `ck_retrieval_query_hash` | SHA-256 형식이 아닌 질의 해시 |
| `ck_retrieval_json_objects` | 배열·문자열 JSON snapshot |
| `ck_retrieval_embedding_context` | 모델·버전·거리함수 일부만 저장 |
| `ck_retrieval_no_evidence` | 사유 없는 근거 없음 종료 |
| `ck_retrieval_failure` | 오류 정보 없는 실패 종료 |
| `ck_retrieval_latency` | 음수 처리 시간 |
| 거리·상태 코드 CHECK | 미승인 코드 저장 |

PostgreSQL은
`(ai_run_id, inquiry_id, correlation_id) -> aiops_ai_run(id, inquiry_id, correlation_id)`
복합 FK로 문맥을 강제한다. SQLite는 같은 의미를 자식 INSERT·UPDATE와
부모 문맥 UPDATE 트리거 3개로 강제한다. 애플리케이션의 `clean()`도
같은 오류를 저장 전에 설명하지만, 최종 무결성은 DB가 담당한다.

## 6. 작업·검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·ADR·Physical v1.2·테이블 사전 교차검증 | 역사 Schema v3와 필드·기본값 비교 | PK와 Top-K 충돌 해소 |
| 2 | Model과 export 구현 | `manage.py check` | test settings 0 issues |
| 3 | 번호 Migration `audit.0003` 작성 | `makemigrations audit --check --dry-run` | drift 0 |
| 4 | 정상·실패·무결성 테스트 작성 | 신규 집중 테스트 | 22 passed |
| 5 | SQLite 실제 적용 | 테이블과 트리거 3개 조회 | 생성 확인 |
| 6 | SQLite 롤백 | 테이블·트리거 재조회 | 모두 제거 확인 |
| 7 | SQLite 재적용 | 테이블·트리거 재조회 | 모두 복원 확인 |
| 8 | 빈 PostgreSQL 임시 DB 적용 | Catalog의 컬럼·제약·Index 조회 | bigint PK, UUID, CHECK 11, FK 3 확인 |
| 9 | PostgreSQL 롤백·재적용 | `to_regclass`, 복합 FK 조회 | ABSENT 후 완전 복원 |
| 10 | Audit 회귀 테스트 | 기존 Audit + AIRun + RetrievalRun | 47 passed |
| 11 | 임시 DB 정리 | `pg_database` 재조회 | ABSENT |

PostgreSQL 검증용 DB는
`watercare_t005_wave2a_verify_20260730_01`로만 생성했고, 검증 직후
삭제했다. 기본 `watercare` 데이터베이스는 수정하지 않았다.

## 7. 재현 명령

저장소 루트에서 실행한다.

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations audit `
    --check --dry-run `
    --settings=config.settings.test
& $python -m pytest `
    .\tests\unit\audit\test_models.py `
    .\tests\unit\audit\test_ai_run_model.py `
    .\tests\unit\audit\test_retrieval_run_model.py `
    -q
```

실제 PostgreSQL에 적용할 때에는 전체 Migration 계획과 대상 DB를 먼저
확인하고, 운영 데이터베이스가 아닌 빈 검증 DB에서 아래 순서를
재현한다.

```powershell
& $python manage.py showmigrations audit `
    --plan `
    --settings=config.settings.local
& $python manage.py migrate audit 0003 `
    --settings=config.settings.local
& $python manage.py migrate audit 0002 `
    --settings=config.settings.local
& $python manage.py migrate audit 0003 `
    --settings=config.settings.local
```

## 8. 알려진 제한과 다음 묶음

| 구분 | 현재 상태 | 후속 조치 |
| --- | --- | --- |
| Terminal Hit Count Policy | 미구현 | `aiops_retrieval_hit` 구현 후 같은 transaction의 서비스·통합 테스트로 연결 |
| RAG 검색 서비스·API | 범위 밖 | AI/API 담당과 검색 설정·상태 전이 계약 확정 후 구현 |
| pgvector Index | 의도적으로 없음 | MVP Exact Search 유지, HNSW·IVFFlat 임의 추가 금지 |
| Seed | 이번 테이블은 실행 이력이라 미작성 | 운영 시 생성되는 기록이며 정적 Seed 대상 아님 |
| T-005 전역 readiness | 이번 Wave에서 미갱신 | 병렬 Wave 통합 시 단일 기준으로 다시 산정 |
| local settings system check | 기존 Workflow Index 이름 4개가 30자를 초과해 실패 | Workflow 소유 변경 단위에서 이름을 축약하고 Migration과 함께 검증 |

마지막 항목 때문에 PostgreSQL 빈 DB 검증은 `migrate --skip-checks`로
Migration 엔진 자체를 실행했다. 문제의 Index는
`workflow.TransitionHistory` 소유이며 이 Wave가 만든 테이블·제약과
무관하다. test settings system check는 0 issues로 통과했다. 이
문서에서는 다른 소유 영역을 수정하지 않고 교차 영향만 기록한다.

다음 AI 검색 묶음은 `aiops_retrieval_hit`이다. 단독 테이블 생성만으로
끝내지 않고 `knowledge_document_chunk` 선행 여부, 점수·순위·선택
제약, RetrievalRun terminal 정책을 함께 검증해야 한다.

## 9. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | Migration 번호·의존성 유지, 후속 복합 FK가 참조할 UNIQUE 보존 |
| AI 담당 | `top_k=5`, Exact Search, `BAAI/bge-m3` 원본 차원과 실행 snapshot을 일치 |
| API 담당 | 외부 응답에는 `public_id`, 내부 조인에는 정수 PK 사용 |
| 데이터·QA 담당 | 실행 이력 테이블을 정적 Seed에 포함하지 않고 Migration·무결성 재현 검증 |
| PM·계약 담당 | Top-K·거리함수·상태 코드 변경 시 지침·ADR·테이블 사전·테스트를 동시 승인 |

## 10. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | `aiops_retrieval_run` Model·Migration·SQLite/PostgreSQL 왕복·회귀 테스트·인계 작성 |

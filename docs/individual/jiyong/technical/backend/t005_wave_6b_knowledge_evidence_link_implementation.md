# T-005 Wave 6B 업무 결과 근거 연결 구현·검증·인계 가이드

- 기준일: 2026-07-30
- 작성·구현 책임: 최지용
- 구현 범위: `knowledge_evidence_link`
- Migration: `evidence.0008_evidencelink`
- 검증 상태: `LOCAL_VERIFIED`
- 팀 검토·병합 상태: 독립 QA·PM 병합 전

> 이 문서는 Wave 6B 시점의 증거다. 이후 32/32·빈 PostgreSQL·
> Seed·Importer·전체 회귀 결과는
> [T-005 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)를
> 현재 기준으로 사용한다.

## 1. 결과 요약

업무 결과 한 건과 실제 사용한 공식 문서 청크, 검색 실행, 검증
스냅샷을 함께 추적하는 `knowledge_evidence_link` Runtime 테이블을
구현했다.

| 검증 항목 | 결과 |
| --- | --- |
| Django Runtime Model | `EvidenceLink` 등록·export 완료 |
| 식별자 | 내부 `BigAutoField` PK + 외부 `public_id` UUID |
| Runtime 컬럼 | 30개 |
| 명시 Index | 테이블 사전의 7개와 일치 |
| 부분 UNIQUE | 결과 대상별 청크·역할 3개 + 표시순서 3개 |
| PostgreSQL 문맥 FK | 복합 FK 5개 |
| Consultation 문맥 | 자식·부모 양방향 Trigger 2개 |
| SQLite 문맥 | 6개 문맥 × 자식 INSERT·UPDATE·부모 UPDATE = 18개 Trigger |
| 집중 검증 | SQLite 38 passed, PostgreSQL 38 passed |
| 연관 회귀 | 259 passed, PostgreSQL 전용 10 skipped |
| SQLite 왕복 | 빈 DB 전체 적용, `0008 → 0007 → 0008` 통과 |
| PostgreSQL 왕복 | 빈 DB 전체 적용, `0008 → 0007 → 0008` 통과 |
| Migration drift | `No changes detected` |

이 결과는 EvidenceLink 테이블과 그 물리 무결성의 로컬 완료를
의미한다. 근거 생성 Service, API, 정식 Importer·Seed, 공통코드
승인, 전체 T-005 완료를 선언한 것은 아니다.

## 2. 적용 기준과 우선순위

| 우선 | 기준 | 적용 내용 |
| ---: | --- | --- |
| 1 | 2026-07-30 `Daily_Process/지침서` | Backend·DB 담당 경계, 작업 후 즉시 검증, 다른 담당 앱의 과거 Migration 불변 |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 신규 주요 테이블의 bigint 내부 PK, 공개 UUID, 내부 정수 FK |
| 3 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | OWNER 기준선과 Runtime 완료를 분리 |
| 4 | [공개 테이블 사전 31번](<../../../../database/watercare_table_dictionary.md#31-knowledge_evidence_link--업무-결과-근거-연결>) | 29개 역사 필드, Index, UNIQUE, 복합 문맥, snapshot 정책 |
| 5 | 현재 Model·Migration 후보키 | 실제 참조 가능한 부모 UNIQUE와 vendor별 강제 방법 확인 |
| 6 | canonical YAML | 승인된 코드만 choices·allowed CHECK에 사용 |

역사 테이블 사전의 UUID PK는 ADR 0010에 따라 bigint PK와 공개 UUID로
분리했다. 따라서 역사 29컬럼에 `public_id`가 추가되어 Runtime은
30컬럼이다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [EvidenceLink Model](<../../../../../backend/apps/evidence/models/evidence_link.py>) | 필드, 명시 Index·UNIQUE·CHECK, portable JSON 표현식, `clean()` 선검증 |
| [Evidence Model export](<../../../../../backend/apps/evidence/models/__init__.py>) | Django Runtime registry에 `EvidenceLink` 공개 |
| [Evidence 0008 Migration](<../../../../../backend/apps/evidence/migrations/0008_evidencelink.py>) | 테이블, PostgreSQL 복합 FK·Consultation Trigger, SQLite 문맥 Trigger 생성·역적용 |
| [EvidenceLink 테스트](<../../../../../backend/tests/unit/evidence/test_evidence_link_model.py>) | 필드·제약·open code·문맥·삭제 보호·vendor Catalog 검증 |

선행 [evidence.0007](<../../../../../backend/apps/evidence/migrations/0007_chunkembedding.py>)과
다른 앱의 기존 Migration은 수정하지 않았다.

## 4. 컬럼 구성

| 묶음 | 컬럼 | 보존 목적 |
| --- | --- | --- |
| 식별자 | `id`, `public_id` | 내부 조인과 외부 공개 식별자 분리 |
| 문의·결과 대상 | `inquiry_id`, `guidance_id`, `consultation_id`, `handoff_report_id` | 정확히 한 업무 결과와 문의 문맥 고정 |
| AI·검색 문맥 | `ai_run_id`, `retrieval_run_id`, `retrieval_hit_id`, `chunk_id` | 검색 실행부터 실제 선택 청크까지 역추적 |
| open code | `selection_origin_code`, `evidence_role_code` | 승인 전 후보값을 손실 없이 저장 |
| 표시 | `display_order`, `citation_label` | 업무 결과별 근거 카드 순서·라벨 재현 |
| 문서 snapshot | `document_code_snapshot`, `document_title_snapshot`, `source_org_snapshot`, `revision_label_snapshot`, `official_source_url_snapshot`, `document_sha256_snapshot` | 선택 시점의 공식 문서 원본 증거 보존 |
| 인용 snapshot | `evidence_summary`, `cited_text_snapshot`, `page_no_snapshot`, `section_snapshot`, `product_model_codes_snapshot` | EvidenceCard와 제품 적용 범위 재현 |
| 검증 | `is_verified`, `verified_by_id`, `verified_at` | 검증 완료 주체·시각 묶음 보존 |
| 감사시각 | `created_at`, `updated_at` | 생성·수정 추적 |

모든 FK는 `PROTECT`, `db_index=False`로 정의했다. Django가 FK마다
암묵 Index를 추가하지 않게 하고 공개 명세의 복합 Index만 생성한다.

## 5. Index와 부분 UNIQUE 대조

### 5.1 명시 Index 7개

| 이름 | 컬럼 |
| --- | --- |
| `ix_evidence_link_inquiry` | `inquiry_id, created_at` |
| `ix_evidence_link_guidance` | `guidance_id, inquiry_id` |
| `ix_evidence_link_consultation` | `consultation_id, inquiry_id` |
| `ix_evidence_link_handoff` | `handoff_report_id, inquiry_id` |
| `ix_evidence_link_chunk` | `chunk_id` |
| `ix_evidence_link_ai_run` | `ai_run_id, inquiry_id` |
| `ix_evidence_link_retrieval_hit` | `retrieval_hit_id, retrieval_run_id, chunk_id` |

### 5.2 부분 UNIQUE 6개

| 이름 | 조건 | 차단 내용 |
| --- | --- | --- |
| `ux_evidence_guidance_chunk` | `guidance_id IS NOT NULL` | 안내 안에서 같은 청크·역할 중복 |
| `ux_evidence_consultation_chunk` | `consultation_id IS NOT NULL` | 상담 안에서 같은 청크·역할 중복 |
| `ux_evidence_handoff_chunk` | `handoff_report_id IS NOT NULL` | 인계 안에서 같은 청크·역할 중복 |
| `ux_evidence_guidance_order` | `guidance_id IS NOT NULL` | 안내 표시순서 중복 |
| `ux_evidence_consultation_order` | `consultation_id IS NOT NULL` | 상담 표시순서 중복 |
| `ux_evidence_handoff_order` | `handoff_report_id IS NOT NULL` | 인계 표시순서 중복 |

실제 Catalog에는 위 13개 외에 PK와 `public_id UNIQUE`가 존재한다.
따라서 PostgreSQL Index는 15개, SQLite는 integer PK가 별도 Index를
만들지 않아 14개다.

## 6. 코드와 무관하게 즉시 강제한 CHECK

| 이름 | 강제 내용 |
| --- | --- |
| `ck_evidence_exactly_one_target` | Guidance·Consultation·Handoff 중 정확히 하나 |
| `ck_evidence_display_order` | `display_order > 0` |
| `ck_evidence_page_no` | `page_no_snapshot > 0` |
| `ck_evidence_verification` | 검증 true이면 검증자·시각 모두 필수, false이면 모두 NULL |
| `ck_evidence_document_hash` | 소문자 16진수 SHA-256 64자 |
| `ck_evidence_product_models` | 비어 있지 않은 JSON array |
| `ck_evidence_retrieval_bundle` | hit·run 모두 NULL 또는 hit·run·AI 모두 존재 |
| `ck_evidence_selection_origin_nonempty` | open 선택출처 코드가 공백 전용이 아님 |
| `ck_evidence_role_nonempty` | open 근거역할 코드가 공백 전용이 아님 |
| `ck_evidence_required_text` | 표시·문서·요약·인용 필수 문자열이 공백 전용이 아님 |

`IsNonEmptyJSONArray`는 PostgreSQL `jsonb`와 SQLite JSON1에서 같은
의미로 동작하며, 배열이 아닌 JSON에 길이 함수를 호출해 오류가 나는
것을 막도록 `CASE`로 타입을 먼저 분기한다.

## 7. 복합 문맥 무결성

| 자식 문맥 | 부모 후보키 | PostgreSQL | SQLite |
| --- | --- | --- | --- |
| `guidance_id, inquiry_id` | `support_guidance(id, inquiry_id)` | 복합 FK | 양방향 Trigger |
| `consultation_id, inquiry_id` | 후보키 없음 | 양방향 Trigger | 양방향 Trigger |
| `handoff_report_id, inquiry_id` | `support_handoff_report(id, inquiry_id)` | 복합 FK | 양방향 Trigger |
| `ai_run_id, inquiry_id` | `aiops_ai_run(id, inquiry_id)` | 복합 FK | 양방향 Trigger |
| `retrieval_hit_id, retrieval_run_id, chunk_id` | `aiops_retrieval_hit(id, retrieval_run_id, chunk_id)` | 복합 FK | 양방향 Trigger |
| `retrieval_run_id, ai_run_id, inquiry_id` | `aiops_retrieval_run(id, ai_run_id, inquiry_id)` | 복합 FK | 양방향 Trigger |

PostgreSQL 복합 FK 5개는 자식 입력·수정과 부모 문맥 수정을 모두
차단한다. SQLite는 같은 의미를 자식 INSERT, 자식 관련 컬럼 UPDATE,
부모 문맥 UPDATE Trigger 세 개로 나눠 6개 문맥에 적용했다.

### 7.1 Consultation만 PostgreSQL Trigger인 이유

`support_consultation`에는 현재 `(id, inquiry_id)` UNIQUE 후보키가 없다.
복합 FK를 만들려면 다른 담당 앱에 새 `consultations.0002`를 추가해야
한다. 이번 Wave는 `evidence.0008` 하나로 범위를 고정하고 과거
Migration을 수정하지 않는 원칙을 적용했다.

기존 `visits.0003_handoffreport`와 동일하게 다음 두 Trigger로 복합 FK와
동등한 양방향 문맥을 강제한다.

1. EvidenceLink INSERT 또는 `consultation_id, inquiry_id` UPDATE 전 부모
   상담의 문의 일치를 확인한다.
2. 참조 중인 Consultation의 `inquiry_id` 변경 전 자식 불일치를
   확인하고 차단한다.

팀이 향후 `Consultation(id, inquiry_id)` 후보키를 공식 승인하면 새
Migration에서 Trigger를 복합 FK로 교체할 수 있다. 기존 Migration을
수정하면 안 된다.

## 8. Model 선검증과 Service 경계

`EvidenceLink.clean()`은 DB 오류 전에 사용자 친화적인 오류를 제공하기
위해 다음을 확인한다.

- 결과 대상 정확히 하나와 동일 문의
- AI Run·RetrievalRun·RetrievalHit·Chunk 문맥 일치
- RetrievalHit의 `selected_for_answer=true`
- 검증자 역할이 `CONSULTANT` 또는 `OPERATOR`
- 양수 순서·페이지, SHA-256, 비어 있지 않은 제품 JSON array
- 검증 bundle과 필수 open code·snapshot 문자열

`clean()`은 raw SQL과 `QuerySet.update()`에 자동 적용되지 않는다.
그래서 행·문맥의 핵심 무결성은 DB CHECK·FK·Trigger가 담당한다.

다음 snapshot 생성 정책은 여러 부모의 현재 상태와 제품 범위를 함께
읽어야 하므로 후속 Service 또는 정식 Importer가 transaction 안에서
수행해야 한다.

1. 클라이언트가 문서 snapshot을 임의 입력하지 못하게 한다.
2. 서버가 `chunk → page → document → verified model scope`를 읽어
   snapshot을 직접 복사한다.
3. active 청크, RAG 적격 페이지, 승인 문서, 검증 제품 범위를 확인한다.
4. 생성 이후 snapshot을 원본 변경으로 덮어쓰지 않는다.

## 9. 승인 전 보류한 코드 의존 정책

현재 다음 canonical YAML은 존재하지 않거나 승인 값 집합이 비어 있다.

- `EVIDENCE_SELECTION_ORIGIN`
- `EVIDENCE_ROLE`
- `EVIDENCE_APPLICABILITY`
- `verification-statuses.yaml`의 실제 코드 목록

따라서 아래 제약을 의도적으로 만들지 않았다.

| 보류 항목 | 이유 | 후속 승인 후 위치 |
| --- | --- | --- |
| origin TextChoices·allowed CHECK | AUTO_RETRIEVAL·MANUAL이 아직 설계 제안 | canonical YAML + additive Migration |
| role TextChoices·allowed CHECK | PRIMARY·SUPPORTING·CONTRAINDICATION 미승인 | canonical YAML + additive Migration |
| `ck_evidence_selection_origin` | origin literal에 따라 retrieval bundle을 분기함 | 코드 승인 후 CHECK |
| RetrievalHit `APPLICABLE` 의존 | applicability 코드 집합·전이 미승인 | Evidence 생성 Service |
| 정확한 문서 `APPROVED` literal | 문서상태 canonical 계약 미확정 | Retrieval·Evidence Service |

물리계약의 `AUTO_RETRIEVAL`, `SUPPORTING` 기본값은 보존했지만 값 집합을
닫지 않았다. PostgreSQL Catalog에서 위 세 allowed·selection CHECK가
0개임을 확인했다.

## 10. Migration 순서와 역적용

`evidence.0008`의 직접 의존성은 다음과 같다.

1. `accounts.0003_promote_integer_primary_keys`
2. `audit.0004_airetrievalhit`
3. `consultations.0001_initial`
4. `evidence.0007_chunkembedding`
5. `inquiries.0008_guidance`
6. `visits.0003_handoffreport`

`inquiries.0009`·`0010`의 모델은 EvidenceLink가 참조하지 않으므로
불필요한 순서 결합을 피하고 Guidance가 생성되는 `0008`에 고정했다.

역적용은 다음 순서를 지킨다.

1. Consultation 부모·자식 Trigger 제거
2. PostgreSQL Trigger 함수 제거
3. PostgreSQL 복합 FK 5개 제거
4. SQLite 문맥 Trigger 18개 제거
5. `knowledge_evidence_link` 테이블 제거

## 11. 검증 결과

### 11.1 단계별 작업·검증

| 단계 | 검증 | 결과 |
| ---: | --- | --- |
| 1 | Physical Contract·ADR·테이블 사전·부모 후보키 대조 | 구현 경계 확정 |
| 2 | Model export 후 Django system check | 0 issues |
| 3 | Migration dry-run·drift | `No changes detected` |
| 4 | SQLite 빈 DB 전체 Migration | 통과 |
| 5 | SQLite 집중 테스트 | 38 passed |
| 6 | Evidence/Audit/Guidance/Consultation/Visit 회귀 | 259 passed, 10 skipped |
| 7 | SQLite `0008 → 0007 → 0008` | 통과 |
| 8 | PostgreSQL 16.14 빈 DB 전체 Migration | 통과 |
| 9 | PostgreSQL 집중 테스트 | 38 passed |
| 10 | PostgreSQL Catalog 대조 | 30컬럼·15 Index·복합 FK 5·Consultation Trigger 2 |
| 11 | PostgreSQL `0008 → 0007` 제거 확인 | table 0·function 0·trigger 0 |
| 12 | PostgreSQL `0007 → 0008` 및 migrate check | 동일 Catalog 복원·미적용 0 |
| 13 | 임시 검증 자원 정리 | SQLite 파일·PostgreSQL 격리 DB 모두 부재 |

회귀의 10개 skip은 SQLite 실행에서 PostgreSQL 전용 vector·Catalog
검사를 건너뛴 것이다. EvidenceLink 자체의 PostgreSQL 검사는 별도
빈 DB에서 38건 모두 실행했다.

### 11.2 검증 중 발견·교정한 항목

첫 집중 테스트에서 CUSTOMER 역할 검증용 Fixture가 모든 역할에
`employee_no`를 넣어 Accounts의 역할·직원번호 제약에 걸렸다.
EvidenceLink 구현 실패가 아니라 테스트 사전조건 오류였다.

Fixture를 직원 역할(`CONSULTANT`, `TECHNICIAN`, `OPERATOR`)에만
직원번호를 넣도록 분기한 뒤 같은 집중 테스트를 처음부터 다시 실행해
38건 모두 통과했다. 제품 코드·근거 코드 제약을 우회하거나 Accounts
구현을 수정하지 않았다.

## 12. 재현 명령

저장소 루트 기준 SQLite 집중·회귀 Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    check --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations evidence --check --dry-run `
    --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\evidence\test_evidence_link_model.py `
    -q -p no:cacheprovider
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\evidence `
    backend\tests\unit\audit `
    backend\tests\unit\inquiries\test_guidance_model.py `
    backend\tests\unit\consultations `
    backend\tests\unit\visits `
    -q -p no:cacheprovider
```

PostgreSQL Gate는 공용 개발 DB가 아니라 새 빈 격리 DB에서만 실행한다.

```powershell
$env:POSTGRES_DB = '<isolated-empty-database>'
$env:DJANGO_SETTINGS_MODULE = 'config.settings.local'

& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\evidence\test_evidence_link_model.py `
    -q -p no:cacheprovider
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate evidence 0007 --noinput `
    --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate evidence 0008 --noinput `
    --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --check --settings=config.settings.local
```

운영·공용 개발 DB에서 rollback 명령을 실행하면 안 된다.

## 13. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | Model·`evidence.0008`, 명시 이름, rollback 대칭성 유지 |
| 윤승혁(PM)·계약 담당 | origin·role·applicability·문서 승인 코드의 값·전이·버전 승인 |
| 이동윤(AI/RAG) | AI Run·RetrievalRun·selected Hit·Chunk 문맥을 같은 inquiry로 제공 |
| Service 담당 | 서버 snapshot factory와 client 임의 입력 차단을 transaction으로 구현 |
| 김은진(Data·QA) | 빈 PostgreSQL에서 Migration·Catalog·위반 쓰기·rollback 독립 재현 |
| API·Web·Mobile 담당 | 승인된 EvidenceCard 공개 필드만 사용하고 내부 score·hash·raw 인용 노출 여부를 계약으로 확정 |
| 통합 담당 | Guidance 승인·AI schema·검증 Evidence 1건 이상의 상태 전이 Gate 연결 |

독립 QA는 다음을 회신해야 한다.

1. 검증 Branch·40자리 Commit SHA
2. 빈 PostgreSQL 전체 Migration 결과
3. 30컬럼, 명시 7 Index, 부분 UNIQUE 6, 복합 FK 5, Trigger 2의 Catalog
4. 결과 대상·검색 문맥·검증 bundle 위반 쓰기 차단 결과
5. `0008 → 0007 → 0008` 왕복 결과
6. 실행 명령과 실패 시 원문 오류

## 14. 잔여 위험과 완료 경계

- canonical evidence 코드 계약이 승인 전이다.
- snapshot을 서버에서 생성하는 Service·Serializer가 아직 없다.
- 문서 승인·제품 범위·Hit applicability를 한 transaction으로 검사하는
  Application Gate가 아직 없다.
- EvidenceCard API와 공개 필드 매핑이 OWNER 정합화 전이다.
- 운영 Importer·Seed와 367건 데이터 연결은 이번 Wave 범위가 아니다.
- 전체 T-005 readiness·빈 PostgreSQL Seed 2회·Auth 종료 Gate는 별도
  통합 검증 대상이다.

따라서 이 문서는 `knowledge_evidence_link` 한 테이블의 Model,
Migration, 물리 무결성, 양방향 문맥, rollback 로컬 완료를 증명한다.
T-005 전체 완료 또는 팀 검토 완료를 뜻하지 않는다.

## 15. 변경 이력

| 버전 | 일자 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | EvidenceLink 30컬럼, Index·부분 UNIQUE, vendor별 문맥 무결성, SQLite·PostgreSQL 왕복과 협업 인계 기록 |

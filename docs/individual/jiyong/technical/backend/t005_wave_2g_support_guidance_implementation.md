# T-005 Wave 2G `support_guidance` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 연계 요구사항: `FR-010`, `FR-011`, `NFR-004`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 범위: 고객지원 묶음 1개 테이블

## 1. 결과 요약

문의별 고객 안내를 버전 단위로 보존하고, 근거 충분성·검토 메타데이터와
선택적 AI 생성 실행을 추적하는 `support_guidance`를 `inquiries` 앱의
Django Runtime Model과 번호 Migration으로 구현했다.

역사 테이블사전의 14개 논리 필드를 보존하면서 식별자 ADR에 따라 내부
`BigAutoField id`와 외부 공개용 unique UUID `public_id`를 분리했다.
Inquiry, AIRun, Accounts User FK는 현재 Runtime의 bigint PK를 사용하므로
실제 테이블은 15개 컬럼이다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | test·local 설정 모두 통과, 0 issues |
| Inquiries Migration drift | 통과, `No changes detected` |
| 신규 집중 테스트 | `17 passed` |
| Inquiry·Audit 전체 단위 회귀 | `142 passed` |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `0008 → 0007 → 0008` | 테이블·Index·Trigger 제거와 복원 통과 |
| 빈 PostgreSQL 전체 Migration | 통과 |
| PostgreSQL 물리 Catalog | 15컬럼, bigint/UUID, 6개 Index, CHECK, 복합 FK 확인 |
| PostgreSQL 유효 쓰기 | open code·AI 생성·검토 쌍·보류 정책 경계 저장 통과 |
| PostgreSQL 위반 쓰기 | DB 위반 9종, AI Application Policy 1종, 부모 PROTECT 3종 차단 |
| PostgreSQL `0008 → 0007 → 0008` | 테이블·복합 FK 제거와 동일 Catalog 복원 통과 |
| 임시 검증 자원 | SQLite 파일·검증 스크립트 제거, PostgreSQL DB 부재 확인 |

이 결과는 `support_guidance` 한 테이블의 로컬 구현·검증 결과이다.
GuidanceItem·EvidenceLink·Serializer·API·정식 Importer·Seed와 중앙
T-005 readiness는 이번 Wave에서 수정하거나 완료로 선언하지 않았다.

## 2. 기준 문서 적용 우선순위

| 우선 | 기준 | 이번 구현의 적용 내용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | Backend·DB 담당 경계, 번호 Migration, 작업 후 즉시 검증, 상대경로 인계 |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 bigint PK, 공개 UUID, 내부 bigint FK |
| 3 | [상태이력 ADR 0011](<../../../../adr/0011-t005-status-history-idempotency-scope.md>) | Guidance 버전을 상태전이 원장이나 HTTP 멱등 원장으로 오인하지 않음 |
| 4 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 최신 식별자 정책과 canonical code 우선 정책 |
| 5 | [테이블사전](<../../../../database/watercare_table_dictionary.md>) | 14개 역사 필드, 버전·복합키·검토·AI 관계·Index 설계 |
| 6 | [AI 작업유형 코드](<../../../../../contracts/codes/ai-task-types.yaml>)·[Schema 검증상태 코드](<../../../../../contracts/codes/ai-schema-validation-statuses.yaml>) | AI 생성 안내는 PASSED 상태의 GENERATE_GUIDANCE 실행만 사용 |
| 7 | [AI UsageGuidance Schema](<../../../../../contracts/ai/common/UsageGuidance.schema.json>) | AI 응답 객체와 DB Guidance 버전의 책임 경계 확인 |

Physical Contract v1.2에는 `support_guidance` 개별 override가 없다.
따라서 최신 식별자·canonical code 공통 정책을 우선 적용하고, 나머지
필드·관계는 테이블사전을 구현 입력으로 사용했다.

## 3. 계약 충돌과 해소 결과

| 항목 | 역사·현재 자료 | 이번 구현 | 판단 이유 |
| --- | --- | --- | --- |
| 기본 PK | 테이블사전 UUID `id` | bigint 자동 증가 `id` | ADR 0010이 최신 확정 결정 |
| 공개 식별자 | 별도 필드 없음 | unique UUID `public_id` | 내부 조인과 외부 식별자 분리 |
| 세 부모 FK | 역사 UUID | bigint | Inquiry·AIRun·Accounts 현재 PK 타입 |
| 검토상태 후보 | PENDING·APPROVED·REJECTED | open `CharField`, 기본 PENDING | `GUIDANCE_REVIEW_STATUS` canonical YAML 부재 |
| 근거충분성 후보 | SUFFICIENT·PARTIAL·INSUFFICIENT | open `CharField` | `EVIDENCE_SUFFICIENCY` canonical YAML 부재 |
| 필수 문자열 | DB NN | 비공백 문자 CHECK 추가 | 공백·탭·개행만 있는 데이터 차단 |
| 검토 메타데이터 | 상태값에 따라 reviewer/time 묶음 | reviewer/time의 코드 비의존 쌍만 강제 | 미승인 상태집합을 DB에 고정하지 않음 |
| 근거 부족 상담전환 | INSUFFICIENT이면 true | 상태값 의존 CHECK 보류 | 미승인 코드 리터럴에 의존 |
| 승인 후 불변 | APPROVED UPDATE/DELETE 금지 제안 | Application Policy 보류 | APPROVED 의미·전이·권한 계약 미승인 |
| AI 출처 | AI run과 Inquiry 동일 | PostgreSQL 복합 FK·SQLite Trigger | raw 쓰기에서도 문의 문맥 보존 |
| AI 실행 품질 | GENERATE_GUIDANCE·PASSED | Model `clean()` 정책 | 승인된 AIRun canonical code 재사용 |
| JSON | DB 테이블에는 JSON 컬럼 없음 | JSON 컬럼·CHECK 미추가 | AI DTO를 DB 물리 컬럼으로 오인하지 않음 |

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [Guidance Model](<../../../../../backend/apps/inquiries/models/guidance.py>) | 필드, 버전·문자열·검토 쌍 CHECK, open code, AI Application Policy |
| [Inquiries Model export](<../../../../../backend/apps/inquiries/models/__init__.py>) | Django Runtime Model registry에 `Guidance` 공개 |
| [Inquiries 0008 Migration](<../../../../../backend/apps/inquiries/migrations/0008_guidance.py>) | 테이블과 PostgreSQL·SQLite 복합 무결성 설치 |
| [집중 단위 테스트](<../../../../../backend/tests/unit/inquiries/test_guidance_model.py>) | 식별자·open code·CHECK·UNIQUE·PROTECT·정책 보류·복합 관계 검증 |
| [부모 AIRun 구현서](<t005_wave_1c_aiops_ai_run_implementation.md>) | AI 실행의 작업유형·검증상태·복합 부모 후보키 |
| [선행 InquiryQA 구현서](<t005_wave_2f_support_inquiry_qa_implementation.md>) | 바로 앞 `inquiries.0007` Migration과 고객지원 Wave 인계 |

## 5. Runtime 필드

| 구분 | 필드 | 구현·무결성 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK |
| 공개 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 수정 불가 |
| 대상 문의 | `inquiry_id` | `support_inquiry.id`, bigint, PROTECT |
| 안내 버전 | `guidance_version` | integer, 기본 1, 0 이하 금지, 문의별 UNIQUE |
| 검토상태 | `review_status_code` | 필수 open code, 기본 PENDING, 비공백 CHECK |
| 제목 | `title` | 필수 `varchar(200)`, 비공백 CHECK |
| 요약 | `summary_text` | 필수 text, 비공백 CHECK |
| 안전문구 | `safety_notice` | nullable text |
| 근거충분성 | `evidence_sufficiency_code` | 필수 open code, 비공백 CHECK |
| 상담전환 | `requires_consultation` | boolean, 기본 false |
| 생성 AI 실행 | `generated_by_ai_run_id` | nullable `aiops_ai_run.id`, bigint, PROTECT |
| 검토자 | `reviewed_by_id` | nullable `accounts_user.id`, bigint, PROTECT |
| 검토시각 | `reviewed_at` | nullable timestamptz, 검토자와 쌍 |
| 감사시각 | `created_at`, `updated_at` | 자동 생성·갱신 |

`UsageGuidance.schema.json`의 `guidance_status`, `message`,
`restricted_functions`, `next_actions`는 AI/API 응답 계약이다. 이 객체를
그대로 저장하는 JSON 컬럼은 `support_guidance` 테이블사전에 없다.
따라서 이번 Migration은 JSON 컬럼이나 임의 JSON presence CHECK를
발명하지 않았다. 향후 Adapter가 Schema 필드를 Guidance·GuidanceItem
구조에 어떻게 매핑할지는 AI·API·Backend 공동 승인 대상이다.

## 6. 승인 코드와 보류 코드

| 코드·정책 | 기준 상태 | 현재 구현 | 후속 조건 |
| --- | --- | --- | --- |
| `AIRun.task_type_code` | OWNER_BASELINE YAML | GENERATE_GUIDANCE 비교 | 기존 AIRun TextChoices·DB CHECK 재사용 |
| `AIRun.schema_validation_status_code` | OWNER_BASELINE YAML | PASSED 비교 | 기존 AIRun TextChoices·DB CHECK 재사용 |
| `review_status_code` | 후보값만 존재 | open `CharField` | guidance-review-statuses YAML OWNER 승인 필요 |
| `evidence_sufficiency_code` | 후보값만 존재 | open `CharField` | evidence-sufficiency YAML OWNER 승인 필요 |
| 승인 후 불변 정책 | 후보 APPROVED에 의존 | 미적용 | 상태집합·전이·Service 권한·예외 처리 승인 필요 |

다음 네 계약은 의도적으로 설치하지 않았다.

```text
ck_support_guidance_review_status_code_allowed
ck_support_guidance_evidence_sufficiency_code_allowed
ck_guidance_review_fields
ck_guidance_insufficient_handoff
```

기본값과 부분 Index 조건에 쓰인 PENDING은 역사 기본 흐름과 검토 대기
조회 최적화를 보존한다. 이는 PENDING·APPROVED·REJECTED만 허용한다는
승인이 아니다. 집중·PostgreSQL 테스트에서 미래 상태·근거 코드를 실제로
저장해 open code 동작을 확인했다.

## 7. DB 무결성

| 제약·Index | 방지하거나 지원하는 내용 |
| --- | --- |
| `ux_guidance_version` | 같은 문의의 안내 버전 중복 차단 |
| `ux_guidance_id_inquiry` | 하위 복합 FK가 참조할 `id+inquiry` 후보키 |
| `ck_guidance_version_positive` | 0 이하 안내 버전 차단 |
| `ck_guidance_review_status_nonempty` | 검토상태의 빈 문자열·공백문자 전용 값 차단 |
| `ck_guidance_title_nonempty` | 제목의 빈 문자열·공백문자 전용 값 차단 |
| `ck_guidance_summary_nonempty` | 요약의 빈 문자열·공백문자 전용 값 차단 |
| `ck_guidance_evidence_code_nonempty` | 근거충분성의 빈 문자열·공백문자 전용 값 차단 |
| `ck_guidance_review_pair` | 검토자와 검토시각 중 한쪽만 있는 행 차단 |
| `ix_guidance_review_queue` | PENDING 검토 대기열의 상태·생성시각 조회 |
| `ix_guidance_ai_run` | AI 실행·문의별 생성 Guidance 추적 |

처음에는 `TRIM(field)` 길이로 필수 문자열을 검증했다. 첫 집중 테스트에서
SQLite와 PostgreSQL의 기본 TRIM 대상이 일반 공백이어서 탭·개행만 있는
문자열을 놓칠 수 있음을 확인했다. 같은 작업 안에서 `.*\S.*` 정규식으로
수정하고 Model·Migration drift·집중 테스트를 다시 실행했다.

PostgreSQL Catalog에는 명시·자동 UNIQUE를 포함해 다음 6개 Index만
존재함을 확인했다.

```text
support_guidance_pkey
support_guidance_public_id_key
ux_guidance_version
ux_guidance_id_inquiry
ix_guidance_review_queue
ix_guidance_ai_run
```

FK 기본 자동 Index는 `db_index=False`로 막아 테이블사전에 없는
`reviewed_by_id`·`generated_by_ai_run_id` 단독 Index를 만들지 않았다.

## 8. 같은 문의 복합 무결성과 AI 정책

PostgreSQL에서는 다음 복합 FK가 Guidance와 AI 실행의 문의 문맥을 같이
강제한다.

```sql
FOREIGN KEY (generated_by_ai_run_id, inquiry_id)
REFERENCES aiops_ai_run (id, inquiry_id)
MATCH SIMPLE
ON DELETE RESTRICT
```

SQLite는 같은 의미를 다음 세 Trigger로 구현한다.

```text
fk_guidance_context_child_insert
fk_guidance_context_child_update
fk_guidance_context_parent_update
```

Model `clean()`은 AI 실행이 같은 문의에 속하고,
`task_type_code=GENERATE_GUIDANCE`,
`schema_validation_status_code=PASSED`인지 검증한다. 다른 행의 작업유형과
검증상태는 단순 DB CHECK로 표현할 수 없으므로 Application Policy이다.
Service·Serializer는 저장 전에 `full_clean()`을 호출해야 하며 raw SQL
Importer도 같은 정책을 별도로 수행해야 한다.

검토자는 테이블사전 설명상 상담사 또는 운영자이다. 사용자 역할은 다른
행의 속성이며 이번 역사 Constraint 목록에는 reviewer-role 정책이 없다.
따라서 DB FK는 계정 존재만 보장한다. API 권한과 Service는 승인된
CONSULTANT·OPERATOR 역할만 검토 동작에 허용해야 한다.

## 9. 보류한 검토·근거 정책

### 9.1 상태별 검토 묶음

역사 `ck_guidance_review_fields`는 PENDING·APPROVED·REJECTED 세 값만
인정하는 형태이다. 그대로 설치하면 다른 미래 상태는 reviewer/time
조합과 무관하게 모두 거부되어 open code 결정과 충돌한다.

이번 Wave는 코드와 무관하게 항상 안전한 `reviewed_by/reviewed_at` 쌍만
`ck_guidance_review_pair`로 강제했다. 상태별 필수·금지 규칙은 canonical
YAML과 전이표 승인 후 별도 Migration으로 추가해야 한다.

### 9.2 근거 부족 상담전환

`ck_guidance_insufficient_handoff`는 미승인 리터럴 INSUFFICIENT에
의존한다. 이번 테스트는 `INSUFFICIENT + requires_consultation=false`가
현재 저장됨을 명시적으로 확인해 정책 미적용 상태를 고정했다.

근거충분성 YAML이 승인되면 이 CHECK와 API·AI safety mapping을 같은
버전에서 추가하고, 기존 데이터 탐색·정규화 Migration을 먼저 수행해야
한다.

### 9.3 승인 후 불변

`policy_guidance_approved_immutable` 역시 APPROVED 의미에 의존하므로
Model의 `save()`·`delete()`를 임의 override하지 않았다. 테스트는
APPROVED 후보 행의 UPDATE·DELETE가 현재 가능함을 확인한다.

이는 승인 안내를 수정해도 안전하다는 의미가 아니다. 정책 승인 전까지
API·Service를 외부 공개하면 안 되며, 승인 후에는 Service 트랜잭션,
권한, 새 `guidance_version` 생성, QuerySet bulk update/raw SQL 우회까지
포함한 통합 정책이 필요하다.

## 10. Migration 순서와 rollback

`inquiries.0008_guidance`의 직접 의존성은 다음과 같다.

```text
accounts.0003_promote_integer_primary_keys
audit.0002_airun
inquiries.0007_inquiryqa
  └─ inquiries.0008_guidance
```

Accounts 0003을 명시적으로 선행해 `reviewed_by_id`가 legacy 문자열이
아닌 bigint로 생성되도록 했다. Guidance는 RetrievalRun을 참조하지
않으므로 `audit.0003`을 불필요한 직접 의존성으로 추가하지 않았다.

SQLite와 PostgreSQL에서 모두 `0008 → 0007 → 0008`을 실행했다. 역적용
후 `support_guidance`와 세 Vendor Trigger 또는 복합 FK가 사라지고,
재적용 후 동일한 컬럼·제약·Index·관계가 복원되는 것을 확인했다.

## 11. 작업→검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·ADR·Physical v1.2·테이블사전·YAML 대조 | 필드·관계·승인/보류 코드 분류 | 1개 테이블 범위 확정 |
| 2 | Model·export 구현 | Django test check | 0 issues |
| 3 | 번호 Migration `inquiries.0008` 작성 | Migration drift | `No changes detected` |
| 4 | 필드·open code·UNIQUE·CHECK·PROTECT·복합 관계 테스트 | 첫 집중 테스트 | 2 failed, 15 passed |
| 5 | 탭·개행 경계 원인 분석 | TRIM 의미와 DB DDL 확인 | 비공백 정규식으로 교정 |
| 6 | Model·Migration 동시 교정 | drift·집중 테스트 재실행 | drift 0, `17 passed` |
| 7 | 빈 SQLite 전체 Migration | 컬럼·CHECK·부분 Index·3 Trigger Catalog | 통과 |
| 8 | SQLite rollback → reapply | 테이블·Trigger 부재 후 정확한 복원 | 통과 |
| 9 | Inquiry·Audit 전체 단위 회귀 | 두 테스트 디렉터리 | `142 passed` |
| 10 | 격리된 빈 PostgreSQL 전체 Migration | 15컬럼·6 Index·CHECK·복합 FK Catalog | 통과 |
| 11 | PostgreSQL 유효 쓰기 4유형 | open code·AI·검토 쌍·보류 정책 경계 | 모두 통과 |
| 12 | PostgreSQL DB 위반 쓰기 9유형 | 버전·문자열·검토 쌍·복합 자식/부모 | 모두 `IntegrityError` |
| 13 | AI Application Policy·부모 삭제 | wrong task 1종·PROTECT 3종 | 모두 차단 |
| 14 | PostgreSQL rollback → reapply | 테이블·복합 FK 부재 후 동일 Catalog 복원 | 통과 |
| 15 | 두 설정 check·inquiries drift | 0 issues·No changes detected | 통과 |
| 16 | 임시 자원 정리 | SQLite 파일·스크립트·`pg_database` 조회 | 모두 부재 |

## 12. 재현 명령

저장소 루트 기준 SQLite 집중·회귀 Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    check --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations inquiries --check --dry-run `
    --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\inquiries\test_guidance_model.py -q
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\inquiries `
    backend\tests\unit\audit -q
```

PostgreSQL Gate는 기존 개발 DB가 아닌 새 빈 격리 DB에서 실행한다.

```powershell
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate inquiries 0007 --noinput `
    --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate inquiries 0008 --noinput `
    --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --check --settings=config.settings.local
```

Catalog와 위반 데이터 검증은 이 문서의 제약·Index·복합 FK 목록을
기준으로 독립 QA에서 재현한다. 운영·공용 개발 DB를 대상으로 rollback
명령을 실행하면 안 된다.

## 13. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | `inquiries.0008`, 세 직접 의존성, 제약·부분 Index·복합 FK/Trigger 이름 유지 |
| PM·계약 담당 | GUIDANCE_REVIEW_STATUS·EVIDENCE_SUFFICIENCY YAML의 값·버전·소유자·전이 승인 |
| AI 담당 | PASSED GENERATE_GUIDANCE 실행과 UsageGuidance→DB 필드 매핑 계약 제공 |
| API 담당 | GuidanceDTO에 `public_id`를 노출하고 미승인 상태 정책 전 외부 승인·수정 API를 열지 않음 |
| Service 담당 | 저장 전 `full_clean()`, 문의별 version 원자적 할당, reviewer 역할·승인 후 불변 정책 구현 |
| 데이터·Importer 담당 | open code를 후보값으로 임의 정규화하지 말고 AI 작업·문의 일치와 필수 문자열 검증 |
| QA 담당 | PostgreSQL 비공백 CHECK, 부분 Index, 복합 FK, 정책 보류 테스트를 독립 재검증 |
| 후속 테이블 담당 | GuidanceItem·Followup·EvidenceLink FK는 `Guidance.id+inquiry_id` 후보키를 사용 |
| 통합 담당 | 남은 Inquiry 자식·API·Importer·Seed 완료 후 중앙 readiness Gate 갱신 |

## 14. 잔여 위험과 제외 범위

- 검토상태와 근거충분성 canonical YAML이 아직 없다.
- 상태별 검토 묶음, 근거 부족 상담전환, 승인 후 불변 정책은 의도적으로
  보류되어 있다.
- `reviewed_by`의 CONSULTANT·OPERATOR 역할 제한은 DB가 아닌 Service
  권한 Gate가 필요하다.
- Model `clean()`은 raw SQL과 `QuerySet.update()`에 자동 적용되지
  않으므로 정식 Importer·Service에서 명시적 검증이 필요하다.
- 문의별 다음 `guidance_version`의 동시 할당은 Service transaction과
  retry 전략이 필요하다.
- AI UsageGuidance 응답과 Guidance·GuidanceItem의 Adapter 매핑은
  공동 승인 전이다.
- GuidanceItem·EvidenceLink·Serializer·API·Importer·367건 적재·Seed는
  이번 Wave 범위가 아니다.
- 중앙 T-005 readiness의 고정 테이블 수는 병렬 Wave 종료 후 통합
  검증에서 갱신해야 하며 이번 변경에는 포함하지 않았다.
- 따라서 이 문서는 해당 테이블 단위 구현 완료를 증명하며 T-005 전체
  완료 선언이 아니다.

## 15. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·0008·open code·문자열/검토 CHECK·복합 FK/Trigger·SQLite/PostgreSQL·rollback 검증 및 협업 인계 |

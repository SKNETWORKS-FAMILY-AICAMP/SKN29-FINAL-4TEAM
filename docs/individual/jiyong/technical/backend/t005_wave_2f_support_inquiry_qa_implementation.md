# T-005 Wave 2F `support_inquiry_qa` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 연계 요구사항: `FR-010`, `FR-011`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 범위: 고객지원 묶음 1개 테이블

## 1. 결과 요약

문의별 정적·규칙·AI·상담사 추가 질문과 선택적 고객 답변을 순서대로
보존하는 `support_inquiry_qa`를 `inquiries` 앱의 Django Runtime Model과
번호 Migration으로 구현했다.

역사 테이블사전의 14개 논리 필드를 보존하면서 식별자 ADR에 따라 내부
`BigAutoField id`와 외부 공개용 unique UUID `public_id`를 분리했다.
부모 문의, AI 실행, 답변자 참조는 현재 Runtime의 bigint PK를 사용하므로
실제 컬럼은 15개이다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | test·local settings 모두 통과, 0 issues |
| Inquiries Migration drift | 통과, `No changes detected` |
| 신규 집중 테스트 | `15 passed` |
| Inquiry·SymptomAssessment·AIRun 포함 회귀 | `54 passed` |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `0007 → 0006 → 0007` | 테이블·트리거 제거와 복원 통과 |
| 빈 PostgreSQL 전체 Migration | 통과 |
| PostgreSQL 물리 Catalog | bigint/UUID/JSONB, 부분 UNIQUE, CHECK, Index, 복합 FK 확인 |
| PostgreSQL 유효 쓰기 | AI 질문·JSON 배열 답변·미승인 open code 저장 통과 |
| PostgreSQL 위반 쓰기 | 복합 관계·부모 변경·AI 출처·답변·부분 UNIQUE·순번 위반 차단 |
| PostgreSQL `0007 → 0006 → 0007` | 테이블·복합 FK·부분 UNIQUE 제거와 복원 통과 |
| 임시 검증 자원 | SQLite 파일 제거, PostgreSQL DB 부재 확인 |

이 결과는 `support_inquiry_qa` 한 테이블의 로컬 구현·검증 결과이다.
추가 질문 생성 Agent, Serializer·API, 정식 Importer, Seed, 중앙 T-005
readiness는 이번 Wave에서 수정하거나 완료로 선언하지 않았다.

## 2. 기준 문서 적용 우선순위

| 우선 | 기준 | 이번 구현의 적용 내용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | Backend·DB 담당 경계, 번호 Migration, 작업 후 즉시 검증, 상대경로 인계 |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 bigint PK, 공개 UUID, 내부 bigint FK |
| 3 | [상태이력 ADR 0011](<../../../../adr/0011-t005-status-history-idempotency-scope.md>) | 질문·답변 누적을 상태전이 원장이나 HTTP 멱등 원장으로 오인하지 않음 |
| 4 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 최신 식별자 정책과 canonical code 우선 정책 |
| 5 | [테이블사전](<../../../../database/watercare_table_dictionary.md>) | 14개 역사 필드, 순번·질문 UNIQUE, 답변·AI 출처 CHECK, Index |
| 6 | [AI 작업유형 코드](<../../../../../contracts/codes/ai-task-types.yaml>)·[Schema 검증상태 코드](<../../../../../contracts/codes/ai-schema-validation-statuses.yaml>) | AI 질문은 PASSED 상태의 GENERATE_QUESTIONS 실행만 사용 |
| 7 | [AI FollowUpQuestion Schema](<../../../../../contracts/ai/common/FollowUpQuestion.schema.json>) | AI 질문 ID·문장·선택지의 향후 Service 입력 경계 참고 |
| 8 | [FollowUpAnswerRequest](<../../../../../contracts/api/components/schemas/questionnaire/FollowUpAnswerRequest.yaml>) | 현재 properties가 비어 있어 API 답변 DTO는 미확정임을 확인 |

Physical Contract v1.2에는 `support_inquiry_qa` 개별 필드 override가 없다.
따라서 식별자·canonical code 공통 정책은 최신 계약을 따르고, 나머지
필드·제약·Index는 테이블사전을 구현 기준으로 사용했다.

## 3. 계약 충돌과 해소 결과

| 항목 | 역사·현재 자료 | 이번 구현 | 판단 이유 |
| --- | --- | --- | --- |
| 기본 PK | 테이블사전 UUID `id` | bigint 자동 증가 `id` | ADR 0010이 최신 확정 결정 |
| 공개 식별자 | 별도 필드 없음 | unique UUID `public_id` | 내부 조인과 API 식별자 분리 |
| 세 부모 FK | 역사 UUID | bigint | Inquiry·AIRun·Accounts 현재 PK 타입 |
| 답변유형 후보 | 5개 값 제안 | open `CharField`, 기본 FREE_TEXT | answer-types canonical YAML 부재 |
| 질문주체 후보 | 4개 값 제안 | open `CharField`, 기본 RULE | question-origins canonical YAML 부재 |
| AI 질문 출처 | AI이면 실행 필요 | AI와 `source_ai_run`을 양방향 일치 | 역사 관계 CHECK를 그대로 보존 |
| AI 질문 작업 | GENERATE_QUESTIONS·PASSED | Model `clean()` Application Policy | canonical AIRun 코드로 확인 가능 |
| AI `question_id` 길이 | AI Schema 최대 100 | DB `question_code` 최대 80 | T-005 테이블사전 80을 임의 변경하지 않고 계약 정합화 보류 |
| 답변 API DTO | 빈 `properties` | API 미구현 | 필드 매핑을 임의 발명하지 않음 |

`question_id` 최대 길이 100과 `question_code varchar(80)`은 향후 Agent와
Backend Service를 연결하기 전에 해결해야 한다. 현재 구현은 역사 DB
계약인 80자를 유지한다. Service에서 조용히 자르거나 해시로 바꾸면
질문 중복 판정이 달라질 수 있으므로, AI·Backend 계약 담당자가 길이와
매핑 규칙을 승인한 후 별도 Migration·Schema 버전으로 반영해야 한다.

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [InquiryQA Model](<../../../../../backend/apps/inquiries/models/inquiry_qa.py>) | 필드, 부분 UNIQUE, 답변·AI 관계 CHECK, Application Policy |
| [Inquiries Model export](<../../../../../backend/apps/inquiries/models/__init__.py>) | Django Runtime Model registry에 `InquiryQA` 공개 |
| [Inquiries 0007 Migration](<../../../../../backend/apps/inquiries/migrations/0007_inquiryqa.py>) | 테이블과 PostgreSQL·SQLite 복합 무결성 설치 |
| [집중 단위 테스트](<../../../../../backend/tests/unit/inquiries/test_inquiry_qa_model.py>) | 식별자·open code·UNIQUE·CHECK·PROTECT·복합 관계 검증 |
| [부모 AIRun 구현서](<t005_wave_1c_aiops_ai_run_implementation.md>) | AI 실행의 상태·작업유형·복합 부모 후보키 |
| [선행 SymptomAssessment 구현서](<t005_wave_2b_support_symptom_assessment_implementation.md>) | 바로 앞 `inquiries.0006` Migration과 고객지원 Wave 인계 |

## 5. Runtime 필드

| 구분 | 필드 | 구현·무결성 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK |
| 공개 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 수정 불가 |
| 대상 문의 | `inquiry_id` | `support_inquiry.id`, bigint, PROTECT |
| 표시 순서 | `sequence_no` | positive smallint, 문의별 UNIQUE |
| 질문 업무코드 | `question_code` | nullable `varchar(80)`, 문의별 조건부 UNIQUE |
| 질문 문장 | `question_text` | 필수 text |
| 답변유형 | `answer_type_code` | 필수 open code, 기본 FREE_TEXT |
| 정규화 답변 | `answer_text` | nullable text |
| 원형 답변 | `answer_payload` | nullable JSONB, 배열·object·scalar 허용 |
| 질문 생성주체 | `asked_by_type_code` | 필수 open code, 기본 RULE |
| 원천 AI 실행 | `source_ai_run_id` | nullable `aiops_ai_run.id`, bigint, PROTECT |
| 답변자 | `answered_by_id` | nullable `accounts_user.id`, bigint, PROTECT |
| 답변 시각 | `answered_at` | nullable timestamptz |
| 감사 시각 | `created_at`, `updated_at` | 자동 생성·갱신 |

`answer_payload`는 다중선택 배열, 단위가 있는 object, boolean·number 등
원형 값을 보존하기 위한 필드다. 특정 JSON 최상위 타입으로 고정하라는
승인 계약이 없으므로 object-only CHECK를 추가하지 않았다.

## 6. 승인 코드와 보류 코드

| 코드·정책 | 기준 상태 | 현재 구현 | 후속 조건 |
| --- | --- | --- | --- |
| `AIRun.task_type_code` | OWNER_BASELINE YAML | GENERATE_QUESTIONS 비교 | 기존 AIRun TextChoices·DB CHECK 재사용 |
| `AIRun.schema_validation_status_code` | OWNER_BASELINE YAML | PASSED 비교 | 기존 AIRun TextChoices·DB CHECK 재사용 |
| `answer_type_code` | 후보값만 존재 | open `CharField` | answer-types YAML OWNER 승인 필요 |
| `asked_by_type_code` | 후보값만 존재 | open `CharField` | question-origins YAML OWNER 승인 필요 |

따라서 다음 두 allowed-value CHECK는 의도적으로 설치하지 않았다.

```text
ck_support_inquiry_qa_answer_type_code_allowed
ck_support_inquiry_qa_asked_by_type_code_allowed
```

역사 후보인 SINGLE_CHOICE, MULTI_CHOICE, FREE_TEXT, BOOLEAN, NUMBER과
STATIC, RULE, AI, CONSULTANT는 설계 참고값이다. 기본값 FREE_TEXT와
RULE은 역사 필드 호환성을 보존할 뿐 전체 허용집합 승인으로 해석하지
않는다.

## 7. DB 무결성

| 제약·Index | 방지하거나 지원하는 내용 |
| --- | --- |
| `ux_inquiry_qa_sequence` | 같은 문의의 표시 순번 중복 차단 |
| `ux_inquiry_qa_question` | question_code가 있을 때 같은 문의의 질문 중복 차단 |
| `ck_inquiry_qa_sequence` | 0 이하 순번 차단 |
| `ck_inquiry_qa_answer_consistency` | 답변 시각이 있는데 답변자 또는 실제 답변이 없는 행 차단 |
| `ck_inquiry_qa_ai_origin` | AI 질문과 source AI run의 불완전·반대 조합 차단 |
| `ix_inquiry_qa_answered` | 문의별 답변 시각 조회 |
| `ix_inquiry_qa_ai_run` | AI 실행·문의별 생성 질문 추적 |

질문코드 UNIQUE는 NULL을 허용하는 부분 인덱스이다.

```sql
CREATE UNIQUE INDEX ux_inquiry_qa_question
ON support_inquiry_qa (inquiry_id, question_code)
WHERE question_code IS NOT NULL
```

`ck_inquiry_qa_answer_consistency`는 역사 계약과 동일하게 `answered_at`이
설정된 행만 답변자와 실제 답변을 필수로 요구한다. 답변 내용이 먼저 임시
저장되고 시각이 나중에 확정되는 흐름까지 DB에서 임의 차단하지 않았다.
Service는 최종 제출 시 `answered_by`, 답변 값, `answered_at`을 같은
트랜잭션에서 갱신해야 한다.

첫 SQLite Catalog 검증에서는 Django FK 기본 동작 때문에 계약에 없는
`answered_by_id` 단독 인덱스가 생성됐다. Model과 Migration에
`db_index=False`를 명시한 뒤 테스트와 빈 DB Migration을 다시 실행해,
명시된 두 일반 Index와 하나의 부분 UNIQUE만 생성됨을 확인했다.

## 8. 같은 문의 복합 무결성과 AI 정책

PostgreSQL에서는 다음 복합 FK가 질문과 AI 실행의 문의 문맥을 같이
강제한다.

```sql
FOREIGN KEY (source_ai_run_id, inquiry_id)
REFERENCES aiops_ai_run (id, inquiry_id)
MATCH SIMPLE
ON DELETE RESTRICT
```

SQLite는 같은 의미를 다음 세 트리거로 구현한다.

```text
fk_inquiry_qa_context_child_insert
fk_inquiry_qa_context_child_update
fk_inquiry_qa_context_parent_update
```

Model `clean()`은 관계가 같은 문의인지 확인하고, AI 질문이면 원천 실행이
`task_type_code=GENERATE_QUESTIONS`,
`schema_validation_status_code=PASSED`인지 검증한다. 다른 행의 속성은
단순 CHECK로 표현할 수 없으므로 이 부분은 Application Policy이다.
Service·Serializer는 저장 전에 `full_clean()`을 호출해야 하며 raw SQL
Importer도 같은 검증을 별도로 수행해야 한다.

## 9. Migration 순서와 rollback

`inquiries.0007_inquiryqa`의 직접 의존성은 다음과 같다.

```text
accounts.0003_promote_integer_primary_keys
audit.0002_airun
inquiries.0006_symptomassessment
  └─ inquiries.0007_inquiryqa
```

Accounts 0003을 명시적으로 선행해 `answered_by_id`가 legacy 문자열이
아닌 bigint로 생성되도록 했다. `audit.0003_airetrievalrun`은
InquiryQA의 부모가 아니므로 불필요한 직접 의존성을 추가하지 않았다.

SQLite와 PostgreSQL에서 모두 `0007 → 0006 → 0007`을 실행했다.
이번 rollback은 `workflow.0004`의 선행점인 `inquiries.0006`을 남기므로
Workflow Migration을 역적용하지 않고 InquiryQA 테이블만 제거했다.

## 10. 작업→검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·ADR·Physical v1.2·테이블사전·YAML 대조 | 필드·관계·승인/보류 코드 분류 | 1개 테이블 범위 확정 |
| 2 | Model·export 구현 | Django system check | 0 issues |
| 3 | 번호 Migration `inquiries.0007` 작성 | Migration drift | `No changes detected` |
| 4 | 식별자·open code·UNIQUE·CHECK·PROTECT 테스트 | 신규 집중 테스트 | `15 passed` |
| 5 | 빈 SQLite 전체 Migration | 컬럼·제약·Index·3 Trigger Catalog 조회 | 계약 외 FK Index 1개 발견 |
| 6 | `answered_by_id` 자동 Index 제거 | drift·집중 테스트 재실행 | drift 0, `15 passed` |
| 7 | SQLite rollback → reapply | 테이블·Trigger 부재 후 정확한 Index 복원 | 통과 |
| 8 | 관련 Inquiry·AIRun 회귀 | 네 테스트 파일 | `54 passed` |
| 9 | 격리된 빈 PostgreSQL 전체 Migration | bigint/uuid/jsonb·CHECK·부분 UNIQUE·FK·Index | 통과 |
| 10 | PostgreSQL 유효 쓰기 | AI 질문·JSON 배열 답변·open code | 모두 통과 |
| 11 | PostgreSQL 위반 쓰기 6종 | 복합 자식, 부모 변경, AI 출처, 답변, 질문 중복, 순번 | 모두 `IntegrityError` |
| 12 | PostgreSQL rollback → reapply | 테이블·복합 FK·부분 UNIQUE 재조회 | 통과 |
| 13 | 임시 자원 정리 | SQLite 파일·`pg_database` 조회 | 모두 부재 |

## 11. 재현 명령

저장소 루트 기준 SQLite 집중 Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    check --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations inquiries --check --dry-run `
    --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\inquiries\test_inquiry_qa_model.py `
    backend\tests\unit\inquiries\test_symptom_assessment_model.py `
    backend\tests\unit\audit\test_ai_run_model.py `
    backend\tests\unit\inquiries\test_t022_models.py -q
```

PostgreSQL Gate는 기존 개발 DB가 아닌 새 빈 격리 DB에서 실행한다.

```powershell
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate inquiries 0006 --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate inquiries 0007 --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --check --settings=config.settings.local
```

## 12. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | `inquiries.0007`, 세 직접 의존성, 부분 UNIQUE와 복합 FK/Trigger 이름 유지 |
| PM·계약 담당 | answer-type·question-origin canonical YAML의 값·버전·소유자 승인 |
| AI 담당 | `question_id` 최대 길이 100과 DB `question_code` 80의 정합화 결정, PASSED GENERATE_QUESTIONS 실행 제공 |
| API 담당 | 비어 있는 FollowUpAnswerRequest를 버전 있는 실제 DTO로 확정하고 `public_id` 노출 |
| Service 담당 | 저장 전 `full_clean()`, 질문 순번 원자적 할당, 답변자·값·시각 동시 갱신 |
| 데이터·Importer 담당 | open code를 임의 후보값으로 정규화하지 말고 AI 작업·문의 일치 검증 |
| QA 담당 | PostgreSQL 부분 UNIQUE, 복합 FK, 여섯 위반 쓰기를 독립 재검증 |
| 통합 담당 | Agent·API·Importer와 남은 Inquiry 자식 완료 후 중앙 readiness·Seed Gate 갱신 |

## 13. 잔여 위험과 제외 범위

- `answer_type_code`와 `asked_by_type_code` 허용집합은 미승인 상태이다.
- AI `question_id` 100자와 DB `question_code` 80자의 정합화 결정이
  필요하다.
- FollowUpAnswerRequest가 빈 Schema이므로 API 답변 형식·필수값·멱등
  계약이 아직 없다.
- Application Policy는 raw SQL 쓰기를 자동 차단하지 않으므로 정식
  Importer에서 GENERATE_QUESTIONS·PASSED 검증이 필요하다.
- 질문 순번 동시 할당 전략은 Service·transaction 범위이며 이번
  테이블 구현에 포함하지 않았다.
- AI 질문 생성 Agent, Serializer·API, 367건 운영 적재와 Seed는 이번
  Wave 범위가 아니다.
- 중앙 T-005 readiness의 고정 테이블 수는 병렬 Wave 종료 후 통합
  검증에서 갱신해야 하며 이번 변경에는 포함하지 않았다.
- 따라서 이 문서는 해당 테이블 단위 구현 완료를 증명하며 T-005 전체
  완료 선언이 아니다.

## 14. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·0007·부분 UNIQUE·복합 FK/Trigger·SQLite/PostgreSQL·rollback 검증 및 협업 인계 |

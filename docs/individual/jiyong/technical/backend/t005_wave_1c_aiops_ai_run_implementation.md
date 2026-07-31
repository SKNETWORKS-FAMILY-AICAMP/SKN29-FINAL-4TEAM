# T-005 Wave 1C `aiops_ai_run` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_VERIFIED`  
> 기준 계약: Physical Contract v1.2

## 1. 결과

`aiops_ai_run`을 Django Runtime Model과 번호 Migration으로 구현했다.
문의별 AI 실행을 재현하고 추적할 수 있도록 내부 정수 PK, 공개 UUID,
상관관계 UUID, 입력 해시, 멱등키, 모델·프롬프트 버전, 스키마 검증 결과,
실행 상태와 오류 정보를 하나의 실행 원장에 저장한다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Migration drift | 통과, `No changes detected` |
| 신규·기존 Audit 집중 테스트 | 통과, `25 passed` |
| PostgreSQL DDL 컴파일 | 통과, `sqlmigrate audit 0002` |
| T-005 구현 매핑 | `aiops_ai_run` IMPLEMENTED |
| T-005 전체 판정 | `NOT_READY`, 현재 병렬 작업 포함 15/32 구현 |

15/32 수치는 이 Wave의 `aiops_ai_run`과 같은 시점에 진행된 Accounts
정수 PK 전환까지 포함한 작업 트리 기준이다. 이 문서는 T-005 전체 완료를
선언하지 않는다.

## 2. 포함·제외 범위

### 포함

- `AIRun` Runtime Model과 Audit Model export
- `aiops_ai_run` 생성 Migration
- Inquiry `PROTECT` 관계와 실행 추적용 Index
- 멱등성·상태 수명주기·재현성·JSON 형태·해시 형식 DB 제약
- SQLite 집중 테스트와 PostgreSQL DDL 컴파일 검증

### 제외

- Accounts Model, 인증, JWT, Seed 수정
- AI 실행 Service·Repository·Serializer·API Route
- 실제 모델 호출과 프롬프트 구현
- Retrieval Run·Hit 및 지식검색 테이블
- 운영 PostgreSQL 데이터베이스에 대한 Migration 적용
- T-005 공용 readiness 테스트의 병렬 작업 통합 기대값 갱신

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [AIRun Model](<../../../../../backend/apps/audit/models/ai_run.py>) | 필드·관계·상태 코드·DB 제약·Index 선언 |
| [Audit Model export](<../../../../../backend/apps/audit/models/__init__.py>) | Runtime Model Registry에 `AIRun` 공개 |
| [Audit 0002 Migration](<../../../../../backend/apps/audit/migrations/0002_airun.py>) | `aiops_ai_run` 물리 테이블 생성 |
| [AIRun 단위 테스트](<../../../../../backend/tests/unit/audit/test_ai_run_model.py>) | 정상 저장, 제약 위반, 멱등성, 삭제 보호 검증 |

Migration은 `audit.0001_initial`과
`inquiries.0005_inquiry_ux_inquiry_id_subscription` 이후에 실행된다.

## 4. 핵심 계약

| 구분 | 구현 |
| --- | --- |
| 내부 PK | `BigAutoField id` |
| 외부 식별자 | `UUIDField public_id`, 자동 생성·UNIQUE |
| 업무 관계 | `inquiry_id bigint`, `PROTECT` |
| 요청 추적 | `idempotency_key`, `correlation_id UUID` |
| 재현 정보 | provider, model, model config/version, prompt version |
| 입력 무결성 | JSON object 입력과 소문자 SHA-256 64자리 |
| 출력 검증 | raw output, validated JSON object, validation status/errors |
| 수명주기 | QUEUED → RUNNING/RETRYING → 종료 상태 |
| 종료 상태 | SUCCEEDED, NO_EVIDENCE, FAILED, TIMED_OUT, CANCELLED |
| 실행 지표 | latency, input/output token, retry count |

DB 상관관계 ID는 Physical Contract에 따라 UUID로 유지했다. API 예시나
레거시 문자열 ID를 DB 컬럼 형식으로 확장하지 않았다.

## 5. DB 제약과 검증 의도

| 제약 묶음 | 방지하는 문제 |
| --- | --- |
| `ux_ai_run_idempotency` | 동일 실행 요청의 중복 저장 |
| `ck_ai_run_lifecycle` | 상태와 시작·완료 시각의 모순 |
| `ck_ai_run_reproducibility` | 실행 후 모델·프롬프트 정보 누락 |
| `ck_ai_run_success` | 검증되지 않은 출력을 성공으로 기록 |
| `ck_ai_run_failure` | 오류 코드 없이 실패·시간초과 종료 |
| `ck_ai_run_schema_failure` | 원문·오류 목록 없이 스키마 실패 기록 |
| `ck_ai_run_json_objects` | 입력·검증 출력의 배열/스칼라 저장 |
| `ck_ai_run_schema_errors_array` | 검증 오류의 object 저장 |
| `ck_ai_run_input_hash` | SHA-256이 아닌 입력 해시 저장 |
| `ck_ai_run_nonnegative_metrics` | 음수 지연·토큰·재시도 횟수 |
| 상태·작업 코드 CHECK | 미승인 코드의 DB 우회 저장 |

JSON 제약 표현은 SQLite에서 `JSON_TYPE`/`JSON_ARRAY_LENGTH`,
PostgreSQL에서 `jsonb_typeof`/`jsonb_array_length`로 컴파일된다.

## 6. 작업-검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 계약 필드·관계·코드·제약 매핑 | Physical v1.2와 테이블 명세 비교 | 구현 단위를 1개 테이블로 고정 |
| 2 | Model·export 구현 | `manage.py check`, Migration dry-run | Meta enum 참조를 SQL literal로 교정 |
| 3 | `0002_airun` 작성 | `makemigrations --check --dry-run` | drift 0 |
| 4 | 신규 제약 테스트 작성 | 신규+기존 Audit 테스트 | Accounts 병렬 정수 PK 변경에 맞춰 fixture의 명시적 문자열 PK 제거 |
| 5 | 집중 회귀 재실행 | Audit 테스트 25건 | 전부 통과 |
| 6 | PostgreSQL SQL 검증 | `sqlmigrate audit 0002` | bigint·UUID·jsonb·FK·CHECK·Index DDL 생성 확인 |
| 7 | T-005 Auditor 재실행 | Model·Runtime·Migration 매핑 | `aiops_ai_run` IMPLEMENTED 확인 |

## 7. 재현 명령

저장소 루트에서 실행한다.

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.local
& $python manage.py makemigrations `
    --check --dry-run `
    --settings=config.settings.local
& $python -m pytest `
    .\tests\unit\audit\test_ai_run_model.py `
    .\tests\unit\audit\test_models.py `
    -q
& $python manage.py sqlmigrate `
    audit 0002 `
    --settings=config.settings.local
```

T-005 매핑은 저장소 루트에서 별도로 확인한다.

```powershell
& .\backend\.venv\Scripts\python.exe `
    .\scripts\database\audit_t005_implementation_readiness.py `
    --settings config.settings.test
```

## 8. 협업 인계

| 담당 | 확인·후속 작업 |
| --- | --- |
| 최지용 | Migration 번호·의존성 유지, AI Service 구현 시 `AIRun` 상태 전이 원칙 적용 |
| AI/API 담당 | 공개 응답에는 `public_id` 사용, 재시도에는 같은 멱등키 정책 확정 |
| 데이터 담당 | 실행 원장은 운영 시 생성되는 데이터이므로 정적 Seed 추가 금지 |
| PM/계약 담당 | 작업 유형·상태 코드 변경 시 Physical Contract와 Model을 함께 변경 |
| 통합 담당 | 병렬 Accounts 작업과 함께 readiness 기대값을 현재 매핑으로 갱신 |

API·Service 구현 시 DB CHECK를 피하기 위한 임의 값 삽입 대신 다음 전이를
지켜야 한다.

1. `QUEUED`: 시작·완료 시각 없이 저장한다.
2. `RUNNING`/`RETRYING`: 시작 시각과 모델·프롬프트 재현 정보를 저장한다.
3. 성공 종료: 완료 시각, PASSED, 검증 출력 object를 함께 저장한다.
4. 실패·시간초과: 완료 시각과 오류 코드를 함께 저장한다.
5. 스키마 실패: raw output과 비어 있지 않은 오류 배열을 함께 저장한다.

## 9. 잔여 위험

- `sqlmigrate`로 PostgreSQL DDL 컴파일까지 확인했으나, 이 Wave에서는
  별도 빈 PostgreSQL DB에 실제 적용·역방향 적용하지 않았다.
- T-005 전체는 나머지 17개 계약 테이블과 통합 Gate가 남아 `NOT_READY`다.
- 공용 readiness 단위 테스트의 기존 고정 수치는 병렬 Wave 통합 시점에
  한 번에 갱신해야 한다.
- AI Service·API가 아직 없으므로 실제 실행 중 상태 전이와 재시도 경쟁
  조건은 후속 Wave의 통합 테스트 대상이다.

## 10. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | `aiops_ai_run` Model·Migration·집중 테스트·PostgreSQL DDL 검증 및 인계 작성 |

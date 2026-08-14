# 이동윤 → 최지용: Backend pgvector `vector_dims(unknown)` Django 사전검증 경고 재현 회신 v0.1

> 작성일: 2026-08-14
>
> 실행 Branch: `dongyoon`
>
> 실행 HEAD: `d6ab1e480e090369a03360aa385c74eff64720a6`
>
> 환경 범위: 이동윤 Host `LOCAL_QA_ISOLATED`
>
> 대상: Backend `ChunkEmbedding` CheckConstraint의 Django 사전검증 경고
>
> 제외: Secret·DSN·Password·공식 원본 실제 경로·Fixture Vector 본문

## 1. 회신 결론

Canonical Import의 신규 Embedding 생성 경로에서 다음 PostgreSQL 경고를 재현했다.

```text
function vector_dims(unknown) is not unique
HINT: Could not choose a best candidate function. You might need to add explicit type casts.
```

경고는 신규 `ChunkEmbedding` 인스턴스에 대한 Django `full_clean()`의
CheckConstraint 사전검증에서 발생했다. 명령은 Exit 0이었고 DB Insert, 동일 입력
Replay, Crosswalk, Readiness Audit와 AI 실제 pgvector 검색은 모두 통과했다.

따라서 현재 판정은 `P1_BACKEND_VALIDATION_WARNING_NON_BLOCKING`이다. G1-A pgvector
기술검증을 막는 P0 장애는 아니지만, 애플리케이션 단계의 Constraint 검증이 DB 오류를
경고로 남기고 계속 진행하므로 Backend 관할에서 명시적 형 변환 또는 별도 검증 방식을
확정해야 한다.

```ini
reproduced=YES
reproduction_scope=NEW_CHUNK_EMBEDDING_FULL_CLEAN
django_prevalidation_warning=YES
import_exit=0
database_insert=PASS
import_replay=PASS
crosswalk_replay=PASS
readiness_audit=READY
actual_pgvector_search=PASS
severity=P1_NON_BLOCKING_VALIDATION_QUALITY
next_owner=최지용_BACKEND
secret_values_printed=NO
```

## 2. 실행 기준과 환경

```ini
branch=dongyoon
head=d6ab1e480e090369a03360aa385c74eff64720a6
git_clean=YES
fixed_main_ancestor=YES
python=3.13.13
postgresql=16.15
pgvector=0.8.6
database_scope=LOCAL_QA_ISOLATED
```

이번 PostgreSQL은 김은진 QA 기록의 `16.14`와 다른 `16.15`다. pgvector는 계약과
같은 `0.8.6`이며 결과는 김은진 Host 증거를 대체하지 않고 별도 로컬 재현으로만
사용한다.

## 3. 재현 절차와 결과

공식 PDF는 ACL 보호 디렉터리에서 크기·SHA가 일치하는 파일 1개만 Loader가 찾아
현재 Runtime Process에 주입했다. 실제 경로는 출력하지 않았다.

```powershell
$loaded = . .\scripts\deployment\import_team_integration_env.ps1 `
  -Role Runtime `
  -LoadOfficialSource `
  -OfficialSourceSearchRoots @($approvedSourceRoot)

$fixture = '.\.runtime\backend-ai\canonical_embedding_fixture_v1.json'
$fixtureHash = (
  Get-FileHash -LiteralPath $fixture -Algorithm SHA256
).Hash.ToLowerInvariant()

.\backend\.venv\Scripts\python.exe -B `
  .\backend\manage.py import_ai_canonical_evidence `
  --settings=config.settings.local `
  --embedding-fixture $fixture `
  --embedding-fixture-sha256 $fixtureHash `
  --verified-by DEMO-OPERATOR-001
```

신규 데이터가 없던 최초 Dry-run과 Apply에서 신규 Embedding 검증마다 위 경고가
반복됐지만 두 명령 모두 Exit 0이었다. 최초 Apply 결과는 다음과 같다.

```ini
products_created=1
batches_created=1
documents_created=1
pages_created=3
scopes_created=1
chunks_created=7
embeddings_created=7
all_updated=0
```

동일 입력 Apply Replay는 다음과 같이 멱등이었다.

```ini
all_created=0
all_updated=0
products_unchanged=1
batches_unchanged=1
documents_unchanged=1
pages_unchanged=3
scopes_unchanged=1
chunks_unchanged=7
embeddings_unchanged=7
```

Import 완료 후 동일 Dry-run을 다시 실행하면 기존 Embedding을 조회하므로 신규
`full_clean()` 경로에 들어가지 않는다. 이 재실행은 Exit 0,
`VECTOR_DIMS_UNKNOWN_WARNING_COUNT=0`, Embedding `unchanged=7`이었다.

## 4. 발생 경계

Backend Importer는 Embedding 자연키가 없을 때 모델 인스턴스를 만들고
`full_clean()` 후 Insert한다.

- `backend/apps/evidence/services/canonical_evidence_importer.py:615`
- `backend/apps/evidence/services/canonical_evidence_importer.py:627`
- `backend/apps/evidence/services/canonical_evidence_importer.py:628`

`ChunkEmbedding`의 DB CheckConstraint는 정수 필드와
`vector_dims(embedding)` 결과가 모두 1024인지 검사한다.

- `backend/apps/evidence/models/chunk_embedding.py:24`
- `backend/apps/evidence/models/chunk_embedding.py:81`
- `backend/apps/evidence/models/chunk_embedding.py:85`

실제 DB Column을 사용하는 저장 Constraint는 정상 동작했다. 경고는 Django가
저장 전 Constraint 검증을 위해 Vector 값을 Query Parameter로 전달할 때 PostgreSQL이
해당 Parameter를 `unknown`으로 보고 `vector_dims` Overload를 하나로 결정하지 못한
경계로 판단한다.

## 5. 영향 범위

확인된 영향은 Django Constraint 사전검증의 신뢰도와 경고 노이즈다. 현재 실행에서
다음 Runtime 결과 손상은 발견되지 않았다.

- Import Transaction 부분 저장 없음
- 7개 Embedding 모두 1024차원으로 저장
- 동일 Fixture Replay에서 Create·Update 0
- Crosswalk `7/7`, Page Link `8`
- Readonly View 8열·7행
- AI Role의 Base Table SELECT·View DML·Schema CREATE 차단
- Readiness Audit `READY`, Blocker 0
- AI 실제 pgvector 검색 `1 passed in 9.97s`
- Backend 표적 회귀 `81 passed in 11.88s`

다만 Django가 사전검증 DB 오류를 경고 후 계속 진행하므로, 잘못된 값이 들어오는
별도 경로에서 애플리케이션 수준 검증이 항상 의도대로 동작한다고 확대할 수 없다.
DB Constraint가 최종 방어선이라는 사실과 사전검증 품질은 구분해야 한다.

## 6. Backend 확인 요청

다음 중 Backend가 선택한 방식으로 PostgreSQL에서 Vector 표현식의 Type을 명시해
사전검증 경고를 제거해 달라.

1. `VectorDimensions.as_postgresql()`에서 대상 표현식을 명시적으로 `vector`로 Cast
2. Django Constraint 검증용 Typed Expression 또는 별도 Validator 적용
3. pgvector/Django가 생성하는 Constraint 검증 SQL을 고정하는 다른 Backend 방식

단순히 `full_clean(validate_constraints=False)`로 경고만 숨기는 방식은 DB Insert 전
검증을 약화하므로 완료 조건으로 인정하지 않는다.

완료 조건은 다음과 같다.

```ini
valid_embedding_prevalidation_warning=0
valid_7x1024_import=PASS
invalid_dimension_rejected=PASS
invalid_vector_length_rejected=PASS
database_constraint_preserved=PASS
import_replay_created_updated=0
readiness_audit=READY
postgresql_regression_test=PASS
makemigrations_check=NO_CHANGES
secret_values_printed=NO
```

수정 후에는 신규 Embedding이 없는 Replay만 실행하지 말고, 폐기 가능한 PostgreSQL
Transaction 또는 QA DB에서 실제 신규 Embedding 생성 경로를 다시 실행해야 한다.

## 7. 회신 요청 형식

```ini
reviewed_commit=<40_SHA>
vector_dims_unknown_root_cause=CONFIRMED|REVISED
backend_fix_status=APPLIED|HOLD
new_embedding_warning_count=<INTEGER>
invalid_dimension_gate=PASS|FAIL|NOT_RUN
invalid_vector_length_gate=PASS|FAIL|NOT_RUN
database_constraint=PASS|FAIL|NOT_RUN
import_replay=PASS|FAIL|NOT_RUN
readiness_audit=READY|BLOCKED|NOT_RUN
remaining_blocker=<NONE_OR_REASON>
```

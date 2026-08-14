# Backend-AI Canonical Embedding Fixture v1 계약 보완·검증 가이드

## 1. 문서 정보

- 작성일: 2026-08-14 KST
- 작성자: 최지용 — Backend·Database
- 범위: Backend가 AI Embedding Fixture를 생성·검증·Import하기 위한 파일 계약
- 상태: `AUTHOR_VERIFIED / AI_EXPORTER_AND_TEAM_POSTGRESQL_PENDING`
- 현재 작업 기준: `origin/jiyong@ad9fd0661f28259a5fd1117705a86cef7dca7646` + 아래 보완
- 현재 확인 main: `origin/main@8238696017ea051b62b74bad06c2eb7a27372ac2`

이 문서는 Fixture 파일 계약만 다룬다. 공개 API, DB Schema, Migration, 모델 선택,
팀 PostgreSQL 권한, 실제 OpenAI 호출 결과는 범위 밖이다.

## 2. 해결하려는 계약 공백

기존 제안에는 7×1024 Vector와 파일 Hash는 있었지만 다음 항목이 명시적으로
고정되지 않았다.

- JSON 숫자만으로 소실되는 원래 Vector dtype
- `rows` 배열의 결정적 순서
- `NaN`·`Infinity` 직렬화 차단
- 정본 문자열의 Unicode NFC 여부
- AI Exporter와 Backend Importer가 공유할 실제 Schema·Status 값

## 3. 확정한 Fixture 계약

```ini
fixture_path=.runtime/backend-ai/canonical_embedding_fixture_v1.json
schema_version=1.0.0
status=GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT
package_format=UTF8_COMPACT_SORTED_JSON
json_options=ensure_ascii:false,sort_keys:true,separators:COMPACT,allow_nan:false
trailing_newline=NO
row_order=chunk_id_ASC
embedding_dtype=FLOAT32
vector_dimension=1024
vector_finite_required=YES
manual_rounding=NONE
nfc_policy=VALIDATE_ONLY_NO_MUTATION
package_hash=SHA256_OF_EXACT_WHOLE_FILE_BYTES
db_replay_vector_tolerance=1e-6
```

Root 필드는 다음과 같다.

```text
schema_version,status,model_name,model_revision,dimension,index_version,
chunk_set_sha256,embedding_dtype,rows
```

Row 필드는 다음과 같다.

```text
chunk_id,chunk_text_sha256,embedding
```

파일 전체 Hash는 자기참조를 피하기 위해 Fixture 내부에 넣지 않는다. 실행 보고서나
Sidecar에서 계산한다. 환경 간 동일성은 파일 Hash 강제가 아니라 Metadata Hash와
Vector 허용오차 `1e-6`으로 판정한다.

## 4. Backend 구현

### 4.1 Builder

- [build_ai_canonical_embedding_fixture.py](../../../../scripts/database/build_ai_canonical_embedding_fixture.py)
- `embedding_dtype=FLOAT32`를 Root에 기록한다.
- 7개 Row를 `chunk_id ASC`로 정렬한다.
- `chunk_id`와 정본 `chunk_text`가 이미 NFC인지 검증하며 문자열을 자동 변환하지 않는다.
- Bool·문자열·`NaN`·`Infinity` Vector를 Fail-closed한다.
- `allow_nan=False`인 compact sorted UTF-8 JSON을 개행 없이 생성한다.

### 4.2 Importer

- [canonical_evidence_importer.py](../../../../backend/apps/evidence/services/canonical_evidence_importer.py)
- Root·Row 필드 집합, Schema, Status, Model, Revision, Dimension, Index Version,
  Chunk Set Hash와 `embedding_dtype=FLOAT32`를 정확히 검증한다.
- 파일 Byte가 canonical compact sorted JSON과 다르면 거부한다.
- Row가 `chunk_id ASC`가 아니거나 ID가 중복되면 거부한다.
- 정본 Text Hash 입력이 비NFC이거나 Vector가 비유한 숫자면 DB 쓰기 전에 거부한다.
- 실패 시 기존 Atomic Import 경계를 유지해 부분 Row를 남기지 않는다.

## 5. 회귀 테스트

- [Builder Test](../../../../backend/tests/unit/evidence/test_ai_canonical_embedding_fixture_builder.py)
- [Importer Test](../../../../backend/tests/unit/evidence/test_ai_canonical_evidence_import.py)
- [G1-B Readiness Test](../../../../backend/tests/unit/database/test_backend_ai_g1b_readiness.py)
- [Crosswalk Test](../../../../backend/tests/unit/evidence/test_ai_chunk_crosswalk.py)
- [Role Provision Test](../../../../backend/tests/unit/database/test_team_integration_provision.py)
- [T-028B Test](../../../../backend/tests/unit/evidence/test_t028b_evidence_card_preparation.py)

추가·보강된 핵심 Case:

- dtype 정상·누락·`FLOAT64` 오류
- 7×1024, `chunk_id ASC`, 중복 ID 차단
- Bool·문자열·`NaN`·`Infinity` 차단
- 비NFC 입력 차단 및 자동 변환 없음
- 추가/누락 Root·Row 필드 차단
- 비정규 JSON Byte와 trailing newline 차단
- 실패 시 DB Write 0 및 Replay Vector 허용오차 `1e-6`

## 6. 작성자 실행 결과

### 6.1 Fixture·Importer 단독

```text
command=pytest builder + importer
result=50 passed / 0 failed / 0 skipped
exit_code=0
```

### 6.2 G1-B 결합 표적

```text
command=pytest builder + importer + readiness + crosswalk + provision + T-028B
result=97 passed / 0 failed / 0 skipped
exit_code=0
```

### 6.3 Backend 전체 회귀

```text
candidate=d80ae060 + current Fixture contract changes
result=1183 passed / 0 failed / 23 skipped
exit_code=0
note=23 skips are PostgreSQL, live HTTP, or explicit team-role environment cases
```

### 6.4 최신 main 증분 확인

Clean `origin/main@8238696017ea051b62b74bad06c2eb7a27372ac2`에서 현재 후보 이후
추가된 T-018 Write·T-016 Live HTTP 테스트를 별도로 실행했다.

```text
result=17 passed / 0 failed / 6 skipped
exit_code=0
skip_reason=PostgreSQL row-lock only
```

### 6.5 정적 검증

```text
python_compile=PASS
django_check=PASS / 0 issues
migration_drift=NONE / No changes detected
git_diff_check=PASS
```

## 7. 영향도

| 영역 | 영향 |
| --- | --- |
| 공개 API | 변경 없음 |
| DB Model·Schema | 변경 없음 |
| Migration | 추가 없음 |
| Runtime DB Data | 작성자 테스트에서는 공식 팀 DB 미적용 |
| AI Exporter | 동일 Schema·Status·dtype·정렬·JSON 규칙으로 생성 필요 |
| QA | 동일 Commit·팀 DB에서 실제 Fixture Import와 READY Gate 재검증 필요 |

## 8. 남은 외부 Gate

1. 이동윤은 AI Exporter가 이 계약으로 Fixture를 생성하도록 구현·검증한다.
2. 김은진 Host 환경에서 공식 PDF 실파일 Hash와 Object Key 매핑을 확인한다.
3. 팀 PostgreSQL에서 Import Dry-run → Apply → Replay를 수행한다.
4. Crosswalk 7/7, View 8열·7행, AI Readonly Role Matrix를 확인한다.
5. 그 뒤 실제 pgvector·OpenAI G1-A와 Backend 저장 G1-B를 같은 Commit에서 수행한다.

작성자 PASS는 파일 계약과 회귀만 증명한다. 실제 OpenAI, 공식 PDF, 팀 pgvector,
AI Readonly DSN 및 공동 E2E를 PASS로 확대하지 않는다.

## 9. 안전선

- Fixture와 Embedding 원문은 Git에 Commit하지 않는다.
- OpenAI Key, DSN, Role Password, 실제 Host 경로를 문서·로그에 기록하지 않는다.
- 공유 DB에서 수동 SQL·임의 ORM·Disposable Vector 초기화를 사용하지 않는다.
- 다른 작업자의 Inquiry·Consultation 변경을 이 변경 묶음에 포함하지 않는다.

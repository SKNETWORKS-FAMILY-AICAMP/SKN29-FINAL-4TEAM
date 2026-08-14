# G1-B VectorDimensions CheckConstraint 독립 재검증 결과

```ini
reviewer=김은진
reviewed_at=2026-08-14 KST
reviewed_commit=11d771ab71aa8adc01a72af45dfe9eff280c219e
qa_decision=APPROVE
environment=Microsoft Windows 11 Pro 10.0.26200 / Python 3.13.13 / Django 5.2.16 / PostgreSQL 16.14 / pgvector 0.8.6
runtime_quiesced=YES
django_check=PASS
migration_drift=NONE
evidence_0011=APPLIED
constraint_sql_cast=PASS
data_counts_preserved=YES
timestamps_preserved=YES
postgresql_targeted_tests=63 passed/0 failed/0 skipped/exit 0
official_embedding_full_clean=7/0/exit 0
invalid_dimension_python=REJECTED
invalid_dimension_database=REJECTED
invalid_vector_python=REJECTED
invalid_vector_database=REJECTED
import_dry_run=created 0/updated 0/unchanged product 1,batch 1,document 1,page 3,scope 1,chunk 7,embedding 7;exit 0
import_replay_1=created 0/updated 0/unchanged product 1,batch 1,document 1,page 3,scope 1,chunk 7,embedding 7;exit 0
import_replay_2=created 0/updated 0/unchanged product 1,batch 1,document 1,page 3,scope 1,chunk 7,embedding 7;exit 0
crosswalk=7/7
readonly_view=8 columns/7 rows/0 duplicates
readiness_audit=READY;exit 0;blockers NONE
failed_test_ids=NONE
blockers=NONE
evidence_paths=docs/individual/eunjin/20260814_G1B_VectorDimensions_CheckConstraint_독립재검증결과.md;backend/.runtime/qa/backups/g1b_pre_0011_11d771ab_20260814.dump
```

## 1. 김은진 역할에서 수행한 변경

- `11d771ab71aa8adc01a72af45dfe9eff280c219e`을 detached Fresh Worktree로
  고정해 PostgreSQL Model·Importer 표적 회귀를 독립 실행했다.
- 실행 중이던 이 작업 공간의 Backend·AI Python Process를 확인하고, 열린
  TCP 연결이 없는 상태에서 해당 Process만 종료했다.
- 팀 통합 DB의 대상 이름·Schema·PostgreSQL·pgvector Version과 Migration
  Plan을 비밀값 없이 확인했다.
- Migration 전 custom-format Backup을 만들고 SHA-256과
  `pg_restore --list`를 검증한 뒤 `evidence.0011`만 적용했다.
- Migration 전후 Count·Timestamp 지문, 제약 SQL, 공식 Embedding 7건
  `full_clean()`, 공식 Fixture Dry-run·Replay, Crosswalk와 Readiness를
  재검증했다.
- Backend Runtime, Model, Migration, 계약과 AI 구현 Source는 수정하지 않았다.

## 2. 변경 파일과 관할 근거

- `docs/individual/eunjin/20260814_G1B_VectorDimensions_CheckConstraint_독립재검증결과.md`

추적 대상 변경은 공동 편집 영역인 `docs/**`의 독립 QA 증적뿐이다. 검증용
스크립트와 DB Backup은 Git에서 제외되는 `backend/.runtime/qa/**`에만 두었고,
임시 스크립트와 Fresh Worktree는 결과 확정 후 제거한다. Backup은 복구 증거로
보존한다.

## 3. 실행한 데이터·QA·CI 검증과 결과

| 검증 | 결과 | Exit |
| --- | --- | ---: |
| 시작·종료 HEAD | `11d771ab71aa8adc01a72af45dfe9eff280c219e` 동일 | 0 |
| Fresh Worktree | tracked/untracked 변경 0건, canonical LF Blob 일치 | 0 |
| Backend 환경 Gate | Python 3.13.13, dependency fingerprint 일치, `pip check` PASS | 0 |
| Django system check | 문제 0건 | 0 |
| Migration drift | `No changes detected` | 0 |
| Migration Plan | `evidence.0011` 1건만 예정 | 0 |
| Migration 전 Backup | custom format, SHA-256 일치, restore list 769행 | 0 |
| `evidence.0011` | 적용 완료, 미적용 Migration 0건 | 0 |
| 제약 SQL | `vector_dims((embedding)::vector)` 포함 | 0 |
| 공식 Embedding 직접 `full_clean()` | 7건, Database Check 경고 0건 | 0 |
| PostgreSQL 표적 회귀 | `63 passed / 0 failed / 0 skipped` | 0 |
| 잘못된 Dimension | Python·DB 모두 거부 | 0 |
| 잘못된 Vector 길이 | Python·DB 모두 거부 | 0 |
| 공식 Fixture Dry-run | created 0, updated 0, 기존 7건 계보 전부 unchanged | 0 |
| 공식 Fixture Apply Replay 1·2 | 두 회차 모두 created 0, updated 0 | 0 |
| Crosswalk Sync | mappings 7, changes 0 | 0 |
| Readonly View | 8열, 7행, 고유 Chunk 7, 중복 0 | 0 |
| Readiness Audit | `READY`, blocker 0 | 0 |
| 자동 PostgreSQL Test DB 정리 | `test_waterbridge_team_integration` 잔존 0건 | 0 |

Migration 전후 Count는 Batch 1, Document 1, Page 3, Scope 1, Chunk 7,
Embedding 7로 동일했다. 각 행의 `created_at`·`updated_at`을 PK 순으로 묶어
계산한 SHA-256도 다음과 같이 전후 및 두 Replay 후까지 동일했다.

| Model | Timestamp SHA-256 |
| --- | --- |
| IngestionBatch | `b2521dd3be58f9627d196a0a532a6ec305ea853a55fb98c8251b3f5e8c07dc07` |
| SourceDocument | `3ee9d4f44d7b24b72544e16eda6c758445ad6d181cbf03fd69efd0efad3aa822` |
| DocumentPage | `f2ae3575865207be82da8bfc48708c30f7f3413fcebbfe4060df4dcabe1e0b8c` |
| DocumentModelScope | `15c8311d69db91543d732562605a5d4dbddb6ae82ef72a4f8aa51be9ce28defa` |
| DocumentChunk | `aa64448e70eac0ab3b019ef9afbaf35eb3e3deceebd77d8b513a08234ddf2185` |
| ChunkEmbedding | `3c0c9dacc2d5ba237511f404edb159f677d67e86e247a65fc2866ed331c95fa1` |

Backup은
`backend/.runtime/qa/backups/g1b_pre_0011_11d771ab_20260814.dump`에
보존했다. SHA-256은
`5b74bf23b4e767f19180fb27182b356a68dfa66328f2e39400d3e6928d6a5626`이다.
Secret, DSN, Password, 공식 원본 Host 경로와 Vector 본문은 기록하지 않았다.

현재 작업 트리에서 첫 표적 테스트는 `44 passed / 19 failed`였다. 19건의 첫
Root Exception은 canonical Identity JSON에서 CRLF가 검출되고 Manifest SHA가
달라진 것이며, 이후 실패는 같은 선행 검증 실패의 연쇄였다. Index 파일은
정상이었고 Identity 파일의 작업 트리 Byte Hash만 Git Blob과 달랐다. Source를
수정하지 않고 detached Fresh Worktree로 Harness를 교정해 같은 63개를
재실행했으며 전부 통과했다. 따라서 이 19건은 제품 FAIL에 포함하지 않는다.

초기 DB 연결 진단 중 루트 Compose의 `watercare-local-postgres-1`을 한 번
기동했으나, 공식 팀 통합 Container와 다른 빈 로컬 DB임을 확인했다. 해당 DB에는
Migration·Import를 적용하지 않았고 제가 시작한 Service만 중지했으며 Volume은
보존했다. 공식 검증은 별도
`waterbridge-team-integration-postgres-1`과 역할별 보호 자격으로 다시 수행했다.

## 4. 실행하지 못한 검증과 이유

- 팀 DB Migration 역적용은 요청서 안전선에 따라 실행하지 않았다. 역적용은
  작성자의 폐기형 DB 증적 범위이며, 이번 독립 QA는 Forward 적용과 실제
  PostgreSQL 표적 회귀를 검증했다.
- 외부 LLM 호출과 G1-A 전체 업무 시나리오는 이번 CheckConstraint G1-B 범위가
  아니므로 실행하지 않았다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

- 현재 주 작업 트리의
  `ai/configs/canonical_evidence_identity.json` 작업 파일 Byte EOL은 CRLF여서
  Git Blob·Manifest SHA와 다르다. Git index 관점에서는 변경으로 표시되지
  않지만 Importer Test Harness를 실패시킨다. AI·Backend 관할 Source는 수정하지
  않았고 Fresh Worktree로 격리했다.

## 6. 필요한 담당자 인계

- 최지용: `evidence.0011` 팀 DB 적용과 독립 QA `APPROVE` 확인
- 윤승혁·이동윤: 현재 Checkout 재사용 시 canonical Identity 작업 파일의
  EOL/Byte Hash Gate를 먼저 확인하고, 제품 실패와 Checkout Harness 실패를
  분리
- Backend·AI 실행 담당자: Migration 전 종료한 두 Process의 재기동 필요 여부를
  후속 운영 순서에 맞춰 결정

## 7. 남은 위험과 확인 필요 항목

- 이번 `APPROVE`는 고정 Commit과 현재 팀 통합 DB의 G1-B 제약·Importer Gate에
  한정된다. HEAD, Fixture, 공식 Source Hash 또는 DB Schema가 바뀌면 재검증해야
  한다.
- Migration 전 Backup은 성공 검증 후에도 명시적 보존 정책이 정해질 때까지
  삭제하지 않는다.
- Backend·AI Process는 요청서 안전선에 따라 종료 상태로 남겼다. 재기동과
  Health 확인은 별도 요청 또는 실행 담당자 조율이 필요하다.

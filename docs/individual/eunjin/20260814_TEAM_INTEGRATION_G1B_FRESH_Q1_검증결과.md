# TEAM_INTEGRATION G1-B Fresh Worktree Q1 검증 결과

```ini
reviewer=김은진
reviewed_at=2026-08-14 KST
initial_import_commit=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
revalidated_commit=a29ec0f966bdefb309ee925503b0302f9e0402e8
fresh_worktree_head_unchanged=PASS
fresh_worktree_clean=PASS
canonical_lf_hash_gate=PASS
fixture_received=YES
fixture_generated_commit=626a7a4584d381085615d80b2269b8155322176d
fixture_generated_commit_ancestor=PASS
fixture_inputs_unchanged=PASS
fixture_sha_match=PASS
importer_regression=44 passed,0 failed
import_replay=PASS
crosswalk_replay=PASS
readiness_audit=READY
role_test=1 passed,0 failed,0 skipped
ai_process_env=OPENAI_KEY_YES,AI_READONLY_DSN_YES
backend_process_env=RUNTIME_DSN_YES,AI_SERVICE_URL_YES
ai_health=PASS
backend_health=PASS
running=YES
environment_ready=YES
g1a_joint_execution_ready=YES
source_policy_review=PENDING
qa_decision=APPROVE_WITH_POLICY_HOLD
```

## 1. 김은진 역할에서 수행한 변경

- 최신 `origin/main` 40SHA를 고정한 detached Fresh Worktree에서 모든 Q1
  검증과 서비스 기동을 수행했다.
- 보호된 Host Runtime의 공식 PDF, 수신 Fixture와 Role별 자격증명을 각
  Process에만 주입했다. Fixture를 복사·재생성·재포맷하지 않았다.
- Import Dry-run, 최초 Apply, 동일 Fixture Replay와 Crosswalk
  Dry-run·Apply·Replay를 순서대로 실행했다.
- 기존 네 Role의 권한을 현재 Schema 기준으로 재조정한 뒤 Readonly Audit과
  Matrix Role 테스트를 실행했다.
- AI와 Backend를 Fresh Worktree 코드로 기동하고 두 Health를 확인했다.
- 기존 PostgreSQL Container·Volume, Secret, Fixture와 Fresh Worktree는 후속
  공동 검증을 위해 보존했다.

## 2. 변경 파일과 관할 근거

- `docs/individual/eunjin/20260814_TEAM_INTEGRATION_G1B_FRESH_Q1_검증결과.md`

이번 단계의 신규 추적 대상 변경은 김은진 공동 편집 영역인 `docs/**`의 검증
증적뿐이다. 기존 Q0의 `infra/**`, `scripts/deployment/**`, `docs/**` 변경은
보존했다. Backend Runtime, AI 구현, 계약, Migration과 공개 API는 수정하지
않았다. Fresh Worktree는 종료 시 clean 상태다.

## 3. 실행한 데이터·QA·CI 검증과 결과

| 검증 | 결과 | Exit |
| --- | --- | ---: |
| Fresh Worktree 시작·종료 HEAD | `a29ec0f966bdefb309ee925503b0302f9e0402e8` 동일 | 0 |
| Fresh Worktree 상태 | clean | 0 |
| Canonical Identity·Index EOL | `i/lf w/lf`, `text eol=lf` | 0 |
| Canonical Identity·Index SHA-256 | Backend Import Manifest 기대값과 일치 | 0 |
| Fixture 생성 Commit 조상 관계 | PASS | 0 |
| 생성 Commit 이후 보호 입력 4종 | 변경 없음 | 0 |
| Fixture SHA-256 | 전달 SHA와 일치 | 0 |
| 공식 PDF | 기대 크기·SHA-256 일치 파일 1개 | 0 |
| Django system check | 문제 0건 | 0 |
| Migration 적용·drift | 미적용 없음·변경 없음 | 0 |
| 합성 검증 Operator | 활성 OPERATOR 1건 | 0 |
| Backend Importer 회귀 | 최초 적재·최신 main 재검증 모두 `44 passed / 0 failed` | 0 |
| Import 전 관련 Count | Product 1, 나머지 Import 대상 0 | 0 |
| Import Dry-run | Product 1, Batch 1, Document 1, Page 3, Scope 1, Chunk 7, Embedding 7 생성 예정 | 0 |
| 최초 Import Apply | `ccf30f2d...`에서 위 예상치와 동일하게 생성 | 0 |
| Import 후 총계 | Product 2, Batch 1, Document 1, Page 3, Scope 1, Chunk 7, Embedding 7 | 0 |
| 동일 Fixture Replay | `ccf30f2d...`에서 timestamp 지문 불변, `a29ec0f...`에서 created 0·updated 0 | 0 |
| Crosswalk Dry-run | mappings 7 | 0 |
| Crosswalk 최초 Apply | created 7, updated 0 | 0 |
| Crosswalk Replay | 최초 검증·최신 main 재검증 모두 created 0, updated 0, unchanged 7 | 0 |
| Crosswalk·Page Link | active verified 7/7, Page Link 8 | 0 |
| Role 권한 재조정 | 기존 Migrator·Runtime·Readonly·AI Readonly 유지 및 적용 | 0 |
| Readiness Audit | `READY`, blocker 0 | 0 |
| Readonly View | 8열, 7행, 고유 Chunk 7 | 0 |
| AI Role 정책 | View SELECT 허용, Base Table SELECT·View DML·Schema CREATE 거부 | 0 |
| PostgreSQL Role Matrix | `1 passed / 0 skipped` | 0 |
| AI Process 주입 | OpenAI Key YES, AI Readonly DSN YES | 0 |
| Backend Process 주입 | Runtime DSN YES, AI Service URL YES | 0 |
| AI·Backend Health | 양쪽 PASS, 포트 Listen | 0 |
| 비밀·실제 Host 경로·Vector 본문 기록 | 0건 | 0 |

대상 DB는 `waterbridge_team_integration`, PostgreSQL은 `16.14`, pgvector는
`0.8.6`으로 확인했다.

최신 main `a29ec0f...`은 최초 검증 Commit 이후 상담 상세 조회 관련 Backend
파일 4개만 변경했다. Canonical Identity, Index Manifest, AI Exporter와 승인
JSONL은 변경되지 않았다. 별도 Fresh Worktree에서 LF·Hash·Fixture provenance,
Importer 44개 회귀, Import·Crosswalk Replay, Readiness Audit, Role Matrix와
최신 Backend Health를 다시 확인했다.

Import Dry-run과 최초 Apply 중 Django의 pgvector CheckConstraint 사전 검증이
`vector_dims(unknown)` 오버로드를 결정하지 못했다는 stderr 경고가 각 Embedding
검증에서 발생했다. 명령은 exit 0이었고 PostgreSQL 저장, Replay, Audit와 Role
Gate는 모두 통과했다. 이번 READY 판정의 차단 조건은 아니지만 Backend 쪽
사전 검증 품질 위험으로 별도 인계한다.

Crosswalk Replay 후 집계 Harness가 존재하지 않는 필드명을 사용해 1회
실패했다. Replay 명령 자체는 그 전에 `created=0, updated=0, unchanged=7`로
완료됐다. 실제 모델 필드로 읽기 전용 집계를 교정해 `7/7`, Page Link 8을
재확인했으며 제품 실패로 집계하지 않았다.

## 4. 실행하지 못한 검증과 이유

- G1-A 업무 시나리오 전체와 실제 Backend→AI 분석 요청은 이번 G1-B 환경 구축
  범위가 아니어서 실행하지 않았다.
- 공식 PDF의 공개·재배포 이용허락 검토는 별도 정책 근거가 없어 실행 완료로
  판정하지 않았다.
- 실제 OpenAI 생성 호출은 Key 주입과 AI Process Health 범위를 넘어가므로
  이번 Gate에서 실행하지 않았다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

- Backend Embedding 모델의 pgvector CheckConstraint 사전 검증에서
  `vector_dims(unknown)` 함수 선택 경고가 발생한다. Import된 값과 DB 결과는
  정상이지만 애플리케이션 단계의 제약식 검증 신뢰도를 별도로 확인해야 한다.
- 현재 Checkout의 Canonical 작업파일 CRLF 문제는 Fresh Worktree로 격리했으며
  저장소의 Backend·AI·계약 파일을 수정하지 않았다.

## 6. 필요한 담당자 인계

- 최지용: pgvector CheckConstraint의 Django 사전 검증 경고 재현과 Backend
  관할에서 명시적 형 변환 또는 검증 방식 확인
- 이동윤: 현재 실행 중인 AI Process와 7행 Readonly View를 사용한 G1-A 공동
  시나리오 진행
- 최지용·이동윤: 동일한 Secret 제거본으로 `environment_ready=YES`와 고정
  Commit을 동시에 확인
- 정책 담당자: 공식 PDF의 이용허락·공개·재배포 근거 확정

## 7. 남은 위험과 확인 필요 항목

- `environment_ready=YES`는 로컬 기술 통합환경 판정이다. 공개·재배포 승인이
  아니며 정책 검토가 끝날 때까지 `APPROVE_WITH_POLICY_HOLD`다.
- AI와 Backend Health는 Liveness 증거다. 실제 OpenAI 응답 품질, Backend 저장,
  Replay·오류 보존을 포함한 G1-A 시나리오 PASS를 대신하지 않는다.
- 검증 결과는 고정 Commit에만 유효하다. HEAD 또는 네 보호 입력이 바뀌면
  이번 결과와 합치지 않고 Gate를 다시 실행해야 한다.
- PostgreSQL Container·Volume, Fixture, Secret, Fresh Worktree와 두 서비스는
  G1-A/G1-B 공동 검증 종료 전까지 보존한다.

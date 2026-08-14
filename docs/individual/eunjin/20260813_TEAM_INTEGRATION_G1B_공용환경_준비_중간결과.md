# TEAM_INTEGRATION G1-B 공용환경 준비 중간 결과

> reviewer: 김은진
> reviewed_at: 2026-08-13 KST
> reviewed_commit: `111da4bcd6fd8cb7e019e545254d55b3ad7406ca`
> environment: `QA_ISOLATED / Windows / Python 3.13.13 / PostgreSQL 16.14 / pgvector 0.8.6`
> qa_decision: `BLOCKED`

## 1. 김은진 역할에서 수행한 변경

- 기존 개발용 PostgreSQL과 분리된 TEAM_INTEGRATION 전용 Compose 위치를
  `infra/docker/compose/team-integration/`에 추가했다.
- Git에 포함되지 않는 `.runtime/team-integration/`에 Admin 및 네 Role의
  Runtime Secret을 생성하고 현재 Windows 사용자만 접근하도록 ACL을 제한했다.
- `waterbridge_team_integration` DB와 Migrator, Runtime, Readonly,
  AI Readonly Role을 생성했다.
- Django Migration 전체를 적용하고 권한을 재조정했다.
- 합성 Demo Seed를 두 번 실행해 두 번째 실행의 신규 생성이 0건임을 확인했다.
- 공식 Evidence·Embedding 7건은 임의 INSERT하지 않았다.

## 2. 변경 파일과 관할 근거

- `infra/docker/compose/team-integration/compose.yaml`
- `infra/docker/compose/team-integration/README.md`
- `infra/docker/env/team-integration.env.example`
- `scripts/deployment/initialize_team_integration_runtime.ps1`
- `scripts/deployment/import_team_integration_env.ps1`
- `docs/individual/eunjin/20260813_TEAM_INTEGRATION_G1B_공용환경_준비_중간결과.md`

`infra/**`, `scripts/deployment/**`, `docs/**`는 김은진 직접 편집 범위다.
Backend Runtime, Migration, DB 검증기와 AI 구현 코드는 수정하지 않았다.

## 3. 실행한 데이터·QA·CI 검증과 결과

| 검증 | 결과 | Exit |
| --- | --- | ---: |
| Compose config | 유효 | 0 |
| PostgreSQL Container Health | `healthy` | 0 |
| PostgreSQL / pgvector | `16.14 / 0.8.6` | 0 |
| Provision Plan·Apply·권한 재조정 | `APPLIED` | 0 |
| Django Migration 전체 적용 | 전체 적용 | 0 |
| `migrate --check` | 미적용 Migration 없음 | 0 |
| `makemigrations --check --dry-run` | `No changes detected` | 0 |
| Django system check | 문제 0건 | 0 |
| 합성 Demo Seed 2회 | 2회차 신규 생성 0건 | 0 |
| G1-B·Provision Unit | `25 passed / 0 failed / 0 skipped` | 0 |
| PostgreSQL Role 통합 | `1 passed / 0 failed / 0 skipped` | 0 |
| Crosswalk dry-run | 공식 Document 또는 Product Model 없음 | 1 |
| G1-B 강제 Audit | `BLOCKED` | 1 |
| AI 실제 pgvector Gate | 데이터 수치 `0/7`로 `1 failed` | 1 |

G1-B 강제 Audit 실측:

- Migration `0009`, `0010`: 적용됨
- Crosswalk 활성·검증: `0/7`
- 승인 Embedding Identity: `0/7`
- View: 존재, 열 순서 `8/8`, 행 `0/7`, 고유 `chunk_id` `0/7`
- AI Role: 기본 Transaction read-only
- AI Role: View SELECT 허용
- AI Role: Base Table SELECT, View DML, Schema CREATE 거부

Audit Blocker:

```text
ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_7
BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_7
BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_7
```

첫 Migration 실행 뒤 후속 Exit 확인 구문에서 PowerShell 인용 Harness 오류가
1회 발생했다. Migration은 전부 적용됐고, 인용을 교정한 후 Migration Check,
Drift Check와 Django Check를 각각 Exit 0으로 재검증했다. 제품 실패 집계에는
포함하지 않았다.

## 4. 실행하지 못한 검증과 이유

- Crosswalk Apply·Replay: 공식 Evidence, Page, Chunk, Embedding 7건을 만드는
  확인된 Backend 적재 명령 또는 Fixture가 저장소에 없다.
- AI Local Runtime Gate: View 7행과 승인 Embedding이 없으므로 시작 조건 미충족이다.
- 실제 Backend→AI HTTP, AIRun·Guidance·EvidenceLink 저장, Replay·409,
  AI 503·Timeout 보존 검증: 공식 Evidence 적재 및 AI Process 기동 전 단계다.
- `TEAM_SHARED` 원격 검증: 현재 환경은 로컬 `QA_ISOLATED`이며 전용 비운영
  Host, 제한 Network와 TLS `verify-full`은 아직 구성하지 않았다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

`sync_ai_canonical_crosswalk`는 기존 공식 Evidence 객체를 Crosswalk로
동기화하는 명령이다. 빈 DB에 공식 Evidence 7건을 생성하는 진입점은 아니다.
임의 SQL이나 비공식 Fixture로 채우면 G1-B 계보와 승인 상태를 위조하게 되므로
Backend 관할 코드를 수정하거나 우회하지 않았다.

## 6. 필요한 담당자 인계

최지용에게 다음 중 하나를 요청한다.

1. 승인 JSONL 7건을 현재 Backend Model에 멱등 적재하는 공식 명령과 정확한
   실행 순서
2. 같은 역할을 하는 검증된 Fixture 및 Fixture Commit
3. 이미 7건이 적재된 팀 비운영 DB를 사용할 경우 대상 환경 식별자와 승인된
   Secret 주입 절차

응답에는 SourceDocument, Page, Chunk, Embedding 생성과 승인 상태 설정의
주체가 포함돼야 한다. Secret·DSN·Password는 문서나 채팅으로 받지 않는다.

## 7. 남은 위험과 확인 필요 항목

- 현재 판정은 `ENVIRONMENT_BLOCKED` 성격의 `BLOCKED`이며 제품 결함 판정이 아니다.
- 로컬 격리 Container와 전용 Volume은 후속 검증을 위해 보존 중이다.
- 최지용 답변 이후에도 Crosswalk dry-run → Apply → Replay → Provision 권한
  재조정 → 강제 Audit 순서를 지켜야 한다.
- `READY`, Crosswalk `7/7`, View `7행`, AI pgvector Gate PASS 전에는 실제
  OpenAI·Backend 수직 E2E 결과를 PASS로 판정하지 않는다.
- 시작·종료 SHA가 달라지면 현재 결과와 후속 결과를 합치지 않는다.

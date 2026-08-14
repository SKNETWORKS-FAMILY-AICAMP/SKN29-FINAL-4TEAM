# TEAM_INTEGRATION G1-B Phase Q0 환경 준비 결과

```ini
reviewer=김은진
reviewed_at=2026-08-14 KST
reviewed_commit=dc8bd191a8fd7623ad1e70b2b9980d9952775062
qa_decision=BLOCKED
q0_environment_prepared=YES
fixture_received=NO
openai_key_storage_path=READY
actual_openai_key_injected=NO
official_source_size_hash=PASS
source_policy_review=PENDING
current_data_gate=BLOCKED_EXPECTED_0_OF_7
readiness_audit=BLOCKED;exit0;crosswalk0,page_links0,view_rows0
role_test=1 passed,0 failed,0 skipped,exit0
ai_process_env=OPENAI_KEY_NO,AI_READONLY_DSN_YES
environment_ready=NO
g1a_joint_execution_ready=NO
```

## 1. 김은진 역할에서 수행한 변경

- 기존 TEAM_INTEGRATION DB, Docker Volume과 네 Role을 재생성하지 않고
  보존했다.
- AI Readonly DSN과 ACL 보호 OpenAI Key를 AI Process에만 주입하는 Loader를
  보완했다. AI Role 선택 시 다른 Role Secret은 Process에서 제거한다.
- OpenAI Key를 대화형으로 등록하는 ACL Runtime 저장 도구를 추가했다. 기본
  실행은 기존 Key를 덮어쓰지 않고 명시적인 `-Rotate`만 회전을 허용한다.
- 공식 PDF를 복사하거나 경로를 기록하지 않고 크기와 SHA-256으로 유일하게
  찾아 Backend Runtime Process에만 주입하도록 했다.
- AI Fixture 수신함을 현재 사용자 전용 ACL로 제한하고 Git ignore를 확인했다.
- 의미 없는 Mobile 줄바꿈 변경은 HEAD 상태로 복구했다.

## 2. 변경 파일과 관할 근거

- `scripts/deployment/import_team_integration_env.ps1`
- `scripts/deployment/set_team_integration_openai_key.ps1`
- `infra/docker/compose/team-integration/README.md`
- `docs/individual/eunjin/20260814_TEAM_INTEGRATION_G1B_Q0_환경준비결과.md`

`scripts/deployment/**`, `infra/**`, `docs/**`는 김은진 직접 편집 범위다.
Backend Runtime, AI 구현, 계약과 Migration은 수정하지 않았다.

## 3. 실행한 데이터·QA·CI 검증과 결과

| 검증 | 결과 | Exit |
| --- | --- | ---: |
| 검증 시작·종료 HEAD | `dc8bd191a8fd7623ad1e70b2b9980d9952775062` 동일 | 0 |
| AI Exporter 표적 회귀 | `10 passed` | 0 |
| PowerShell Parser | 3개 스크립트 오류 0건 | 0 |
| 합성 OpenAI Key ACL 저장 | 생성·기본 덮어쓰기 차단·명시적 회전 PASS | 0 |
| 합성 AI Process 주입 | Key YES, AI Readonly DSN YES, 다른 Role Secret 0개 | 0 |
| AI→Runtime Process 전환 | AI Key·DSN 제거 PASS | 0 |
| 공식 PDF 실제 파일 | 기대 크기·SHA-256 일치 파일 1개 | 0 |
| 기존 Docker Volume | 존재·보존 | 0 |
| PostgreSQL Container | 기존 Container `healthy` | 0 |
| 대상 DB·4개 Role | DB 1개·Role 4개 존재 | 0 |
| PostgreSQL·pgvector | `16.14`·`0.8.6` | 0 |
| Role Matrix | `1 passed / 0 skipped` | 0 |
| G1-B Readiness Audit | `BLOCKED`, View 8열·0행, Crosswalk 0/7 | 0 |

Audit의 기술적 blocker는 다음 네 건이다.

```text
ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_7
BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_7
ACTIVE_VERIFIED_CROSSWALK_PAGE_LINK_COUNT_NOT_8
BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_7
```

Backend Importer 표적 회귀는 현재 Commit에서 `25 passed / 19 failed`다. 모든
실패는 Fixture 계약 평가 전에 Canonical Identity 파일의 실제 SHA-256과 Backend
Import Manifest 기대 SHA-256이 다른 지점에서 시작한다. Index Manifest Hash는
현재 일치한다.

검증 도중 로컬 `origin/main` 참조가 Mobile 변경 Commit으로 전진했다. 현재
워크트리 HEAD는 시작부터 종료까지 바뀌지 않았으며, 새 main 결과를 이번 Q0
집계와 합치지 않았다. 전진한 변경에는 Backend Import Manifest 정합화가 포함되지
않았다.

DB 메타데이터 검증의 첫 두 시도는 PowerShell Native Argument 인용과 임시 QA
모듈의 Python 경로가 잘못되어 DB 접근 전에 실패했다. Git 비추적 임시 모듈을
교정해 재실행했고 성공 후 제거했다. 제품 실패로 집계하지 않았다.

## 4. 실행하지 못한 검증과 이유

- 실제 OpenAI Key 주입: Key를 전달받거나 출력하지 않고 저장·주입 경로만
  합성값으로 검증했다.
- AI Fixture Hash·계약 검증과 Backend Import: 이동윤 실제 Artifact가 없다.
- Import Dry-run·Apply·Replay, Crosswalk Apply·Replay: Q1 진입 조건과 Backend
  Importer 회귀가 충족되지 않았다.
- AI·Backend Health와 실제 G1-A: Data Gate가 `0/7`이다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

Backend Import Manifest가 현재 `ai/configs/canonical_evidence_identity.json`의
Byte SHA-256과 일치하지 않아 Importer 회귀 19건이 실패한다. Backend 관할
파일이므로 수정하지 않았다.

또한 현재 AI Exporter Artifact에는 `fixture_generated_commit` 필드가 없다.
생성 Commit은 Artifact 내부 값으로 추측하지 않고 이동윤 전달 증적으로 받아야
한다.

## 6. 필요한 담당자 인계

- 최지용: Canonical Identity Hash 정합화와 Backend Importer 회귀 통과가 포함된
  최종 main 40SHA 전달
- 이동윤: 해당 최종 main의 AI Exporter로 만든 실제 Fixture, Fixture SHA-256,
  생성 Commit 증적 전달
- OpenAI Key 관리자: 채팅이나 문서가 아닌 Host 대화형 입력으로 ACL Runtime
  Key 등록

## 7. 남은 위험과 확인 필요 항목

- Q0 인프라 준비는 완료됐지만 Data Gate와 전체 환경은 READY가 아니다.
- 공식 PDF 이용약관만으로 RAG 이용허락이 입증되지 않아 정책 검토는
  `PENDING`이다. 로컬 기술 검증 외 공개·재배포는 HOLD다.
- PostgreSQL Service와 Volume은 Q1 후속 검증을 위해 실행·보존 중이다.
- Q1 시작 전 명시적으로 전달된 최종 main SHA에서 전체 Gate를 새로 실행해야
  하며 이번 `dc8bd...` 결과와 다른 Commit의 결과를 합치지 않는다.
- Reference Builder, AI Exporter, Import, Crosswalk Apply와 Secret 회전은 이번
  단계에서 실행하지 않았다.

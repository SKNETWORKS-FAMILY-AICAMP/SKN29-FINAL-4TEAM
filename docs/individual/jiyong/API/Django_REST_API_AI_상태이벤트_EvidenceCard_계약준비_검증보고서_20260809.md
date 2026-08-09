# Django REST API AI 상태 이벤트·EvidenceCard 계약 준비 검증 보고서

> 검증일: 2026-08-09 KST
> 기준선: 2026-08-08 22:00 KST 기준 `origin/main`(data-ci.yml 충돌 처리 반영) 기반 별도 안전 Worktree
> 판정: `LOCAL_AUTHOR_VERIFIED / BACKEND_MAPPING_EVIDENCE_READY`
> T-028B 판정: `PREPARATION_ONLY`
> 게시 범위: `origin/jiyong` 검토 후보

## 1. 결론

외부 회신 없이 확정할 수 있는 두 범위만 반영했다.

1. 기존 AI 응답 Mapper가 생성하는 세 이벤트를 팀 승인 State Machine과
   동적으로 대조했다.
2. T-028B는 실제 Runtime을 만들지 않고 역할별 EvidenceCard 계약 예시,
   비노출 Test와 선행조건 차단 Readiness만 준비했다.

공개 Backend–AI Dispatch, Evidence Endpoint·Service·Serializer·URL, Model과
Migration은 변경하지 않았다. 따라서 이 결과는 W5-G05·T-028B 완료나 공동
E2E PASS가 아니다.

## 2. AI 결과와 State Event 정합

| AI Mapper 후보 | 승인 전이 | 필수 안전 Guard |
| --- | --- | --- |
| `SAFE_GUIDANCE_READY` | `QUESTIONNAIRE_IN_PROGRESS` → `AI_GUIDANCE` | 안전 안내, 공식 근거, 위험 충돌 없음 |
| `DANGER_DETECTED` | `QUESTIONNAIRE_IN_PROGRESS` → `CONSULTATION_REQUIRED` | 명시적 위험 판정 |
| `NO_EVIDENCE` | `QUESTIONNAIRE_IN_PROGRESS` → `CONSULTATION_REQUIRED` | 사용 가능한 공식 근거 없음 |

각 후보가 다음 조건을 모두 만족하는지 실행 Test로 확인했다.

- `SYSTEM_EVENT`·`AI_RESULT`·`SYSTEM` 수행자
- `state_version` 필수
- 외부 Action 비노출
- `TEAM_APPROVED` Event·Transition·Guard만 참조
- 승인된 From/To State, Guard와 Effect가 정확히 일치

판정은 `BACKEND_MAPPING_EVIDENCE_READY`다. 이동윤 공동 확인과 공개 HTTP
Dispatch가 없으므로 W5-G05 또는 W5-G07을 `PASS`로 바꾸지 않는다.

## 3. EvidenceCard 계약 준비

역할별 계약 예시는 Runtime Example과 분리한
`contracts/api/preparation/evidence/`에 저장했다. 전역 OpenAPI Runtime
Example 허용 목록에 포함하지 않는다.

| 역할 | 공개 필드 | 추가 비노출 |
| --- | --- | --- |
| CUSTOMER | 확정 화면 계약 23개 | `chunk_id` 숨김 |
| CONSULTANT | 확정 화면 계약 24개 | 내부 경로·원문·검색정보 숨김 |
| TECHNICIAN | 확정 화면 계약 24개 | 내부 경로·원문·검색정보 숨김 |

모든 역할에서 `source_path`, `ManualPage.text`, `retrieval_text`, 검색 점수,
Prompt, 고객 원문과 내부 저장 경로를 금지한다. 예시는
`NON_RUNTIME_CONTRACT_PREPARATION`과 `PREPARATION_ONLY`를 명시한다.

## 4. Runtime 차단 결과

```text
status=PREPARATION_ONLY
runtime_ready=false
blockers=W5_G04_NOT_PASS,T028A_NOT_COMPLETE,
         EVIDENCE_API_CONTRACT_EMPTY,EVIDENCE_RUNTIME_STUBS_ONLY
```

`--require-runtime-ready` 실행은 Exit 2로 실패한다. 선행조건이 실제로 열리고
API 계약과 Runtime이 존재하기 전에는 계약 Fixture만으로 T-028B를 완료 처리할
수 없다.

## 5. 검증 결과

| 검증 | 결과 |
| --- | --- |
| 신규 AI Mapping·Evidence 준비 Test | `6 passed` |
| AI·State Machine·Evidence 관련 회귀 | `240 passed, 8 skipped` |
| Runtime Example 경계 보정 후 표적 회귀 | `16 passed` |
| Django Check | 문제 0 |
| Migration Drift | `No changes detected` |
| Backend 전체 회귀 | `850 passed, 13 skipped` |
| 후보 파일 Git 공백 검사 | PASS |

첫 전체 회귀에서는 계약 준비 JSON을 Runtime Example 폴더에 둔 문제가 전역
허용 목록 Test에서 1건 검출됐다. 파일을 `contracts/api/preparation/`으로
분리하고 경계 Test를 다시 통과시킨 뒤 전체 회귀를 재실행했다.

오늘 PostgreSQL 재검증은 Docker daemon과 PostgreSQL 프로세스가 꺼져 있어
실행하지 못했다. 이번 변경은 DB Runtime·Model·Migration을 수정하지 않으며,
과거 PostgreSQL PASS를 오늘의 신규 PASS로 기록하지 않는다.

## 6. 작업 파일

| 파일 | 목적 |
| --- | --- |
| `backend/tests/unit/ai_integration/test_ai_state_event_contract_conformance.py` | AI Mapper와 승인 State Event 동적 정합 |
| `contracts/api/preparation/evidence/evidence-card.contract-preparation.json` | 역할별 EvidenceCard 비Runtime 계약 예시 |
| `contracts/api/preparation/evidence/README.md` | 준비 Artifact와 Runtime Example 경계 |
| `backend/apps/evidence/readiness.py` | T-028B 선행조건 Fail-closed 감사 |
| `backend/tests/unit/evidence/test_t028b_evidence_card_preparation.py` | 필드·비노출·차단 Exit 회귀 |

## 7. 재현 명령

후보 파일을 포함한 동일 checkout의 저장소 루트에서 실행한다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python -m pytest -q -p no:cacheprovider `
  backend/tests/unit/ai_integration/test_ai_state_event_contract_conformance.py `
  backend/tests/unit/evidence/test_t028b_evidence_card_preparation.py

& $python backend/apps/evidence/readiness.py
& $python backend/apps/evidence/readiness.py --require-runtime-ready
```

두 번째 Readiness 명령은 현재 선행조건에서 의도적으로 Exit 2를 반환한다.

## 8. 다음 착수 조건

1. W5-G05 공동 확인 전 공개 Backend–AI Dispatch를 추가하지 않는다.
2. W5-G04 PASS와 T-028A 완료 전 T-028B Runtime을 시작하지 않는다.
3. Evidence API 계약 확정 후 Repository → Service → Serializer → View → URL
   순서로 구현한다.
4. Runtime 후보는 격리 PostgreSQL·역할별 비노출·전체 회귀 후 독립 QA를
   요청한다.

## 9. 관련 문서

- [Backend 작성자 회귀검증 보고서](../개발환경/Django_PostgreSQL_Backend_작성자_회귀검증_보고서_20260808.md)
- [문의 AI 결과 저장·상태 전이·후속 API 검증 보고서](Django_REST_API_문의_AI결과저장_상태전이_후속API_검증보고서_20260809.md)
- [Backend·AI API 계약·구현 미해결 사항](../연동_인계/Backend_AI_API_계약_구현_미해결_사항.md)

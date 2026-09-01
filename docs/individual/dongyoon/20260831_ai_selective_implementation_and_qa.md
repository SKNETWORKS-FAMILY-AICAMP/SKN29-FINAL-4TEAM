# 최신 main 기반 AI 선별 통합 — 구현·검증·QA 인계

**현재 적용 위치 정정:** 사용자 요청으로 수정 사항을 기존 `dongyoon` checkout에 직접 반영했다. 아래 별도 worktree/원래 dongyoon Clean 표기는 최초 선별 검증 당시의 이력이다. 최신 Git 상태와 재실행 결과는 [dongyoon 반영 기록](20260831_dongyoon_selective_transfer.md)을 따른다. 임시 브랜치와 worktree 등록은 제거했다.

상태: **LOCAL_UNCOMMITTED_CANDIDATE / MERGE_HOLD**. 원인 ledger 구현과 최종 45·50 Case, 독립 QA는 완료하지 않았다. RDS 쓰기와 Public Runtime 활성화는 수행하지 않았다.

2026-08-31 정정: **CAUTION HumanReview 정책, Backend HumanReview 원장, 상담 잠금 분류와 해소 조건은 이미 확정·구현되어 있으며 재승인 대상이 아니다.** 아래 ledger 승인 대기는 AI/Harness가 생성한 구조화 원인의 증빙·검증·전달/저장을 연결하는 추가 명세에만 해당한다. 기존 HumanReview를 미구현 또는 미확정으로 해석하지 않는다.

## 기준과 선별 판단

| 항목 | 확인 기준 |
| --- | --- |
| 작업 브랜치 | `codex/ai-main-selective-20260831` |
| 기반 main / 현재 HEAD | `2305189a1fd62f6fe40bd55c6d2c1fc310a6a783` |
| Backend 정책 병합 | `95ed453c0484d2fb2c2212116c67ad830e3028ee` |
| 선별한 renew 소스 | `e411be3dd39f2a6b8b7defb219cdd8aaf572d68e` |
| 마지막 확인한 renew HEAD | `f8d090ae780a1bcba5d2b2b0b547df6a31700ae5` |
| 원래 dongyoon | `40a59a539035ba91c3df0491bc021a7f20153011`, Clean 유지 |
| Python | `3.13.13` |
| 변경 상태 | 별도 worktree의 미커밋 변경. HEAD 자체는 수정 코드의 최종 SHA가 아님 |

작업 위치는 저장소의 `.codex_tmp/ai-main-selective-20260831`이다. `ai/renew` 전체를 merge/cherry-pick하지 않았다. 42개 관련 파일을 선별한 뒤 아래 검증·안전 수정을 추가했다. 파일별 원본과 후보 Hash는 [선별 목록](20260831_ai_selective_source_manifest.json), 테스트·Gate 증거는 [검증 기록](20260831_ai_selective_validation.json)에 남긴다.

| 변경 묶음 | 판단과 반영 |
| --- | --- |
| LLM Adapter·의미 출처 검증·필드별 Follow-up fallback | 방향 수용 후 보강. 실제 입력과 맞지 않는 의미·Safety 증거를 거절하고 나머지 유효 필드는 보존 |
| Guidance·Routing | 근거 문장의 조건·경고·순서를 보존하도록 제한. 기존 CAUTION 검수와 Fail-closed 경로 유지 |
| `a55d2d6b4f0e8997e9df982f4d36112650373108`, `a297be331782f179a288462e7094b5f544795602` | 이번 후보에서 제외. 필수 입력보다 검색을 앞세우는 흐름과 Timeout 확대를 도입하지 않음 |
| `f8d090ae780a1bcba5d2b2b0b547df6a31700ae5` | 제외. CAUTION을 CONFIRMED로 처리하고 PRE_SEND HumanReview 생성 경로를 제거하는 변경이 PM의 승인 전 공개 금지와 충돌 |
| Backend·Data·Infra·공개 계약·MCP/A2A 구현 | main 그대로 유지. 다른 소유자의 코드나 승인 데이터 변경 없음 |

## 구현한 동작

### P0: 실제 입력과 Safety

- 명시적인 현재 Raw Symptom이 선택 증상 힌트와 오래된 답변보다 먼저 적용된다. LLM 의미 병합 경로에서도 이 우선순위를 다시 검사한다.
- 전선 노출·전기 부품 손상·전기 주변 물·누수·연기/탄 냄새·감전/불꽃을 원문에서 독립적으로 검사한다. 부정·가정·인접 절을 구분하고, 무관한 질문에 대한 답변에 위험 신호가 있어도 버리지 않는다.
- 명확한 위험은 외부 증상 Provider보다 먼저 판정한다. Provider 실패나 LLM 필드 거절이 결정적 Safety 신호를 지우지 않는다.
- Danger는 Single/Multi 및 미승인 제품에서도 기존 Rule ID·상담 필요·추적 필드를 보존하고 Vector/Provider 호출을 하지 않는 HTTP 회귀를 추가했다.

### 문진·Guidance

- 필수 질문에 모름/확인 불가로 답한 것을 확인 완료로 보지 않는다. 같은 질문을 반복하지 않으며 검색 없이 상담 대기로 전환한다. 검색하지 않았으므로 NO_EVIDENCE로 기록하지 않는다.
- 생성 질문의 위험한 수리 지시·단정·보증을 차단한다. 잘못된 질문 필드만 고정 문구로 대체한다.
- Guidance는 검증된 근거의 완전한 문장을 선택·조합하는 범위로 제한한다. 새로운 행동·수치·안전 보증, 조건·부정·경고 누락, 문장 순서 변경을 거절한다. 따라서 임의의 자연스러운 의역까지 허용한 상태는 아니다.
- 공개 응답 계약 `4.0.0`, 기본 `single_rag`, 전체 Timeout 30초, 기존 Backend의 CAUTION/PENDING/HumanReview 및 잠금 정책을 유지한다. 새 ledger 필드나 상담 해제 API는 추가하지 않았다.

### Scenario Evidence

- 공식 53개 Child의 canonical identity를 검증한 뒤 Topic을 복원한다. 제품·문서·페이지·Source/Content Hash·Index·Chunk-set·Child 역할이 다른 행은 사용하지 않는다.
- 온수는 모듈 알림, 히터 고장, 증기, 중간 끊김, 중간 중단, 미지근함, 미출수를 구분한다. 해당 하위 조건의 안내와 경고만 선택하며, 조건 미확정이면 일반적인 온수 문단을 임의로 안내하지 않는다.
- 모듈 고장의 상담/음용 금지 문장을 단순 미지근함에 섞지 않는다. 미출수의 잠금 해제 조건과 뒤따르는 상담 경고는 보존한다.
- 물맛/냄새도 원문에 있는 조건별 조치만 선택한다. 장기 미사용에 다른 조건의 임의 출수량을 전용하지 않는다.
- Data 원문과 45개 평가 JSON은 수정하지 않았다. Scenario 선택은 매뉴얼 조건을 사용하며 45개 정답 ID/해설 lookup을 사용하지 않는다.

## Profile·Index 정체성: 코드 검증과 운영 적용의 구분

| 용도 | Profile / Manifest | Index / Chunk-set | 상태 |
| --- | --- | --- | --- |
| 기존 기본값 | `mvp` / `index_manifest.json` | `1.0.0`, 7개, `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` | 변경하지 않음 |
| main에 이미 있는 JAC104 복구 후보 | `jac104_v2_recovery` / `index_manifest_3model.json` | `2.0.0`, 전체 53개 정체성, JAC104만 허용 | 배포·활성 승인 별도 |
| 3모델 검증 | `three_model_integration` / `index_manifest_3model.json` | `2.0.0`, 53개, `5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304` | 통합검증 전용, Public HOLD |

공통 임베딩은 BGE-M3, Revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024차원이다. 승인된 Readonly View는 `backend_ai_rag_chunks_v1`이며, 같은 실행에서 53행과 모델별 15/19/19 및 각 행 정체성을 확인한 뒤 검색/Provider 검증으로 진행한다. Embedding 초기화보다 Readonly 정체성 확인을 먼저 수행하도록 평가 도구를 보강했다.

실제 환경 파일의 설정 이름·Profile/View/Revision 일치 여부만 확인했다. DSN 값은 기록하지 않았다. RDS Readonly 사전 조회는 sandbox 안과 허용된 네트워크 실행에서 모두 `ProtectedDatabaseOperationError`로 중단됐다. 따라서 **실제 RDS 53행, 운영 Process의 Profile·Manifest 정합성, 운영 배포 완료를 확인했다고 주장하지 않는다.** 기존 `runtime_identity.json`은 MVP 기준이며 v2 배포 시 관련 소유자가 실제 실행 식별자와 Backend 감사 기록도 함께 갱신·검수해야 한다.

## 검증 범위와 결과

정확한 실행 건수·종료 코드·명령·소스/결과 Hash는 [검증 JSON](20260831_ai_selective_validation.json)에 기록한다. 모든 후보 검증은 위 HEAD의 **Dirty worktree**에서 실행했으며 최종 PR SHA 검증이 아니다.

| 실행 범위 | 실제 결과 | 한계 |
| --- | --- | --- |
| AI 전체 Unit + Contract | **1,041 PASS**: Unit 985, Contract 56; subtests 41 PASS, warnings 4 | 네트워크 없는 로컬 회귀 |
| Backend 전체 Unit + HumanReview/고객 조회 API | **1,304 PASS / 18 SKIP** | SQLite 격리; PostgreSQL 전용 검증 등 미실행 |
| 실행 가능한 AI Integration | **5 PASS / 13 SKIP** | RDS 필수 파일 1개 별도 NOT_RUN; 외부 Gate 미실행 |
| 의존성 / 변경 형식 | `pip check`, `git diff --check` PASS | 실행 품질·운영 배포 증거가 아님 |
| 45개 판단 / 공식 RDS 50 Case | **HOLD / 실행 0건** | Dataset Schema 확인을 모델 평가 PASS로 계산하지 않음 |

- AI 전체 Unit·Contract 회귀와 관련 HTTP Safety/Scenario Evidence/평가 도구 회귀를 실행했다.
- Backend는 자체 Python 3.13.13 환경에서 전체 Unit 및 HumanReview·고객 조회 API를 SQLite 격리 설정으로 실행했다. PostgreSQL 전용 검증 등 Skip은 그대로 한계로 기록한다. Backend 코드·테스트는 수정하지 않았다.
- AI Integration은 로컬 실행 가능한 범위만 수행했다. RDS 필수 `test_pgvector_runtime.py`는 접속 실패로 NOT_RUN이고, 나머지 외부 환경 의존 Skip을 서비스 E2E PASS로 계산하지 않는다.
- 실제 `gpt-4o-mini-2024-07-18` 합성 증상 호출은 응답했지만 `symptom_type`, `target_water_type` 출처가 거절돼 부분 규칙 fallback이 발생했다. 원래 smoke의 PASS 라벨을 정정한 별도 증거를 남겼고 원본은 보존했다. 자연어 품질 PASS가 아니다.
- 합성 Follow-up Provider 호출은 응답했고 문구 검증 거절은 관측되지 않았다. 고객 데이터·공식 Evidence를 이 두 smoke에 보내지 않았다.
- 공식 Evidence를 사용하는 실제 Guidance 검증은 자동 안전 검토가 외부 전송 승인을 요구해 차단했다. 호출하지 않았으며 다른 경로로 우회하지 않았다.

### 45개 판단 / 50 Case

`evaluate_reference_scenarios.py`는 평가 전용이다. 고객 발화와 정확한 모델 코드만 Runtime에 전달하고 context_facts, risk/route 정답, Evidence ID, 해설을 입력·Prompt에서 제외한다. 현재 프로토콜은 첫 발화 평가이며, 추가 질문에 대한 답변을 Oracle에서 만들어 채우지 않는다. 이 프로토콜과 Oracle 기준은 PM·Data/QA 확정이 필요하다.

45개 Dataset의 Schema와 3제품 × 3위험도 × 5건 분포는 확인했다. **실제 판단 평가 실행은 0건, HOLD**다. 실제 자동 공개 여부는 AI 결과만으로 증명할 수 없어 Backend 동일 Inquiry 저장·공개 테스트가 별도로 필요하다.

50 Case 도구는 기존 43 positive / 7 negative를 유지하고 전체 View 정체성·DB 버전·근거와 결과 Hash를 추가 기록한다. 실행 전후 SHA·Dirty·Runtime/Config Hash가 바뀌면 HOLD로 내린다. `--expected-sha`가 없는 기존 CI 실행은 최종 SHA 인증으로 사용하지 않으며 `final_sha_eligible`을 별도로 기록한다. **공식 RDS 50 Case는 미실행이다.**

## 남은 Gate와 담당자

| Gate | 담당 / 필요한 입력 | 완료 조건 / 회신 |
| --- | --- | --- |
| 추가 원인 ledger 연동 명세 | PM 윤승혁 + Backend 최지용 | 기존 HumanReview·코드·잠금 분류는 고정. [제안서](20260831_consultation_cause_ledger_proposal.md)의 추가 증빙 필드·출처 검증·전달/원자 저장·검증 방법만 APPROVED 또는 CHANGES_REQUESTED로 회신. 승인 후 추가 연동 구현 |
| RDS Readonly 연결 | Data/QA·DevOps 김은진 + Backend | 승인된 VPN/터널 필요 여부 또는 새 환경 파일 위치. 값 전달 금지. 같은 SHA에서 53행·15/19/19 및 50 Case 재현 |
| 공식 Evidence Provider 전송 | 프로젝트 승인권자 | 아래 외부 전송 범위 승인. 승인 전 Guidance 및 45개 실평가 HOLD |
| v2 운영 정체성 | AI·Backend·DevOps | 배포할 Profile·View·Manifest·Index·Chunk-set과 Backend AIRun의 실제 모델/Prompt 정체성 공동 확인. 별도 활성 승인 전 HOLD |
| 공유 경로 검수 | PM/Harness 윤승혁, MCP 양정현 | Pipeline/문진/라우팅 경계와 MCP 통합 테스트 fixture 검수. MCP/Harness Production 내부는 수정하지 않음 |
| 최종 SHA | 구현자 + 리뷰어 | ledger 포함 필요한 구현과 검수 후 commit/PR 확정. Dirty가 없는 해당 40자리 SHA에서 전체 평가·회귀 실행 |
| 비운영 CI | DevOps | 기존 Readonly workflow의 고정 SHA `f595dd8777eaf3f3f7f59ff63aa8bb2a250225ab`를 승인된 최종 SHA로 연결. `.github` 파일은 이번 작업에서 수정하지 않음 |
| 독립 QA | 김은진 | 아래 체크리스트와 동일 SHA·Hash 증거의 PASS/FAIL, 한계, 검토자·시각 회신. 현재 NOT_RUN이며 요청문만 준비 |
| PM 병합 승인 | 윤승혁 | 독립 QA PASS 이후 승인. RDS 쓰기/Public 활성화와 별도 |

## 독립 QA 요청 초안 — 아직 발송하지 않음

Ledger 구현 승인과 구현, 연결 문제 해결, 최종 SHA 실행이 끝난 뒤 아래 내용으로 요청한다. 구현자의 자체 테스트는 독립 QA가 아니다.

1. main 대비 diff에 Backend CAUTION 우회, PRE_SEND 제거, 상담 잠금 해제, Public 제품 승인 변경이 없는지 확인한다.
2. Raw와 선택/과거 답변 충돌, 전선 노출/젖은 전기부/연기/감전, 부정·가정·복합 절을 확인한다. 위험 입력의 Provider·Vector 0회와 추적 필드 보존을 Single/Multi 및 미승인 제품에서 재현한다.
3. 필수 답변 확인 불가에서 질문 반복·자동 안내·검색 실행이 없는지 확인한다. Follow-up 생성 실패가 다른 유효 필드를 지우지 않는지 확인한다.
4. 온수 하위 조건 선택 및 근거 조건·경고 보존, 미확정 조건 차단, 다른 제품/Parent/미검증/변조 근거 차단을 재현한다.
5. 원인 ledger의 누락·변조·stale/replay를 확인한다. Safety·Fail-closed·Unknown 상담 잠금 해제 0, 조건 없는 NON_SAFETY_RESOLVABLE 해소 0을 확인한다.
6. 같은 최종 SHA에서 AI·Backend 회귀, 공식 50 Case, 45개 판단 및 Backend 승인 전 공개 차단을 재현한다. DANGER 누락/부적절 자동 안내/CAUTION 자동 공개 0을 확인한다. 미실행 건을 0 위반으로 보고하지 않는다.
7. 실제 Provider·Prompt·Evidence·결과 Hash와 저장/Replay의 동일 Inquiry·state_version을 대조한다. 남은 Web/Mobile·외부 Transport 검증은 범위를 따로 기재한다.

회신: `검토 SHA / PASS·FAIL·HOLD / 재현 명령 / 결과 파일과 Hash / 위반 건수 또는 NOT_RUN / 한계 / 검토자·시각`. QA PASS가 있어도 PM 병합 승인과 RDS/Public 활성 승인 전에는 배포하지 않는다.

## 외부 전송 승인 요청 범위

자동 안전 검토가 두 작업을 차단했다. 우회하지 않았으며 현재 외부 게시/해당 Provider 전송은 없다.

- **PM 전달:** public GitHub 저장소 `SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM`의 Issue에 이 작업의 [ledger 제안서](20260831_consultation_cause_ledger_proposal.md) 내용을 게시하고 PM에게 검토를 요청하는 행위. 내부 설계와 합격 기준이 공개된다는 점에 대한 명시적 승인이 필요하다. 승인하지 않으면 제안서를 기존 비공개 PM 전달 경로로 사용한다.
- **실제 Guidance/45개 평가:** `https://api.openai.com/v1/responses`에 `gpt-4.1-mini` Guidance 및 `gpt-4o-mini` 구조화/Follow-up 평가 요청을 전송한다. 범위는 평가용 합성 발화, 모델 코드, 정규화된 증상, 결정적 Safety 상태/허용 행동과 검증된 근거 요약이다. 근거는 승인된 MVP 7청크/3모델 53개 Child와 동일 정체성의 RDS View에서 해당 사례에 선택된 내용만 보낸다. Guidance 요청당 요약 최대 5개·각 4,000자이며 `store=false`를 사용한다. 원문 PDF 전체, 실제 고객 PII, Oracle 정답·해설, DSN/키 값은 본문으로 보내지 않는다. 전송 승인과 API 비용 승인이 필요하다. `store=false`를 외부 처리나 보존이 전혀 없다는 보장으로 해석하지 않는다.

전송 대상 근거의 로컬 원본은 [MVP 7청크](../../../data/processed/structured/rag/mvp/rag_verified_sample.jsonl)와 [3모델 53개 Child](../../../data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl)다. 동일 파일/Index 정체성에서 선택된 요약만 승인 범위에 포함한다.

승인 범위가 다르면 승인된 부분만 실행한다. API Key나 DB 비밀번호 자체는 채팅에 요청하지 않는다.

## 승인 후 재현 명령

저장소 Root, Python 3.13.13, 승인된 Readonly 환경을 사용한다. 아래 명령의 SHA는 ledger 등 구현 완료 후 리뷰할 실제 PR SHA여야 한다. 평가 중 소스 수정이나 Public 설정 전환을 하지 않는다. RDS/Provider 승인이 없으면 `--execute`를 실행하지 않는다.

```powershell
$candidateSha = git rev-parse HEAD
$aiPython = 'C:\Project\SKN29-FINAL-4TEAM\ai\.venv\Scripts\python.exe'
& $aiPython -m pytest ai/tests/unit ai/tests/contract -q
& $aiPython -m ai.scripts.verify_three_model_readonly_runtime --expected-sha $candidateSha --output .codex_tmp/readonly-50-final.json
& $aiPython -m ai.scripts.evaluate_reference_scenarios --expected-sha $candidateSha --execute --runtime single_rag --output .codex_tmp/reference-45-single-final.json
& $aiPython -m ai.scripts.evaluate_reference_scenarios --expected-sha $candidateSha --execute --runtime multi_agent --output .codex_tmp/reference-45-multi-final.json
```

45개 모델 비교의 비용·평가 프로토콜은 PM 확정 범위를 따른다. Backend 동일 Inquiry 저장·Replay·HumanReview/공개 및 독립 QA 증거를 이 AI 실행 결과에 합쳐 최종 판정한다.

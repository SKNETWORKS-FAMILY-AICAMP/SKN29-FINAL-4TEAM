# 이동윤 → 윤승혁: Harness·HITL·Consultation Handoff Runtime 증거 보강 요청

> 발신: 이동윤 — Multi-Agent Core·RAG·Generation·Evaluation
> 수신: 윤승혁 — Reliability·Harness·HITL·Handoff
> 작성일: 2026-08-24 KST
> 요청 작성 기준 Branch / HEAD: `dongyoon` / `1c6eccd82b7be63de57b6810374a010b3bb8d693`
> 현재 상태: `REQUESTED / OWNER_EVIDENCE_REQUIRED`

## 1. 요청 목적

현재 `ai/scripts/verify_local_runtime.py`는 실제로 선택된 Pipeline Runtime,
Retriever·Provider, 응답 Trace Identity와 Multi-Agent 내부 Handoff Reason을
검증하도록 보강 중이다. 다만 이 Gate는 아래 항목을 증명하지 않는다.

- Harness 최종 판정과 Retry·Escalate 분기
- HITL Interrupt·Resume 결과
- Consultation Handoff Payload 생성·개인정보 제거
- Backend Handoff 실제 전달·저장

위 네 항목을 한 묶음의 `Multi-Agent E2E PASS`로 추정하지 않기 위해 Local
Runtime Gate 결과에는
`owner_evidence_boundaries.harness_hitl_consultation_handoff=OWNER_EVIDENCE_REQUIRED`
를 남긴다. 윤승혁 담당 영역의 현재 코드와 실행 결과를 기준으로 이 빈칸을 별도
증거로 채워 달라는 요청이다.

이 요청서는 Harness·HITL·Handoff 코드를 대신 수정하거나 공개 계약 변경을
지시하지 않는다. 필요한 구현 변경과 관련 테스트 변경은 담당자가 검토·수행한다.

## 2. 담당 경계

검토·실행 대상은 다음 윤승혁 주관 경로다.

- `ai/app/orchestration/harness/**`
- `ai/app/orchestration/hitl/**`
- `ai/app/orchestration/handoff/**`
- 위 Production 코드에 대응하는 `ai/tests/unit/harness/**`,
  `ai/tests/unit/hitl/**`, `ai/tests/unit/handoff/**`

`ai/scripts/**` 또는 공유 Pipeline·Schema 변경이 필요하면 변경 목적과 대상 파일을
먼저 공유하고 한 명의 편집자를 지정해 달라. 이동윤은 위 주관 경로를 이번 작업에서
수정하지 않는다.

## 3. 요청 실행 범위

최종 통합 Commit의 Clean Worktree에서 아래 Case를 실행하고, Case별 실제
`decision`, Issue Code, Retry 횟수, Escalate 여부를 정제된 증거로 남겨 달라.

| Case | 입력·조건 | 필수 확인 |
| --- | --- | --- |
| `H01` | 제품·공식 근거·Safety·출력 Schema 정상 | `PASS`, Retry 0, Escalate false |
| `H02` | 정상 검색 완료 후 근거 없음 | 즉시 `ESCALATE`, `NO_EVIDENCE`, Retrieval Retry 0 |
| `H03` | 타 제품 근거 | 1차 `RETRY_RETRIEVAL`, 최대 1회 후 `ESCALATE` |
| `H04` | Danger인데 `NORMAL` Guidance | `ESCALATE`, `SAFETY_CONFLICT` |
| `H05` | 출력 Schema 불일치 | `RETRY_GENERATION`, Generation Retry 최대 1회 |
| `H06` | 전체 처리 Timeout | `ESCALATE`, `AI_PROCESSING_TIMEOUT` |
| `H07` | HITL Reject와 오래된 `state_version` Resume | Reject 시 Guidance 없음, Version 불일치 fail-closed |
| `H08` | Consultation Handoff Payload 생성 | Exact 모델·Trace 보존, 연락처 등 민감정보 제거 |
| `H09` | Backend Handoff 전달 | 실제 Socket·수신·저장을 실행한 경우만 `PASS`; 미실행은 `NOT_RUN` |

최소 단위 회귀 명령은 다음과 같다. 실제 Runtime 또는 Socket 검증 명령이 따로
있으면 같은 회신에 추가해 달라.

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\harness ai\tests\unit\hitl ai\tests\unit\handoff -q
```

## 4. 증거 파일 계약

Git에 넣지 않는 `.runtime` 증거 파일은 다음 정보를 포함해야 한다.

- Schema Version, KST/UTC 생성 시각, 실행 환경의 비밀이 아닌 식별자
- Branch, 40자리 Commit SHA, Dirty 여부, Python Version
- 실행 명령별 Exit Code와 Test 결과
- Case ID별 Harness Decision, 공개 가능한 Issue Code, Retry Count,
  HITL/Handoff 결과
- 실제 Backend 전달 여부와 수신·저장 확인 범위
- 증거 파일 자체의 SHA-256

권장 경로는 다음과 같다.

```text
.runtime/evidence/20260824_harness_hitl_handoff_<commit12>_v0.1.json
```

다음 값은 증거 본문·문서·채팅에 넣지 않는다.

- DSN, API Key, Token, 비밀번호
- 고객 입력 원문·전화번호·개인정보
- Prompt·Source 원문·내부 Chunk 본문·Vector·Score
- Stack Trace와 Provider 원문 응답

식별이 필요하면 원시 ID 목록 대신 개수와 정렬된 ID 집합의 SHA-256을 사용한다.

## 5. 완료 조건

- [ ] 최종 통합 Commit의 40자리 SHA와 `git_dirty=false`가 기록됨
- [ ] H01~H08의 Case별 판정이 누락 없이 기록됨
- [ ] H09는 실제 Backend Socket·수신·저장을 확인했을 때만 `PASS`임
- [ ] Unit/표적 PASS와 실제 Runtime·Socket PASS가 별도 필드로 구분됨
- [ ] `retry_count`가 실제 요청 범위의 `0..1` 의미를 유지함
- [ ] HITL Reject·오래된 State Version·개인정보 제거가 fail-closed로 확인됨
- [ ] 공개 AI 응답 Schema나 승인된 Safety·Retry 정책을 증거 생성 목적으로 바꾸지 않음
- [ ] 증거 경로와 SHA-256이 회신됨

Harness Unit만 통과한 경우 상태는 `PARTIAL`이다. Backend 실제 전달을 실행하지
않았다면 `backend_delivery=NOT_RUN`으로 남기며, 이를 동일 Inquiry 저장 E2E나
Web/Mobile 소비 PASS로 확장하지 않는다.

## 6. 회신 형식

```text
owner=윤승혁
reviewed_commit=<40자리 SHA>
dirty=false | true
decision=APPROVE | CHANGE_REQUEST | HOLD
commands=<실행 명령>
exit_codes=<명령별 Exit Code>
harness_unit=PASS | FAIL | NOT_RUN
harness_runtime=PASS | FAIL | NOT_RUN
hitl_interrupt_resume=PASS | FAIL | NOT_RUN
consultation_handoff_build=PASS | FAIL | NOT_RUN
backend_delivery=PASS | FAIL | NOT_RUN
scenario_results=<H01~H09 Case별 결과>
evidence_path=<.runtime 경로, 원문 첨부 금지>
evidence_sha256=<64자리 SHA-256>
blocker_owner=<없으면 NONE>
blockers=<없으면 NONE>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```

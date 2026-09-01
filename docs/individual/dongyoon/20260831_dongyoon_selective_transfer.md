# dongyoon 직접 반영 기록

상태: **APPLIED_UNCOMMITTED**. 사용자 요청에 따라 작업 위치를 원래 `dongyoon` checkout으로 옮겼다. 추가 브랜치는 만들지 않았으며, 이전에 만든 `codex/ai-main-selective-20260831` 브랜치와 worktree 등록은 제거했다.

## 반영 위치와 Git 상태

| 항목 | 값 |
| --- | --- |
| 현재 작업 위치 | `C:/Project/SKN29-FINAL-4TEAM` |
| 현재 브랜치 | `dongyoon` |
| 보존한 HEAD | `40a59a539035ba91c3df0491bc021a7f20153011` |
| 미커밋 병합한 main | `2305189a1fd62f6fe40bd55c6d2c1fc310a6a783` |
| 선별 원본 renew | `e411be3dd39f2a6b8b7defb219cdd8aaf572d68e` |
| 반영 내용 | 후보 AI 파일 60개 + 기존 작성 문서 4개, 이후 이관 기록 추가 |
| 충돌 | 없음 |
| Commit / Push | 수행하지 않음 |

`dongyoon`에 없던 main의 HumanReview 보강 및 45개 평가 데이터가 필요해 `git merge --no-commit --no-ff origin/main`을 먼저 수행했다. 이후 검증된 선별 AI 수정을 복사했다. main에서 가져온 내용은 Stage에 있고 AI 수정·새 파일은 미커밋 상태다. **MERGE_HEAD가 남아 있으며 아직 병합 커밋은 만들어지지 않았다.** 현재 HEAD만으로 최종 구현 SHA를 표현하지 않는다.

원래 HEAD의 JAC104 증거 파일 12개와 사용자 미추적 `docs/handoffs/20260831_JAC104_v2_operating_mcp_probe.py`는 Hash를 비교해 보존했다. 해당 MCP 점검 스크립트를 실행하거나 Stage에 넣지 않았다. Backend·Data·Infra·공개 계약에는 main에서 온 변경 외에 별도 수정을 하지 않았다.

## 코드와 검증

이관 전후 후보 AI 60개 파일의 Hash가 같음을 확인했다. Raw Symptom 우선, 독립 Safety 신호, 문진 fallback, Guidance 검증, 온수 Scenario Evidence 선택 및 최종 SHA 평가 도구가 그대로 반영됐다. CAUTION 검수를 없애는 renew `f8d090ae`는 계속 제외한다.

현재 `dongyoon`에서 다시 실행한 검증은 [이관 검증 JSON](20260831_dongyoon_selective_validation.json)에 기록한다. 이전 별도 worktree의 결과는 [초기 검증 JSON](20260831_ai_selective_validation.json)에 이력으로 보존한다.

- AI 전체 Unit + Contract: 1,041 PASS, warnings 4, subtests 41 PASS.
- 로컬 AI Integration: 5 PASS / 13 SKIP. RDS 필수 테스트는 별도 HOLD/NOT_RUN.
- Backend 최초 재실행: 1,292 PASS / 18 SKIP / 3 FAIL / 9 ERROR. 중단된 12건은 `.runtime/backend-ai` 고정 테스트 출력의 PermissionError였다.
- 코드·테스트·Fixture 기대값·ACL을 수정하지 않고 권한이 허용된 실행으로 관련 18개를 재검증해 PASS했다. 이어 전체 Backend 회귀도 **1,304 PASS / 18 SKIP, 종료 코드 0**으로 완료했다. 실행 시간은 283.31초이며 SQLite/Fake 검증이다.

## 백업과 임시 작업 정리

이관할 파일, 이관 전 파일, 기존 작업 기록을 `.codex_tmp/dongyoon-selective-transfer-20260831-191755/candidate-and-preimages.zip`에 백업하고 CRC 및 파일별 Hash를 확인했다. `transfer.json`에는 파일 목록과 사용자 파일 보존 Hash가 있다.

Git에는 `dongyoon` checkout만 worktree로 등록돼 있고, 임시 브랜치는 삭제했다. Windows 접근 제한 때문에 이전 worktree의 일부 파일과 pytest 캐시는 `.codex_tmp`에 남아 있다. 삭제·이동을 강행하거나 ACL을 바꾸지 않았으며, 이 디렉터리에서 작업을 계속하지 않는다. 백업용 부분 이동 디렉터리도 데이터 보존을 위해 남겼다.

## 그대로 남는 승인·검증 경계

- CAUTION HumanReview와 기존 Backend 원장·잠금 정책은 이미 확정·구현돼 재승인 대상이 아니다.
- 추가 AI/Harness 원인 ledger 증빙·전달·검증/저장 계약은 [제안서](20260831_consultation_cause_ledger_proposal.md)의 PM 사전 확인 범위를 유지한다. 이번 이관으로 해당 추가 기능을 구현하지 않았다.
- 공식 RDS 50 Case와 45개 실제 판단 평가는 미실행이다. RDS 연결, 공식 Evidence의 Provider 전송 승인, 최종 Commit/PR SHA가 필요하다.
- 독립 QA 및 PM 병합 승인은 남아 있다. **RDS 쓰기와 Public Runtime 활성화는 HOLD**다.

이전 문서의 '원래 dongyoon은 Clean/미변경'은 이관 전 관측이다. 현재 상태는 이 문서와 이관 검증 JSON을 기준으로 판단한다.

# 2026-08-31 잔여 작업 수행 결과

`dongyoon` 작업 트리에 수정했다. 새 개발 브랜치, Commit, Push, 운영 배포는 수행하지 않았다.
기준 HEAD는 `521c1d1d0a372ad29dc7ff627b195dfd1a8666c8`이고, 이번 수정은 미커밋 상태다.

**실제 RDS Readonly 50건과 로컬 회귀는 통과했다. 냉매 P0와 온수 계약·평가 충돌이 남아 있으므로 병합·최종 QA·Public 활성 준비 완료는 아니다.**

## 수정한 내용

- 온수·정수·냉수 버튼 동시 점멸과 빨간 표시창 조합을 결정적으로 감지한다. 기존 승인 `SAFETY-HOT-WATER-HEATER-001`을 사용하며, 두 Pipeline 모두 LLM·문진·검색보다 먼저 안전 분기한다. 한 버튼 점멸, 잠금 표시등, 부정·가정 문장은 구분한다. 새로운 위험 ID나 Backend 정책은 추가하지 않았다.
- 평가 출처 검증을 보강했다. Git SHA 문자열만으로 통과하지 않고 실제 저장소 Root·Commit Object를 확인한다. 실행 중 Runtime·평가 도구·Prompt·Dataset·Manifest 변경과 필수 입력 누락도 검출한다.
- 오프라인 입력 준비 도구와 Provider/검색을 금지하는 위험 15건 진단 도구를 추가했다. 입력 검증 PASS와 실제 평가 PASS를 분리한다.
- 기존 AWS AI 이미지에 임시 QA 환경을 구성하는 Readonly 실행 스크립트를 추가했다. 실제 Git·고정 SHA·전체 추적 파일 원본 검증, verify-full TLS, View 최소 권한, 자원 제한, 실패 시 정리를 포함한다. 운영 서비스에는 적용하지 않는다.

Backend·Data·공유 Safety 원장·루트 Git 속성은 수정하지 않았다. CAUTION HumanReview, 승인 전 고객 공개 금지, Safety/Fail-closed 잠금과 추가 ledger 구현 전 확인 조건을 유지했다.

## 실제 검증 결과

| 검증 | 결과 | 범위 및 제한 |
| --- | --- | --- |
| AI Unit + Contract | **1,076 passed**, 4 warnings, 41 subtests | Python 3.13.13, 최종 Dirty 작업 트리. 모델 성능·전체 서비스 E2E 수치가 아님 |
| Backend Unit + API | **1,671 passed, 37 skipped** | Clean 기준 SHA, 로컬 SQLite. Backend 코드는 이후에도 변경하지 않음. Skip과 실제 운영 저장 검증을 완료로 대체하지 않음 |
| 온수 경고·기존 안전 표적 테스트 | **114 passed** | 부정·가정·조건 부족, 기존 승인 안내, 두 Pipeline 외부 호출 0, 전기 위험 동반 시 TOTAL_STOP |
| 위험 15건 × 2 Pipeline | **FAIL — 각각 9/15 전체 기대값 일치** | 12건 DANGER 확인. 그중 온수 3건은 사용 제한 기대값 불일치. 냉매 3건 미해결 |
| 공식 RDS Readonly 50건 | **50/50 PASS** | 현재 커밋 `521c1d1…`의 격리 three_model_integration / direct. 최종 수정 SHA의 결과는 아님 |
| 오프라인 평가 입력 | **QA_INPUTS_READY** | 45개 분포, 50=43+7, 53 Child·15/19/19·Canonical 일치. 실제 실행 건수는 0으로 기록 |
| 의존성·형식 | `pip check`, `git diff --check`, Shell/Python 구문 PASS | 실행 품질 또는 운영 승인 증거로 확대하지 않음 |
| 전체 45개 Provider 평가 | **NOT_RUN** | 외부 Evidence 전송 승인과 최종 SHA 실행 필요 |
| 동일 Inquiry 저장·고객 공개 E2E / 독립 QA | **NOT_RUN** | 로컬 회귀를 공동 E2E나 독립 QA로 대체하지 않음 |

위험 15건 진단은 평가표의 위험 라벨로 부분집합만 선택하고, Runtime에는 실제 고객 원문과 제품 코드만 전달한다. `context_facts`, 기대 위험·경로, 근거 정답은 입력하지 않는다. 평가 데이터·기대값을 수정하거나 Runtime 정답 Lookup으로 사용하지 않았다.

냉매 중 1건은 CAUTION 문진 대기, 2건은 금지된 검색 호출에서 ERROR가 발생했다. 실제 Provider·DB 호출은 모두 차단했으며 전체 DANGER 누락 수를 0으로 기록하지 않는다. 온수 감지 보완 전에는 두 IAC 경고도 검색으로 넘어갔지만, 수정 후에는 외부 호출 전에 DANGER로 분기한다.

## RDS 브라우저 실행 증거

AWS Console → SSM → 별도 임시 QA 컨테이너 → 기존 승인 RDS Readonly 역할로 검증했다.

- 성공 SSM: `26e71b64-50b4-4a91-a551-c5d37340af63`, 2026-08-31 12:19:00–12:21:05 UTC, exit 0.
- 실제 Git Commit, Clean 상태, **3,438개 추적 파일의 원본 바이트**를 검증한 뒤 실행했다.
- Python 3.13.13, PostgreSQL 16.14, pgvector 0.8.2, BAAI/bge-m3 고정 Revision `5617a9f61b028005a4858fdac845db406aefb181`.
- 승인 View `backend_ai_rag_chunks_v1`: 53건, 모델별 15/19/19, Index 2.0.0, Canonical Chunk-set 일치.
- 43 positive / 7 negative 모두 PASS. cross-model, direct-parent, unverified Hit 각각 0.
- 생성 모델·Prompt는 사용하지 않았다. Provider 호출·Backend 쓰기·RDS 데이터 쓰기 0. Fixture 삽입이 없으므로 Rollback 검증은 해당 없음이다.
- 운영 컨테이너 ID·Image·시작 시각·재시작 횟수·Health는 전후 동일했다. 임시 QA 컨테이너·이름 붙인 이미지·작업 디렉터리·RAM 임시 비밀값 파일은 정리했다. 공유 Docker Build Cache는 prune하지 않았다.

첫 실행은 QA 스크립트의 CA 경로 가정 때문에 중단됐다. 실제 경로 `/run/secrets/rds-ca.pem`과 기존 verify-full 설정을 확인한 후 재시도했다. 이후 바이너리 NPZ에 적용된 Git text 속성 때문에 Clean 검사에서 멈췄다. 해당 파일이 Commit Blob과 동일함을 확인하고 임시 checkout의 `.git/info/attributes` 한 항목만 보정했다. 모든 파일의 원본 검증도 추가했다. 실패 이력과 임시 예외를 숨기지 않고 원시 증거에 보존했다.

운영 설정은 계속 **jac104_v2_recovery / multi_agent / mcp, JAC104만 승인**이다. QA의 3모델 Profile은 운영 제품 활성화가 아니다.

원시 50건 보고서의 `final_sha_eligible=true`는 그 Clean 실행 SHA의 출처 조건 통과를 뜻한다. 이번 미커밋 수정·추가 ledger·독립 QA·PM 승인까지 완료했다는 뜻이 아니다. 종합 기록의 `final_release_eligible`와 `final_pr_evidence_eligible`는 **false**로 유지했다.

50건 결과 파일 SHA-256:
`9086f53ea3e9d35c48867945841f98393615189352e2014c739e07cfe27aaa91`

## 남은 작업과 순서

1. **냉매 안전 Rule 공동 확정** — 현재 Backend 원장에 전용 Rule이 없다. 기존 전기/누수 Rule을 재사용하면 가스 상황에서 플러그 제거를 유도할 수 있어 전용 Rule과 복합 위험 행동 우선순위가 필요하다.
2. **온수 3건의 제한 범위 결정** — 평가표 TOTAL_STOP, 현재 PM 승인 히터 계약 PARTIAL_STOP, 매뉴얼 음용 금지 범위를 PM·Backend·Data/QA가 함께 정리해야 한다. 평가 정답이나 승인 계약을 임의로 바꾸지 않았다.
3. **추가 ledger 연동 승인 후 구현** — 기존 CAUTION HumanReview는 확정 사항이다. 추가 원인 증빙·전달 Envelope·원자 저장 계약만 확인이 남아 있다.
4. **최종 Clean PR SHA 평가** — 공식 Evidence 외부 Provider 전송 승인 후 전체 45건을 실행하고, 최종 SHA로 Readonly 50건과 필요한 Backend 저장·공개 경계를 다시 검증한다.
5. **김은진 독립 QA → 윤승혁 PM 병합 승인** — 요청용 로컬 패키지를 준비했다. 메시지/이슈 발송 또는 승인 수령은 수행하지 않았다.

이 확인이 필요한 이유는 사용자에게 전달받은 PM의 구현 전 ledger 확인 조건과 프로젝트의 공동 Safety 원장 관할이다. 이미 정해진 CAUTION 정책을 다시 승인받기 위해 멈춘 것이 아니다. RDS 쓰기와 Public Runtime 활성화는 별도 승인 전 HOLD다.

## 원시 산출물

- [검증 종합 JSON](20260831_remaining_work_validation.json)
- [공동 결정안·재현 명령·독립 QA 인계](20260831_remaining_decisions_and_qa_handoff.md)
- [전체 Artifact Hash 목록](evidence/20260831_remaining/artifact-manifest.json)
- [최종 작업 트리 Source/Prompt/Dataset Hash](evidence/20260831_remaining/working-tree-source-manifest.json)
- [현재 커밋 RDS 50건 원본](evidence/20260831_remaining/readonly-50-current-commit.json)
- [위험 15건 수정 후 결과](evidence/20260831_remaining/danger-15-after-fix.json)
- [브라우저 수집 원본·중단 이력](evidence/20260831_remaining/rds-browser-captures.json)

이전 개인 기록을 삭제하거나 과거 결과를 최신 PASS로 바꾸지 않았다. 이전 RDS 감사 기록도 당시 범위로 보존했다. 이번 실행 결과는 이 문서와 동행 원시 JSON을 기준으로 판단한다.

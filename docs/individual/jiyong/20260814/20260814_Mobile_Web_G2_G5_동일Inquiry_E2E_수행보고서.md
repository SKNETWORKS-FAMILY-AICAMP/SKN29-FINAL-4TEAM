# Mobile·Web G2~G5 동일 Inquiry E2E 수행 보고서

## 1. 현재 판정

```text
baseline=ed4afa79c4f24393ec03740e4a2da10e0073288a
mobile_candidate=cde29fd7f69cf9f6e3fdeea015ee96531c3923a9
mobile_g2_g3_client=READY
web_g4_source=NO_EDIT_SOURCE_READY_AUTHOR_STATIC_PASS
web_g4_runtime=NOT_RUN
galaxy_install=PASS
g1a_actual_ai=NOT_READY
jiyong_local_g1b=BLOCKED
team_g1b_prior_qa=READY_AT_11d771a
final_main_g1b=REVALIDATION_PENDING
g2_g3_g4_g5_actual=NOT_RUN
overall=HOLD_G1_ENVIRONMENT
```

## 2. 실행 순서별 상태

| 순서 | 작업 | 결과 | 근거·남은 조건 |
| ---: | --- | --- | --- |
| 0 | 최신 main·jiyong 정렬 | PASS | 시작 기준 `ed4afa7`, 당시 0/0 |
| 1 | Mobile DTO·API·Repository·DI | PASS | Customer Guidance GET 실제 Remote 경계 구현 |
| 2 | Mobile ViewModel·UI·오류 처리 | PASS | 200 빈 Evidence 정상 표시, 409 재시도, Fake fallback 금지 |
| 3 | Unit·APK·Galaxy 설치 | PASS | Unit 75, APK·AndroidTest Build, SM_X610 설치·실행, 실 Backend AndroidTest 진입점 준비 |
| 4 | G1 READY 확인 | BLOCKED | 로컬 AI 8001 DOWN·로컬 DB 미준비, final main 팀 환경 재검증 필요 |
| 5 | 새 Inquiry G2→G3 | NOT_RUN | G1 READY 뒤 새 Inquiry 필요 |
| 6 | 같은 Inquiry Web G4 | NOT_RUN | G3 인계값 필요 |
| 7 | Mobile G5 재조회 | NOT_RUN | G4 완료값 필요 |
| 8 | 독립 QA·PM 판정 | NOT_READY | G2~G5 실제 증거 필요 |
| 9 | 원 담당자 사후 인계 | PENDING | 양정현·한예나 복귀 후 Diff·증거 검토 |

## 3. Web 무수정 Gate

현재 Web에는 다음 경로가 이미 연결돼 있다.

```text
GET /api/v1/inquiries
GET /api/v1/inquiries/{id}
POST /api/v1/inquiries/{id}/start-consultation
PATCH /api/v1/inquiries/{id}/consultation-summary
POST /api/v1/inquiries/{id}/consultation-summary/confirm
POST /api/v1/inquiries/{id}/complete-consultation
```

정적·단위 검증 결과:

| 검증 | 결과 |
| --- | --- |
| 표적 Vitest | `6 files / 31 tests PASS` |
| Lint | PASS |
| Typecheck | PASS |
| Production Build | PASS |
| Web Production 수정 | 없음 |

따라서 PM 승인대로 Web은 실제 동일 Inquiry G4를 먼저 무수정으로 실행한다. Network·HTTP·Correlation 증거로 Web 결함이 재현될 때만 최소 수정한다.

## 4. G1 차단 근거

- AI `/health`: 미기동.
- Backend `/health`: 검증 종료 시점 미기동.
- 현재 DB: 팀 격리 통합 DB가 아닌 로컬 `waterbridge`.
- 최지용 로컬 Readiness 강제 감사: `BLOCKED`.
- Crosswalk `0/7`, Page Link `0/8`, RAG View `0/7`.
- AI Readonly Role·SELECT Gate가 준비되지 않음.
- 팀 환경은 과거 `main@11d771a`에서 QA READY였으나 final main 재검증은 아직 없다.
- `/health` 200만으로 G1 PASS를 판정하지 않는다. Audit, 실제 Provider·pgvector·HTTP, 같은 Inquiry DB 저장을 각각 증명한다.
- 실제 OpenAI·pgvector·Schema·Backend 저장 동일 Correlation 증거가 없음.

이 상태에서 G2를 실행하면 실패 AIRun과 멱등 원장만 남을 수 있으므로 최종 Inquiry 생성을 중단했다.

작성자 우선 실행은 실제로 4번 G1 READY 확인까지 진행했다. Readiness Exit 1을 확인한 뒤 새 Inquiry 생성 전 멈췄으므로 G2~G5 데이터는 만들지 않았다. 이는 `NOT_RUN`을 숨긴 것이 아니라 대표 Inquiry 오염을 막기 위한 중단조건 적용이다.

## 5. G1 READY 후 동일 Inquiry 실행 절차

| Gate | 담당 | 실행 | 필수 증거 |
| --- | --- | --- | --- |
| G2 | 최지용 임시 Mobile | Galaxy에서 실제 Guidance 조회 | inquiry ID, 200, state/version, 안전 문구, correlation |
| G3 | 최지용 임시 Mobile | 상담 요청 후 Snapshot 재조회 | 전후 상태·버전, allowed_actions, idempotency |
| G4 | 최지용 임시 Web | Mock Off, 같은 ID로 Start→Save→Confirm→Complete | 단계별 HTTP·버전·actions·correlation |
| G4 재조회 | 최지용 임시 Web | 브라우저 전체 새로고침 | 상담 내용 복구, 최종 `COMPLETION_PENDING` |
| G5 | 최지용 임시 Mobile | 앱 재진입·Snapshot 재조회 | Web·Mobile·DB 상태/버전 일치 |

Mobile AndroidTest는 G1 제출과 G2·G3를 분리한다.

- `CustomerG1SubmitSmoke`: 새 Inquiry ID·code·상태·버전·Replay를 Logcat에 기록한다.
- `CustomerG2G3Smoke`: 동일 Inquiry의 Guidance와 상담 요청 전후 상태·버전을 Logcat에 기록한다.
- QA가 가진 Process Secret을 문서나 Git에 옮기지 않고 같은 실행 세션의 환경변수로만 주입한다.

## 6. Web 결함 분류

다음은 Web 수정 사유가 아니다.

- AI/G1 미준비
- Backend·Proxy·DB 미기동
- 기대된 음성 케이스의 인증 401, 역할 403, 배정 은닉 404
- 기대된 음성 케이스의 stale state version 409
- 계약·State Machine·Error Code 변경 요구

Web 수정 전 반드시 Method, URL, Request/Response, HTTP, error code, correlation ID, 상태·버전 전후를 확보한다.

Happy Path 대표 Inquiry를 오염시키지 않도록 504·No-Evidence·Danger·Replay·403·404·409는 정상 흐름 완료 후 별도 합성 Inquiry로 검증한다.

## 7. 최종 완료 기준

- 같은 새 Inquiry 하나로 G2→G3→G4→G5를 순서대로 수행한다.
- 모든 Client가 Mock Off이며 같은 Backend·PostgreSQL을 사용한다.
- Backend·DB·Web·Mobile의 상태와 버전이 일치한다.
- G4 정상 종료는 `COMPLETION_PENDING`이며 임의 `RESOLVED` 판정 금지.
- 김은진 독립 QA와 PM 최종 판정 전 전체 PASS 선언 금지.

# 5주차 우선순위 Backlog

> 기준일: **2026-08-10 KST**  
> 기간: **2026-08-10 ~ 2026-08-14**  
> 기준 Commit: `f3c66b3cbfd41852440bf0726722438612d6885f`  
> 운영 순서: **Gate → Runtime 생산 → 실제 소비 → 대표 E2E → 전체 회귀**

## 1. P0 실행 순서

| 순서 | 마감 | 산출물 | 주관 | 선행 산출물 | 완료 증거 | 상태 |
|---:|---|---|---|---|---|---|
| 1 | 8/10 오전 | 계획·WBS·Scope·Dependency 기준본 | 윤승혁 | 팀원별 5주차 지침 | 문서 정합성 검사·변경 이력 | 진행 중 |
| 2 | 8/10 오전 | 계약·Data·Backend·AI·Web·Mobile 동일 Commit Gate | 김은진·영역 담당 | 계획 기준 Commit | 명령·Exit Code·결과 경로 | 재검증 필요 |
| 3 | 8/10 | 상담사 Inquiry 조회·고객 문진 Runtime | 최지용 | Backend·계약 Gate | API·권한·DB Test | 미판정 |
| 4 | 8/10 | Multi-Agent 책임·Schema·Event 계약 | 이동윤·윤승혁·최지용 | 계약 Gate | Architecture·Mapping Test | 미판정 |
| 5 | 8/10 | Web 비동기 Remote 기반·Mobile 제품/구독 Remote | 한예나·양정현 | 대상 Operation | Test·Build·Remote 증거 | 미판정 |
| 6 | 8/11 | 실제 LLM·팀 DB pgvector Retrieval | 이동윤·김은진 | Data·AI Gate | 검색·평가·LLM Schema Test | 미판정 |
| 7 | 8/11 | Backend↔AI 실제 HTTP 수직 연결 | 최지용·이동윤 | Agent 계약·Backend Gate | HTTP·Event·DB·`correlation_id` | 미판정 |
| 8 | 8/11 | Web 상담 목록·상세 Remote | 한예나 | 상담 조회 Runtime | Pagination·Filter·409 Test | 미판정 |
| 9 | 8/12 | 추가 질문·위험·근거·Fallback Runtime | 이동윤·최지용 | HTTP 수직 연결·Vector | 정상·위험·근거 없음 Test | 미판정 |
| 10 | 8/12 | 상담 Start·Summary·Confirm·Complete Runtime | 최지용·한예나 | 상담 Operation | API·DB·State·Web Test | 미판정 |
| 11 | 8/12 | 방문 Review·Create·Schedule·Confirm Runtime | 최지용 | 상담 완료·후반 Action 승인 | API·권한·상태 Test | 미판정 |
| 12 | 8/12 | Web·Mobile AI/Evidence·Fallback 소비 | 한예나·양정현 | 공개 DTO·Backend Runtime | DTO·UiState·비노출 Test | 미판정 |
| 13 | 8/13 오전 | Visit Remote·E2E 후반 Operation | 최지용·한예나·양정현 | 방문 Runtime | 실제 Remote·기사 권한 Test | 미판정 |
| 14 | 8/13 오전 | 대표 고객→AI→상담→방문→후속 E2E 1차 PASS | 전 팀원·김은진 | 1~13 산출물 | 단계별 HTTP·DB·State·UI 증거 | 미판정 |
| 15 | 8/13 오후 | P0 동결 Commit | 윤승혁 | E2E 1차 결과 | SHA·예외 승인 기록 | 미판정 |
| 16 | 8/14 | 전체 회귀·대표 E2E 재실행·Feature Complete 판정 | 김은진·윤승혁 | 동결 Commit | QA Summary·Exit Gate | 미판정 |

## 2. P0 완료 경계

- P0 완료는 파일 존재가 아니라 실제 URL·권한·Service·DB·State·AI·소비자 실행 증거로 판정한다.
- Web·Mobile은 Mock 자동 대체 없이 Remote 경로로 대표 E2E에 참여한다.
- AI는 실제 LLM·팀 DB Vector와 연결하되, Provider 장애는 별도 Fallback E2E로 기록한다.
- 대표 E2E 1차 PASS는 8월 13일, 최종 판정은 8월 14일 최신 Commit 재실행 결과다.
- 실패한 P0는 담당자·해제 조건·목표 시간을 기록하고 완료로 표시하지 않는다.

## 3. P1 — 5주차 필수 범위 밖

| P1 항목 | 5주차 허용 범위 | 착수 조건 |
|---|---|---|
| 운영 Dashboard | 요구·지표 메모 | P0 E2E·회귀 PASS 후 |
| Graph DB | 도입 판단 기록 | pgvector P0 완료 후 |
| Kubernetes | 배포 설계 검토 | 6주차 Release Gate |
| 제품 모델 대규모 확대 | 후보 목록 | 대표 제품 E2E PASS 후 |
| 추가 Agent 확대 | 필요성 기록 | 현재 Agent Routing·Fallback PASS 후 |
| 대규모 UI 재설계 | 결함 메모 | Remote 전환·E2E PASS 후 |

## 4. 주간 Exit 조건

1. P0 Runtime이 실제 URL과 DB에서 동작한다.
2. 실제 LLM·Vector·Backend HTTP 경계가 통과한다.
3. Web·Mobile이 확정 DTO와 서버 State를 Remote로 소비한다.
4. 정상 대표 E2E가 8월 13일 최소 1회 PASS한다.
5. 8월 13일 오후 동결 후 8월 14일 전체 회귀와 E2E가 재실행된다.
6. WBS·Scope·Dependency·Owner·Exit 문서가 같은 담당자·날짜·증거를 가리킨다.

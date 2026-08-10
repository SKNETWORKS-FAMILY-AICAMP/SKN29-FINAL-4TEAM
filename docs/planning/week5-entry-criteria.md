# 5주차 진입 조건

> 기준일: **2026-08-10 KST**  
> 계획 기준 Commit: `f3c66b3cbfd41852440bf0726722438612d6885f`  
> 운영 판정: **FEATURE_COMPLETE_ENTRY / GATED_EXECUTION**  
> 목표: **8월 13일 대표 E2E 1차 PASS · 8월 14일 P0 Feature Complete 재검증**

## 1. 진입 원칙

1. `UNBLOCK_FIRST`는 8월 10일 오전의 선행 단계이며 5주차 전체 목표가 아니다.
2. 5주차 종료 기준은 최소 연결이 아니라 실제 Client·Backend·Multi-Agent·PostgreSQL을 통과한 P0 대표 E2E다.
3. 담당자 완료 선언 대신 같은 Commit의 Runtime·Test·DB·로그 산출물로 Gate를 판정한다.
4. 선행 Runtime이 열리는 날 Web·Mobile이 Remote 소비를 시작한다.
5. 8월 13일 오후 이후 신규 P0 기능·계약·핵심 Agent·DB Schema를 추가하지 않는다.
6. Gate가 실패하면 상태를 `BLOCKED`로 유지하고 Mock·과거 증거를 PASS로 승격하지 않는다.

## 2. Feature Complete 진입 Gate

| Gate | 8월 10일 확인 조건 | 현재 계획 상태 | PASS 증거 | 책임 |
|---|---|---|---|---|
| `W5-G01` 기준선 | WBS·Scope·Backlog·Dependency·Owner·Exit가 같은 일정 | `IN_PROGRESS` | 문서 Diff, 깨끗한 기준 Commit | 윤승혁 |
| `W5-G02` 계약 | State·Code·OpenAPI·Example·Action Crosswalk 검사 | `REVALIDATION_REQUIRED` | Validator·Contract Test Exit 0 | 윤승혁·최지용 |
| `W5-G03` Data·Seed | 대표 제품·구독·문의·근거와 Backend Crosswalk 일치 | `REVALIDATION_REQUIRED` | Data Test·QA·Seed·Hash | 김은진·최지용 |
| `W5-G04` Backend·DB | Python·Django·PostgreSQL·Migration·Seed·회귀 | `REVALIDATION_REQUIRED` | Version, Migration Drift 0, pytest | 최지용·김은진 |
| `W5-G05` AI·Vector·LLM | 실제 LLM, 팀 DB pgvector, 제품·세대 Filter 검색 | `REVALIDATION_REQUIRED` | AI Test, Index·검색 로그, 평가 결과 | 이동윤·김은진 |
| `W5-G06` Web | Test·Lint·TypeScript·Build와 Remote 경계 | `REVALIDATION_REQUIRED` | 명령·Exit Code·Build | 한예나·김은진 |
| `W5-G07` Mobile | SDK·JDK·Gradle, Core·Customer·Technician Test·APK | `REVALIDATION_REQUIRED` | Version, Test, APK | 양정현·김은진 |
| `W5-G08` Backend↔AI | 실제 HTTP→Schema→Event→DB→추적 ID | `TARGET_8_11` | 통합 Test와 DB·로그 | 최지용·이동윤 |
| `W5-G09` 상담·방문 | 상담·방문 P0 Operation과 권한·409·멱등성 | `TARGET_8_12` | API Test, OpenAPI, DB State | 최지용 |
| `W5-G10` 소비자 Remote | Web·Mobile이 실제 Backend DTO·State를 소비 | `TARGET_8_13` | Remote Test·화면 증거 | 한예나·양정현 |
| `W5-G11` 대표 E2E | 고객→AI→상담→방문→후속 확인 1차 PASS | `TARGET_8_13` | 단계별 HTTP·DB·State·UI 증거 | 전 팀원·김은진 |
| `W5-G12` 최종 회귀 | 동결 Commit에서 전체 회귀·E2E 재실행 | `TARGET_8_14` | Feature Complete QA Summary | 김은진·윤승혁 |

## 3. 준비된 고정 입력

- 대표 제품 `WPUJAC104DWH`
- 대표 구독 `SYN-JAC104-002`
- 대표 문의 `DEMO-INQ-002`
- 대표 증상 `출수량 저하`
- 공식 근거 `WPU-JAC104D·WPU-JCC104D REV.00 38쪽`
- State Machine `1.0.0 / TEAM_APPROVED`와 Action 23개 Crosswalk

입력은 8월 10일 현재 Commit에서 다시 검증한 뒤 사용한다. 과거 PASS만으로 현재 PASS를 기록하지 않는다.

## 4. 일자별 진입 경계

| 날짜 | 열려야 하는 산출물 | 후속 소비 |
|---|---|---|
| 8/10 | `W5-G01`~`G07`, 상담사 조회·고객 문진 Runtime, Agent 책임 계약 | Web Remote·Mobile 구독·문의·AI 구현 |
| 8/11 | 실제 LLM·Vector, `W5-G08`, 상담 조회 Runtime | 상담 Agent·Web 상담·AI 결과 소비 |
| 8/12 | `W5-G09`, 역할별 AI 결과, 후반 Action 승인 | Visit Remote·전체 E2E 조립 |
| 8/13 오전 | `W5-G10`·`G11` | Feature Complete 후보 Commit |
| 8/13 오후 | P0 기능 동결 | 회귀 수정만 허용 |
| 8/14 | `W5-G12` | 6주차 Release Gate 인계 |

## 5. Gate 완료 정의

Gate는 다음 항목이 모두 있을 때만 `PASS`다.

1. 검증 Commit 전체 SHA
2. Runtime·DB·도구 Version
3. 재현 명령과 Exit Code
4. PASS·FAIL·SKIP 집계
5. 결과 파일·로그·Test 경로
6. Mock·미연동·제외 범위
7. 해당 산출물을 소비한 후속 단계의 결과

## 6. 진입 결정

5주차는 **Feature Complete 목표로 진입**한다. 8월 10일 Gate 복구가 지연되면 후속 일정과 담당 Blocker를 즉시 갱신하며, 목표를 자동으로 “최소 연결”로 낮추지 않는다. 8월 14일 `W5-G12`가 실패하면 `FEATURE_COMPLETE`가 아니라 `INTEGRATION_BLOCKED` 또는 `DONE_WITH_LIMITATION`으로 판정한다.

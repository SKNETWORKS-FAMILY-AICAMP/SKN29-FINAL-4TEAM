# 5주차 진입 조건

> 기준일: **2026-08-07 KST**
> 기준 Commit: `dad0e7a2c0e6c184ac8811bce6c6974bd7cb3fe0`
> 4주차 Exit: [CONDITIONAL_EXIT / WEEK5_BLOCKERS_OPEN](../testing/week4-exit-gate.md)
> 진입 판정: **CONDITIONAL_ENTRY / UNBLOCK_FIRST**

## 1. 진입 원칙

1. 4주차 잔여 환경·통합 결함을 신규 Agent 구현보다 먼저 처리한다.
2. 담당자 완료가 아니라 계약·API·DB·Test·로그 산출물로 Gate를 해제한다.
3. Gate가 막힌 소비자 작업은 Mock을 늘리지 않고 계약 Fixture·Adapter 경계까지만 진행한다.
4. 발표 피드백은 검증 가능한 기존 WBS에 연결하고 즉시 신규 범위로 추가하지 않는다.

## 2. Gate 판정

| Gate | 진입 조건 | 현재 상태 | 해제 증거 | 책임 |
|---|---|---|---|---|
| `W5-G01` 기준선·Issue | 3.3·3.6 문서 Commit, WBS·Issue·담당자 일치 | `PENDING_COMMIT_AND_ISSUE` | 깨끗한 HEAD, Issue 링크·회신 | 윤승혁·김은진 |
| `W5-G02` 계약 기준선 | State Machine·Crosswalk·Code·OpenAPI·Example Gate 통과 | `PASS_WITH_TEST_CARRY` | Validator 6종 PASS, Contract Test 7/7 승계 | 윤승혁·김은진 |
| `W5-G03` 대표 Data·Seed | 대표 제품·구독·문의·근거를 같은 Version으로 재현 | `PASS_CARRIED` | Data 67/67, QA·Finalize, Seed·Manifest | 김은진 |
| `W5-G04` Vector 검색 | 팀 DB에서 제품·세대 Filter와 대표 근거 검색 재현 | `BLOCKED` | pgvector Index 로그, 12건 평가, 문서·페이지 | 이동윤·김은진 |
| `W5-G05` AI Schema | 구조화·위험·근거·Fallback 요청·응답과 Event 매핑 확정 | `CONTRACT_READY_RUNTIME_MAPPING_PENDING` | Schema Test, Backend Mapper·Event 표 | 이동윤·최지용 |
| `W5-G06` Backend Gate | 공식 환경에서 Test·Migration 통과 | `ENVIRONMENT_BLOCKED` | Python 3.13.13, pytest 집계, Migration Drift | 최지용·김은진 |
| `W5-G07` Backend–AI 최소 연결 | 증상 제출→AI 호출→검증→Event→DB 저장 1건 통과 | `NOT_READY` | HTTP·Schema·DB·추적 ID E2E | 최지용·이동윤 |
| `W5-G08` Web Gate | 기존 Test·Lint·Build 유지, Mock·Remote 경계 명시 | `PASS_CARRIED` | Test 113, Lint·TypeScript·Build | 한예나·김은진 |
| `W5-G09` Mobile Gate | Core·Customer·Technician Test와 APK Build 통과 | `SDK_PLATFORM_BLOCKED` | SDK·JDK·Gradle, Test 집계, APK | 양정현·김은진 |

## 3. 준비된 입력

- State Machine `1.0.0 / TEAM_APPROVED`
- Action 23개 Crosswalk와 공통 Code Registry
- OpenAPI 23개 Operation과 연결 Example
- 대표 제품 `WPUJAC104DWH`, 구독 `SYN-JAC104-002`, 문의 `DEMO-INQ-002`
- 출수량 저하와 공식 매뉴얼 REV.00 38쪽 근거
- Data 단위 Test·QA·Finalize 증거
- Web 공통 상태·Action·오류 표현과 Mock Repository 경계
- 발표 피드백의 구현·기술 부채·최종 발표 분류

## 4. 신규 구현 착수 규칙

| 작업 | 필수 선행 Gate | Gate 미충족 시 허용 범위 |
|---|---|---|
| `T-025` 기준선·책임 분리 비교 | `W5-G02`, `W5-G05` | 동일 Fixture 기반 인터페이스·비교 계획 작성 |
| `T-026` 소비자 연동 | `W5-G05`, `W5-G06`, `W5-G07` | AI 단독 Schema·Fixture Test 유지 |
| `T-027` 위험·사용 안내 분류 | `W5-G02`, `W5-G05` | 규칙 단위 Test와 금지 출력 Test |
| `T-028A` 제품·이력·근거 검색 | `W5-G03`, `W5-G04` | 저장된 평가 결과 분석만 허용 |
| `T-028B` `EvidenceCardDTO` 조립 | `W5-G02`, `W5-G04`, `T-028A` | 계약 Example·비노출 Test 작성 |
| `T-031` 근거 없음 Guard | `W5-G02`, `T-027`, `T-028A` | 규칙·계약 Test 우선 작성 |
| `T-032` 전체 Fallback | `W5-G05`, `W5-G06`, `W5-G07` | AI 내부 Timeout·1회 재시도까지만 인정 |
| Mobile 소비자 작업 | `W5-G09`와 대상 Backend Operation | DTO·UiState 단위 Test까지만 허용 |

## 5. Gate 완료 정의

Gate는 다음 여섯 항목이 함께 있을 때만 `PASS`로 바꾼다.

1. 검증 Commit 전체 SHA
2. Runtime·DB·도구 Version
3. 재현 명령
4. PASS·FAIL 집계와 Exit Code
5. 결과 파일·로그·Test 경로
6. Mock·미연동·후속 제외 범위

## 6. 진입 결정

계약·대표 Data·Web은 5주차 입력으로 사용할 수 있으나 Vector DB, Backend, Backend–AI, Mobile Gate가 열려 있다. 따라서 5주차는 **조건부 진입**하며 첫 작업은 `W5-G01`, `W5-G04`~`W5-G07`, `W5-G09` 해제다.

Gate와 독립적인 계약 Test·비교 계획·안전 규칙 Test는 병행할 수 있지만, 전체 Runtime 또는 E2E 완료로 승격하지 않는다.

# 5주차 진입 조건

> 기준일: **2026-08-10 KST**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 계획 기준 Commit: `main@dd172c796bfeede07a9f72094b5d044b67855381`
> 문서 상태: **PM_BASELINE_CANDIDATE**
> 운영 판정: **WBS_WEEK5_ENTRY / GATED_EXECUTION**
> 지침서 호환 표기: **CONDITIONAL_ENTRY / UNBLOCK_FIRST · W5-G01~G09**

## 1. 진입 원칙

1. 현행 WBS의 일정·Task ID·범위를 변경하지 않는다.
2. 5주차 필수 범위는 환경·계약 Gate, Multi-Agent 핵심 Runtime, Backend↔AI 최소 수직 연결, WBS 5주차 잔여 Runtime, Web·Mobile 소비 준비다.
3. 전체 고객→상담사→기사→고객 E2E, 전체 회귀와 최종 Feature Complete는 6~7주차 범위다.
4. 6~7주차 업무는 5주차 필수 Gate가 모두 PASS한 경우에만 **조기 완료 조건부 업무**로 착수한다.
5. 조건부 업무의 미착수·미완료는 5주차 실패로 계산하지 않는다.
6. 과거 PASS, Mock, Fixture 전용 결과와 현재 Commit의 실제 Runtime 결과를 구분한다.
7. Gate가 실패하면 담당자·해제 조건·목표일을 기록하고 후속 작업을 완료로 표시하지 않는다.

## 2. 5주차 필수 진입 Gate

| Gate | 필수 확인 조건 | 초기 상태 | PASS 증거 | 책임 |
|---|---|---|---|---|
| `W5-G01` 계획 기준선 | WBS·Scope·Backlog·Dependency·Owner·Exit가 같은 일정과 범위 | `PM_BASELINE_CANDIDATE` | 문서 정합성 검사, 기준 Commit | 윤승혁 |
| `W5-G02` 계약 | State·Code·OpenAPI·Example·Crosswalk 검사 | `REVALIDATION_REQUIRED` | Validator·Contract Test Exit 0 | 윤승혁·최지용 |
| `W5-G03` Data·Seed | 대표 제품·구독·문의·근거와 Backend Crosswalk 일치 | `REVALIDATION_REQUIRED` | Data Test·QA·Seed·Hash | 김은진·최지용 |
| `W5-G04` AI·Vector 검색 | 실제 LLM, 팀 DB pgvector, 제품·세대 Filter | `REVALIDATION_REQUIRED` | 검색·평가·LLM 결과 | 이동윤·김은진 |
| `W5-G05` AI Runtime·Mapping | 핵심 Agent·상담 요약 최소 Runtime과 AI Schema–State Event Mapping | `REVALIDATION_REQUIRED` | Agent·Schema·Mapping Test | 이동윤·최지용·김은진 |
| `W5-G06` Backend·DB | Python·Django·PostgreSQL·Migration·Seed와 WBS 대상 회귀 | `REVALIDATION_REQUIRED` | Version, Migration Drift 0, pytest | 최지용·김은진 |
| `W5-G07` Backend↔AI | 실제 HTTP→Schema→Event→DB→`correlation_id` | `TARGET_8_11` | 최소 수직 Integration Test | 최지용·이동윤·김은진 |
| `W5-G08` Web 소비 준비 | WBS 대상 API의 Remote 경계와 Test·Build | `REVALIDATION_REQUIRED` | Test·Lint·TypeScript·Build·Remote 증거 | 한예나·김은진 |
| `W5-G09` Mobile 소비 준비 | SDK·JDK·Gradle과 WBS 대상 고객·기사 Remote 경계 | `REVALIDATION_REQUIRED` | Version, Test, APK·Remote 증거 | 양정현·김은진 |
| `W5-G10` 5주차 잔여 Runtime | WBS 5-2와 8/10~8/14 Task의 소비 가능한 결과 | `TARGET_8_14` | Runtime·DB·State·Test·DTO 증거 | 영역 담당자 |
| `W5-G11` 5주차 Exit | 필수 Gate 결과와 잔여 Blocker·6~7주차 인계 확정 | `TARGET_8_14` | `week5-exit-gate.md` | 윤승혁·김은진 |

## 3. 조기 완료 조건부 Gate

| Gate | 착수 조건 | 미착수 시 처리 | 책임 |
|---|---|---|---|
| `W5-C01` 대표 E2E | `W5-G01`~`W5-G10` PASS와 고정 Fixture 준비 | 현행 WBS의 `T-046` 일정 유지 | 전 팀원·김은진 |
| `W5-C02` 전체 회귀 | 대표 E2E 후보 Commit과 영역별 필수 Test PASS | 현행 WBS의 `T-047`~`T-051` 일정 유지 | 김은진·영역 담당자 |
| `W5-C03` Feature Complete | 대표 E2E·전체 회귀·차단 결함 0 | 5주차 Exit와 분리해 `NOT_ASSESSED` | 윤승혁 |

## 4. 준비된 고정 입력

- 대표 제품: `WPUJAC104DWH`
- 대표 구독: `SYN-JAC104-002`
- 대표 문의: `DEMO-INQ-002`
- 대표 증상: `출수량 저하`
- 공식 근거: `WPU-JAC104D·WPU-JCC104D REV.00` 38쪽
- State Machine: 승인된 YAML 계약과 Action Crosswalk

고정 입력은 현재 기준 Commit에서 재검증한 뒤 사용한다. 과거 PASS만으로 현재 PASS를 기록하지 않는다.

## 5. 일자별 필수 경계

| 날짜 | 필수 출력 | 후속 소비 |
|---|---|---|
| 8/10 | 계획 기준본, 동일 Commit Gate, Agent 책임 계약, WBS 당일 Runtime | Backend↔AI와 소비자 Adapter 준비 |
| 8/11 | 실제 LLM·Vector, Backend↔AI 최소 수직 연결 | 위험·근거·Fallback과 공개 DTO |
| 8/12 | 추가 질문·위험 분류·검색, WBS 대상 고객·상담 소비 준비 | 8/13 잔여 Runtime |
| 8/13 | 제품·세대 검색, EvidenceCardDTO, 추적성, WBS 대상 Remote 경계 | 5주차 Exit 증거 취합 |
| 8/14 | 필수 범위 회귀, 잔여 Blocker와 6~7주차 인계 확정 | WBS 5주차 Exit 판정 |

대표 E2E·전체 회귀·Feature Complete는 위 필수 경계가 조기에 닫힌 경우에만 별도 조건부 Gate로 실행한다.

## 6. Gate 완료 정의

Gate는 다음 항목이 모두 있을 때만 `PASS`다.

1. 검증 Commit 전체 SHA
2. Runtime·DB·도구 Version
3. 재현 명령과 Exit Code
4. PASS·FAIL·SKIP 집계
5. 결과 파일·로그·Test 경로
6. Mock·미연동·제외 범위
7. 다음 소비자가 사용할 수 있는 산출물 또는 정확한 Blocker

## 7. 진입 결정

5주차는 **WBS 5주차 필수 범위 완료**를 목표로 진입한다. 최종 판정은 `WBS_WEEK5_PASS`, `WBS_WEEK5_CONDITIONAL_PASS`, `WBS_WEEK5_HOLD` 중 하나로 기록한다. Feature Complete 여부는 조기 완료 조건부 Gate가 실제 실행된 경우에만 별도로 판정한다.

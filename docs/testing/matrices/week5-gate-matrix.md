# 5주차 Gate Matrix

> 검증일: **2026-08-11 KST**
> 검증 Branch: `eunjin`
> 검증 Commit: `88148c97ba727c62fc520104aa20a796d089d10b`
> 실행 전 작업 트리: **CLEAN**
> 종료까지 HEAD 변경: **없음**
> 현재 판정: **LOCAL_BASELINE_PASS · WBS_WEEK5_HOLD**
> 상세 결과: [5주차 현재 HEAD 서비스 회귀 기준선](../results/week5-service-regression-baseline.md)

PM 공식 기준선은 `main@92b0674cd1a3376a2c058715cd5ef32222125755`를
유지한다. 이 Matrix의 `88148c9...`는 김은진 Branch의 현재 QA 후보 기준선이며
PM 승인이나 Week5 Exit 승격을 의미하지 않는다.

## 1. 상태 판정 규칙

| 상태 | 의미 |
| --- | --- |
| `PASS` | 현재 Commit에서 Gate의 필수 Runtime·환경·테스트·소비 증거가 모두 확인됨 |
| `PASS_LOCAL` | 로컬 필수 검사는 통과했지만 원격 자동화나 실연동 증거가 남음 |
| `BLOCKED` | 일부 증거는 통과했지만 필수 외부 환경·실연동·승인 또는 Runtime 증거가 없어 Gate를 닫을 수 없음 |
| `ENVIRONMENT_BLOCKED` | 승인된 SDK·DB·외부 서비스 환경이 없어 실행하지 못함 |
| `FAIL` | 현재 Commit의 코드·계약·데이터 검증이 Assertion 또는 Runtime 오류로 실패함 |
| `NOT_RUN` | 선행 Gate 미충족 또는 종료일 미도래로 판정을 실행하지 않음 |

부분 통과 수치는 진행 상황을 보여 주는 참고 증거일 뿐 `PASS`로 승격하지 않는다.

## 2. 필수 Gate Matrix

| Gate | 필수 완료 경계 | 현재 증거 | 상태 | 해제 조건 | 담당 |
| --- | --- | --- | --- | --- | --- |
| `W5-G01` 계획 기준선 | Scope·Backlog·Dependency·Owner·Exit가 승인 SHA와 일치 | PM 공식 `92b0674...`, QA 후보 `88148c9...`로 구분됨 | `BLOCKED` | 윤승혁이 최종 후보 SHA와 Planning 상태 승인 | 윤승혁·김은진 |
| `W5-G02` 계약 | OpenAPI·Code·Example·State·Crosswalk Validator와 Root Contract Test Exit 0 | Validator 6종 PASS, Root Contract `38 passed`, OpenAPI 33 Operation, Action 23개 | `PASS_LOCAL` | Contract CI Commit·Push·원격 Run PASS | 윤승혁·최지용·김은진 |
| `W5-G03` Data·Seed | 대표 입력·Hash·Fixture·Seed·Crosswalk의 현재 Commit 검증 | Data `76 passed`, QA 오류 0·경고 0, 48 files·740 records, 대표 Data E2E 17/17, Drift 0 | `BLOCKED` | 독립 PostgreSQL DB에서 Seed Replay와 기대 건수 확인 | 김은진·최지용 |
| `W5-G04` AI·Vector 검색 | 실제 팀 DB pgvector·제품/세대 Filter·외부 LLM 구분 | AI Unit `142 passed`, pgvector `1 skipped`, 실제 Provider 미실행 | `BLOCKED` | 승인 DSN·Embedding Revision으로 실제 검색, Provider 실행 여부 확정 | 이동윤·김은진 |
| `W5-G05` AI Runtime·Mapping | 핵심 Runtime·상담 요약·Schema–State Mapping·Fallback | 단일 Workflow Unit·Root 계약·Safety 기준선 PASS, 목표 Multi-Agent Runtime 없음 | `BLOCKED` | 역할별 Routing·Handoff·Hop, 실제 LLM·Mapping·Fallback 결과 | 이동윤·최지용·김은진 |
| `W5-G06` Backend·DB | Python·Django·Migration·전체 회귀·PostgreSQL·Seed | 공식 `--full` PASS, `966 passed, 17 skipped`, Migration Drift 0 | `BLOCKED` | 독립 PostgreSQL에서 Migration·Seed·Row Lock·Composite FK 재검증 | 최지용·김은진 |
| `W5-G07` Backend↔AI | 실제 HTTP→Schema→Event→DB→`correlation_id` | Backend 전체 회귀에서 Live HTTP 1건 Skip, Root Live 통합 Test 없음 | `BLOCKED` | 정상·오류·Timeout·Fallback·멱등·충돌을 실제 HTTP·DB로 통과 | 최지용·이동윤·김은진 |
| `W5-G08` Web 소비 준비 | WBS 대상 Remote 경계·Test·Lint·Build·실제 Smoke | Lint PASS, 기본 병렬 Harness 실패, 단일 worker `137 passed`, Build PASS·133 modules | `BLOCKED` | 실제 Backend Remote 응답·오류·409 입력 보존·Correlation Smoke | 한예나·최지용·김은진 |
| `W5-G09` Mobile 소비 준비 | SDK·JDK·Gradle·Unit·APK·Remote Smoke | Mobile 병합 Commit은 현재 HEAD에 포함. Java 26.0.1, SDK 환경·`local.properties`·ADB 없음 | `ENVIRONMENT_BLOCKED` | 승인 SDK/JDK에서 Unit·APK·고객/기사 Remote Smoke 재현 | 양정현·최지용·김은진 |
| `W5-G10` 5주차 잔여 Runtime | WBS 대상 Operation별 Runtime·DB·State·소비 가능 DTO | Action 23개 중 Runtime 12, OpenAPI-only 7, Deferred 4; Backend 계약 의미 수정 요청 유지 | `BLOCKED` | PostgreSQL·권한·Guard·멱등·DTO 증거와 소비자 재검토 | 영역 담당자 |
| `W5-G11` 5주차 Exit | Gate 결과·잔여 Blocker·6~7주차 인계 승인 | 8/11 QA 후보 기준선이며 PM Exit 미실행 | `NOT_RUN` | 8/14 동일 Commit 증거 취합 후 PM 판정 | 윤승혁·김은진 |

## 3. 현재 검증 수치

| 영역 | 현재 Commit 실행 결과 | 판정 제한 |
| --- | --- | --- |
| Contract | Validator 6종 PASS, Root `38 passed` | 원격 Workflow `REMOTE_NOT_RUN` |
| Root Safety | `4 passed` | Runtime Safety·E2E가 아닌 계약 교차 검증 |
| Data | `76 passed`, QA 오류 0·경고 0, Drift 0 | 실제 PostgreSQL Seed Replay 미실행 |
| Backend | 환경·Django Check·Migration Drift PASS, `966 passed, 17 skipped` | 17건은 PostgreSQL·Live HTTP 전용 또는 명시적 Team Role Test |
| PostgreSQL | `NOT_CONFIGURED`, `POSTGRES_DB` 미설정 | 연결·적용 Migration·Row Lock 재검증 불가 |
| AI | `142 passed, 3 warnings` | pgvector 1건 Skip, 외부 LLM·Multi-Agent·Backend Live 미검증 |
| Web | Lint PASS, 단일 worker `137 passed`, Build PASS | 기본 병렬 Harness는 15 worker timeout, 실제 Remote Smoke 미검증 |
| Mobile | 환경 존재 여부만 점검 | SDK·ADB·승인 JDK 없음 |
| Root Integration·E2E | 실행 Live Test 없음 | 골격 디렉터리 유지 |

## 4. Critical Blocker

| Blocker | 영향 Gate | 현재 원인 | 해제 증거 |
| --- | --- | --- | --- |
| `W5-B01` PM 기준 SHA 불일치 | G01·G11 | 공식 `92b0674...`, QA 후보 `88148c9...` | 최종 기준 SHA·상태 승인 |
| `W5-B02` PostgreSQL 미구성 | G03·G06·G10 | `POSTGRES_DB` 미설정 | 독립 QA DB 식별, `--postgresql`, Seed Replay, PostgreSQL 표적 Test |
| `W5-B03` 팀 pgvector·LLM 미검증 | G04·G05·G07 | 승인 DSN·실제 Provider 실행 증거 없음 | 검색 Case·Filter·금지 Hit·LLM Schema/Timeout 결과 |
| `W5-B04` Backend↔AI 수직 연결 없음 | G07 | 실제 HTTP·DB Integration Test 부재 | 동일 Inquiry의 HTTP·Schema·Event·DB·Trace 결과 |
| `W5-B05` Public Evidence 계약 미완성 | G05·G07·G08 | EvidenceCard·Source·Verification·Path가 빈 객체 | 공개 Allowlist·비노출 Test·Backend DTO·Web 소비 결과 |
| `W5-B06` Web·Mobile 실제 소비 미확인 | G08·G09 | Web Remote Smoke 없음, Mobile은 병합됐으나 QA 환경 SDK·Remote Route 없음 | 동일 Commit Remote Smoke·Build·APK |
| `W5-B07` Contract CI 원격 미검증 | G02 | Workflow·자체 Test는 Local PASS, Commit·Push 없음 | Branch 또는 PR Run URL과 7개 Step PASS |

## 5. 현재 Exit 해석

- `WBS_WEEK5_PASS`: 불가
- `WBS_WEEK5_CONDITIONAL_PASS`: 불가 — 핵심 최소 수직 연결 `W5-G07`이 아직 `BLOCKED`
- `WBS_WEEK5_HOLD`: 현재 적용

`HOLD`는 8월 11일 QA 후보 기준선의 상태이며 주간 종료 실패 판정이 아니다.
G07 최소 수직 연결과 PostgreSQL·Vector 실증이 닫히기 전에는 Local Unit·계약·
Mock 결과를 통합 완료로 승격하지 않는다.

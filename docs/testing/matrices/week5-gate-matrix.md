# 5주차 Gate Matrix

> 검증일: **2026-08-10 KST**
> 검증 구간: **2026-08-10 21:25~21:34 KST**
> 검증 Branch: `eunjin`
> 검증 Commit: `4d955116c00f715e1ba9e465104a381b858996b9`
> 실행 전 작업 트리: **CLEAN**
> 현재 판정: **WBS_WEEK5_HOLD**
> 상세 결과: [5주차 현재 HEAD 통합 QA 보고서](../results/week5-entry-gate-result.md)

## 1. 상태 판정 규칙

| 상태 | 의미 |
| --- | --- |
| `PASS` | 현재 Commit에서 Gate의 필수 Runtime·환경·테스트·소비 증거가 모두 확인됨 |
| `BLOCKED` | 일부 증거는 통과했지만 필수 외부 환경·실연동·승인 또는 Runtime 증거가 없어 Gate를 닫을 수 없음 |
| `FAIL` | 현재 Commit의 코드·계약·데이터 검증이 Assertion 또는 Runtime 오류로 실패함 |
| `NOT_RUN` | 선행 Gate 미충족 또는 종료일 미도래로 판정을 실행하지 않음 |

부분 통과 수치는 진행 상황을 보여 주는 참고 증거일 뿐 `PASS`로 승격하지 않는다.

## 2. 필수 Gate Matrix

| Gate | 필수 완료 경계 | 현재 증거 | 상태 | 해제 조건 | 담당 |
| --- | --- | --- | --- | --- | --- |
| `W5-G01` 계획 기준선 | Scope·Backlog·Dependency·Owner·Exit가 현재 기준 SHA와 일치 | 본 Matrix와 통합 QA 보고서는 `4d955116...`에 고정했으나 Planning 문서는 `dd172c7...`의 `PM_BASELINE_CANDIDATE` 유지 | `BLOCKED` | 윤승혁이 현재 기준 SHA와 Planning 상태를 승인·갱신 | 윤승혁·김은진 |
| `W5-G02` 계약 | OpenAPI·Code·Example·State·Crosswalk Validator와 Root Contract Test Exit 0 | Validator 5종 PASS, Root Contract `12 passed`, OpenAPI 33 Operation, Action 23개 | `PASS` | 없음 | 윤승혁·최지용·김은진 |
| `W5-G03` Data·Seed | 대표 입력·Hash·Fixture·Seed·Crosswalk의 현재 Commit 검증 | Data `69 passed`, QA 오류 0·경고 0, 48 files·740 records, 대표 E2E invariant 17/17, Drift 0, Fixture 367건 | `BLOCKED` | 명시한 독립 PostgreSQL DB에서 Backend Seed Replay와 기대 건수 확인 | 김은진·최지용 |
| `W5-G04` AI·Vector 검색 | 실제 팀 DB pgvector·제품/세대 Filter·외부 LLM 구분 | AI Unit `127 passed`, pgvector Integration `1 skipped`; 실제 Provider 호출 미실행 | `BLOCKED` | 승인된 DSN·Embedding Revision으로 pgvector 검색·평가, 실제 LLM 또는 `EXTERNAL_LLM_NOT_VERIFIED` 증거 확정 | 이동윤·김은진 |
| `W5-G05` AI Runtime·Mapping | 핵심 Runtime·상담 요약·Schema–State Mapping·Fallback | AI 단위 Schema·Safety·상담 요약 기준선은 통과, Multi-Agent 문서는 Target Contract 초안 | `BLOCKED` | 실제 Routing·Mapping·Timeout·Fallback 실행 결과와 Backend 소비 Schema 확정 | 이동윤·최지용·김은진 |
| `W5-G06` Backend·DB | Python·Django·Migration·전체 회귀·PostgreSQL·Seed | 공식 `--full` Gate PASS, `933 passed, 15 skipped`, Migration Drift 0; `--postgresql`은 `POSTGRES_DB` 미설정으로 실패 | `BLOCKED` | 독립 PostgreSQL DB를 명시해 Migration 적용 상태, Seed, Row Lock·Composite FK·pgvector 의미론 재검증 | 최지용·김은진 |
| `W5-G07` Backend↔AI | 실제 HTTP→Schema→Event→DB→`correlation_id` | Root `tests/integration/backend-ai/**`에 실행 테스트 없음, 실제 수직 연결 미실행 | `BLOCKED` | 정상·Schema 오류·5xx·Timeout·Fallback·멱등·State 충돌을 실제 HTTP와 DB에서 통과 | 최지용·이동윤·김은진 |
| `W5-G08` Web 소비 준비 | WBS 대상 Remote 경계·Test·Lint·Build·실제 Smoke | Lint PASS, 기본 Test `137 passed`, 단일 worker Test `137 passed`, Build PASS·133 modules; 실제 Backend Remote Smoke 없음 | `BLOCKED` | 목록·상세·상담·방문 Operation의 실제 응답·오류·409 입력 보존·Correlation Smoke | 한예나·최지용·김은진 |
| `W5-G09` Mobile 소비 준비 | SDK·JDK·Gradle·Unit·APK·Remote Smoke | Wrapper 존재, Java 26.0.1; Android SDK 환경값·`local.properties`·ADB 없음. `origin/jeonghyun@eb78910...`은 현재 HEAD에 미포함 | `BLOCKED` | Mobile 변경 병합 후 승인된 SDK/JDK에서 Unit·APK·고객/기사 Remote Smoke 실행 | 양정현·최지용·김은진 |
| `W5-G10` 5주차 잔여 Runtime | WBS 대상 Operation별 Runtime·DB·State·소비 가능 DTO | 전체 Action 23개 중 Runtime 12, OpenAPI-only 7, Deferred 4; 고객 문의 조회·추가답변 Runtime은 추가됨 | `BLOCKED` | WBS 5주차 대상 Operation을 별도 매핑하고 각 Operation의 PostgreSQL·권한·멱등·DTO 증거 확정 | 영역 담당자 |
| `W5-G11` 5주차 Exit | Gate 결과·잔여 Blocker·6~7주차 인계 승인 | 본 Matrix는 8/10 중간 기준선이며 PM Exit 판정은 미실행 | `NOT_RUN` | 8/14 동일 Commit 증거 취합 후 PM 판정 | 윤승혁·김은진 |

## 3. 현재 검증 수치

| 영역 | 현재 Commit 실행 결과 | 판정 제한 |
| --- | --- | --- |
| Contract | Validator 5종 PASS, Root `12 passed` | Public Evidence Schema·Path는 빈 객체 |
| Data | `69 passed`, QA 오류 0·경고 0, Drift 0 | 실제 PostgreSQL Seed Replay 미실행 |
| Backend | 환경·Django Check·Migration Drift PASS, `933 passed, 15 skipped` | 15건은 PostgreSQL 전용 또는 명시적 Team Role Test |
| PostgreSQL | `NOT_CONFIGURED`, `POSTGRES_DB` 미설정 | 연결·적용 Migration·Row Lock 재검증 불가 |
| AI | `127 passed, 3 warnings` | pgvector 1건 Skip, 외부 LLM·Backend 실제 HTTP 미검증 |
| Web | Lint PASS, `137 passed`, Build PASS | 실제 Remote Smoke 미검증 |
| Mobile | 환경 존재 여부만 점검 | SDK·ADB 없음, 현재 HEAD에 5주차 Mobile 변경 미통합 |
| Root Integration·E2E·Safety | 실행 테스트 없음 | 골격 디렉터리만 존재 |

## 4. Critical Blocker

| Blocker | 영향 Gate | 현재 원인 | 해제 증거 |
| --- | --- | --- | --- |
| `W5-B01` PM 기준 SHA 불일치 | G01·G11 | Planning은 `dd172c7...`, QA는 `4d955116...` | Planning 기준 SHA·상태 갱신 Commit |
| `W5-B02` PostgreSQL 미구성 | G03·G06·G10 | `POSTGRES_DB` 미설정 | 독립 QA DB 식별, `--postgresql`, Seed Replay, PostgreSQL 표적 Test |
| `W5-B03` 팀 pgvector·LLM 미검증 | G04·G05·G07 | 승인 DSN·실제 Provider 실행 증거 없음 | 검색 Case·Filter·금지 Hit·LLM Schema/Timeout 결과 |
| `W5-B04` Backend↔AI 수직 연결 없음 | G07 | 실제 HTTP·DB Integration Test 부재 | 동일 Inquiry의 HTTP·Schema·Event·DB·Trace 결과 |
| `W5-B05` Public Evidence 계약 미완성 | G05·G07·G08 | EvidenceCard·Source·Verification·Path가 빈 객체 | 공개 Allowlist·비노출 Test·Backend DTO·Web 소비 결과 |
| `W5-B06` Web·Mobile 실제 소비 미확인 | G08·G09 | Web Remote Smoke 없음, Mobile 미병합·SDK 없음 | 동일 Commit Remote Smoke·Build·APK |

## 5. 현재 Exit 해석

- `WBS_WEEK5_PASS`: 불가
- `WBS_WEEK5_CONDITIONAL_PASS`: 불가 — 핵심 최소 수직 연결 `W5-G07`이 아직 `BLOCKED`
- `WBS_WEEK5_HOLD`: 현재 적용

`HOLD`는 8월 10일 중간 기준선의 상태이며 주간 종료 실패 판정이 아니다. G07 최소 수직 연결과 PostgreSQL·Vector 실증이 닫히기 전에는 화면·문서·Mock 결과를 통합 완료로 승격하지 않는다.

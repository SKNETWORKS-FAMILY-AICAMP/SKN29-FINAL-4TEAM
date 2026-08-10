# 4주차 → 5주차 통합 인계

> 재기준일: **2026-08-10 KST**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 계획 기준 Commit: `main@dd172c796bfeede07a9f72094b5d044b67855381`
> 5주차 진입: **WBS_WEEK5_ENTRY / GATED_EXECUTION**
> 종료 목표: **WBS 5주차 필수 Scope Exit 판정**
> 용도: **2026-08-10 팀 공지용 5주차 기준본**

## 1. 인계 원칙

4주차 산출물은 5주차 입력 후보이며 현재 Commit에서 재검증하기 전까지 PASS를 승계하지 않는다. 5주차에는 환경·계약 Gate, Multi-Agent 핵심 Runtime, Backend↔AI 최소 수직 연결, WBS 잔여 Runtime과 Web·Mobile 소비 준비를 우선한다.

전체 E2E·전체 회귀·Feature Complete는 현행 WBS의 6~7주차 범위다. 5주차 필수 Gate가 모두 PASS하면 조기 착수할 수 있지만, 미착수·미완료를 5주차 실패로 계산하지 않는다.

## 2. 담당자별 첫 출력과 5주차 Exit 증거

| 담당자 | 첫 출력 | 5주차 필수 출력 | 8월 14일 Exit 증거 |
|---|---|---|---|
| 윤승혁 | Scope·Dependency·Owner·Exit 기준본 | 계약·일정·Blocker Gate 운영 | WBS 5주차 Exit 판정·6~7주차 인계 |
| 최지용 | Backend·DB Gate | WBS 잔여 Runtime·Backend↔AI·Evidence DTO | WBS 대상 Test·PostgreSQL·Runtime Status |
| 이동윤 | AI·RAG·LLM·Vector Gate | 핵심 Agent·상담 요약 최소 Runtime·실제 LLM·팀 DB 검색·Safety/Fallback | AI 필수 Test·아키텍처·현재 결과 |
| 한예나 | Web Gate·Remote 기반 | 제공된 WBS 대상 API의 Web 소비 | Test·Lint·TypeScript·Build·Remote Smoke |
| 양정현 | Mobile Gate·API 대응표 | WBS 대상 고객·기사 Remote 소비 | Unit·UI·Build·APK·Remote 결과 |
| 김은진 | 동일 Commit Gate·대표 Seed 판정 | Backend↔AI·Vector·핵심 Safety 검증과 Evidence 집계 | QA 기준선·Blocker·인계 증거 |

## 3. 필수 인계 순서

| 선행 출력 | 후속 소비 | 전달 조건 |
|---|---|---|
| 계약·Data·환경 Gate | 전 영역 Runtime | 현재 Commit 명령·Exit Code·증거 경로 |
| 케어·문진·문의 Runtime | Web·Mobile Remote | DTO·권한·오류·State Test PASS |
| Agent 책임·Schema·Event Mapping | Backend AI Client·Mapper | 정상·오류·Fallback Mapping Test PASS |
| 실제 LLM·팀 DB Vector | 위험·근거·Fallback | 모델·세대 Filter·공식 페이지·Schema PASS |
| Backend↔AI 최소 HTTP | Evidence DTO·Client 소비 | HTTP·Event·DB·`correlation_id` PASS |
| 공개 DTO | Web·Mobile Mapper | 내부 경로·원문·내부 ID 비노출 PASS |
| 영역별 필수 결과 | WBS 5주차 Exit | 담당자·목표일·해제 조건을 포함한 증거 |

## 4. 열린 Gate 관리

| Gate | 초기 상태 | 해제 조건 | 목표일 |
|---|---|---|---|
| 계획 기준선 | `PM_BASELINE_CANDIDATE` | Planning 문서 정합성 검토·Commit | 8/10 |
| 계약·Data | `REVALIDATION_REQUIRED` | Validator·Data QA 같은 Commit PASS | 8/10 |
| Backend·PostgreSQL | `REVALIDATION_REQUIRED` | WBS 대상 Migration·Seed·Test PASS | 8/10~8/14 |
| AI·LLM·Vector | `REVALIDATION_REQUIRED` | 핵심 Agent·실제 Provider·팀 DB 검색 PASS | 8/11~8/13 |
| Web·Mobile 소비 준비 | `REVALIDATION_REQUIRED` | 제공 Runtime의 Remote·Build 경계 PASS | Runtime 제공 당일 |
| Backend↔AI | `NOT_RUN` | 실제 HTTP·Event·DB·Trace PASS | 8/11 |
| WBS 잔여 Runtime | `NOT_RUN` | 대상별 Runtime·Test 또는 정확한 Blocker | 8/14 |
| 5주차 Exit | `NOT_ASSESSED` | 필수 Gate 판정·6~7주차 인계 | 8/14 |

## 5. 조기 완료 조건부 인계

| 조건부 범위 | 착수 조건 | 미착수 시 인계 |
|---|---|---|
| 상담 요약 저장·확정 통합 고도화와 기사 브리핑 Formatter/Prototype | 상담 요약 최소 Runtime과 AI·Backend 필수 Gate PASS | 6주차 `T-030A`~`T-030C` |
| 기사 조치·고객 후속 완료 | 상담·방문 선행 Runtime PASS | 6주차 `T-043`·`T-044`·`T-055` |
| 대표 전체 E2E | 5주차 필수 Gate 전체 PASS | 7주차 `T-046` |
| 전체 회귀 | 대표 E2E 후보 Commit | 7주차 `T-047`~`T-051` |
| Feature Complete | 전체 E2E·회귀 PASS | 7주차 결과 이후 판정 |

## 6. 인수 회신 형식

```text
owner=<이름>
scope_id=<W5-Sxx | W5-Cxx>
baseline_commit=<전체 SHA>
output=<소비 가능한 산출물>
status=PASS | FAIL | BLOCKED | NOT_RUN
commands=<재현 명령>
exit_codes=<명령별 Exit Code>
evidence=<Test·Log·Report 경로>
consumer=<다음 소비자>
remaining_blocker=<없으면 NONE>
target_at=<YYYY-MM-DD HH:mm KST>
```

회신·실행 증거가 없는 작업은 `진행 중` 이상으로 승격하지 않는다. 조건부 업무는 반드시 `W5-Cxx`로 표시한다.

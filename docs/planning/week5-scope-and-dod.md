# 5주차 Scope 및 Definition of Done

> 기준일: **2026-08-10 KST**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 기준 Commit: `main@dd172c796bfeede07a9f72094b5d044b67855381`
> 상태: **PM_BASELINE_CANDIDATE**

## 1. 범위 원칙

1. 이 문서는 현행 WBS를 설명하며 WBS 일정·Task ID·범위를 변경하지 않는다.
2. 5주차 필수 범위는 WBS의 환경·계약·최소 수직 연결과 8/10~8/14 잔여 Runtime이다.
3. 전체 E2E·전체 회귀·Feature Complete는 6~7주차 또는 조기 완료 조건부 범위다.
4. 조건부 범위를 수행하지 못해도 5주차 필수 DoD가 충족되면 5주차 실패로 판정하지 않는다.
5. 완료 증거는 같은 Commit의 명령·Exit Code·Test·Runtime·DB·로그 경로로 남긴다.

## 2. 5주차 필수 Scope

| Scope ID | 필수 산출물 | WBS 근거 | 주관·협업 | 목표일 | Definition of Done | 완료 증거 |
|---|---|---|---|---|---|---|
| `W5-S01` | 계획 기준선 | WBS 5-2 순서 1 | 윤승혁·김은진 | 8/10 | Scope·Backlog·Dependency·Owner·Exit가 같은 일정과 범위를 가리킨다. | 문서 Diff·정합성 검사·기준 SHA |
| `W5-S02` | 동일 Commit Gate | WBS 5-2 순서 2 | 김은진·전 영역 | 8/10 | 계약·Data·Backend·AI·Web·Mobile 결과가 같은 SHA에서 PASS·FAIL·NOT_RUN으로 기록된다. | 명령·Exit Code·결과 경로 |
| `W5-S03` | 핵심 Agent Runtime·상담 요약 최소 출력과 구조 비교 | `T-025`, `T-026`, `T-027`, `T-030A` 선행 경계 | 이동윤·최지용·김은진 | 8/10~8/12 | 단일 RAG와 선택형 책임 분리 비교, 구조화·위험·검색·안내·검증 Routing·Fallback과 상담 요약 최소 Schema가 재현된다. | Agent·Routing·Handoff·상담 요약·Safety Test |
| `W5-S04` | 실제 LLM·팀 DB 검색 | `T-011`, `T-028A` | 이동윤·김은진 | 8/11~8/13 | 실제 Provider와 팀 pgvector에서 제품·세대·공식 근거 Filter가 검증된다. | 검색·평가·LLM Schema 결과 |
| `W5-S05` | Backend↔AI 최소 수직 연결 | WBS 5-2 순서 4 | 최지용·이동윤·김은진 | 8/11 | 실제 HTTP, Schema, Event, DB 저장과 `correlation_id`가 하나의 요청에서 연결된다. | Integration Test·DB·Trace |
| `W5-S06` | Backend 잔여 Runtime | `T-020`~`T-024`, WBS 5-2 순서 11 | 최지용·김은진 | 8/10~8/14 | WBS 날짜에 해당하는 케어·문진·문의·State·추적 경계가 URL·권한·DB·Test로 확인된다. | API·Unit·PostgreSQL·State Test |
| `W5-S07` | Evidence·Guard·Fallback | `T-028B`, `T-031`, `T-032` 재계획 | 최지용·이동윤·김은진 | 8/13~8/14 | 검증 근거만 공개 DTO로 조립되고 근거 없음·Timeout·검색 장애가 안전한 결과로 끝난다. | DTO·비노출·Fallback Test |
| `W5-S08` | Web 소비 준비 | `T-038`~`T-041`, WBS 5-2 순서 12 | 한예나·최지용·김은진 | Runtime 제공 당일 | 제공된 WBS 대상 DTO·State를 Remote Repository가 소비하며 Mock 자동 성공이 없다. | Test·Lint·TypeScript·Build·Remote Smoke |
| `W5-S09` | Mobile 소비 준비 | `T-033`, `T-034`, `T-037`, `T-042` | 양정현·최지용·김은진 | 8/10~8/14 | WBS 대상 고객·기사 경계가 DTO·UiState·행동·오류 처리로 연결된다. | Unit·UI·Build·APK·Remote 결과 |
| `W5-S10` | WBS 5주차 Exit | WBS 주차별 목표 | 윤승혁·김은진 | 8/14 | 필수 Scope별 판정, 미완료 담당자·목표일·해제 조건과 6~7주차 인계가 확정된다. | `week5-exit-gate.md` |

## 3. 조기 완료 조건부 Scope

| Scope ID | 조건부 산출물 | 현행 WBS 위치 | 착수 조건 | 미착수 시 처리 |
|---|---|---|---|---|
| `W5-C01` | 상담 요약 저장·확정 통합 고도화와 기사 브리핑 Formatter/Prototype | `T-030A`~`T-030C`, 6주차 | `W5-S03`~`W5-S07` PASS | 6주차 유지 |
| `W5-C02` | 기사 조치·고객 피드백·최종 종료 Operation | `T-043`, `T-044`, `T-055`, 6주차 | 상담·방문 선행 Runtime PASS | 6주차 유지 |
| `W5-C03` | 대표 전체 E2E | `T-046`, 7주차 | `W5-S01`~`W5-S09` PASS | 7주차 유지 |
| `W5-C04` | 전체 권한·상태·안전·성능 회귀 | `T-047`~`T-051`, 7주차 | `W5-C03` 후보 Commit | 7주차 유지 |
| `W5-C05` | Feature Complete 판정 | 7주차 통합·검증 결과 | `W5-C03`·`W5-C04` PASS | `NOT_ASSESSED` |

## 4. P1 및 제외 Scope

- 운영 Dashboard
- Graph DB
- Kubernetes 본 구현
- 제품 모델 대규모 확대
- 추가 Agent 무분별 확대
- 대규모 UI 재설계
- 실제 사내 시스템 API·실제 기사 자동 배정·결제·외부 알림

P1은 메모·설계 검토까지만 허용하며 5주차 P0 필수 인력과 시간을 사용하지 않는다.

## 5. 공통 DoD 증거 형식

```text
scope_id=<W5-Sxx | W5-Cxx>
owner=<담당자>
baseline_commit=<전체 SHA>
status=PASS | FAIL | BLOCKED | NOT_RUN
commands=<재현 명령>
exit_codes=<명령별 Exit Code>
evidence=<Test·Log·Report·PR 경로>
consumer=<다음 소비자>
remaining_blocker=<없으면 NONE>
target_at=<YYYY-MM-DD HH:mm KST>
```

설명 없는 `SKIP`, Mock 결과, 과거 Commit 결과는 PASS 증거로 사용하지 않는다.

## 6. 3.2 E2E Action 결정 기록

- 정상 14단계의 계약 미정 6개 Action을 P0 PM 승인안으로 결정했다.
- 미해결→재상담 2개 Action은 정상 14단계에서 제외하고 `T-055` 보조 시나리오 승인안으로 결정했다.
- 현행 WBS 일정은 변경하지 않는다.
- OpenAPI·Crosswalk·Code는 최지용, Contract Test는 김은진의 주관할 적용 대기이며 3.2 전체 상태는 `OWNER_APPLY_PENDING`이다.
- 결정 원본: `docs/decisions/week5-e2e-action-decision.md`
- Event–Operation 연결: `docs/decisions/week5-e2e-event-operation-matrix.md`
- 구현 인계: `docs/handoffs/week5-e2e-action-implementation-handoff.md`

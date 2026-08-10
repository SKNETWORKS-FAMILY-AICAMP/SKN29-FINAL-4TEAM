# 5주차 우선순위 Backlog

> 기준일: **2026-08-10 KST**
> 기간: **2026-08-10 ~ 2026-08-14**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 기준 Commit: `main@dd172c796bfeede07a9f72094b5d044b67855381`
> 운영 순서: **기준선 → Gate → 최소 수직 연결 → WBS 잔여 Runtime → 소비 준비 → Exit**

## 1. P0 필수 실행 순서

| 순서 | 마감 | 산출물 | WBS 근거 | 주관 | 선행 산출물 | 완료 증거 | 상태 |
|---:|---|---|---|---|---|---|---|
| 1 | 8/10 오전 | 계획·Scope·Dependency·Owner·Exit 기준본 | WBS 5-2 순서 1 | 윤승혁 | 현행 WBS·팀원별 지침서 | 문서 정합성 검사·변경 이력 | 검토 대기 |
| 2 | 8/10 오전 | 계약·Data·Backend·AI·Web·Mobile 동일 Commit Gate | WBS 5-2 순서 2 | 김은진·영역 담당 | 계획 기준 Commit | 명령·Exit Code·증거 경로 | 재검증 필요 |
| 3 | 8/10~8/11 | 단일 RAG 기준선·선택형 책임 분리 비교, 핵심 Agent와 상담 요약 최소 Runtime | `T-025`, `T-030A` 선행 경계 | 이동윤 | AI 계약·안전 규칙 | 비교 결과·Routing·Handoff·상담 요약 Test | 미판정 |
| 4 | 8/10~8/12 | 위험·사용 안내 분류와 추가 질문 소비 경계 | `T-027`, `T-026` | 이동윤·최지용 | 구조화 증상·State Event Mapping | 정상·위험·누락 정보 Test | 미판정 |
| 5 | 8/10~8/14 | 케어·문진·문의·State·추적 잔여 Runtime | `T-020`~`T-024`, WBS 5-2 순서 11 | 최지용 | Backend·계약 Gate | API·DB·권한·State·로그 Test | 미판정 |
| 6 | 8/11 | 실제 LLM·팀 DB pgvector와 Backend↔AI 실제 HTTP | WBS 5-2 순서 4, `T-011`, `T-025` | 이동윤·최지용 | Agent Schema·Backend Gate | HTTP·Schema·Event·DB·Trace | 미판정 |
| 7 | 8/12~8/13 | 제품·세대 기반 공식 검색 | `T-028A` | 이동윤·김은진 | 팀 DB·공식 Dataset | 검색·Filter·금지 자료 Test | 미판정 |
| 8 | 8/13~8/14 | `EvidenceCardDTO` 조립과 비노출 경계 | `T-028B` | 최지용·이동윤 | 검증된 검색 결과·레지스트리 | DTO·Lineage·비노출 Test | 미판정 |
| 9 | 8/13~8/14 | 근거 없음 Guard·Timeout·Fallback 잔여 경계 | WBS 5-2 순서 10, `T-031`, `T-032` | 이동윤·최지용 | 검색·HTTP 최소 연결 | 위험·근거 없음·장애 Test | 미판정 |
| 10 | Runtime 제공 당일 | Web·Mobile WBS 대상 Remote 소비 준비 | `T-033`, `T-034`, `T-037`, `T-040`~`T-042` | 한예나·양정현 | 소비 가능한 API·DTO | Mapper·UiState·화면·Build 증거 | 미판정 |
| 11 | 8/14 | WBS 5주차 Exit·잔여 Blocker·6~7주차 인계 | WBS 5주차 목표 | 윤승혁·김은진 | 1~10 결과 | Exit Gate·Owner Matrix·인계서 | 미판정 |

## 2. P0 필수 완료 경계

- 파일 존재가 아니라 Runtime·DB·State·Test·소비 가능한 DTO로 완료를 판정한다.
- Backend↔AI 최소 수직 연결은 실제 HTTP·Schema·Event·DB·`correlation_id`를 통과해야 한다.
- AI는 핵심 Agent, 실제 LLM, 팀 DB pgvector, 위험·근거 없음·Fallback 경계를 구분한다.
- Web·Mobile은 WBS 대상 Runtime이 열린 구간부터 Remote를 소비하며, 미제공 API를 Fake 성공으로 대체하지 않는다.
- 실패한 P0는 담당자·해제 조건·목표일을 기록하고 완료로 표시하지 않는다.

## 3. 조기 완료 조건부 Backlog

| 순서 | 산출물 | 현행 WBS 위치 | 착수 조건 | 미착수 시 처리 |
|---:|---|---|---|---|
| C1 | 상담 요약 저장·확정 통합 고도화와 기사 브리핑 Formatter/Prototype | `T-030A`~`T-030C`, 6주차 | 상담 요약 최소 Runtime과 필수 AI·Backend Gate PASS | 6주차 유지 |
| C2 | 기사 조치·고객 피드백·최종 종료 후반 Operation | `T-043`, `T-055`, 6주차 | 상담·방문 선행 Runtime PASS | 6주차 유지 |
| C3 | 고객→상담사→기사→고객 대표 E2E | `T-046`, 7주차 | 모든 5주차 필수 Gate PASS | 7주차 유지 |
| C4 | 전체 권한·상태·안전·성능 회귀 | `T-047`~`T-051`, 7주차 | 대표 E2E 후보 Commit | 7주차 유지 |
| C5 | Feature Complete 판정 | 7주차 통합 결과 이후 | C3·C4 PASS | `NOT_ASSESSED` |

조건부 Backlog의 미착수·미완료는 5주차 필수 실패로 계산하지 않는다.

## 4. P1 — 5주차 필수 범위 밖

| P1 항목 | 5주차 허용 범위 | 정식 착수 |
|---|---|---|
| 운영 Dashboard | 요구·지표 메모 | WBS 후속 일정 |
| Graph DB | 도입 판단 기록 | pgvector P0 완료 이후 |
| Kubernetes | 배포 설계 검토 | 배포 단계 |
| 제품 모델 대규모 확대 | 후보 목록 | MVP 완료 이후 |
| 추가 Agent 확대 | 필요성 기록 | 현재 Routing·Fallback 검증 이후 |
| 대규모 UI 재설계 | 결함 메모 | Remote 전환 이후 별도 승인 |

## 5. 주간 Exit 조건

1. `W5-G01`~`W5-G10`의 결과와 증거가 같은 기준 Commit에 연결된다.
2. 실제 LLM·Vector·Backend HTTP 최소 수직 경계가 통과하거나 정확한 `HOLD` 사유가 있다.
3. WBS 5주차 잔여 Runtime과 Web·Mobile 소비 준비의 PASS·BLOCKED 범위가 구분된다.
4. 모든 미완료 항목에 담당자·목표일·해제 조건이 있다.
5. 대표 E2E·전체 회귀·Feature Complete의 조건부 착수 여부와 6~7주차 유지 범위가 기록된다.

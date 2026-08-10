# 5주차 담당자·완료 증거 Matrix

> 기준일: **2026-08-10 KST**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 기준 Commit: `main@dd172c796bfeede07a9f72094b5d044b67855381`

## 1. 필수 Owner Matrix

| 담당자 | 5주차 필수 책임 | 선행 산출물 | 목표일 | 완료 증거 | 다음 소비자 |
|---|---|---|---|---|---|
| 윤승혁 | Scope·Dependency·Exit 정렬, 계약 Gate, WBS 5주차 Exit 판정 | 현행 WBS·팀원별 지침서 | 8/10, 8/14 | Planning 문서·Validator 결과·Exit 판정 | 전 팀원 |
| 최지용 | Backend·PostgreSQL Gate, 케어·문진·문의·State·추적 잔여 Runtime, Backend↔AI HTTP, Evidence DTO | 계약·Data·AI Schema | 8/10~8/14 | API·DB·권한·State·HTTP·DTO Test | AI·Web·Mobile·QA |
| 이동윤 | 단일 RAG/선택형 비교, 핵심 Agent와 상담 요약 최소 Runtime, 실제 LLM·팀 DB 검색, 위험·근거 없음·Fallback | AI 계약·공식 Data·Backend Adapter | 8/10~8/14 | Agent·Routing·상담 요약·Retrieval·LLM·Safety Test | Backend·Web·Mobile·QA |
| 한예나 | WBS 대상 상담사 Web Remote 소비 준비와 State·오류·Build 정합성 | 소비 가능한 Backend DTO·Operation | Runtime 제공 당일 | Test·Lint·TypeScript·Build·Remote Smoke | QA·PM |
| 양정현 | WBS 대상 고객·기사 Mobile Remote 소비 준비와 DTO·UiState·행동 정합성 | 소비 가능한 Backend DTO·Operation | 8/10~8/14 | Unit·UI·Build·APK·Remote 결과 | QA·PM |
| 김은진 | 동일 Commit Gate, 팀 DB·Vector 검증, 최소 Backend↔AI·Vector·핵심 Safety Test, Evidence 집계 | 영역별 재현 명령·Fixture | 매일, 8/14 | 명령·Exit Code·Test Report·Blocker Register | PM·전 팀원 |

## 2. 산출물별 승인 책임

| 산출물 | 작성·구현 | 검수 | 최종 판정 |
|---|---|---|---|
| Planning 기준본 | 윤승혁 | 김은진 | 윤승혁 |
| 계약·Crosswalk | 윤승혁·최지용 | 소비자 담당자 | 윤승혁 |
| Backend Runtime·DB | 최지용 | 김은진 | 최지용·윤승혁 |
| AI·RAG Runtime | 이동윤 | 김은진·최지용 | 이동윤·윤승혁 |
| Web Remote 소비 | 한예나 | 김은진·최지용 | 한예나·윤승혁 |
| Mobile Remote 소비 | 양정현 | 김은진·최지용 | 양정현·윤승혁 |
| 동일 Commit QA Evidence | 김은진 | 영역 담당자 | 김은진·윤승혁 |
| WBS 5주차 Exit | 전 영역 증거 제공 | 김은진 | 윤승혁 |

## 3. 조기 완료 조건부 Owner Matrix

| 조건부 업무 | 주관 | 협업·검수 | 착수 승인 | 미착수 시 일정 |
|---|---|---|---|---|
| 상담 요약 저장·확정 통합 고도화와 기사 브리핑 Formatter/Prototype | 이동윤 | 최지용·김은진 | 윤승혁 | 6주차 |
| 후반 방문·완료 Operation | 최지용 | 양정현·한예나·김은진 | 윤승혁 | 6주차 |
| 대표 E2E | 김은진 | 전 팀원 | 윤승혁 | 7주차 `T-046` |
| 전체 회귀 | 김은진 | 영역 담당자 | 윤승혁 | 7주차 `T-047`~`T-051` |
| Feature Complete | 윤승혁 | 김은진·전 팀원 | 윤승혁 | 7주차 결과 이후 |

## 4. Blocker 기록 규칙

모든 `BLOCKED` 항목은 다음 값을 가진다.

- 차단된 Scope ID 또는 WBS ID
- 실패한 산출물 경계
- 재현 명령과 Exit Code
- 해결 주관·협업자
- 해제 조건
- 목표일
- 다음 소비자 영향

담당자 이름만 적은 “확인 필요”는 Blocker 기록으로 인정하지 않는다.

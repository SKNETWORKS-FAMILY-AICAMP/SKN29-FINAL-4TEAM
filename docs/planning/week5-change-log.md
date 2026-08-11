# 5주차 Planning 변경 이력

> 최초 기준일: **2026-08-10 KST**
> WBS 기준: `docs/planning/md/WBS.md` v2.1
> 최초 기준 Commit: `main@dd172c796bfeede07a9f72094b5d044b67855381`

## 1. 기준본 변경 이력

| 변경 ID | 일시 | 변경자 | 대상 | 변경 내용 | WBS 영향 | 상태 |
|---|---|---|---|---|---|---|
| `W5-PLAN-001` | 2026-08-10 KST | 윤승혁 | 팀원별 5주차 지침서 | 3장은 WBS 5주차 필수, 5장은 6~7주차 조기 완료 조건부로 분리 | WBS 변경 없음 | 완료 |
| `W5-PLAN-002` | 2026-08-10 KST | 윤승혁 | Entry·Backlog·Dependency | 강제 E2E·Feature Complete Exit를 WBS 5주차 Exit와 분리 | WBS 변경 없음 | 완료 |
| `W5-PLAN-003` | 2026-08-10 KST | 윤승혁 | Scope·Owner·Exit | 필수 산출물·담당자·목표일·DoD·증거와 조건부 Gate 신설 | WBS 변경 없음 | 완료 |
| `W5-PLAN-004` | 2026-08-10 KST | 윤승혁 | 4→5주차 인계 | 필수 출력과 6~7주차 인계를 WBS 일정으로 재정렬 | WBS 변경 없음 | 완료 |
| `W5-PLAN-005` | 2026-08-10 KST | 윤승혁 | Issue Template | 필수·조건부·후속·P1 일정 범위 분류 추가 | WBS 변경 없음 | 완료 |
| `W5-PLAN-006` | 2026-08-11 KST | 윤승혁 | 3.6·3.7 Gate | Web·Mobile 사전 Gate, 일일 Integration 기록과 Blocker Register 착수 | WBS 변경 없음 | 진행 중 |
| `W5-PLAN-007` | 2026-08-11 KST | 윤승혁 | 3.3·3.4 Gate | Backend Runtime12 수정 회신, 후속 계약 결정, 소비자 재검증과 Contract CI 원격 PASS 반영 | WBS 변경 없음 | 승인 |

## 2. 기준본 확정 조건

현재 문서 상태는 `PM_BASELINE_CANDIDATE`다. 다음 조건을 만족한 Commit부터 기준본으로 사용한다.

1. Planning 문서 링크·표·Mermaid·Markdown 검사 PASS
2. 현행 WBS 파일 Diff 없음
3. 팀원별 5주차 지침서와 필수·조건부 범위 충돌 없음
4. 변경 Commit 전체 SHA 기록

## 3. 후속 변경 기록 형식

| 변경 ID | 일시 | 변경자 | 대상 | 변경 내용 | WBS 영향 | 상태 |
|---|---|---|---|---|---|---|
| `W5-PLAN-XXX` | YYYY-MM-DD HH:mm KST | 이름 | 파일·Gate | 변경 사유와 결과 | 없음 또는 승인 참조 | 제안·승인·철회 |

WBS 변경이 필요한 요청은 이 문서만 수정해 우회하지 않고 별도 PM 승인 대상으로 올린다.

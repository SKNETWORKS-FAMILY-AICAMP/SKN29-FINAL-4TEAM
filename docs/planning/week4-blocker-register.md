# 4주차 차단 요소 Register

> 기준 시각: **2026-08-05 15:51 KST**  
> 기준 브랜치·Commit: `main@e2b21faadea72ae25e29510d775b297c3daf17a7`  
> 연계 문서: `docs/planning/week4-current-baseline.md`  
> 운영 원칙: 차단 전달만으로 완료 처리하지 않고 재현 명령·해제 조건·증거를 확인한다.

## 1. 우선순위 기준

| 우선순위 | 의미 |
|---|---|
| `P0` | 8월 5일 발표 기준 동결 또는 8월 6일 시연·발표를 직접 차단 |
| `P1` | 발표에서 제한 사항으로 분리할 수 있으나 5주차 진입 전에 해결 필요 |
| `P2` | 발표 후 개선 가능한 비차단 품질·운영 항목 |

## 2. 차단 요소 요약

| ID | 우선순위 | 영역 | 증상 | 책임자 | 현재 상태 | 목표 시점 |
|---|---|---|---|---|---|---|
| `W4-BLK-001` | P0 | Git·Release | 발표 기준 Commit 확정 | 윤승혁 | RESOLVED | 2026-08-05 |
| `W4-BLK-002` | P0 | Data | 기준 Commit Data Gate 재검증 | 김은진 | RESOLVED | 2026-08-05 |
| `W4-BLK-003` | P0 | Contract Env | 계약 검증 환경 확보 및 실행 | 윤승혁·김은진 | RESOLVED | 2026-08-05 |
| `W4-BLK-004` | P0 | State Machine | Mermaid 1.0.0 재생성 및 CI Gate 추가 | 윤승혁 | FIXED_PENDING_COMMIT | 변경 Commit 전 |
| `W4-BLK-005` | P0 | Backend | 현재 HEAD의 Backend Test·Migration 증거 없음 | 최지용 | ENVIRONMENT_BLOCKED | 8월 5일 동결 전 |
| `W4-BLK-006` | P0 | Web | 현재 Source의 Test·Build가 선택 의존성 문제로 미검증 | 한예나·김은진 | ENVIRONMENT_BLOCKED | 8월 5일 동결 전 |
| `W4-BLK-007` | P0 | Mobile | Gradle 미캐시·네트워크 차단으로 최신 Build·Test 없음 | 양정현·김은진 | ENVIRONMENT_BLOCKED | 8월 5일 동결 전 |
| `W4-BLK-008` | P0 | PM·WBS | WBS 상태가 실제 Runtime·Mock·계약 수준과 불일치 | 윤승혁 | OPEN | 8월 5일 동결 전 |
| `W4-BLK-009` | P0 | T-052 | 중앙 시연 패키지·Fallback·3회 리허설·승인 기록 없음 | 윤승혁·김은진 | OPEN | 8월 5일 동결 전 |
| `W4-BLK-010` | P1 | Backend↔AI | 실제 HTTP 호출·Schema 검증·DB 저장 E2E 없음 | 최지용·이동윤 | INTEGRATION_BLOCKED | 5주차 진입 전 |
| `W4-BLK-011` | P1 | 상담·방문 | G2 11개 Operation이 후보·NOT_IMPLEMENTED 상태 | 최지용 | CONTRACT_ONLY | 5주차 우선순위 확정 시 |
| `W4-BLK-012` | P1 | AI | 현재 AI Test·팀 DB pgvector 재검증 없음 | 이동윤·김은진 | ENVIRONMENT_BLOCKED | 5주차 진입 전 |
| `W4-BLK-013` | P1 | Contract Crosswalk | 행동 23개 전체의 OpenAPI·Runtime·후속 분류가 없음 | 윤승혁·최지용 | OPEN | 8월 7일 Exit Gate 전 |

## 3. 상세 차단 기록

### W4-BLK-001 — 발표 기준 Commit 불명확

| 항목 | 내용 |
|---|---|
| 증상 | `main@e2b21fa`이지만 Data Raw 변경과 팀원 진행도 문서가 미커밋 상태 |
| 직접 원인 | 병합 후 작업 트리 포함 범위와 발표 Source 동결 Commit이 아직 확정되지 않음 |
| 영향 | 같은 Commit·같은 파일로 Test·발표·Fallback을 재현할 수 없음 |
| 책임 | 윤승혁, 변경 파일별 주관 담당자 |
| 해제 조건 | 미커밋 파일의 포함·제외를 주관 담당자가 확인하고 발표 기준 Commit·작업 트리 상태를 기록 |
| 증거 | `git status --short`, 발표 승인 문서 |
| 주의 | 사용자 변경을 PM이 임의 삭제·이동하지 않음 |
| 해제 시각 | 2026-08-05 KST |
| 해제 Commit | `e2b21faadea72ae25e29510d775b297c3daf17a7` |
| 해제 결정 | 현재 최신 Commit을 발표 기준으로 사용하며 미커밋 파일은 발표 기준에서 제외 |
| 잔여 제한 | 직접 Gate 결과는 미커밋 작업 트리에서 실행됐으므로 깨끗한 Checkout 재검증 필요 |

### W4-BLK-002 — Data Raw 비보존 정책 실패

| 항목 | 내용 |
|---|---|
| 증상 | Data 단위 테스트 67개 중 1개 실패, 기대 Raw 정책 파일 7개 대비 실제 8개 |
| 재현 | `python -B -m unittest discover -s data/tools/tests -v` |
| 직접 원인 | 미추적 `data/raw/faq/source-lists/Q&A 크롤링.md`가 Raw 정책 검사 대상에 추가됨 |
| 영향 | Data QA Gate와 발표 기준선의 67/67 선언 차단 |
| 책임 | 김은진 |
| 협업 | 이동윤, 윤승혁 |
| 해제 조건 | 파일의 정식 위치·보존 정책을 결정하고 67/67 통과, QA·Finalize를 같은 작업 트리에서 재실행 |
| 목표 | 2026-08-05 발표 동결 전 |
| 주의 | 원본·수집 자료일 수 있으므로 확인 없이 삭제하지 않음 |
| 해제 시각 | 2026-08-05 KST |
| 해제 Commit | `e2b21faadea72ae25e29510d775b297c3daf17a7` |
| 해제 증거 | 깨끗한 임시 Checkout에서 Data 67/67, QA Verify Rebuild PASS, Finalize PASS, 오류·경고·Canonical Drift 0개 |
| 해제 판정 | 미추적 `Q&A 크롤링.md`는 기준 Commit에 포함되지 않으며 원본 작업 트리에서 보존한다. 기준 Commit 자체의 Data Gate는 정상이다. |

### W4-BLK-003 — 계약 검증 Python 환경 부재

| 항목 | 내용 |
|---|---|
| 증상 | `validate_state_machine.py`와 `render_state_machine.py --check`가 `ModuleNotFoundError: yaml`로 종료 |
| 직접 원인 | 현재 Python과 번들 Python에 `PyYAML`이 설치되지 않음 |
| 영향 | State Machine 내부 정합성과 Diagram Drift를 공식 Gate로 확인할 수 없음 |
| 책임 | 윤승혁 |
| 협업 | 김은진 |
| 해제 조건 | 재현 가능한 계약 검증 환경에서 두 명령이 exit 0으로 통과하고 환경·명령을 기록 |
| 목표 | 2026-08-05 발표 동결 전 |
| 해제 시각 | 2026-08-05 KST |
| 해제 환경 | Python 3.13.12, PyYAML 6.0.3 격리 설치; CI도 동일 Version 고정 |
| 해제 증거 | `validate_state_machine.py` PASS, `render_state_machine.py --check` PASS |
| 해제 판정 | Validator와 Diagram Check를 재현 가능한 명령으로 실행할 수 있으므로 환경 차단 해제 |

### W4-BLK-004 — State Machine Diagram Drift

| 항목 | 내용 |
|---|---|
| 증상 | `inquiry-state-machine.mmd` Header는 `states/events/transitions/guards=0.1.0` |
| 직접 원인 | State Machine 1.0.0 승인 이후 생성 파일을 다시 만들지 않음 |
| 영향 | 발표 다이어그램과 기계 계약이 다른 Version을 설명하게 됨 |
| 책임 | 윤승혁 |
| 선행 | `W4-BLK-003` |
| 해제 조건 | 1.0.0 원본에서 재생성하고 `render_state_machine.py --check` 통과 |
| 증거 | 생성 파일 Header, 입력 Hash, 생성 명령, Check 결과 |
| 목표 | 2026-08-05 발표 동결 전 |
| 수정 결과 | 1.0.0 YAML에서 재생성, 입력 SHA-256·생성 명령 Header 추가, Diagram Check PASS |
| 재발 방지 | `.github/workflows/data-ci.yml`에 `render_state_machine.py --check` 추가 |
| 잔여 조건 | 생성기·Mermaid·CI 변경을 Commit하고 발표 기준 Commit을 해당 Commit으로 갱신해야 최종 `RESOLVED` |

### W4-BLK-005 — Backend 현재 Gate 미검증

| 항목 | 내용 |
|---|---|
| 증상 | `backend/.venv`가 없어 `check_environment.py`와 현재 pytest·Migration 검증을 실행하지 못함 |
| 직접 원인 | Backend 재현 환경 미구성 |
| 영향 | 과거 778/791 통과 기록을 현재 HEAD 성공으로 사용할 수 없음 |
| 책임 | 최지용 |
| 협업 | 김은진, 윤승혁 |
| 해제 조건 | Backend 가상환경 재현 후 전체 Test, Migration drift, 필요 시 PostgreSQL Gate 결과 기록 |
| 목표 | 2026-08-05 동결 전 또는 발표에서 `RECORDED_RUNTIME`으로 강등 승인 |

### W4-BLK-006 — Web 현재 Test·Build 미검증

| 항목 | 내용 |
|---|---|
| 증상 | Lint·TypeScript는 통과하지만 Vitest·Vite Build가 시작 전 실패 |
| 직접 원인 | 기본 Node가 최소 버전 미달이고 현재 `node_modules`에 Windows Rolldown 선택 의존성이 없음 |
| 영향 | Web 동결 Commit 이후 변경 16개의 현재 회귀 결과 없음 |
| 책임 | 한예나 |
| 협업 | 김은진 |
| 해제 조건 | README 지원 Node에서 깨끗한 `npm ci` 후 Test·Lint·Build 통과, 현재 Commit 기록 |
| 대안 | 해결하지 못하면 저장된 이전 Web 성공 Commit을 `RECORDED_RUNTIME/MOCK_UI` 기준으로 사용 |
| 목표 | 2026-08-05 발표 동결 전 |

### W4-BLK-007 — Mobile 최신 Build·Test 미검증

| 항목 | 내용 |
|---|---|
| 증상 | Gradle 9.5.0 배포본 다운로드가 네트워크 권한으로 실패 |
| 직접 원인 | Gradle 배포본 미캐시 및 현재 실행 환경 네트워크 차단 |
| 영향 | 최신 Customer·Core 및 새 Technician 변경의 Build·Test 증거 없음 |
| 책임 | 양정현 |
| 협업 | 김은진 |
| 해제 조건 | Gradle 사용 가능 환경에서 Core·Customer·Technician Test와 APK Build를 현재 Commit으로 실행 |
| 대안 | 이전 `5692124` 모바일 증거만 `RECORDED_RUNTIME`으로 사용하고 신규 기사 기능은 발표 제외 |
| 목표 | 2026-08-05 발표 동결 전 |

### W4-BLK-008 — WBS 상태 불일치

| 항목 | 내용 |
|---|---|
| 증상 | 구현·Mock·계약이 있는 T-011·T-022·T-023·T-026·T-032·T-038·T-040·T-041·T-052가 `미착수`로 남음 |
| 직접 원인 | WBS가 파일·Runtime·Mock·Gate 상태를 구분해 갱신되지 않음 |
| 영향 | 팀 우선순위와 발표 구현 범위를 잘못 설명할 위험 |
| 책임 | 윤승혁 |
| 해제 조건 | `week4-current-baseline.md` 상태 분류와 WBS·Issue 상태를 일치시킴 |
| 목표 | 2026-08-05 발표 동결 전 |

### W4-BLK-009 — 중앙 T-052 시연 패키지 부재

| 항목 | 내용 |
|---|---|
| 증상 | 영역별 자료는 있으나 중앙 단계표·초기화·Fallback·리허설·승인 문서 없음 |
| 직접 원인 | 팀별 산출물을 같은 Commit·대표 ID·시연 순서로 통합하지 않음 |
| 영향 | Mock을 실제 연동으로 설명하거나 시연 실패 시 복구하지 못할 위험 |
| 책임 | 윤승혁 |
| 협업 | 김은진, 전 팀원 |
| 해제 조건 | 각 단계를 `LIVE_RUNTIME/RECORDED_RUNTIME/MOCK_UI/CONTRACT_ONLY/NOT_INCLUDED`로 분류하고 Fallback 및 최소 3회 리허설 기록 확보 |
| 목표 | 2026-08-05 발표 동결 전 |

### W4-BLK-010 — Backend↔AI 실제 수직 연결 부재

| 항목 | 내용 |
|---|---|
| 증상 | AI Client·Mapper·Schema Validator·조율 Service의 실제 HTTP 호출과 DB 저장 E2E 없음 |
| 영향 | 증상 제출 이후 AI 결과와 State Machine 자동 이벤트를 Live로 시연할 수 없음 |
| 책임 | 최지용·이동윤 |
| 해제 조건 | 대표 요청의 HTTP 호출, Schema 검증, 결과·근거 저장, 이벤트 전이와 추적 ID를 검증 |
| 발표 처리 | `NOT_INCLUDED` 또는 명시적 `CONTRACT_ONLY`, Web·Mobile Fixture와 혼동 금지 |
| 목표 | 5주차 진입 전 우선순위 확정 |

### W4-BLK-011 — 상담·방문 Runtime 부재

| 항목 | 내용 |
|---|---|
| 증상 | G2 상담·방문 Operation 11개가 모두 `NOT_IMPLEMENTED`, 구현·소비 시작 Gate `false` |
| 영향 | Web 상담·방문 버튼은 Mock이며 Backend 저장 성공을 의미하지 않음 |
| 책임 | 최지용 |
| 협업 | 한예나, 양정현, 윤승혁 |
| 해제 조건 | Operation별 Runtime·Test를 구현하거나 5주차 이관 상태를 최종 확정 |
| 발표 처리 | Web은 `MOCK_UI`, Backend 상담·방문은 `NOT_INCLUDED` |
| 목표 | 2026-08-07 5주차 Backlog 확정 시 |

### W4-BLK-012 — AI 현재 Gate 미검증

| 항목 | 내용 |
|---|---|
| 증상 | 현재 Python에 pytest가 없고 AI 가상환경도 없어 단위 Test를 실행하지 못함 |
| 영향 | 과거 95개 Test와 pgvector 12/12를 현재 HEAD 직접 성공으로 선언할 수 없음 |
| 책임 | 이동윤 |
| 협업 | 김은진 |
| 해제 조건 | 재현 환경에서 AI Test와 팀 DB pgvector 평가를 현재 Commit으로 실행 |
| 발표 처리 | Source 불변과 과거 증거를 밝히고 `DONE_WITH_LIMITATION`으로 표현 |
| 목표 | 5주차 진입 전 |

### W4-BLK-013 — Action 전체 Crosswalk 미폐쇄

| 항목 | 내용 |
|---|---|
| 증상 | 행동 Registry 23개는 있으나 모든 Action의 OpenAPI·Runtime·후속 분류표가 없음 |
| 영향 | 소비자가 구현 가능한 Action과 계약 전용 Action을 구분하기 어려움 |
| 책임 | 윤승혁 |
| 협업 | 최지용, 한예나, 양정현, 이동윤, 김은진 |
| 해제 조건 | 23개 모두를 `RUNTIME_IMPLEMENTED/OPENAPI_CONFIRMED/CONTRACT_ONLY/DEFERRED` 중 하나로 분류하고 검증 Test 추가 |
| 목표 | 2026-08-07 Exit Gate 전 |

## 4. 발표 동결 전 실행 순서

1. `W4-BLK-004` 생성기·Mermaid·CI 변경 Commit 및 발표 기준 Commit 갱신
2. `W4-BLK-005`·`006`·`007` 영역별 현재 Gate 확보 또는 Recorded·Mock 강등 결정
3. `W4-BLK-008` WBS 상태 현행화
4. `W4-BLK-009` 중앙 시연 패키지와 Fallback 작성·리허설
5. 김은진 발표자료의 주장–증거와 기능 상태를 최종 검수

## 5. 해제 기록 양식

차단을 닫을 때 다음을 추가한다.

| 항목 | 기록 내용 |
|---|---|
| 해제 시각 | KST 날짜·시각 |
| 해제 Commit | 전체 SHA |
| 실행 환경 | OS·Runtime·의존성 Version |
| 실행 명령 | 재현 가능한 명령 |
| 결과 | 통과 수·실패 수·Exit Code |
| 증거 경로 | 로그·리포트·PR·Commit |
| 검토자 | 작성자 외 검토자 |
| 잔여 제한 | Mock·미연동·후속 범위 |

해제 조건과 증거가 없는 항목은 담당자가 “수정 완료”라고 전달해도 `OPEN` 상태를 유지한다.

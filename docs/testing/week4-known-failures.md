# 4주차 Known Failures

> 기준 Commit: `e95e633d58324579a28bf7858fa8be1555ca1a09`  
> 원본 Register: [4주차 차단 요소 Register](../planning/week4-blocker-register.md)

## 1. 현재 열림·차단 항목

| ID | 영역 | 현상·재현 | 구분 | 담당·협업 | 해제 또는 발표 처리 조건 |
|---|---|---|---|---|---|
| `W4-BLK-005` | Backend | `python scripts/development/bootstrap.py --service backend` 실행 시 요구 Python 3.13.13과 보유 Version 불일치 | 환경 차단 | 최지용 / 김은진·윤승혁 | Python 3.13.13 환경에서 전체 Test·Migration Gate 실행, 또는 `RECORDED_RUNTIME` 강등 승인 |
| `W4-BLK-007` | Mobile | Gradle 실행 시 `:core:compileDebugJavaWithJavac` Provider 값 부재 | 환경·설정 차단 | 양정현 / 김은진 | SDK Platform 정합화 후 Core·Customer·Technician Test 및 APK Build 통과, 또는 신규 기능 발표 제외 |
| `W4-BLK-009` | T-052 | 중앙 실행 순서·초기화·Fallback·리허설 3회 기록 없음 | 산출물 미완료 | 윤승혁 / 김은진·한예나 | 단계별 기능 상태를 분류하고 Fallback 및 리허설 3회 기록 확보 |
| `W4-BLK-010` | Backend-AI | 실제 HTTP 호출·Schema 검증·DB 저장 E2E 없음 | 통합 차단 | 최지용·이동윤 | 요청부터 결과·근거 저장과 이벤트까지 추적 가능한 E2E 통과 |
| `W4-BLK-011` | 상담·방문 | G2 Operation 11개가 모두 `NOT_IMPLEMENTED` | 계약 전용 | 최지용 / 한예나·양정현·윤승혁 | Operation별 Runtime·Test 구현 또는 5주차 이관 확정; 발표에서는 `NOT_INCLUDED` |
| `W4-BLK-012` | AI | 현재 단위 테스트·팀 DB pgvector 재실행 증거 없음 | 환경 차단 | 이동윤 / 김은진 | 현재 Commit에서 AI Test 및 팀 DB pgvector 평가 실행 |
| `W4-BLK-013` | Action Crosswalk | Action 23개의 OpenAPI·Runtime·클라이언트 전체 분류 없음 | 문서·검증 미완료 | 윤승혁 / 전 팀원 | 모든 Action을 구현·OpenAPI 확인·계약 전용·이관 중 하나로 분류하고 근거 연결 |
| 외부 Issue 정합성 | PM | GitHub Issue 상태를 로컬 문서와 직접 대조하지 못함 | 외부 확인 대기 | 윤승혁 / 각 담당자 | WBS·Blocker와 Issue 상태·담당자·목표일 의미 일치 확인 |

## 2. 해제된 항목

| ID | 결과 | 해제 근거 |
|---|---|---|
| `W4-BLK-002` | RESOLVED | Raw 비보존 정책 복구, Data 67/67, QA·Finalize PASS |
| `W4-BLK-003` | RESOLVED | Python 3.13.12·PyYAML 6.0.3 환경에서 계약 Validator 실행 |
| `W4-BLK-004` | RESOLVED | Mermaid 1.0.0 재생성 및 CI Diagram Check 추가 |
| `W4-BLK-006` | RESOLVED | Web 113 Test, Lint, TypeScript, Production Build PASS |
| `W4-BLK-008` | RESOLVED | `e95e633`에서 WBS 상태·집계·Gantt 현행화 |

## 3. 발표 시 금지되는 주장

- Backend 전체 Test와 Migration이 현재 기준선에서 통과했다는 주장
- AI 95개 Test와 pgvector 12/12가 현재 기준선에서 직접 재검증됐다는 주장
- Web 상담·방문 UI가 실제 Backend와 연결됐다는 주장
- Mobile 안내·Evidence가 실제 Runtime 응답이라는 주장
- 상담·방문 Operation과 Backend-AI 수직 흐름이 Live Runtime이라는 주장

각 항목은 실제 상태에 따라 `RECORDED_RUNTIME`, `MOCK_UI`, `CONTRACT_ONLY`, `NOT_INCLUDED`로 표시한다.

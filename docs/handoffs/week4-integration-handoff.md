# 4주차 통합 인계 목록

> 기준 Commit: `e95e633d58324579a28bf7858fa8be1555ca1a09`  
> 목적: 3.1 기준선 검토 이후 담당자별 해제 작업과 제출 증거를 한곳에서 관리한다.

## 1. 담당자별 인계

| 담당자 | 다음 조치 | 제출할 증거 | 연결 항목 | 완료 판정 |
|---|---|---|---|---|
| 최지용 | Python 3.13.13 환경에서 Backend 전체 Test·Migration Gate 실행 | 환경 Version, 명령, Test 집계, Migration Drift 결과, Commit | `W4-BLK-005` | PASS 증거 확보 또는 발표 `RECORDED_RUNTIME` 강등 합의 |
| 최지용·이동윤 | Backend-AI 실제 HTTP·Schema·DB 저장 경로 검증 | 요청·응답, 추적 ID, 위험·근거 없음 정책 결과, 저장 이벤트 E2E | `W4-BLK-010` | 수직 E2E 통과 또는 `NOT_INCLUDED` 확정 |
| 이동윤 | 현재 Commit에서 AI Test와 팀 DB pgvector 평가 재실행 | Test 수·PASS/FAIL, DB 환경, 평가 12건 결과, Commit | `W4-BLK-012` | 현재 기준선 직접 실행 증거 확보 |
| 한예나 | Web 통과 Gate 유지 및 상담·방문 화면의 Mock 표시 확인 | `npm ci` 기반 Test·Lint·Build 결과, 화면 상태 표기 | `W4-BLK-011` | Mock UI가 Live Runtime으로 오인되지 않음 |
| 양정현 | Android SDK Platform 정합화 후 전체 지정 Task 재실행 | SDK·JDK·Gradle Version, Test 결과, APK 경로, Commit | `W4-BLK-007` | 전체 PASS 또는 신규 Mobile 범위 발표 제외 |
| 김은진 | 영역별 증거를 같은 Commit 기준으로 재검토하고 발표 자료에 상태 반영 | QA 확인표, 기능별 주장·증거·상태 표, 최종 인계 기록 | `W4-BLK-005/007/009/012` | 증거 없는 PASS 주장이 없음 |
| 윤승혁 | GitHub Issue-WBS 정합성 확인 및 Action 23개 Crosswalk 완성 | Issue 대조 기록, Action별 분류·근거, Commit | `W4-BLK-013` | WBS·Issue·계약·Runtime 의미가 일치 |
| 윤승혁·김은진 | 중앙 실행 패키지·Fallback·리허설 기록 작성 | 초기화 명령, 단계별 실행 순서, Fallback, 리허설 3회 결과 | `W4-BLK-009`, T-052 | 발표 재현 가능 및 김은진 최종 인계 완료 |

## 2. 발표 기능 상태 인계

| 기능 | 현재 허용 분류 | 발표 조건 |
|---|---|---|
| State Machine 계약·Data 14단계 | `CONTRACT_ONLY` | 계약·Fixture 기반 검증임을 명시 |
| Web 상담·방문 화면 | `MOCK_UI` | 실제 Backend 미연결 표시 유지 |
| Mobile 인증·문의 생성·증상 제출 | `RECORDED_RUNTIME` | 과거 실기기 증거임을 명시하고 현재 재검증으로 표현하지 않음 |
| Mobile AI 안내·Evidence | `MOCK_UI` | Fixture 기반임을 명시 |
| Backend 상담·방문 | `NOT_INCLUDED` | Runtime 구현과 Gate 통과 전 포함 금지 |
| Backend-AI 수직 흐름 | `NOT_INCLUDED` | HTTP·Schema·DB 저장 E2E 통과 전 포함 금지 |

## 3. 증거 제출 형식

각 담당자는 다음 항목을 함께 전달한다.

1. 검증 Commit 전체 SHA
2. OS·Runtime·핵심 의존성 Version
3. 재현 가능한 실행 명령
4. PASS·FAIL 수와 Exit Code
5. 로그·리포트·스크린샷 또는 테스트 파일 경로
6. Mock·미연동·후속 이관 범위

증거가 없거나 기준 Commit이 다른 결과는 `VERIFIED_DONE`으로 승격하지 않는다. 최신 상태는 [현재 기준선](../planning/week4-current-baseline.md), 상세 재현은 [Main 회귀 결과](../testing/week4-main-regression-result.md)를 따른다.

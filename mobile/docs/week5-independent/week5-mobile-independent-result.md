# 5주차 모바일 독립 Gate 결과

> 생성 일시: 2026-08-11T10:37:14+09:00
>
> 작업 트리 기준 HEAD: `eb78910ce1b82a8d0fc3dd53dd5e9c43eb3b19f1`

## 최종 판정

- `INDEPENDENT_MOBILE_WEEK5 = PASS`
- `FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND`

## 테스트 / 빌드

- 방문기사 상태 매핑 단위 테스트: PASS
- Core 단위 테스트: PASS
- 고객 단위 테스트: PASS
- 방문기사 단위 테스트: PASS
- 고객 Connected Test: PASS
- 방문기사 Connected Test: PASS
- 고객 Debug APK: PASS
- 방문기사 Debug APK: PASS
- 고객 AndroidTest APK: PASS
- 방문기사 AndroidTest APK: PASS
- `verify-build.bat`: PASS

## AndroidTest 실행 Activity 처리

- `CustomerMinimumFlowTest`: `createEmptyComposeRule` + `ActivityScenario` 수동 호스트
- `TechnicianMinimumFlowTest`: `createEmptyComposeRule` + `ActivityScenario` 수동 호스트
- Activity가 RESUMED가 아니면 moveToState(RESUMED) 후 Compose content 설정
- ComponentActivity.setContent를 ActivityScenario.onActivity에서 직접 호출
- T106 실단말 Probe에서 manual host semantics PASS 확인
- Technician UI 리디자인 문구와 AndroidTest assertion 정합성 반영
  - 오프라인 합성 데이터
  - 방문 API 연결 대기
- 기존 테스트 시나리오 의미와 Backend fail-closed 의미 유지
- 프로덕션 Customer/Technician UI 로직 추가 변경 없음
- Backend/API/Repository/ViewModel 변경 없음

## 실단말

- 기기: R3CT8076D7B
- 고객 APK 설치: PASS
- 방문기사 APK 설치: PASS

## APK SHA-256

- 고객: `30adb51f3fda92274376da447fe0d771367f9a2ff38cd9f4c7d563e06fb8c6e9`
- 방문기사: `2dea430bd7ca19c90c6f286eeb1ce2a4d8610bb34686ac23001b35a1101cd40f`

## 독립 회귀 기준

- Remote 실패를 Fixture 성공으로 자동 대체하지 않음
- Offline Preview는 명시적 사용자 선택으로 분리
- `WAITING_COMPLETION`은 완료 대기
- `COMPLETED`를 모바일이 임의 완료 처리하지 않음
- 알 수 없는 Legacy Visit 상태는 상태 확인 필요

## 남은 백엔드 차단 항목

- CUSTOMER_FOLLOWUP_RUNTIME
- CUSTOMER_GUIDANCE_EVIDENCE_RUNTIME
- CUSTOMER_REQUEST_CONSULTATION_RUNTIME
- TECHNICIAN_ASSIGNED_VISIT_LIST_DETAIL_RUNTIME
- TECHNICIAN_VISIT_START_COMPLETE_RUNTIME
- FULL_CUSTOMER_AI_CONSULTATION_VISIT_TECHNICIAN_E2E

## Git

- `git diff --check`: PASS
- Git 추적 대상 `mobile/local.properties`: False
- Commit 메시지: `고객/기사 AndroidTest 두 파일의 테스트  완료`
- Push 수행: False

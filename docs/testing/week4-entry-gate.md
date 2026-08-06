# 4주차 진입 Gate

> 기준 시각: **2026-08-05 18:19 KST**  
> 기준 Commit: `e95e633d58324579a28bf7858fa8be1555ca1a09`  
> 진입 판정: **조건부 진입 가능 / 발표 동결 불가**

## Gate 결과

| Gate | 결과 | 분류 | 판정 근거 또는 차단 원인 |
|---|---|---|---|
| Git 기준선 | PASS | `VERIFIED_DONE` | `main@e95e633`, WBS 현행화 포함 |
| Data 단위 테스트 | PASS | `VERIFIED_DONE` | 격리된 깨끗한 검증 환경에서 67/67 통과 |
| Data QA·Finalize | PASS | `VERIFIED_DONE` | 오류 0, 경고 0, Canonical Drift 0, Dataset 0.9.0 |
| State Machine Validator | PASS | `VERIFIED_DONE` | 상태 13, 이벤트 30, 전이 34, Guard 39, 허용 행동 23 |
| State Machine Diagram Check | PASS | `VERIFIED_DONE` | Mermaid 1.0.0 재생성 및 `--check` 통과 |
| Backend Test·Migration | BLOCKED | `INTEGRATION_BLOCKED` | 요구 Python 3.13.13, 확보 환경 3.13.12·번들 3.12.13 |
| AI Test·pgvector | NOT RERUN | `DONE_WITH_LIMITATION` | 저장된 95개·pgvector 12/12 증거는 있으나 현재 기준선 재실행 없음 |
| Web Test | PASS | `VERIFIED_DONE` | 27개 파일, 113개 Test 통과 |
| Web Lint·TypeScript·Build | PASS | `VERIFIED_DONE` | Node 24.14.0과 `npm ci` 환경에서 통과 |
| Mobile Test·Build | BLOCKED | `INTEGRATION_BLOCKED` | `:core:compileDebugJavaWithJavac` Provider 값 부재, SDK Platform 정합성 의심 |
| WBS 현행화 | PASS | `VERIFIED_DONE` | `e95e633`에 구현·Mock·계약 경계와 집계 반영 |
| 중앙 발표 패키지 | NOT READY | `NOT_STARTED` | `W4-BLK-009`, Fallback·리허설 3회·최종 인계 미확보 |

## 판정 규칙

- 4주차 통합 준비 작업은 차단 항목을 공개한 상태로 계속 진행할 수 있다.
- Backend·AI·Mobile을 최신 Live Runtime으로 발표하려면 각 영역의 현재 Gate 통과 증거가 필요하다.
- Gate를 해제하지 못한 영역은 `RECORDED_RUNTIME`, `MOCK_UI`, `CONTRACT_ONLY`, `NOT_INCLUDED` 중 하나로 명시해야 한다.
- 중앙 발표 패키지와 Fallback이 준비되기 전에는 발표 기준선을 동결하지 않는다.

상세 결과는 [Main 회귀 결과](week4-main-regression-result.md), 원인과 해제 조건은 [Known Failures](week4-known-failures.md) 및 [차단 요소 Register](../planning/week4-blocker-register.md)를 따른다.

# 4주차 Main 회귀 검증 결과

> 기준 Commit: `e95e633d58324579a28bf7858fa8be1555ca1a09`  
> 검증일: **2026-08-05 KST**  
> 종합 판정: **부분 PASS / 통합 차단 유지**

## 1. 결과 요약

| 영역 | 실행 또는 확인 내용 | 결과 | 현재 판정 |
|---|---|---|---|
| Data | 단위 테스트 | 67/67 PASS | `VERIFIED_DONE` |
| Data | QA Verify Rebuild | PASS, 오류·경고·Drift 0 | `VERIFIED_DONE` |
| Data | Finalize | PASS, Dataset 0.9.0, Manifest 154개 | `VERIFIED_DONE` |
| Contract | State Machine Validator | PASS | `VERIFIED_DONE` |
| Contract | Mermaid 생성 결과 Check | PASS | `VERIFIED_DONE` |
| Backend | Bootstrap·가상환경 준비 | Python Patch Version 불일치로 중단 | `INTEGRATION_BLOCKED` |
| AI | 현재 기준선 단위·pgvector 재실행 | 미실행 | `DONE_WITH_LIMITATION` |
| Web | Vitest | 27개 파일·113개 Test PASS | `VERIFIED_DONE` |
| Web | ESLint·TypeScript·Vite Build | 전부 PASS | `VERIFIED_DONE` |
| Mobile | Core·Customer·Technician Test 및 APK Build | Core Java Compile Task 구성 중 실패 | `INTEGRATION_BLOCKED` |

## 2. 직접 실행 명령과 결과

### Data

Raw 비보존 정책을 복구한 깨끗한 검증 환경에서 실행했다.

```text
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py qa --verify-rebuild
python -B data/tools/pipeline.py finalize
```

- 단위 테스트: 67/67 통과, 실패 0, 오류 0
- QA Verify Rebuild: PASS, 오류 0, 경고 0, Canonical Drift 0
- Finalize: PASS, Dataset 0.9.0, Manifest 154개
- 검증 결과와 Raw 정책 복구는 `24b6b3371b50679a3b2c449a651606e6cbdc581b`에 포함되며 현재 기준선이 이를 포함한다.

### State Machine 계약

```text
python contracts/tools/validate_state_machine.py
python contracts/tools/render_state_machine.py --check
```

- Validator: PASS
- 집계: 상태 13, 이벤트 30, 전이 34, Guard 39, 허용 행동 23, 역할 14
- Mermaid: 계약 Version 1.0.0, 입력 SHA-256 및 생성 명령 Header 포함
- Diagram Check: PASS

### Backend

```text
python scripts/development/bootstrap.py --service backend
```

- 결과: Backend 공식 가상환경 생성 전 중단
- 요구 Version: Python 3.13.13
- 확인된 Version: 기본 Python 3.13.12, 번들 Python 3.12.13
- 판정: 테스트 코드 실패가 아니라 **재현 환경 차단**이다. 따라서 현재 HEAD의 전체 pytest·Migration 통과를 주장하지 않는다.

### AI

- 현재 환경에 AI 전용 가상환경과 `pytest`가 없어 재실행하지 못했다.
- 과거 증거: 단위 테스트 95개, 팀 DB pgvector 12/12 후보 결과
- 현재 판정: Source 변경이 없는 점은 확인했으나 현재 기준선 직접 통과로 승격하지 않는다.

### Web

Node 24.14.0과 `package-lock.json` 기준 `npm ci` 환경에서 확인했다.

- ESLint: PASS
- TypeScript `tsc -b`: PASS
- Vitest: 27개 파일, 113개 Test PASS
- Vite Production Build: PASS
- 단일 Worker 전체 실행은 240초 제한 후 종료되어 나머지 Test를 분할 실행했고, 합계 113개 전체 통과를 확인했다.
- 상담·방문 화면은 Remote Backend가 아니라 Mock·Repository 경계이므로 Runtime 판정은 `MOCK_ONLY / BACKEND_BLOCKED`이다.

### Mobile

```text
gradlew.bat :core:test :customer-app:testDebugUnitTest :customer-app:assembleDebug --no-daemon
```

- Gradle 9.5.0, Android SDK, JDK 21 인식 성공
- `:core:compileDebugJavaWithJavac` 의존성 계산에서 값이 없는 Provider 오류로 중단
- 설치 SDK `android-37.0`과 `compileSdk=37` 조합의 Platform Provider 정합성 문제로 추정하되, 확정 원인으로 단정하지 않는다.
- 판정: 최신 Core·Customer·Technician 테스트와 APK Build는 미검증이다.

## 3. 결론

Data·State Machine·Web의 현재 Gate는 통과했다. Backend와 Mobile은 재현 환경에서 차단되었고, AI는 현재 기준선 재실행 증거가 없다. 그러므로 전체 Main은 **부분 PASS**이며, 프로젝트 상태는 **`INTEGRATION_BLOCKED`**를 유지한다.

해제 조건은 [Known Failures](week4-known-failures.md), 담당자별 조치는 [통합 인계](../handoffs/week4-integration-handoff.md)에 기록한다.

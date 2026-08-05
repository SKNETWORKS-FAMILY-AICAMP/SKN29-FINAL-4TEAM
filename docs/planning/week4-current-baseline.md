# 4주차 현재 기준선

> 기준 시각: **2026-08-05 15:51 KST**  
> 기준 브랜치: `main`  
> 기준 Commit: `e2b21faadea72ae25e29510d775b297c3daf17a7`  
> Commit 시각: `2026-08-05 15:40:50 +09:00`  
> 발표 기준 Commit 승인: **2026-08-05, 윤승혁**  
> 검증 범위: 최신 작업 트리의 계약·Data·Backend·AI·Web·Mobile·WBS·발표 준비 상태  
> 종합 상태: **INTEGRATION_BLOCKED / PRESENTATION_FREEZE_NOT_APPROVED**

## 1. 기준선 원칙

이 문서는 팀원이 보고한 완료율이나 과거 성공 수치를 현재 성공으로 재사용하지 않는다. 다음 세 가지를 분리한다.

1. 현재 작업 트리에서 직접 실행해 통과한 결과
2. 과거 Commit에서 저장된 성공 증거
3. 실행 환경 부족 또는 외부 의존성으로 확인하지 못한 결과

상태 판정은 다음 값을 사용한다.

| 상태 | 의미 |
|---|---|
| `VERIFIED_DONE` | 현재 작업 트리에서 실행·검증까지 통과 |
| `DONE_WITH_LIMITATION` | 구현과 과거 증거는 있으나 현재 전체 Gate 또는 실제 연동이 제한됨 |
| `INTEGRATION_BLOCKED` | 다른 영역·계약·환경이 준비되지 않아 실제 연결을 완료하지 못함 |
| `MOCK_ONLY` | 합성 Mock으로만 동작하며 실제 Backend 저장을 의미하지 않음 |
| `CONTRACT_ONLY` | 계약·예시·테스트 골격만 존재하고 Runtime이 없음 |
| `NOT_STARTED` | 검증 가능한 구현 또는 산출물이 없음 |

## 2. Git·작업 트리 기준

사용자는 모든 팀 브랜치를 최신화했다고 확인했다. 현재 체크아웃 상태는 `main@e2b21fa`다.

다만 작업 트리는 깨끗하지 않다. 검증 시점에 다음 미커밋 변경이 존재했다.

- `data/raw/faq/source-lists/.gitkeep` 삭제
- `data/raw/manuals/mvp/.gitkeep` 삭제
- `data/raw/faq/source-lists/Q&A 크롤링.md` 신규·미추적
- 팀원 6명의 `docs/individual/**/4주차 작업 진행도` 문서 신규·미추적

발표 기준 Commit은 `e2b21faadea72ae25e29510d775b297c3daf17a7`로 확정한다. 위 미커밋 파일은 발표 기준 Commit에 포함되지 않는다.

초기 직접 실행 결과는 미커밋 변경을 포함한 현재 작업 트리에서 얻었다. Data Gate는 이후 기준 Commit의 깨끗한 Checkout에서 재검증을 완료했으며, 나머지 영역은 각 절에 명시한 실행 환경과 증거 시점을 기준으로 판정한다. 초기 Data Raw 정책 실패는 미추적 `Q&A 크롤링.md`의 영향이었으므로 기준 Commit 자체의 실패와 작업 트리 오염을 구분한다.

## 3. 영역별 Gate 결과

### 3.1 State Machine·공통 계약

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| State Machine YAML | `1.0.0 / TEAM_APPROVED` | `VERIFIED_DONE` | Validator 통과: 상태 13·이벤트 30·전이 34·Guard 39·외부 행동 23 |
| Inquiry 상태 Registry | 상태 13개 등록 | `VERIFIED_DONE` | `contracts/codes/inquiry-statuses.yaml` |
| Workflow Action Registry | 외부 행동 23개 등록 | `VERIFIED_DONE` | `contracts/codes/workflow-actions.yaml` |
| State Machine Validator | PASS | `VERIFIED_DONE` | Python 3.13.12·PyYAML 6.0.3 격리 환경에서 직접 실행 |
| Mermaid 최신성 | `1.0.0` 재생성 | `FIXED_PENDING_COMMIT` | Version·입력 SHA-256·생성 명령 Header 기록 |
| Diagram Check | PASS | `FIXED_PENDING_COMMIT` | CI에도 `render_state_machine.py --check` Gate 추가 |
| Action–OpenAPI–Runtime Crosswalk | G2 후보 존재 | `CONTRACT_ONLY` | `G2_ACTIVE_CANDIDATE`, 구현·소비 시작 Gate 모두 `false` |

`contracts/api/g2-operation-crosswalk.yaml`에 상담·방문 Operation 11개가 정의되어 있으나 모두 `NOT_IMPLEMENTED`다. 이 파일은 Action 23개 전체에 대한 최종 Runtime 분류표가 아니며 소비자 통합 시작도 승인되지 않았다.

### 3.2 Data·Fixture·QA

기준 Commit `e2b21faadea72ae25e29510d775b297c3daf17a7`의 깨끗한 임시 Checkout에서 실행한 명령:

```text
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py qa --verify-rebuild
python -B data/tools/pipeline.py finalize
```

Git 안전 경로를 명령 범위로 적용한 재실행 결과:

- 총 67개
- 통과 67개
- 실패 0개
- 오류 0개
- 실행 시간: 15.073초
- QA: PASS, 오류 0개, 경고 0개
- 대표 E2E: 17/17 PASS
- Reproducibility: PASS, Canonical Drift 0개
- Finalize: PASS, Manifest 154개 확인
- 실행 후 `git status --short` 및 `git diff --name-only -- data`: 변경 없음

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| Data 단위 테스트 | 67/67 | `VERIFIED_DONE` | 기준 Commit의 깨끗한 Checkout에서 직접 재실행 |
| 계약 소스 Hash | 테스트 통과 | `VERIFIED_DONE` | State Machine Hash 불일치 없음 |
| 대표 14단계 E2E | 테스트 통과 | `VERIFIED_DONE` | 14단계·최종 `RESOLVED`·Version 14 |
| QA Verify Rebuild | PASS | `VERIFIED_DONE` | 오류·경고·Canonical Drift 0개 |
| QA Finalize | PASS | `VERIFIED_DONE` | Dataset 0.9.0, Manifest 154개 확인 |

`latest_qa_summary.json`의 `source_commit=fff23ac...`는 실행 HEAD가 아니라 `contracts/state-machine`을 마지막으로 변경한 Commit을 기록하도록 구현된 계약 출처 필드다. 실행 HEAD는 별도로 `e2b21fa...`임을 확인했으며, Data Gate는 현재 발표 기준 Commit에서 전체 통과했다.

### 3.3 Backend

현재 `/api/v1`에는 Accounts와 Inquiries URL만 등록되어 있다. Inquiry Runtime에서 확인되는 상태 변경 Route는 다음 세 개다.

- 문의 생성 `START_INQUIRY`
- DRAFT 문의 취소 `CANCEL_INQUIRY`
- 증상 제출 `SUBMIT_SYMPTOM`

상담·방문 URL과 View는 Runtime에 등록되지 않았다. Backend↔AI Client·Mapper·Validator·조율 Service의 실제 HTTP·저장 연결도 완료되지 않았다.

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| Backend 가상환경 | 없음 | `INTEGRATION_BLOCKED` | `backend/.venv/Scripts/python.exe` 없음 |
| 현재 Backend 전체 Test | 미실행 | `INTEGRATION_BLOCKED` | `check_environment.py`가 가상환경 부재로 종료 |
| 문의 생성·취소·증상 제출 | 구현 존재 | `DONE_WITH_LIMITATION` | 저장된 작성자 증거는 있으나 현재 HEAD 재검증 없음 |
| State·409·Replay 기반 | 코드·테스트 존재 | `DONE_WITH_LIMITATION` | 현재 환경에서 pytest 미실행 |
| 상담·방문 Runtime | 없음 | `CONTRACT_ONLY` | G2 Operation은 모두 `NOT_IMPLEMENTED` |
| Backend↔AI 수직 연결 | 없음 | `INTEGRATION_BLOCKED` | 실제 HTTP 호출·결과 저장 E2E 없음 |

팀원 진행 문서가 기준으로 삼은 `d905262` 이후 Backend Runtime Source는 바뀌지 않았고 계약 테스트 파일 5개가 추가됐다. 과거 SQLite·PostgreSQL 성공 기록은 보존하되 현재 기준선의 직접 성공으로 승격하지 않는다.

### 3.4 AI·RAG

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| AI Source | `d905262` 이후 변경 없음 | `DONE_WITH_LIMITATION` | 이전 95개 테스트 후보 증거와 Source 동일 |
| 현재 AI 단위 테스트 | 미실행 | `INTEGRATION_BLOCKED` | AI 가상환경 없음, 현재 Python에 `pytest` 없음 |
| 위험·근거 없음 정책 | 구현 존재 | `DONE_WITH_LIMITATION` | 현재 환경 재실행 없음 |
| pgvector 12/12 | 과거 후보 증거 | `DONE_WITH_LIMITATION` | 팀 DB·현재 Commit 재실행 아님 |
| 증상 구조화·추가 질문 | 구현 존재 | `DONE_WITH_LIMITATION` | Backend·Web·Mobile 소비 미연결 |
| Backend 자동 이벤트·저장 | 없음 | `INTEGRATION_BLOCKED` | Backend Client·Mapper·저장 E2E 없음 |

발표에서는 AI Runtime Source와 과거 단위 테스트 증거를 설명할 수 있으나, Backend와 연결된 전체 AI 서비스 E2E로 표현하면 안 된다.

### 3.5 Web

현재 작업 트리에서 직접 확인한 결과:

| 검사 | 결과 | 판정 |
|---|---|---|
| ESLint | 통과 | `VERIFIED_DONE` |
| TypeScript `tsc -b` | 통과 | `VERIFIED_DONE` |
| Vitest | 시작 전 실패 | 환경 차단 |
| Vite Production Build | 시작 전 실패 | 환경 차단 |

환경 분리 결과:

- 기본 Node `20.11.0`은 README 최소 `20.19`보다 낮아 `node:util.styleText`를 제공하지 않는다.
- 번들 Node `24.14.0`에서는 현재 `node_modules`에 Windows Rolldown 선택 의존성 `@rolldown/binding-win32-x64-msvc`가 없어 Test와 Vite Build가 시작되지 않는다.
- 저장된 `1d1011d` 기준 결과는 113개 Test·Lint·Build 통과다.
- 현재 HEAD는 해당 Web 동결 Commit 이후 Web 파일 16개가 변경되어 과거 결과를 그대로 현재 성공으로 사용할 수 없다.

상담·방문 화면은 Repository 경계를 두었지만 실제 Remote Adapter가 없으며 기본 업무 흐름은 `MOCK_ONLY` 또는 `BACKEND_BLOCKED`로 표시된다.

종합 판정: **`MOCK_ONLY / DONE_WITH_LIMITATION`**

### 3.6 Mobile

현재 검증 명령:

```text
gradlew.bat :core:test :customer-app:testDebugUnitTest :customer-app:assembleDebug --no-daemon
```

현재 환경에서는 Gradle 9.5.0 배포본이 캐시에 없어 다운로드를 시도했고 네트워크 권한으로 차단됐다. 따라서 최신 작업 트리의 Build·Test 결과를 얻지 못했다.

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| 인증·문의 생성·증상 제출 | 과거 실단말 성공 증거 | `DONE_WITH_LIMITATION` | 구현 Commit `5692124`, 현재 HEAD 재검증 없음 |
| `state_version`·`allowed_actions` 모델 | 구현 존재 | `DONE_WITH_LIMITATION` | 현재 Gradle Test 미실행 |
| 고객 홈·AI 안내·Evidence | Fixture | `MOCK_ONLY` | 실제 Runtime Endpoint 대기 |
| 상담 요청 | 미연동 | `INTEGRATION_BLOCKED` | Runtime Endpoint 없음 |
| 최신 Core·Customer Build | 미확인 | `INTEGRATION_BLOCKED` | Gradle 배포본 다운로드 차단 |
| 기사 앱 신규 변경 | 미확인 | `INTEGRATION_BLOCKED` | `d905262` 이후 Technician Source·Test 변경 11개 |

발표에서는 인증·문의 생성·증상 제출의 **저장된 실제 연동 증거**와 홈·안내 Fixture를 분리해야 한다.

## 4. WBS 현행성

현재 WBS는 실제 코드·Mock·계약 상태와 맞지 않는다.

- `T-011`, `T-022`, `T-023`, `T-026`, `T-032`, `T-038`, `T-040`, `T-041`, `T-052`가 `미착수`로 남아 있다.
- 실제로는 일부 Runtime, 계약, Mock 또는 테스트가 존재한다.
- 반대로 파일이나 Mock이 존재한다고 `완료`로 올릴 수는 없다.

WBS는 이 문서의 상태 분류를 사용해 현행화해야 한다. 특히 T-022·T-023은 `DONE_WITH_LIMITATION`, T-040·T-041은 `MOCK_ONLY / BACKEND_BLOCKED`, T-052는 `INTEGRATION_BLOCKED`로 보는 것이 현재 증거에 맞다.

## 5. 중간 발표 기준선

대표 기준은 다음으로 고정한다.

- 제품: `WPUJAC104DWH`
- 시나리오: `SYN-JAC104-002`
- 문의: `DEMO-INQ-002`
- 증상: 출수량 저하
- 근거: WPU-JAC104D·WPU-JCC104D REV.00 38쪽

현재 중앙 발표 패키지는 없다. 영역별 Web·Mobile·AI 자료는 존재하지만 다음 통합 산출물이 확인되지 않는다.

- 중앙 대표 시연 단계표
- 동일 Commit 기준 실행·초기화 명령
- Live·Recorded·Mock·Contract-only 구분표
- 전체 Fallback 계획
- 전체 리허설 3회 기록
- 김은진 전달용 최종 기능 상태표
- 윤승혁 최종 승인 기록

현 시점의 안전한 발표 분류는 다음과 같다.

| 단계 | 발표 분류 | 설명 |
|---|---|---|
| 계약·대표 14단계 데이터 | `CONTRACT_ONLY` | 계약과 합성 E2E 검증 결과 |
| 모바일 인증·문의 생성·증상 제출 | `RECORDED_RUNTIME` | 과거 실단말 성공 증거, 현재 재검증 전 |
| Web 상담·방문 화면 | `MOCK_UI` | 실제 Backend 저장 아님 |
| Mobile 홈·AI 안내·Evidence | `MOCK_UI` | 합성 Fixture |
| Backend 상담·방문 | `NOT_INCLUDED` | Runtime 없음 |
| Backend↔AI 수직 흐름 | `NOT_INCLUDED` | 실제 HTTP·DB 저장 E2E 없음 |

현재 전체 흐름을 `LIVE_RUNTIME`으로 승인하지 않는다.

## 6. PM 기준선 판정

### 확인된 강점

- State Machine 계약 1.0.0과 상태 13개·행동 23개 Registry가 존재한다.
- Data 단위 테스트 67/67, QA Verify Rebuild, Finalize와 대표 14단계 E2E가 기준 Commit에서 통과한다.
- Backend 문의 생성·취소·증상 제출 Slice와 Mobile 실제 연동의 저장된 증거가 있다.
- Web Lint와 TypeScript 검사는 현재 작업 트리에서 통과했다.
- 각 영역이 Mock과 실제 Runtime의 경계를 문서화하기 시작했다.

### 발표 동결 전 필수 해제 조건

1. State Machine 생성기·Mermaid·CI Gate 변경을 Commit하고 발표 기준 Commit 갱신
2. Backend·AI·Web·Mobile의 최신 Gate 결과 또는 명시적 환경 차단 승인
3. WBS 상태 현행화
4. 중앙 시연 단계표·Fallback·기능 상태표 작성 및 김은진 전달

위 조건이 충족되기 전 종합 상태는 **`INTEGRATION_BLOCKED / PRESENTATION_FREEZE_NOT_APPROVED`**로 유지한다.

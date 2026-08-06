# 4주차 현재 기준선

> 기준 시각: **2026-08-05 17:45 KST**
> 기준 브랜치: `main`  
> 기준 Commit: `6512178aded1eef745dc40ddc8ed480f1e7870fa`
> Commit 시각: `2026-08-05 17:16:29 +09:00`
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

사용자는 계약·Data·팀원 진행도 문서를 Commit했고 현재 체크아웃 상태는 `main@6512178`이다. 이 Commit에는 State Machine 생성기·Mermaid·CI Gate와 `Q&A 크롤링.md`, 팀원 6명의 4주차 진행도 문서가 포함된다.

발표 기준 Commit은 현재 `6512178aded1eef745dc40ddc8ed480f1e7870fa`다. 이 Commit의 Raw 구성 회귀를 수정해 별도의 깨끗한 Clone에서 재검증했으며, 수정 내용과 갱신된 QA 산출물은 아직 작업 트리에 있다. 따라서 Data는 검증은 완료됐지만 새 Commit으로 포함되기 전까지 `FIXED_PENDING_COMMIT`으로 판정한다.

## 3. 영역별 Gate 결과

### 3.1 State Machine·공통 계약

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| State Machine YAML | `1.0.0 / TEAM_APPROVED` | `VERIFIED_DONE` | Validator 통과: 상태 13·이벤트 30·전이 34·Guard 39·외부 행동 23 |
| Inquiry 상태 Registry | 상태 13개 등록 | `VERIFIED_DONE` | `contracts/codes/inquiry-statuses.yaml` |
| Workflow Action Registry | 외부 행동 23개 등록 | `VERIFIED_DONE` | `contracts/codes/workflow-actions.yaml` |
| State Machine Validator | PASS | `VERIFIED_DONE` | Python 3.13.12·PyYAML 6.0.3 격리 환경에서 직접 실행 |
| Mermaid 최신성 | `1.0.0` 재생성 | `VERIFIED_DONE` | Version·입력 SHA-256·생성 명령 Header가 Commit됨 |
| Diagram Check | PASS | `VERIFIED_DONE` | CI에도 `render_state_machine.py --check` Gate가 Commit됨 |
| Action–OpenAPI–Runtime Crosswalk | G2 후보 존재 | `CONTRACT_ONLY` | `G2_ACTIVE_CANDIDATE`, 구현·소비 시작 Gate 모두 `false` |

`contracts/api/g2-operation-crosswalk.yaml`에 상담·방문 Operation 11개가 정의되어 있으나 모두 `NOT_IMPLEMENTED`다. 이 파일은 Action 23개 전체에 대한 최종 Runtime 분류표가 아니며 소비자 통합 시작도 승인되지 않았다.

### 3.2 Data·Fixture·QA

기준 Commit `6512178...`에 Raw 정책 수정안을 적용한 깨끗한 임시 Clone에서 실행한 명령:

```text
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py qa --verify-rebuild
python -B data/tools/pipeline.py finalize
```

재실행 결과:

- 총 67개
- 통과 67개
- 실패 0개
- 오류 0개
- 실행 시간: 13.971초
- QA Verify Rebuild: PASS, 오류 0개, 경고 0개, Canonical Drift 0개
- Finalize: PASS, Dataset 0.9.0, Manifest 154개 확인
- 원문 백업: `tmp/local-backups/week4-data-raw/Q&A 크롤링.md` 79,555바이트, Git 무시 확인

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| Data 단위 테스트 | 67/67 | `FIXED_PENDING_COMMIT` | Raw 정책 수정안을 적용한 깨끗한 Clone에서 통과 |
| Raw 비보존 정책 | PASS | `FIXED_PENDING_COMMIT` | 원문은 Git 무시 백업으로 이동하고 두 `.gitkeep` 복원 |
| 계약 출처 Commit | `6512178...` | `FIXED_PENDING_COMMIT` | QA Summary 재생성 완료 |
| 대표 14단계 E2E | 테스트 통과 | `VERIFIED_DONE` | 14단계·최종 `RESOLVED`·Version 14 |
| QA Verify Rebuild | PASS | `FIXED_PENDING_COMMIT` | 오류·경고·Canonical Drift 0개 |
| QA Finalize | PASS | `FIXED_PENDING_COMMIT` | Dataset 0.9.0, Manifest 154개 확인 |

`source_commit`은 `contracts/state-machine`을 마지막으로 변경한 Commit을 기록한다. QA Summary를 재생성해 `6512178...`로 갱신했다. `Q&A 크롤링.md`는 삭제하지 않고 Git이 무시하는 로컬 백업 영역에 보존했다.

### 3.3 Backend

현재 `/api/v1`에는 Accounts와 Inquiries URL만 등록되어 있다. Inquiry Runtime에서 확인되는 상태 변경 Route는 다음 세 개다.

- 문의 생성 `START_INQUIRY`
- DRAFT 문의 취소 `CANCEL_INQUIRY`
- 증상 제출 `SUBMIT_SYMPTOM`

상담·방문 URL과 View는 Runtime에 등록되지 않았다. Backend↔AI Client·Mapper·Validator·조율 Service의 실제 HTTP·저장 연결도 완료되지 않았다.

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| Backend 가상환경 | 생성 실패 | `INTEGRATION_BLOCKED` | 요구 Python 3.13.13, 현재 Python 3.13.12·번들 Python 3.12.13 |
| 현재 Backend 전체 Test | 미실행 | `INTEGRATION_BLOCKED` | 공식 Bootstrap이 Python Patch Version 불일치로 선행 차단 |
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

Node 24.14.0과 `package-lock.json` 기준 `npm ci` 환경에서 직접 확인한 결과:

| 검사 | 결과 | 판정 |
|---|---|---|
| ESLint | 통과 | `VERIFIED_DONE` |
| TypeScript `tsc -b` | 통과 | `VERIFIED_DONE` |
| Vitest | 27개 파일·113개 Test 통과 | `VERIFIED_DONE` |
| Vite Production Build | 통과 | `VERIFIED_DONE` |

환경 분리 결과:

- 기본 Node `20.11.0`은 지원 범위보다 낮으므로 번들 Node `24.14.0`을 사용했다.
- `npm ci`로 Windows Rolldown 선택 의존성을 Lockfile 기준 복구했다.
- 단일 Worker 전체 실행은 240초 제한에서 21개 파일·92개 Test까지 통과 후 종료됐고, 남은 6개 파일·21개 Test를 별도 실행해 전체 113개 통과를 확인했다.
- `npm ci`는 High Severity 취약점 3개와 `jsdom`의 Node 24.15 이상 권장 경고를 출력했지만 현재 Lint·TypeScript·Test·Build에는 실패가 없었다.

상담·방문 화면은 Repository 경계를 두었지만 실제 Remote Adapter가 없으며 기본 업무 흐름은 `MOCK_ONLY` 또는 `BACKEND_BLOCKED`로 표시된다.

종합 판정: **코드 Gate `VERIFIED_DONE`, 상담·방문 Runtime은 `MOCK_ONLY / BACKEND_BLOCKED`**

### 3.6 Mobile

현재 검증 명령:

```text
gradlew.bat :core:test :customer-app:testDebugUnitTest :customer-app:assembleDebug --no-daemon
```

Gradle 9.5.0과 Android SDK를 인식시킨 뒤 Core·Customer·Technician Test·Build를 실행했다. Gradle 실행 환경은 복구됐지만 `:core:compileDebugJavaWithJavac` 의존성 계산에서 값이 없는 Provider 오류로 Build가 중단됐다. 설치 SDK에는 `android-37.0`이 있으나 Build의 `compileSdk=37`이 기대하는 정확한 Platform Provider를 얻지 못한 것으로 보이며, 이는 실행 결과와 설치 목록을 바탕으로 한 추론이다.

| 항목 | 현재 결과 | 판정 | 근거·제한 |
|---|---|---|---|
| 인증·문의 생성·증상 제출 | 과거 실단말 성공 증거 | `DONE_WITH_LIMITATION` | 구현 Commit `5692124`, 현재 HEAD 재검증 없음 |
| `state_version`·`allowed_actions` 모델 | 구현 존재 | `DONE_WITH_LIMITATION` | 현재 Gradle Test 미실행 |
| 고객 홈·AI 안내·Evidence | Fixture | `MOCK_ONLY` | 실제 Runtime Endpoint 대기 |
| 상담 요청 | 미연동 | `INTEGRATION_BLOCKED` | Runtime Endpoint 없음 |
| Gradle·Android SDK | 인식 성공 | `DONE_WITH_LIMITATION` | Gradle 9.5.0, Android SDK·JDK 21 확인 |
| 최신 Core·Customer Build | 실패 | `INTEGRATION_BLOCKED` | `compileDebugJavaWithJavac` Provider 값 없음 |
| 기사 앱 신규 변경 | 실패 전 미실행 | `INTEGRATION_BLOCKED` | 공통 Core Task Graph 구성 단계에서 선행 중단 |

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
- State Machine Validator·Diagram Check와 대표 14단계 E2E가 기준 Commit에서 통과한다.
- Backend 문의 생성·취소·증상 제출 Slice와 Mobile 실제 연동의 저장된 증거가 있다.
- Web 27개 파일·113개 Test, Lint, TypeScript와 Production Build가 Lockfile 환경에서 통과했다.
- 각 영역이 Mock과 실제 Runtime의 경계를 문서화하기 시작했다.

### 발표 동결 전 필수 해제 조건

1. Data Raw 정책 수정·QA 산출물을 Commit하고 발표 기준 Commit 갱신
2. Backend·AI·Mobile의 최신 Gate 결과 또는 명시적 환경 차단·발표 제외 승인
3. WBS 상태 현행화
4. 중앙 시연 단계표·Fallback·기능 상태표 작성 및 김은진 전달

위 조건이 충족되기 전 종합 상태는 **`INTEGRATION_BLOCKED / PRESENTATION_FREEZE_NOT_APPROVED`**로 유지한다.

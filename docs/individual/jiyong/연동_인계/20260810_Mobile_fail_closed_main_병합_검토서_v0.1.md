# Mobile Fail-Closed `main` 병합 검토서 v0.1

## 0. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-08-10 KST |
| 작성자 | 최지용 — Backend·DB |
| 검토 대상 | `origin/jeonghyun` Mobile fail-closed 후보 |
| 검토 시점 `origin/main` | `c6848a9ec170db37bdf10a0b46e860ef5677b072` |
| 후보 최종 Tip | `eb78910ce1b82a8d0fc3dd53dd5e9c43eb3b19f1` |
| Guidance fail-closed 핵심 Commit | `de36e048f7e992f797195201f621e0f2f79ea6a9` |
| Technician 계약·경계 문서 Commit | `205aae4` |
| 최신 `main` 병합 Commit | `f04d0d8` |
| 판정 | `APPROVE_WITH_CONDITIONS / PM_MERGE_REQUIRED` |

이 문서는 Mobile 코드를 수정하거나 `main` 병합을 실행하는 문서가 아니다.
현재 후보의 안전 경계와 병합 범위를 검토하여 윤승혁 PM에게 병합 여부를 요청하는 문서다.

## 1. 결론

`origin/jeonghyun`의 fail-closed 방향은 `main` 병합을 권장한다.

현재 `main`은 실제 방문기사 로그인 뒤에도 `FakeTechnicianVisitRepository`를 주입하여 합성 방문이 실제 Remote 결과처럼 보일 수 있다. 후보는 실제 로그인 경로를 `BlockedTechnicianVisitRepository`로 분리하고, 사용자가 명시적으로 선택한 Offline Preview에서만 Fake를 사용한다.

Guidance도 Remote에서 Fixture로 성공시키지 않고 `GUIDANCE_ROUTE_UNAVAILABLE`로 실패한다. 실제 Runtime이 없는 기능을 합성 성공으로 바꾸지 않는다는 프로젝트 원칙에 맞는다.

다만 후보 전체는 fail-closed 파일만 포함한 소규모 Patch가 아니다. `main` 대비 10개 Commit, 51개 파일의 Mobile·문서·개인 확장 변경을 포함하므로 PM은 최종 Tip 전체 범위를 확인한 뒤 병합해야 한다.

## 2. 기준선 확인

| 검증 | 결과 | 판정 |
|---|---|---|
| `origin/main`이 후보의 조상인지 | 예 | `PASS` |
| 후보의 최신 `main` 포함 | `f04d0d8`에서 `c6848a9` 포함 | `PASS` |
| 후보 고유 Commit | 10개 | 범위 검토 필요 |
| 후보 변경 파일 | 51개 | 범위 검토 필요 |
| 변경 최상위 범위 | `mobile/**` 40, `personal/**` 8, `docs/**` 3 | Backend·Web Production 변경 없음 |
| `git diff --check origin/main..origin/jeonghyun` | 오류 없음 | `PASS` |
| 후보 작성자 Gate | Build·Unit·APK·Galaxy 결과 `PASS` 보고 | `SELF_REPORTED` |
| 본 문서의 독립 Build 실행 | detached 후보에서 Gradle 9.5.0 준비 후 Android SDK 탐색 단계까지 실행 | `BLOCKED_ENV_ANDROID_SDK_MISSING` |

작성자 보고와 독립 QA를 구분한다. 후보 문서의 `PASS`를 본 검토서가 다시 실행해 확정한 것으로 해석하지 않는다.

### 2.1 독립 실행 기록

새 브랜치를 만들지 않고 `origin/jeonghyun@eb78910`을 임시 detached
작업선에서 검증했다. Gradle 9.5.0 Wrapper 다운로드와 프로젝트 설정 진입은
성공했으나, 이 PC에는 Android SDK 경로가 없어 Unit Test Task 의존성 계산 전에
중단됐다.

```text
SDK location not found.
Define ANDROID_HOME or mobile/local.properties sdk.dir.
```

이는 후보 Kotlin 코드의 Test 실패가 아니다. 동시에 독립 Test `PASS` 증거도
아니므로 판정은 `ENVIRONMENT_BLOCKED`로 유지한다. 임시 detached 작업선은 검증
후 제거했으며 `jiyong` 외 새 브랜치는 만들지 않았다.

## 3. 현재 `main`의 위험

현재 `main`의 Technician 앱은 다음 구조다.

```text
실제 Technician 로그인
→ TechnicianApp
→ FakeTechnicianVisitRepository
→ 합성 방문 목록·상세 성공
```

따라서 Backend에 기사 Visit 목록·상세 Runtime이 없어도 실제 로그인 화면에서 합성 방문이 표시될 수 있다. 이는 다음 판정을 흐린다.

- 실제 Backend 응답인지 여부
- 본인 배정 Visit인지 여부
- 401·403·404 오류인지 여부
- PostgreSQL 저장 데이터인지 여부
- Remote E2E가 완료됐는지 여부

Offline Preview 자체는 허용할 수 있지만 Remote 성공의 대체값으로 사용하면 안 된다.

## 4. 후보가 추가한 안전 경계

### 4.1 Technician Visit

후보는 다음 두 Repository를 분리한다.

| 경로 | Repository | 결과 |
|---|---|---|
| 실제 로그인·Remote | `BlockedTechnicianVisitRepository` | `VISIT_RUNTIME_UNAVAILABLE` 실패 |
| 사용자가 선택한 Offline Preview | `FakeTechnicianVisitRepository` | 합성 Fixture, 명시적 표시 |

실제 로그인 경로에서 목록·상세 실패 시 Fake로 자동 전환하지 않는다. 화면도 `실제 방문 API · BLOCKED_BY_BACKEND`를 표시하고 Remote 목록을 빈 상태로 유지한다.

### 4.2 Customer Guidance

후보의 `RemoteIntakeCustomerCareRepository.getGuidance()`는 Backend Guidance Route가 없을 때 다음 실패를 반환한다.

```text
code=GUIDANCE_ROUTE_UNAVAILABLE
retryable=false
```

Customer Guidance Fixture는 FAKE 또는 Offline Preview에만 남기며, Remote 접수 성공 뒤 합성 Guidance를 실제 서버 결과처럼 표시하지 않는다.

### 4.3 후보 테스트

후보에는 다음 경계 Test가 포함된다.

- Remote Guidance Route 부재 시 fail-closed
- 실제 Technician 경로의 목록·상세 fail-closed
- Offline Preview에서만 Visit Fixture 사용
- Galaxy Customer·Technician UI와 Remote Auth 회귀 결과 문서

## 5. 잔여 상태 코드 문제

fail-closed 후보는 실제 Remote와 Fake의 경계를 고치지만, 기존 Offline Fixture의 상태 코드를 모두 정리하지는 않는다.

현재 Mobile Fixture·표시 코드에는 다음 Legacy 값이 남아 있다.

- `COORDINATING`
- `WAITING_COMPLETION`

두 값은 canonical Visit 상태가 아니다.

```text
ASSIGNING
SCHEDULING
CONFIRMED
IN_PROGRESS
COMPLETED
FOLLOW_UP_REQUIRED
CANCELLED
```

특히 `WAITING_COMPLETION`을 `COMPLETED`로 변환하면 안 된다. 완료 대기와 완료는 다른 업무 상태다. `COMPLETION_PENDING`은 Inquiry 상태이며 Visit 상태와도 혼합하지 않는다.

이 잔여 문제는 기존 `main`에도 있고 후보가 새로 만든 회귀는 아니다. fail-closed 병합을 막기보다 Offline Fixture로 격리한 뒤 별도 Web·Mobile ACK와 계약 정렬로 해소한다.

## 6. 병합 범위 위험

후보는 fail-closed 외에도 다음을 포함한다.

- 고객 Subscription 목록·상세·선택 Remote 연결
- Customer Home 상태·오류 처리 확장
- Mobile Week5 Runtime Matrix·Blocker·E2E 문서
- Customer·Technician Android Test 확장
- `personal/mobile-extension/**` 자동 Gate와 검증 자료

따라서 `de36e04` 하나만 검토하고 최종 `origin/jeonghyun` 전체를 병합하면 안 된다. PM은 `eb78910` Tip의 전체 Diff와 Mobile 담당자의 최종 검증 범위를 함께 확인해야 한다.

## 7. Backend·DB 검토 판정

| 항목 | 판정 | 근거 |
|---|---|---|
| Remote Guidance의 Fixture 자동 성공 금지 | `ACCEPT` | Route 부재를 실패로 보존 |
| 실제 Technician 로그인과 Offline Fixture 분리 | `ACCEPT` | Remote/Fake 경계 명확 |
| 실제 Visit Runtime 완료 주장 | `REJECT` | 기사 목록·상세·시작·완료 Runtime 미구현 |
| 후보의 Build·Galaxy 결과 | `REVIEWED_SELF_REPORT` | 독립 실행은 Android SDK 부재로 차단 |
| Legacy Visit 상태 | `CHANGE_REQUIRED_SEPARATE` | canonical 외 값 존재 |
| `WAITING_COMPLETION → COMPLETED` 변환 | `PROHIBITED` | 의미 손실·완료 오판 |
| PM의 후보 전체 병합 | `APPROVE_WITH_CONDITIONS` | 안전 개선이지만 51파일 범위 |

## 8. PM 병합 조건

다음 조건을 충족하면 `origin/jeonghyun@eb78910`의 `main` 병합을 권장한다.

1. 양정현이 최종 후보 SHA와 51개 파일 전체가 의도한 Mobile 범위임을 확인한다.
2. 작성자 Build·Unit·APK·Galaxy 증거 경로를 PM과 김은진에게 전달한다.
3. 실제 Remote 경로에서 Guidance·Visit Fixture 자동 전환이 없음을 유지한다.
4. Offline Preview에는 합성 Fixture임을 계속 표시한다.
5. 병합 후에도 기사 Visit Runtime을 `IMPLEMENTED` 또는 Full E2E `PASS`로 표기하지 않는다.
6. Legacy Visit 상태는 별도 ACK 문서에 따라 정리하되 `WAITING_COMPLETION`을 `COMPLETED`로 변환하지 않는다.
7. 병합은 윤승혁 PM이 수행하고, 팀원은 병합 후 `main`을 Pull하여 검증한다.

## 9. 병합과 Visit 계약의 선후

fail-closed는 안전 경계이므로 기사 Visit API 계약 확정을 기다리지 않고 먼저 병합할 수 있다.

```text
Mobile fail-closed 후보 검토
→ PM main 병합
→ Web·Mobile canonical Visit 상태·DTO ACK
→ PM 계약 결정
→ Backend 기사 Visit Runtime 구현
→ PostgreSQL·Mobile 실연동 Smoke
```

fail-closed 병합은 실제 Visit Runtime 활성화 승인이 아니다. 실제 Remote Adapter로 교체하는 시점은 Backend Route·DTO·권한·Test·실행환경이 모두 준비된 뒤다.

## 10. 담당자별 후속

| 담당자 | 후속 |
|---|---|
| 양정현 | 후보 SHA·전체 범위·Gate 증거 확인, Legacy 상태 ACK |
| 한예나 | Web의 canonical Visit 상태·date-only DTO ACK |
| 최지용 | Backend 계약 원본 제시, 기사 Runtime은 승인 후 구현 |
| 김은진 | 후보 Test 증거와 병합 후 Fake/Remote 경계 독립 확인 |
| 윤승혁 | 후보 전체 Diff 검토와 `main` 병합 최종 결정 |

## 11. PM 회신 요청

```text
sender=윤승혁
receiver=최지용,양정현,한예나,김은진
scope=MOBILE_FAIL_CLOSED_MAIN_MERGE

candidate_tip=eb78910ce1b82a8d0fc3dd53dd5e9c43eb3b19f1
candidate_scope_review=ACK | CHANGE_REQUEST
fail_closed_boundary=APPROVE | CHANGE_REQUEST
full_branch_merge=APPROVE | HOLD | CHANGE_REQUEST
visit_runtime_completion_claim=REJECTED_ACK
waiting_completion_to_completed=PROHIBITED_ACK
merge_commit=<병합 후 SHA 또는 PENDING>
notes=<추가 조건>
```

## 12. 최종 판정

```text
mobile_fail_closed_safety=ACCEPT
candidate_contains_latest_main=PASS
diff_check=PASS
independent_mobile_test=BLOCKED_ENV_ANDROID_SDK_MISSING
candidate_scope=10_COMMITS_51_FILES
legacy_visit_status=SEPARATE_ACK_REQUIRED
backend_visit_runtime=NOT_IMPLEMENTED
pm_merge_recommendation=APPROVE_WITH_CONDITIONS
```

# Mobile Customer Guidance G2·G3 구현·검증 보고서

## 1. 문서 정보

| 항목 | 내용 |
| --- | --- |
| 작성일 | 2026-08-14 KST |
| 작성자 | 최지용 — Backend·DB, 당일 Mobile 임시 관할 |
| 기준선 | `main@ed4afa79c4f24393ec03740e4a2da10e0073288a` |
| 작업 브랜치 | `jiyong` |
| Mobile commit | `cde29fd7f69cf9f6e3fdeea015ee96531c3923a9` |
| PM 승인 | `TEMP_OWNER_EXCEPTION_TODAY_G2_G3_G4_G5=APPROVE_SCOPED_TODAY` |
| 현재 판정 | `MOBILE_G2_G3_CLIENT_READY / ACTUAL_RUNTIME_WAITING_G1` |

## 2. 결론

Mobile 고객 앱이 Backend Customer Guidance GET을 실제 Remote로 소비할 수 있도록 DTO·API·Repository·DI·ViewModel·UI를 최소 구현했다.

Unit 75건, Debug APK, AndroidTest APK, Galaxy Tab 설치·실행은 PASS했다. 다만 실제 AI Runtime과 팀 통합 PostgreSQL이 READY가 아니므로 실제 AI Guidance 표시와 상담 요청 G2·G3는 아직 실행하지 않았다.

## 3. 확정 계약 반영

- Endpoint: `GET /api/v1/me/inquiries/{inquiry_id}/guidance`
- 성공 응답은 Backend의 필수 16개 필드를 파싱한다.
- `evidence=[]`는 이번 P0의 정상 응답이다. Guidance 실패나 No-Evidence로 바꾸지 않는다.
- `409 AI_GUIDANCE_NOT_READY`는 새로고침 가능한 `NotReady` 상태로 표시한다.
- 타인·미존재 문의는 동일 404, 비고객 역할은 403을 Backend 계약대로 따른다.
- `risk_level`, `usage_guidance_status`, `next_action`, `allowed_actions`, `state_version`을 Client가 새로 추론하지 않는다.
- Guidance 200의 최신 `allowed_actions`를 화면에 우선 반영하고, 상담 요청 POST 직전에는 Snapshot을 다시 조회한다.
- 알 수 없는 안전 코드만 fail-closed로 상담 필요 상태로 바꾼다.
- Remote 오류를 Fake 성공으로 자동 전환하지 않는다.

## 4. 변경 파일

| 영역 | 파일 | 작업 |
| --- | --- | --- |
| DI | `mobile/core/src/main/java/com/skn29/watercare/core/WaterCareCore.kt` | Remote Repository에 고객 문의 Repository 주입 |
| Model | `mobile/core/src/main/java/com/skn29/watercare/core/model/CareModels.kt` | Guidance DTO·상태/버전·Mapper 정렬 |
| API | `mobile/core/src/main/java/com/skn29/watercare/core/network/WaterCareApi.kt` | Customer Guidance GET 추가 |
| Repository | `mobile/core/src/main/java/com/skn29/watercare/core/repository/CustomerInquiryRepository.kt` | 실제 GET 호출과 409 전용 정규화 |
| Repository | `mobile/core/src/main/java/com/skn29/watercare/core/repository/RemoteIntakeCustomerCareRepository.kt` | 하드코딩 차단 제거, Remote 호출 위임 |
| UI State | `mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceUiState.kt` | `NotReady` 추가 |
| ViewModel | `mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceViewModel.kt` | 200·409·fail-closed 분기 |
| UI | `mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceScreen.kt` | 재시도와 Public Evidence 미공개 안내 |
| Tests | Mobile Unit·AndroidTest 5개 | DTO·Mapper·Remote·409·실 Backend Smoke 정렬 |

## 5. 검증 결과

| 검증 | 결과 |
| --- | --- |
| `:core:test` | PASS |
| `:customer-app:testDebugUnitTest` | PASS |
| Unit 합계 | `75 passed / 0 failed / 0 skipped` |
| `:customer-app:assembleDebug` | PASS |
| `:customer-app:assembleDebugAndroidTest` | APK BUILD PASS, DEVICE TEST NOT RUN |
| `git diff --check` | PASS |
| Galaxy 연결 | `SM_X610`, ADB `device` |
| Port reverse | `tcp:8000 -> tcp:8000` |
| APK 설치 | `adb install -r -t` PASS |
| 앱 실행 | `com.skn29.watercare.customer/.MainActivity` Cold Start PASS |

실 Backend용 AndroidTest 진입점도 함께 고정했다.

- `login_subscriptionDetail_createAndSubmit_realBackend`: 새 Inquiry 생성·증상 제출 후 `CustomerG1SubmitSmoke` 로그로 ID·상태·버전을 남긴다.
- `customerGuidanceAndConsultationRequest_realBackend`: 지정 Inquiry의 Guidance 200과 상담 요청·Snapshot 재조회를 검증하고 `CustomerG2G3Smoke` 로그를 남긴다.
- `runRemoteSmoke=true`인데 `guidanceInquiryId`가 없으면 Skip이 아니라 실패하므로 false PASS를 막는다.

APK:

```text
mobile/customer-app/build/outputs/apk/debug/customer-app-debug.apk
SHA256=2D78BE71C863CF788BA949B992353EA1ECD72A38D53F0A58828200F85B09DBF1
SIZE=20445023 bytes
```

## 6. 실제 Runtime 미실행 사유

- `127.0.0.1:8001` AI Runtime이 내려가 있다.
- `127.0.0.1:8000` Backend Runtime도 검증 종료 시점에 내려가 있다.
- 현재 PC의 DB는 팀 통합 DB가 아닌 로컬 `waterbridge`다.
- 최지용 로컬 `waterbridge`의 G1-B readiness는 Crosswalk·Page Link·View·AI Readonly Role이 준비되지 않아 `BLOCKED`다.
- 팀 환경은 과거 `main@11d771a` QA에서 READY였으나 현재 final main 기준 재검증은 `PENDING`이다.
- 작성자 실행은 G1 readiness Audit Exit 1에서 중단했다. 실패한 AI 요청을 같은 멱등키로 재사용하지 않기 위해 최종 E2E Inquiry는 생성하지 않았다.

## 7. G1 READY 직후 실행

1. 최신 main과 Backend·AI·Mobile APK SHA를 기록한다.
2. Backend·AI `/health` 200을 Liveness로 확인한다.
3. G1-B Audit READY, 실제 Provider·pgvector·Schema와 동일 Inquiry DB 저장을 별도로 확인한다.
4. 새 고객 Inquiry를 생성해 증상 답변을 제출한다.
5. Backend DB의 AIRun·Guidance·Evidence와 Correlation ID를 확인한다.
6. Galaxy 고객 앱에서 Guidance 200, `evidence=[]`, 안전 문구와 허용 행동을 확인한다.
7. 상담 요청을 한 번 실행하고 성공 또는 409 후 최신 Snapshot을 재조회한다.
8. 같은 `inquiry_id`, 전후 `state_version`, `allowed_actions`, Correlation ID를 Web G4에 인계한다.

## 8. 완료 경계

- 완료: Mobile Client 구현, Unit, APK, AndroidTest 빌드, Galaxy 설치·실행.
- 미완료: 실제 AI 데이터 G2, 실제 상담 요청 G3, 동일 Inquiry G4·G5, 독립 QA.
- 금지: 현 결과를 전체 E2E PASS 또는 G1 PASS로 확대 해석.

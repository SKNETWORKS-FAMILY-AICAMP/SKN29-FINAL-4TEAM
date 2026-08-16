# E2E G1~G5 QA·PM 인계 Manifest

## 1. 기준 정보

| 항목 | 값 |
| --- | --- |
| 작성 기준 | 2026-08-14 KST |
| Git branch | `jiyong` |
| 시작 baseline | `ed4afa79c4f24393ec03740e4a2da10e0073288a` |
| Mobile candidate commit | `cde29fd7f69cf9f6e3fdeea015ee96531c3923a9` |
| Documentation commit | Mobile commit과 분리, `git log`의 다음 문서 Commit 기준 |
| Final main SHA | `PENDING_MERGE` |
| Mobile 임시 관할 | PM 승인됨, G2·G3 최소 범위 |
| Web 임시 관할 | 무수정 우선, 재현 결함만 최소 수정 |

## 2. 산출물

| 산출물 | 위치 | 상태 |
| --- | --- | --- |
| Mobile 구현 보고서 | `docs/individual/jiyong/20260814/20260814_Mobile_CustomerGuidance_G2_G3_구현검증보고서.md` | 작성 완료 |
| G2~G5 수행 보고서 | `docs/individual/jiyong/20260814/20260814_Mobile_Web_G2_G5_동일Inquiry_E2E_수행보고서.md` | G1 차단 기록 |
| QA·PM 요청서 | `docs/individual/jiyong/20260814/20260814_최지용_to_김은진_윤승혁_G1_G5_독립QA_PM최종판정_요청_v0.1.md` | 단일 세션 Runbook 보강 |
| Customer APK | `mobile/customer-app/build/outputs/apk/debug/customer-app-debug.apk` | Build·설치 PASS |

## 3. 변경 범위

```text
mobile/core/src/main/java/com/skn29/watercare/core/WaterCareCore.kt
mobile/core/src/main/java/com/skn29/watercare/core/model/CareModels.kt
mobile/core/src/main/java/com/skn29/watercare/core/network/WaterCareApi.kt
mobile/core/src/main/java/com/skn29/watercare/core/repository/CustomerInquiryRepository.kt
mobile/core/src/main/java/com/skn29/watercare/core/repository/RemoteIntakeCustomerCareRepository.kt
mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceScreen.kt
mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceUiState.kt
mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceViewModel.kt
mobile/core/src/test/java/com/skn29/watercare/core/model/CareModelsTest.kt
mobile/core/src/test/java/com/skn29/watercare/core/repository/RemoteIntakeCustomerCareRepositoryTest.kt
mobile/customer-app/src/test/java/com/skn29/watercare/customer/feature/customer/guidance/GuidanceViewModelTest.kt
mobile/customer-app/src/androidTest/java/com/skn29/watercare/customer/CustomerMinimumFlowTest.kt
mobile/customer-app/src/androidTest/java/com/skn29/watercare/customer/CustomerRemoteBackendSmokeTest.kt
```

Web Production 변경은 없다. `.codex_tmp/**`, Secret, Build output은 Git 후보에서 제외한다.

## 4. 작성자 검증

| 구분 | 결과 |
| --- | --- |
| Mobile Unit | 75 PASS |
| Mobile Debug APK | PASS |
| Mobile AndroidTest APK | BUILD PASS / 실제 G2·G3 DEVICE TEST는 G1 대기 |
| Galaxy SM_X610 설치·Cold Start | AUTHOR OBSERVED |
| ADB reverse 8000 | PASS |
| Web 표적 Unit | 31 PASS |
| Web Lint·Typecheck·Build | PASS |
| `git diff --check` | PASS |
| 실제 G1-A | NOT_RUN |
| 최지용 로컬 G1-B | BLOCKED |
| 팀 G1-B 과거 QA | READY AT `11d771a` |
| final main G1-B | REVALIDATION PENDING |
| 실제 G2~G5 | G1 readiness에서 중단, 새 Inquiry 생성 전 STOP |

APK SHA-256:

```text
2D78BE71C863CF788BA949B992353EA1ECD72A38D53F0A58828200F85B09DBF1
```

## 5. 기준 우선순위

- 현재 소스와 이 QA 요청서가 실행 기준이다.
- `mobile/README.md`의 Customer `Blocked by Backend` 설명은 Guidance Route 병합 전의 과거 상태이다.
- README를 이번 임시 관할 작업에서 고치지 않으며, Customer Guidance·상담 요청 검증에는 이 Manifest와 QA 요청서를 우선한다.
- 실제 실행은 Mobile commit이 main에 병합된 최종 40자리 SHA에서 다시 빌드한다.

## 6. QA 입력값

G1 READY 후 아래 값을 채운다.

```text
final_main_sha=
qa_revalidated_main_sha=
backend_base_url=
ai_base_url=
team_database_identity=
customer_apk_sha256=
apk_built_from_sha=
device_model=SM_X610
adb_state=
adb_reverse_8000=
mobile_remote_mode=
web_mock_off=
inquiry_id=
inquiry_code=
g2_before_state_version=
g3_after_state_version=
g4_final_state_version=
g5_observed_state_version=
g2_correlation_id=
g3_correlation_id=
g4_correlation_ids=
backend_log_path=
qa_evidence_root=
g1a_evidence_path=
g1b_evidence_path=
g2_g3_evidence_path=
g4_evidence_path=
g5_evidence_path=
```

Token, Password, DSN, API Key 원문은 이 문서·Git·채팅에 기록하지 않는다.

## 7. 인계 조건

- Backend·AI·Mobile·Web이 같은 final main SHA를 사용한다.
- 팀 통합 PostgreSQL, pgvector, Crosswalk, View, Role이 READY다.
- 실제 OpenAI·pgvector G1-A와 Backend 저장 G1-B가 PASS다.
- G2~G5가 같은 Inquiry로 실행됐다.
- 해당 조건 전 QA 요청서는 `DRAFT_NOT_READY_TO_SEND`다.
- `source_policy_review=PENDING`은 기술 Runtime Gate와 별도로 추적한다.

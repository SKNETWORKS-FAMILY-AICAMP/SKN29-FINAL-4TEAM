# 양정현 3주차 업무 지침서

> 프로젝트: 정수기 구독 고객 케어 및 A/S 업무 지원 시스템
> 
> 
> 대상 기간: 2026년 7월 27일 ~ 7월 31일
> 
> 필수 산출물 목표 완료일: **2026년 7월 29일**
> 
> 7월 30일~31일 운영 원칙: 신규 필수 화면을 무리하게 늘리기보다 **계약 반영, 연동 확인, 오류 수정, 테스트와 다음 주 진입 준비**를 우선한다.
> 

---

# 1. 담당자 기본 정보

| 항목 | 내용 |
| --- | --- |
| 담당자 | 양정현 |
| 담당 역할 | 모바일 애플리케이션 개발 담당 |
| 주관할 영역 | `mobile/**` 전체 |
| 주요 협업 영역 | `core/network/**`는 최지용, `customer/followup/**`·`customer/guidance/**`는 이동윤, `src/test/**`·`src/androidTest/**`·`mobile/gradle/**`는 김은진과 협업 |
| 담당 사용자 | 고객·방문기사. 단, 3주차에는 고객 최소 흐름을 우선한다. |
| 주요 협업 대상 | 최지용, 이동윤, 윤승혁, 김은진, 한예나 |
| 3주차 핵심 책임 | Android 실행 기반, 고객 최소 화면, 상태 관리, Mock·테스트 API 연동, AI 안내·공식 근거 표시 |
| 핵심 산출물 | 실행 가능한 앱, CUST-01·02·04 화면, API·AI DTO와 Mock, 로딩·오류 상태, 기술 결정·연동 이슈 기록 |

3주차에는 전체 `CUST-01~06`, `TECH-01~03`을 완성하지 않는다. Kotlin·Compose 학습은 실제 화면과 연동 코드를 만드는 데 필요한 범위로 한정하고, Hilt·Room·WorkManager·FCM·다중 모듈화는 필수 업무에서 제외한다.

---

# 2. 3주차 역할 목표

1. **7월 29일까지 실행 가능한 Android 프로젝트와 고객 최소 화면을 만든다.**
    
    Kotlin·Jetpack Compose·Material 3·Navigation Compose를 적용하고 `CUST-01`, `CUST-02`, `CUST-04`를 에뮬레이터에서 확인한다.
    
2. **백엔드·AI 계약을 모바일 DTO와 화면 상태로 표현한다.**
    
    공통 응답·오류, 문의 입력, 위험도, 사용 안내, EvidenceCard를 Mock 또는 테스트 API로 검증한다.
    
3. **7월 30일~31일에 실제 연동으로 교체할 수 있는 구조를 확보한다.**
    
    로딩·입력 오류·네트워크 오류·AI 실패·근거 없음 상태와 변경 지점을 문서화한다.
    

---

# 3. 3주차 필수 업무

## 3.1 Android 프로젝트 실행 환경과 최소 공통 구조 구성

### 작업 목적

고객·기사 화면을 확장할 수 있는 Android 기반을 만들되, 빈 계층과 다중 모듈을 미리 늘리지 않고 단일 `app` 모듈로 실행 가능성을 먼저 확보한다.

### 작업 위치

```
mobile/
├─ settings.gradle.kts
├─ build.gradle.kts
├─ gradle.properties
├─ gradle/wrapper/**
├─ app/build.gradle.kts
├─ app/src/main/AndroidManifest.xml
├─ app/src/main/java/com/skn29/watercare/app/
├─ app/src/main/java/com/skn29/watercare/core/designsystem/theme/
└─ README.md
```

### 세부 작업 지침

1. 팀이 합의한 JDK·Android SDK·Gradle 환경에서 Sync와 Debug 빌드를 확인한다.
2. package를 `com.skn29.watercare`로 통일하고 `MainActivity.kt`에서 Compose 앱을 실행한다.
3. Material 3 Theme와 기본 Typography를 구성한다. 위험도는 색상뿐 아니라 문구·아이콘으로도 구분한다.
4. Compose, Navigation, ViewModel, Coroutines, StateFlow, Kotlinx Serialization, Retrofit, OkHttp만 우선 적용한다.
5. API Base URL·Mock 사용 여부·빌드 환경은 `AppConfig.kt` 또는 BuildConfig로 분리하고 비밀값을 하드코딩하지 않는다.
6. 에뮬레이터에서 로컬 서버를 호출할 때 `10.0.2.2` 사용 여부와 HTTP 개발 설정을 확인한다.
7. `mobile/README.md`에 실행 환경, Gradle 명령, 에뮬레이터, API 주소, Mock 전환, 현재 구현 범위를 기록한다.
8. `local.properties`, 빌드 산출물, keystore, 실제 토큰이 Git에 포함되지 않는지 확인한다.
9. `feature/`, `core/` 아래에 실제 코드가 없는 빈 `data/domain/presentation` 디렉터리를 한꺼번에 만들지 않는다.

### 완료 기준

- `assembleDebug`가 성공하고 앱이 에뮬레이터에서 실행된다.
- package와 단일 `app` 구조가 디렉터리 설계와 일치한다.
- 필수 의존성이 충돌 없이 빌드된다.
- API 주소와 Mock 여부가 화면 코드에 흩어져 있지 않다.
- Hilt·Room·WorkManager·FCM 등 보류 기술이 불필요하게 포함되지 않는다.
- README 절차로 다른 팀원이 실행할 수 있다.

### 산출물

- 실행 가능한 `mobile/` 프로젝트
- Gradle·Manifest·Theme·환경 설정
- `mobile/README.md`
- 에뮬레이터 실행 및 빌드 증빙

---

## 3.2 고객 최소 화면과 Navigation 흐름 구현

### 작업 목적

제품·문의 진입점을 확인하고 증상을 입력한 뒤 AI 안내·공식 근거를 확인하는 최소 고객 흐름을 Compose로 구현한다. 3주차 핵심은 `CUST-01`, `CUST-02`, `CUST-04`이며 실제 API가 없어도 Mock으로 동작해야 한다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/
├─ app/navigation/{AppNavigation,CustomerNavigation}.kt
├─ core/navigation/{AppRoute,NavigationArgument}.kt
├─ feature/customer/home/{CustomerHomeScreen,CustomerHomeViewModel,CustomerHomeUiState}.kt
├─ feature/customer/intake/{SymptomIntakeScreen,SymptomIntakeViewModel,SymptomIntakeUiState}.kt
├─ feature/customer/guidance/{GuidanceScreen,GuidanceViewModel,GuidanceUiState}.kt
└─ feature/shared/{ProductInfoCard,EvidenceCard,StatusBadge}.kt
```

### 세부 작업 지침

1. Navigation 목적지와 `inquiryId`, `questionnaireSessionId`, `entryMode` 인자를 한 위치에서 관리한다. `inquiryId`는 Backend가 외부에 공개하는 UUID를 사용하고, 화면에 표시하는 `inquiryCode`와 구분한다. DB 내부 정수 PK는 모바일 Route에 사용하지 않는다.
2. CUST-03은 추가 질문 계약이 확정되기 전까지 Route 또는 Placeholder만 둘 수 있다.
3. `CUST-01`에는 합성 데이터 배지, `WPUJAC104DWH`, `WPU-JAC104D`, 관리 유형, 문진 상태, 진행 문의와 진입 버튼을 표시한다. 후속 모델·IoT·실제 개인정보는 숨긴다.
4. `CUST-02`에는 출수량 저하, 물맛·냄새 이상, 제품 누수, 냉·온수 온도 이상, 기타 증상을 복수 선택으로 제공하고 고객 원문·발생 조건·표시 문구를 입력받는다. 대표 증상 미선택 시 원문은 필수이며, 미확인 오류 코드의 의미를 앱에서 추정하지 않는다.
5. `CARE_PRECHECK`와 `ADHOC_INQUIRY`를 구분해 표시·제출할 수 있게 하되, 3주차에는 실제 문진 전체 문항과 케어 일정 계산을 구현하지 않는다.
6. `CUST-04`는 현재 행동, 위험도·사용 제한, 공식 안전조치, 상담 조건, 공식 근거, 증상 요약, 금지 행동 순으로 표시한다.
7. 일반·위험·근거 없음 Mock을 최소 제공한다. 위험·상담 필수 상태에는 해결됨·문의 종료 버튼을 표시하지 않고, 근거 없음에는 판단 보류·상담 필요를 우선한다.
8. Route 인자 오류, 뒤로 가기, 화면 재진입에서도 앱이 종료되거나 입력이 초기화되지 않도록 확인한다.

### 완료 기준

- `CUST-01 → CUST-02 → CUST-04` 이동이 동작한다.
- 세 화면이 에뮬레이터에서 표시되고 CUST-02 입력 검증이 동작한다.
- 일반·위험·근거 없음 상태를 Mock으로 확인할 수 있다.
- API 조회에는 공개 UUID를 사용하고 화면에는 별도 문의번호를 표시한다.
- 내부 정수 PK, `chunk_id`, 내부 경로, 원문 전체가 노출되지 않는다.
- 화면은 ViewModel·UiState 데이터로 렌더링된다.
- 화면명·필드·행동이 화면설계서와 충돌하지 않는다.

### 산출물

- 고객 Navigation Graph
- CUST-01·02·04 최소 화면
- Product·Status·Evidence 공통 UI 초안
- 화면 이동·입력 검증 증빙

---

## 3.3 ViewModel·StateFlow 상태 관리와 입력 직렬화

### 작업 목적

Composable에 API 호출과 검증 로직을 직접 넣지 않고 ViewModel·StateFlow로 분리하여 Mock과 실제 API를 교체할 수 있게 한다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/
├─ feature/customer/**/**ViewModel.kt
├─ feature/customer/**/**UiState.kt
├─ feature/customer/intake/data/{SymptomIntakeRequest,SymptomTopic,SymptomIntakeMapper}.kt
└─ core/model/{RiskLevel,UsageGuidanceStatus,WorkflowState,DataClassification}.kt
```

### 세부 작업 지침

1. 화면별 상태를 초기·로딩·내용·입력 오류·네트워크 오류·업무 오류·AI 실패·근거 없음으로 구분한다. 서로 모순되는 Boolean 여러 개보다 sealed 상태 또는 단일 UiState를 우선한다.
2. `SymptomIntakeUiState`에 선택 증상, 원문, 발생 조건, 표시 문구·오류 코드, `entryMode`, 제출 중 여부, 필드 오류와 전역 오류를 둔다.
3. 입력 변경·제출·재시도·오류 확인을 ViewModel 함수로 구분하고 Composable은 상태 표시와 이벤트 전달만 담당한다.
4. 제출은 현재 입력 Snapshot 확보 → 필수값 검증 → 로딩 → Repository 호출 → 성공 시 식별자 저장·이동 → 실패 시 입력 유지 순으로 처리한다.
5. 제출 중 버튼을 비활성화하고 실제 API에서는 `idempotency_key`와 함께 사용한다.
6. 요청 DTO를 Kotlinx Serialization로 직렬화하고, 서버 문자열과 Kotlin Enum 변환은 Mapper에 모은다. 정의되지 않은 코드를 기본값으로 숨기지 말고 `UNKNOWN` 또는 안전한 오류로 처리한다.
7. `UsageGuidanceStatus`는 다음 값을 기준으로 정의한다.
    - `NORMAL`
    - `PARTIAL_STOP`
    - `TOTAL_STOP`
    - `PENDING_CONSULTATION`
8. `UNKNOWN`은 서버에 전송하는 정상 상태가 아니라 알 수 없는 응답 코드를 안전하게 처리하기 위한 모바일 내부 값으로만 사용한다.
9. API·Mock 교체가 필요한 기능만 Repository 인터페이스를 만들고 불필요한 UseCase 계층은 생성하지 않는다.

### 완료 기준

- 입력·로딩·성공·실패가 ViewModel·StateFlow에서 관리된다.
- 재구성이나 제출 실패 뒤에도 입력값이 유지된다.
- 중복 제출이 차단된다.
- 요청 JSON 필드와 Enum이 `contracts/**`의 계약과 일치한다.
- 알 수 없는 위험도·사용 안내 코드에도 앱이 종료되지 않는다.
- Composable 내부에 Retrofit 직접 호출이 없다.

### 산출물

- 화면별 ViewModel·UiState
- 문진 요청 DTO·Mapper
- 공통 상태 모델
- 직렬화·오류 처리 확인 결과

---

## 3.4 백엔드 API와 Mock Repository 연동

### 작업 목적

실제 API가 늦어져도 모바일 개발이 멈추지 않도록 Repository 인터페이스와 Fake 구현을 준비하고, 가능한 경우 `/health` 또는 테스트 API를 Retrofit으로 호출한다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/
├─ core/network/{ApiClient,ApiResponse,ApiError,AuthInterceptor,TraceInterceptor}.kt
├─ feature/customer/home/data/**
├─ feature/customer/intake/data/**
└─ feature/customer/guidance/data/**

mobile/app/src/debug/java/com/skn29/watercare/mock/**
```

### 세부 작업 지침

1. `contracts/**`를 API·공통 코드의 최종 기준으로 사용한다. 계약 변경이 필요한 경우 계약 PR이 구현 PR보다 먼저 병합된 이후 실제 API 연동을 반영한다.
2. Retrofit·OkHttp에 Base URL, Serialization Converter, 연결·읽기 Timeout, 디버그 로그와 Interceptor 연결 지점을 구성한다. 로그에는 토큰과 개인정보를 남기지 않는다.
3. 공통 응답·오류는 `contracts/api/**`를 기준으로 DTO화하고, HTTP 성공과 업무 성공이 별도인지 확인한다.
4. 서버 상태, 고객 홈, 문의 시작·증상 제출, 안내 결과의 최소 API 또는 Fake Repository를 만든다.
5. 실제 API가 없으면 임시 경로를 확정 API처럼 사용하지 않고 `Fake`·`Mock`임을 이름과 문서에 표시한다. 화면은 Repository 인터페이스만 의존한다.
6. Access Token은 60분, Refresh Token은 최초 발급 시점부터 7일간 유효한 고정 만료 정책을 적용한다.
7. Access Token 만료로 401이 반환되면 유효한 Refresh Token으로 Access Token 재발급을 한 번 요청하고, 성공하면 기존 API 요청을 한 번 다시 수행한다.
8. Refresh Token이 만료·폐기되었거나 재발급에 실패하면 저장된 Token을 삭제하고 로그인 화면으로 이동한다.
9. 로그아웃 시 클라이언트의 Access Token과 Refresh Token을 삭제하고, 서버의 Refresh Token 폐기 API를 호출한다.
10. `Authorization`, `correlation_id`, `idempotency_key`, `state_version` 전달 방식을 계약에 따라 반영한다. 동일 쓰기 요청의 중복 터치와 재전송을 함께 고려한다.
11. API에서 받은 날짜·시간은 `+09:00`이 포함된 ISO 8601 형식을 사용한다. 모바일에서는 한국 시간으로 다시 9시간을 더하지 않고 화면 표시 형식만 변환한다.
12. 미인증·Token 만료는 401, 역할상 허용되지 않은 기능 접근은 403, 실제로 존재하지 않거나 다른 사용자가 소유한 리소스 접근은 404로 처리한다.
13. 상태 변경이 필요한 기능은 `/request-consultation`, `/start-consultation`, `/finalize` 등 행동별 Endpoint를 사용한다. 모바일에서 State Machine Event 이름이나 다음 상태를 직접 만들어 전송하지 않는다.
14. `state_version` 충돌로 409가 반환되면 응답의 최신 상태, `state_version`, `allowed_actions`를 UiState에 반영한다. 추가 상세 정보가 필요한 경우에만 상세 API를 다시 조회하며 사용자 입력값은 유지한다.
15. 연결 실패·Timeout, 400 입력 오류, 401·403·404, 409 상태 충돌, 5xx, 파싱 실패, AI 실패를 구분한다. 서버 원문을 그대로 노출하지 않고 오류 코드와 재시도 가능 여부를 사용자 문구로 Mapping한다.
16. 정상 출수량 저하, 위험 누수, 근거 없음, AI 실패, 네트워크 실패, 미지원 제품 Mock을 준비한다. 정상 업무 Mock은 `data/synthetic/fixtures/**`를 기준으로 생성된 모바일 Fixture를 사용하며, 생성된 Fixture를 직접 수정하지 않는다.
17. 대표 정상 Mock은 `SYN-JAC104-002`·`DEMO-INQ-002`와 공식 매뉴얼 38쪽을 사용한다. 모바일 전용 네트워크 실패·파싱 실패 Mock은 별도로 작성할 수 있다.

### 완료 기준

- 테스트 API 또는 Fake Repository 데이터가 화면에 표시된다.
- ViewModel이 Repository 인터페이스를 사용한다.
- 실제 API가 없어도 앱 전체가 컴파일된다.
- Access Token 만료 시 재발급 흐름과 Refresh Token 실패 시 재로그인 흐름을 처리할 수 있다.
- 401·403·404와 409 충돌을 구분한다.
- 409 응답의 최신 상태와 `allowed_actions`가 화면에 반영된다.
- API 일시 값이 중복 시간대 변환 없이 표시된다.
- 비밀 토큰·운영 주소·실제 개인정보가 코드와 Mock에 없다.
- 실제 API 교체 지점과 미제공 항목이 문서에 기록된다.

### 산출물

- Retrofit·OkHttp Client와 공통 응답·오류 모델
- 고객 기능 Repository와 Fake 구현
- 인증 갱신·로그아웃 처리 구조
- 정상·위험·근거 없음·실패 Mock
- `/health` 또는 테스트 호출 결과
- 백엔드 연동 이슈 목록

---

## 3.5 AI 결과·위험도·공식 근거 표시

### 작업 목적

백엔드가 검증한 고객용 AI 응답만 안전한 순서로 표시하고, 위험·근거 없음 상태에서 잘못된 자가조치를 노출하지 않도록 한다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/
├─ feature/customer/guidance/data/{GuidanceResponse,UsageGuidanceDto,EvidenceCardDto,GuidanceMapper}.kt
├─ feature/customer/guidance/{GuidanceScreen,GuidanceViewModel,GuidanceUiState}.kt
└─ feature/shared/{EvidenceCard,StatusBadge,WorkflowActionButton}.kt

mobile/app/src/debug/assets/mock/guidance-*.json
```

### 세부 작업 지침

1. `risk_level`, `usage_guidance_status`, `usage_guidance_message`, `restricted_functions`, `safe_actions`, `escalation_conditions`, `prohibited_actions`, `next_action`, `requires_consultation`, `evidence`, `allowed_actions`를 표시 모델에 반영한다.
2. 사용 안내 상태는 다음과 같이 표시한다.
    - `NORMAL`: 정상 사용 안내
    - `PARTIAL_STOP`: 일부 출수·기능 사용 중지 안내
    - `TOTAL_STOP`: 제품 전체 사용 중지와 안전 행동 안내
    - `PENDING_CONSULTATION`: 판단 보류·상담 필요 안내
3. EvidenceCard에는 문서명·버전·페이지·구조화 요약·검증 상태·데이터 분류와 백엔드 제공 공식 URL만 표시한다. 직접 다운로드 URL이 없으면 문서 정보만 보여준다.
4. `chunk_id`, `source_path`, `retrieval_text`, 원문 전체, 내부 RAG 경로와 앱이 임의 조립한 PDF URL은 숨긴다.
5. `general`·`caution`에는 공식 근거가 있는 안전한 조치만 제공하고, 분해·직접 수리·고장 확정 표현을 만들지 않는다.
6. `danger` 또는 상담 필수 상태는 사용 제한과 즉시 행동을 상단에 표시하고 일반 해결·종료 버튼을 제거한다. 누수·전기·화상 위험 문구는 계약된 안전 규칙만 사용한다.
7. 근거 없음은 `PENDING_CONSULTATION`으로 표시하고 사용 가능 여부나 자가조치를 추정하지 않는다.
8. AI 실패는 입력 유지, 재시도 가능 여부, 상담 Fallback만 사용자 문구로 안내하고 내부 오류·Stack Trace를 노출하지 않는다.
9. `official`, `team_designed`, `synthetic` 배지를 구분하고 공식 URL이 없으면 링크 버튼을 숨긴다.

### 완료 기준

- 일반·주의·위험·근거 없음·AI 실패 상태가 렌더링된다.
- `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`이 계약과 동일하게 처리된다.
- 위험 상태에서 일반 해결 버튼이 보이지 않는다.
- 근거 없음에서 임의 안내가 생성되지 않는다.
- EvidenceCard의 표시·비노출 필드가 계약과 일치한다.
- 알 수 없는 AI 코드도 안전한 오류·상담 상태로 처리된다.
- 이동윤·최지용이 사용 필드와 예시를 검토한다.

### 산출물

- Guidance DTO·Mapper·UiState
- 위험도·사용 안내·근거 카드 UI
- 상태별 Mock JSON
- 내부 필드 비노출 확인 기록

---

## 3.6 테스트·기술 결정 기록·7월 29일 제출

### 작업 목적

로컬 실험으로 끝나지 않도록 최소 테스트와 실행 문서를 남기고, 7월 29일까지 팀원이 검토할 수 있는 PR 상태로 만든다.

### 작업 위치

```
mobile/app/src/test/java/com/skn29/watercare/**
mobile/app/src/androidTest/java/com/skn29/watercare/**
mobile/docs/
├─ week3-mobile-decisions.md
├─ week3-api-ai-field-map.md
├─ week3-test-result.md
└─ week3-open-issues.md
```

### 세부 작업 지침

1. 문진 검증, 실패 후 입력 유지, 요청 JSON 직렬화, Guidance Mapper, 근거 없음 처리의 단위 테스트를 작성한다.
2. Access Token 만료 후 재발급 성공·실패, 403·404 구분, 409 충돌 응답 Mapping을 가능한 범위에서 단위 테스트한다.
3. 고객 홈 → 증상 입력 이동, 필수 입력 오류, danger 상태의 상담 문구 중 최소 1~2개의 Compose·Navigation 테스트를 작성한다.
4. 자동화하지 못한 화면은 수동 확인 절차, 입력값, 기대 결과와 실행 캡처를 남긴다.
5. 기술 결정 문서에 채택·보류 기술, 단일 모듈, Mock 교체 방식, 인증 갱신 방식, 테스트 범위와 다음 변경 가능성을 기록한다.
6. 필드 매핑 문서에 CUST-01·02·04의 화면 필드, 공개 UUID·업무 문의번호, 요청·응답 DTO, 공통 오류, 추적 Header와 `allowed_actions` 요구를 정리한다.
7. 테스트 결과에는 Android Studio·JDK·에뮬레이터, 빌드 명령, 자동·수동 테스트, Mock 시나리오, 실패 원인과 미완료 사항을 포함한다.
8. 7월 29일까지 빌드·화면·Mock·DTO·테스트 근거와 실제 API 미연동 범위가 포함된 PR을 만든다. PR에는 관련 요구사항·WBS, 변경 파일, 확인 방법과 후속 작업을 기록한다.
9. 7월 30일~31일에는 계약 변경, 빌드 오류, 위험·근거 표시 오류, 리뷰 의견을 우선 반영한다.

### 완료 기준

- 7월 29일까지 검토 가능한 PR 또는 공유 파일이 있다.
- Debug 빌드와 에뮬레이터 실행이 성공한다.
- 최소 테스트가 통과하거나 실패 원인이 기록되어 있다.
- 정상·위험·근거 없음 흐름을 재현할 수 있다.
- 인증 갱신·권한 오류·409 처리 방식이 문서화되어 있다.
- 기술 결정, API·AI 필드, 미해결 사항이 문서화되어 있다.
- 7월 30일~31일 수정 내역이 변경 기록에 남는다.

### 산출물

- 단위·Compose 테스트
- 기술 결정·필드 매핑·테스트 결과·이슈 문서
- 7월 29일 검토용 PR

---

# 4. 조기 완료 시 추가 업무

필수 업무·7월 29일 산출물·리뷰 대응이 끝난 뒤에만 착수한다. 아래 작업은 공통 협의 결과 Q-01~Q-10과 contracts/**에서 확정된 계약만으로 비교적 독립적으로 진행할 수 있다.

## 4.1 `CUST-03 AI 추가 질문` 최소 화면 선행 구현

### 해당 WBS

- T-035, FR-010~FR-014

### 착수 조건

- `missing_fields`, 질문 유형, 기존 답변, `SUBMIT_ANSWERS` Mock이 확정되어 있다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/feature/customer/followup/
├─ FollowUpQuestionScreen.kt
├─ FollowUpQuestionViewModel.kt
├─ FollowUpQuestionUiState.kt
└─ data/**
```

### 작업 내용

- 이미 답한 항목을 제외하고 필요한 질문만 표시한다.
- 계약된 입력 유형만 구현하고 제출 실패 시 답변을 유지한다.
- 처리 단계·재시도 초과·상담 필요 상태를 표시한다.
- 실제 AI가 없으면 Mock 질문과 응답만 사용한다.

### 완료 기준

- CUST-02의 `missing_fields` Mock에서 CUST-03으로 이동하고 답변 후 CUST-04로 이어진다.
- 중복 질문과 입력 유실이 없다.
- 이동윤이 Schema Mapping을 확인한다.

---

## 4.2 `CUST-06 문의 상세` 읽기 전용 골격 선행 구현

### 해당 WBS

- T-037, T-055, FR-026, FR-032~FR-034, FR-038

### 착수 조건

- Inquiry 상태, 현재 담당, 다음 단계, 방문 일정, `allowed_actions`, 완료 정책이 확정되어 있다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/feature/customer/inquirydetail/**
mobile/app/src/main/java/com/skn29/watercare/feature/shared/{StatusTimeline,WorkflowActionButton}.kt
```

### 작업 내용

- 문의 상태·담당 주체·다음 단계·고객 행동·사용 안내·근거를 표시한다.
- `COMPLETION_PENDING`, 담당자 확인 중, `RESOLVED`, `REOPENED` Mock을 구분한다.
- 버튼은 `allowed_actions`에 따라 표시한다.
- 실제 피드백 저장·상태 전환은 다음 주로 남긴다.

### 완료 기준

- 네 가지 상태가 표시되고 완료 대기와 최종 완료가 구분된다.
- 허용되지 않은 버튼이 보이지 않는다.
- 윤승혁·최지용이 완료 정책 표현을 확인한다.

---

## 4.3 공통 컴포넌트와 Compose UI 테스트 보강

### 해당 WBS

- T-045, T-050

### 착수 조건

- 두 화면 이상에서 반복되는 UI와 공통 코드가 확인되어 있다.

### 작업 위치

```
mobile/app/src/main/java/com/skn29/watercare/feature/shared/**
mobile/app/src/main/java/com/skn29/watercare/core/designsystem/**
mobile/app/src/androidTest/java/com/skn29/watercare/**
```

### 작업 내용

- EvidenceCard, StatusBadge, 로딩·오류, `WorkflowActionButton`을 재사용 컴포넌트로 정리한다.
- 위험도는 텍스트·아이콘·접근성 설명을 함께 제공한다.
- 내부 근거 필드 비노출, danger·no-evidence 문구, 허용 버튼을 UI 테스트로 확인한다.

### 완료 기준

- 중복 UI가 공통화되고 기존 화면이 동일하게 동작한다.
- 핵심 UI 테스트가 통과하며 김은진이 재현 방법을 확인한다.

---

# 5. 완료 기준 및 최종 체크리스트

## 5.1 7월 29일 필수 완료 기준

- [ ]  Gradle Sync·Debug 빌드·에뮬레이터 실행이 성공한다.
- [ ]  단일 `app` 모듈과 `com.skn29.watercare` 구조가 적용되어 있다.
- [ ]  CUST-01·02·04가 표시되고 최소 Navigation이 동작한다.
- [ ]  CUST-02 입력 검증과 실패 후 입력 유지가 동작한다.
- [ ]  ViewModel·StateFlow와 Kotlinx Serialization이 적용되어 있다.
- [ ]  Retrofit·OkHttp Client와 Repository 교체 지점이 있다.
- [ ]  정상·위험·근거 없음·AI 실패·네트워크 실패 Mock이 있다.
- [ ]  위험 상태에서 일반 해결·종료 버튼이 보이지 않는다.
- [ ]  EvidenceCard에 내부 경로·`chunk_id`·원문 전체가 노출되지 않는다.
- [ ]  최소 테스트 또는 수동 검증 결과가 있다.
- [ ]  README, 기술 결정, 필드 매핑, 미해결 사항이 작성되어 있다.
- [ ]  7월 29일까지 검토 가능한 PR 또는 공유 파일이 있다.

## 5.2 7월 30일~31일 최종 정리 기준

- [ ]  API·AI·State Machine 계약 변경이 DTO와 화면에 반영되었다.
- [ ]  다른 팀원이 README로 앱을 실행할 수 있다.
- [ ]  빌드·Navigation·위험·근거 표시 오류가 수정되었다.
- [ ]  Mock과 실제 API 차이가 문서에 표시되어 있다.
- [ ]  최지용·이동윤·김은진에게 연동·테스트 자료를 전달했다.
- [ ]  미완료 화면과 다음 주 작업이 Issue에 기록되어 있다.
- [ ]  필수 업무 완료 후에만 4장의 추가 업무를 시작했다.

## 5.3 모바일 역할 수행 시 주의사항

- 기술 학습은 실행 코드·화면·DTO·테스트로 남긴다.
- 전체 CUST·TECH 화면보다 CUST-01·02·04와 공통 기반을 우선한다.
- 상태와 버튼은 API의 `allowed_actions`를 사용하고 모바일에서 추정하지 않는다.
- AI 내부 응답 대신 백엔드가 검증한 고객용 필드만 표시한다.
- 미확인 오류·미지원 모델은 추정하지 않고 안전한 오류·상담 안내로 처리한다.
- 실제 개인정보·토큰·운영 비밀값은 Mock과 저장소에 넣지 않는다.
- FCM·Room·WorkManager·다중 모듈은 팀 합의와 필요가 생긴 뒤 적용한다.
- `contracts/**`, `tests/**`, `.github/**` 수정은 해당 주관할과 협의한다.

---

# 6. 지침서 작성 시 참고 문서

| 문서명 | 참고한 내용 | 지침서 반영 위치 |
| --- | --- | --- |
| `(WBS_29기_4팀) 정수기 구독 고객 케어 및 AS 업무 지원 시스템.md` | 모바일 후속 작업 T-033~T-037, 기사 화면 T-042~T-043, 공통 T-045, 통합·테스트 T-046·T-050, 사후 상태 T-055의 일정과 선후행 관계 | 2장 역할 목표, 3장 필수 업무 범위, 4장 조기 완료 추가 업무 |
| `(요구사항정의서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | 사전 문진·증상 입력, 추가 질문, 위험도, 사용 안내, 공식 근거, 상태 확인, 데이터·비기능·제약 요구사항 | 3.2~3.5 화면·상태·안전 기준, 5장 체크리스트 |
| `(화면설계서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | CUST-01~06 화면 목적·필드·행동·이벤트, EvidenceCardDTO, `allowed_actions`, 완료 정책 | 3.2 고객 화면, 3.5 AI·근거 표시, 4.1~4.2 추가 업무 |
| `업무계획서_애플리케이션(양정현)(1).md` | Kotlin·Compose·Navigation·ViewModel·StateFlow·Retrofit·AI 응답 표시 학습 및 실험 계획 | 1장 역할 해석, 3.1~3.4 기술 구성, 5.3 기술 도입 주의사항 |
| `프로젝트 디렉토리 구조.md` | 단일 `app` Gradle 모듈, `app/feature/core` 구조, 고객·기사 화면별 권장 파일과 모바일 네이밍 | 1장 관할, 3장 작업 위치와 파일명 전체 |
| `팀원별 관할 영역.md` | `mobile/**` 주관할 및 network·followup·guidance·test·gradle 협업 담당 | 1장 기본 정보 |
| `공통 개발 규칙.md` | 브랜치·Issue·커밋·PR, API 계약, 환경변수·보안, 오류·로그, 테스트·완료 기준 | 3.1 환경 구성, 3.4 API 처리, 3.6 테스트·PR, 5장 체크리스트 |
| `(기획서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | MVP 제품·사용자·대표 흐름, 고객 안전 안내와 상담·방문 연계 범위 | 2장 역할 목표, 3.2 화면 범위, 3.5 안전 표시 |
| `(수집데이터보고서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템(1).md` | 공식 매뉴얼 모델·버전·페이지, D세대와 후속 모델 분리, 근거 메타데이터 | 3.2 제품 Mock, 3.5 EvidenceCard와 대표 근거 시나리오 |
| `윤승혁_3주차_업무_지침서.md` | 3주차 공통 일정, 7월 29일 산출물 완료 원칙, 상태·API·AI 계약과 4주차 진입 기준 | 문서 전체의 일정·구조·상세 수준 통일 |

---

본 지침서의 필수 업무는 7월 29일까지 검토 가능한 결과물을 만드는 것을 기준으로 한다. 7월 30일~31일에는 계약 변경 반영, 빌드·테스트, 위험·근거 없음 표시 검토와 리뷰 수정에 우선 대응하며, 이 작업이 끝난 경우에만 4장의 추가 업무를 수행한다.
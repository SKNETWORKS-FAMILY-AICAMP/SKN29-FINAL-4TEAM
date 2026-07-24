# 4. Mobile 디렉토리 세부 구조

## 4.1 담당 화면

### 고객

| 화면 ID | 화면 |
|---|---|
| `CUST-01` | 고객 홈 |
| `CUST-02` | 사전 문진·증상 입력 |
| `CUST-03` | AI 추가 질문 |
| `CUST-04` | 공식 근거·안전 안내 |
| `CUST-05` | 자가조치 결과·상담 요청 |
| `CUST-06` | 문의 상태·처리 결과·후속 확인 |

### 방문기사

| 화면 ID | 화면 |
|---|---|
| `TECH-01` | 기사 업무 목록 |
| `TECH-02` | 방문 상세·사전 점검 리포트 |
| `TECH-03` | 방문 결과 등록 |

## 4.2 구조 선택

현재 MVP에서는 **단일 `app` Gradle 모듈 + 기능 중심 패키지 구조**를 사용한다.

```text
mobile/                                             # Kotlin·Jetpack Compose Android 프로젝트
└─ app/                                             # 실제 Android 애플리케이션을 빌드하는 단일 Gradle 모듈
   └─ src/main/java/com/skn29/watercare/            # Kotlin 운영 코드 기본 패키지
      ├─ app/                                       # 앱 시작·세션·Navigation 구성
      ├─ feature/                                   # 고객·기사 화면별 기능
      └─ core/                                      # 네트워크·저장소·디자인 시스템 등 공통 기능
```

초기 MVP에서는 다음 구조를 사용하지 않는다.

```text
사용하지 않는 구조
├─ feature-customer/                                # 고객 기능 전용 별도 Gradle 모듈
├─ feature-technician/                              # 기사 기능 전용 별도 Gradle 모듈
├─ core-network/                                    # 네트워크 전용 별도 Gradle 모듈
└─ 모든 기능의 data/domain/presentation 선생성     # 실제 코드 없이 빈 계층만 늘어나는 구조
```

기능별 디렉토리에는 우선 화면, ViewModel, UI 상태 파일을 함께 둔다.

```text
feature/customer/home/
├─ CustomerHomeScreen.kt
├─ CustomerHomeViewModel.kt
└─ CustomerHomeUiState.kt
```

API DTO, Repository, UseCase 등 독립 계층이 실제로 필요해지는 기능만 이후에 `data/`, `domain/`, `presentation/`으로 분리한다.

## 4.3 상세 구조

```text
mobile/                                             # Kotlin·Jetpack Compose Android 프로젝트
│
├─ app/                                             # 실제 Android 애플리케이션 모듈
│  ├─ src/                                         # Android 운영·테스트 Source Set
│  │  ├─ main/                                     # 운영 코드와 Android 리소스
│  │  │  ├─ java/com/skn29/watercare/              # Kotlin 기본 패키지
│  │  │  │  │
│  │  │  │  ├─ app/                                # 앱 시작·역할 분기·전체 구성
│  │  │  │  │  ├─ WaterCareApplication.kt          # Android Application 진입점
│  │  │  │  │  ├─ MainActivity.kt                  # Compose UI 실행 Activity
│  │  │  │  │  ├─ navigation/                      # 역할별 화면 이동 구조
│  │  │  │  │  │  ├─ AppNavigation.kt              # 전체 Navigation Graph 조립
│  │  │  │  │  │  ├─ AuthNavigation.kt             # 로그인·역할 확인 흐름
│  │  │  │  │  │  ├─ CustomerNavigation.kt         # CUST-01~06 고객 화면 흐름
│  │  │  │  │  │  └─ TechnicianNavigation.kt       # TECH-01~03 기사 화면 흐름
│  │  │  │  │  ├─ UserSession.kt                    # 사용자 ID·역할·로그인 상태
│  │  │  │  │  ├─ SessionManager.kt                 # 세션 조회·갱신·초기화
│  │  │  │  │  └─ AppConfig.kt                      # API 주소·빌드 환경 공개 설정
│  │  │  │  │
│  │  │  │  ├─ feature/                            # 역할·화면별 기능 코드
│  │  │  │  │  ├─ auth/                            # 가상 로그인·로그아웃·역할 확인
│  │  │  │  │  │  ├─ LoginScreen.kt                # 가상 로그인 Compose 화면
│  │  │  │  │  │  ├─ LoginViewModel.kt             # 로그인 요청·화면 상태 관리
│  │  │  │  │  │  └─ LoginUiState.kt               # 로그인 화면 상태
│  │  │  │  │  │
│  │  │  │  │  ├─ customer/                        # 고객용 CUST-01~06 기능
│  │  │  │  │  │  ├─ home/                         # CUST-01 고객 홈
│  │  │  │  │  │  │  ├─ CustomerHomeScreen.kt      # 제품·케어·진행 문의 화면
│  │  │  │  │  │  │  ├─ CustomerHomeViewModel.kt   # 고객 홈 데이터 조회·상태 관리
│  │  │  │  │  │  │  └─ CustomerHomeUiState.kt     # 고객 홈 화면 상태
│  │  │  │  │  │  ├─ intake/                       # CUST-02 문진·증상 입력
│  │  │  │  │  │  │  ├─ SymptomIntakeScreen.kt     # 사전 문진·증상 입력 화면
│  │  │  │  │  │  │  ├─ SymptomIntakeViewModel.kt  # 임시 저장·증상 제출 처리
│  │  │  │  │  │  │  └─ SymptomIntakeUiState.kt    # 문진·증상 입력 화면 상태
│  │  │  │  │  │  ├─ followup/                     # CUST-03 AI 추가 질문
│  │  │  │  │  │  │  ├─ FollowUpQuestionScreen.kt  # 추가 질문과 답변 입력 화면
│  │  │  │  │  │  │  ├─ FollowUpQuestionViewModel.kt # 질문 조회·답변 제출 처리
│  │  │  │  │  │  │  └─ FollowUpQuestionUiState.kt # 추가 질문 화면 상태
│  │  │  │  │  │  ├─ guidance/                     # CUST-04 근거·안전 안내
│  │  │  │  │  │  │  ├─ GuidanceScreen.kt          # 위험도·사용 안내·공식 근거 화면
│  │  │  │  │  │  │  ├─ GuidanceViewModel.kt       # 분석 결과·근거 조회 처리
│  │  │  │  │  │  │  └─ GuidanceUiState.kt         # 안내 화면 상태
│  │  │  │  │  │  ├─ actionresult/                 # CUST-05 자가조치 결과
│  │  │  │  │  │  │  ├─ ActionResultScreen.kt      # 조치 수행 여부·결과 입력 화면
│  │  │  │  │  │  │  ├─ ActionResultViewModel.kt   # 결과 저장·상담 요청 처리
│  │  │  │  │  │  │  └─ ActionResultUiState.kt     # 조치 결과 화면 상태
│  │  │  │  │  │  └─ inquirydetail/                # CUST-06 문의 상세·후속 확인
│  │  │  │  │  │     ├─ InquiryDetailScreen.kt     # 처리 결과·상태 이력·해결 피드백 화면
│  │  │  │  │  │     ├─ InquiryDetailViewModel.kt  # 문의 조회·해결 여부·재개 처리
│  │  │  │  │  │     └─ InquiryDetailUiState.kt    # 문의 상세 화면 상태
│  │  │  │  │  │
│  │  │  │  │  ├─ technician/                      # 방문기사용 TECH-01~03 기능
│  │  │  │  │  │  ├─ worklist/                     # TECH-01 기사 업무 목록
│  │  │  │  │  │  │  ├─ TechnicianWorkListScreen.kt # 배정 방문 목록·필터 화면
│  │  │  │  │  │  │  ├─ TechnicianWorkListViewModel.kt # 방문 목록 조회·정렬 처리
│  │  │  │  │  │  │  └─ TechnicianWorkListUiState.kt # 기사 업무 목록 화면 상태
│  │  │  │  │  │  ├─ visitdetail/                  # TECH-02 방문 상세·사전 리포트
│  │  │  │  │  │  │  ├─ VisitDetailScreen.kt       # 방문 정보·근거·사전 리포트 화면
│  │  │  │  │  │  │  ├─ VisitDetailViewModel.kt    # 방문 조회·방문 시작 처리
│  │  │  │  │  │  │  └─ VisitDetailUiState.kt      # 방문 상세 화면 상태
│  │  │  │  │  │  └─ visitresult/                  # TECH-03 방문 결과 등록
│  │  │  │  │  │     ├─ VisitResultScreen.kt       # 원인·조치·교체·처리 상태 입력 화면
│  │  │  │  │  │     ├─ VisitResultViewModel.kt    # 결과 임시 저장·완료 처리
│  │  │  │  │  │     └─ VisitResultUiState.kt      # 방문 결과 화면 상태
│  │  │  │  │  │
│  │  │  │  │  └─ shared/                          # 고객·기사 화면에서 공유하는 업무 UI
│  │  │  │  │     ├─ EvidenceCard.kt               # 공식 근거 요약·출처 버튼 카드
│  │  │  │  │     ├─ ProductInfoCard.kt            # 제품·구독·관리 이력 카드
│  │  │  │  │     ├─ StatusBadge.kt                # 문의·방문·위험 상태 배지
│  │  │  │  │     ├─ StatusTimeline.kt             # 상태 변경 이력 타임라인
│  │  │  │  │     └─ WorkflowActionButton.kt       # allowed_actions 기반 행동 버튼
│  │  │  │  │
│  │  │  │  └─ core/                               # 특정 업무에 속하지 않는 모바일 공통 코드
│  │  │  │     ├─ network/                         # `/api/v1` REST API 공통 통신
│  │  │  │     │  ├─ ApiClient.kt                  # 백엔드 API 요청 Client
│  │  │  │     │  ├─ ApiResponse.kt                # success·data·error 공통 Wrapper
│  │  │  │     │  ├─ ApiError.kt                   # 업무 오류 코드·사용자 메시지 모델
│  │  │  │     │  ├─ Pagination.kt                 # page·size·total 목록 응답 모델
│  │  │  │     │  ├─ AuthInterceptor.kt            # JWT 인증 Header 처리
│  │  │  │     │  └─ TraceInterceptor.kt           # correlation_id·멱등성 Header 처리
│  │  │  │     ├─ storage/                         # 기기 내부 최소 상태 저장
│  │  │  │     │  ├─ SessionStorage.kt             # 토큰·역할·사용자 정보 저장
│  │  │  │     │  └─ DraftStorage.kt               # 작성 중 문진·결과 임시 보존
│  │  │  │     ├─ designsystem/                    # 공통 Jetpack Compose UI
│  │  │  │     │  ├─ theme/                        # 색상·글꼴·크기·Material Theme
│  │  │  │     │  ├─ component/                    # 버튼·입력·카드·배지·모달
│  │  │  │     │  └─ feedback/                     # 로딩·빈 상태·오류·성공 UI
│  │  │  │     ├─ navigation/                      # 화면 경로와 전달 인자
│  │  │  │     │  ├─ AppRoute.kt                   # 전체 화면 목적지 타입
│  │  │  │     │  └─ NavigationArgument.kt         # inquiryId·visitId 등 전달 인자
│  │  │  │     ├─ model/                           # 여러 기능에서 공유하는 기본 모델
│  │  │  │     │  ├─ UserRole.kt                   # CUSTOMER·TECHNICIAN 역할
│  │  │  │     │  ├─ RiskLevel.kt                  # general·caution·danger 위험도
│  │  │  │     │  ├─ WorkflowState.kt              # 문의·방문 상태 표현 모델
│  │  │  │     │  └─ DataClassification.kt         # official·team_designed·synthetic
│  │  │  │     ├─ platform/                        # Android 플랫폼 기능 래퍼
│  │  │  │     │  ├─ ExternalBrowser.kt            # 공식 출처 URL 외부 열기
│  │  │  │     │  └─ NetworkMonitor.kt             # 네트워크 연결 상태 확인
│  │  │  │     └─ util/                            # 공통 변환·검증 도구
│  │  │  │        ├─ DateFormatter.kt              # ISO 8601 날짜·시간 표시 변환
│  │  │  │        └─ IdentifierValidator.kt        # inquiryId·visitId 등 식별자 검증
│  │  │  │
│  │  │  ├─ res/                                   # Android 리소스
│  │  │  │  ├─ drawable/                           # 벡터 아이콘·배경 리소스
│  │  │  │  ├─ mipmap/                             # 앱 런처 아이콘
│  │  │  │  ├─ values/                             # 문자열·색상·테마 공통 리소스
│  │  │  │  └─ xml/                                # 네트워크 보안·백업 설정
│  │  │  └─ AndroidManifest.xml                    # 인터넷 권한·앱 구성요소 선언
│  │  │
│  │  ├─ test/                                     # JVM 단위 테스트
│  │  │  └─ java/com/skn29/watercare/              # ViewModel·변환·검증 테스트
│  │  └─ androidTest/                              # 에뮬레이터·기기 기반 테스트
│  │     └─ java/com/skn29/watercare/              # Compose UI·Navigation 테스트
│  │
│  ├─ build.gradle.kts                             # 앱 모듈 의존성·빌드 설정
│  ├─ proguard-rules.pro                           # Release 난독화·최적화 규칙
│  └─ README.md                                    # 앱 모듈 구조·구현 규칙
│
├─ gradle/                                         # Gradle Wrapper와 Version Catalog
│  ├─ wrapper/                                     # Gradle Wrapper 실행 파일
│  └─ libs.versions.toml                           # Android·Kotlin 의존성 버전 중앙 관리
├─ build.gradle.kts                                # 프로젝트 공통 Gradle 설정
├─ settings.gradle.kts                             # `app` 모듈 등록
├─ gradle.properties                               # 공통 Gradle·Android 빌드 옵션
├─ gradlew                                         # macOS·Linux용 Gradle 실행 파일
├─ gradlew.bat                                     # Windows CMD용 Gradle 실행 파일
├─ local.properties.example                        # SDK 경로·로컬 개발 설정 예시
├─ .gitignore                                      # APK·빌드 결과·로컬 설정 제외
└─ README.md                                       # 설치·실행·빌드·테스트 안내
```

## 4.4 기능 내부 기본 형식과 확장 기준

초기에는 각 화면 기능에 다음 세 파일을 기본으로 둔다.

```text
feature/<role>/<feature>/
├─ <Feature>Screen.kt                              # Compose 화면
├─ <Feature>ViewModel.kt                           # API 호출·입력·화면 상태 처리
└─ <Feature>UiState.kt                             # 로딩·성공·오류·입력 상태
```

화면 내부에서만 사용하는 작은 Composable은 같은 디렉토리에 추가한다.

```text
feature/customer/home/
├─ CustomerHomeScreen.kt
├─ CustomerHomeViewModel.kt
├─ CustomerHomeUiState.kt
├─ CareScheduleSection.kt
└─ ActiveInquirySection.kt
```

다음 조건이 생겼을 때 해당 기능만 계층을 분리한다.

### `data/` 분리 기준

- API 요청·응답 DTO가 화면 모델과 크게 다르다.
- Remote 데이터와 Local 저장 데이터를 함께 사용한다.
- Mapper 또는 Repository 구현체가 둘 이상 필요하다.
- 같은 API 접근 로직을 여러 ViewModel에서 공유한다.

```text
feature/customer/inquirydetail/
├─ data/
│  ├─ InquiryDetailDto.kt
│  ├─ InquiryDetailMapper.kt
│  └─ InquiryDetailRepository.kt
├─ InquiryDetailScreen.kt
├─ InquiryDetailViewModel.kt
└─ InquiryDetailUiState.kt
```

### `domain/` 분리 기준

- Android UI와 무관한 업무 규칙이 복잡해진다.
- 여러 화면에서 동일한 UseCase를 사용한다.
- 독립적인 단위 테스트가 필요한 계산·검증 로직이 생긴다.

```text
feature/customer/inquirydetail/
├─ domain/
│  ├─ InquiryDetail.kt
│  └─ GetInquiryDetailUseCase.kt
├─ InquiryDetailScreen.kt
├─ InquiryDetailViewModel.kt
└─ InquiryDetailUiState.kt
```

### `presentation/` 분리 기준

- 한 기능의 화면·컴포넌트·ViewModel 파일이 7~10개 이상으로 늘어난다.
- 화면 코드와 데이터·업무 로직 파일을 한 디렉토리에서 찾기 어려워진다.

```text
feature/customer/inquirydetail/
├─ data/
├─ domain/
└─ presentation/
   ├─ InquiryDetailScreen.kt
   ├─ InquiryDetailViewModel.kt
   ├─ InquiryDetailUiState.kt
   └─ component/
```

모든 기능을 동시에 계층화하지 않고 복잡도가 증가한 기능만 단계적으로 분리한다.

## 4.5 역할별 Navigation

```text
로그인
│
├─ CUSTOMER
│  └─ CustomerNavigation
│     ├─ CUST-01 고객 홈
│     ├─ CUST-02 문진·증상 입력
│     ├─ CUST-03 추가 질문
│     ├─ CUST-04 근거·안전 안내
│     ├─ CUST-05 조치 결과
│     └─ CUST-06 문의 상세·후속 확인
│
└─ TECHNICIAN
   └─ TechnicianNavigation
      ├─ TECH-01 업무 목록
      ├─ TECH-02 방문 상세
      └─ TECH-03 방문 결과
```

- 저장된 역할과 화면 Graph가 일치하지 않으면 진입을 차단한다.
- 실제 데이터 접근 권한은 백엔드가 최종 검증한다.
- `CUST-02`는 `CARE_PRECHECK`과 `ADHOC_INQUIRY` 진입 모드를 하나의 화면에서 구분한다.
- `inquiryId`, `visitId` 등 화면 이동 식별자는 `NavigationArgument.kt`에서 공통 관리한다.
- 화면 경로는 문자열을 화면마다 직접 작성하지 않고 `AppRoute.kt`를 기준으로 관리한다.

## 4.6 Mobile State Machine 원칙

모바일은 문의·방문 상태를 자체 계산하지 않고 백엔드 응답을 기준으로 업무 버튼을 구성한다.

```text
백엔드 응답
├─ current_state
├─ allowed_actions
├─ state_version
├─ current_assignee
├─ next_action
└─ customer_action_required

모바일
├─ 현재 상태와 다음 행동 표시
└─ allowed_actions에 포함된 행동만 버튼으로 표시·활성화
```

상태 전환 요청에는 다음 값을 사용한다.

```text
state_version       # 오래된 화면에서 발생한 동시 수정 방지
idempotency_key     # 중복 터치·재전송에 따른 중복 처리 방지
correlation_id      # 모바일→백엔드→AI 처리 흐름 추적
```

- 모바일은 `allowed_actions`에 없는 이벤트를 임의로 전송하지 않는다.
- 상태 전환 성공 후 응답으로 받은 최신 상태와 `state_version`을 화면에 반영한다.
- 동시 수정 오류가 발생하면 기존 입력을 보존한 뒤 최신 문의·방문 정보를 다시 조회한다.
- AI 처리 상태는 문의 상태와 구분하여 로딩·진행 문구에만 사용한다.

## 4.7 입력 보존과 오류 처리

고객 문진, 자가조치 결과와 기사 방문 결과는 저장 실패나 네트워크 오류가 발생해도 사라지지 않아야 한다.

```text
<Feature>UiState.kt
└─ 현재 화면 입력·선택값·저장 상태 유지

<Feature>ViewModel.kt
└─ 화면 재구성·회전 중 상태 유지

core/storage/DraftStorage.kt
└─ 화면 이탈·앱 재실행에 대비한 최소 임시 저장
```

임시 저장 대상은 사용자가 다시 작성하기 어려운 입력으로 제한한다.

```text
임시 저장 권장
├─ CUST-02 문진·증상 입력
├─ CUST-05 자가조치 수행 결과
└─ TECH-03 방문 점검·조치 결과

임시 저장 제외
├─ 서버에서 다시 조회할 수 있는 제품·문의 상세
├─ 공식 근거 원문
└─ 토큰 외 불필요한 민감정보
```

공통 오류 상태는 `core/designsystem/feedback/`에서 제공한다.

```text
LoadingContent          # 조회·AI 분석 진행 중
EmptyContent            # 문의·배정 방문이 없음
ErrorContent            # 조회·저장 실패
OfflineContent          # 네트워크 연결 없음
AccessDeniedContent     # 역할·권한 오류
SaveStatusContent       # 저장 중·저장 완료·저장 실패
```

- 저장 실패 시 입력을 유지하고 재시도 버튼을 제공한다.
- 세션 만료 시 입력을 보존한 상태로 다시 로그인하도록 안내한다.
- 복구 불가능한 오류와 사용자 입력 오류를 구분해 표시한다.
- 백엔드 오류 코드와 사용자 표시 문구는 `ApiError.kt`에서 연결한다.

## 4.8 Mobile 공식 근거 처리 원칙

모바일은 백엔드가 조립한 `EvidenceCardDTO`만 사용한다.

```text
표시 가능
├─ 문서명
├─ 문서 버전
├─ 근거 페이지
├─ 항목명
├─ 구조화된 근거 요약
├─ 위험도
├─ 검증 상태
├─ 안전하게 수행 가능한 조치
├─ 상담 전환 조건
└─ 백엔드가 제공한 공식 URL
```

```text
표시·저장·전달 금지
├─ source_path
├─ ManualPage.text 원문 전체
├─ retrieval_text
├─ Vector Store 내부 식별 정보
├─ RAG 내부 저장 경로
└─ 앱에서 임의 조합한 공식 PDF URL
```

- 공식 출처 버튼은 백엔드가 반환한 `source_landing_url`을 기본으로 사용한다.
- 검증된 `source_direct_download_url`이 존재하는 경우에만 PDF 열기 버튼을 제공한다.
- URL 열기는 `core/platform/ExternalBrowser.kt`를 통해 처리한다.
- 직접 링크 열기에 실패하면 공식 랜딩 페이지로 이동할 수 있도록 안내한다.
- 고객 화면에서는 내부 추적용 `chunk_id`를 표시하지 않는다.
- 공식 근거와 팀 설계·합성 시연 데이터는 배지로 구분한다.

# 정수기 구독 고객 케어 및 A/S 업무 지원 시스템

## 디렉토리 구조 설계안

> 대상 저장소: `SKN29-FINAL-4TEAM`
>
> 작성 범위
>
> 1. 전체 디렉토리 골격
> 2. `web/` 세부 구조
> 3. `mobile/` 세부 구조
> 4. `ai/` 세부 구조
> 5. `contracts/` 세부 구조
> 6. `data/` 세부 구조
> 7. `infra/` 및 CI/CD 세부 구조
> 8. `scripts/`, `tests/`, `docs/` 세부 구조
>
> 반영 기준
>
> - 웹: React + TypeScript + Vite + React Router
> - 모바일: Kotlin + Jetpack Compose 기반 Android Native
> - 백엔드: Python + Django + Django REST Framework
> - 관계형 DB: PostgreSQL
> - 배포: Docker·Kubernetes·GitHub Actions 기반 확장 가능 구조
> - 공통 개발 규칙의 기술 영역별 분리, 기능 중심 프론트엔드, 영역별 공통 코드, 별도 테스트 구조 반영


---

> 이 문서의 디렉토리 트리에는 **모든 디렉토리와 모든 파일**에 용도 주석을 표시한다.

# 1. 네이밍 규칙

## 1.1 Web

| 대상 | 규칙 | 예시 |
|---|---|---|
| React 컴포넌트·페이지·레이아웃 | `PascalCase` | `InquiryDetailPage.tsx`, `EvidenceCard.tsx` |
| React Hook | `camelCase`, `use` 접두사 | `useInquiryDetail.ts` |
| 일반 TypeScript 파일 | `camelCase` | `httpClient.ts`, `routePaths.ts` |
| Web 디렉토리 | `kebab-case` | `inquiry-detail/`, `workflow-action/` |
| 상수 식별자 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 테스트 파일 | 원본 파일명 + `.test` | `EvidenceCard.test.tsx` |

## 1.2 Mobile

| 대상 | 규칙 | 예시 |
|---|---|---|
| Kotlin 클래스·Compose·ViewModel·UseCase 파일 | `PascalCase` | `CustomerHomeScreen.kt`, `VisitResultViewModel.kt` |
| Kotlin 패키지·디렉토리 | 영문 소문자 | `feature.customer.home`, `core.network` |
| 상수 식별자 | `UPPER_SNAKE_CASE` | `DEFAULT_PAGE_SIZE` |
| Android 리소스 파일명 | `snake_case` | `ic_warning.xml`, `network_security_config.xml` |

## 1.3 공통 원칙

- 파일명은 언어·프레임워크 관례를 우선한다.
- 디렉토리와 파일은 기술 이름보다 **책임과 기능**을 기준으로 명명한다.
- `retrofit/`, `hilt/`, `room/`처럼 특정 라이브러리 이름을 디렉토리에 직접 사용하지 않는다.
- 복잡한 규칙과 의도를 설명할 때만 주석을 작성한다.

---

# 2. 전체 디렉토리 골격

```text
SKN29-FINAL-4TEAM/                                      # skn29·최종·4·team 항목의 역할과 책임 설명
│
├─ web/                                                 # 상담사·운영 담당자용 React 웹 애플리케이션
│
├─ mobile/                                              # 고객·방문기사용 Kotlin·Jetpack Compose Android 앱
│
├─ backend/                                             # Django·DRF 기반 REST API와 업무 상태 관리
│
├─ ai/                                                  # LLM·RAG·안전 규칙·역할별 결과 생성
│
├─ contracts/                                           # 웹·모바일·백엔드·AI 사이의 공통 데이터 계약
│
├─ data/                                                # 공식 문서·전처리 데이터·합성 시연 데이터
│
├─ infra/                                               # Docker·Kubernetes·PostgreSQL 실행 및 배포 설정
│
├─ scripts/                                             # 데이터·DB·개발·배포·테스트 자동화 스크립트
│
├─ tests/                                               # 둘 이상의 영역을 연결하는 통합·E2E 테스트
│
├─ docs/                                                # 기획·설계·개발·테스트·배포 문서
│
├─ .github/                                             # Issue·PR 양식과 GitHub Actions CI/CD
│
├─ .editorconfig                                        # 인코딩·들여쓰기·줄바꿈 공통 설정
├─ .gitattributes                                       # 운영체제별 줄바꿈 차이 제어
├─ .gitignore                                           # 비밀값·빌드 결과·공식 원본 PDF 등 제외
├─ .env.example                                         # 저장소 공통 환경변수 이름 예시
├─ docker-compose.yml                                   # 로컬 통합 개발 환경 실행 설정
├─ CONTRIBUTING.md                                      # 브랜치·Issue·커밋·PR·리뷰 규칙
└─ README.md                                            # 프로젝트 소개·구조·실행 방법
```

## 2.1 한 단계 확장한 전체 골격

```text
SKN29-FINAL-4TEAM/                                      # skn29·최종·4·team 항목의 역할과 책임 설명
│
├─ web/                                                 # 상담사·운영 담당자용 React 웹 애플리케이션
│  ├─ src/                                              # React 웹 운영 코드
│  ├─ tests/                                            # 웹 단위·컴포넌트·통합 테스트
│  └─ README.md                                         # 웹 설치·실행·빌드·테스트 안내
│
├─ mobile/                                              # 고객·방문기사용 Kotlin·Jetpack Compose Android 앱
│  ├─ app/                                              # Android 애플리케이션 모듈
│  ├─ gradle/                                           # Gradle Wrapper와 의존성 버전 관리
│  └─ README.md                                         # Android 설치·실행·빌드·테스트 안내
│
├─ backend/                                             # Django·DRF 기반 REST API와 업무 상태 관리 영역
│  ├─ config/                                           # Django 전역 설정과 URL·ASGI·WSGI
│  ├─ apps/                                             # 업무 도메인별 Django App
│  ├─ common/                                           # 인증·권한·응답·오류·로그 공통 코드
│  ├─ tests/                                            # 백엔드 공통 테스트
│  └─ README.md                                         # 서버·Migration·Seed 안내
│
├─ ai/                                                  # 증상 구조화·RAG·안전 규칙·역할별 생성 결과 처리 영역
│  ├─ app/                                              # AI·RAG 운영 코드
│  ├─ evaluation/                                       # 검색·안전·생성 평가 데이터와 결과
│  ├─ tests/                                            # AI 모듈 테스트
│  └─ README.md                                         # AI 실행·평가·프롬프트 관리 안내
│
├─ contracts/                                           # 서비스 간 API·AI·상태·코드 계약의 단일 기준 저장소
│  ├─ api/                                              # REST API 요청·응답 계약
│  ├─ ai/                                               # AI 입력·출력 JSON 계약
│  ├─ state-machine/                                    # 상태·이벤트·allowed_actions 계약
│  ├─ error-codes/                                      # 공통 업무 오류 코드
│  └─ codes/                                            # 역할·상태·위험도 등 공통 코드값
│
├─ data/                                                # 공식 원본·전처리·구조화·합성 데이터를 관리하는 영역
│  ├─ raw/                                              # 공식 PDF 등 원본 자료, Git 추적 제외
│  ├─ processed/                                        # 전처리·검증된 데이터
│  ├─ synthetic/                                        # 개인정보 없는 합성 시연 데이터
│  └─ README.md                                         # 데이터 출처·사용 범위·갱신 방법
│
├─ infra/                                               # Docker·Kubernetes·클라우드·모니터링 배포 설정 영역
│  ├─ docker/                                           # 컨테이너 이미지·Compose 관련 설정
│  ├─ kubernetes/                                       # Kubernetes Deployment·Service·Job 등
│  ├─ postgresql/                                       # 로컬 PostgreSQL 초기 실행 설정
│  ├─ monitoring/                                       # 로그·메트릭·Health Check 설정
│  └─ README.md                                         # 배포·롤백·Smoke Test 절차
│
├─ scripts/                                             # 데이터·DB·개발·테스트·배포 작업 자동화 영역
│  ├─ data/                                             # 공식 문서 추출·전처리·검증
│  ├─ database/                                         # Seed·백업·복구
│  ├─ development/                                      # 로컬 환경 실행·종료·초기화
│  ├─ deployment/                                       # 배포·Migration·롤백
│  └─ testing/                                          # Smoke·E2E 테스트 실행
│
├─ tests/                                               # 여러 서비스가 연결되는 계약·통합·E2E 검증 영역
│  ├─ contract/                                         # 영역 간 데이터 계약 검증
│  ├─ integration/                                      # API·DB·AI 연동 검증
│  ├─ e2e/                                              # 고객→상담사→기사→고객 흐름 검증
│  ├─ performance/                                      # API·AI 응답 시간 검증
│  └─ fixtures/                                         # 공통 합성 테스트 데이터
│
├─ docs/                                                # 기획·설계·개발·테스트·배포 지식을 관리하는 문서 영역
│  ├─ planning/                                         # 기획서·요구사항정의서·WBS
│  ├─ architecture/                                     # 시스템·모듈·배포 아키텍처
│  ├─ screens/                                          # 화면설계서와 화면 흐름
│  ├─ api/                                              # 사람이 읽는 API 명세와 예시
│  ├─ database/                                         # ERD·데이터 사전·DB 규칙
│  ├─ ai/                                               # AI·RAG·프롬프트·평가·안전 기준
│  ├─ testing/                                          # 테스트 계획·결과·결함 보고서
│  ├─ deployment/                                       # Docker·Kubernetes·CI/CD 문서
│  ├─ adr/                                              # 주요 기술 결정 기록
│  └─ meetings/                                         # 데일리 스크럼·멘토링·회의록
│
└─ .github/                                             # GitHub 협업 설정과 Actions 기반 CI/CD 자동화 영역
   ├─ ISSUE_TEMPLATE/                                   # 기능·버그 Issue 양식
   ├─ workflows/                                        # 영역별 CI와 Kubernetes CD
   ├─ CODEOWNERS                                        # 영역별 기본 리뷰 담당자
   └─ pull_request_template.md                          # 변경·테스트·영향 범위 PR 양식
```

## 2.2 전체 구조 운영 원칙

1. `web/`, `mobile/`, `backend/`, `ai/`는 서로의 내부 소스에 직접 의존하지 않는다.
2. 웹과 모바일은 백엔드 REST API만 호출한다.
3. AI는 분석 결과를 반환하지만 문의·방문 상태를 직접 변경하지 않는다.
4. 업무 상태와 권한 검증은 백엔드 State Machine이 최종 책임을 가진다.
5. API·AI·상태 코드의 영역 간 계약은 `contracts/`에서 관리한다.
6. PostgreSQL 스키마 변경의 기준은 Django Migration이다.
7. Kubernetes 설정은 `infra/kubernetes/`에서만 관리한다.
8. Android 앱은 Kubernetes 배포 대상이 아니며 APK 또는 AAB로 빌드한다.
9. 공식 원본 문서는 `data/raw/`에 보관하되 Git 저장소에는 올리지 않는다.
10. 최상위 `common/`은 만들지 않고 각 기술 영역 내부에서 공통 코드를 관리한다.

---

# 3. Web 디렉토리 세부 구조

## 3.1 담당 화면

| 사용자 | 화면 ID | 화면 |
|---|---|---|
| 상담사 | `CONS-01` | 상담사 대시보드 |
| 상담사 | `CONS-02` | 문의 상세·상담 기록 |
| 상담사 | `CONS-03` | 방문 전환·일정 등록 |
| 운영 담당자 | `ADMIN-01` | 운영 대시보드·예외 조회(P1) |

## 3.2 상세 구조

```text
web/                                              # React + TypeScript + Vite 웹 프로젝트
│
├─ public/                                              # 빌드 과정에서 가공 없이 배포되는 공개 파일
│  ├─ favicon.svg                                       # 브라우저 탭 아이콘
│  └─ images/                                           # 브랜드·로그인 등에 사용하는 공개 이미지
│
├─ src/                                                 # 웹 애플리케이션 운영 소스
│  │
│  ├─ app/                                              # 앱 시작·라우팅·권한·레이아웃·전역 설정
│  │  │
│  │  ├─ router/                                        # React Router 기반 경로 관리
│  │  │  ├─ AppRouter.tsx                               # 전체 Route와 Layout 조립
│  │  │  ├─ routePaths.ts                               # URL 경로 상수
│  │  │  └─ guards/                                     # 화면 진입 전 인증·권한 검사
│  │  │     ├─ AuthGuard.tsx                            # 로그인 여부 검사
│  │  │     └─ RoleGuard.tsx                            # 상담사·운영 역할 검사
│  │  │
│  │  ├─ layouts/                                       # 역할별 공통 화면 틀
│  │  │  ├─ RootLayout.tsx                              # 최상위 레이아웃과 공통 오류 영역
│  │  │  ├─ AuthLayout.tsx                              # 로그인 화면 레이아웃
│  │  │  ├─ ConsultantLayout.tsx                        # 상담사용 메뉴·헤더·콘텐츠 영역
│  │  │  └─ AdminLayout.tsx                             # 운영 담당자용 메뉴·헤더·콘텐츠 영역
│  │  │
│  │  ├─ providers/                                     # 전역 Provider 조립
│  │  │  └─ AppProviders.tsx                            # 인증·서버 상태·전역 오류 Provider 연결
│  │  │
│  │  ├─ config/                                        # 프론트엔드 실행 환경 설정
│  │  │  └─ env.ts                                      # Vite 환경변수 검증과 공개 설정 제공
│  │  │
│  │  └─ App.tsx                                        # Router와 Provider를 결합하는 최상위 컴포넌트
│  │
│  ├─ pages/                                            # URL과 직접 연결되는 페이지
│  │  ├─ auth/                                          # 로그인 화면과 인증 관련 페이지 그룹
│  │  │  └─ LoginPage.tsx                               # 역할별 가상 로그인 화면
│  │  │
│  │  ├─ consultant/                                    # CONS-01~03 상담사 페이지 그룹
│  │  │  ├─ ConsultantDashboardPage.tsx                 # CONS-01 상담사 대시보드
│  │  │  ├─ InquiryDetailPage.tsx                       # CONS-02 문의 상세·상담 기록
│  │  │  └─ VisitTransitionPage.tsx                     # CONS-03 방문 전환·일정 등록
│  │  │
│  │  ├─ admin/                                         # ADMIN-01 운영 담당자 페이지 그룹
│  │  │  └─ OperationsDashboardPage.tsx                 # ADMIN-01 운영 대시보드(P1)
│  │  │
│  │  └─ system/                                        # 권한 오류·404·전역 오류 페이지 그룹
│  │     ├─ ForbiddenPage.tsx                           # 권한 없는 역할의 접근 차단
│  │     ├─ NotFoundPage.tsx                            # 존재하지 않는 URL 처리
│  │     └─ ErrorPage.tsx                               # 복구 불가능한 화면 오류 처리
│  │
│  ├─ features/                                         # 사용자 행동과 업무 기능 중심 모듈
│  │  │
│  │  ├─ auth/                                          # 로그인·로그아웃·세션 확인
│  │  │  ├─ api/                                        # 인증 API 요청
│  │  │  ├─ components/                                 # 로그인 폼·사용자 메뉴
│  │  │  ├─ hooks/                                      # 로그인 상태·권한 조회 Hook
│  │  │  └─ model/                                      # 인증 상태·역할 판정 로직
│  │  │
│  │  ├─ inquiry-queue/                                 # CONS-01 문의 대기열 기능
│  │  │  ├─ api/                                        # 문의 목록·집계 조회
│  │  │  ├─ components/                                 # 목록·필터·검색·페이지네이션 UI
│  │  │  ├─ hooks/                                      # 목록 조회·필터 상태 관리
│  │  │  ├─ model/                                      # 검색 조건·정렬·페이지 상태
│  │  │  └─ validation/                                 # 검색·기간 필터 입력 검증
│  │  │
│  │  ├─ inquiry-detail/                                # CONS-02 문의 전체 정보 조회
│  │  │  ├─ api/                                        # 문의 상세·상태 이력 조회
│  │  │  ├─ components/                                 # 고객·제품·증상·문진·조치 정보 UI
│  │  │  ├─ hooks/                                      # 상세 조회·새로고침 처리
│  │  │  └─ model/                                      # 상세 화면 표시 데이터 조립
│  │  │
│  │  ├─ evidence-viewer/                               # 공식 문서 근거 표시
│  │  │  ├─ components/                                 # 근거 카드·출처 버튼·검증 상태 UI
│  │  │  ├─ hooks/                                      # 출처 열기·URL 실패 처리
│  │  │  └─ model/                                      # EvidenceCardDTO 화면 변환
│  │  │
│  │  ├─ consultation/                                  # 상담 시작·기록·완료 처리
│  │  │  ├─ api/                                        # 상담 시작·저장·완료 요청
│  │  │  ├─ components/                                 # 상담 기록 폼·방문 필요 선택 UI
│  │  │  ├─ hooks/                                      # 상담 작성 상태·요청 처리
│  │  │  ├─ model/                                      # 상담 초안·수정·저장 상태
│  │  │  └─ validation/                                 # 상담 완료 필수값 검사
│  │  │
│  │  ├─ visit-transition/                              # CONS-03 방문 전환 기능
│  │  │  ├─ api/                                        # 방문 생성·일정 수정·확정 요청
│  │  │  ├─ components/                                 # 기사·희망일·확정일·전달사항 입력
│  │  │  ├─ hooks/                                      # 방문 일정 저장·확정 처리
│  │  │  ├─ model/                                      # 방문 일정 작성 상태
│  │  │  └─ validation/                                 # 일정·기사·필수 전달 정보 검증
│  │  │
│  │  ├─ workflow-action/                               # 백엔드 State Machine 이벤트 실행
│  │  │  ├─ api/                                        # 상태 전환 이벤트 요청
│  │  │  ├─ components/                                 # allowed_actions 기반 업무 버튼
│  │  │  ├─ hooks/                                      # 중복 요청·동시 수정 제어
│  │  │  └─ model/                                      # 상태·허용 행동과 버튼 연결
│  │  │
│  │  └─ operations-dashboard/                          # ADMIN-01 운영 조회 기능(P1)
│  │     ├─ api/                                        # 집계·차트·예외 건 조회
│  │     ├─ components/                                 # 필터·지표·차트·예외 목록 UI
│  │     ├─ hooks/                                      # 운영 데이터·필터 상태 관리
│  │     ├─ model/                                      # 차트·집계 데이터 변환
│  │     └─ validation/                                 # 기간·모델·담당자 필터 검증
│  │
│  ├─ entities/                                         # 여러 기능이 공유하는 업무 데이터 표현
│  │  ├─ account/                                       # 로그인 사용자와 역할
│  │  ├─ customer/                                      # 합성 고객 기본 정보
│  │  ├─ product/                                       # 제품·구독·관리 유형
│  │  ├─ care/                                          # 케어·필터 교체 이력
│  │  ├─ inquiry/                                       # 문의·증상·위험도·우선순위
│  │  ├─ consultation/                                  # 상담 기록과 상담 요약
│  │  ├─ visit/                                         # 방문 일정과 방문 상태
│  │  ├─ evidence/                                      # 공식 근거 카드 데이터
│  │  └─ workflow/                                      # 상태·이벤트·허용 행동·상태 이력
│  │
│  │  # 각 entity는 필요한 경우에만 아래 폴더 사용
│  │  # ├─ types/                                       # TypeScript 타입
│  │  # ├─ model/                                       # 표시값 변환·파생 상태
│  │  # └─ components/                                  # 단순 카드·배지 등 표현 UI
│  │
│  ├─ common/                                           # 특정 업무에 속하지 않는 웹 공통 코드
│  │  │
│  │  ├─ api/                                           # REST API 공통 통신 계층
│  │  │  ├─ httpClient.ts                               # Base URL·헤더·응답 처리
│  │  │  ├─ apiResponse.ts                              # success·data·error Wrapper 타입
│  │  │  ├─ apiError.ts                                 # 업무 오류 코드와 오류 객체
│  │  │  ├─ pagination.ts                               # page·size·total 목록 응답 타입
│  │  │  └─ requestContext.ts                           # correlation_id·idempotency_key 처리
│  │  │
│  │  ├─ components/                                    # 웹 전체 공통 UI
│  │  │  ├─ inputs/                                     # 입력·선택·날짜·검색 UI
│  │  │  ├─ navigation/                                 # 헤더·사이드바·메뉴 UI
│  │  │  ├─ data-display/                               # 표·카드·배지·페이지네이션
│  │  │  ├─ feedback/                                   # 로딩·빈 상태·오류·성공 안내
│  │  │  ├─ overlay/                                    # 모달·확인창·드로어
│  │  │  └─ accessibility/                              # 포커스·스크린리더 보조 UI
│  │  │
│  │  ├─ hooks/                                         # 기능에 종속되지 않는 공통 Hook
│  │  ├─ constants/                                     # 공통 상수와 화면 표시명
│  │  ├─ types/                                         # 범용 TypeScript 타입
│  │  ├─ utils/                                         # 날짜·문자열·배열·ID 처리 함수
│  │  ├─ validation/                                    # 범용 폼 검증 함수
│  │  └─ styles/                                        # 전역 CSS·레이아웃·디자인 토큰
│  │
│  ├─ assets/                                           # Vite 번들에 포함되는 이미지·아이콘
│  │  ├─ icons/                                         # 웹 UI 아이콘
│  │  └─ images/                                        # 화면 내부 이미지
│  │
│  ├─ main.tsx                                          # React DOM 렌더링 진입점
│  └─ vite-env.d.ts                                     # Vite 환경변수 TypeScript 선언
│
├─ tests/                                               # 웹 운영 코드와 분리된 테스트
│  ├─ unit/                                             # 유틸리티·모델·검증 함수 테스트
│  ├─ component/                                        # 공통·기능 컴포넌트 테스트
│  ├─ integration/                                      # 페이지·API 연동 흐름 테스트
│  ├─ fixtures/                                         # 합성 고객·문의·근거 테스트 데이터
│  └─ setup/                                            # 테스트 공통 초기화 설정
│
├─ index.html                                           # Vite SPA HTML 진입 문서
├─ package.json                                         # 의존성과 실행·빌드·테스트 명령
├─ package-lock.json                                    # npm 의존성 버전 고정
├─ tsconfig.json                                        # TypeScript 공통 설정
├─ tsconfig.app.json                                    # 브라우저 애플리케이션 설정
├─ tsconfig.node.json                                   # Vite 설정 파일용 Node 설정
├─ vite.config.ts                                       # 개발 서버·빌드·경로 별칭 설정
├─ prettier.config.cjs                                  # 코드 포맷 설정
├─ .env.example                                         # VITE_API_BASE_URL 등 공개 변수 예시
├─ Dockerfile                                           # 웹 정적 파일 컨테이너 이미지 생성
├─ nginx.conf                                           # SPA 라우팅·API 프록시 설정
└─ README.md                                            # 설치·실행·빌드·테스트 안내
```

## 3.3 Web 계층별 책임

```text
app
└─ 애플리케이션 시작·라우팅·권한·레이아웃·전역 설정

pages
└─ URL과 직접 연결되며 여러 feature를 조합

features
└─ 조회·입력·저장·상태 전환 등 사용자의 업무 행동 처리

entities
└─ 문의·제품·방문·근거 등 여러 기능이 공유하는 업무 데이터 표현

common
└─ 특정 업무에 종속되지 않는 API·UI·Hook·유틸리티
```

## 3.4 Web 의존 방향

```text
app
 └─ pages
     └─ features
         └─ entities
             └─ common
```

- `pages`는 `features`, `entities`, `common`을 사용할 수 있다.
- `features`는 `entities`, `common`을 사용할 수 있다.
- `entities`는 `common`을 사용할 수 있다.
- `common`은 상위 계층을 참조하지 않는다.
- 페이지 컴포넌트에 직접 API 호출이나 복잡한 상태 전환 로직을 작성하지 않는다.

## 3.5 Web State Machine 원칙

- 프론트엔드는 문의·방문 상태를 임의로 변경하지 않는다.
- 백엔드가 반환한 `allowed_actions`에 포함된 버튼만 표시·활성화한다.
- 상태 전환 요청에는 다음 값을 사용한다.

```text
state_version       # 오래된 화면의 동시 수정 방지
idempotency_key     # 중복 클릭·재전송으로 인한 중복 처리 방지
correlation_id      # 웹→백엔드→AI 처리 흐름 추적
```

## 3.6 Web 공식 근거 처리 원칙

웹은 백엔드가 조립한 `EvidenceCardDTO`만 표시한다.

```text
표시 가능
├─ 문서명
├─ 문서 버전
├─ 페이지
├─ 구조화된 근거 요약
├─ 위험도
├─ 검증 상태
└─ 백엔드가 제공한 공식 출처 URL
```

```text
표시·직접 조립 금지
├─ source_path
├─ ManualPage.text 원문 전체
├─ retrieval_text
├─ RAG 내부 저장 경로
└─ 프론트엔드에서 임의 생성한 공식 PDF URL
```

---

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


---

# 5. AI 디렉토리 세부 구조

## 5.1 책임 범위

```text
AI 서비스가 담당
├─ 고객 자연어 증상 구조화
├─ 누락 정보 확인과 추가 질문 생성
├─ 명시적 안전 규칙 적용
├─ 공식 문서 RAG 검색과 재정렬
├─ 고객 안내 생성
├─ 상담사용 AI 요약 초안 생성
├─ 방문기사용 사전 리포트 초안 생성
└─ 출력 Schema·근거·안전성 검증

AI 서비스가 담당하지 않음
├─ 문의·방문 State Machine 직접 변경
├─ 사용자 권한 최종 검증
├─ PostgreSQL 업무 데이터 직접 수정
├─ 상담사·기사 확정본 저장
└─ 화면용 EvidenceCard 최종 조립
```

## 5.2 상세 구조

```text
ai/                                                # Python 기반 AI·RAG 독립 서비스
│
├─ app/                                                 # AI 운영 코드
│  ├─ interfaces/                                       # 외부 호출 진입 계층
│  │  ├─ http/                                          # 백엔드가 호출하는 내부 HTTP 인터페이스
│  │  │  ├─ routes/                                     # AI 기능별 HTTP Endpoint 정의
│  │  │  │  ├─ analysis_routes.py                       # 증상 분석·추가 질문·안내 요청
│  │  │  │  ├─ consultation_summary_routes.py           # 상담 요약 초안 생성
│  │  │  │  ├─ technician_report_routes.py              # 기사 사전 리포트 생성
│  │  │  │  └─ health_routes.py                         # Liveness·Readiness
│  │  │  ├─ request_models.py                           # HTTP 입력 변환
│  │  │  ├─ response_models.py                          # HTTP 출력 변환
│  │  │  └─ error_handlers.py                           # 공통 오류 응답 변환
│  │  └─ cli/                                           # 평가·디버깅을 위한 명령행 실행 도구
│  │     └─ commands.py                                 # 로컬 분석·검색·평가 명령
│  │
│  ├─ orchestration/                                    # AI 실행 순서 제어
│  │  ├─ pipelines/                                     # 기준선과 제안형 AI 처리 파이프라인 구현
│  │  │  ├─ single_rag_pipeline.py                      # 기준선 단일 RAG
│  │  │  └─ selective_pipeline.py                       # 선택형 책임 분리 구조
│  │  ├─ stages/                                        # 구조화부터 검증까지 단계별 실행 어댑터
│  │  │  ├─ structuring_stage.py                        # STRUCTURING
│  │  │  ├─ missing_fields_stage.py                     # CHECKING_MISSING_FIELDS
│  │  │  ├─ safety_check_stage.py                       # SAFETY_CHECK
│  │  │  ├─ retrieval_stage.py                          # RETRIEVING
│  │  │  ├─ reranking_stage.py                          # RERANKING
│  │  │  ├─ generation_stage.py                         # GENERATING
│  │  │  └─ validation_stage.py                         # VALIDATING
│  │  ├─ pipeline_router.py                             # 목적·역할별 Pipeline 선택
│  │  ├─ pipeline_context.py                            # 단계 간 공유 Context
│  │  ├─ pipeline_status.py                             # 처리 상태·실패 단계
│  │  └─ pipeline_result.py                             # 최종 결과 구조
│  │
│  ├─ structuring/                                      # 증상 구조화·추가 질문
│  │  ├─ symptom_structurer.py                          # 고객 자연어 증상을 표준 증상 필드로 구조화
│  │  ├─ missing_field_checker.py                       # 증상 분석에 필요한 필수 정보 누락 여부 검사
│  │  ├─ followup_question_generator.py                 # 누락 정보 확인을 위한 추가 질문 생성
│  │  ├─ duplicate_question_guard.py                    # 이미 확인한 내용을 반복 질문하지 않도록 차단
│  │  └─ symptom_normalizer.py                          # 다양한 증상 표현을 표준 증상 코드로 정규화
│  │
│  ├─ safety/                                           # LLM보다 우선하는 안전 규칙
│  │  ├─ risk_classifier.py                             # 증상을 general·caution·danger 위험도로 분류
│  │  ├─ priority_classifier.py                         # 일반 안내·상담 권고·우선 상담의 처리 우선순위 분류
│  │  ├─ usage_guidance_classifier.py                   # 제품 사용 가능·제한·중지 상태와 제한 범위 결정
│  │  ├─ prohibited_action_guard.py                     # 분해·직접 수리 등 금지된 자가조치 차단
│  │  ├─ diagnosis_expression_guard.py                  # 확정 고장 진단·안전 보증 표현 생성 차단
│  │  ├─ no_evidence_policy.py                          # 공식 근거가 없을 때 판단 보류·상담 전환 정책 적용
│  │  └─ rule_loader.py                                 # YAML 안전 규칙을 로딩하고 형식을 검증
│  │
│  ├─ retrieval/                                        # 공식 문서 검색
│  │  ├─ indexing/                                      # 검증 청크 임베딩과 Vector DB 인덱스 생성
│  │  │  ├─ chunk_loader.py                             # 검증된 구조화 RAG 청크를 인덱싱 입력으로 로딩
│  │  │  ├─ embedding_indexer.py                        # 문서 임베딩을 생성해 Vector Store에 적재
│  │  │  └─ index_manifest.py                           # 인덱스 버전·문서 해시·생성 정보를 기록
│  │  ├─ query/                                         # 증상·질문을 검색 질의로 변환하는 기능
│  │  │  ├─ query_builder.py                            # 구조화 증상과 질문을 기반으로 검색 질의 구성
│  │  │  └─ query_expander.py                           # 검색 질의를 공식 증상 용어 범위에서 제한적으로 확장
│  │  ├─ filters/                                       # 제품·세대·범위·근거 정책 기반 검색 필터
│  │  │  ├─ product_filter.py                           # 정확한 제품 판매 코드에 맞는 문서만 필터링
│  │  │  ├─ generation_filter.py                        # 제품 세대가 다른 문서의 혼용을 방지
│  │  │  ├─ scope_filter.py                             # MVP·확장·제외 범위에 따라 검색 대상을 분리
│  │  │  └─ document_policy_filter.py                   # 검증 상태와 allowed_use 정책에 따라 문서 사용 여부 결정
│  │  ├─ search/                                        # 벡터·키워드·하이브리드 검색 실행
│  │  │  ├─ vector_search.py                            # Vector Store 유사도 검색 실행
│  │  │  ├─ keyword_search.py                           # 공식 용어 기반 키워드 검색 실행
│  │  │  └─ hybrid_search.py                            # 벡터 검색과 키워드 검색 결과를 결합
│  │  ├─ reranking/                                     # 검색 후보 점수 보정과 재정렬
│  │  │  ├─ evidence_reranker.py                        # 질의 관련도와 근거 적합성을 기준으로 후보 재정렬
│  │  │  └─ score_normalizer.py                         # 검색 방식별 점수를 공통 비교 범위로 정규화
│  │  ├─ verification/                                  # 생성 전 근거·모델·페이지 사용 가능성 재검증
│  │  │  ├─ model_scope_validator.py                    # 검색 근거의 제품·세대·모델 적용 범위 검증
│  │  │  ├─ evidence_policy_validator.py                # 근거의 검증 상태와 사용 허용 정책 검사
│  │  │  ├─ page_reference_validator.py                 # 문서 ID와 페이지 참조의 존재·일치 여부 검사
│  │  │  └─ faq_usage_validator.py                      # 미검증 FAQ 단독 사용과 적용 범위 위반 차단
│  │  └─ models/                                        # 검색 과정에서 사용하는 내부 데이터 모델
│  │     ├─ retrieval_query.py                          # AI 검색 단계에서 사용하는 구조화 질의 모델
│  │     ├─ retrieved_chunk.py                          # 검색된 RAG 청크와 점수를 표현하는 모델
│  │     └─ verified_evidence.py                        # 생성에 사용할 수 있도록 검증된 근거 모델
│  │
│  ├─ generation/                                       # 역할별 결과 생성
│  │  ├─ customer_guidance/                             # 고객용 안전 안내와 다음 행동 생성
│  │  │  ├─ guidance_generator.py                       # 공식 근거 범위 안에서 고객 안내와 다음 행동 생성
│  │  │  └─ guidance_formatter.py                       # 고객 안내 결과를 읽기 쉬운 형식으로 변환
│  │  ├─ consultation_summary/                          # 상담사용 AI 요약 초안 생성
│  │  │  ├─ summary_generator.py                        # 상담사용 AI 요약 초안을 고정 Schema로 생성
│  │  │  └─ summary_formatter.py                        # 상담 요약을 화면·API 전달 형식으로 정리
│  │  └─ technician_report/                             # 방문기사용 사전 점검 리포트 생성
│  │     ├─ report_generator.py                         # 방문기사 사전 점검 리포트 초안 생성
│  │     └─ report_formatter.py                         # 기사 리포트를 화면·API 전달 형식으로 정리
│  │
│  ├─ validation/                                       # 생성 결과 최종 검증
│  │  ├─ schema/                                        # AI 출력 JSON 구조 검증 로직
│  │  │  ├─ output_schema_validator.py                  # AI 출력의 필수 필드·타입·Enum을 Schema로 검증
│  │  │  └─ regeneration_policy.py                      # 출력 검증 실패 시 재생성·Fallback 여부 결정
│  │  ├─ grounding/                                     # 생성 문장과 공식 근거의 일치 여부 검증
│  │  │  ├─ evidence_grounding_validator.py             # 생성 문장이 공식 근거 범위를 벗어나지 않았는지 검사
│  │  │  └─ citation_reference_validator.py             # 생성 결과의 문서·페이지 참조 일치 여부 검사
│  │  ├─ consistency/                                   # 고객·상담사·기사 결과 간 핵심 사실 일관성 검증
│  │  │  └─ cross_role_consistency_validator.py         # 고객·상담사·기사 결과의 핵심 사실 모순 검사
│  │  ├─ safety/                                        # 최종 문장의 위험·금지 표현 재검사
│  │  │  ├─ prohibited_phrase_validator.py              # 확정 진단·안전 보증 등 금지 표현 포함 여부 검사
│  │  │  └─ usage_guidance_validator.py                 # 위험도와 제품 사용 안내 상태의 일관성 검사
│  │  └─ scope/                                         # MVP·확장·제외 모델 범위 검증
│  │     └─ product_scope_validator.py                  # MVP에서 확장·제외 모델 데이터 혼입을 차단
│  │
│  ├─ schemas/                                          # 내부 Pydantic 모델
│  │  ├─ common.py                                      # common 처리 로직 모듈
│  │  ├─ symptom.py                                     # 증상 처리 로직 모듈
│  │  ├─ safety.py                                      # 안전 처리 로직 모듈
│  │  ├─ retrieval.py                                   # 검색 처리 로직 모듈
│  │  ├─ guidance.py                                    # 안내 처리 로직 모듈
│  │  ├─ consultation_summary.py                        # 상담·요약 처리 로직 모듈
│  │  ├─ technician_report.py                           # 방문기사·보고서 처리 로직 모듈
│  │  └─ pipeline.py                                    # pipeline 처리 로직 모듈
│  │
│  ├─ integrations/                                     # 외부 서비스 연결
│  │  ├─ llm/                                           # 생성형 AI 모델 호출 어댑터와 사용량 기록
│  │  │  ├─ llm_client.py                               # LLM 공급자와 무관한 공통 호출 인터페이스
│  │  │  ├─ model_router.py                             # AI 과업별로 사용할 모델과 설정 선택
│  │  │  └─ token_usage.py                              # LLM 토큰 사용량·비용·응답 지연 기록
│  │  ├─ embedding/                                     # 문서·질의 임베딩 생성 어댑터
│  │  │  └─ embedding_client.py                         # 문서·질의 임베딩 생성 서비스 호출
│  │  ├─ vector_store/                                  # Vector DB 연결과 컬렉션 관리
│  │  │  ├─ vector_store.py                             # Vector Store 조회·적재 공통 인터페이스
│  │  │  └─ collection_manager.py                       # MVP·확장 Vector Store 컬렉션 분리 관리
│  │  └─ backend/                                       # 제품·문의·관리 이력을 읽는 백엔드 연동
│  │     └─ context_client.py                           # 백엔드에서 제품·문의·관리 이력을 읽어오는 클라이언트
│  │
│  ├─ common/                                           # 설정·오류·로그·재시도
│  │  ├─ config/                                        # 환경변수와 AI 실행 설정 로딩
│  │  ├─ errors/                                        # AI 단계별 업무 오류 정의
│  │  ├─ logging/                                       # correlation_id 기반 AI 구조화 로그
│  │  ├─ retry/                                         # LLM·검색 단계별 재시도 정책
│  │  ├─ timeout/                                       # LLM·검색·검증 단계별 제한 시간 관리
│  │  ├─ tracing/                                       # 단계별 지연·실패 위치·재시도 횟수 추적
│  │  └─ utils/                                         # AI 영역 공통 문자열·ID·날짜 도구
│  │
│  ├─ bootstrap.py                                      # 의존성 조립
│  └─ main.py                                           # 서비스 실행 진입점
│
├─ prompts/                                             # 버전 관리되는 프롬프트
│  ├─ prompt_registry.yaml                              # AI 과업별 현재 적용 프롬프트 버전 등록
│  ├─ common/                                           # 모든 역할의 프롬프트에 적용하는 공통 규칙
│  │  ├─ grounding_rules.yaml                           # 공식 근거 범위 안에서만 생성하도록 하는 공통 규칙
│  │  ├─ safety_constraints.yaml                        # 위험 조치·확정 진단·안전 보증을 제한하는 공통 규칙
│  │  └─ output_style.yaml                              # 고객·상담사·기사 역할별 출력 문체와 형식 기준
│  ├─ symptom_structuring/v1/                           # symptom structuring 관련 파일과 하위 항목을 관리하는 디렉토리
│  │  ├─ system.txt                                     # 현재 AI 과업의 시스템 프롬프트 원문
│  │  └─ user_template.txt                              # 현재 AI 과업의 사용자 입력 프롬프트 템플릿
│  ├─ followup_question/v1/                             # followup question 관련 파일과 하위 항목을 관리하는 디렉토리
│  │  ├─ system.txt                                     # 현재 AI 과업의 시스템 프롬프트 원문
│  │  └─ user_template.txt                              # 현재 AI 과업의 사용자 입력 프롬프트 템플릿
│  ├─ customer_guidance/v1/                             # 고객용 안전 안내와 다음 행동 생성
│  │  ├─ system.txt                                     # 현재 AI 과업의 시스템 프롬프트 원문
│  │  └─ user_template.txt                              # 현재 AI 과업의 사용자 입력 프롬프트 템플릿
│  ├─ consultation_summary/v1/                          # 상담사용 AI 요약 초안 생성
│  │  ├─ system.txt                                     # 현재 AI 과업의 시스템 프롬프트 원문
│  │  └─ user_template.txt                              # 현재 AI 과업의 사용자 입력 프롬프트 템플릿
│  └─ technician_report/v1/                             # 방문기사용 사전 점검 리포트 생성
│     ├─ system.txt                                     # 현재 AI 과업의 시스템 프롬프트 원문
│     └─ user_template.txt                              # 현재 AI 과업의 사용자 입력 프롬프트 템플릿
│
├─ configs/                                             # 공개 가능한 실행 설정
│  ├─ base.yaml                                         # 기본 설정·정책 정의
│  ├─ development.yaml                                  # 개발 설정·정책 정의
│  ├─ test.yaml                                         # 테스트 설정·정책 정의
│  ├─ demo.yaml                                         # 시연 설정·정책 정의
│  ├─ model_profiles.yaml                               # 과업별 모델·temperature·토큰 제한 설정
│  ├─ retrieval_policy.yaml                             # 검색 Top-k·필터·재정렬 기준 설정
│  ├─ safety_rules.yaml                                 # 누수·전기·화상 등 명시적 안전 분기 규칙
│  ├─ prohibited_expressions.yaml                       # AI가 생성하면 안 되는 진단·보증 표현 목록
│  └─ retry_policy.yaml                                 # AI 단계별 재시도 횟수·백오프·타임아웃 정책
│
├─ evaluation/                                          # AI·RAG 품질 평가
│  ├─ datasets/                                         # 과업별 AI 평가 입력과 기대 결과
│  │  ├─ structuring/                                   # 증상 필드 구조화·누락 탐지 평가 자료
│  │  ├─ safety/                                        # 위험도·사용 안내·금지 행동의 기대 결과 평가 자료
│  │  ├─ retrieval/                                     # 정답 문서·페이지 검색 성능 평가 자료
│  │  ├─ generation/                                    # 역할별 생성 품질 평가 자료
│  │  └─ end_to_end/                                    # AI 전체 파이프라인 대표 시나리오 평가
│  ├─ runners/                                          # 과업별 평가 실행기
│  │  ├─ structuring_runner.py                          # structuring·실행기 처리 로직 모듈
│  │  ├─ safety_runner.py                               # 안전·실행기 처리 로직 모듈
│  │  ├─ retrieval_runner.py                            # 검색·실행기 처리 로직 모듈
│  │  ├─ generation_runner.py                           # 생성·실행기 처리 로직 모듈
│  │  └─ pipeline_comparison_runner.py                  # pipeline·comparison·실행기 처리 로직 모듈
│  ├─ metrics/                                          # 정확도·검색·안전·성능 지표 계산
│  │  ├─ structuring_metrics.py                         # structuring·지표 처리 로직 모듈
│  │  ├─ retrieval_metrics.py                           # 검색·지표 처리 로직 모듈
│  │  ├─ safety_metrics.py                              # 안전·지표 처리 로직 모듈
│  │  ├─ generation_metrics.py                          # 생성·지표 처리 로직 모듈
│  │  └─ performance_metrics.py                         # 성능·지표 처리 로직 모듈
│  ├─ human_review/                                     # 사람이 수행하는 정성 평가 체크리스트
│  │  └─ review_template.yaml                           # 사람이 AI 결과를 평가할 때 사용하는 검토 양식
│  └─ reports/                                          # 평가 실행 결과와 비교 보고서
│     └─ .gitkeep                                       # 빈 디렉토리를 Git 저장소에 유지하기 위한 파일
│
├─ tests/                                               # AI 자체 테스트
│  ├─ unit/                                             # AI 모듈별 독립 단위 테스트
│  │  ├─ structuring/                                   # 증상 구조화·누락 탐지 모듈 단위 테스트
│  │  ├─ safety/                                        # 위험 분류·금지 행동·금지 표현 단위 테스트
│  │  ├─ retrieval/                                     # 검색·필터·재정렬·근거 검증 단위 테스트
│  │  ├─ generation/                                    # 역할별 생성기와 Formatter 단위 테스트
│  │  └─ validation/                                    # 스키마·근거·안전·일관성 검증 단위 테스트
│  ├─ integration/                                      # 둘 이상의 구성 요소를 연결해 검증하는 영역
│  │  ├─ pipeline/                                      # 전체 AI 처리 단계 연결 통합 테스트
│  │  ├─ llm/                                           # LLM 호출 어댑터와 오류 처리 통합 테스트
│  │  └─ vector_store/                                  # Vector DB 연결·검색·컬렉션 통합 테스트
│  ├─ contract/                                         # 백엔드와 AI 간 입력·출력 계약 테스트
│  ├─ fixtures/                                         # 합성 문의·근거·관리 이력 테스트 데이터
│  └─ conftest.py                                       # Pytest 공통 Fixture와 테스트 초기화 설정
│
├─ scripts/                                             # 인덱싱·평가·비교·Smoke 실행 스크립트
│  ├─ build_vector_index.py                             # 검증된 MVP RAG 청크로 Vector Store 인덱스 생성
│  ├─ verify_prompt_registry.py                         # 프롬프트 Registry와 실제 버전 디렉토리 정합성 검사
│  ├─ run_evaluation.py                                 # 구조화·안전·검색·생성 평가를 일괄 실행
│  ├─ compare_pipelines.py                              # 단일 RAG와 선택형 책임 분리 Pipeline 성능 비교
│  └─ smoke_test.py                                     # 배포된 AI 서비스의 대표 요청을 빠르게 확인
│
├─ pyproject.toml                                       # Python 의존성·포맷·테스트·빌드 설정
├─ .env.example                                         # 필요한 환경변수 이름과 예시 값 안내
├─ Dockerfile                                           # 현재 서비스의 컨테이너 이미지 빌드 절차 정의
└─ README.md                                            # AI 실행·인덱싱·평가·프롬프트 관리 안내
```

## 5.3 네이밍 규칙

| 대상 | 규칙 | 예시 |
|---|---|---|
| Python 파일·패키지 | `snake_case` | `risk_classifier.py` |
| 클래스 | `PascalCase` | `RiskClassifier` |
| 함수·변수 | `snake_case` | `classify_risk()` |
| 상수 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 테스트 파일 | `test_*.py` | `test_risk_classifier.py` |
| 프롬프트·설정 | `snake_case` | `safety_rules.yaml` |
| 프롬프트 버전 | `v1`, `v2` | `customer_guidance/v1/` |

---

# 6. Contracts 디렉토리 세부 구조

## 6.1 책임 범위

```text
contracts가 담당
├─ REST API 요청·응답 구조
├─ Backend↔AI JSON 구조
├─ State Machine 상태·이벤트·허용 행동
├─ 역할·위험도·사용 안내 등 공통 코드
├─ 공통 업무 오류 코드
├─ 정상·오류 예시
└─ 계약 버전과 변경 이력

contracts가 담당하지 않음
├─ TypeScript·Kotlin·Python 구현 코드
├─ Django Serializer 구현
├─ Pydantic 모델 구현
├─ PostgreSQL 테이블 정의
└─ 사람이 읽는 상세 설명 문서
```

## 6.2 상세 구조

```text
contracts/                                          # 서비스 간 공통 데이터 계약
│
├─ README.md                                            # 책임·작성법·변경 절차
├─ VERSION                                              # 전체 계약 버전
├─ CHANGELOG.md                                         # 호환·비호환 변경 이력
│
├─ api/                                                 # Web·Mobile↔Backend REST 계약
│  ├─ openapi.yaml                                      # `/api/v1` 전체 REST API 계약의 OpenAPI 진입 문서
│  ├─ paths/                                            # 도메인별 REST API 경로 정의
│  │  ├─ auth.yaml                                      # 인증·토큰·세션 API 경로 정의
│  │  ├─ products.yaml                                  # 제품·구독 정보 API 경로 정의
│  │  ├─ care.yaml                                      # 케어 일정·관리 이력 API 경로 정의
│  │  ├─ questionnaires.yaml                            # 문진·추가 질문 답변 API 경로 정의
│  │  ├─ inquiries.yaml                                 # 문의 생성·목록·상세·후속 확인 API 경로 정의
│  │  ├─ consultations.yaml                             # 상담 시작·저장·완료 API 경로 정의
│  │  ├─ visits.yaml                                    # 방문 생성·일정·결과 API 경로 정의
│  │  ├─ evidence.yaml                                  # 공식 근거 조회 API 경로 정의
│  │  ├─ workflow.yaml                                  # State Machine 이벤트 실행 API 경로 정의
│  │  ├─ operations.yaml                                # 운영 지표·예외 조회 API 경로 정의
│  │  └─ health.yaml                                    # 서비스 Liveness·Readiness API 경로 정의
│  ├─ components/                                       # 여러 API 경로가 재사용하는 OpenAPI 구성 요소
│  │  ├─ schemas/                                       # API 요청·응답 객체의 공통 Schema
│  │  │  ├─ common/                                     # 응답 Wrapper·오류·페이지·추적 공통 구조
│  │  │  │  ├─ ApiResponse.yaml                         # success·data·error·meta를 포함한 공통 응답 Wrapper
│  │  │  │  ├─ ApiError.yaml                            # 오류 코드·사용자 메시지·상세·재시도 여부 구조
│  │  │  │  ├─ FieldError.yaml                          # 입력 필드별 검증 오류 구조
│  │  │  │  ├─ PageInfo.yaml                            # page·size·total·total_pages 페이지 정보
│  │  │  │  ├─ TraceContext.yaml                        # correlation_id 등 요청 추적 정보
│  │  │  │  └─ AuditMetadata.yaml                       # 생성·수정 시각과 처리 주체 감사 정보
│  │  │  ├─ auth/                                       # 로그인·토큰·현재 사용자 Schema와 예시
│  │  │  │  ├─ LoginRequest.yaml                        # 가상 로그인 입력 구조
│  │  │  │  ├─ LoginResponse.yaml                       # 토큰·사용자·역할 로그인 결과 구조
│  │  │  │  └─ AuthenticatedUser.yaml                   # 현재 로그인 사용자와 역할 정보
│  │  │  ├─ product/                                    # 제품·구독 관련 Schema
│  │  │  │  ├─ ProductSummary.yaml                      # 목록·카드용 제품 기본 정보
│  │  │  │  ├─ ProductDetail.yaml                       # 제품·구독·지원 범위 상세 정보
│  │  │  │  └─ SubscriptionSummary.yaml                 # 구독 상태·시작일·관리 유형 요약
│  │  │  ├─ care/                                       # 관리 일정·케어 이력 관련 Schema
│  │  │  │  ├─ CareHistoryItem.yaml                     # 필터 교체·정기 관리 이력 항목
│  │  │  │  └─ NextCareSchedule.yaml                    # 다음 관리 예정일과 관리 유형 정보
│  │  │  ├─ questionnaire/                              # 문진·증상·추가 답변 관련 Schema
│  │  │  │  ├─ QuestionnaireAnswer.yaml                 # 문진 문항 ID와 답변 구조
│  │  │  │  ├─ SymptomSubmissionRequest.yaml            # 고객 증상·문진 제출 요청 구조
│  │  │  │  └─ FollowUpAnswerRequest.yaml               # AI 추가 질문 답변 제출 요청 구조
│  │  │  ├─ inquiry/                                    # 문의 생성·목록·상세·피드백 관련 Schema
│  │  │  │  ├─ InquirySummary.yaml                      # 문의 목록용 상태·위험도·고객·제품 요약
│  │  │  │  ├─ InquiryDetail.yaml                       # 문의·문진·조치·상담·방문 전체 상세 구조
│  │  │  │  ├─ InquiryHistoryItem.yaml                  # 문의 상태 변경과 처리 이력 항목
│  │  │  │  ├─ CreateInquiryRequest.yaml                # 신규 문의 생성 입력 구조
│  │  │  │  └─ ResolutionFeedbackRequest.yaml           # 고객 해결·미해결 후속 피드백 구조
│  │  │  ├─ consultation/                               # 상담 기록·요약·완료 요청 관련 Schema
│  │  │  │  ├─ ConsultationRecord.yaml                  # 상담사가 작성한 상담 기록 구조
│  │  │  │  ├─ ConsultationSummary.yaml                 # 상담사가 확정한 상담 요약 구조
│  │  │  │  ├─ SaveConsultationRequest.yaml             # 상담 기록 임시·중간 저장 요청 구조
│  │  │  │  └─ CompleteConsultationRequest.yaml         # 상담 완료와 방문 필요 판단 요청 구조
│  │  │  ├─ visit/                                      # 방문 일정·상세·결과 관련 Schema
│  │  │  │  ├─ VisitSummary.yaml                        # 기사 업무 목록용 방문 요약 구조
│  │  │  │  ├─ VisitDetail.yaml                         # 고객·제품·인계·근거를 포함한 방문 상세 구조
│  │  │  │  ├─ VisitSchedule.yaml                       # 희망일·확정일·담당 기사·일정 상태 구조
│  │  │  │  ├─ VisitResult.yaml                         # 원인·조치·교체·추가 방문을 포함한 결과 구조
│  │  │  │  ├─ CreateVisitRequest.yaml                  # 상담에서 방문 업무를 생성하는 요청 구조
│  │  │  │  ├─ UpdateVisitScheduleRequest.yaml          # 기사 배정·희망일·확정일 수정 요청 구조
│  │  │  │  └─ SubmitVisitResultRequest.yaml            # 기사 방문 결과 저장·완료 요청 구조
│  │  │  ├─ evidence/                                   # 화면용 공식 근거 카드와 출처 Schema
│  │  │  │  ├─ EvidenceCard.yaml                        # 화면에 전달하는 공식 근거 카드 구조
│  │  │  │  ├─ EvidenceSource.yaml                      # 문서명·버전·페이지·공식 URL 구조
│  │  │  │  └─ EvidenceVerification.yaml                # 근거 검증 상태와 사용 허용 범위 구조
│  │  │  ├─ workflow/                                   # 상태 Snapshot·허용 행동·전이 요청 Schema
│  │  │  │  ├─ WorkflowSnapshot.yaml                    # 현재 상태·담당 주체·allowed_actions Snapshot
│  │  │  │  ├─ AllowedAction.yaml                       # 현재 역할이 실행 가능한 행동 코드와 표시 정보
│  │  │  │  ├─ StateTransitionRequest.yaml              # 이벤트·state_version·payload 상태 전이 요청
│  │  │  │  └─ StateTransitionResult.yaml               # 전이 후 상태·버전·허용 행동 결과
│  │  │  └─ operations/                                 # 운영 집계·예외 조회 관련 Schema
│  │  │     ├─ OperationsMetrics.yaml                   # 문의·상담·방문 운영 집계 지표 구조
│  │  │     └─ OperationsExceptionItem.yaml             # 지연·실패·예외 업무 조회 항목
│  │  ├─ parameters/                                    # 공통 Path·Query Parameter 정의
│  │  │  ├─ Page.yaml                                   # 목록 조회의 현재 페이지 번호 Parameter
│  │  │  ├─ Size.yaml                                   # 목록 조회의 페이지당 항목 수 Parameter
│  │  │  ├─ InquiryId.yaml                              # 문의 식별자 Path Parameter
│  │  │  └─ VisitId.yaml                                # 방문 식별자 Path Parameter
│  │  ├─ headers/                                       # 인증·추적·멱등성 HTTP Header 정의
│  │  │  ├─ CorrelationId.yaml                          # 전체 요청 흐름 추적용 X-Correlation-ID Header
│  │  │  ├─ IdempotencyKey.yaml                         # 중복 쓰기 방지용 Idempotency-Key Header
│  │  │  └─ Authorization.yaml                          # JWT Bearer 인증 Authorization Header
│  │  ├─ responses/                                     # HTTP 상태별 공통 오류 응답 정의
│  │  │  ├─ BadRequest.yaml                             # 잘못된 입력에 대한 400 공통 오류 응답
│  │  │  ├─ Unauthorized.yaml                           # 인증 누락·실패에 대한 401 공통 오류 응답
│  │  │  ├─ Forbidden.yaml                              # 역할·담당자 권한 부족에 대한 403 공통 오류 응답
│  │  │  ├─ NotFound.yaml                               # 대상 리소스 없음에 대한 404 공통 오류 응답
│  │  │  ├─ Conflict.yaml                               # 상태 버전·중복 요청 충돌에 대한 409 공통 오류 응답
│  │  │  └─ InternalServerError.yaml                    # 예상하지 못한 서버 오류에 대한 500 공통 응답
│  │  └─ security-schemes/                              # JWT Bearer 인증 방식 정의
│  │     └─ BearerAuth.yaml                             # JWT Bearer Token 인증 방식 정의
│  └─ examples/                                         # 도메인별 API 정상·오류 예시
│     ├─ auth/                                          # 인증 API 정상·오류 요청·응답 예시
│     ├─ inquiries/                                     # 문의 API 정상·오류 요청·응답 예시
│     ├─ consultations/                                 # 상담 API 정상·오류 요청·응답 예시
│     ├─ visits/                                        # 방문 API 정상·오류 요청·응답 예시
│     ├─ evidence/                                      # 공식 근거 API 정상·오류 예시
│     ├─ workflow/                                      # 상태 전환 API 정상·충돌 예시
│     └─ errors/                                        # 공통 업무 오류 응답 예시
│
├─ ai/                                                  # Backend↔AI JSON 계약
│  ├─ requests/                                         # 백엔드에서 AI로 전달하는 요청 JSON Schema
│  │  ├─ SymptomAnalysisRequest.schema.json             # 증상 구조화·안전 판단·검색·고객 안내 통합 요청 Schema
│  │  ├─ ConsultationSummaryRequest.schema.json         # 상담용 AI 요약 초안 생성 요청 Schema
│  │  └─ TechnicianReportRequest.schema.json            # 기사 사전 점검 리포트 생성 요청 Schema
│  ├─ responses/                                        # AI가 백엔드로 반환하는 응답 JSON Schema
│  │  ├─ SymptomAnalysisResponse.schema.json            # 구조화·위험도·근거·고객 안내 통합 응답 Schema
│  │  ├─ ConsultationSummaryResponse.schema.json        # 상담용 AI 요약 초안 응답 Schema
│  │  └─ TechnicianReportResponse.schema.json           # 기사 사전 점검 리포트 응답 Schema
│  ├─ common/                                           # AI 요청·응답이 공유하는 구조와 메타데이터 Schema
│  │  ├─ StructuredSymptom.schema.json                  # 표준화된 증상 필드 공통 Schema
│  │  ├─ MissingField.schema.json                       # 추가 확인이 필요한 누락 필드 Schema
│  │  ├─ FollowUpQuestion.schema.json                   # 누락 정보를 확인하는 추가 질문 Schema
│  │  ├─ SafetyAssessment.schema.json                   # 위험도·우선순위·상담 필요 여부 Schema
│  │  ├─ UsageGuidance.schema.json                      # 사용 가능 여부·제한 기능·다음 행동 안내 Schema
│  │  ├─ EvidenceReference.schema.json                  # AI가 반환하는 내부 문서·청크·페이지 근거 참조 Schema
│  │  ├─ ValidationResult.schema.json                   # 스키마·근거·안전 검증 결과 Schema
│  │  ├─ ProcessingTrace.schema.json                    # 단계별 상태·처리 시간·실패 위치 추적 Schema
│  │  └─ ModelMetadata.schema.json                      # 모델명·프롬프트 버전·토큰 사용량 Schema
│  ├─ examples/                                         # AI 정상·실패·Fallback 요청·응답 예시
│  │  ├─ symptom-analysis/                              # 증상 분석 요청·응답 예시
│  │  ├─ consultation-summary/                          # 상담 요약 요청·응답 예시
│  │  ├─ technician-report/                             # 기사 리포트 요청·응답 예시
│  │  └─ fallback/                                      # 근거 부족·AI 실패 시 Fallback 예시
│  └─ README.md                                         # AI 실행·인덱싱·평가·프롬프트 관리 안내
│
├─ state-machine/                                       # 업무 흐름 계약
│  ├─ inquiry-states.yaml                               # 문의 상태 코드·의미·담당 주체 정의
│  ├─ inquiry-events.yaml                               # 실행 가능한 State Machine 이벤트 정의
│  ├─ transition-rules.yaml                             # 현재 상태·이벤트·결과 상태 전이 규칙
│  ├─ transition-guards.yaml                            # 역할·담당자·필수값 상태 전이 조건
│  ├─ allowed-actions.yaml                              # 상태·역할별 화면 허용 행동 정의
│  ├─ role-permissions.yaml                             # 고객·상담사·기사·운영자 상태 처리 권한
│  ├─ completion-policy.yaml                            # 자가 해결·상담·방문 완료와 재개 정책
│  ├─ concurrency-policy.yaml                           # state_version·Idempotency-Key 동시성 정책
│  ├─ diagrams/                                         # State Machine 흐름을 표현하는 Mermaid 원본
│  │  └─ inquiry-state-machine.mmd                      # 문의·상담·방문 State Machine Mermaid 원본
│  ├─ examples/                                         # 대표 상태 전이 흐름 예시
│  │  ├─ self-resolution.yaml                           # 고객 자가 해결 대표 상태 전이 예시
│  │  ├─ consultation-resolution.yaml                   # 상담 후 해결 대표 상태 전이 예시
│  │  ├─ visit-resolution.yaml                          # 방문 후 해결 대표 상태 전이 예시
│  │  ├─ danger-detected.yaml                           # 위험 감지·사용 제한·상담 전환 상태 예시
│  │  ├─ no-evidence.yaml                               # 공식 근거 없음·판단 보류 상태 예시
│  │  └─ reopened-inquiry.yaml                          # 고객 미해결 피드백·문의 재개 상태 예시
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ codes/                                               # 표준 코드
│  ├─ user-roles.yaml                                   # CUSTOMER·CONSULTANT·TECHNICIAN·OPERATOR 역할 코드
│  ├─ inquiry-statuses.yaml                             # 문의 업무 상태 표준 코드
│  ├─ visit-statuses.yaml                               # 기사 배정·일정·방문 처리 상태 코드
│  ├─ workflow-actions.yaml                             # allowed_actions에 사용하는 업무 행동 코드
│  ├─ risk-levels.yaml                                  # general·caution·danger 위험도 코드
│  ├─ priority-levels.yaml                              # 일반·상담 권고·우선 상담 우선순위 코드
│  ├─ usage-guidance-statuses.yaml                      # 사용 가능·일부 제한·사용 중지 안내 상태 코드
│  ├─ data-classifications.yaml                         # official·team_designed·synthetic 데이터 분류 코드
│  ├─ verification-statuses.yaml                        # 근거·데이터 검증 상태 코드
│  ├─ allowed-use.yaml                                  # 근거 사용 허용 범위 코드
│  ├─ product-scopes.yaml                               # MVP·확장·제외 제품 범위 코드
│  └─ ai-stages.yaml                                    # AI 처리 단계와 실패 위치 코드
│
├─ error-codes/                                         # 업무 오류 코드
│  ├─ error-codes.yaml                                  # 전체 공통 업무 오류 코드 통합 레지스트리
│  ├─ categories/                                       # 도메인별 오류 코드 분류 파일
│  │  ├─ auth.yaml                                      # 인증·세션 오류 코드
│  │  ├─ validation.yaml                                # 입력값·필수값 검증 오류 코드
│  │  ├─ permission.yaml                                # 역할·담당자 권한 오류 코드
│  │  ├─ workflow.yaml                                  # 상태 충돌·중복 이벤트 오류 코드
│  │  ├─ product.yaml                                   # 제품·세대·지원 범위 오류 코드
│  │  ├─ evidence.yaml                                  # 출처·근거 검증 오류 코드
│  │  ├─ ai.yaml                                        # AI 생성·Schema 검증 오류 코드
│  │  ├─ retrieval.yaml                                 # 검색·재정렬 오류 코드
│  │  ├─ persistence.yaml                               # 저장·수정·DB 처리 오류 코드
│  │  └─ external.yaml                                  # 외부 URL·서비스 연동 오류 코드
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
└─ examples/                                            # 영역 연결 대표 흐름
   ├─ customer-to-consultant.json                       # 고객·TO·상담사 JSON 데이터·예시
   ├─ consultant-to-technician.json                     # 상담사·TO·방문기사 JSON 데이터·예시
   ├─ technician-to-customer.json                       # 방문기사·TO·고객 JSON 데이터·예시
   ├─ danger-fallback.json                              # danger·fallback JSON 데이터·예시
   └─ state-conflict.json                               # 상태·conflict JSON 데이터·예시
```

## 6.3 네이밍 규칙

| 대상 | 규칙 | 예시 |
|---|---|---|
| 디렉토리 | `kebab-case` | `state-machine/` |
| DTO·Schema 파일 | `PascalCase` | `EvidenceCard.yaml` |
| 정책·레지스트리 파일 | `kebab-case` | `allowed-actions.yaml` |
| JSON 필드 | `snake_case` | `allowed_actions` |
| 상태·이벤트·Enum | `UPPER_SNAKE_CASE` | `START_CONSULTATION` |
| 오류 코드 | `UPPER-KEBAB-NUMBER` | `STATE-CONFLICT-01` |
| URL | 복수형 `kebab-case` | `/api/v1/inquiries` |

---

# 7. Data 디렉토리 세부 구조

## 7.1 상세 구조

```text
data/                                                   # 공식 문서·전처리·합성 데이터
│
├─ raw/                                                 # 수집 당시 공식 원본
│  ├─ manuals/                                          # 공식 제품 매뉴얼 원본 또는 페이지 추출 데이터
│  │  ├─ mvp/                                           # WPU-JAC104D MVP 공식 매뉴얼 원본 보관 위치
│  │  │  └─ skmagic_wpu_jac104d_jcc104d_rev00.pdf       # Git 제외
│  │  └─ expansion/                                     # WPU-IAC425 확장 매뉴얼 원본 보관 위치
│  │     └─ skmagic_wpu_iac425_rev02.pdf                # MVP 검색 제외
│  ├─ faq/                                              # 공식 FAQ 원문·정규화·적용성 분류 데이터
│  │  ├─ snapshots/                                     # 수집 시점의 FAQ 원문 스냅샷
│  │  └─ source-lists/                                  # FAQ URL·ID·수집 대상 목록
│  ├─ .gitignore                                        # Git에서 제외할 비밀값·빌드 결과·원본 데이터 지정
│  ├─ .gitkeep                                          # 빈 디렉토리를 Git 저장소에 유지하기 위한 파일
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ processed/                                           # 전처리·검수 데이터
│  ├─ documents/                                        # 페이지·문서 단위로 추출한 읽기 가능한 본문
│  │  ├─ manuals/                                       # 공식 제품 매뉴얼 원본 또는 페이지 추출 데이터
│  │  │  ├─ mvp/                                        # JAC104D 매뉴얼 페이지 추출 본문
│  │  │  │  └─ manual_pages_jac104d.jsonl               # JAC104D 매뉴얼의 페이지별 추출 텍스트
│  │  │  └─ expansion/                                  # IAC425 매뉴얼 페이지 추출 본문
│  │  │     └─ manual_pages_iac425.jsonl                # IAC425 확장 매뉴얼의 페이지별 추출 텍스트
│  │  └─ faq/                                           # 공식 FAQ 원문·정규화·적용성 분류 데이터
│  │     └─ faq_snapshot_normalized.jsonl               # 공식 FAQ 스냅샷을 표준 필드로 정규화한 문서
│  ├─ metadata/                                         # 출처·버전·해시·계보·수집 이력
│  │  ├─ source_inventory.csv                           # 공식 문서의 출처·버전·페이지 수·해시 목록
│  │  ├─ model_document_lineage.csv                     # 판매 코드·제품 계열·세대·공식 문서 연결 관계
│  │  ├─ manual_keyword_hits.csv                        # 증상 키워드가 탐지된 매뉴얼 페이지 목록
│  │  ├─ collection_log.csv                             # 데이터 수집 시각·방법·성공 여부 기록
│  │  ├─ error_missing_list.csv                         # 미확보·파싱 실패·모델 불일치 항목 기록
│  │  └─ dataset_manifest.json                          # 현재 데이터셋 버전·구성·건수 요약
│  ├─ structured/                                       # RAG·FAQ·근거 레지스트리 구조화 데이터
│  │  ├─ rag/                                           # 검증된 검색용 RAG 청크 데이터
│  │  │  ├─ mvp/                                        # MVP 검색에 사용되는 검증 RAG 청크
│  │  │  │  └─ rag_verified_sample.jsonl                # JAC104D MVP용 검증 완료 RAG 청크
│  │  │  └─ expansion/                                  # 후속 확장용으로 격리한 RAG 청크
│  │  │     └─ rag_expansion_iac425.jsonl               # IAC425 후속 확장용 RAG 청크
│  │  ├─ faq/                                           # 공식 FAQ 원문·정규화·적용성 분류 데이터
│  │  │  └─ selected_faq_candidates.jsonl               # 적용성·사용 제한을 분류한 FAQ 후보 목록
│  │  └─ evidence/                                      # 근거 사용 가능 범위를 관리하는 레지스트리
│  │     └─ jac104_evidence_registry.jsonl              # JAC104D 공식·조건부·제외 근거 사용 정책 레지스트리
│  └─ validation/                                       # 스키마·정합성·안전성 검증 기능
│     ├─ schema/                                        # 데이터 필드·타입·필수값 검증 결과
│     │  └─ latest_schema_report.json                   # 가장 최근 데이터 Schema 검증 결과
│     ├─ integrity/                                     # 해시·페이지·참조 무결성 검증 결과
│     │  └─ latest_integrity_report.json                # 가장 최근 해시·페이지·참조 무결성 검증 결과
│     ├─ quality/                                       # 중복·빈 본문·인코딩 품질 검증 결과
│     │  └─ latest_quality_report.json                  # 가장 최근 중복·누락·인코딩 품질 검증 결과
│     └─ README.md                                      # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ synthetic/                                           # 실제 개인정보 없는 합성 데이터
│  ├─ scenarios/                                        # 대표 사용자 업무 흐름 합성 시나리오
│  │  ├─ demo_scenarios.json                            # JAC104D 대표 합성 문의 시나리오 통합본
│  │  ├─ self_resolution.json                           # 고객 자가조치 후 해결되는 합성 시나리오
│  │  ├─ consultation_handoff.json                      # 고객 문의가 상담사에게 인계되는 합성 시나리오
│  │  ├─ visit_handoff.json                             # 상담 결과가 방문기사에게 인계되는 합성 시나리오
│  │  ├─ danger_escalation.json                         # 위험 감지 후 사용 제한·상담 우선 전환 시나리오
│  │  ├─ no_evidence_fallback.json                      # 공식 근거 부족 시 판단 보류·상담 전환 시나리오
│  │  └─ reopened_inquiry.json                          # 후속 확인에서 문의가 재개되는 합성 시나리오
│  ├─ fixtures/                                         # DB Seed와 통합 테스트에 사용하는 합성 데이터
│  │  ├─ users.json                                     # 가상 고객·상담사·기사·운영 담당자 데이터
│  │  ├─ products.json                                  # MVP·확장 제품 기본 데이터
│  │  ├─ subscriptions.json                             # 가상 제품 구독·관리 계약 데이터
│  │  ├─ care_histories.json                            # 가상 필터 교체·정기 관리 이력 데이터
│  │  ├─ inquiries.json                                 # 가상 문의·증상·문진 데이터
│  │  ├─ consultations.json                             # 가상 상담 기록과 확정 요약 데이터
│  │  ├─ visits.json                                    # 가상 방문 일정·점검·결과 데이터
│  │  └─ audit_events.json                              # 가상 상태 전환·사용자 행동 감사 이력
│  ├─ expected/                                         # 상태·근거·안전·인계의 기대 결과
│  │  ├─ workflow_states.json                           # 시나리오별 기대 상태와 allowed_actions 결과
│  │  ├─ evidence_references.json                       # 시나리오별 기대 공식 청크·문서·페이지 참조
│  │  ├─ safety_assessments.json                        # 시나리오별 기대 위험도와 제품 사용 안내
│  │  └─ role_handoffs.json                             # 상담사·기사에게 전달돼야 하는 기대 인계 정보
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ schemas/                                             # 저장 데이터 검증 Schema
│  ├─ processed/                                        # 전처리·구조화 데이터 파일 검증 Schema
│  │  ├─ manualPage.schema.json                         # 매뉴얼 페이지 추출 데이터 검증 JSON Schema
│  │  ├─ sourceInventory.schema.json                    # 공식 출처·무결성 메타데이터 검증 JSON Schema
│  │  ├─ ragChunk.schema.json                           # RAG 청크 필드·타입·참조 검증 JSON Schema
│  │  ├─ faqCandidate.schema.json                       # FAQ 적용성 분류 데이터 검증 JSON Schema
│  │  └─ evidenceRegistry.schema.json                   # 근거 사용 정책 레지스트리 검증 JSON Schema
│  ├─ synthetic/                                        # 합성 시나리오·Fixture·기대 결과 검증 Schema
│  │  ├─ demoScenario.schema.json                       # 합성 업무 시나리오 검증 JSON Schema
│  │  ├─ syntheticInquiry.schema.json                   # 합성 문의 데이터 검증 JSON Schema
│  │  └─ expectedWorkflow.schema.json                   # 기대 상태 전이와 허용 행동 검증 JSON Schema
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ catalog/                                             # 사람이 읽는 데이터 카탈로그
│  ├─ datasets.yaml                                     # datasets 설정·정책 정의
│  ├─ field_dictionary.yaml                             # 필드·dictionary 설정·정책 정의
│  └─ CHANGELOG.md                                      # 버전별 추가·변경·제외 내역 기록
│
└─ README.md                                            # 데이터 처리 흐름·출처·사용 범위 전체 안내
```

## 7.2 처리 흐름

```text
공식 원본
→ 페이지·FAQ 문서 추출
→ 출처·모델 계보 기록
→ MVP·확장 적용성 분류
→ RAG 청크·근거 레지스트리 생성
→ Schema·해시·페이지·참조 검증
→ AI 인덱싱 또는 시연·테스트에 사용
```

## 7.3 관리 원칙

```text
raw/
├─ 원본 수정 금지
├─ 전처리 결과 저장 금지
├─ Git Commit 금지
└─ README·.gitignore·.gitkeep만 Git 관리

MVP 검색
└─ WPU-JAC104D 계열만 사용

후속 확장
└─ WPU-IAC425 별도 보관·별도 인덱스

data/archive/
└─ 생성 금지
```

## 7.4 네이밍 규칙

| 대상 | 규칙 | 예시 |
|---|---|---|
| 데이터 디렉토리 | 소문자 또는 `kebab-case` | `source-lists/` |
| CSV·JSON·JSONL | `snake_case` | `source_inventory.csv` |
| JSON 필드 | `snake_case` | `exact_sales_code` |
| JSON Schema | `camelCase.schema.json` | `ragChunk.schema.json` |
| 상태·Enum | `UPPER_SNAKE_CASE` | `MVP_PRIMARY` |
| 문서·청크 ID | 대문자·하이픈 | `MAN-WPU-JAC104D-P38-LOW-FLOW` |
| 합성 ID | `SYN-`·`DEMO-` 접두사 | `SYN-JAC104-001` |

---

# 8. Infra 디렉토리 세부 구조

## 8.1 환경 구분

```text
로컬 개발
└─ Docker Compose

PR·통합 검증
└─ GitHub Actions + Docker Compose CI 환경

공유 개발·시연
└─ Kubernetes demo 환경

별도 production
└─ MVP 범위에서는 생성하지 않음
```

## 8.2 상세 구조

```text
infra/                                             # 로컬·배포·운영 설정
│
├─ docker/                                              # Docker Compose 실행 설정
│  ├─ compose/                                          # 로컬·CI·비상 시연용 Docker Compose 조합
│  │  ├─ docker-compose.base.yml                        # 공통 서비스·네트워크·볼륨 Docker Compose 설정
│  │  ├─ docker-compose.dev.yml                         # 로컬 개발 포트·볼륨·Hot Reload Docker Compose 설정
│  │  ├─ docker-compose.ci.yml                          # GitHub Actions 통합 테스트 Docker Compose 설정
│  │  └─ docker-compose.demo.yml                        # Kubernetes 장애 시 비상 시연 Docker Compose 설정
│  ├─ env/                                              # 서비스별 환경변수 이름 예시
│  │  ├─ common.env.example                             # common 서비스 환경변수 이름·예시·필수 여부 안내
│  │  ├─ web.env.example                                # 웹 서비스 환경변수 이름·예시·필수 여부 안내
│  │  ├─ backend.env.example                            # 백엔드 서비스 환경변수 이름·예시·필수 여부 안내
│  │  ├─ ai.env.example                                 # AI 서비스 환경변수 이름·예시·필수 여부 안내
│  │  └─ database.env.example                           # 데이터베이스 서비스 환경변수 이름·예시·필수 여부 안내
│  ├─ healthcheck/                                      # Compose 서비스 준비 상태 확인 스크립트
│  │  ├─ check_backend.sh                               # Django Backend Health Endpoint 확인 스크립트
│  │  ├─ check_ai.sh                                    # AI 서비스 Health Endpoint 확인 스크립트
│  │  └─ check_postgresql.sh                            # PostgreSQL 연결·응답 상태 확인 스크립트
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ kubernetes/                                          # 공유 개발·시연 배포 선언
│  ├─ base/                                             # 모든 Kubernetes 환경이 공유하는 기본 리소스
│  │  ├─ namespace/                                     # 프로젝트 전용 Kubernetes Namespace 선언
│  │  │  ├─ namespace.yaml                              # Namespace 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ web/                                           # React 정적 웹 Deployment·Service·ConfigMap
│  │  │  ├─ deployment.yaml                             # 배포 설정·정책 정의
│  │  │  ├─ service.yaml                                # 서비스 설정·정책 정의
│  │  │  ├─ configmap.yaml                              # ConfigMap 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ backend/                                       # Django API Deployment·Service·ServiceAccount
│  │  │  ├─ deployment.yaml                             # 배포 설정·정책 정의
│  │  │  ├─ service.yaml                                # 서비스 설정·정책 정의
│  │  │  ├─ configmap.yaml                              # ConfigMap 설정·정책 정의
│  │  │  ├─ service-account.yaml                        # 서비스·계정 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ ai/                                            # AI 내부 서비스 Deployment·Service·ConfigMap
│  │  │  ├─ deployment.yaml                             # 배포 설정·정책 정의
│  │  │  ├─ service.yaml                                # 서비스 설정·정책 정의
│  │  │  ├─ configmap.yaml                              # ConfigMap 설정·정책 정의
│  │  │  ├─ service-account.yaml                        # 서비스·계정 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ ingress/                                       # 외부 URL을 Web·Backend Service로 라우팅
│  │  │  ├─ ingress.yaml                                # Ingress 설정·정책 정의
│  │  │  ├─ tls.yaml                                    # TLS 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ jobs/                                          # Migration·Seed·인덱싱·Smoke 일회성 작업
│  │  │  ├─ migration-job.yaml                          # Migration·Job 설정·정책 정의
│  │  │  ├─ seed-job.yaml                               # Seed·Job 설정·정책 정의
│  │  │  ├─ vector-index-job.yaml                       # 벡터·인덱스·Job 설정·정책 정의
│  │  │  ├─ smoke-test-job.yaml                         # Smoke Test·테스트·Job 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ external-services/                             # 클러스터 밖 DB·Vector Store 연결 추상화
│  │  │  ├─ postgresql-service.yaml                     # PostgreSQL·서비스 설정·정책 정의
│  │  │  ├─ vector-store-service.yaml                   # 벡터·저장소·서비스 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ security/                                      # NetworkPolicy·Secret 예시 등 보안 경계
│  │  │  ├─ network-policy.yaml                         # 네트워크·정책 설정·정책 정의
│  │  │  ├─ secret.example.yaml                         # 비밀값·example 설정·정책 정의
│  │  │  └─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │  ├─ availability/                                  # 자원 제한과 정상 종료 등 가용성 설정
│  │  │  ├─ resource-limits-patch.yaml                  # 리소스·limits·patch 설정·정책 정의
│  │  │  └─ termination-policy-patch.yaml               # 종료·정책·patch 설정·정책 정의
│  │  └─ kustomization.yaml                             # kustomization 설정·정책 정의
│  ├─ overlays/                                         # 환경별 차이만 덮어쓰는 Kustomize 설정
│  │  └─ demo/                                          # 팀 공유 개발·중간·최종 시연 환경 Overlay
│  │     ├─ kustomization.yaml                          # kustomization 설정·정책 정의
│  │     ├─ ingress-patch.yaml                          # Ingress·patch 설정·정책 정의
│  │     ├─ image-tags-patch.yaml                       # image·tags·patch 설정·정책 정의
│  │     ├─ replica-patch.yaml                          # 복제본·patch 설정·정책 정의
│  │     ├─ resource-patch.yaml                         # 리소스·patch 설정·정책 정의
│  │     └─ config-patch.yaml                           # 설정·patch 설정·정책 정의
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ cloud/                                               # 공급자별 연결·권한
│  ├─ aws/                                              # AWS Registry·Secret·IAM·RDS 연동 자료
│  │  ├─ registry/README.md                             # registry 관련 파일과 하위 항목을 관리하는 디렉토리
│  │  ├─ secrets/README.md                              # secrets 관련 파일과 하위 항목을 관리하는 디렉토리
│  │  ├─ iam/README.md                                  # iam 관련 파일과 하위 항목을 관리하는 디렉토리
│  │  ├─ database/README.md                             # PostgreSQL 데이터·Migration·Seed 관련 요소
│  │  └─ README.md                                      # 현재 디렉토리의 사용·관리·갱신 방법 안내
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ monitoring/                                          # 로그·Health·지표·알림
│  ├─ logging/                                          # 구조화 로그 필드와 민감정보 제외 기준
│  │  ├─ fields.yaml                                    # 필드 설정·정책 정의
│  │  └─ README.md                                      # 현재 디렉토리의 사용·관리·갱신 방법 안내
│  ├─ health/                                           # Liveness·Readiness Endpoint와 점검 기준
│  │  ├─ endpoints.yaml                                 # endpoints 설정·정책 정의
│  │  └─ README.md                                      # 현재 디렉토리의 사용·관리·갱신 방법 안내
│  ├─ dashboards/                                       # 서비스 상태와 AI 성능 대시보드 정의
│  │  ├─ service-health.json                            # 서비스·health JSON 데이터·예시
│  │  └─ ai-performance.json                            # AI·성능 JSON 데이터·예시
│  ├─ alerts/                                           # Pod 실패·응답 오류·AI 지연 알림 규칙
│  │  └─ alert-rules.yaml                               # 알림·규칙 설정·정책 정의
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ backup/                                              # PostgreSQL 백업과 복구 정책 문서
│  ├─ backup-policy.md                                  # 백업·정책 설명·운영 기준 문서
│  ├─ restore-policy.md                                 # 복구·정책 설명·운영 기준 문서
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
└─ README.md                                            # 인프라 구성·실행·배포·복구 절차 안내
```

## 8.3 배포 경계

```text
Kubernetes 배포
├─ web
├─ backend
└─ ai

Kubernetes 미배포
└─ mobile APK·AAB

외부 공개
├─ `/` → web Service  # ` 관련 파일과 하위 항목을 관리하는 디렉토리
└─ `/api/v1` → backend Service  # ` 관련 파일과 하위 항목을 관리하는 디렉토리

클러스터 내부
├─ ai Service
├─ PostgreSQL
└─ Vector Store
```

## 8.4 Job 실행 순서

```text
1. PostgreSQL 연결·백업 확인
2. migration-job
3. 필요 시 seed-job
4. 필요 시 vector-index-job
5. Web·Backend·AI Deployment 갱신
6. smoke-test-job
7. 외부 대표 E2E
```

Django Migration은 Backend Pod 시작 명령에 포함하지 않고 별도 Kubernetes Job으로 한 번만 실행한다.

---

# 9. CI/CD 디렉토리 세부 구조

## 9.1 `.github/` 구조

```text
.github/                                                # github 항목의 역할과 책임 설명
│
├─ workflows/                                           # 영역별 CI·이미지 빌드·배포·롤백 Workflow
│  ├─ web-ci.yml                                        # React Web 검증
│  ├─ mobile-ci.yml                                     # Kotlin·Compose 검증
│  ├─ backend-ci.yml                                    # Django·DRF 검증
│  ├─ ai-ci.yml                                         # AI·RAG 검증
│  ├─ contracts-ci.yml                                  # OpenAPI·Schema·상태 계약
│  ├─ data-ci.yml                                       # 데이터 Schema·무결성
│  ├─ integration-ci.yml                                # Docker Compose 통합 검증
│  ├─ e2e-ci.yml                                        # 정상·위험·근거 없음 E2E
│  ├─ build-images.yml                                  # Web·Backend·AI 이미지
│  ├─ build-mobile.yml                                  # Android APK Artifact
│  ├─ deploy-demo.yml                                   # 승인 후 Kubernetes 배포
│  ├─ reset-demo.yml                                    # Demo Seed·Index 초기화
│  ├─ rollback-demo.yml                                 # 이전 이미지 롤백
│  └─ release.yml                                       # SemVer Release
│
├─ actions/                                             # 재사용 GitHub Action
│  ├─ setup-python/action.yml                           # setup python 관련 파일과 하위 항목을 관리하는 디렉토리
│  ├─ setup-node/action.yml                             # setup node 관련 파일과 하위 항목을 관리하는 디렉토리
│  ├─ setup-android/action.yml                          # setup android 관련 파일과 하위 항목을 관리하는 디렉토리
│  ├─ docker-metadata/action.yml                        # docker metadata 관련 파일과 하위 항목을 관리하는 디렉토리
│  └─ wait-for-service/action.yml                       # wait for service 관련 파일과 하위 항목을 관리하는 디렉토리
│
├─ ISSUE_TEMPLATE/                                      # 기능·버그 Issue 작성 양식
│  ├─ feature.yml                                       # 기능 Issue 작성 양식
│  └─ bug.yml                                           # 버그 Issue 작성 양식
│
├─ CODEOWNERS                                           # 영역별 기본 코드 리뷰 담당자를 지정
├─ pull_request_template.md                             # PR 변경 내용·테스트·영향 범위 작성 양식
└─ dependabot.yml                                       # 의존성 자동 업데이트 정책 설정
```

## 9.2 영역별 CI

```text
web-ci.yml
├─ npm ci
├─ Formatter
├─ TypeScript typecheck
├─ 단위·컴포넌트 테스트
└─ Vite production build

mobile-ci.yml
├─ JDK·Android SDK
├─ Kotlin Formatter
├─ JVM 단위 테스트
├─ Android Lint
└─ assembleDebug

backend-ci.yml
├─ Python 의존성
├─ Formatter
├─ Django system check
├─ makemigrations --check --dry-run
├─ PostgreSQL Migration
└─ 단위·API·State Machine 테스트

ai-ci.yml
├─ Formatter
├─ Prompt Registry 검증
├─ Pydantic·JSON Schema 검증
├─ 구조화·안전·검색 테스트
└─ PR에서는 Mock LLM 우선

contracts-ci.yml
├─ OpenAPI·JSON Schema 문법
├─ YAML 참조
├─ Example 일치
├─ 상태·이벤트·allowed_actions 참조
└─ 오류 코드 중복

data-ci.yml
├─ 공식 원본 Git 포함 여부
├─ JSON·JSONL·CSV 구문
├─ Schema 일치
├─ ID·페이지 참조 무결성
├─ MVP·확장 혼입
└─ IAC506 존재 여부
```

## 9.3 CI/CD 흐름

```text
기능 브랜치 Push
→ 변경 경로별 CI 병렬 실행
→ 필요 시 Integration·E2E
→ 리뷰 승인
→ main 병합
→ Docker 이미지·APK 빌드
→ GitHub Environment `demo` 승인
→ Migration Job
→ Kubernetes Rollout
→ Smoke Test
→ 대표 E2E
→ 실패 시 이전 이미지로 롤백
```

## 9.4 이미지 태그

```text
허용
├─ v0.5.0
├─ v1.0.0
└─ sha-a1b2c3d

금지
└─ 실제 배포에서 latest만 사용
```

---

# 10. Scripts 디렉토리 세부 구조

## 10.1 상세 구조

```text
scripts/                                            # 저장소 전체 자동화
│
├─ common/                                              # 자동화 스크립트가 공유하는 경로·환경·실행 도구
│  ├─ paths.py                                          # 저장소 루트와 영역별 절대 경로 계산
│  ├─ process.py                                        # 외부 명령 실행·표준 출력·종료 코드 처리
│  ├─ environment.py                                    # 환경변수 로딩과 필수 설정 누락 검사
│  ├─ console.py                                        # 스크립트 공통 콘솔 메시지와 상태 표시
│  └─ identifiers.py                                    # 실행 ID·배포 ID·추적 ID 생성
│
├─ data/                                                # 공식 문서 추출·정규화·RAG·데이터 검증 자동화
│  ├─ extract_manual_pages.py                           # 공식 PDF에서 페이지별 텍스트 추출
│  ├─ normalize_faq_snapshots.py                        # FAQ 스냅샷을 표준 JSONL 구조로 정규화
│  ├─ build_source_inventory.py                         # 공식 출처·버전·해시 Inventory 생성
│  ├─ build_model_lineage.py                            # 제품 코드·세대·공식 문서 계보 생성
│  ├─ build_rag_chunks.py                               # 검증용 구조화 RAG 청크 생성
│  ├─ build_evidence_registry.py                        # 공식·조건부·제외 근거 레지스트리 생성
│  ├─ validate_processed_data.py                        # 전처리 데이터 Schema·중복·참조 무결성 검증
│  ├─ validate_synthetic_data.py                        # 합성 데이터 ID·상태·근거 참조 검증
│  ├─ check_model_scope.py                              # MVP·확장 데이터 혼입 여부 검사
│  └─ check_legacy_exclusion.py                         # 제외 모델 IAC506 관련 데이터 존재 여부 검사
│
├─ database/                                            # Migration·Seed·백업·복구 자동화
│  ├─ check_migrations.py                               # Django Migration 누락·충돌 여부 검사
│  ├─ apply_migrations.py                               # 로컬·CI 환경에 Django Migration 적용
│  ├─ seed_demo_data.py                                 # 합성 시연 데이터를 PostgreSQL에 Upsert
│  ├─ reset_demo_data.py                                # 시연용 업무 데이터를 초기 상태로 재설정
│  ├─ verify_demo_data.py                               # 대표 제품·고객·문의 Seed 존재 여부 확인
│  ├─ backup_postgresql.py                              # pg_dump를 사용한 PostgreSQL 논리 백업
│  └─ restore_postgresql.py                             # 승인된 PostgreSQL 백업 파일 복구
│
├─ development/                                         # 로컬 환경 준비·실행·종료·초기화 자동화
│  ├─ bootstrap.py                                      # 최초 개발 환경·의존성·필수 디렉토리 준비
│  ├─ check_environment.py                              # Docker·Python·Node·JDK·환경변수 설치 상태 검사
│  ├─ start_local.py                                    # Docker Compose 기반 로컬 개발 환경 시작
│  ├─ stop_local.py                                     # 로컬 개발 서비스 정상 종료
│  ├─ reset_local.py                                    # 로컬 컨테이너·볼륨·Seed 데이터 초기화
│  ├─ wait_for_services.py                              # Backend·AI·DB 준비 상태가 될 때까지 대기
│  └─ print_service_urls.py                             # 로컬 서비스 URL과 시연 계정 정보 출력
│
├─ contracts/                                           # OpenAPI·Schema·State Machine·코드 검증 자동화
│  ├─ validate_openapi.py                               # OpenAPI 문법·참조·Example 정합성 검증
│  ├─ validate_json_schemas.py                          # AI·데이터 JSON Schema 문법과 예시 검증
│  ├─ validate_state_machine.py                         # 상태·이벤트·전이·가드 연결 관계 검증
│  ├─ validate_allowed_actions.py                       # 상태·역할별 allowed_actions 정합성 검증
│  ├─ validate_codes.py                                 # 공통 코드 중복과 참조 무결성 검증
│  ├─ validate_error_codes.py                           # 오류 코드·HTTP 상태·재시도 정책 정합성 검증
│  ├─ validate_examples.py                              # 계약 예시 JSON이 Schema와 일치하는지 검증
│  └─ check_breaking_changes.py                         # 이전 계약 버전 대비 비호환 변경 탐지
│
├─ testing/                                             # 계약·통합·E2E·성능·Smoke 테스트 실행 조율
│  ├─ run_contract_tests.py                             # 최상위 계약 테스트 일괄 실행
│  ├─ run_integration_tests.py                          # 서비스·DB·AI 통합 테스트 일괄 실행
│  ├─ run_e2e_tests.py                                  # 대표 사용자 업무 흐름 E2E 테스트 실행
│  ├─ run_safety_tests.py                               # 위험·근거·모델 범위 안전성 테스트 실행
│  ├─ run_performance_tests.py                          # API·AI 성능 테스트와 기준값 측정
│  ├─ run_resilience_tests.py                           # 타임아웃·재시도·Fallback 복원력 테스트 실행
│  ├─ run_smoke_tests.py                                # 로컬·CI·Demo 환경 핵심 기능 Smoke Test 실행
│  └─ collect_test_reports.py                           # 영역별 테스트 결과를 통합 리포트로 취합
│
├─ deployment/                                          # Kubernetes 배포·Job·Rollout·롤백 자동화
│  ├─ check_cluster.py                                  # Kubernetes 클러스터·Namespace·권한 상태 확인
│  ├─ run_migration_job.py                              # Django Migration Kubernetes Job 실행·완료 확인
│  ├─ run_seed_job.py                                   # 합성 시연 데이터 Seed Kubernetes Job 실행
│  ├─ run_vector_index_job.py                           # MVP Vector Index Kubernetes Job 실행
│  ├─ deploy_demo.py                                    # Kustomize 기반 Demo 환경 배포와 이미지 갱신
│  ├─ verify_rollout.py                                 # Kubernetes Deployment Rollout 완료 여부 확인
│  ├─ verify_demo_environment.py                        # Demo URL·Health·대표 데이터·버전 확인
│  ├─ rollback_demo.py                                  # 이전 Web·Backend·AI 이미지 태그로 Demo 환경 복구
│  └─ record_deployment.py                              # 배포 버전·Commit·시간·결과 기록
│
├─ release/                                             # 버전·Release Note·제출 패키지 생성 자동화
│  ├─ validate_version.py                               # Semantic Version 형식과 Git 태그 정합성 검증
│  ├─ generate_release_notes.py                         # CHANGELOG를 기반으로 Release Note 생성
│  ├─ verify_release_artifacts.py                       # 이미지·APK·문서·테스트 리포트 존재 여부 검사
│  ├─ build_deliverable_index.py                        # 최종 제출 산출물 파일·링크·버전 목록 생성
│  └─ package_submission.py                             # 최종 제출용 파일을 검증해 압축 패키지 생성
│
└─ README.md                                            # 스크립트 실행법·선행 조건·책임 경계 안내
```

## 10.2 책임 원칙

```text
영역 고유 명령
├─ Web → web/package.json  # Web → web 관련 파일과 하위 항목을 관리하는 디렉토리
├─ Mobile → Gradle Task
├─ Django 업무 명령 → backend/.../management/commands/  # Django 업무 명령 → backend 관련 파일과 하위 항목을 관리하는 디렉토리
└─ AI 인덱싱·평가 → ai/scripts/  # AI 인덱싱·평가 → ai 관련 파일과 하위 항목을 관리하는 디렉토리

여러 영역을 조율하는 명령
└─ 최상위 scripts/  # 여러 기술 영역을 함께 조율하는 저장소 공통 자동화
```

최상위 자동화는 Windows와 Linux에서 모두 실행하기 쉽도록 Python을 기본 언어로 사용한다.

---

# 11. Tests 디렉토리 세부 구조

## 11.1 테스트 위치 구분

```text
영역 내부
├─ web/tests/  # 상담사·운영 담당자용 React 웹 애플리케이션
├─ mobile/app/src/test/  # 고객·방문기사용 Kotlin·Jetpack Compose Android 앱
├─ mobile/app/src/androidTest/  # 고객·방문기사용 Kotlin·Jetpack Compose Android 앱
├─ backend/tests/  # Django·DRF 기반 REST API와 업무 상태 관리 영역
└─ ai/tests/  # 백엔드와 AI 간 요청·응답 계약 테스트

최상위 tests/
└─ 둘 이상의 서비스·저장소가 연결되어야 하는 검증
```

## 11.2 상세 구조

```text
tests/                                              # 통합 품질 검증
│
├─ contract/                                            # API·AI·상태·코드 계약 자동 검증
│  ├─ api/                                              # OpenAPI 요청·응답·예시 계약 검증
│  │  ├─ requests/                                      # REST 요청 Body·Header·Parameter 계약 테스트
│  │  ├─ responses/                                     # REST 정상·오류 응답 Wrapper 계약 테스트
│  │  └─ examples/                                      # OpenAPI 예시와 Schema 일치 여부 테스트
│  ├─ ai/                                               # 백엔드와 AI 간 요청·응답 계약 테스트
│  │  ├─ requests/                                      # 백엔드→AI 요청 JSON Schema 계약 테스트
│  │  └─ responses/                                     # AI→백엔드 응답 JSON Schema 계약 테스트
│  ├─ state-machine/                                    # 상태·이벤트·가드·허용 행동 계약 테스트
│  │  ├─ transitions/                                   # 모든 상태 전이 규칙 테스트
│  │  ├─ guards/                                        # 역할·담당자·필수값 Guard 테스트
│  │  └─ allowed-actions/                               # 상태·역할별 허용 행동 테스트
│  ├─ codes/                                            # 역할·상태·위험도 표준 코드 검증
│  ├─ error-codes/                                      # 업무 오류 코드와 HTTP 상태 검증
│  └─ test_contract_references.py                       # 계약 파일 간 참조 경로와 대상 존재 여부 테스트
│
├─ integration/                                         # 서비스·저장소 간 실제 연결 테스트
│  ├─ backend-database/                                 # Django ORM과 PostgreSQL 연동 테스트
│  ├─ backend-ai/                                       # 백엔드의 AI 요청·응답·저장 연동 테스트
│  ├─ backend-vector-store/                             # 백엔드와 Vector Store 연결 테스트
│  ├─ evidence-pipeline/                                # 근거 참조에서 EvidenceCard 조립까지 검증
│  ├─ workflow/                                         # API 요청부터 상태 전환·이력 저장까지 검증
│  ├─ permissions/                                      # 역할·담당자별 데이터 접근 권한 검증
│  ├─ idempotency/                                      # 동일 키 재요청의 중복 처리 방지 검증
│  ├─ concurrency/                                      # state_version 기반 동시 수정 충돌 검증
│  └─ tracing/                                          # correlation_id 기반 서비스 간 로그 연결 검증
│
├─ e2e/                                                 # 고객·상담사·기사·운영자를 잇는 전체 흐름 테스트
│  ├─ scenarios/                                        # 업무 유형별 E2E 시나리오
│  │  ├─ self-resolution/                               # 고객 자가조치 후 해결되는 흐름
│  │  ├─ consultation-resolution/                       # 상담 처리 후 해결되는 흐름
│  │  ├─ visit-resolution/                              # 상담에서 방문과 후속 확인까지 이어지는 흐름
│  │  ├─ danger-escalation/                             # 위험 감지 후 사용 제한·우선 상담 흐름
│  │  ├─ no-evidence-fallback/                          # 공식 근거 부족 시 판단 보류·상담 연결 흐름
│  │  └─ reopened-inquiry/                              # 완료 후 미해결 피드백으로 문의가 재개되는 흐름
│  ├─ clients/                                          # 고객·상담사·기사·운영자 역할별 테스트 클라이언트
│  │  ├─ customer_client.py                             # 고객 역할 API 요청을 수행하는 E2E 테스트 클라이언트
│  │  ├─ consultant_client.py                           # 상담사 역할 API 요청을 수행하는 E2E 테스트 클라이언트
│  │  ├─ technician_client.py                           # 방문기사 역할 API 요청을 수행하는 E2E 테스트 클라이언트
│  │  └─ operator_client.py                             # 운영 담당자 역할 API 요청을 수행하는 E2E 테스트 클라이언트
│  ├─ assertions/                                       # 상태·근거·안전·인계 공통 검증 함수
│  │  ├─ workflow_assertions.py                         # 상태·담당 주체·allowed_actions 공통 검증 함수
│  │  ├─ evidence_assertions.py                         # 근거·문서·페이지·비노출 필드 공통 검증 함수
│  │  ├─ safety_assertions.py                           # 위험도·사용 안내·금지 행동 공통 검증 함수
│  │  └─ handoff_assertions.py                          # 상담·방문 인계 필수 정보 공통 검증 함수
│  ├─ test_self_resolution.py                           # 고객 자가 해결 전체 흐름 E2E 테스트
│  ├─ test_consultation_resolution.py                   # 상담 후 해결·완료 처리 E2E 테스트
│  ├─ test_visit_resolution.py                          # 상담→방문→후속 확인 전체 흐름 E2E 테스트
│  ├─ test_danger_escalation.py                         # 위험 감지·사용 제한·우선 상담 E2E 테스트
│  ├─ test_no_evidence_fallback.py                      # 공식 근거 부족 시 안전한 Fallback E2E 테스트
│  └─ test_reopened_inquiry.py                          # 미해결 피드백에 따른 문의 재개 E2E 테스트
│
├─ safety/                                              # 서비스 전체 안전성 회귀 테스트
│  ├─ risk-guidance/                                    # 누수·전기·화상·온수 위험 분기 검증
│  ├─ prohibited-actions/                               # 분해·직접 수리 등 금지 행동 차단 검증
│  ├─ prohibited-expressions/                           # 확정 진단·안전 보증 표현 차단 검증
│  ├─ grounding/                                        # 공식 근거 없는 생성과 참조 불일치 검증
│  ├─ model-scope/                                      # JAC104·IAC425·IAC506 모델 범위 검증
│  ├─ evidence-exposure/                                # 내부 경로·원문 전체 비노출 검증
│  ├─ faq-policy/                                       # 미검증 FAQ 단독 답변 차단 검증
│  └─ privacy/                                          # 개인정보·비밀값 노출 패턴 검증
│
├─ performance/                                         # API·AI·DB 성능과 복원력 테스트
│  ├─ api/                                              # 일반 REST API 응답 시간과 안정성 측정
│  ├─ ai/                                               # AI 전체·단계별 응답 시간과 p95 측정
│  ├─ database/                                         # 주요 조회·저장 Query 성능 측정
│  ├─ idempotency/                                      # 동일 키 반복 요청 처리 성능과 정확성 검증
│  ├─ concurrency/                                      # 동시 상태 전환 요청의 충돌 처리 검증
│  ├─ resilience/                                       # 타임아웃·재시도·Fallback 복원력 검증
│  └─ baselines/                                        # 버전별 성능 기준 측정값
│
├─ smoke/                                               # 배포 직후 핵심 기능 최소 확인
│  ├─ local/                                            # Docker Compose 로컬 환경 Smoke Test
│  ├─ ci/                                               # GitHub Actions 통합 환경 Smoke Test
│  └─ demo/                                             # Kubernetes 시연 환경 Smoke Test
│
├─ fixtures/                                            # 테스트 도구용 소규모 입력과 Mock 자료
│  ├─ api/                                              # API 요청·응답 테스트용 소규모 Fixture
│  ├─ ai/                                               # AI Mock 요청·응답 테스트 Fixture
│  ├─ errors/                                           # 오류 코드·재시도·권한 응답 Fixture
│  ├─ mocks/                                            # 외부 LLM·Vector Store 대체 응답
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ helpers/                                             # 환경·인증·DB·리포트 공통 테스트 도구
│  ├─ environment.py                                    # 환경변수 로딩과 필수 설정 누락 검사
│  ├─ service_waiter.py                                 # 통합 테스트 전 서비스 준비 상태를 대기·확인
│  ├─ database.py                                       # 테스트 DB 초기화·정리·Fixture 적재 보조 코드
│  ├─ auth.py                                           # 역할별 테스트 인증 토큰과 헤더 생성 보조 코드
│  └─ report.py                                         # 테스트 결과를 표준 형식으로 기록하는 보조 코드
│
├─ config/                                              # 로컬·CI·Demo 테스트 환경 설정
│  ├─ local.yaml                                        # 로컬 설정·정책 정의
│  ├─ ci.yaml                                           # CI 설정·정책 정의
│  └─ demo.yaml                                         # 시연 설정·정책 정의
│
├─ reports/                                             # 자동 생성되는 테스트 원시·통합 결과
│  ├─ raw/                                              # 도구가 직접 생성한 XML·JSON·HTML 결과
│  ├─ merged/                                           # 영역별 테스트 결과를 취합한 산출물
│  ├─ .gitignore                                        # Git에서 제외할 비밀값·빌드 결과·원본 데이터 지정
│  └─ README.md                                         # 현재 디렉토리의 사용·관리·갱신 방법 안내
│
├─ conftest.py                                          # Pytest 공통 Fixture와 테스트 초기화 설정
└─ README.md                                            # 통합 테스트 실행 순서·환경·완료 기준 안내
```

## 11.3 테스트 데이터 구분

```text
data/synthetic/                                         # data/synthetic 항목의 역할과 책임 설명
└─ 서비스가 사용하는 공식 합성 업무 데이터                               # 서비스가 사용하는 공식 합성 업무 데이터 항목의 역할과 책임 설명

tests/fixtures/
└─ 잘못된 요청·Mock 응답 등 테스트 도구용 소규모 입력                      # 잘못된 요청·mock 응답 등 테스트 도구용 소규모 입력 항목의 역할과 책임 설명
```

---

# 12. Docs 디렉토리 세부 구조

## 12.1 상세 구조

```text
docs/
├─ planning/           # 공식 산출물
├─ architecture/       # 전체 구조
├─ technical/          # 영역별 개발 설명
├─ testing/            # 테스트 문서
├─ deployment/         # 실행·배포 방법
├─ daily-scrum/        # 데일리 스크럼
├─ weekly-standup/     # 데일리 스크럼
├─ presentation/       # 주간·중간·최종 발표
└─ submission/         # 최종 제출 준비
```

## 12.2 문서 책임 경계

```text
contracts/                                              # 계약 항목의 역할과 책임 설명
└─ 기계가 검증하는 계약 원본                                       # 기계가 검증하는 계약 원본 항목의 역할과 책임 설명

docs/api/
└─ 사람이 이해하기 위한 API 설명                                   # 사람이 이해하기 위한 api 설명 항목의 역할과 책임 설명

tests/reports/
└─ 자동 생성 원시 결과, Git 제외                                  # 자동 생성 원시 결과, git 제외 항목의 역할과 책임 설명

docs/testing/results/
└─ 사람이 검토·승인한 결과 보고서                                    # 사람이 검토·승인한 결과 보고서 항목의 역할과 책임 설명
```

---

---

# 13. Backend 디렉토리 세부 구조

## 13.1 설계 원칙

공통 개발 규칙의 `Controller–Service–Repository` 구조를 Django·DRF에 맞게 적용한다.

```text
DRF View·ViewSet                                      # HTTP 요청·응답과 인증 진입점
└─ Serializer                                        # 요청값 검증과 응답 데이터 변환
   └─ Service                                        # 업무 규칙·트랜잭션·상태 전환
      └─ Repository                                  # Django ORM 조회·저장
         └─ Model                                    # DB 스키마와 최소 데이터 제약
```

```text
금지 기준
├─ View에서 복잡한 ORM Query 직접 작성 금지
├─ Serializer에서 상태 전환·외부 연동 수행 금지
├─ Model.save()에서 AI 서비스 호출 금지
├─ Repository에서 업무 상태·권한 판단 금지
└─ Web·Mobile이 State Machine을 자체 계산하는 것 금지
```

## 13.2 상세 구조

```text
backend/                                             # Django·DRF 기반 업무 API 서버
│
├─ config/                                          # Django 프로젝트 전역 설정
│  ├─ __init__.py                                   # config Python 패키지 선언
│  ├─ settings/                                     # 실행 환경별 Django 설정
│  │  ├─ __init__.py                                # settings Python 패키지 선언
│  │  ├─ base.py                                    # 앱·미들웨어·DB·REST Framework 공통 설정
│  │  ├─ local.py                                   # 로컬 개발 환경 설정
│  │  ├─ test.py                                    # 자동 테스트 환경 설정
│  │  └─ production.py                              # Kubernetes Demo 배포 환경 설정
│  ├─ urls.py                                       # Health·Admin·API 최상위 URL 연결
│  ├─ api_urls.py                                   # `/api/v1` 하위 도메인 API 통합 URL
│  ├─ asgi.py                                       # ASGI 서버 실행 진입점
│  └─ wsgi.py                                       # Gunicorn WSGI 실행 진입점
│
├─ apps/                                            # 업무 도메인별 Django Application
│  │
│  ├─ accounts/                                     # 사용자·인증·역할·프로필 관리
│  │  ├─ __init__.py                                # Accounts App Python 패키지 선언
│  │  ├─ api/                                       # 로그인·현재 사용자 API 계층
│  │  │  ├─ __init__.py                            # Accounts API 패키지 선언
│  │  │  ├─ urls.py                                # 인증 API URL
│  │  │  ├─ views.py                               # 로그인·토큰·현재 사용자 조회 Controller
│  │  │  └─ serializers.py                         # 로그인 요청·사용자 응답 Serializer
│  │  ├─ models/                                    # 사용자 관련 DB Model
│  │  │  ├─ __init__.py                            # Accounts Model 공개 목록
│  │  │  ├─ user.py                                # 가상 사용자·역할·활성 상태 Model
│  │  │  └─ customer_profile.py                    # 고객 합성 프로필 Model
│  │  ├─ services/                                  # 인증·사용자 업무 로직
│  │  │  ├─ __init__.py                            # Accounts Service 패키지 선언
│  │  │  ├─ authentication_service.py              # JWT 발급·로그인 검증 Service
│  │  │  └─ account_service.py                     # 사용자 조회·상태 변경 Service
│  │  ├─ repositories/                              # 사용자 DB 접근 계층
│  │  │  ├─ __init__.py                            # Accounts Repository 패키지 선언
│  │  │  └─ account_repository.py                  # 사용자·역할 ORM 조회 Repository
│  │  ├─ permissions.py                            # 역할 기반 DRF Permission
│  │  ├─ admin.py                                  # Django Admin 사용자 설정
│  │  ├─ apps.py                                   # Accounts App 설정
│  │  └─ migrations/                               # 사용자 테이블 Migration
│  │     └─ __init__.py                            # Accounts Migration 패키지 선언
│  │
│  ├─ products/                                     # 지원 제품·모델·문서 계보 관리
│  │  ├─ __init__.py                                # Products App Python 패키지 선언
│  │  ├─ api/                                       # 제품 조회·등록 API 계층
│  │  │  ├─ __init__.py                            # Products API 패키지 선언
│  │  │  ├─ urls.py                                # 지원 제품 조회 API URL
│  │  │  ├─ views.py                               # 제품 목록·상세 Controller
│  │  │  └─ serializers.py                         # 제품 요청·응답 Serializer
│  │  ├─ models/                                    # 제품 관련 DB Model
│  │  │  ├─ __init__.py                            # Products Model 공개 목록
│  │  │  ├─ product_model_registry.py              # 판매 코드·모델·세대·지원 범위 Model
│  │  │  └─ product.py                             # 고객에게 등록되는 실제 제품 Model
│  │  ├─ services/                                  # 제품 업무 규칙
│  │  │  ├─ __init__.py                            # Products Service 패키지 선언
│  │  │  ├─ product_service.py                     # 제품 조회·등록·수정 Service
│  │  │  └─ product_validation_service.py          # MVP·세대·제외 모델 검증 Service
│  │  ├─ repositories/                              # 제품 DB 접근 계층
│  │  │  ├─ __init__.py                            # Products Repository 패키지 선언
│  │  │  ├─ product_repository.py                  # 제품 ORM 접근 Repository
│  │  │  └─ model_registry_repository.py           # 제품 모델 레지스트리 조회 Repository
│  │  ├─ admin.py                                  # Django Admin 제품 설정
│  │  ├─ apps.py                                   # Products App 설정
│  │  └─ migrations/                               # 제품 테이블 Migration
│  │     └─ __init__.py                            # Products Migration 패키지 선언
│  │
│  ├─ subscriptions/                                # 고객과 구독 제품 연결 관리
│  │  ├─ __init__.py                                # Subscriptions App Python 패키지 선언
│  │  ├─ api/                                       # 구독 조회·등록·수정 API 계층
│  │  │  ├─ __init__.py                            # Subscriptions API 패키지 선언
│  │  │  ├─ urls.py                                # 구독 조회·등록·수정 API URL
│  │  │  ├─ views.py                               # 구독 Controller
│  │  │  └─ serializers.py                         # 구독 요청·응답 Serializer
│  │  ├─ models/                                    # 구독 관련 DB Model
│  │  │  ├─ __init__.py                            # Subscriptions Model 공개 목록
│  │  │  └─ subscription.py                        # 고객·제품·관리 유형·사용 시작일 Model
│  │  ├─ services/                                  # 구독 업무 규칙
│  │  │  ├─ __init__.py                            # Subscriptions Service 패키지 선언
│  │  │  └─ subscription_service.py                # 본인 구독 조회·수정 Service
│  │  ├─ repositories/                              # 구독 DB 접근 계층
│  │  │  ├─ __init__.py                            # Subscriptions Repository 패키지 선언
│  │  │  └─ subscription_repository.py             # 구독 ORM 접근 Repository
│  │  ├─ permissions.py                            # 고객 본인 구독 접근 Permission
│  │  ├─ admin.py                                  # Django Admin 구독 설정
│  │  ├─ apps.py                                   # Subscriptions App 설정
│  │  └─ migrations/                               # 구독 테이블 Migration
│  │     └─ __init__.py                            # Subscriptions Migration 패키지 선언
│  │
│  ├─ care/                                         # 케어 이력·관리 일정 관리
│  │  ├─ __init__.py                                # Care App Python 패키지 선언
│  │  ├─ api/                                       # 케어 이력·일정 API 계층
│  │  │  ├─ __init__.py                            # Care API 패키지 선언
│  │  │  ├─ urls.py                                # 케어 이력·다음 일정 API URL
│  │  │  ├─ views.py                               # 케어 Controller
│  │  │  └─ serializers.py                         # 케어 요청·응답 Serializer
│  │  ├─ models/                                    # 케어 관련 DB Model
│  │  │  ├─ __init__.py                            # Care Model 공개 목록
│  │  │  ├─ care_history.py                        # 필터 교체·세척·방문 관리 이력 Model
│  │  │  └─ care_schedule.py                       # 다음 케어 예정일·확인 필요 상태 Model
│  │  ├─ services/                                  # 케어 업무 규칙
│  │  │  ├─ __init__.py                            # Care Service 패키지 선언
│  │  │  ├─ care_history_service.py                # 케어 이력 등록·조회 Service
│  │  │  └─ care_schedule_service.py               # 공식 기준 기반 일정 산정·갱신 Service
│  │  ├─ repositories/                              # 케어 DB 접근 계층
│  │  │  ├─ __init__.py                            # Care Repository 패키지 선언
│  │  │  ├─ care_history_repository.py             # 케어 이력 ORM 접근 Repository
│  │  │  └─ care_schedule_repository.py            # 케어 일정 ORM 접근 Repository
│  │  ├─ admin.py                                  # Django Admin 케어 설정
│  │  ├─ apps.py                                   # Care App 설정
│  │  └─ migrations/                               # 케어 테이블 Migration
│  │     └─ __init__.py                            # Care Migration 패키지 선언
│  │
│  ├─ questionnaires/                               # 사전 문진·추가 질문 답변 관리
│  │  ├─ __init__.py                                # Questionnaires App Python 패키지 선언
│  │  ├─ api/                                       # 문진 생성·임시 저장·제출 API 계층
│  │  │  ├─ __init__.py                            # Questionnaires API 패키지 선언
│  │  │  ├─ urls.py                                # 문진 생성·임시 저장·제출 API URL
│  │  │  ├─ views.py                               # 문진 Controller
│  │  │  └─ serializers.py                         # 문진 문항·답변 Serializer
│  │  ├─ models/                                    # 문진 관련 DB Model
│  │  │  ├─ __init__.py                            # Questionnaires Model 공개 목록
│  │  │  ├─ questionnaire_session.py               # CARE_PRECHECK·ADHOC 문진 세션 Model
│  │  │  └─ questionnaire_answer.py                # 문항별 누적 답변 Model
│  │  ├─ services/                                  # 문진 업무 규칙
│  │  │  ├─ __init__.py                            # Questionnaires Service 패키지 선언
│  │  │  ├─ questionnaire_service.py               # 문진 생성·임시 저장·제출 Service
│  │  │  └─ inquiry_link_service.py                # 사전 문진을 새 문의에 연결하는 Service
│  │  ├─ repositories/                              # 문진 DB 접근 계층
│  │  │  ├─ __init__.py                            # Questionnaires Repository 패키지 선언
│  │  │  └─ questionnaire_repository.py            # 문진 세션·답변 ORM 접근 Repository
│  │  ├─ admin.py                                  # Django Admin 문진 설정
│  │  ├─ apps.py                                   # Questionnaires App 설정
│  │  └─ migrations/                               # 문진 테이블 Migration
│  │     └─ __init__.py                            # Questionnaires Migration 패키지 선언
│  │
│  ├─ inquiries/                                    # 고객 문의와 전체 처리 흐름의 중심
│  │  ├─ __init__.py                                # Inquiries App Python 패키지 선언
│  │  ├─ api/                                       # 문의 생성·조회·답변·전이 API 계층
│  │  │  ├─ __init__.py                            # Inquiries API 패키지 선언
│  │  │  ├─ urls.py                                # 문의 생성·조회·답변·전이 API URL
│  │  │  ├─ views.py                               # 고객·상담사 문의 Controller
│  │  │  └─ serializers/                           # 문의 요청·응답별 Serializer
│  │  │     ├─ __init__.py                         # 문의 Serializer 공개 목록
│  │  │     ├─ create_inquiry.py                   # START_INQUIRY 요청 Serializer
│  │  │     ├─ symptom_submission.py               # 자연어·대표 증상 제출 Serializer
│  │  │     ├─ action_result.py                    # 자가조치 결과 Serializer
│  │  │     ├─ resolution_feedback.py              # 고객 해결 여부 Serializer
│  │  │     └─ inquiry_response.py                 # 문의 상세·allowed_actions 응답 Serializer
│  │  ├─ models/                                    # 문의 관련 DB Model
│  │  │  ├─ __init__.py                            # Inquiries Model 공개 목록
│  │  │  ├─ inquiry.py                             # 문의 ID·현재 상태·담당 주체 Model
│  │  │  ├─ symptom_entry.py                       # 최초 자연어·대표 증상·구조화 결과 Model
│  │  │  ├─ followup_answer.py                     # AI 추가 질문 누적 답변 Model
│  │  │  └─ customer_action_result.py              # 자가조치 수행 여부·증상 변화 Model
│  │  ├─ services/                                  # 문의 업무 규칙·상태 전환
│  │  │  ├─ __init__.py                            # Inquiries Service 패키지 선언
│  │  │  ├─ inquiry_service.py                     # 문의 생성·조회·내용 누적 Service
│  │  │  ├─ inquiry_transition_service.py          # State Machine 실행과 상태 저장 Service
│  │  │  ├─ resolution_service.py                  # 해결·미해결·재개 처리 Service
│  │  │  └─ inquiry_ai_service.py                  # 문의 분석 AI 요청 조율 Service
│  │  ├─ repositories/                              # 문의 DB 접근 계층
│  │  │  ├─ __init__.py                            # Inquiries Repository 패키지 선언
│  │  │  ├─ inquiry_repository.py                  # 문의 조회·잠금·저장 Repository
│  │  │  └─ inquiry_history_repository.py          # 문의 관련 이력 조회 Repository
│  │  ├─ permissions.py                            # 고객 본인·담당 상담사 접근 Permission
│  │  ├─ admin.py                                  # Django Admin 문의 설정
│  │  ├─ apps.py                                   # Inquiries App 설정
│  │  └─ migrations/                               # 문의 테이블 Migration
│  │     └─ __init__.py                            # Inquiries Migration 패키지 선언
│  │
│  ├─ consultations/                                # 상담사 업무·상담 결과 관리
│  │  ├─ __init__.py                                # Consultations App Python 패키지 선언
│  │  ├─ api/                                       # 상담 대기·상세·완료 API 계층
│  │  │  ├─ __init__.py                            # Consultations API 패키지 선언
│  │  │  ├─ urls.py                                # 상담 대기·상세·완료 API URL
│  │  │  ├─ views.py                               # 상담 Controller
│  │  │  └─ serializers.py                         # 상담 기록·완료 요청 Serializer
│  │  ├─ models/                                    # 상담 관련 DB Model
│  │  │  ├─ __init__.py                            # Consultations Model 공개 목록
│  │  │  ├─ consultation.py                        # 상담 담당자·시작·완료 정보 Model
│  │  │  └─ consultation_summary.py                # AI 초안·상담사 확정 요약 Model
│  │  ├─ services/                                  # 상담 업무 규칙
│  │  │  ├─ __init__.py                            # Consultations Service 패키지 선언
│  │  │  ├─ consultation_service.py                # 상담 시작·저장·완료 Service
│  │  │  └─ consultation_summary_service.py        # AI 초안 생성·수정·확정 Service
│  │  ├─ repositories/                              # 상담 DB 접근 계층
│  │  │  ├─ __init__.py                            # Consultations Repository 패키지 선언
│  │  │  └─ consultation_repository.py             # 상담·요약 ORM 접근 Repository
│  │  ├─ permissions.py                            # 상담사 역할·담당자 Permission
│  │  ├─ admin.py                                  # Django Admin 상담 설정
│  │  ├─ apps.py                                   # Consultations App 설정
│  │  └─ migrations/                               # 상담 테이블 Migration
│  │     └─ __init__.py                            # Consultations Migration 패키지 선언
│  │
│  ├─ visits/                                       # 방문 배정·일정·결과 관리
│  │  ├─ __init__.py                                # Visits App Python 패키지 선언
│  │  ├─ api/                                       # 방문 전환·일정·결과 API 계층
│  │  │  ├─ __init__.py                            # Visits API 패키지 선언
│  │  │  ├─ urls.py                                # 방문 전환·일정·결과 API URL
│  │  │  ├─ views.py                               # 방문 Controller
│  │  │  └─ serializers.py                         # 일정·방문 결과 Serializer
│  │  ├─ models/                                    # 방문 관련 DB Model
│  │  │  ├─ __init__.py                            # Visits Model 공개 목록
│  │  │  ├─ visit.py                               # 담당 기사·희망일·확정일·상태 Model
│  │  │  ├─ technician_report.py                   # AI 초안·기사용 사전 리포트 Model
│  │  │  └─ visit_result.py                        # 원인·조치·교체·처리 결과 Model
│  │  ├─ services/                                  # 방문 업무 규칙
│  │  │  ├─ __init__.py                            # Visits Service 패키지 선언
│  │  │  ├─ visit_service.py                       # 방문 생성·배정·일정 수정 Service
│  │  │  ├─ visit_transition_service.py            # 방문 상태 전이 Service
│  │  │  ├─ technician_report_service.py           # 기사 사전 리포트 생성 Service
│  │  │  └─ visit_completion_service.py            # 방문 완료·케어 이력 반영 Service
│  │  ├─ repositories/                              # 방문 DB 접근 계층
│  │  │  ├─ __init__.py                            # Visits Repository 패키지 선언
│  │  │  └─ visit_repository.py                    # 방문·결과 ORM 접근 Repository
│  │  ├─ permissions.py                            # 배정 기사 접근 Permission
│  │  ├─ admin.py                                  # Django Admin 방문 설정
│  │  ├─ apps.py                                   # Visits App 설정
│  │  └─ migrations/                               # 방문 테이블 Migration
│  │     └─ __init__.py                            # Visits Migration 패키지 선언
│  │
│  ├─ workflow/                                     # 상태·이벤트·가드·허용 행동 엔진
│  │  ├─ __init__.py                                # Workflow App Python 패키지 선언
│  │  ├─ domain/                                    # 상태 전이 도메인 객체
│  │  │  ├─ __init__.py                            # Workflow 도메인 객체 패키지 선언
│  │  │  ├─ state.py                               # 문의·방문 상태 값 객체
│  │  │  ├─ event.py                               # State Machine 이벤트 값 객체
│  │  │  ├─ transition.py                          # 전이 결과 데이터 구조
│  │  │  └─ workflow_snapshot.py                   # 현재 상태·담당자·버전 Snapshot
│  │  ├─ engine/                                    # State Machine 계산 엔진
│  │  │  ├─ __init__.py                            # Workflow Engine 패키지 선언
│  │  │  ├─ state_machine.py                       # 상태+이벤트 전이 계산 엔진
│  │  │  ├─ guard_evaluator.py                     # 역할·담당자·필수값 Guard 검사
│  │  │  └─ allowed_action_resolver.py             # 화면 허용 행동 계산
│  │  ├─ contracts/                                 # 최상위 상태 계약 연결
│  │  │  ├─ __init__.py                            # Workflow 계약 로더 패키지 선언
│  │  │  ├─ state_machine_loader.py                # `contracts/state-machine` YAML 로더
│  │  │  └─ contract_validator.py                  # 상태·이벤트·가드 참조 검증
│  │  ├─ models/                                    # 상태 변경·멱등성 DB Model
│  │  │  ├─ __init__.py                            # Workflow Model 공개 목록
│  │  │  ├─ transition_history.py                  # 이전·다음 상태·변경자·시각 Model
│  │  │  └─ idempotency_record.py                  # 중복 쓰기 요청 처리 기록 Model
│  │  ├─ services/                                  # 멱등성·감사 이력 업무 규칙
│  │  │  ├─ __init__.py                            # Workflow Service 패키지 선언
│  │  │  ├─ idempotency_service.py                 # Idempotency-Key 검사·결과 재사용 Service
│  │  │  └─ transition_history_service.py          # 상태 변경 감사 이력 Service
│  │  ├─ repositories/                              # 상태 변경·멱등성 DB 접근
│  │  │  ├─ __init__.py                            # Workflow Repository 패키지 선언
│  │  │  └─ workflow_repository.py                 # 전이 이력·멱등성 ORM 접근 Repository
│  │  ├─ apps.py                                   # Workflow App 설정
│  │  └─ migrations/                               # Workflow 테이블 Migration
│  │     └─ __init__.py                            # Workflow Migration 패키지 선언
│  │
│  ├─ evidence/                                     # 공식 근거·EvidenceCardDTO 조립
│  │  ├─ __init__.py                                # Evidence App Python 패키지 선언
│  │  ├─ api/                                       # 문의별 근거 조회 API 계층
│  │  │  ├─ __init__.py                            # Evidence API 패키지 선언
│  │  │  ├─ urls.py                                # 문의별 근거 조회 API URL
│  │  │  ├─ views.py                               # 근거 조회 Controller
│  │  │  └─ serializers.py                         # EvidenceCard 응답 Serializer
│  │  ├─ models/                                    # 근거·문서·청크 DB Model
│  │  │  ├─ __init__.py                            # Evidence Model 공개 목록
│  │  │  ├─ source_document.py                     # 문서명·버전·제공기관·공식 URL Model
│  │  │  ├─ document_chunk.py                      # 청크 ID·문서·페이지 참조 Model
│  │  │  └─ evidence_registry.py                   # 검증 상태·허용 범위·안전조치 Model
│  │  ├─ services/                                  # 근거 검증과 화면 DTO 조립
│  │  │  ├─ __init__.py                            # Evidence Service 패키지 선언
│  │  │  ├─ evidence_card_service.py               # AI 참조와 근거 레지스트리 결합 Service
│  │  │  ├─ evidence_validation_service.py         # 모델·세대·사용 정책 검증 Service
│  │  │  └─ source_link_service.py                 # 공식 랜딩·다운로드 URL 제공 Service
│  │  ├─ repositories/                              # 근거·문서 DB 접근 계층
│  │  │  ├─ __init__.py                            # Evidence Repository 패키지 선언
│  │  │  ├─ evidence_repository.py                 # 근거 레지스트리 ORM 접근 Repository
│  │  │  └─ document_repository.py                 # 문서·청크·페이지 조회 Repository
│  │  ├─ admin.py                                  # Django Admin 근거 설정
│  │  ├─ apps.py                                   # Evidence App 설정
│  │  └─ migrations/                               # 근거 테이블 Migration
│  │     └─ __init__.py                            # Evidence Migration 패키지 선언
│  │
│  ├─ audit/                                        # 변경·AI·오류 추적 기록
│  │  ├─ __init__.py                                # Audit App Python 패키지 선언
│  │  ├─ models/                                    # 감사·AI 실행 로그 Model
│  │  │  ├─ __init__.py                            # Audit Model 공개 목록
│  │  │  ├─ audit_event.py                         # 주요 생성·수정·상태 변경 이력 Model
│  │  │  └─ ai_execution_log.py                    # AI 단계·모델·프롬프트·처리시간 Model
│  │  ├─ services/                                  # 공통 감사 기록 업무 규칙
│  │  │  ├─ __init__.py                            # Audit Service 패키지 선언
│  │  │  └─ audit_service.py                       # 공통 감사 이벤트 기록 Service
│  │  ├─ repositories/                              # 감사 로그 DB 접근 계층
│  │  │  ├─ __init__.py                            # Audit Repository 패키지 선언
│  │  │  └─ audit_repository.py                    # 감사 로그 ORM 저장·조회 Repository
│  │  ├─ apps.py                                   # Audit App 설정
│  │  └─ migrations/                               # 감사 로그 테이블 Migration
│  │     └─ __init__.py                            # Audit Migration 패키지 선언
│  │
│  └─ operations/                                   # 운영 대시보드·예외 조회 P1
│     ├─ __init__.py                                # Operations App Python 패키지 선언
│     ├─ api/                                       # 운영 지표·예외 API 계층
│     │  ├─ __init__.py                            # Operations API 패키지 선언
│     │  ├─ urls.py                                # 운영 지표·예외 API URL
│     │  ├─ views.py                               # 운영 대시보드 Controller
│     │  └─ serializers.py                         # 운영 집계 응답 Serializer
│     ├─ services/                                  # 운영 집계 업무 규칙
│     │  ├─ __init__.py                            # Operations Service 패키지 선언
│     │  └─ operations_service.py                  # 문의·상담·방문 집계 Service
│     ├─ repositories/                              # 통계·예외 DB 조회 계층
│     │  ├─ __init__.py                            # Operations Repository 패키지 선언
│     │  └─ operations_repository.py               # 통계·예외 ORM Query Repository
│     ├─ permissions.py                            # 운영 담당자 역할 Permission
│     ├─ apps.py                                   # Operations App 설정
│     └─ migrations/                               # 운영 P1 테이블 Migration
│        └─ __init__.py                            # Operations Migration 패키지 선언
│
├─ common/                                          # 백엔드 전 영역 공통 코드
│  ├─ __init__.py                                   # Backend common Python 패키지 선언
│  ├─ api/                                          # 공통 API 응답과 페이지네이션
│  │  ├─ __init__.py                               # 공통 API 패키지 선언
│  │  ├─ response.py                               # success·data·error 공통 Wrapper
│  │  ├─ pagination.py                             # page·size·total 페이지네이션
│  │  └─ metadata.py                               # correlation_id 응답 Metadata
│  ├─ exceptions/                                   # 공통 예외·업무 오류 처리
│  │  ├─ __init__.py                               # 공통 예외 패키지 선언
│  │  ├─ base.py                                   # Backend 기본 예외
│  │  ├─ business.py                               # 업무 규칙 예외
│  │  ├─ error_codes.py                            # contracts 오류 코드 로더
│  │  └─ handler.py                                # DRF 전역 예외 응답 변환
│  ├─ middleware/                                   # 모든 요청에 적용되는 처리
│  │  ├─ __init__.py                               # 공통 Middleware 패키지 선언
│  │  ├─ correlation_id.py                         # X-Correlation-ID 생성·전파
│  │  ├─ request_logging.py                        # 요청·응답 구조화 로그
│  │  └─ request_context.py                        # 사용자·역할·추적 Context
│  ├─ authentication/                               # JWT 공통 인증 처리
│  │  ├─ __init__.py                               # JWT 공통 인증 패키지 선언
│  │  ├─ jwt_authentication.py                     # Bearer Token 검증
│  │  └─ claims.py                                 # 사용자 ID·역할 Claim 파싱
│  ├─ models/                                       # 공통 Django Model 기반 클래스
│  │  ├─ __init__.py                               # 공통 Model 패키지 선언
│  │  ├─ base.py                                   # created_at·updated_at 기반 Model
│  │  ├─ soft_delete.py                            # deleted_at 논리 삭제 기반 Model
│  │  └─ versioned.py                              # state_version 낙관적 잠금 기반 Model
│  ├─ contracts/                                    # 최상위 contracts 접근 보조 코드
│  │  ├─ __init__.py                               # 계약 접근 패키지 선언
│  │  ├─ loader.py                                 # YAML·JSON Schema 로더
│  │  └─ paths.py                                  # 계약 파일 경로 계산
│  ├─ logging/                                      # 구조화 JSON 로그 설정
│  │  ├─ __init__.py                               # 구조화 로그 패키지 선언
│  │  ├─ filters.py                                # 추적·역할·문의 ID 로그 필터
│  │  └─ formatter.py                              # JSON 로그 Formatter
│  ├─ validators/                                   # 공통 입력값 검증
│  │  ├─ __init__.py                               # 공통 Validator 패키지 선언
│  │  ├─ identifiers.py                            # DEMO-*·SYN-* 식별자 검증
│  │  └─ datetime.py                               # ISO 8601 날짜·시간 검증
│  └─ utils/                                        # 특정 도메인에 속하지 않는 유틸리티
│     ├─ __init__.py                               # 공통 Utility 패키지 선언
│     ├─ enum.py                                   # 공통 Enum 변환
│     └─ masking.py                                # 로그·응답 민감정보 마스킹
│
├─ integrations/                                    # 외부 서비스 연결 Adapter
│  ├─ __init__.py                                   # Integrations Python 패키지 선언
│  ├─ ai/                                           # 독립 AI 서비스 HTTP 연동
│  │  ├─ __init__.py                               # AI 연동 패키지 선언
│  │  ├─ client.py                                 # AI API HTTP Client
│  │  ├─ request_mapper.py                         # Backend Model→AI 요청 변환
│  │  ├─ response_mapper.py                        # AI 응답→Backend 결과 변환
│  │  ├─ schema_validator.py                       # `contracts/ai` Schema 검증
│  │  ├─ retry_policy.py                           # AI 타임아웃·재시도 정책
│  │  └─ exceptions.py                             # AI 연동 오류
│  └─ object_storage/                               # S3 등 객체 저장소 연동
│     ├─ __init__.py                               # 객체 저장소 연동 패키지 선언
│     ├─ client.py                                 # 객체 저장소 공통 Client
│     └─ exceptions.py                             # 객체 저장소 연동 오류
│
├─ tests/                                           # Backend 내부 자동 테스트
│  ├─ __init__.py                                   # Backend 테스트 Python 패키지 선언
│  ├─ unit/                                         # Service·Repository·Engine 단위 테스트
│  │  ├─ accounts/                                  # 사용자·인증 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ products/                                  # 제품 검증 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ care/                                      # 케어 일정·이력 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ questionnaires/                            # 문진 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ inquiries/                                 # 문의 생성·누적·해결 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ consultations/                             # 상담 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ visits/                                    # 방문 Service 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  ├─ workflow/                                  # State Machine·Guard·멱등성 단위 테스트
│  │  │  └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  │  └─ evidence/                                  # 근거 검증·EvidenceCard 조립 단위 테스트
│  │     └─ .gitkeep                               # 빈 디렉토리를 Git에 유지
│  ├─ api/                                          # DRF Endpoint 요청·응답 테스트
│  │  └─ .gitkeep                                   # 빈 디렉토리를 Git에 유지
│  ├─ integration/                                  # PostgreSQL·AI Adapter 통합 테스트
│  │  └─ .gitkeep                                   # 빈 디렉토리를 Git에 유지
│  ├─ permissions/                                  # 고객·상담사·기사·운영 권한 테스트
│  │  └─ .gitkeep                                   # 빈 디렉토리를 Git에 유지
│  ├─ migrations/                                   # Migration 적용·누락·충돌 테스트
│  │  └─ .gitkeep                                   # 빈 디렉토리를 Git에 유지
│  ├─ factories/                                    # 테스트 Model Factory
│  │  └─ .gitkeep                                   # 빈 디렉토리를 Git에 유지
│  ├─ fixtures/                                     # 소규모 Backend 테스트 데이터
│  │  └─ .gitkeep                                   # 빈 디렉토리를 Git에 유지
│  └─ conftest.py                                   # Pytest 공통 Fixture
│
├─ requirements/                                    # 실행 환경별 Python 의존성
│  ├─ base.txt                                      # Django·DRF·공통 운영 의존성
│  ├─ local.txt                                     # 개발·Formatter·테스트 의존성
│  └─ production.txt                                # Gunicorn·운영 환경 의존성
│
├─ manage.py                                        # Django 명령 실행 진입점
├─ pyproject.toml                                   # Formatter·Pytest·Python 도구 설정
├─ .env.example                                     # DB·JWT·AI URL 환경변수 이름 예시
├─ .dockerignore                                    # 이미지에서 제외할 캐시·비밀값
├─ Dockerfile                                       # Django·Gunicorn 컨테이너 이미지
└─ README.md                                        # 설치·Migration·테스트·API 실행 안내
```

## 13.3 도메인별 책임

| Django App | 핵심 책임 |
|---|---|
| `accounts` | 사용자 역할·가상 로그인·JWT 인증·접근 권한 |
| `products` | 제품 모델·세대·MVP·확장·제외 범위 검증 |
| `subscriptions` | 고객과 구독 제품·관리 유형 연결 |
| `care` | 필터·카트리지·방문 관리 이력과 다음 케어 일정 |
| `questionnaires` | 사전 문진·추가 답변·문의 연결 |
| `inquiries` | 문의 생성·증상·자가조치·후속 해결 여부 |
| `consultations` | 상담 시작·기록·요약·방문 필요 판단 |
| `visits` | 기사 배정·일정·사전 리포트·방문 결과 |
| `workflow` | 상태·이벤트·가드·allowed_actions·멱등성 |
| `evidence` | 공식 근거 검증과 화면용 EvidenceCard 조립 |
| `audit` | 사용자 행위·상태 변경·AI 실행 추적 |
| `operations` | 운영 대시보드·지연·예외 조회 P1 |

## 13.4 주요 요청 처리 흐름

### 일반 저장 API

```text
DRF View
→ Serializer 입력 검증
→ Service 업무 규칙·transaction.atomic
→ Repository ORM 조회·저장
→ 응답 Serializer
→ 공통 ApiResponse
```

### 상태 전환 API

```text
StateTransition View
→ 이벤트·state_version 검증
→ Idempotency-Key 검사
→ select_for_update로 문의 조회
→ Workflow Engine 전이·Guard 검사
→ 문의 상태·담당 주체 저장
→ TransitionHistory 저장
→ allowed_actions 계산
→ StateTransitionResult 반환
```

### AI 분석 요청

```text
Inquiry Service
→ 문의·제품·문진·관리 이력 조회
→ integrations/ai/request_mapper.py
→ AI Service 호출
→ contracts/ai 응답 Schema 검증
→ EvidenceReference 추출
→ EvidenceCard Service에서 공식 근거 결합
→ AI 결과·근거·추적 로그 저장
→ 화면 응답 조립
```

AI 서비스는 문의 상태를 직접 변경하지 않는다. AI 결과를 받은 백엔드가 State Machine Guard를 검사한 뒤 자동 이벤트를 실행한다.

## 13.5 의존 방향

```text
api
 ↓
services
 ↓
repositories
 ↓
models
```

```text
추가 허용 의존
├─ services → workflow engine
├─ services → integrations
├─ services → common
├─ repositories → models
└─ integrations → contracts
```

```text
금지 의존
├─ models → services
├─ repositories → api
├─ integrations → DRF View
├─ common → 특정 업무 App
└─ AI Service → PostgreSQL 직접 수정
```

## 13.6 네이밍 기준

| 대상 | 기준 | 예시 |
|---|---|---|
| Python 파일 | `snake_case` | `inquiry_service.py` |
| Python 패키지·디렉토리 | `snake_case` 또는 단일 소문자 | `questionnaires/` |
| Python 클래스 | `PascalCase` | `InquiryTransitionService` |
| 함수·변수 | `snake_case` | `transition_inquiry()` |
| 상수·Enum 값 | `UPPER_SNAKE_CASE` | `CONSULTATION_REQUIRED` |
| 테스트 파일 | `test_*.py` | `test_inquiry_transition.py` |

## 13.7 초기 생성 우선순위

```text
P0 초기 생성
├─ accounts/
├─ products/
├─ subscriptions/
├─ care/
├─ questionnaires/
├─ inquiries/
├─ consultations/
├─ visits/
├─ workflow/
├─ evidence/
└─ audit/

P1 구현 시 활성화
└─ operations/
```

빈 `api/`, `services/`, `repositories/`를 모든 App에 기계적으로 늘리기보다 실제 기능이 생기는 시점에 파일을 추가하되, 계층별 책임과 의존 방향은 위 기준을 유지한다.

---

# 14. 최종 전체 구조 요약

```text
SKN29-FINAL-4TEAM/                                      # 정수기 고객 케어·A/S 업무 지원 Monorepo
├─ web/                                                 # React·TypeScript 상담사·운영 웹
├─ mobile/                                              # Kotlin·Jetpack Compose 고객·기사 앱
├─ backend/                                             # Django·DRF API·State Machine·Evidence 조립
├─ ai/                                                  # 구조화·안전·RAG·생성·검증
├─ contracts/                                           # API·AI·상태·코드·오류 계약
├─ data/                                                # 원본·전처리·구조화·합성 데이터
├─ infra/                                               # Docker·Kubernetes·운영 설정
├─ scripts/                                             # 저장소 전체 자동화
├─ tests/                                               # 계약·통합·E2E·안전·성능 검증
├─ docs/                                                # 기획·설계·테스트·배포·발표·제출 문서
├─ .github/                                             # 협업 양식과 GitHub Actions CI/CD
├─ .editorconfig                                        # 편집기 공통 인코딩·들여쓰기·줄바꿈 설정
├─ .gitattributes                                       # 운영체제별 Git 줄바꿈·텍스트 처리 기준
├─ .gitignore                                           # 비밀값·빌드 결과·원본 데이터 제외 규칙
├─ .env.example                                         # 필요한 환경변수 이름과 예시 값 안내
├─ docker-compose.yml                                   # 로컬 전체 서비스 통합 실행 진입 설정
├─ CONTRIBUTING.md                                      # 브랜치·Issue·커밋·PR·리뷰 규칙 안내
└─ README.md                                            # 저장소 실행·구조·협업·배포 개요
```

## 14.1 영역 간 의존·책임 원칙

```text
Web·Mobile
└─ Backend `/api/v1`만 호출

Backend
├─ 인증·권한·State Machine·업무 저장의 최종 책임
├─ AI 서비스 호출과 결과 검증·저장
└─ 공식 근거를 결합한 EvidenceCard 최종 조립

AI
├─ 증상 구조화·안전 판정·검색·생성·출력 검증
└─ 업무 상태와 PostgreSQL을 직접 변경하지 않음

Contracts
└─ 서비스 간 요청·응답·상태·코드 형식의 단일 기준

Data
└─ 공식 원본과 검증된 전처리·구조화·합성 데이터의 계보 관리

Infra·CI/CD
└─ 빌드·검증·배포·Smoke Test·롤백 자동화
```

## 14.2 네이밍 최종 기준

| 영역 | 기준 |
|---|---|
| Web React 컴포넌트·페이지 | `PascalCase.tsx` |
| Web Hook·일반 TypeScript | `camelCase.ts` |
| Web 디렉토리 | `kebab-case` |
| Kotlin 클래스·Compose 파일 | `PascalCase.kt` |
| Kotlin 패키지 | 영문 소문자 |
| Python 파일·패키지 | `snake_case` |
| Kubernetes·Workflow 파일 | `kebab-case.yaml`, `kebab-case.yml` |
| 데이터 파일 | `snake_case` |
| JSON 필드 | `snake_case` |
| 상수·Enum 값 | `UPPER_SNAKE_CASE` |

## 14.3 상세 설계 완료 현황

다음 영역의 세부 디렉토리 구조와 책임 경계를 모두 설계했다.

```text
완료
├─ web/
├─ mobile/
├─ backend/
├─ ai/
├─ contracts/
├─ data/
├─ infra/
├─ .github/workflows/
├─ scripts/
├─ tests/
└─ docs/
```

실제 구현 과정에서는 사용하지 않는 빈 하위 디렉토리를 한꺼번에 생성하지 않고, 해당 기능을 개발하는 시점에 필요한 파일과 디렉토리만 추가한다.

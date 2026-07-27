# 한예나 3주차 업무 지침서

> 프로젝트: 정수기 구독 고객 케어 및 A/S 업무 지원 시스템
> 
> 
> 대상 기간: 2026년 7월 27일 ~ 7월 31일
> 
> 필수 산출물 목표 완료일: **2026년 7월 29일**
> 
> 7월 30일~31일 운영 원칙: 신규 화면을 무리하게 늘리기보다 **계약 반영, 화면 간 정합성 검토, API·Mock 교체 확인, 오류 수정과 다음 주 진입 준비**를 우선한다.
> 

---

# 1. 담당자 기본 정보

| 항목 | 내용 |
| --- | --- |
| 담당자 | 한예나 |
| 담당 역할 | 웹 프론트엔드 개발 담당 |
| 주관할 영역 | `web/**` 전체 |
| 주요 협업 영역 | `web/src/common/api/**`, `web/src/features/*/api/**`, `web/src/features/workflow-action/**`는 최지용과 협업, `web/src/features/evidence-viewer/**`·`web/src/entities/evidence/**`는 이동윤과 협업, `web/tests/**`는 김은진과 협업 |
| 담당 사용자 | 상담사·운영 담당자. 단, 3주차에는 상담사 P0 흐름을 우선한다. |
| 주요 협업 대상 | 최지용, 윤승혁, 이동윤, 김은진, 양정현 |
| 3주차 핵심 책임 | React 웹 실행 기반, 상담사 문의 목록·상세 화면, 상담 기록 입력 구조, 상태·위험도·공식 근거 표시, Mock·API 필드 정리 |
| 핵심 산출물 | 실행 가능한 웹, `CONS-01`·`CONS-02` 최소 화면, `CONS-03` 입력 골격, 공통 상태·오류 UI, API·DB 필드 매핑, 테스트·기술 결정 기록 |

한예나는 상담사와 운영 담당자가 사용하는 PC 웹 애플리케이션을 주관한다. 3주차에는 운영 대시보드 전체를 만들거나 모든 후속 상담·방문 기능을 완성하는 것이 아니라, 상담사가 우선 문의를 찾고 한 문의의 고객·제품·증상·AI 요약·공식 근거를 확인한 뒤 현재 상태에서 허용된 행동을 선택할 수 있는 최소 흐름을 구현하는 데 집중한다.

웹은 문의 상태나 위험도를 화면에서 임의로 계산하지 않는다. 백엔드가 반환한 상태, 위험도, 현재 담당 주체, `allowed_actions`, `state_version`을 기준으로 표시하며, 상태 변경은 승인된 이벤트 API를 통해서만 요청한다. AI 상담 요약 초안과 상담사가 수정·확정한 내용을 구분하고, 공식 근거 카드는 백엔드가 공개를 허용한 필드만 표시한다.

---

# 2. 3주차 역할 목표

1. **7월 29일까지 실행 가능한 React·Vite·TypeScript 웹과 상담사 최소 흐름을 만든다.**
    
    역할별 Router·Layout, 상담사 문의 목록 `CONS-01`, 문의 상세 `CONS-02`, 상담 기록·행동 영역의 최소 구조를 팀 저장소에서 실행 가능한 상태로 만든다.
    
2. **백엔드·AI·State Machine 계약을 TypeScript 타입과 화면 상태로 표현한다.**
    
    목록·상세·공식 근거·상담 기록에 필요한 필드와 오류 응답을 Mock 또는 테스트 API로 검증하고, 상태·위험도·사용 안내·허용 행동을 공통 컴포넌트에 반영한다.
    
3. **7월 30일~31일에 실제 연동과 다음 주 기능 확장에 대비한다.**
    
    로딩·빈 상태·권한 없음·부분 실패·근거 없음·409 충돌을 확인하고, 화면–DB·API 필드 매핑과 미확정 항목을 문서화하여 `CONS-03` 및 상담 결과 저장 기능으로 확장할 수 있게 한다.
    

3주차 필수 범위는 상담사 웹의 목록·상세·최소 상담 입력 흐름이다. `ADMIN-01` 운영 대시보드의 차트·통계·관리 기능, 방문 일정 전체 구현, 디자인 시스템 고도화, 전체 E2E 통합은 필수 업무에서 제외한다.

---

# 3. 3주차 필수 업무

## 3.1 React 웹 실행 환경과 역할별 공통 구조 구성

### 작업 목적

상담사 화면을 안정적으로 확장할 수 있는 실행 기반을 만들고 Router·권한·레이아웃·오류 처리를 화면마다 중복 구현하지 않도록 한다. 개인 시안은 참고하되 팀 프로젝트 설정을 덮어쓰지 않는다.

### 작업 위치

```
web/
├─ package.json
├─ vite.config.ts
├─ tsconfig*.json
├─ .env.example
├─ src/main.tsx
├─ src/app/{App,config/env,providers/AppProviders}.tsx
├─ src/app/router/{AppRouter,routePaths}.tsx
├─ src/app/router/guards/{AuthGuard,RoleGuard}.tsx
├─ src/app/layouts/{RootLayout,ConsultantLayout,AdminLayout}.tsx
├─ src/pages/system/{ForbiddenPage,NotFoundPage,ErrorPage}.tsx
└─ README.md
```

### 세부 작업 지침

1. 합의된 Node.js·npm 환경에서 설치, 개발 서버, TypeScript 검사, Production Build를 확인한다.
2. 로그인·상담사·운영자·403·404 경로를 분리하고 경로 상수는 한 파일에서 관리한다.
3. `AuthGuard`와 `RoleGuard`로 인증과 역할 권한을 구분한다.
4. Access Token 만료로 401이 반환되면 Refresh Token으로 재발급을 한 번 시도하고, 재발급이 실패하면 로그인 화면으로 이동한다.
5. 로그아웃 시 서버의 로그아웃 API를 호출하고 클라이언트에 저장된 Access Token과 Refresh Token을 삭제한다.
6. `ConsultantLayout`에 Header·Side Navigation·Content 영역과 `CONS-01~03` 경로를 연결한다.
7. `AdminLayout`과 `ADMIN-01`은 Route·Menu Placeholder까지만 만든다.
8. `env.ts`에서 API Base URL과 Mock 사용 여부를 검증하고 비밀값을 하드코딩하지 않는다.
9. 개인 프로젝트의 `package.json`, Router, DOM 조작 코드는 복사하지 않고 필요한 UI만 React 컴포넌트로 다시 작성한다.
10. `web/README.md`에 설치·실행·빌드·테스트·환경변수·Mock 전환 방법을 기록한다.

### 완료 기준

- 개발 서버와 Production Build가 성공한다.
- 상담사 역할은 상담사 Layout에 진입하고 권한 없는 역할은 403으로 이동한다.
- 401·403·404·전역 오류가 구분된다.
- Access Token 만료 후 재발급 성공·실패 흐름을 확인할 수 있다.
- 환경변수와 Mock 전환 값이 컴포넌트에 흩어져 있지 않다.
- 다른 팀원이 README로 웹을 실행할 수 있다.

### 산출물

- 실행 가능한 `web/` 프로젝트
- 역할별 Router·Layout·Guard
- 인증 갱신·로그아웃 처리 구조
- 환경 설정·시스템 오류 페이지
- `web/README.md`와 실행 증빙

---

## 3.2 공통 API 계층과 상태·근거 UI 구성

### 작업 목적

목록·상세·상담 화면이 같은 응답·오류 모델과 상태 표시 컴포넌트를 사용하게 한다. 화면은 업무 코드를 임의로 해석하지 않고 `contracts/**`에서 확정된 표시명과 공개 필드만 사용한다.

### 작업 위치

```
web/src/common/api/{httpClient,apiResponse,apiError,pagination,requestContext}.ts
web/src/common/components/data-display/{DataTable,Pagination,StatusBadge,RiskBadge,PriorityBadge}.tsx
web/src/common/components/feedback/{LoadingState,EmptyState,ErrorState,ForbiddenState}.tsx
web/src/entities/{inquiry,workflow,evidence}/**
web/src/features/evidence-viewer/{components/EvidenceCard,model/evidenceMapper}.tsx
```

### 세부 작업 지침

1. Base URL, JSON 처리, 인증 Header, Access Token 재발급, Timeout, 공통 오류 변환을 `httpClient.ts`에 둔다.
2. `ApiResponse`, `ApiError`, 페이지네이션 타입은 `contracts/api/**`에 맞춘다.
3. 오류를 다음 기준으로 구분한다.
    - 400: 잘못된 요청
    - 401: 미인증·Token 만료 및 갱신 실패
    - 403: 역할상 허용되지 않은 기능
    - 404: 실제 리소스 없음 또는 다른 사용자의 리소스
    - 409: 현재 상태·`state_version` 충돌
    - 422: 입력값 검증 실패
    - 5xx·네트워크·응답 파싱 실패
4. `correlation_id`, `idempotency_key`, `state_version` 사용 위치를 공통 또는 기능 API에 명시한다.
5. API의 날짜·시간은 `+09:00`이 포함된 ISO 8601 값을 사용하며, 프론트에서는 한국 시간으로 다시 변환하지 않고 표시 형식만 변경한다.
6. API 조회·Route에는 공개 식별자를 사용하고 내부 정수 PK를 노출하지 않는다. 화면에는 `DEMO-INQ-002`와 같은 업무용 문의 번호를 별도로 표시한다.
7. 사용 안내 상태는 다음 값을 사용한다.
    - `NORMAL`
    - `PARTIAL_STOP`
    - `TOTAL_STOP`
    - `PENDING_CONSULTATION`
8. 상태·위험도·우선순위 Badge는 계약된 코드와 한글 표시명을 사용하며 알 수 없는 값은 미확인으로 표시한다.
9. 위험도는 색상뿐 아니라 문구·아이콘·접근성 설명으로 구분한다.
10. EvidenceCard는 문서명·리비전·페이지·요약·검증 상태·데이터 분류·공식 URL만 표시한다.
11. `chunk_id`, 내부 경로, 검색 점수, 원문 전체, 프롬프트는 노출하지 않는다.
12. 로딩, 최초 데이터 없음, 검색 결과 없음, 부분 실패와 재시도 가능 오류를 구분한다.

### 완료 기준

- 공통 API Client와 응답·오류 타입이 Mock 또는 테스트 API에서 동작한다.
- 목록과 상세가 같은 상태·위험도 컴포넌트를 사용한다.
- 401·403·404·409가 서로 다른 사용자 상태로 표시된다.
- 날짜·시간을 중복 변환하지 않는다.
- 공개 식별자와 화면용 문의 번호가 구분된다.
- EvidenceCard에 내부 RAG 필드가 노출되지 않는다.
- 누락 필드나 알 수 없는 Enum에도 화면이 종료되지 않는다.

### 산출물

- 공통 API Client·타입
- 상태·위험도·우선순위 Badge
- Loading·Empty·Error UI
- EvidenceCard·Mapper

---

## 3.3 `CONS-01` 상담사 문의 목록·검색·필터 구현

### 작업 목적

상담사가 처리할 문의를 빠르게 찾고 위험도·우선순위·대기 시간을 기준으로 업무 순서를 판단하게 한다.

### 작업 위치

```
web/src/pages/consultant/ConsultantDashboardPage.tsx
web/src/features/inquiry-queue/
├─ api/{getInquiryQueue,inquiryQueueApiTypes}.ts
├─ components/{InquiryQueueTable,InquiryQueueFilters,InquirySearchForm}.tsx
├─ hooks/{useInquiryQueue,useInquiryQueueFilters}.ts
├─ model/{inquiryQueueTypes,inquiryQueueMapper,queryKeys}.ts
└─ validation/inquiryQueueFilterSchema.ts
web/tests/fixtures/inquiry-queue/{normal,danger,reopened,empty,error}.json
```

### 세부 작업 지침

1. 상담 필요·재개·상담 진행 등 계약에서 정한 문의를 목록으로 표시한다.
2. 문의 번호, 고객 표시명, 제품 모델, 대표 증상, 상태, 위험도, 우선순위, 접수·최근 변경 시각을 표시한다.
3. 문의 번호·고객·제품 검색과 상태·위험도·우선순위·기간·담당자 필터를 제공한다.
4. 위험·재개·장기 대기 정렬은 백엔드 계약을 따르고 프론트에서 임의 점수를 계산하지 않는다.
5. 서버 페이지네이션을 반영하고 검색·필터·정렬·페이지 상태를 URL Query 또는 합의된 방식으로 유지한다.
6. 로딩, 최초 문의 없음, 검색 결과 없음, 권한 없음, API 오류를 구분한다.
7. 항목 선택 시 공개 식별자를 사용하여 `CONS-02`로 이동한다.
8. 목록에는 고객 표시명과 허용된 마스킹 정보만 노출한다.
9. `data/synthetic/fixtures/**`를 기준으로 생성된 Web Fixture를 사용하고, `DEMO-INQ-002`, `SYN-JAC104-002`, `WPUJAC104DWH`, 출수량 저하 시나리오를 포함한다.

### 완료 기준

- Mock 또는 API 데이터가 목록에 렌더링된다.
- 검색·필터·정렬·페이지 변경이 조회 결과에 반영된다.
- 최초 데이터 없음과 검색 결과 없음이 구분된다.
- 상세 이동 후 돌아왔을 때 기존 조건이 유지된다.
- 공개 식별자와 화면용 문의 번호가 구분된다.
- 개인정보 과다 노출과 프론트 단독 우선순위 계산이 없다.

### 산출물

- `CONS-01` 목록 화면
- 검색·필터·정렬·페이지네이션
- 목록 타입·Mapper·Hook
- 정상·위험·재개·빈 결과 Fixture

---

## 3.4 `CONS-02` 문의 상세·AI 요약·공식 근거 구현

### 작업 목적

상담사가 한 문의의 고객·제품·증상·문진·조치·AI 요약·공식 근거·상태 이력을 확인하게 하고, AI 초안과 상담사 확정 내용을 명확히 구분한다.

### 작업 위치

```
web/src/pages/consultant/InquiryDetailPage.tsx
web/src/features/inquiry-detail/
├─ api/{getInquiryDetail,inquiryDetailApiTypes}.ts
├─ components/{InquiryHeader,CustomerProductSection,SymptomQuestionnaireSection,
│  CustomerActionSection,AiSummarySection,StatusHistorySection}.tsx
├─ hooks/useInquiryDetail.ts
└─ model/{inquiryDetailTypes,inquiryDetailMapper}.ts
web/src/features/evidence-viewer/**
web/tests/fixtures/inquiry-detail/{normal,danger,no-evidence,partial-failure,forbidden}.json
```

### 세부 작업 지침

1. 공개 식별자로 상세 API를 조회하고, 화면에는 업무용 문의 번호를 표시한다.
2. 문의 번호, 상태, 위험도, 우선순위, 현재 담당 주체, 고객 행동 필요 여부를 상단에 표시한다.
3. 고객 표시 정보, 제품·구독·관리 유형·최근 케어 정보를 역할에 맞게 마스킹해 표시한다.
4. 고객 원문, 구조화 증상, 문진·추가 답변, 고객 조치와 시스템 안내를 영역별로 구분한다.
5. 위험도, 사용 안내 상태, 제한 기능, 상담 필요 여부와 다음 행동을 표시한다.
6. AI 상담 요약은 `AI 초안`으로 표시하고 상담사 확정본과 분리한다.
7. 공식 근거는 EvidenceCard로 표시하고 상태 이력은 이전·다음 상태, 이벤트, 수행자, 시각을 보여준다.
8. API 일시 값은 별도 시간대 계산 없이 화면 표시 형식만 변환한다.
9. 상세 기본 정보·근거·이력은 독립 로딩과 부분 오류를 허용한다.
10. 403·404·미지원 제품·근거 없음·AI 실패를 구분한다.
11. 긴 원문·근거·상담 메모와 누락 필드가 레이아웃을 깨뜨리지 않게 한다.
12. 화면 필드의 API·DB 출처를 매핑 문서에 기록한다.

### 완료 기준

- 하나의 공개 식별자로 주요 상세 영역이 표시된다.
- AI 초안과 상담사 확정본이 구분된다.
- 위험·근거 없음·AI 실패가 다른 안내로 표시된다.
- 내부 정수 PK, 내부 경로, 검색 점수와 원문 전체가 노출되지 않는다.
- 근거나 이력의 부분 실패가 상세 전체를 가리지 않는다.
- 개인정보가 역할 기준에 맞게 마스킹된다.

### 산출물

- `CONS-02` 상세 화면
- 상세 타입·Mapper·Hook
- AI 초안·확정본 UI
- Evidence·상태 이력 영역
- 정상·위험·근거 없음·부분 실패 Fixture

---

## 3.5 상담 기록 Form과 `allowed_actions` 기반 행동 골격

### 작업 목적

상담사가 추가 확인사항·안내 내용·상담 결과를 입력하고 현재 상태에서 허용된 행동만 선택할 수 있는 최소 구조를 만든다. 3주차에는 Mock으로 입력·검증·충돌 처리를 우선 확인한다.

### 작업 위치

```
web/src/features/consultation/
├─ api/{saveConsultationDraft,startConsultation,finalizeInquiry}.ts
├─ components/{ConsultationForm,AiSummaryEditor,ConsultationResultFields}.tsx
├─ hooks/{useConsultationForm,useSaveConsultation}.ts
├─ model/**
└─ validation/consultationSchema.ts
web/src/features/workflow-action/{api,components,hooks,model}/**
web/tests/fixtures/workflow-action/{success,conflict,forbidden,validation-error}.json
```

### 세부 작업 지침

1. 상담 메모, 추가 확인사항, 고객 안내, 상담 결과, 방문 필요 여부를 입력할 수 있게 한다.
2. AI 초안을 수정하고 상담사 확정 여부를 구분한다.
3. 필수값과 서버 필드 오류를 Form에 연결하고 실패 후 입력을 유지한다.
4. 버튼은 `allowed_actions`에 포함된 행동만 표시한다.
5. 상태 변경은 `start-consultation`, `finalize` 등의 행동별 Endpoint를 사용하며, 이벤트 이름이나 다음 상태를 프론트에서 직접 구성하지 않는다.
6. 쓰기 요청에 `state_version`, `idempotency_key`, `correlation_id`를 반영한다.
7. 저장 중 중복 클릭을 차단하고 성공 후 최신 상세를 조회한다.
8. 403·409·422·네트워크 실패를 구분하며 409 발생 시 자동으로 덮어쓰지 않는다.
9. 409 응답의 최신 `current_status`, `state_version`, `allowed_actions`를 화면에 즉시 반영하고, 담당자·메모 등 추가 정보가 필요할 때만 상세 API를 재조회한다.
10. 409 처리 후에도 사용자가 작성한 상담 입력값은 유지한다.
11. 실제 API가 없으면 Mock 성공·실패·충돌로 검증하고 임시임을 표시한다.

### 완료 기준

- Form 입력·검증·실패 후 입력 유지가 동작한다.
- `allowed_actions`에 없는 버튼이 보이지 않는다.
- 상태 변경이 행동별 Endpoint를 통해 요청된다.
- 성공·403·409·422·네트워크 실패를 재현할 수 있다.
- 409 응답의 최신 상태와 허용 행동이 화면에 반영된다.
- 중복 클릭이 차단되고 성공 후 상세가 갱신된다.
- AI 초안과 상담사 확정본의 편집 책임이 구분된다.

### 산출물

- 상담 기록 Form·검증 Schema
- AI 요약 편집·확정 UI
- 행동별 Workflow Action 버튼·Hook
- 성공·충돌·권한·검증 오류 Mock

---

## 3.6 테스트·필드 매핑·7월 29일 검토용 산출물 정리

### 작업 목적

화면이 시안으로 끝나지 않도록 테스트·실행 문서·화면–API–DB 매핑을 남기고 7월 29일까지 검토 가능한 PR을 만든다.

### 작업 위치

```
web/tests/{unit,component,integration,fixtures,setup}/**
web/docs/
├─ week3-web-decisions.md
├─ week3-screen-api-db-map.md
├─ week3-test-result.md
└─ week3-open-issues.md
docs/testing/week3-web-review.md
```

### 세부 작업 지침

1. 상태·위험도 Mapper, 목록 Query, 상세 부분 실패, Form 검증, `allowed_actions` 버튼 테스트를 작성한다.
2. 목록→상세, 검색 결과 없음, danger 표시, 403 차단, 타 사용자 리소스 404, 409 충돌 중 최소 2~3개 통합 흐름을 검증한다.
3. Access Token 만료 후 재발급 성공·실패와 로그아웃 흐름을 검증한다.
4. 409 응답에 최신 상태, `state_version`, `allowed_actions`가 포함되고 화면에 반영되는지 확인한다.
5. 자동화하지 못한 흐름은 입력·절차·기대·실제 결과와 화면 캡처를 남긴다.
6. 기술 결정 문서에 채택·보류 라이브러리, 개인 시안 이전 범위, Router·Mock 교체 방식을 기록한다.
7. `CONS-01`, `CONS-02`, 상담 Form의 화면 필드·API 필드·DB 출처·마스킹·필수 여부를 매핑한다.
8. 정상 업무 Fixture는 `data/synthetic/fixtures/**`에서 생성하며 생성된 Web Fixture를 직접 수정하지 않는다.
9. DB 설계 문서의 상담사 필드와 전처리 결과서의 Evidence 메타데이터를 검수해 최지용·김은진·이동윤에게 의견을 전달한다.
10. 계약 변경이 필요한 경우 `contracts/**`의 계약 PR을 구현 PR보다 먼저 병합한다.
11. 7월 29일까지 실행 화면, Mock, 타입, 테스트, 미연동 범위가 포함된 PR을 만든다.
12. 7월 30~31일에는 계약 변경과 리뷰 의견, 마스킹·근거 노출 문제를 우선 수정한다.

### 완료 기준

- 7월 29일까지 검토 가능한 PR 또는 공유 파일이 있다.
- `CONS-01`·`CONS-02`와 상담 입력을 Mock으로 재현할 수 있다.
- 테스트가 통과하거나 실패 원인과 수동 검증이 기록되어 있다.
- 인증 갱신, 403·404 구분과 409 최신 상태 반영을 확인할 수 있다.
- 화면–API–DB 매핑과 미확정 필드가 문서화되어 있다.
- 공통 Fixture 기준본과 Web Fixture의 관계가 기록되어 있다.
- 두 공식 산출물에 웹 관점 검수 의견이 전달되어 있다.

### 산출물

- 단위·컴포넌트·통합 테스트
- 기술 결정·필드 매핑·테스트 결과·이슈 문서
- 산출물 검수 의견
- 7월 29일 검토용 PR

---

# 4. 조기 완료 시 추가 업무

필수 업무, 7월 29일 산출물, 리뷰 대응을 완료한 뒤에만 착수한다. 아래 업무는 공통 협의 결과 Q-01~Q-10과 contracts/**에서 확정된 상태·API 계약만으로 비교적 독립적으로 진행할 수 있는 4주차 이후 작업이다.

## 4.1 `CONS-03 방문 전환·일정 등록` 읽기·입력 골격 선행 구현

### 해당 WBS

- `T-041`, FR-026, CR-005

### 착수 조건

- 방문 필요 이벤트, 고객 희망일·가상 기사·방문 일정 상태, 방문 생성·수정 Mock이 3번 협의로 확정되어 있다.

### 작업 위치

```
web/src/pages/consultant/VisitTransitionPage.tsx
web/src/features/visit-transition/
├─ components/{VisitTransitionForm,TechnicianSelect,VisitScheduleFields}.tsx
├─ hooks/useVisitTransitionForm.ts
├─ model/**
├─ validation/**
└─ api/**
```

### 작업 내용

- 고객 방문 희망일, 가상 담당 기사, 전달사항, 기사 배정·일정 조율·방문 확정 상태를 입력·표시한다.
- 희망일과 확정일을 다른 필드로 구분한다.
- 상태 전환은 실제 저장 대신 Mock 성공·실패로 검증할 수 있다.
- 기사 인계 정보는 상담 상세에서 이미 확인된 정보만 사용하며 임의 진단을 추가하지 않는다.

### 완료 기준

- Mock 데이터로 방문 전환 Form이 표시되고 필수값 검증이 동작한다.
- 희망일·확정일과 방문 일정 상태가 구분된다.
- `allowed_actions`에 방문 검토가 없으면 화면 진입 또는 저장이 차단된다.

---

## 4.2 상담 결과 저장·409 충돌 처리 실제 API 연동

### 해당 WBS

- `T-040`, FR-024~FR-025, DR-001, DR-010

### 착수 조건

- 상담 저장·완료 API와 State Machine 이벤트, `state_version`, `idempotency_key`가 확정되고 테스트 API가 제공되어 있다.

### 작업 위치

```
web/src/features/consultation/api/**
web/src/features/workflow-action/api/**
web/src/features/consultation/hooks/**
web/tests/integration/**
```

### 작업 내용

- Mock Repository를 실제 API 호출로 교체한다.
- 상담 초안 저장, 상담 완료, 방문 필요 분기를 각각 검증한다.
- 409 충돌 시 최신 상세 조회와 사용자 확인 흐름을 구현한다.
- 성공 후 상태·이력·`allowed_actions`가 갱신되는지 확인한다.

### 완료 기준

- 실제 테스트 API에서 상담 저장·완료 또는 방문 검토 요청이 동작한다.
- 중복 요청과 오래된 `state_version`이 안전하게 처리된다.
- 통합 테스트 또는 재현 가능한 수동 검증 기록이 남는다.

---

## 4.3 `ADMIN-01` 운영 대시보드 Route·정보 구조 Placeholder

### 해당 WBS

- `T-101~T-103`, FR-035~FR-037, DR-013

### 착수 조건

- 상담사 필수 화면과 검토 대응이 완료되었고, 운영 화면의 P1 범위를 확대하지 않기로 확인되어 있다.

### 작업 위치

```
web/src/pages/admin/OperationsDashboardPage.tsx
web/src/features/operations-dashboard/
├─ components/**
├─ model/**
└─ api/**

docs/screens/admin-dashboard-field-plan.md
```

### 작업 내용

- 운영자 Route·Menu·권한 Guard와 빈 대시보드 골격만 만든다.
- 문의 상태·위험·장기 대기·AI 실패·근거 없음 등 필요한 지표와 API 필드를 문서로 정리한다.
- 차트 라이브러리 도입과 실제 집계 API 연결은 다음 주 이후로 남긴다.

### 완료 기준

- 운영자만 `ADMIN-01` Placeholder에 접근할 수 있다.
- 필요한 지표·필터·API 필드가 문서화되어 있다.
- P1 대시보드 구현이 3주차 P0 업무를 침해하지 않는다.

---

---

# 5. 완료 기준 및 최종 체크리스트

## 5.1 7월 29일 필수 완료 기준

- [ ]  `web/` 의존성 설치·개발 서버·TypeScript 검사·Production Build가 성공한다.
- [ ]  상담사 Router·Layout·Role Guard가 동작한다.
- [ ]  401·403·404·전역 오류가 구분되어 있다.
- [ ]  공통 API 응답·오류·페이지네이션 타입이 있다.
- [ ]  상태·위험도·우선순위·근거 카드 공통 UI가 있다.
- [ ]  `CONS-01` 목록에서 검색·필터·정렬·페이지네이션을 Mock 또는 API로 확인할 수 있다.
- [ ]  목록에서 `CONS-02` 상세로 이동할 수 있다.
- [ ]  `CONS-02`에서 고객·제품·증상·문진·AI 요약·공식 근거·상태 이력이 구분되어 표시된다.
- [ ]  AI 초안과 상담사 확정 내용이 구분된다.
- [ ]  내부 경로·검색 점수·`chunk_id`·원문 전체가 화면에 노출되지 않는다.
- [ ]  상담 기록 Form과 `allowed_actions` 기반 버튼 골격이 있다.
- [ ]  정상·위험·근거 없음·권한 없음·409 충돌 Mock이 있다.
- [ ]  최소 테스트 또는 수동 검증 결과가 있다.
- [ ]  화면–API–DB 매핑과 미확정 사항이 문서화되어 있다.
- [ ]  7월 29일까지 검토 가능한 PR 또는 공유 파일이 있다.

## 5.2 7월 30일~31일 최종 정리 기준

- [ ]  API·AI·State Machine 계약 변경이 TypeScript 타입과 화면에 반영되었다.
- [ ]  다른 팀원이 README로 웹을 실행할 수 있다.
- [ ]  목록·상세·상담 입력의 빌드·렌더링 오류가 수정되었다.
- [ ]  개인정보 마스킹과 내부 근거 비노출을 다시 확인했다.
- [ ]  Mock과 실제 API 차이가 문서에 표시되어 있다.
- [ ]  최지용·이동윤·김은진에게 API·근거·테스트 자료를 전달했다.
- [ ]  두 공식 산출물에 웹 관점 검수 의견이 반영되었는지 확인했다.
- [ ]  미완료 기능과 다음 주 작업이 Issue에 기록되어 있다.
- [ ]  필수 업무 완료 후에만 4장의 추가 업무를 시작했다.

## 5.3 웹 역할 수행 시 주의사항

- 개인 시안은 참고 자료이며 팀 프로젝트의 React·TypeScript 구조로 다시 작성한다.
- 운영 대시보드 P1보다 상담사 `CONS-01`·`CONS-02` P0 흐름을 우선한다.
- 프론트엔드는 상태·위험도·우선순위를 독자적으로 계산하지 않는다.
- 버튼은 백엔드의 `allowed_actions`를 기준으로 표시한다.
- 쓰기 요청은 `state_version`, `idempotency_key`, `correlation_id` 계약을 따른다.
- AI 초안과 상담사 확정본을 같은 값처럼 표시하거나 덮어쓰지 않는다.
- 공식 근거는 공개가 허용된 EvidenceCardDTO만 표시한다.
- 실제 개인정보·토큰·운영 비밀값은 Fixture와 저장소에 넣지 않는다.
- Backend 지연을 이유로 화면·Mock·타입·테스트 작업을 중단하지 않는다.
- `contracts/**`, `tests/**`, `.github/**`, `infra/**`를 수정할 때는 해당 주관할 담당자와 협의한다.

---

# 6. 지침서 작성 시 참고 문서

| 문서명 | 참고한 내용 | 지침서 반영 위치 |
| --- | --- | --- |
| `(WBS_29기_4팀) 정수기 구독 고객 케어 및 AS 업무 지원 시스템.md` | `T-038` 상담 목록, `T-039` 상담 상세, `T-040` 상담 결과, `T-041` 방문 일정, `T-045` 웹 공통, `T-046` 통합, `T-050` 테스트, `T-101~103` P1 운영 기능의 일정·선후행 관계 | 2장 역할 목표, 3장 필수 업무, 4장 조기 완료 업무 |
| `(요구사항정의서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | 상담사 목록·상세·상담 결과·방문 전환, 권한·오류·공식 근거·상태 처리 요구사항 | 3.3~3.5 기능·예외 기준, 5장 체크리스트 |
| `(화면설계서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | `CONS-01~03`, `ADMIN-01`의 목적·필드·행동·진입 조건, EvidenceCardDTO, `allowed_actions`, 완료 정책 | 3.3~3.5 화면 구현, 4.1·4.3 추가 업무 |
| `한예나_3주차_업무계획서_역할방향반영.md` | 상담사·운영 화면 구조, 검색·목록·상세 기능, 화면–DB·API 매핑, 기존 개인 시안 이전 계획 | 1장 역할 해석, 2장 목표, 3장 작업 범위 전체 |
| `프로젝트 디렉토리 구조.md` | React·Vite·TypeScript 기반 `app/pages/features/entities/common` 구조, 상담사·운영 페이지·기능별 권장 파일 | 1장 관할, 3장 작업 위치와 파일명 전체 |
| `팀원별 관할 영역.md` | `web/**` 주관할 및 API·Workflow·Evidence·Web Test의 부관할 관계 | 1장 기본 정보 |
| `공통 개발 규칙.md` | 브랜치·Issue·커밋·PR, API 계약, 환경변수·보안, 오류·로그, 테스트·완료 기준 | 3.1 실행 환경, 3.2 API 처리, 3.6 테스트·PR, 5장 체크리스트 |
| `(기획서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | 상담사 사용자 역할, 고객 문의→상담→방문 연결, MVP 제품·대표 시나리오와 안전·근거 원칙 | 2장 역할 목표, 3.3~3.5 상담사 화면 범위 |
| `(수집데이터보고서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템(1).md` | 공식 매뉴얼 모델·버전·페이지, D세대·후속 모델 분리, 근거 메타데이터 | 3.2 EvidenceCard, 3.3~3.4 대표 Mock과 근거 표시 |
| `윤승혁_3주차_업무_지침서.md` | 7월 29일 산출물 완료 원칙, 상태·API·AI 공통 계약, 4주차 진입 조건 | 문서 전체 일정·공통 계약·완료 기준 정합성 |
| `양정현_3주차_업무_지침서.md` | 웹·모바일 공통 상태·위험도·Evidence 표시명과 지침서 분량·상세 구조 | 3.2 공통 UI, 문서 형식 통일 |

---

본 지침서의 필수 업무는 7월 29일까지 검토 가능한 결과물을 만드는 것을 기준으로 한다. 7월 30일~31일에는 API·AI·State Machine 계약 변경 반영, 목록·상세·상담 입력 오류 수정, 개인정보 마스킹과 공식 근거 비노출 검토, 리뷰 의견 반영을 우선하며, 이 작업이 끝난 경우에만 4장의 추가 업무를 수행한다.
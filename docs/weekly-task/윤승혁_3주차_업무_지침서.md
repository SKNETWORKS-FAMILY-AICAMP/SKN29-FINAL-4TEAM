# 윤승혁 3주차 업무 지침서

> 프로젝트: 정수기 구독 고객 케어 및 A/S 업무 지원 시스템
> 
> 
> 대상 기간: 2026년 7월 27일 ~ 7월 31일
> 
> 필수 산출물 목표 완료일: **2026년 7월 29일**
> 
> 7월 30일~31일 운영 원칙: 신규 필수 업무 착수보다 **통합 검토, 계약 정합성 확인, 오류 수정, 다음 주 진입 준비**를 우선한다.
> 

---

# 1. 담당자 기본 정보

| 항목 | 내용 |
| --- | --- |
| 담당자 | 윤승혁 |
| 담당 역할 | PM·기술 통합 담당 |
| 주관할 영역 | 저장소 최상위 구조, `contracts/state-machine/**`, `contracts/examples/**`, `scripts/contracts/**`, `.github/ISSUE_TEMPLATE/**` |
| 부관할 영역 | `backend/**`, `tests/**`, `.github/workflows/**`, `scripts/testing/**`, `scripts/release/**` |
| 공동 편집 영역 | `docs/**` |
| 주요 협업 대상 | 최지용, 이동윤, 김은진, 한예나, 양정현 |
| 3주차 핵심 책임 | 공통 계약 확정, State Machine 기준 정리, 일정·의존성 관리, 7월 29일 산출물 검수, 4주차 진입 조건 확정 |
| 핵심 산출물 | 상태 전이 계약 묶음, 기술 결정 기록, 3주차 범위·완료 기준, 산출물 검토 기록, 주간 장애·의존성 현황 |

윤승혁은 특정 서비스의 기능을 대신 구현하는 역할보다, 각 담당자의 결과물이 서로 충돌하지 않고 하나의 서비스 흐름으로 연결되도록 기준을 확정하고 검토하는 역할을 맡는다. 특히 3주차에는 백엔드 State Machine, AI JSON 스키마, 프론트엔드 표시 규칙, 데이터·DB 산출물이 동시에 진행되므로, 구현 이후에 맞추는 방식이 아니라 **구현 전에 계약을 고정하는 것**이 핵심이다.

---

# 2. 3주차 역할 목표

1. **서비스 간 공통 계약을 7월 27일~28일에 확정한다.**
    
    백엔드, AI, 웹, 모바일, 데이터·QA가 공통으로 사용하는 상태·이벤트·위험도·사용 안내·오류·추적 필드를 하나의 기준으로 통일한다.
    
2. **3주차 필수 산출물을 7월 29일까지 검토 가능한 상태로 완성한다.**
    
    데이터 전처리 결과서와 데이터베이스·저장소 설계 문서가 템플릿 수준에 머무르지 않고, 실제 파일·테이블·처리 건수·설계 근거를 포함하도록 검수한다.
    
3. **7월 30일~31일을 통합 품질 확보 기간으로 운영한다.**
    
    상태 계약, API·AI 스키마, 화면 필드, 테스트 기준의 불일치를 제거하고 4주차 작업에 들어가기 위한 진입 조건과 미해결 사항을 명확히 기록한다.
    

---

# 3. 3주차 필수 업무

## 3.1 3주차 P0 범위와 완료 기준 확정

### 작업 목적

3주차에 반드시 끝내야 하는 일과 다음 주로 넘겨도 되는 일을 구분하여, 각 담당자가 과도한 확장 기능이나 후순위 기술에 시간을 사용하지 않도록 한다. 특히 7월 29일을 산출물 완료일로 고정하고, 7월 30일~31일에는 검토와 수정이 가능하도록 작업 순서를 조정한다.

### 작업 위치

- 현재 WBS 최신본: `(WBS_29기_4팀) 정수기 구독 고객 케어 및 AS 업무 지원 시스템.md`
- 저장소 반영 위치: `docs/planning/**`
- 권장 생성 파일: `docs/planning/week3-scope-and-dod.md`
- 작업 추적: GitHub Issues
- Issue 양식 검토: `.github/ISSUE_TEMPLATE/**`

### 세부 작업 지침

1. WBS의 3주차 작업 중 진행 중·지연·미착수 항목을 다시 확인한다.
    - T-005 ERD·표준 코드
    - T-006 AI 공통 상태·JSON 스키마
    - T-007 테스트 설계
    - T-011 임베딩·Vector DB·검색 파이프라인
    - T-012 RAG 평가 세트
    - T-013 합성 사용자·구독·케어 데이터
    - T-015 안전 규칙
    - T-016 백엔드 공통 구조
    - T-017 가상 로그인·역할 권한
    - T-022 문의 생성·누적
    - T-023 State Machine API 준비
    - T-025 AI 오케스트레이터 최소 골격 준비
    - T-038~T-040 상담사 웹 화면 최소 구현
2. 담당자별 필수 결과를 기능 단위가 아니라 검증 가능한 결과 단위로 정의한다.
    - 실행되는 서버 또는 앱
    - 검증 가능한 API 또는 Mock
    - 실제 값이 들어간 데이터·문서
    - 정상·오류 예시
    - PR 또는 파일 경로
3. 3주차에서 제외하거나 선택 사항으로 둘 항목을 명확히 한다.
    - 전체 다중 에이전트 완성
    - RunPod·sLLM 전환
    - 모바일 Hilt·Room·WorkManager·FCM 심화 적용
    - 운영 대시보드 P1 본격 구현
    - 전체 배포·Kubernetes 완성
    - 전체 고객→상담사→기사 E2E 통합
4. 각 Issue에 요구사항 ID, 담당자, 선행 작업, 완료 기준, 결과물 경로를 연결한다.
5. 7월 29일 이후 남은 작업은 반드시 다음 중 하나로 분류한다.
    - 검토 대기
    - 오류 수정
    - 연동 확인
    - 다음 주 인계
    - 범위 제외

### 완료 기준

- 팀원 6명의 3주차 필수 업무와 추가 업무가 구분되어 있다.
- 모든 필수 업무에 담당자, 결과물, 완료 기준, 파일 또는 디렉터리 위치가 기록되어 있다.
- 7월 29일 산출물 완료와 7월 30~31일 검토 원칙이 WBS 또는 운영 문서에 반영되어 있다.
- P1 및 후순위 기술이 3주차 필수 업무에 혼입되지 않는다.
- 팀원이 자신의 우선순위와 선행 의존성을 설명할 수 있다.

### 산출물

- 3주차 범위·완료 기준 문서
- 최신 WBS 상태
- 담당자별 GitHub Issue 또는 작업 목록
- 범위 제외·다음 주 이관 목록

---

## 3.2 State Machine 계약 최종 정리

### 작업 목적

백엔드, 웹, 모바일, AI, 테스트가 동일한 문의 상태와 이벤트를 사용하도록 단일 기준을 확정한다. 윤승혁은 `contracts/state-machine/**`의 주관할 담당자로서 상태 흐름의 의미와 업무 정책을 책임지고, 최지용은 실제 백엔드 구현 가능성과 DB 저장 구조를 검토한다.

### 작업 위치

```
contracts/state-machine/
├─ inquiry-states.yaml
├─ inquiry-events.yaml
├─ transition-rules.yaml
├─ transition-guards.yaml
├─ allowed-actions.yaml
├─ role-permissions.yaml
├─ completion-policy.yaml
├─ concurrency-policy.yaml
├─ diagrams/inquiry-state-machine.mmd
├─ examples/self-resolution.yaml
├─ examples/consultation-resolution.yaml
├─ examples/visit-resolution.yaml
├─ examples/danger-detected.yaml
├─ examples/no-evidence.yaml
├─ examples/reopened-inquiry.yaml
└─ README.md
```

연계 파일:

```
contracts/codes/inquiry-statuses.yaml
contracts/codes/workflow-actions.yaml
contracts/codes/user-roles.yaml
contracts/codes/visit-statuses.yaml
contracts/examples/customer-to-consultant.json
contracts/examples/consultant-to-technician.json
contracts/examples/technician-to-customer.json
contracts/examples/danger-fallback.json
contracts/examples/state-conflict.json
```

### 세부 작업 지침

1. `inquiry-states.yaml`에 각 상태의 코드, 사용자 표시명, 의미, 현재 담당 주체, 고객 행동 필요 여부를 정의한다.
    - `DRAFT`
    - `QUESTIONNAIRE_IN_PROGRESS`
    - `AI_GUIDANCE`
    - `CONSULTATION_REQUIRED`
    - `CONSULTATION_IN_PROGRESS`
    - `VISIT_REVIEW_PENDING`
    - 방문 관련 상태와의 연결
    - `COMPLETION_PENDING`
    - `REOPENED`
    - `RESOLVED`
    - 필요 시 `CANCELLED`
2. `inquiry-events.yaml`에서 이벤트 유형을 구분한다.
    - 사용자·담당자 요청 이벤트
    - 백엔드 자동 이벤트
    - 문의 상태를 변경하지 않는 데이터 수정 이벤트
    - 외부 REST API는 `/request-consultation`, `/start-consultation`, `/finalize` 등의 행동별 Endpoint를 사용하고, 각 Endpoint를 내부 State Machine 이벤트와 연결한다.
3. `transition-rules.yaml`에 현재 상태, 이벤트, 결과 상태, 이력 저장 여부를 연결한다.
4. `transition-guards.yaml`에 다음 검증 기준을 포함한다.
    - 역할과 담당자 일치
    - 단계별 필수 입력값 존재
    - 지원 모델·세대 검증
    - 현재 상태에서 이벤트 허용 여부
    - 상담·방문 최종 완료 권한
    - 위험·근거 부족 시 일반 안내 경로 차단
5. `allowed-actions.yaml`에는 웹·모바일이 화면 버튼을 임의 판단하지 않도록 상태와 역할별 행동 코드를 정의한다.
6. `completion-policy.yaml`에는 다음 세 경로를 구분한다.
    - 자가조치 단독 해결
    - 상담 처리 후 고객 피드백·담당자 최종 완료
    - 방문 처리 후 고객 피드백·담당자 최종 완료
7. `concurrency-policy.yaml`에는 최소한 다음을 명시한다.
    - `state_version` 불일치 시 409 Conflict를 반환하고, 응답에 최신 `current_status`, `state_version`, `allowed_actions`를 포함
    - 동일 `idempotency_key` 재요청의 중복 처리 방지
    - `correlation_id`를 통한 요청 추적
    - 같은 문의에 대한 동시 상태 변경 처리 원칙
8. Mermaid 다이어그램과 YAML 규칙이 서로 다르지 않은지 확인한다.
9. 정상 흐름 외에도 위험, 근거 없음, 미지원 제품, 동시 수정 충돌, 미해결 재개 예시를 작성한다.

### 완료 기준

- 상태·이벤트·전이·가드·허용 행동·권한·완료 정책이 별도 파일로 구분되어 있다.
- 화면설계서의 핵심 상태 흐름과 계약 YAML이 일치한다.
- 최지용이 백엔드 구현 가능성을 검토하고, 한예나·양정현이 화면 행동과 표시 필드를 검토한다.
- 김은진이 계약 테스트로 검증 가능한 구조인지 확인한다.
- 이동윤이 AI 자동 이벤트와 결과 상태의 연결을 확인한다.
- 행동별 Endpoint와 내부 State Machine 이벤트의 연결이 정의되어 있다.
- 위험·근거 없음·재개·충돌 사례가 예시 파일로 존재한다.
- 계약 변경 내용이 `contracts/CHANGELOG.md`에 기록되어 있다.

### 산출물

- State Machine 계약 파일 일체
- 상태 전이 Mermaid 원본
- 대표 전이 예시 6종
- 계약 변경 기록
- 관련 팀원 검토 결과

---

## 3.3 API·AI·공통 코드의 영역 간 정합성 검토

### 작업 목적

API와 AI 스키마는 각각 최지용과 이동윤이 주관하지만, 동일한 개념을 서로 다른 이름이나 값으로 표현하면 화면·DB·테스트에서 변환 코드가 난립한다. PM은 계약 전체를 가로질러 공통 필드와 코드가 일치하는지 검토하고 충돌을 해소한다.

### 작업 위치

```
contracts/api/**
contracts/ai/**
contracts/codes/**
contracts/error-codes/**
contracts/examples/**
contracts/VERSION
contracts/CHANGELOG.md
contracts/README.md
```

중점 검토 파일:

```
contracts/api/components/schemas/common/ApiResponse.yaml
contracts/api/components/schemas/common/ApiError.yaml
contracts/api/components/schemas/common/TraceContext.yaml
contracts/api/components/schemas/inquiry/InquirySummary.yaml
contracts/api/components/schemas/inquiry/InquiryDetail.yaml
contracts/api/components/schemas/workflow/WorkflowSnapshot.yaml
contracts/api/components/schemas/workflow/AllowedAction.yaml
contracts/api/components/schemas/workflow/StateTransitionRequest.yaml
contracts/api/components/schemas/workflow/StateTransitionResult.yaml
contracts/ai/responses/SymptomAnalysisResponse.schema.json
contracts/ai/common/SafetyAssessment.schema.json
contracts/ai/common/UsageGuidance.schema.json
contracts/ai/common/EvidenceReference.schema.json
contracts/codes/risk-levels.yaml
contracts/codes/usage-guidance-statuses.yaml
contracts/error-codes/categories/workflow.yaml
contracts/error-codes/categories/ai.yaml
contracts/error-codes/categories/evidence.yaml
```

### 세부 작업 지침

1. 아래 공통 값의 영문 코드와 의미를 하나로 고정한다.
    - 역할: CUSTOMER, CONSULTANT, TECHNICIAN, OPERATOR
    - 위험도: `general`, `caution`, `danger`
    - 사용 안내 상태: `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`
    - 담당 주체와 고객 행동 필요 여부
    - Evidence 검증 상태와 사용 허용 범위
2. AI 응답과 REST 응답에서 같은 필드를 다른 이름으로 사용하지 않는지 확인한다.
    - `usage_guidance_status`
    - `usage_guidance_message`
    - `restricted_functions`
    - `evidence`
    - `next_action`
    - `requires_consultation`
    - `risk_level`
3. 내부 AI 근거와 화면용 EvidenceCard를 구분한다.
    - AI 내부 참조에는 문서·청크 식별자를 포함할 수 있다.
    - 화면 응답에는 내부 경로, 원문 전체, 검색용 내부 텍스트를 노출하지 않는다.
    - 사용자에게는 문서명, 버전, 페이지, 검증 상태, 요약 근거만 제공한다.
4. DB·API 공통 정책이 계약과 설계 문서에 동일하게 반영되어 있는지 확인한다.
    - DB에는 UTC로 저장하고 API에는 `+09:00`이 포함된 ISO 8601 형식으로 반환한다.
    - 주요 업무 테이블은 정수형 내부 PK와 별도 공개 식별자를 사용하며, `DEMO-*`, `SYN-*` 값은 업무·시연 식별자로 관리한다.
    - 고정 상태·역할 값은 문자열 칼럼과 Django `TextChoices`로 관리한다.
5. 인증·공통 오류 응답을 검토한다.
    - Access Token과 Refresh Token을 사용하며 만료 시간은 각각 60분, 7일로 한다.
    - 로그아웃 시 서버에서 Refresh Token을 무효화한다.
    - 입력값 누락: 400
    - 인증 실패·토큰 만료: 401
    - 역할·소유권·담당 권한 부족: 403
    - 대상 없음: 404
    - 상태 버전·중복 요청 충돌: 409이며 최신 상태, `state_version`, `allowed_actions`를 포함한다.
    - AI·검색 실패: 재시도 가능 여부와 상담 Fallback 정보 포함
6. 목록·상세·행동별 상태 변경 API의 Mock 예시가 웹·모바일이 바로 사용할 수 있는 수준인지 확인한다.
7. `contracts/VERSION`과 `CHANGELOG.md`에 호환·비호환 변경을 구분하여 기록한다.
8. 계약 파일을 수정할 때 주관할 담당자의 승인을 받는다.
    - API: 최지용 주관할
    - AI: 이동윤 주관할
    - 공통 코드·오류 코드: 최지용 주관할, 윤승혁 부관할
    - State Machine: 윤승혁 주관할

### 완료 기준

- 동일 개념의 필드명과 코드값이 API, AI, DB 설계, 화면 Mock에서 일치한다.
- 사용 안내 상태가 `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`으로 통일되어 있다.
- 날짜·시간, 식별자, Enum, 인증·오류 정책이 API·DB 설계·Mock에서 일치한다.
- 정상·위험·근거 없음·오류 응답 예시를 웹과 모바일에서 사용할 수 있다.
- 화면에 노출해서는 안 되는 내부 근거 필드가 구분되어 있다.
- 계약 변경의 주관할 담당자 승인이 확인된다.
- 계약 버전과 변경 이력이 갱신되어 있다.

### 산출물

- 공통 필드·코드 정합성 검토표
- 수정된 계약 파일과 예시 JSON
- 오류 코드 충돌 해소 내역
- 계약 버전·변경 이력

---

## 3.4 7월 29일 필수 산출물 통합 검수

### 작업 목적

3주차 공식 산출물이 템플릿 문구와 임의 예시에 머무르지 않고, 실제 프로젝트의 데이터·DB·저장소 설계를 반영하도록 한다. 윤승혁은 문서의 주 작성자가 아니지만, 제출 전에 서로 다른 산출물 간 용어·수치·구조가 일치하는지 최종 검토한다.

### 작업 위치

원본 양식:

```
[데이터 전처리] 데이터 전처리 결과서.docx
[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx
```

저장소 반영 권장 위치:

```
docs/planning/[데이터 전처리] 데이터 전처리 결과서.docx
docs/planning/[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx
docs/testing/week3-deliverable-review.md
```

관련 근거:

```
data/raw/**
data/processed/**
data/synthetic/**
data/catalog/**
backend/apps/**/migrations/**
contracts/codes/**
contracts/ai/**
contracts/state-machine/**
```

### 세부 작업 지침

#### A. 데이터 전처리 결과서 검수

1. MVP 대상이 `WPUJAC104DWH`, 공식 매뉴얼 적용 모델이 WPU-JAC104D·WPU-JCC104D REV.00으로 일치하는지 확인한다.
2. WPUIAC425SNW가 MVP 검색·화면 범위에 포함되지 않았는지 확인한다.
3. D세대와 S세대, MVP와 후속 확장 자료가 분리되어 있는지 확인한다.
4. 수집→추출→정제→청크→검증 단계별 실제 파일과 처리 건수를 기록했는지 확인한다.
5. 원본 건수, 추출 성공·실패, 제거·중복, 최종 청크 수가 서로 산술적으로 설명되는지 확인한다.
6. 문서명, 버전, 페이지, 해시, 제품 세대, 증상, 검증 상태 메타데이터가 포함되었는지 확인한다.
7. 대표 P0 질의 모두에서 정답 문서·페이지가 Top-5에 포함되는지 확인한다.
8. 모델·세대 불일치 근거가 정답 결과에 포함된 사례가 0건인지 확인한다.
9. 비공식 자료나 미검증 FAQ가 단독 근거로 사용되지 않는지 확인한다.

#### B. 데이터베이스·저장소 설계 문서 검수

1. 사용자, 역할, 제품, 구독, 케어 이력, 문의, 문진, AI 분석, 근거, 상담, 방문, 상태 이력 테이블이 포함되었는지 확인한다.
2. Inquiry 없이 시작하는 사전 문진을 위해 QuestionnaireSession 또는 동등한 구조가 반영되었는지 확인한다.
3. 현재 사용 안내 상태, 제한 기능, 판단 근거, 현재 담당 주체, 고객 행동 필요 여부가 저장 가능한지 확인한다.
4. 방문 희망일과 확정일, 일정 상태가 구분되어 있는지 확인한다.
5. AI 초안과 상담사·기사 수정·확정본을 구분할 수 있는지 확인한다.
6. 상태 변경 시 이전 상태, 다음 상태, 변경자, 변경 시각, 사유, 버전을 저장하는지 확인한다.
7. 정수형 내부 PK, 별도 공개 식별자와 업무·시연 식별자가 구분되어 있는지 확인한다.
8. 고정 상태·역할 값이 문자열 칼럼과 Django `TextChoices`로 관리되는지 확인한다.
9. DB UTC 저장과 API `+09:00` ISO 8601 반환 정책이 반영되어 있는지 확인한다.
10. PostgreSQL 관계형 데이터와 pgvector 검색 데이터의 책임 경계가 명시되어 있는지 확인한다.
11. `BAAI/bge-m3` 원본 출력 차원과 VectorField 차원이 일치하고 MVP 검색이 Exact Search로 설계되어 있는지 확인한다.
12. 원본 PDF, 전처리 파일, 합성 데이터, DB Seed, Vector 데이터의 저장 위치와 Git 추적 여부가 구분되어 있는지 확인한다.
13. 실제 개인정보를 사용하지 않고 합성 고객·연락처·방문 데이터를 사용한다는 원칙이 기록되어 있는지 확인한다.

#### C. 문서 간 공통 검수

- 제품 코드와 모델명이 동일하다.
- 위험도와 사용 안내 상태 코드가 동일하며, 사용 안내 상태는 `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`을 사용한다.
- 데이터 분류가 official, team_designed, synthetic 등으로 일관된다.
- 대표 시나리오 ID가 SYN-JAC104-002 / DEMO-INQ-002로 일치한다.
- 표·그림·파일 경로가 실제 저장소 구조와 맞는다.
- 아직 측정하지 않은 수치를 임의로 작성하지 않는다.
- 미완료 내용은 완료된 것처럼 표현하지 않고 예정·미측정으로 표시한다.

### 완료 기준

- 두 산출물의 모든 템플릿 예시가 실제 프로젝트 내용으로 교체되어 있다.
- 문서 내 테이블명·파일명·건수·모델명이 실제 결과와 일치한다.
- 김은진과 최지용이 각각 주 작성자 검토를 완료했다.
- 이동윤이 전처리·RAG·Vector 관련 내용을 검토했다.
- 화면 필드가 필요한 부분은 한예나·양정현의 요구와 충돌하지 않는다.
- 윤승혁의 통합 검토 결과와 수정 요청이 `docs/testing/week3-deliverable-review.md` 또는 동등한 검토 기록으로 남아 있다.
- 7월 29일 종료 시점에 다른 팀원이 읽고 검토할 수 있는 완성본이 존재한다.

### 산출물

- 데이터 전처리 결과서 검토 완료본
- 데이터베이스·저장소 설계 문서 검토 완료본
- 통합 검토 체크리스트
- 수정 요청·반영 결과 기록

---

## 3.5 일정·장애·PR·관할 충돌 관리

### 작업 목적

개별 담당자의 작업이 끝났더라도 계약 변경, PR 순서, 파일 관할 충돌로 통합이 지연될 수 있다. PM은 매일 막힌 작업을 확인하고, 결정을 미루지 않으며, 변경 이력이 남도록 관리한다.

### 작업 위치

```
.github/ISSUE_TEMPLATE/**
.github/CODEOWNERS
.github/pull_request_template.md
docs/daily-scrum/**
docs/planning/**
contracts/CHANGELOG.md
```

GitHub 관리 대상:

- Issues
- Pull Requests
- Project 또는 작업 보드
- 리뷰 요청 및 병합 순서

### 세부 작업 지침

1. 매일 작업 시작 전 또는 데일리 스크럼에서 다음을 확인한다.
    - 어제 완료한 결과
    - 오늘 완료할 결과
    - 다른 담당자의 결정·파일을 기다리는 항목
    - 7월 29일 산출물에 영향을 주는 장애
    - 관할이 아닌 파일을 수정해야 하는 작업
2. 장애는 단순 메모가 아니라 다음 정보로 기록한다.
    - 장애 내용
    - 영향을 받는 담당자와 작업
    - 결정권자
    - 해결 기한
    - 임시 대안
    - 최종 결정
3. `contracts/**`를 계약의 유일한 기준본으로 사용하고, 계약 변경 PR을 해당 계약에 의존하는 구현 PR보다 먼저 병합한다. Mock·Stub 기반 작업은 계약 병합 전에도 진행할 수 있으나 실제 연동 완료로 판정하지 않는다.
4. PR 설명에는 다음 항목을 포함하도록 검토한다.
    - 변경 목적
    - 관련 요구사항·WBS ID
    - 변경 파일
    - 테스트 또는 확인 방법
    - 다른 영역에 미치는 영향
    - 미완료·후속 작업
5. 다음과 같은 병합 순서를 우선 적용한다.
    1. 공통 코드·State Machine·API·AI 계약
    2. DB·Backend 구현
    3. AI·RAG 구현
    4. Web·Mobile Mock 또는 연동
    5. 계약·통합 테스트
    6. 문서와 결과 보고서
6. 관할 규칙을 적용한다.
    - 주관할: 자체 수정 가능
    - 부관할: 주관할과 협의 후 수정
    - 관할 아님: 주관할 협의와 PM 허가 필요
    - `docs/**`: 공동 편집 가능하나 기계 검증 계약은 `contracts/**`에만 작성
7. PM이 모든 PR을 직접 수정하지 않는다. 충돌 원인을 정리하고, 해당 주관할 담당자가 수정하도록 배정한다.

### 완료 기준

- 팀원이 막힌 작업과 결정 대기 항목을 확인할 수 있다.
- 24시간 이상 방치된 핵심 계약 장애가 없다.
- 계약 변경과 구현 변경의 순서가 관리된다.
- PR에 요구사항·테스트·영향 범위가 기록되어 있다.
- 관할이 아닌 디렉터리의 무단 수정이 없다.
- 7월 29일 산출물과 핵심 계약 관련 PR이 우선 검토된다.
- 7월 31일 기준 미완료 작업은 다음 주 인계 항목으로 기록되어 있다.

### 산출물

- 일별 장애·의존성 기록
- 최신 WBS·Issue 상태
- PR 검토 및 병합 순서
- 관할 충돌 해결 기록
- 다음 주 인계 목록

---

## 3.6 계약 검증과 4주차 진입 조건 확정

### 작업 목적

계약 문서가 존재하는 것만으로는 충분하지 않다. 최소한의 자동 검증 또는 체크리스트를 통해 참조 오류, 상태 전이 누락, 코드 중복, 예시 JSON 불일치를 발견하고, 4주차 작업을 시작해도 되는 상태인지 판단한다.

### 작업 위치

```
scripts/contracts/
├─ validate_openapi.py
├─ validate_ai_schemas.py
├─ validate_state_machine.py
├─ validate_allowed_actions.py
├─ validate_codes.py
├─ validate_error_codes.py
├─ validate_examples.py
└─ check_breaking_changes.py

tests/contract/state-machine/
├─ transitions/
├─ guards/
└─ allowed-actions/

tests/contract/codes/
tests/contract/error-codes/
tests/contract/test_contract_references.py

docs/testing/**
docs/planning/**
```

권장 생성 파일:

```
docs/testing/week3-contract-validation.md
docs/planning/week4-entry-criteria.md
```

### 세부 작업 지침

1. 김은진과 협의하여 3주차에 실행할 최소 검증 범위를 확정한다.
    - YAML·JSON 파싱 성공
    - 참조 대상 파일 존재
    - 상태·이벤트 코드 중복 없음
    - 모든 전이의 시작·종료 상태 존재
    - 모든 `allowed_actions`가 정의된 이벤트 또는 업무 행동 코드와 연결
    - 예시 JSON이 계약 Schema와 일치
    - Backend↔AI 전체 Timeout 30초, AI 내부 최대 재시도 1회, Backend 자동 재시도 0회가 계약과 설정에 일치
    - `BAAI/bge-m3` 원본 출력 차원과 DB VectorField 차원이 일치하며 MVP 검색은 Exact Search 사용
    - 대표 P0 질의 모두에서 정답 페이지가 Top-5에 포함되고 모델·세대 불일치 근거가 0건
    - `data/synthetic/fixtures/**` 기준본과 서비스별 자동 변환 Fixture가 일치
2. State Machine에서 최소 다음 사례를 검증 대상으로 지정한다.
    - 정상 증상 제출
    - 위험 감지 후 상담 전환
    - 공식 근거 없음 후 상담 전환
    - 자가조치 해결
    - 상담 완료 후 `COMPLETION_PENDING`
    - 방문 완료 후 `COMPLETION_PENDING`
    - 미해결 후 `REOPENED`
    - 담당자가 아닌 사용자의 `FINALIZE_INQUIRY` 차단
    - 동일 `idempotency_key` 재요청
    - 오래된 `state_version` 요청 충돌
3. 검증 스크립트를 윤승혁이 전부 구현하려 하지 않는다.
    - 김은진: 테스트 구조와 실행 조율
    - 최지용: API·코드·백엔드 구현 가능성
    - 이동윤: AI Schema와 자동 이벤트
    - 윤승혁: 상태·계약 기준과 합격 조건
4. 4주차 진입 조건을 작성한다.
    - ERD와 주요 코드가 동결 또는 변경 절차가 정해짐
    - Inquiry 생성·누적의 최소 API 또는 Mock이 있음
    - AI 요청·응답 Mock이 Schema를 통과함
    - `data/synthetic/fixtures/**`를 기준으로 생성된 Web·Mobile·Backend·AI용 Mock·Fixture가 있음
    - State Machine 핵심 경로가 문서·예시로 검증됨
    - Backend↔AI Timeout·재시도 정책과 pgvector 차원·검색 방식이 확정됨
    - 대표 P0 질의의 Top-5 검색 기준을 통과함
    - 두 개의 3주차 산출물이 검토 완료됨
    - 미해결 장애의 담당자와 처리 시점이 정해짐
5. 7월 30일~31일에는 검증 실패와 문서 수정에 우선 대응한다.

### 완료 기준

- 계약 파일이 최소 검증 스크립트 또는 수동 체크리스트를 통과한다.
- 상태 전이의 핵심 정상·예외 사례와 409 최신 상태 응답이 테스트 항목으로 존재한다.
- 누락된 코드·참조·예시 불일치가 기록되고 담당자가 배정된다.
- Timeout·재시도, Vector 차원·검색 방식, Top-5 평가와 공통 Fixture 기준이 검증되어 있다.
- 4주차 진입 조건이 문서화되어 있다.
- 진입 조건을 충족하지 못한 항목은 완료로 표시하지 않는다.
- 7월 31일 기준 다음 주 첫 작업이 명확하다.

### 산출물

- 계약 검증 결과
- 상태 전이 핵심 테스트 목록
- 수정 필요 항목과 담당자
- 4주차 진입 조건 문서

---

# 4. 조기 완료 시 추가 업무

아래 업무는 3번의 필수 업무와 7월 29일 산출물 검토가 끝난 뒤에만 착수한다. 추가 업무 때문에 다른 팀원의 긴급 장애 해결이나 필수 산출물 검토가 지연되어서는 안 된다.

## 4.1 중간 발표 대표 시연 시나리오 사전 패키지 작성

### 해당 WBS

- T-052 시연 준비: 2026년 8월 4일 예정

### 착수 조건

- 대표 시나리오와 상태 계약이 확정되어 있다.
- 데이터 전처리·DB 설계 산출물 검토가 끝났다.
- 다른 담당자의 추가 결정 없이 문서 초안을 작성할 수 있다.

### 작업 위치

```
docs/presentation/**
contracts/examples/**
data/synthetic/scenarios/**
scripts/development/**
```

권장 생성 파일:

```
docs/presentation/midterm-demo-scenario.md
docs/presentation/midterm-demo-checklist.md
```

### 작업 내용

- 대표 시연을 `WPUJAC104DWH / SYN-JAC104-002 / DEMO-INQ-002 / 출수량 저하 / 매뉴얼 38쪽`으로 고정한다.
- 고객 입력→추가 질문→위험 판정→공식 근거→자가조치→상담→방문→후속 확인의 단계별 기대 화면과 데이터를 작성한다.
- 각 단계에서 사용할 이벤트, 상태, 담당 주체, `allowed_actions`를 연결한다.
- 시연 실패 시 사용할 Mock·Seed·화면 대체 절차를 초안으로 작성한다.
- 실제 통합 구현이 끝나지 않은 단계는 구현 완료처럼 표현하지 않고 “예정 연결”로 표시한다.

### 완료 기준

- 팀원이 같은 시나리오 ID와 상태 흐름을 기준으로 시연을 준비할 수 있다.
- 필요한 데이터·API·화면·AI 결과가 단계별로 정리되어 있다.
- 4주차에 구현 결과를 채워 넣을 수 있는 체크리스트가 존재한다.

---

## 4.2 전체 통합 사전 체크리스트 작성

### 해당 WBS

- T-046 통합 개발의 사전 준비
- T-054 최종 통합 검수의 추적 구조 선행 작성

### 착수 조건

- 3번 협의 사항의 필드·상태·코드가 확정되어 있다.
- 실제 서비스 통합 구현을 하지 않고도 인터페이스 기준을 정리할 수 있다.

### 작업 위치

```
docs/architecture/**
docs/testing/**
tests/e2e/**
```

권장 생성 파일:

```
docs/architecture/integration-boundary-checklist.md
docs/testing/e2e-readiness-checklist.md
```

### 작업 내용

- Web·Mobile→Backend→AI·DB의 호출 경계를 정리한다.
- 영역별 입력·출력, 인증·추적 Header, 오류·Fallback, 저장 책임을 표로 작성한다.
- 대표 E2E에서 필요한 Seed, Mock, 상태 전이, Evidence 검증 항목을 정의한다.
- 각 통합 지점의 담당자와 검증 방법을 기록한다.

### 완료 기준

- 4주차 이후 통합 시 무엇을 어떤 순서로 확인할지 명확하다.
- 담당 영역 간 직접 소스 의존이 아니라 계약을 통해 연결되는 구조가 확인된다.
- 아직 구현되지 않은 인터페이스가 목록으로 드러난다.

---

## 4.3 P0 요구사항 추적표 골격 작성

### 해당 WBS

- T-054 최종 통합 검수의 선행 준비

### 착수 조건

- 현재 요구사항정의서와 WBS의 P0 범위가 확정되어 있다.
- 추가 기능 협의 없이 문서 구조를 만들 수 있다.

### 작업 위치

```
docs/planning/**
docs/testing/**
```

권장 생성 파일:

```
docs/planning/p0-requirements-traceability.md
```

### 작업 내용

다음 열을 가진 추적표를 만든다.

| 요구사항 ID | 기능·정책 | 담당자 | 구현 경로 | 계약 파일 | 테스트 경로 | 상태 | 증빙 |
| --- | --- | --- | --- | --- | --- | --- | --- |

우선 3주차에 관련된 요구사항부터 연결한다.

- FR-019~FR-026
- FR-032~FR-034
- FR-038
- NFR-001~NFR-006
- NFR-009~NFR-015
- NFR-017
- DR-007, DR-009~DR-012, DR-014~DR-015

### 완료 기준

- 요구사항이 WBS, 계약, 구현, 테스트 증빙과 연결될 수 있는 구조가 마련되어 있다.
- 미구현 항목을 완료로 표시하지 않는다.
- 이후 팀원이 자신의 구현 경로와 증빙만 추가할 수 있다.

---

# 5. 완료 기준 및 최종 체크리스트

## 5.1 7월 29일 필수 완료 기준

- [ ]  팀원들과 협의해야 할 State Machine, API, AI Schema, DB·Seed 기준이 결정되었다.
- [ ]  결정 결과가 구두 합의가 아니라 계약 파일·문서·Issue 중 하나에 기록되었다.
- [ ]  3주차 P0 범위와 제외 범위가 구분되어 있다.
- [ ]  담당자별 필수 결과물과 완료 기준이 WBS 또는 Issue에 연결되어 있다.
- [ ]  `contracts/state-machine/**`의 상태·이벤트·전이·가드·허용 행동·권한·완료 정책이 작성되었다.
- [ ]  State Machine 계약이 화면설계서의 핵심 흐름과 일치한다.
- [ ]  API·AI·공통 코드에서 위험도와 사용 안내 상태가 같은 값으로 사용된다.
- [ ]  정상·위험·근거 없음·상태 충돌 예시가 존재한다.
- [ ]  데이터 전처리 결과서가 실제 파일·건수·메타데이터를 반영한다.
- [ ]  데이터베이스·저장소 설계 문서가 실제 테이블·저장소·Seed·Vector 경계를 반영한다.
- [ ]  두 산출물에서 템플릿 사용자·임의 테이블·예시 수치가 제거되었다.
- [ ]  산출물 주 작성자와 연계 담당자의 검토가 끝났다.
- [ ]  7월 29일 종료 시점에 팀원이 산출물과 핵심 계약을 검토할 수 있다.

## 5.2 7월 30일~31일 최종 정리 기준

- [ ]  계약 검증 또는 수동 정합성 체크가 수행되었다.
- [ ]  상태·코드·예시 파일의 누락과 참조 오류가 수정되었다.
- [ ]  웹·모바일 Mock이 확정 계약과 크게 어긋나지 않는다.
- [ ]  백엔드와 AI가 같은 요청·응답 Schema를 사용한다.
- [ ]  핵심 PR의 리뷰·병합 순서가 관리되었다.
- [ ]  관할이 아닌 파일의 변경은 주관할 담당자와 협의되었다.
- [ ]  해결되지 않은 장애마다 담당자와 처리 시점이 기록되어 있다.
- [ ]  4주차 진입 조건과 다음 작업이 문서화되어 있다.
- [ ]  추가 업무는 필수 업무와 산출물 검수가 끝난 뒤에만 진행되었다.
- [ ]  WBS, Issue, PR, 문서의 상태가 서로 모순되지 않는다.

## 5.3 PM 역할 수행 시 주의사항

- [ ]  PM이 모든 코드를 직접 수정하는 방식으로 병목을 만들지 않았다.
- [ ]  기술 결정이 개인 선호가 아니라 요구사항·시연 범위·안전성·구현 가능성에 근거한다.
- [ ]  미완료 결과를 발표나 문서에서 완료된 것처럼 표현하지 않는다.
- [ ]  팀원의 작업을 재작성하기 전에 주관할 담당자에게 수정 근거와 기대 결과를 전달한다.
- [ ]  7월 29일 이후 새로운 필수 범위를 무리하게 추가하지 않는다.

---

# 6. 지침서 작성 시 참고 문서

| 문서명 | 주요 참고 내용 | 지침서 반영 위치 |
| --- | --- | --- |
| `(WBS_29기_4팀) 정수기 구독 고객 케어 및 AS 업무 지원 시스템.md` | 3주차 일정, T-001~T-055 작업, 담당자, 선행 관계, 완료 기준 | 2장, 3장, 4장, 5장 |
| `(요구사항정의서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | P0 기능, AI 안전·근거·권한·상태·데이터 요구사항 | 3.2~3.4, 4.3, 5장 |
| `(화면설계서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | 상태·이벤트·완료 정책, 고객·상담사·기사 화면, 필드·행동 연결 | 3.2, 3.3, 3.4 |
| `(기획서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | MVP 범위, 대표 제품·증상, 사용자 흐름, 기술 구조 | 2장, 3.1, 4.1 |
| `(수집데이터보고서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템(1).md` | 공식 문서 범위, 대상 모델, 데이터 출처·전처리·메타데이터 기준 | 3.4, 4.1 |
| `공통 개발 규칙.md` | 저장소·브랜치, Issue·커밋·PR, API 계약, DB·Migration, State Machine, 테스트·완료 기준 | 3.1, 3.5, 3.6 |
| `프로젝트 디렉토리 구조.md` | `contracts`, `scripts`, `tests`, `docs`, `.github`, Backend·AI·Frontend 경계 | 1장, 3장, 4장 |
| `팀원별 관할 영역.md` | 주관할·부관할·공동 편집 권한, 계약·테스트·스크립트 담당 | 1장, 3.3, 3.5 |
| `RAG_기술스택_업무계획서_v1(1).md` | 이동윤의 AI·RAG 3주차 계획, Schema·검색·안전·LangGraph 범위 | 3.3 |
| `최지용_업무계획표_v0.1(1).md` | 백엔드·DB 구조, 인증·문의·State Machine 구현 계획 | 3.2~3.4 |
| `한예나_3주차_업무계획서_역할방향반영(1).md` | 상담사 Web 화면, 목록·상세·상태 행동·Mock API 요구 | 3.3 |
| `업무계획서_애플리케이션(양정현)(1).md` | 모바일 환경, 화면·상태 관리, API·AI DTO 요구 | 3.3 |
| `[데이터 전처리] 데이터 전처리 결과서.docx` | 3주차 데이터 전처리 공식 산출물 양식 | 3.4, 5장 |
| `[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx` | 3주차 DB·저장소 공식 산출물 양식 | 3.4, 5장 |
| `SK네트웍스 Family AI 캠프 29기_최종 프로젝트 오프닝 자료.pdf` | 프로젝트 일정과 주차별 제출 산출물 | 문서 전체 일정 기준 |

> 윤승혁의 별도 개인 업무계획서는 제공되지 않았으므로, 본 지침서는 WBS의 PM·기술 통합 담당 항목과 전체 팀원의 업무계획서, 요구사항·화면·디렉터리·관할 문서를 교차 검토하여 작성하였다.
>
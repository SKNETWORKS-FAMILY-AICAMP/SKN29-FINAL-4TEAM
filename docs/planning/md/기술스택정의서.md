# 프로젝트 기술스택 선정안 v0.8

## 1. 문서 개요

| 항목 | 내용 |
|---|---|
| 프로젝트 | 정수기 구독 고객 케어 및 A/S 업무 지원 시스템 |
| 버전 | v0.8 |
| 기준일 | 2026-07-24 |
| 상위 기준 | 팀 WBS, 공통 개발 규칙 |
| 적용 원칙 | 상위 기준과 기술스택 선정안이 충돌하면 기술스택 선정안을 수정한다. |
| 미정 사항 | 공통 개발 규칙에서 보류·미정·충돌로 남긴 항목은 팀 승인 전 임의 확정하지 않는다. |
| 대상 독자 | 개발팀, PM, QA, 외부 검토자 |

이 문서는 기술 이름만 나열하는 목록이 아니다. 사용자 채널, WBS 담당 역할, API·DB·AI 경계, 협업 방식, 보안·테스트·배포 기준과 완료 증거를 한 문서에서 확인할 수 있도록 정리한 실행 기준이다.

## 2. 우선 적용 기준

WBS와 공통 개발 규칙에 따라 다음 항목을 적용하며, 세부 정책은 팀 결정 목록으로 분리한다.

| 항목 | 적용 결과 | 남은 결정 |
|---|---|---|
| 인증 | `JWT + RBAC`를 필수 기준으로 적용 | 만료·폐기·rotation·revocation, 채널별 안전 저장 방식 |
| 배포 | `Kubernetes + GitHub Actions + Docker image`를 필수 기준으로 적용 | 백업 주기·대상·위치·보존 기간·복구 목표 |
| RAG 검색 | `PostgreSQL FTS + GIN`과 `pgvector`를 함께 사용하는 하이브리드 검색 적용 | 임베딩 모델·차원·거리 함수·재색인 조건 |
| API 문서 | 사람이 읽는 공식 계약은 Markdown, 기계 계약과 타입 생성은 OpenAPI로 구분 | 날짜·시간의 시간대 |
| WBS 연계 | WBS 수정을 요구하지 않고 기술·산출물·검증 순서에서 대응 | 선행 작업이 겹치는 항목의 실행 증거 관리 |

## 3. 사용자 채널과 화면 기술

| 사용자 | 전용 채널 | 화면 기술 기준 | 주담당 | WBS |
|---|---|---|---|---|
| 정수기 이용 고객 | 스마트폰 모바일 전용 | Android Native + Kotlin + Jetpack Compose 담당자안 | 양정현 | T-033~T-037 |
| 상담원 | Web 전용 | React + TypeScript + Vite | 한예나 | T-038~T-041 |
| 방문기사 | 태블릿 모바일 전용 | Android Native 또는 태블릿 Web 중 팀 결정 | 양정현 | T-042~T-043 |
| 운영직원(SUPERVISOR) | Web 전용 | React + TypeScript + Vite, P1 운영 화면 | 한예나 | T-101~T-104 |

고객과 방문기사 채널을 Web으로 임의 변경하지 않는다. 상담원·운영직원 Web과 모바일 채널은 코드를 억지로 공유하지 않고 다음 계약을 공통으로 사용한다.

- REST `/api/v1` 계약
- JWT 인증과 역할 기반 권한
- `allowed_actions`, `state_version`, `idempotency_key`
- 상태·오류·로딩·빈 화면의 의미
- 공통 `EvidenceCardDTO`
- 디자인 의미, 접근성, 오류 문구와 완료 정책

## 4. 전체 시스템 기술 구조

```text
고객 Android 앱 ─┐
상담원 Web ──────┼─> Public API/BFF ─> Django/DRF 업무 백엔드 ─> PostgreSQL
기사 태블릿 ─────┤                          │                         ├─ FTS + GIN
운영직원 Web ────┘                          │                         └─ pgvector
                                             │
                                             └─> FastAPI/Pydantic AI·RAG API
                                                        │
                                                        └─> 공식 문서·Evidence·안전 fallback
```

핵심 책임은 다음처럼 분리한다.

- Django/DRF: 인증·권한, 업무 CRUD, State Machine, 이력, Evidence 조립, 통합 API
- FastAPI/Pydantic: AI 입력·출력 검증, 증상 구조화, 검색·안내·fallback
- PostgreSQL: 업무 데이터, 상태 이력, 문서 메타데이터, 키워드·벡터 검색
- React/Vite/TypeScript: 상담원·운영직원 Web
- Android/Kotlin/Compose: 고객 스마트폰 앱 담당자안
- Node.js: Web 프론트엔드 빌드·개발·테스트 런타임
- Kubernetes/GitHub Actions: 통합 배포, 승인, 롤백과 배포 후 검증

AI와 프론트엔드는 업무 상태를 직접 변경하지 않는다. 모든 상태 전이는 Django 업무 백엔드가 역할·현재 상태·버전·멱등성 키를 검증한 뒤 수행한다.

## 5. 핵심 기술 선정

### 5.1 필수 기술

| 영역 | 기술 | 적용 목적 | 주담당 | 연계 WBS |
|---|---|---|---|---|
| 업무 백엔드 | Python + Django + Django REST Framework | 업무 모델, 인증·RBAC, State Machine, CRUD, Evidence 조립 | 최지용 | T-005·T-016~T-024·T-028B·T-044·T-046·T-047·T-055·T-106 |
| AI·RAG API | Python + FastAPI + Pydantic + Uvicorn | 구조화 출력 검증, 검색·안내·fallback API | 이동윤 | T-006·T-025~T-032·T-046·T-051 |
| Web 런타임 | Node.js LTS + TypeScript | Web 개발·빌드·테스트와 정적 타입 | 한예나 | T-038~T-045·T-046·T-101~T-104 |
| Web UI | React + Vite | 상담원·운영직원 Web | 한예나 | T-038~T-041·T-045·T-101~T-104 |
| 관계형 DB | PostgreSQL | 업무 데이터, 상태 이력, 문서 메타데이터 | 최지용 | T-005·T-016~T-024·T-044·T-047 |
| 키워드 검색 | PostgreSQL FTS + GIN | 공식 문서 키워드 검색과 필터 | 이동윤 | T-010~T-012·T-028A·T-031 |
| 벡터 검색 | pgvector | 문서 청크 임베딩 검색 | 이동윤 | T-011·T-012·T-028A·T-031 |
| 인증·권한 | JWT + RBAC | 4개 역할의 인증과 데이터 접근 제한 | 최지용 | T-017·T-033~T-043·T-046·T-051 |
| API 문서 | Markdown API 명세 | 사람이 읽는 공식 요청·응답 계약 | 최지용 | T-016~T-024·T-046·T-047·T-050 |
| API 자동화 | drf-spectacular + FastAPI OpenAPI | 기계 계약, 타입 생성, contract test | 최지용·이동윤 | T-006·T-016~T-024·T-046·T-050 |
| 로컬 통합 | Docker Compose | 팀 공통 로컬·통합 실행과 Smoke Test | 김은진 | T-016·T-046·T-051·T-053 |
| 배포·CI/CD | Kubernetes + GitHub Actions + Docker image | 테스트·빌드·배포·롤백 자동화 | 김은진 | T-046·T-051·T-053·T-054·T-107 |
| 로그·추적 | 구조화 JSON 파일 로그 + `correlation_id` | 프론트·백엔드·AI 흐름 추적 | 김은진·최지용 | T-024·T-046·T-051·T-053 |

### 5.2 개발·검증 기술

| 영역 | 기술 | 적용 기준 |
|---|---|---|
| DB 연결 | psycopg 3 | Django가 쓰기 스키마를 소유하고 FastAPI 직접 접근은 승인된 경계로 제한 |
| Web 데이터·라우팅 | TanStack Query + React Router | 서버 상태와 역할별 Web 경로 관리 |
| Web 입력 | React Hook Form + Zod | 화면 입력 검증과 서버 오류 매핑 |
| Web 타입 | openapi-typescript 계열 | 승인된 OpenAPI에서 생성하며 생성 위치·명령·diff 기준을 고정 |
| 백엔드 테스트 | pytest + pytest-django + HTTPX | State Machine, API, DB, AI 계약·통합 검증 |
| Web 테스트 | Vitest + React Testing Library + Playwright | 컴포넌트·사용자 행동·브라우저 E2E |
| 표 데이터 수집 | pandas + openpyxl | CSV·XLSX 정제와 적재 보고서 |
| PDF 수집 | PyMuPDF | 페이지 번호를 보존한 매뉴얼 추출 |
| HTML 수집 | HTTPX + BeautifulSoup4 | 공식 FAQ·제품 페이지 수집 |
| 수집 검증 | Pydantic + SHA-256 + Django management command | 메타데이터 검증, 변경 감지, Upsert 적재 |

### 5.3 조건부 기술

| 영역 | 기술 | 도입 조건 |
|---|---|---|
| 비동기 작업 | Celery + Redis | 동기 처리 지연·오류·재시도 요구가 실측된 경우 |
| 내부 원본 저장소 | S3/MinIO | 원문 보존·권한·URI/hash·백업·복구 정책 승인 후 |
| 운영 게이트웨이 | Nginx + Gunicorn/Uvicorn workers | Kubernetes Ingress·서비스 책임과 중복되지 않도록 배포 ADR 승인 후 |
| 실시간 알림 | SSE 또는 WebSocket | 폴링 대비 UX·부하 개선 효과를 확인한 경우 |
| 고객 Android 연계 | Retrofit·OkHttp, Kotlinx Serialization, Hilt, Room | Public API·JWT·오프라인·동기화·민감정보 저장 범위 승인 후 |

### 5.4 제외 기술

| 제외 대상 | 이유 | 재검토 조건 |
|---|---|---|
| Express/NestJS 업무 백엔드 | Django와 FastAPI 책임 중복 | 전체 아키텍처 변경 승인 |
| Prisma/TypeORM/Sequelize/SQLAlchemy ORM/Alembic | Django ORM·Migration 단일 소유권과 충돌 | DB 소유권 ADR 승인 |
| GraphQL/gRPC/Kafka | MVP 범위 대비 운영 복잡도 증가 | REST로 충족되지 않는 기능·성능 증거 |
| MongoDB/Elasticsearch/별도 Vector DB | PostgreSQL·FTS/GIN·pgvector로 현재 범위 충족 | 실측 성능·기능 한계와 ADR |
| XState의 업무 상태 권위 | State Machine은 백엔드가 담당 | 업무 상태와 무관한 화면 표현에 한해 별도 검토 |
| Next.js·Redux·Tailwind CSS | 현재 Web 범위와 기존 React/Vite/CSS 구성에서 우선 필요하지 않음 | 팀 승인과 명확한 도입 효과 |

## 6. API·DB·상태 계약

### 6.1 API 공통 형식

- 방식: REST API
- 버전 경로: `/api/v1`
- 정상·오류 Wrapper: `success`, `data`, `error`
- 오류 상세: `code`, `message`, `details`
- 날짜·시간: `YYYY-MM-DD HH:mm:ss`
- 값 없음: `null`
- 목록: `page`, `size`, `total`
- 문서: Markdown 공식 명세와 OpenAPI를 같은 PR에서 함께 갱신
- 추적: 모든 채널에 `correlation_id` 전달

시간대는 아직 정해지지 않았으므로 임의로 UTC 또는 KST로 확정하지 않는다.

### 6.2 DB 공통 기준

- 스키마 변경은 Django Migration 파일로만 수행한다.
- 주요 테이블에 `created_at`, `updated_at`을 적용한다.
- 삭제는 `deleted_at` 등을 이용한 논리 삭제를 사용한다.
- 기본키는 도메인형 문자열 ID를 사용한다.
- 합성 데이터 초기화는 Upsert 방식으로 반복 실행에 안전하게 만든다.
- 직접 수동 INSERT로 공통 개발 데이터를 관리하지 않는다.

도메인형 ID 생성 규칙, Enum 관리 방식, Seed 저장 형식과 시간대는 팀 결정 전 확정하지 않는다.

### 6.3 State Machine

- 문의 상태와 방문 상태를 분리한다.
- 이벤트 기반으로 상태를 전이한다.
- 백엔드는 역할과 현재 상태에 맞는 `allowed_actions`를 반환한다.
- 동시 수정은 `state_version`으로 제어한다.
- 중복 요청은 `idempotency_key`로 제어한다.
- 이전·다음 상태, 변경자, 시각과 사유를 이력으로 저장한다.
- 상담·방문 경로의 완료는 `COMPLETION_PENDING`을 거쳐 확정한다.
- 잘못된 전이는 `INVALID_STATE_TRANSITION`과 같은 업무 오류로 반환한다.

## 7. AI·RAG 적용 기준

### 7.1 AI 출력과 프롬프트

- AI는 JSON과 사용자용 문장을 함께 반환한다.
- Pydantic 또는 JSON Schema로 필수 필드와 Enum을 포함한 전체 출력을 검증한다.
- 잘못된 출력은 재생성하고 계속 실패하면 상담으로 전환한다.
- 프롬프트는 별도 텍스트·YAML 파일로 관리하고 버전과 변경 이력을 저장한다.
- 고객·상담원·방문기사 역할별 프롬프트를 분리한다.
- 위험 규칙과 상태 전이는 AI가 아니라 코드가 처리한다.
- 입력·모델·schema 결과·프롬프트 버전을 저장한다.

작업별 AI 모델 매핑은 팀 결정 전 임의 확정하지 않는다.

### 7.2 하이브리드 검색과 근거

- 키워드 검색은 PostgreSQL FTS + GIN을 사용한다.
- 벡터 검색은 pgvector를 사용한다.
- 제품 모델·세대·문서 버전을 검색 전에 필터링한다.
- 검색 결과를 반환하기 전에 적용성·공식성·버전을 다시 검증한다.
- 근거가 없으면 답변을 보류하고 상담으로 전환한다.
- 모든 채널에서 공통 `EvidenceCardDTO`를 사용한다.
- 화면에는 문서명·버전·페이지·요약과 공식 랜딩 페이지 링크를 제공한다.
- 내부 파일 경로, 원문 전체와 고객 화면의 내부 청크 식별자는 노출하지 않는다.
- MVP 데이터와 확장 데이터를 물리적으로 분리한다.
- 문서 변경은 해시와 버전으로 감지한다.

보조 문서의 구체 사용 조건과 임베딩 모델·차원·거리 함수는 팀 승인 후 확정한다.

## 8. WBS 역할 분담

| 담당 역할 | 담당자 | 주요 책임 | 주요 WBS |
|---|---|---|---|
| PM·기술 통합 | 윤승혁 | 범위·우선순위·아키텍처·최종 통합 승인 | T-001~T-004·T-052·T-054·T-107 |
| 모바일 앱 개발 | 양정현 | 고객 스마트폰 앱, 방문기사 태블릿 화면 | T-033~T-037·T-042·T-043 |
| 웹 프론트엔드 | 한예나 | 상담원·운영직원 Web, 공통 Web UI | T-038~T-041·T-045·T-101~T-104 |
| 백엔드·데이터베이스 | 최지용 | ERD, Django API, 권한·상태, 통합·시험 | T-005·T-016~T-024·T-028B·T-044·T-046·T-047·T-055·T-106 |
| AI·RAG | 이동윤 | AI schema, 검색, 위험·근거·fallback | T-006·T-011·T-015·T-025~T-032·T-049·T-105 |
| 데이터·QA·DevOps | 김은진 | 공식 문서·합성 데이터, QA·CI, 배포·복구 | T-007~T-014·T-048·T-050·T-051·T-053 |

최지용의 정리 역할은 다른 담당자의 기술을 대신 결정하는 역할이 아니다. 각 OWNER가 자기 영역의 기술·계약·시험 범위를 검수하고, 최지용은 Django 업무 백엔드·DB·Public API·상태 계약을 중심으로 통합본을 유지한다.

## 9. 고정 WBS 실행 대응

WBS는 수정하지 않는다. 일정과 선행 관계에서 주의가 필요한 부분은 기술선정안의 실행·증빙 방식으로 보완한다.

| 연계 | 실행 대응 |
|---|---|
| T-004 아키텍처 완료 | 구성도·모듈 책임·주요 API 목록의 완료로 해석한다. 개별 기술의 구현·시험 완료로 보지 않는다. |
| T-011 → T-012 | T-012는 정답 구간과 평가 fixture를 먼저 준비할 수 있다. 최종 검색 품질 판정은 T-011 실제 검색 결과가 나온 뒤 수행한다. |
| T-013 → T-014 | T-014에 사용한 합성 데이터 버전·hash를 고정하고, T-013 잔여 범위를 완료한 뒤 전체 재현성을 다시 검증한다. |
| T-049~T-051 → T-048 | T-048 일정에는 시험 계획·보고서 템플릿을 준비하고, 실제 시험 결과와 미해결 이슈는 T-054 최종 검수 전 반영한다. |
| T-017 인증·RBAC | JWT를 필수 적용하고, 만료·폐기·저장 정책은 보안 ADR에서 결정한다. |
| T-053 배포 | Docker Compose는 로컬·통합용, Kubernetes와 GitHub Actions는 배포용으로 구분한다. |
| T-046 통합 | 고객→상담원→방문기사→고객 후속 확인 전 과정이 승인된 API·상태·Evidence 계약을 사용한다. |

## 10. 저장소·협업 기준

- 단일 Monorepo를 사용한다.
- 최상위는 `frontend/`, `backend/`, `ai/`, `data/`로 분리한다.
- 각 영역 내부에 필요한 `common/`과 별도 `tests/`를 둔다.
- 백엔드는 Controller–Service–Repository 구조를 적용한다.
- 프론트엔드는 기능 중심 구조를 적용한다.
- AI는 프롬프트·검색·생성·검증 모듈을 분리한다.
- `main`에서 기능 브랜치를 만들고 PR로 병합한다.
- `main` 직접 Push를 금지한다.
- Issue는 기능·버그 단위로 만들고 요구사항 ID를 연결한다.
- PR은 하루 작업 단위로 작성하며 1명 승인 후 작성자 이외의 리뷰어가 병합한다.
- PM만 병합하는 기준과 리뷰어 병합 기준의 관계는 팀 확인 전 임의 해석하지 않는다.
- Formatter를 사용한다.
- 클래스·컴포넌트는 `PascalCase`, 상수는 `UPPER_SNAKE_CASE`, 파일은 `snake_case`를 사용한다.
- 변수·함수 이름 규칙과 기존 비표준 파일명의 전환 방식은 팀 결정이 필요하다.

## 11. 보안·로그·테스트·배포

### 11.1 보안과 환경 변수

- 필요한 키 이름만 포함한 `.env.example`을 제공한다.
- 실제 비밀값은 Git·로그·화면·오류 응답에 남기지 않는다.
- 배포 비밀값은 AWS Secrets Manager 등 승인된 비밀 저장소를 사용한다.
- 백엔드는 모든 요청에서 역할과 데이터 범위를 검증한다.
- CORS는 개발·배포 주소만 허용한다.
- 실제 개인정보 대신 가명·합성 데이터만 사용한다.
- 비밀값 유출 시 즉시 폐기·재발급하고 이력을 확인한다.

### 11.2 로그와 장애 처리

- 구조화 JSON 파일 로그를 사용한다.
- 로그 수준은 `DEBUG`, `INFO`, `WARN`, `ERROR`로 구분한다.
- 사용자용 문구와 내부 상세 로그를 분리한다.
- 민감정보를 제외한 메타데이터와 요약만 저장한다.
- `correlation_id`로 프론트·백엔드·AI 흐름을 연결한다.
- 장애 시 입력을 보존하고 재시도한 뒤 계속 실패하면 상담으로 전환한다.

### 11.3 테스트와 완료 기준

- 단위 테스트는 State Machine·위험 규칙·날짜 계산 등 핵심 비즈니스 로직에 집중한다.
- 통합 테스트는 API·DB·AI/RAG까지 검증한다.
- E2E는 정상·위험·근거 없음 시나리오를 검증한다.
- AI는 자동 검사와 사람 평가를 병행한다.
- 핵심 테스트 실패 시 병합하지 않는다.
- 구현·테스트·리뷰와 결과 파일·리포트가 모두 있어야 완료로 인정한다.

### 11.4 배포와 버전

- Kubernetes와 GitHub Actions CI/CD를 사용한다.
- 개발 서버 하나에 배포한다.
- Semantic Versioning과 중간·최종 Git 태그를 사용한다.
- 테스트 통과 후 PM·DevOps가 배포를 승인한다.
- DB Migration은 애플리케이션 시작 시 자동 실행한다.
- 문제 발생 시 이전 Docker image와 Git tag로 롤백한다.
- 배포 후 대표 E2E 시나리오를 실행한다.
- 코드 태그, 환경 설정, DB Seed와 배포 문서를 최종 산출물로 보존한다.

## 12. 팀 결정이 필요한 항목

다음 항목은 임의로 확정하지 않는다.

1. 커밋 메시지의 정확한 형식
2. PM만 병합하는 기준과 리뷰어 병합 기준의 관계
3. 변수·함수 네이밍과 기존 비표준 파일명 전환 방식
4. 날짜·시간의 시간대
5. 도메인형 문자열 ID 생성 규칙
6. Enum 관리 방식과 Seed 저장 형식
7. JWT 만료·폐기·rotation·revocation과 채널별 안전 저장
8. RAG 보조 문서의 구체 사용 조건
9. 작업별 AI 모델 매핑
10. 임베딩 모델·차원·거리 함수·재색인 조건
11. 백업 주기·대상·저장 위치·보존 기간·복구 목표
12. 방문기사 태블릿의 Android Native/Web 최종 선택
13. 고객 Android의 Gradle·JDK·API level과 배포 방식
14. PostgreSQL과 주요 런타임의 정확한 버전

## 13. 완료 증거

| 영역 | 필수 증거 |
|---|---|
| 결정 | 팀 승인 기록과 ADR |
| API | Markdown 명세, versioned OpenAPI, 정상·오류 예제, contract test |
| DB | ERD, Migration, schema diff, 논리 삭제·시각·Upsert 검증 |
| 백엔드 | 실행 가능한 서버, RBAC·State·멱등성·동시성 테스트 |
| AI·RAG | Pydantic schema, 역할별 예제, prompt 이력, 검색 평가, no-evidence test |
| Web | 빌드·typecheck, route map, 컴포넌트·브라우저 E2E |
| 모바일 | 플랫폼 ADR, 빌드·실단말, contract·UI·E2E |
| 보안 | `.env.example`, secret scan, RBAC·401·logout·CORS·마스킹 검증 |
| 배포 | CI/CD 기록, Git tag, image digest, Migration·restore·rollback, 배포 후 E2E |

이 증거가 준비되지 않은 기술이나 기능은 WBS 문서의 일정이 도래했거나 관련 파일이 존재한다는 이유만으로 완료 처리하지 않는다.

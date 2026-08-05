# 4주차 Web 실제 API 구현 준비표

기준일: 2026-08-04
현재 상태: `REVIEWED / IMPLEMENTATION_HOLD`

## 한 줄 결론

Web은 목록 → 상세 → 상담 → 방문 순서로 실제 API를 연결할 준비가 되어 있다. 다만 최신 `origin/main`과 `origin/jiyong`의 `consultations.yaml`, `visits.yaml`이 여전히 비어 있고 PM `FINAL_APPROVED`가 없으므로 이 문서는 구현 계획이지 Active 계약이 아니다.

## 승인 Gate

아래 네 조건이 모두 충족된 뒤에만 실제 API 코드를 작성한다.

1. PM이 대상 DEC를 `FINAL_APPROVED`로 기록한다.
2. Active OpenAPI에 URL·Method·Request·Response·Error Schema가 반영된다.
3. Backend Runtime과 Demo DB·계정·대표 문의가 준비된다.
4. QA가 실제/Mock 검증 기준과 증거 위치를 확인한다.

## 단계별 연결 순서

| 단계 | 범위 | 현재 상태 | 승인 후 Web 완료 증거 |
| --- | --- | --- | --- |
| 1 | 상담사 문의 목록 | `BACKEND_BLOCKED` | 실제 Network 응답, 목록 표시, Loading·Empty·오류 캡처 |
| 2 | 상담사 문의 상세 | `BACKEND_BLOCKED` | 실제 상세 응답, Section별 표시·부분 실패 기록 |
| 3 | 상담 4 Action | 계약형 Mock만 존재 | 실제 DB 저장, 성공 Snapshot, 저장 후 상세 재조회 |
| 4 | 방문 Action | Mock만 존재 | Visit 생성·일정·확정 저장과 최신 Snapshot |
| 5 | 409·오류 복구 | 상담 Mock 검증 | 실제 Error Code별 입력 보존·재조회·수동 재시도 |

한 단계가 실패해도 전체 화면을 자동으로 Mock으로 전환하지 않는다. 실패한 단계는 실제 오류로 표시하고 Mock은 환경변수로 명시적으로 선택한 시연·테스트에서만 사용한다.

## 화면–API 필드 매핑

아래 Endpoint와 필드는 Backend 제안 상태이며 Active OpenAPI 확정 전에는 코드에 고정하지 않는다.

### 1. 상담사 문의 목록

제안 Endpoint: `GET /api/v1/inquiries`

| Backend 제안 | Web 사용 위치 | 변환 원칙 |
| --- | --- | --- |
| `q` | 검색어 | URL 검색 조건과 동기화 |
| `status` | 상태 필터·탭 | 소문자 Enum을 View Model Enum으로 Mapper에서 변환 |
| `risk_level` | 위험도 필터·Badge | Web에서 재계산하지 않음 |
| `priority` | 우선순위 필터·Badge | Web에서 재계산하지 않음 |
| `from`, `to`, `sort` | 기간·정렬 | Backend가 지원하는 값만 노출 |
| `page`, `size` | 페이지 | Pagination 응답과 함께 사용 |
| `status_counts` | 탭별 건수 | 화면에서 전체 배열을 다시 집계하지 않음 |
| `current_assignee` | 담당자 | Backend Projection을 그대로 표시 |
| `waiting_seconds` | 대기 시간 | 제공될 때만 대기 시간으로 표시 |
| `state_version` | 후속 Action 기준 | 목록에서 계산·증가하지 않음 |
| `allowed_actions` | 버튼·진입 가능 여부 | Backend 객체 배열을 공통 Mapper로 변환 |

Web 전용 `bucket`, `consultation`, `mockState`, `mockFailure`는 실제 API Query로 보내지 않는다.

### 2. 상담사 문의 상세

제안 Endpoint: `GET /api/v1/inquiries/{id}`

| Backend 제안 영역 | Web 사용 위치 | 보류·오류 처리 |
| --- | --- | --- |
| 문의·고객·제품 Projection | 상세 Header·기본 정보 | 누락값은 미확인·제공되지 않음으로 표시 |
| 문진·조치·상담 정보 | 답변·요약 영역 | DTO를 Component에 직접 연결하지 않음 |
| AI 원본·수정본·확정본 | 상담 요약 영역 | 세 값을 구분하고 임의 합치지 않음 |
| `evidence_cards` | 공식 근거 독립 Section | DEC-008 확정 전 보류 가능, 기본 상세는 계속 사용 |
| 상태 이력 | 처리 이력 | 부분 실패 시 다른 Section은 유지 |
| `state_version`, `allowed_actions` | Action Panel | Backend Snapshot만 사용 |

### 3. 상담 4 Action

| Web 행동 | Backend 제안 | Web 요청 원칙 |
| --- | --- | --- |
| 상담 시작 | `POST /api/v1/inquiries/{id}/start-consultation` | 최신 `state_version`, 요청 Context 사용 |
| 임시 저장 | `PATCH /api/v1/inquiries/{id}/consultation-draft` | 입력 필드만 전송, 다음 상태를 보내지 않음 |
| 요약 확정 | `POST /api/v1/inquiries/{id}/consultation-summary/confirm` | 저장된 최신 수정본을 1회 확정 |
| 상담 완료 | `POST /api/v1/inquiries/{id}/complete-consultation` | Backend가 반환한 분기와 Action 사용 |

모든 쓰기 요청은 `Authorization`, `Idempotency-Key`, `X-Correlation-ID`와 Body의 최신 `state_version`을 사용한다. 성공 Snapshot 적용 후 상세 GET을 다시 호출한다.

### 4. 방문 Action

| 단계 | Backend 제안 | 화면 표시 |
| --- | --- | --- |
| 방문 검토 | `POST /api/v1/inquiries/{id}/visit-review` | Visit 없음·검토 대기 |
| 방문 필요 | `POST /api/v1/inquiries/{id}/visits` | `visit` 생성, `ASSIGNING` 미배정 가능 |
| 방문 불필요 | `POST /api/v1/inquiries/{id}/visit-not-needed` | 방문 불필요와 완료 대기 구분 |
| 일정 저장 | `PATCH /api/v1/visits/{visit_id}/schedule` | `preferred_date`·`confirmed_date`, 기사 상태 표시 |
| 방문 확정 | `POST /api/v1/visits/{visit_id}/confirm` | `CONFIRMED`, 기사와 확정일 필수 |

공통 응답의 `visit` Key는 항상 존재하는 required·nullable 필드여야 한다. `visit: null`은 Visit 미생성, Key 누락은 계약 불일치로 처리한다.

## 승인 후 파일별 작업 순서

| 순서 | 파일·폴더 | 작업 |
| --- | --- | --- |
| 1 | `src/features/consultation/api/` | Active DTO와 목록·상세·상담 Action Client 추가 |
| 2 | `src/features/consultation/mappers/` | `snake_case` DTO를 기존 View Model로 변환 |
| 3 | `src/features/consultation/repositories/` | Mock·Remote Repository 구현 분리와 Provider 선택 |
| 4 | `src/pages/consultant/ConsultantDashboardPage.tsx` | 실제 Loading·Empty·오류·Pagination 연결 |
| 5 | `src/pages/consultant/InquiryDetailPage.tsx` | 실제 상세·부분 실패·재조회 연결 |
| 6 | `src/features/consultation/hooks/useSaveConsultation.ts` | Mock API를 실제 Action Client로 교체 가능한 경계 추가 |
| 7 | `src/features/visit-transition/` | 방문 DTO·Mapper·Action Client·날짜/기사 상태 연결 |
| 8 | `src/features/auth/`, `src/app/providers/` | 최종 401 사유와 15분 메모리 Draft 복구 추가 |
| 9 | `tests/unit`, `tests/integration` | Mapper·Repository·Action·409·401 계약 테스트 추가 |

## 하지 않을 일

- 승인 전 Endpoint·Enum·Payload를 추측해 코드에 추가하지 않는다.
- Backend 계약과 State Machine 파일을 Web 담당자가 임의 수정하지 않는다.
- 실제 API 실패를 성공한 Mock 화면으로 숨기지 않는다.
- 상태·위험도·우선순위·담당자·허용 행동을 Web에서 계산하지 않는다.
- 운영 대시보드 P1 확장을 상담사 P0보다 먼저 진행하지 않는다.

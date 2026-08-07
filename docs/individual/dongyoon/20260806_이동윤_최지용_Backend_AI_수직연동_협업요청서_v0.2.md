# 이동윤 → 최지용 Backend↔AI 수직 연동 협업요청서 v0.2

> 요청 ID: `AI-BE-HANDOFF-20260804-P0`
>
> 요청자: 이동윤 — AI·RAG
>
> 수신자: 최지용 — Backend·Database
>
> 관련 작업: `T-022 Slice B`, `T-025`, `T-032`
>
> 작성일: 2026-08-06
>
> 우선순위: `P0`
>
> 상태: `READY_TO_SEND` — 문서 작성 완료, Backend 회신·공동 E2E 전

## 1. 요청 요약

현재 FastAPI AI 계약과 독립 Runtime은 준비됐지만
`backend/integrations/ai/`의 Client·Mapper·Validator·Retry Policy는 빈
골격이다. 고객 증상 제출 후 Django가 실제 AI API를 호출하고, 계약 검증을
거친 결과를 Backend DB에 저장하는 최소 수직 흐름을 공동 구현·검증해 달라.

이번 요청의 목표 흐름은 다음과 같다.

```text
SUBMIT_SYMPTOM 입력·필수 Context 저장
→ Backend AI Run 생성·요청 Mapper
→ POST FastAPI /api/v1/ai/analyze?mode=local
→ AI 계약 응답 검증
→ AI Run·구조화 증상·안내·검색 실행 결과 저장
→ Backend가 최신 state_version 재검증
→ Backend State Machine Event·공개 DTO 결정
```

AI는 Inquiry 상태·객체 권한·최종 EvidenceCard·DB Transaction을 직접 변경하지
않는다. 해당 책임은 Backend에 있다.

이 요청서는 Backend↔AI 실행 연동용이다. 공개 EvidenceCard 규격인
`DEC-WEB-BE-008` 수정 제안의 최종 승인과는 별도이며, 해당 구현 Gate는 계속
`HOLD`다.

## 2. AI 측 현재 제공 상태

| 항목 | 현재 값 | 판정 |
| --- | --- | --- |
| AI Endpoint | `POST /api/v1/ai/analyze?mode=mock\|local` | 준비 |
| AI Base URL | 기본 `http://127.0.0.1:8001` | 환경변수화 필요 |
| 계약 | `contracts/ai/**`, Version `1.1.0` | 준비 |
| Python | `3.13.13`, `ai/.venv` | 검증 |
| 단위 테스트 | `96 passed, 3 warnings` | PASS |
| 전체 AI Timeout | 30초 | Runtime 적용 |
| AI 내부 재시도 | 일시적 검색 오류 최대 1회, Backoff 0.5초 | Runtime 적용 |
| Backend 자동 재시도 | 0회 | 협업 정책 |
| 검색 결과 구분 | 근거 있음·정상 0건·설정 오류·실행 실패·Timeout | 적용 |
| 위험 우선 | 위험 입력은 Vector 검색 없이도 안전 안내 가능 | 적용 |
| 실제 pgvector | 개인 격리 DB 12/12 PASS | 팀 DB 완료 증거 아님 |
| 개인 격리 응답속도 | Warm 전체 p95 `270.4 ms` | 팀 DB·HTTP SLA 아님 |
| 공식 기준선 | `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT` | 확정본 아님 |
| 팀 DB·Backend E2E | 미수행 | 공동 작업 필요 |

AI 재시도 구현 Commit은 `090ca03`이다. 이 문서 작성 시점의 `dongyoon`
Branch HEAD는 `0baac6911ffd373bcdece8d2b6a88caf1dc0900a`이지만 작업 트리가
Dirty이므로 최종 연동 기준 SHA로 고정하지 않는다. 저장소 기준으로 실행할
때는 Commit 후 40자리 SHA와 Dirty 여부를 공동 E2E 증거에 다시 기록해야 한다.
공식 기준선도 팀 DB 재실행과 Commit 반영 전까지 `CANDIDATE`다.

## 3. Backend 구현·확인 요청

### 3.1 실제 HTTP Client와 요청 Mapper

다음 골격 파일을 Backend 관할에서 구현해 달라.

```text
backend/integrations/ai/client.py
backend/integrations/ai/request_mapper.py
backend/integrations/ai/response_mapper.py
backend/integrations/ai/schema_validator.py
backend/integrations/ai/retry_policy.py
```

필수 요청 규칙:

1. 고객 원문과 필수 Context가 DB에 보존된 뒤 AI를 호출한다.
2. `START_INQUIRY` 직후 임의 호출하지 않는다.
3. 미지원 제품·필수값 누락·정책 차단이면 AI 호출 전에 Backend가 거부한다.
4. 내부 정수 PK 대신 공개 UUID `inquiry_id`를 전달한다.
5. `correlation_id`, `ai_request_id`, 호출 시점 `state_version`을 보존한다.
6. 선택적 `X-Correlation-ID` Header는 Body `correlation_id`와 같게 보낸다.
7. `AI_SERVICE_BASE_URL`을 환경변수로 받고 운영 Secret·내부 경로를 기록하지
   않는다.
8. Backend 전체 호출 Timeout은 30초, Backend 자동 재시도는 0회로 적용한다.

요청 필드:

| 필드 | Backend 원천 | 비고 |
| --- | --- | --- |
| `inquiry_id` | Inquiry 공개 UUID | 내부 정수 PK 금지 |
| `correlation_id` | 요청 Middleware·업무 추적값 | Header·Body·로그·DB 일치 |
| `ai_request_id` | Backend 발급 멱등 ID | 동일 논리 요청 재전송 시 재사용 |
| `state_version` | AI 호출 시작 시점 Inquiry 버전 | 응답 수신 후 최신 버전과 재비교 |
| `raw_symptom` | 저장된 고객 증상 원문 | 로그 비노출, 계약 최대 4,000자 |
| `model_code` | 검증된 제품 판매 코드 | MVP `WPUJAC104DWH` |
| `selected_symptoms` | 대표 증상 선택값 | 선택 필드 |
| `previous_answers` | 저장된 추가 문진 답변 | `question_id`, `answer_text` |

### 3.2 응답 Schema 검증과 오류 매핑

성공 응답은
`contracts/ai/responses/SymptomAnalysisResponse.schema.json`, 오류 응답은
`contracts/ai/common/AIErrorResponse.schema.json`으로 검증한다.

Schema 검증 실패 시 부분 데이터나 임의 기본값을 저장하지 않는다. 원시 예외,
Prompt, Stack Trace와 Secret은 공개 응답·구조화 로그에 남기지 않는다.

| AI 결과 | 핵심 값 | Backend 저장 후보 | Backend 처리 요청 |
| --- | --- | --- | --- |
| 근거 있음 | HTTP 200, `SUCCEEDED`, 근거 1건 이상 | `AIRun=SUCCEEDED` | 검증된 결과만 저장 후 상태 Guard 평가 |
| 정상 0건 | HTTP 200, `FALLBACK`, `failure_stage=RETRIEVING` | `AIRun=NO_EVIDENCE` | 장애로 기록하지 않고 상담 전환 후보 |
| 설정 누락 | HTTP 503, `retryable=false`, `retry_count=0` | `AIRun=FAILED` | 운영 설정 오류, 정상 0건과 분리 |
| 일시 오류 소진 | HTTP 503, `retryable=true`, `retry_count=1` | `AIRun=FAILED` | Backend 자동 재시도 없이 후속 정책으로 전달 |
| 비일시적 검색 오류 | HTTP 503, `retryable=false`, `retry_count=0` | `AIRun=FAILED` | 동일 Payload 자동 반복 금지 |
| Timeout | HTTP 504, `AI-TIMEOUT-01` | `AIRun=TIMED_OUT` | 고객 입력 보존·상담 또는 수동 후속 처리 |
| 요청 검증 오류 | HTTP 400/422, `AI-VALIDATION-01` | 호출 전 거부 또는 `FAILED` | Mapper·계약 결함으로 분리 |

위 DB 상태 매핑은 AI의 제안이다. 최지용은 현행 `AIRun` 제약과 Transaction에
맞는 최종 매핑을 확인하고 차이가 있으면 `CHANGE_REQUEST`로 회신해 달라.

### 3.3 결과 저장 경계

현행 Backend Model을 기준으로 다음 저장 위치를 검토해 달라.

| AI 결과 | Backend 후보 Model | 확인 요청 |
| --- | --- | --- |
| 실행·계약·오류·재시도 | `audit.AIRun` | 상태, Schema 검증, `retry_count`, 오류 코드 |
| 검색 실행·필터·0건·장애 | `audit.AIRetrievalRun` | `NO_EVIDENCE`와 `FAILED` 분리 |
| 구조화 증상·위험도 | `inquiries.SymptomAssessment` | AI Run·Inquiry Context FK와 위험 불변식 |
| 사용 안내·상담 필요 | `inquiries.Guidance` 또는 확정된 현행 Model | `usage_guidance_status`, `requires_consultation` |
| 근거 후보 | `evidence.EvidenceLink` | Backend 재검증 후에만 생성 |

필수 원칙:

- Schema 검증 전 결과를 업무 Model에 저장하지 않는다.
- AI 응답의 `state_version`은 상태 전환 결과가 아니라 요청 값의 Echo다.
- 응답 수신 시 현재 Inquiry 버전이 달라졌으면 결과 적용을 중단한다.
- 중복 `ai_request_id`와 동일 Payload는 멱등 재생하고, 다른 Payload는 충돌로
  차단한다.
- AI 내부 `retry_count`를 Backend 자동 호출 횟수로 해석하지 않는다.
- AI가 전달한 EvidenceReference는 후보이며 최종 EvidenceCard가 아니다.

### 3.4 State Machine 연결

AI는 `AI_RESULT` Event를 직접 실행하지 않는다. Backend가 다음을 확인한 뒤
State Machine Event를 실행한다.

1. 응답 Schema PASS
2. `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version` 일치
3. 최신 Inquiry 버전과 호출 시작 버전 일치
4. 위험도·사용 안내 불변식 PASS
5. 근거가 있으면 Backend Evidence 검증 PASS

실제 호출 시점과 Event 이름·Guard는 최지용·윤승혁의 State 계약 판정이
필요하다. AI가 임의로 `AI_GUIDANCE` 또는 상담 상태를 확정하지 않는다.

### 3.5 팀 DB 연결 입력

팀 DB 연동 시 다음 경계를 지켜 달라.

- pgvector Extension·Table·Index는 Backend 정식 Migration으로 준비한다.
- AI 적재 스크립트는 팀 DB에서 DDL을 실행하지 않는다.
- AI에는 최소 권한 DSN을 Secret 경로로 전달하고 문서·Git·로그에 기록하지
  않는다.
- 승인 청크 UPSERT와 평가 재실행은 Migration 확인 뒤 수행한다.
- 개인 격리 DB `watercare_ai_verify` 결과를 팀 DB 완료로 승격하지 않는다.
- 13번째 문서 정책 차단 Case는 김은진의 문서 ID·기대값 승인 후 추가한다.

## 4. 공동 E2E 요청 Case

| ID | Case | 기대 HTTP·AI 결과 | Backend 확인 |
| --- | --- | --- | --- |
| `BE-AI-E2E-01` | 정상 근거 있음 | 200 `SUCCEEDED`, `retry_count=0` | `AIRun=SUCCEEDED`, 근거 실행 저장 |
| `BE-AI-E2E-02` | 정상 검색 0건 | 200 `FALLBACK`, `PENDING_CONSULTATION` | `NO_EVIDENCE`, 장애와 분리 |
| `BE-AI-E2E-03` | 누수·전기 위험 | 200, `danger`, `TOTAL_STOP` | 위험 불변식·상담 필요 저장 |
| `BE-AI-E2E-04` | Vector 설정 누락 | 503, `retryable=false` | 설정 장애, 0건으로 저장 금지 |
| `BE-AI-E2E-05` | 일시적 검색 오류 후 복구 | 200, `retry_count=1` | 최종 성공·실제 재시도 횟수 저장 |
| `BE-AI-E2E-06` | 일시적 검색 오류 2회 | 503, `retryable=true`, `retry_count=1` | `FAILED`, Backend 자동 재시도 없음 |
| `BE-AI-E2E-07` | 비일시적 검색 결과 오류 | 503, `retryable=false`, `retry_count=0` | 동일 요청 자동 반복 금지 |
| `BE-AI-E2E-08` | Pipeline Timeout | 504 `AI-TIMEOUT-01` | `TIMED_OUT`, 입력 보존 |
| `BE-AI-E2E-09` | Header·Body Correlation 불일치 | 400 `AI-VALIDATION-01` | Mapper 결함으로 차단 |
| `BE-AI-E2E-10` | 응답 후 `state_version` 변경 | AI 응답은 정상 | Backend stale 결과 적용 금지 |

Mock 성공과 실제 연동 성공을 구분한다.

- `mode=mock`: Client·Schema·화면 계약 Smoke 용도
- `mode=local`: 실제 FastAPI Pipeline·pgvector 공동 E2E 용도
- 팀 완료 증거: `mode=local`과 팀 DB에서 수행한 결과만 인정

## 5. 공동 완료 기준

- [ ] Django 증상 제출 흐름에서 FastAPI가 실제 호출된다.
- [ ] Backend 요청·AI 성공·AI 오류가 JSON Schema 1.1.0을 통과한다.
- [ ] 내부 PK·Secret·개인정보가 요청 식별자나 로그에 추가 노출되지 않는다.
- [ ] `correlation_id`가 Backend 요청→AI 로그→Backend DB까지 일치한다.
- [ ] `ai_request_id` 중복·Payload 충돌과 stale `state_version`이 차단된다.
- [ ] 정상·위험·0건·503·504가 DB 상태에서 구분된다.
- [ ] `retry_count=1`이 Backend 재요청이 아닌 AI 내부 재시도로 저장된다.
- [ ] 고객 입력은 AI 장애·Timeout에도 Backend DB에 보존된다.
- [ ] AI가 Inquiry 상태와 최종 EvidenceCard를 직접 변경하지 않는다.
- [ ] Mock와 실제 Local·팀 DB 결과가 테스트·문서에서 구분된다.
- [ ] 동일 Branch·Commit·계약 버전·실행 시각·명령·Exit code가 증거에 남는다.

## 6. 담당자별 작업 분리

| 담당자 | 작업 | 반환 증거 |
| --- | --- | --- |
| 이동윤 | AI 실행 기준선 Commit 고정, FastAPI 실행, 계약·오류 설명, E2E AI 로그 제공 | AI Branch·SHA, 96개 단위 테스트, HTTP·로그 결과 |
| 최지용 | Client·Mapper·Validator·저장·멱등·stale Guard 구현 | Backend Branch·SHA, 통합 테스트, DB 저장 결과 |
| 이동윤·최지용 | 실제 HTTP·팀 DB E2E 공동 수행 | 10개 Case 결과, Correlation 추적, 제한사항 |
| 김은진 | 팀 DB Data·13번째 차단 Case·독립 QA | Data 결정, 검색·금지 Hit 검증 |
| 윤승혁 | State Event·완료 Gate·팀 기준선 판정 | 승인·HOLD·변경 요청 기록 |

## 7. 최지용 회신 요청

다음 항목을 `ACCEPT`, `CHANGE_REQUEST`, `BLOCKED` 중 하나로 회신해 달라.

| 확인 항목 | 회신 값 |
| --- | --- |
| AI 호출 시점·동기/비동기 dispatch 방식 |  |
| Client·Mapper·Validator 구현 가능 여부 |  |
| `AIRun`·`AIRetrievalRun`·업무 Model 저장 매핑 |  |
| Backend Timeout 30초·자동 재시도 0회 적용 |  |
| 멱등 `ai_request_id`와 stale `state_version` 처리 |  |
| 팀 DB Migration·최소 권한 DSN 준비 상태 |  |
| 공동 E2E 가능한 Branch·환경·일정 |  |
| 추가 계약 변경 필요 여부 |  |
| 최종 판정 |  |

계약이나 DB 매핑 차이가 있으면 다음 형식으로 반환해 달라.

```text
항목:
현재 경로·필드:
현재 값:
기대 값:
재현 절차:
Backend 제안:
AI 재검토 필요 여부:
```

## 8. 전달 대상 파일

- `contracts/ai/README.md`
- `contracts/ai/requests/SymptomAnalysisRequest.schema.json`
- `contracts/ai/responses/SymptomAnalysisResponse.schema.json`
- `contracts/ai/common/AIErrorResponse.schema.json`
- `contracts/ai/examples/symptom-analysis/`
- `contracts/ai/examples/fallback/`
- `ai/README.md`
- `ai/configs/retry_policy.yaml`
- `ai/app/interfaces/http/routes/analysis_routes.py`
- `ai/evaluation/reports/official_mvp_baseline_20260803.json`
- `ai/evaluation/reports/pgvector_latency_baseline_20260806.json`
- `docs/submission/20260803_AI_RAG_중간발표_기술자료.md`
- `docs/individual/dongyoon/20260804_이동윤_DEC-WEB-BE-008_수정PROPOSED_v0.2.md`

## 9. 최지용에게 보낼 메시지 초안

```text
안녕하세요. T-022 Slice B Backend↔AI 실제 연동 P0 협업을 요청드립니다.

AI 측은 계약 1.1.0, FastAPI /api/v1/ai/analyze, 정상 근거·0건·설정 오류·
검색 실패·Timeout 구분과 검색 일시 오류 내부 최대 1회 재시도까지 구현했고
Python 3.13.13 전체 단위 테스트 96개가 통과했습니다.

개인 격리 pgvector에서는 12/12 PASS와 Warm 검색 전체 p95 270.4 ms를
확인했지만, 이는 팀 DB·HTTP·Backend E2E 완료 증거가 아닙니다.

현재 backend/integrations/ai의 Client·Mapper·Validator·Retry Policy가 빈
골격이라 Django 증상 제출→FastAPI 호출→Schema 검증→AIRun·검색·안내 저장의
실제 수직 흐름과 공동 E2E가 필요합니다.

첨부한 AI-BE-HANDOFF-20260804-P0 문서의 3장 구현 요청, 4장 E2E 10개 Case,
7장 회신 표를 확인해 ACCEPT / CHANGE_REQUEST / BLOCKED로 회신 부탁드립니다.
팀 DB DSN은 문서나 Git이 아닌 별도 Secret 경로로 조율하겠습니다.
```

## 10. 변경 기록

| 버전 | 날짜 | 변경 내용 | 상태 |
| --- | --- | --- | --- |
| v0.1 | 2026-08-04 | Backend↔AI Client·저장·팀 DB·E2E P0 협업 요청 작성 | `READY_TO_SEND` |
| v0.2 | 2026-08-06 | 96개 테스트·현재 기준선 상태·격리 DB 응답속도·최종 SHA 고정 조건 반영 | `READY_TO_SEND` |

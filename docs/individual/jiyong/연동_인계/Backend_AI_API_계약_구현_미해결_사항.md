# Backend·AI API 계약·구현 미해결 사항

- 최초 검토일: 2026-07-27
- 상세 재검수일: 2026-07-30
- 현행화일: 2026-07-31
- Backend·DB·API 책임: 최지용
- AI·RAG·AI Schema 책임: 이동윤
- 교차 영역 최종 결정: 윤승혁(PM)
- 현재 판정: Backend·AI 공동 통합 검증 대기
- 내부 상태 코드: `BACKEND_AI_INTEGRATION_PENDING`

이 문서는 DB 스키마·API 계약(T-005)과 AI 처리 계약(T-006)의 정합성,
확인된 기술 반례와 공동 통합 수락 조건을 정의한다.
담당자별 실행·반환 형식은
[백엔드 팀 검토 및 인계 체크리스트](Backend_팀_검토_인계_체크리스트.md)를
따른다.

AI 보완 구현과 격리 pgvector 검증을 수령했지만, 다음 네 영역은 아직
완료 증거가 부족하다.

1. JSON Schema와 Pydantic의 전체 Parity
2. 운영 구조화 로그와 실행 중 작업의 취소 경계
3. 검색 결과 후검증과 Document·Index·Embedding Revision Assertion
4. 같은 계약 버전의 Backend Adapter·Evidence·공동 E2E

## 1. 책임과 시스템 경계

| 경로·기능 | 주관 역할 | 협업·소비 역할 |
|---|---|---|
| `contracts/codes/**` | Backend·Database | AI·RAG, PM·계약 검토 |
| `contracts/api/**` | Backend·API | Web·Mobile·AI 소비 검토 |
| `contracts/ai/**` | AI·RAG | Backend Adapter 소비 |
| `ai/**` | AI·RAG | Backend Runtime 소비 |
| `backend/integrations/ai/**` | Backend·API | AI 계약 검토 |
| `backend/apps/evidence/**` | Backend·Database | AI Evidence 입력 |
| Data AI/RAG Schema·Catalog | Data·QA | AI·RAG 협업 |
| 상태 계약·통합 결정 | PM·State 계약 | Backend·AI 협업 |

AI는 증상 구조화·질문·안전·검색·생성·검증 결과를 제안한다. 권한,
업무 상태 전환, 최종 EvidenceCard 조립과 DB 저장은 Backend
Service·Guard·Transaction 책임이다.

## 2. 확정된 DB·API 기준

| 항목 | 확정 기준 |
|---|---|
| 사용 안내 DB 필드 | `usage_guidance_status` |
| 사용 안내 코드 | `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION` |
| Legacy 변환 | `USE_ALLOWED` → `NORMAL` |
| Legacy 저장 | `usage_guidance_code` Dual-write 금지 |
| 위험도 | `general`, `caution`, `danger` |
| 문의 식별자 | 외부 Public UUID |
| 추적 | `correlation_id`를 Backend→AI→응답·오류·로그에 보존 |
| 상태 동시성 | 호출 시점 `state_version`과 결과 수신 시점 현재 버전 비교 |
| AI 결과 | 상태를 직접 바꾸지 않는 제안 구조 |

근거:

- [T-005 데이터 설계 기준선](../../../database/t-005/README.md)
- [T-005 물리 계약](../../../database/t-005/t005_physical_contract_v1.3.json)
- [사용 안내 상태 코드](../../../../contracts/codes/usage-guidance-statuses.yaml)
- [위험도 코드](../../../../contracts/codes/risk-levels.yaml)
- [UsageGuidance AI Schema](../../../../contracts/ai/common/UsageGuidance.schema.json)
- [SafetyAssessment AI Schema](../../../../contracts/ai/common/SafetyAssessment.schema.json)
- [SymptomAnalysisResponse AI Schema](../../../../contracts/ai/responses/SymptomAnalysisResponse.schema.json)

`UsageGuidance.guidance_status`, `message`, `next_actions`와 Backend/API의
`usage_guidance_status`, `usage_guidance_message`, `next_action`이
동일 이름일 필요는 없다. 다만 변환 위치·방향·Nullability·오류 처리를
명시한 Adapter 규칙과 왕복 테스트가 필요하다.

## 3. 수령한 AI 보완 구현의 인정 범위

2026-07-30 재검수에서 다음은 구현·문서·격리 결과로 확인했다.

- Public UUID와 요청 배열·문자열의 기본 경계
- AI Runtime Port `8001`
- 내부 Retry 비활성·실제 Retry 0회
- HTTP 30초 Timeout과 DB 연결·SQL Timeout
- 협력적 취소 Token과 취소 후 새 DB Stage 진입 차단
- 검색 전 모델·세대 Allowlist
- DB Query Case와 정책 차단 Case의 분리
- 여러 `page_refs` 보존
- DDL과 UPSERT 분리
- Disposable DB 이름 Guard와 Fixture Transaction Rollback
- Windows CPython 3.10.20 호환
- 격리 pgvector 7행·1024차원·평가 12/12·금지 혼입 0

이 범위는 다시 구현할 필요가 없다. 단, 격리 AI 실증 수령은 팀 DB와
Backend-AI 통합 완료를 뜻하지 않는다.

Python 3.10.20 역사 실측:

```text
ai/**/*.py 구문 검사: 138 files, syntax_errors=0
requirements.lock Pin: 84
Python 3.10 Resolver 결과: 85 packages
pip check: No broken requirements found
AI 전체 테스트: 50 passed, 1 skipped, 3 warnings
```

`1 skipped`는 Live pgvector 환경변수가 없는 경우의 의도적 Skip이었다.
이 수치는 해당 작업본의 역사 증거이므로 현재 완료를 주장하려면 동일
기준선에서 다시 실행한다.

## 4. 계약 Parity 미해결 반례

같은 Payload를 JSON Schema와 Pydantic 양쪽에 넣었을 때 다음 차이가
확인됐다.

| 대상 | 반례 | JSON Schema | Pydantic | 필요한 조치 |
|---|---|---|---|---|
| `MissingField` | 빈 `field_name`·`reason`, `importance="urgent"` | 거부 | 수락 | 길이·Enum 제약 반영 |
| `FollowUpQuestion` | `options` 11개 | 거부 | 수락 | 선택지 최대 10개·항목 길이 반영 |
| `EvidenceReference` | `page_refs=[0]` | 거부 | 수락 | 페이지 최솟값 1 반영 |
| `AIErrorResponse` | 필수 Nullable 필드 4종 생략 | 거부 | 수락 | Key 존재·값만 Null 허용 |
| `ModelMetadata` | 빈 모델·Prompt Version, 음수 Token·Latency | 거부 | 수락 | 문자열·숫자 경계 반영 |
| `ProcessingTrace` | 101자 `error_code` | 거부 | 수락 | 최대 100자 반영 |
| `ValidationResult` | 계약 Schema 존재 | 해당 없음 | Runtime 모델 없음 | Runtime 구현 또는 계약 제거 결정 |

원인:

- `MissingField`, `FollowUpQuestion` Runtime 모델에 계약 길이·Enum·배열
  최대 길이가 없다.
- `EvidenceReference.page_refs`에 페이지 최솟값이 없다.
- Pydantic 오류 모델에서 계약상 필수인 Nullable Key를 생략 가능한
  기본값으로 선언한다.
- `ModelMetadata`, `ProcessingTrace.error_code`의 계약 경계가 Runtime에
  반영되지 않았다.
- `ValidationResult.schema.json`의 대응 Runtime 모델이 없다.

### 완료 조건

- [ ] 위 6개 반례가 Runtime에서도 거부됨
- [ ] `ValidationResult`의 Runtime 모델 구현 또는 계약 제거가 PM 승인됨
- [ ] 모든 공통·요청·응답 Schema에 정상·경계·위반 Payload가 있음
- [ ] 같은 Payload의 JSON Schema·Pydantic 수락/거부 결과가 전부 일치
- [ ] 성공 응답뿐 아니라 오류·근거·Fallback 구조도 양쪽 Validator로 검사

## 5. Port·환경·의존성 재현성

현재 실행 기준은 Backend `8000`, AI `8001`이다. Backend 대체 Port가
AI `8001`을 점유하지 않도록 별도 값으로 정해야 한다.

AI 인계에는 다음 값을 한 묶음으로 제공한다.

```text
ai_branch=<branch>
ai_commit_sha=<40자리 SHA>
main_merge_sha=<40자리 SHA>
python_version=<정확한 버전>
operating_system=<OS와 Architecture>
dependency_manifest=<Lock 경로>
lock_generator=<도구·명령>
start_command=<검증한 상대경로 명령>
test_command=<검증한 상대경로 명령>
health_url=<실제 URL>
analysis_endpoint=<Method·Path>
ai_service_base_url=<Port 포함>
request_schema_version=<버전>
response_schema_version=<버전>
```

역사 Lock에는 `torch`가 요구하는 `setuptools>=77.0.3`가 명시적으로
고정되지 않았고 Hash Pin·플랫폼 Marker도 없다. Windows 개발용 Lock과
Linux/CPU 배포용 Lock의 보증 범위를 구분해야 한다.

### 완료 조건

- [ ] Lock에 누락된 직접·전이 의존성 처리 방식 기록
- [ ] Python·OS·Architecture·Hash 사용 여부 명시
- [ ] 깨끗한 Python 3.10 환경에서 설치·`pip check`·전체 테스트 재현
- [ ] 과거 AI `8000`, 개인 절대경로, `PENDING_COMMIT` 문서 정리
- [ ] 실행 가능한 Container 또는 배포 환경 검증은 배포 Gate로 별도 기록

## 6. Timeout·Retry·구조화 로그

### 6.1 확인된 Timeout 경계

HTTP Timeout에서 취소 Token을 설정하고, Embedding 반환 뒤 Token을
재확인해 새 DB Query와 다음 Stage 진입을 막는 것은 확인했다.

```text
취소 50ms 후:
worker_alive=true
store_calls=0

Embedding 반환 후:
worker_alive=false
exception=PipelineCancelledError
store_calls=0
```

남은 위험:

- 이미 실행 중인 Embedding은 HTTP 504 뒤에도 반환할 때까지 계속 실행
- 취소 뒤 이미 진입한 DB Query는 PostgreSQL Statement Timeout에 의존
- 외부 LLM·Embedding 호출의 실제 Hard Cancel 경계가 불명확
- 동시 Timeout 작업의 자원 상한과 Backpressure 기준이 없음

Hard Timeout·별도 Process·외부 API 취소·DB Cancel을 구현하거나,
협력적 취소의 한계·동시 작업 수·최대 잔존 시간을 수치화해 PM 승인을
받아야 한다.

### 6.2 구조화 로그 반례

```text
기본 effective log level=WARNING
INFO enabled=false
watercare.ai.analysis handler=0
잘못된 UUID 422: 구조화 로그 0건
Header/Body correlation 불일치 400: 구조화 로그 0건
```

성공 경로 테스트는 Logger Level을 강제로 INFO로 바꿔 통과했으므로 운영
Bootstrap의 동작 증거가 아니다. `AI_LOG_LEVEL`을 실제 Logger 초기화에
연결하고, Route 진입 전 Validation 실패에도 안전한 추적 로그를 남긴다.

### 완료 조건

- [ ] 운영 Bootstrap이 `AI_LOG_LEVEL`을 적용
- [ ] 성공은 `started → completed`
- [ ] Route 진입 후 실패는 가능한 경우 `started → failed`
- [ ] Request Validation 전 실패는 `failed` 단일 Event
- [ ] 422, Header/Body 불일치 400, Timeout, 내부 실패를 모두 검증
- [ ] `correlation_id`, `ai_request_id`, `state_version`, Stage,
  `retry_count`, latency, 오류 코드를 보존
- [ ] 원문, Prompt, Secret, Stack Trace, 개인정보는 구조화 로그에서 제외
- [ ] AI 내부 Retry와 Backend Retry가 승인 정책을 초과하지 않음

## 7. 검색 결과 후검증과 Revision

### 7.1 확인된 개선

- Allowlist 밖 모델과 `D` 이외 세대를 Embedding·DB Query 전에 차단
- 실제 DB Query Case 7건과 정책 차단 Case 5건 분리
- PostgreSQL 16.14, pgvector 0.8.6, 7행, 1024차원
- 평가 12/12, Positive Recall@5 1.0
- MRR `0.8857142857142858`
- 금지 근거 혼입 0
- DDL·UPSERT 분리와 Fixture Transaction Rollback

### 7.2 검색 후 반례

`VectorSearchService`는 Store가 반환한 Chunk를 최종 반환 전에 다시
검증하지 않았다. 다음 가짜 Store 결과도 한 건 그대로 통과했다.

```text
model_code=WRONG
product_generation=S
verification_status=unverified
allowed_use=false
returned_count=1
```

실제 SQL의 사전 필터만으로 Adapter 교체·회귀·잘못된 Store 구현을
방어할 수 없다. 검색 전·검색 후에 같은 정책을 적용해야 한다.

또한 평가 스크립트는 기대 Chunk·Document·Page는 확인하지만
`document_version`, `index_version`, `embedding_model_revision`,
`chunk_set_sha256`가 실제 DB 결과와 같은지는 검증하지 않았다.
Index Manifest에 Revision이 존재하는 것과 조회된 Row가 그 Revision으로
생성됐음을 증명하는 것은 다르다.

### 완료 조건

- [ ] Store 반환 뒤 모델 코드·제품 세대·검증 상태·`allowed_use=true` 재검증
- [ ] 잘못된 Store 반환값이 최종 Evidence로 전달되지 않는 Negative Test
- [ ] DB Row 또는 Index Build ID에 Document·Index·Embedding Revision 연결
- [ ] Chunk Set SHA-256과 Build Provenance 저장
- [ ] 평가 결과에 결과별 모델 코드·세대·Revision 기록
- [ ] 평가 설정·Index Manifest·DB 검색 결과의 Revision Assertion

## 8. T-005 DB와 AI Runtime 연결

과거 재검수 당시 T-005 진행률은 중간 Wave 상태였지만, 현재
Model·App Registry·Migration 기술 판정은
[T-005 워터브리지 PostgreSQL 통합 검증 보고서](../데이터베이스/PostgreSQL_통합검증_보고서_20260731.md)의
`32/32`를 우선한다.

정규화된 연결 구조:

```text
knowledge_source_document
→ knowledge_document_page
→ knowledge_document_chunk
→ knowledge_chunk_embedding vector(1024)

knowledge_document_model_scope
knowledge_ingestion_batch
knowledge_data_quality_issue
knowledge_evidence_link

aiops_ai_run
→ aiops_retrieval_run
→ aiops_retrieval_hit
```

격리 AI 실증의 단일 `ai_rag_chunks` 테이블을 팀 DB의 정식 구조로
복사하지 않는다. 현재 Model·Migration을 기준으로 AI 적재·조회 계정의
최소 권한, UPSERT, Provenance, Backup·Rollback 절차를 다시 검증한다.

### Backend Adapter 완료 조건

- [ ] 실제 HTTP Client·Request/Response Mapper 구현
- [ ] JSON Schema Validator와 표준 Exception Mapping
- [ ] 전체 Timeout과 Backend 자동 Retry 정책 적용
- [ ] `inquiry_id`, `correlation_id`, `ai_request_id`,
  `state_version` 보존
- [ ] 늦게 도착한 응답의 현재 상태 버전 재확인
- [ ] 같은 AI 요청 ID와 같은 Payload는 멱등 재생
- [ ] 같은 AI 요청 ID와 다른 Payload는 충돌 차단
- [ ] AI EvidenceReference를 Backend가 검증한 뒤 최종 EvidenceCard 저장
- [ ] 권한·상태·최종 DB 기록은 Backend Service가 수행

## 9. 공동 인수 테스트

같은 Commit과 계약 버전에서 다음을 모두 검증한다.

1. Disposable PostgreSQL 전체 Migration 적용·Rollback·복구
2. 승인 Chunk UPSERT 2회 후 비의도 중복 0
3. Vector Column 1024차원과 pgvector 버전 확인
4. 실제 DB 검색 Case와 정책 차단 Case 분리
5. 잘못된 모델·세대·미검증·사용 금지 근거 혼입 0
6. 정상·위험·근거 없음·Schema 오류·Timeout Backend→AI HTTP E2E
7. Header·Body·Backend 로그·AI 로그·DB 이력의 `correlation_id` 일치
8. 중복 AI 요청 ID와 오래된 `state_version` 차단
9. Timeout 뒤 작업·DB Query의 종료 또는 승인된 위험 범위 확인
10. Prompt·내부 경로·API Key·Token·개인정보 비노출 자동 검사
11. Branch·40자리 SHA·Dirty 여부·명령·시각·Exit code·결과 보존

최종 판정은 다음 조건이 모두 충족될 때만
`BACKEND_AI_INTEGRATION_COMPLETE`로 변경한다.

- AI 계약 Parity 완료
- AI Runtime 로그·Timeout·검색 후검증 완료
- Backend Adapter·Evidence 완료
- 공통 코드 Registry와 PM 결정 반영
- Data·통합·Resilience QA 완료
- 동일 기준선의 공동 E2E 완료

## 10. 담당자별 다음 행동

| 역할(담당자) | 다음 행동 | 완료 증거 |
|---|---|---|
| AI·RAG(이동윤) | Parity·로그·취소·검색 후검증·Revision 보완 | AI Commit, 테스트, HTTP·로그·검색 증거 |
| Backend·Database(최지용) | AI 계약 수령 후 Backend Adapter·Evidence 검증 | Backend Commit, Mapper·오류·멱등·상태 E2E |
| Data·QA(김은진) | 계약·Data·Resilience 통합 QA | QA Commit 또는 결과, 불일치 0 |
| PM·계약(윤승혁) | 공통 코드·잔여 위험·완료 Gate 승인 | Decision 기록과 병합된 `main` SHA |

## 11. 금지사항

- AI 계약 입력 없이 Backend Client·Mapper를 추측 구현하지 않는다.
- AI가 업무 상태·권한·최종 EvidenceCard를 직접 변경하지 않는다.
- 격리 pgvector 실증을 팀 DB·Backend-AI 전체 완료로 표시하지 않는다.
- 테스트 개수만으로 Parity·취소·검색 후검증 완료를 주장하지 않는다.
- Retry 증가로 전체 Timeout을 우회하지 않는다.
- 내부 Source Path·Prompt·Secret·개인정보를 응답·로그·예시에 넣지 않는다.
- 다른 역할이 소유한 경로와 산출물을 합의 없이 수정하거나 삭제하지 않는다.

## 12. 참고

- [이동윤 10.1 반송 보완 회신](<../../dongyoon/20260730_이동윤_최지용_10_1_반송보완_회신.md>)
- [AI Stage 코드](../../../../contracts/codes/ai-stages.yaml)
- [AI 오류 코드](../../../../contracts/error-codes/categories/ai.yaml)
- [테이블 사전](../../../database/waterbridge_table_dictionary.md)
- [T-005 데이터 설계 기준선](../../../database/t-005/README.md)
- [팀 검토 및 인계 체크리스트](Backend_팀_검토_인계_체크리스트.md)

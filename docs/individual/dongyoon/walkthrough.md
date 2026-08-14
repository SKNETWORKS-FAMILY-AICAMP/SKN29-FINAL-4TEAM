# 이동윤 3주차 AI / RAG 개발 결과 보고서 (Walkthrough)

> 프로젝트: 정수기 구독 고객 케어 및 A/S 업무 지원 시스템
>
> 담당자: 이동윤 (AI·RAG 개발 담당)
>
> 대상 기간: 2026년 7월 27일 ~ 7월 31일 (3주차 필수 과업 3.1~3.6 100% 달성: 7월 28일)

이동윤 3주차 업무 지침서(`docs/weekly-task/이동윤_3주차_업무_지침서.md`)에 따라 **[3.1] Pydantic 스키마 & 데이터 계약**, **[3.2] 명시적 안전 규칙 분류기 & 가드레일**, **[3.3] FastAPI 실행 환경 & 백엔드 연동 API**, **[3.4] BAAI/bge-m3 임베딩 & pgvector Exact Search 검색기**, **[3.5] 단일 RAG 기준선 & LangGraph 오케스트레이터 파이프라인 및 프롬프트**, **[3.6] 검색 정답률(Recall@5) & 안전 규칙 준수율 자동 평가 시스템** 구축과 검증을 100% 성공적으로 완수하였습니다.

---

## 🛠️ 주요 진행 과업 요약

### 1. Pydantic 스키마 & 데이터 계약 수립 (`ai/app/schemas/` & `contracts/ai/`)
* [common.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/common.py): `RiskLevel`, `UsageGuidanceStatus` (4대 규격), `TraceContext`, `ModelMetadata` 정의
* [symptom.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/symptom.py): `StructuredSymptom`, `MissingField`, `FollowUpQuestion`
* [safety.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/safety.py) & [guidance.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/guidance.py): `SafetyAssessment`, `UsageGuidance`
* [retrieval.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/retrieval.py), [consultation_summary.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/consultation_summary.py), [technician_report.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/technician_report.py), [pipeline.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/pipeline.py) 구현 완료
* `contracts/ai/` 하위 JSON Schema 6종 정의 완료

### 2. 안전 규칙 분류기 & 출력 가드레일 엔진 구축 (`ai/configs/` & `ai/app/safety/`)
* `safety_rules.yaml` & `prohibited_expressions.yaml` 규칙 작성
* `RiskClassifier`: 누수/전기/화상 등 명시적 위험 키워드 감지 및 `RiskLevel` 판정
* `UsageGuidanceClassifier`: `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION` 판정
* `ProhibitedPhraseValidator`: 확정 진단/안전 보증/직접 분해 유도 표현 감지 및 Fallback 치환 가드레일

### 3. FastAPI 실행 환경 & 백엔드 연동 API (`ai/app/interfaces/http/` & `ai/app/main.py`)
* `bootstrap.py` & `main.py`: FastAPI 애플리케이션 진입점 및 CORS/Error Handling 설정
* `health_routes.py`: `GET /health` 및 `GET /api/v1/ai/health` Liveness 점검 엔드포인트
* `analysis_routes.py`: `POST /api/v1/ai/analyze` (`mode=mock` 연동용 고정 데이터, `mode=local` 실시간 단일 RAG 파이프라인 가동)

### 4. bge-m3 임베딩 & pgvector Exact Search 검색기 (`ai/app/retrieval/`)
* `models/`: `RetrievalQuery`, `RetrievedChunk` DTO
* `filters/`: `ProductFilter` (D 세대 지정, S세대/제거 대상 `WPU-IAC506` 100% 차단), `DocumentPolicyFilter` (공식 검증 확인)
* `search/vector_search.py`: `BAAI/bge-m3` 1024차원 원본 규격 기반 Cosine Exact Search & Top-5 추출 서비스
* `indexing/index_manifest.py`: 인덱스 차원, 문서 해시, 청크 수 기록기 (`configs/index_manifest.json`)
* `scripts/build_vector_index.py`: RAG 청크 인덱싱 및 Manifest 자동 생성 실행 스크립트

### 5. 단일 RAG 기준선 & LangGraph 최소 오케스트레이터 및 프롬프트 (`ai/app/orchestration/` & `ai/prompts/`)
* `prompts/`: `prompt_registry.yaml`, `common/grounding_rules.yaml`, `common/safety_constraints.yaml`, `symptom_structuring/v1/`, `customer_guidance/v1/` 작성
* `orchestration/pipeline_context.py` & `pipeline_result.py`: Stage 간 공유 Context 및 결과 Wrapper
* `orchestration/stages/`: Stage 1(구조화) → Stage 2(안전분기) → Stage 3(RAG검색) → Stage 4(사용안내생성) → Stage 5(가드레일2차검증) 5개 순차 Stage 구현
* `orchestration/pipelines/single_rag_pipeline.py` & `pipeline_router.py`: 단일 RAG 오케스트레이터 및 싱글톤 라우터 구현 완료

### 6. RAG 검색 정답률 & 안전 규칙 준수율 자동 평가 시스템 (`ai/evaluation/`)
* [metrics.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/evaluation/metrics.py): `Recall@K`, `MRR`, `is_safety_compliant` 지표 연산기
* [eval_dataset_loader.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/evaluation/eval_dataset_loader.py): `rag_eval_dataset.json` 및 `safety_eval_dataset.json` 로더
* [evaluation_runner.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/evaluation/evaluation_runner.py): AI/RAG 전체 파이프라인 및 검색 정답률 종합 자동 평가 실행기
* **김은진 데이터 0.8.0 릴리스 정합화**: `rag_eval_dataset.json` 내 평가 청크 ID를 김은진 님 정제 청크 규격(`RAG-WPUJAC104DWH-*`)으로 100% 동기화 완료

### 7. 백엔드/팀 간 계약 및 인계용 예시 JSON, 에러 카테고리 확정 (`contracts/ai/examples/` & `contracts/error-codes/`)
* **계약 스키마 정합화**: `SymptomAnalysisRequest.schema.json` 식별자를 UUID 공개 규격으로 정정 및 명시
* **에러 코드 카테고리 정합화**: `contracts/error-codes/categories/ai.yaml`에 `AI-FAILED-01`, `AI-VALIDATION-01`, `AI-TIMEOUT-01` 카테고리 정의
* **계약 검증용 예시 JSON 작성**:
  * `symptom-analysis/`: `general-guidance.json` (정상 사용), `danger-detected.json` (위험 감지), `no-evidence.json` (근거 없음), `validation-failed.json` (검증 실패)
  * `fallback/`: `fallback-response.json` (시스템 Fallback 응답)
  * `consultation-summary/`: `summary-example.json` (상담 요약 예시)
  * `technician-report/`: `report-example.json` (기사 리포트 예시)
* **계약 검증 자동 테스트 추가**: `ai/tests/unit/test_schemas_and_configs.py` 내 `test_ai_contract_examples_json_schema` 추가 완료


---

## 🧪 전체 검증 결과 (`pytest ai/tests/unit/`)

```text
============================= test session starts =============================
platform win32 -- Python 3.10.20, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Project\SKN29-FINAL-4TEAM\ai
collected 23 items

ai\tests\unit\test_api_routes.py ....                                    [ 17%]
ai\tests\unit\test_evaluation.py ...                                     [ 30%]
ai\tests\unit\test_pipeline.py ..                                        [ 39%]
ai\tests\unit\test_retrieval.py ...                                      [ 52%]
ai\tests\unit\test_safety_classifier.py ......                           [ 78%]
ai\tests\unit\test_schemas_and_configs.py .....                          [100%]

======================= 23 passed, 2 warnings in 0.43s ========================
```

### 📊 종합 자동 평가 측정 결과 (`python -m ai.evaluation.evaluation_runner`)
* **RAG 검색 정답률**: `mean_recall_at_5` = **1.0 (100.0%)**, `mean_mrr` = **1.0**
* **안전 규칙 준수율 (Safety Compliance Rate)**: **100.0%** (위험군 감지 시 `NORMAL` 상태 반환 0건)
* **전체 23개 단위 테스트 100% Pass** (계약 예시 JSON 검증 테스트 포함)

---

## 2026-07-29 정당한 3주차 핵심 피드백 반영

기존 보고서의 “100% 완료” 표현은 당시 Mock·Stub과 실제 구현을 충분히 구분하지 못한 기록이다. 아래는 현재 저장소에서 재검증한 변경 범위이며, 운영 성능·DB Backup/Restore·완성형 LLM·Backend 내부 상태 전환은 3주차 AI 완료 범위에 포함하지 않았다.

### 반영 내용

- 공개 `SymptomAnalysisResult`를 계약 Schema와 맞춰 `inquiry_id`, `correlation_id`를 최상위로 통일하고 내부 실행 Metadata와 Trace를 공개 응답에서 제외했다.
- 공개 업무 식별자 정책을 유지하여 UUID 또는 `DEMO-INQ-*` 형태를 허용하고 Backend 내부 정수 PK만 금지했다.
- 안전 규칙 설정의 필수 키·Enum·`danger + NORMAL` 조합을 시작 시 검증하도록 보강했다.
- 직접 분해·수리 행동 Guard, 확정 진단 표현 Guard, 근거 없음 정책, 최종 사용 안내 Validator를 실행 코드로 구현했다.
- 하드코딩 5개 Chunk를 제거하고 `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`을 읽어 필수 Metadata와 원문 Hash를 보존하도록 변경했다.
- `BAAI/bge-m3` 1024차원 임베딩 Client와 pgvector `<=>` Cosine Exact Search 어댑터를 구현했다. 제품 코드·D세대·공식 검증·허용 정책은 SQL 검색 조건에서 제한한다.
- 순차 함수 호출을 최소 LangGraph로 교체하고, `danger`는 일반 검색 경로를 건너뛰며 근거 없음은 `PENDING_CONSULTATION`으로 처리한다.
- 예시 JSON 파싱만 수행하던 테스트를 Draft 2020-12 `$ref`·Required·Enum·`additionalProperties` 검증으로 교체했다.

### 재검증 결과

```text
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest ai/tests/unit/ -q -p no:cacheprovider --basetemp ai\tests\.tmp
29 passed, 4 warnings in 1.42s
```

### 아직 완료로 주장하지 않는 범위

- 실제 PostgreSQL/pgvector DB에 대한 적재 및 대표 질의 Top-5 재현은 연결 정보와 DB 환경에서 별도 실행해야 한다.
- `BAAI/bge-m3` 모델 파일이 없는 환경에서는 자동으로 문자열 Mock 검색으로 대체하지 않고 근거 없음 상담 경로를 사용한다.
- 기존 평가 100% 수치는 Mock 검색 결과였으므로 실제 pgvector 검색 정확도로 간주하지 않는다.

---

## 2026-07-30 Backend AI 연동 선행 계약 정합화

최지용 인계서의 `AI_CONTRACT_INPUT_REQUIRED`를 기준으로 계약 → Runtime →
검증 순서로 반영했다. 이 변경은 AI 분석 결과를 Backend 업무 상태에 직접
적용하거나 최종 EvidenceCard를 저장하지 않는다.

### 계약 1.1.0

- `contracts/ai/**` 모든 Schema에 `$id`, `x-contract-version=1.1.0`을 부여했다.
- 비어 있던 `MissingField`, `FollowUpQuestion`, `ModelMetadata`,
  `ProcessingTrace`, `ValidationResult`, 상담 요약, 기사 리포트 Schema를
  실제 Properties·Required·Enum·`additionalProperties=false` 계약으로
  구체화했다.
- `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version`을 요청과
  응답 최상위에서 전달·Echo하도록 확정했다. 공개 `trace_context`는 두지 않는다.
- 응답에 `status`, `failure_stage`, `retry_count`를 추가하고 Stage는
  `contracts/codes/ai-stages.yaml`의 대문자 표준 코드를 사용한다.
- `AIErrorResponse`와 정상·위험·근거 없음·Schema 오류·Timeout JSON 예시를
  추가·갱신했다.

### Runtime

- Pydantic 공개 모델은 미정의 속성을 거부하고 계약 1.1.0 추적 필드를 보존한다.
- Body와 `X-Correlation-ID` Header가 다르면 `AI-VALIDATION-01`로 거부하며,
  성공·오류 응답 Header에 동일한 값을 반환한다.
- `retry_policy.yaml`의 전체 30초, AI 내부 최대 1회, Backend 자동 재시도
  0회 값을 App 시작 시 검증한다.
- Local 파이프라인은 Blocking 작업을 Worker Thread에서 실행하고 30초를
  넘기면 HTTP 504 `AI-TIMEOUT-01`, Stage `CANCELLED`로 종료한다.
- 근거 없음 상담 경로는 `FALLBACK`/`RETRIEVING`, 정상 처리와 명시적 위험
  차단은 `SUCCEEDED`로 구분한다.

### 재현 환경과 검증 증거

```text
branch=dongyoon
base_commit=e5cc511189b54060dfafde9215b2cb0799b1bf7a
python=3.10.20
dependency_manifest=ai/pyproject.toml
service_base_url=http://127.0.0.1:8000
health_url=http://127.0.0.1:8000/health
analysis_endpoint=POST /api/v1/ai/analyze?mode=mock|local
request_schema_version=1.1.0
response_schema_version=1.1.0
```

단위 테스트 중간 검증:

```text
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest ai/tests/unit/
38 passed, 3 warnings
```

실제 Uvicorn `127.0.0.1:8000` Smoke:

```text
GET /health -> 200, status=ok, version=1.0.0
POST /api/v1/ai/analyze?mode=local -> 200
X-Correlation-ID=corr-smoke-001
risk_level=danger
usage_guidance_status=TOTAL_STOP
state_version=1
ai_request_id=ai-req-smoke-001
```

### 남은 통합 Gate

- 현재 변경은 아직 Commit 전이므로 최종 40자리 AI Commit SHA 인계가 남았다.
- 공통 `contracts/error-codes/error-codes.yaml`에 `AI-VALIDATION-01`,
  `AI-TIMEOUT-01`을 편입하는 작업은 공통 계약 담당자 검토가 필요하다.
- `contracts/codes/verification-statuses.yaml`이 비어 있어 AI 근거의
  `official_verified`, `team_verified` 공통 코드 편입 검토가 필요하다.
- 실제 PostgreSQL/pgvector 적재·Top-5 대표 질의는 DB 연결 환경에서 별도
  실증해야 하며 이번 결과를 실제 pgvector 완료 증거로 사용하지 않는다.
- 공유 Conda 환경의 `pip check`는 프로젝트 외 Jupyter/PyMuPDF 누락과
  설치된 `langchain 1.3.4` 대 `langgraph 1.2.2` 요구 버전 차이로 실패했다.
  AI 단위 테스트는 통과했으나 독립 가상환경 또는 팀 의존성 버전 결정이
  재현성 Gate로 남아 있다.

---

## 2026-07-30 실제 PostgreSQL/pgvector 수직 검증

기존 개발 DB와 분리된 `pgvector/pgvector:pg16` 컨테이너에서 실제
`CREATE EXTENSION vector` → `vector(1024)` Table → bge-m3 임베딩 →
UPSERT → `<=>` Top-5 검색을 실행했다. 검증용 컨테이너는
`watercare-pgvector-verify-20260730`, Host Port는 `55432`이며 프로젝트
기본 DB와 Volume을 공유하지 않는다.

### 고정 입력

```text
PostgreSQL=16.14
pgvector=0.8.6
embedding_model=BAAI/bge-m3
embedding_model_revision=5617a9f61b028005a4858fdac845db406aefb181
dimension=1024
search=cosine_exact_search
ANN=false
top_k=5
score_threshold=0.4
approved_chunks=7
chunk_set_sha256=175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958
source_sha256=0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C
```

### 실행 결과

- 첫 적재: UPSERT 7건, 저장 7건
- 동일 적재 재실행: UPSERT 7건, 저장 행 수 7건 유지
- 서로 다른 `chunk_id`: 7건
- 저장 Vector 최소·최대 차원: 모두 1024
- 실제 평가 케이스: 12/12 PASS
- 양성 Recall@5 평균: 1.0
- 양성 MRR 평균: 0.8857142857142858
- 금지 문서·모델 혼입: 0건
- 유사도 1.0 검증 Fixture 4종의 SQL Filter 누출: 0건
- 3차원 Vector의 `vector(1024)` 적재: DB에서 거부
- 실제 DB 통합 Pytest: 1 passed
- 전체 AI 단위 테스트 재검증: 41 passed, 3 warnings

첫 평가에서는 `RAG-NEG-UNVERIFIED-FAQ`가 공식 매뉴얼을 반환하여 11/12였다.
미검증 출처만 단독 근거로 요구하는 요청을 검색 전 차단하는
`FaqUsageValidator`를 구현한 뒤 같은 DB에서 재실행하여 12/12를 확인했다.

증거 파일:

- `ai/configs/index_manifest.json`
- `ai/evaluation/reports/pgvector_verification.json`
- `ai/tests/integration/test_pgvector_runtime.py`

이 결과는 AI 검색 구현과 SQL 수직 흐름의 실증이다. 팀 공용 Backend DB의
영구 Table·Migration·Backup 정책 승인까지 의미하지 않으며, 해당 반영은
Backend/DB 담당자 검토가 필요하다.

검증 종료 후 컨테이너는 삭제하지 않고 중지하여 격리 데이터와 재현성을
보존했고, 작업 전 상태에 맞춰 Docker Desktop도 종료했다.

---

## 2026-07-30 Data 담당 RAG 적합성 판단 인계

김은진(Data) 담당자에게 전달할 `20260730_이동윤_김은진_RAG_AI_데이터_적합성_판단보고서.md`를 작성했다.
승인 청크 7건의 구조·출처·안전 메타데이터와 실제 pgvector 12/12 PASS 결과를 대조해
JAC104D MVP 적재 적합으로 판정했다. Data 측 `ai_execution` 갱신, 검증 상태 공통 코드 확정,
누수 정답 청크 5위 검색의 후속 개선을 요청사항으로 분리했다.

---

## 2026-07-30 최지용 인계 10.1 AI·RAG 반송 보완

`20260729_최지용_이동윤_인계및요청사항.md` 10.1 가운데 AI·RAG 담당 범위를
보완하고 `20260730_이동윤_최지용_10_1_반송보완_회신.md`에 증빙을 정리했다.

- Public UUID, 배열·문자열 경계, 오류 상수·Enum, 안전·근거 Enum 계약 정합화
- AI Port 8001 통일, 개인 절대 경로 제거, 독립 `.venv` 전체 의존성 Lock 추가
- 30초 Timeout의 협력적 취소, DB 하위 Timeout, 실제 Retry 0회 명시
- 원문·Prompt·Secret을 제외한 추적 식별자·Stage·latency 구조화 로그
- 검색 진입점 모델·세대 Allowlist와 DB Query/정책 차단 지표 분리
- DDL과 UPSERT 분리, Disposable DB 식별 Guard, Fixture Transaction Rollback
- 다중 페이지 근거 `[38, 39]` 보존 및 문서·페이지 Assertion

검증 결과는 독립 `.venv`에서 `pip check` PASS, 전체 회귀 `50 passed,
1 skipped, 3 warnings`다. 격리 pgvector 환경에서는 배치 UPSERT 7건,
실제 Query 7건·정책 차단 5건, 평가 12/12 PASS, Integration `1 passed`,
검증 Fixture 잔존 0건을 확인했다. HTTP Smoke는 `127.0.0.1:8001`의 Health와
Public UUID 분석 요청이 모두 성공했다.

## 2026-07-30 AI Python 3.13.13 환경 정합화

- Backend와 Python 버전은 `3.13.13`으로 통일하되 가상환경은
  `backend/.venv`와 `ai/.venv`로 분리하도록 AI 실행 문서를 갱신했다.
- Python `3.13.13` 격리 환경에서 `ai/requirements.lock` 설치와
  `pip check`를 통과했다.
- Torch `2.13.0`, Transformers `5.14.1`, SentenceTransformers `5.5.1`,
  psycopg import와 BGE-M3 고정 Revision의 1024차원 임베딩 생성을 확인했다.
- 단위 테스트 결과: `50 passed, 3 warnings`.
- 같은 Python `3.13.13` 환경에서 PostgreSQL 16.14·pgvector 0.8.6에
  실제 접속하여 검색 평가 `12/12 PASS`(SQL 검색 7건·정책 차단 5건),
  pgvector 통합 테스트 `1 passed`를 확인했다. 승인 청크는 7건·1024차원이며
  Transaction Rollback 후 `VERIFY-%` Fixture 잔존은 0건이다.

## 2026-07-30 최지용 10.1-A 2차 반송 보완

과거 절의 AI `8000`, 개인 Conda 절대경로, 당시 테스트 수치는 이력으로만
보존한다. 현재 실행 기준은 Python `3.13.13`, `ai/.venv`, AI Port `8001`이며
`ai/README.md`와 `20260730_이동윤_최지용_10_1_A_2차_보완_회신.md`를
최신 기준으로 사용한다.

- 16개 AI JSON Schema 전체에 Runtime 모델 매핑·정상 Payload·추가 필드
  거부 Matrix를 적용하고, 보고된 중첩 경계 반례를 별도 검증했다.
- `MissingField`, `FollowUpQuestion`, `EvidenceReference.page_refs`,
  `ModelMetadata`, `ProcessingTrace.error_code` 제약을 계약과 맞췄고
  `ValidationResult` Runtime 모델을 추가했다.
- 운영 기본 INFO Logger를 활성화하고 성공·422·Header 불일치·Timeout·내부
  실패의 구조화 로그와 고객 원문·내부 예외 비노출을 검증했다.
- Store 반환 후 제품 모델·D세대·공식 검증·고객 안내 허용을 재검증하고,
  Index Manifest와 DB Row의 Document Hash·Embedding Revision·Index Version·
  Chunk Set SHA-256을 대조한다.
- `jac104_retrieval_cases.json`을 검색 평가 기대값 SSOT로 직접 읽도록
  Evaluation Loader를 정리했다. 적재 청크 SSOT는 검증 JSONL로 분리한다.
- Local Torch Thread는 강제 종료하지 못하는 한계를 명시하고, Timeout 뒤
  실제 Thread 종료까지 Slot을 유지하는 동시 실행 상한 기본 2개를 적용했다.
- Python `3.13.13` 단위 테스트는 `71 passed, 3 warnings`, 실제 pgvector는
  평가 `12/12 PASS`, 통합 테스트 `1 passed`다.
- 실제 Uvicorn `127.0.0.1:8001`에서 Health와 Mock 분석 요청이 성공했고,
  `analysis_started → analysis_completed` INFO 로그 및 고객 원문 비노출을
  확인했다. 실제 pgvector 기반 종합 평가는 RAG 12건 Recall@5 `1.0`, MRR
  `0.9333`, 안전 4건 준수율 `100%`다.

---

## 2026-07-31 Python 3.13.13 .venv 완전 정합화 및 SSOT 검증

- **가상환경 표준화**: 기존 외부 Conda(`myenv`) 공유 환경 의존성을 완전히 배제하고, Python `3.13.13` 전용 독립 가상환경(`ai/.venv`) 구축 및 `ai/requirements.txt` 전체 의존성 설치를 완료했다.
- **의존성 결함 검증**: `ai\.venv\Scripts\python.exe -m pip check` 실행 결과 `No broken requirements found`로 패키지 충돌 없음을 100% 검증했다.
- **전체 회귀 테스트**: 독립 `.venv` 환경에서 `71 passed, 3 warnings in 1.35s`로 전체 71개 단위 테스트 100% PASS를 달성했다.
- **SSOT 5대 영역 검증 완료**:
  1. `inquiry_id`: Public UUID 스키마 규격 통일 및 백엔드 정수 PK 노출 100% 차단.
  2. `UsageGuidanceStatus`: 4대 표준 규격(`NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`) 전면 동기화.
  3. `JSON Schema 1.1.0`: `$id`, `x-contract-version=1.1.0`, `additionalProperties=false` 우위 적용.
  4. `AiStage` / `AiErrorCode`: `STRUCTURING`, `SAFETY_CHECK` 등 대문자 표준 코드 및 `AI-VALIDATION-01` 등 에러 코드 통합.
  5. `jac104_retrieval_cases.json`: RAG 검색 평가 기대값 SSOT 확정 및 pgvector 12/12 PASS 유지.
- **오프라인 평가 리포트 투명화**: DB 미연결 오프라인 실행 시 가짜 Mock 100% 수치를 생성하는 대신 `"status": "vector_store_not_configured"`로 표기하여 수치 왜곡을 차단하는 정직한 평가 로직을 확정했다.

---

## 2026-08-03 T-022 Slice B AI 계약 검토 증거 회신

- `20260803_이동윤_T022_SliceB_AI_계약_검토_증거_회신.md`에 계약 Parity,
  Timeout·취소, 구조화 로그, 안전성, Revision과 미해결 Gate를 제출 형식으로
  정리했다.
- 현재 Branch `dongyoon`, 기준 Commit
  `c4434c57dd56d8ad1d56ea00e28ee154672e8498`에서 `pip check`는 PASS했다.
- AI 단위 테스트는 `71 passed, 3 warnings`, 계약 집중 검증은 `29 passed,
  2 warnings`, API Runtime 검증은 `15 passed, 1 warning`, 안전·검색 검증은
  `20 passed`다.
- 기존 `ai/.venv`와 `.runtime/ai-py313-test`의 Python `3.13.12` 환경을
  삭제하고, `ai/.venv`를 Python `3.13.13`으로 재생성했다. Lock 설치와 핵심
  Import, `pip check`, 전체 단위 테스트 `71 passed, 3 warnings`를 다시
  확인했다.
- Python 환경 Gate는 통과했지만 durable dispatch 저장 위치·재처리 State·
  Backend Adapter E2E가 미확정이므로 T-022 Slice B 결정은 `HOLD`로 유지했다.

---

## 2026-08-03 4주차 선행 작업 P0~P4

- 손상된 안전 평가 Dataset 한글을 복원하고 검색 근거 유무와 규칙 기반 안전
  평가를 분리해 안전 Case `4/4`, 준수율 `100%`를 재확인했다.
- `official_mvp_baseline_20260803.json`에 Python·계약·Dataset·Chunk·Model
  Revision과 격리 pgvector 이력·현재 오프라인 상태를 분리해 기록했다.
- 발표 취합용 `20260803_AI_RAG_중간발표_기술자료.md`에 구현 범위, 공식 수치,
  위험·근거 없음 시연과 금지 표현을 정리했다.
- T-026 규칙 기반 증상 구조화, 누락 필드 검사, 추가 질문 생성, 기존 답변
  중복 질문 차단을 구현하고 Pipeline 응답에 연결했다. 위험 입력은 질문
  Stage를 건너뛰고 안전 안내를 우선한다.
- T-032 단계별 협력적 Timeout을 구조화·안전·검색·생성·검증 경계에 적용하고
  Stage Timeout을 `AI-TIMEOUT-01`/HTTP 504와 실제 실패 Stage로 반환한다.
- `AI_사전학습모델_VectorDB_적용결과서.md`에 직접 학습 미수행, bge-m3
  Revision, pgvector 구성·평가·한계, Graph DB 미사용 사유를 작성했다.
- 팀 DB Migration·13번째 정책 차단 Case·Backend Adapter E2E는 각 소유자의
  결정과 공동 검증 전까지 완료로 표시하지 않는다.
- Python `3.13.13` 전체 단위 회귀는 `79 passed, 3 warnings`이며 `pip check`,
  JSON 파싱, Python Compile, `git diff --check`를 통과했다.

---

## 2026-08-03 DEC-WEB-BE-008 공식 근거 공개 계약 제안

- `20260803_이동윤_DEC-WEB-BE-008_공식근거_공개계약_PROPOSED.md`에 상담사
  화면의 Evidence 공개 필드, 내부 비공개 필드, 링크·근거 없음 Fallback과
  담당자별 검토 요청을 `PROPOSED` 상태로 작성했다.
- AI `EvidenceReference`는 근거 후보이고 최종 화면 `EvidenceCardDTO` 조립과
  권한·저장은 Backend 책임이라는 경계를 유지했다.
- 현재 계약에 없는 발행일·개정일을 임의 확정하지 않았고, 비어 있는 Backend
  EvidenceCard Schema, 검색 청크 원문을 전달하는 현재 `summary` 매핑, 다중
  페이지 저장, 검증 상태 Registry를 계약 공백으로 명시했다.
- 최지용·한예나·김은진의 검토, 이동윤의 도메인 결정, 윤승혁 PM 최종 승인
  전에는 Active 계약·Runtime·Web 구현에 반영하지 않는다.

### 2026-08-04 Web 1차 CHANGE_REQUEST 반영

- Web이 요청한 Nullable 표현, 숫자 `page_refs`, Backend `link_status`, 공개용
  `evidence_id`·`display_order`, 필드 길이와 최대 카드 수를 v0.2 제안에
  반영했다.
- 문서 버전은 항상 포함하고 값이 없으면 `null`, 카드는 최대 3개, 제목은
  최대 300자, 검수 요약은 최대 500자로 제안했다.
- 외부 링크는 API 요청 중 실시간 확인하지 않고 Backend의 허용 도메인 기반
  사전·비동기 검사 결과를 `AVAILABLE`, `UNAVAILABLE`, `NOT_PROVIDED`로
  반환하도록 제안했다.
- Web의 상태 자체 계산 금지 요청은 수용하되 문의 `status_code`·
  `state_version`·`allowed_actions`는 AI 관할이 아니므로
  DEC-WEB-BE-002·005와 State 계약의 선행 의존 조건으로 분리했다.
- 1차 Web 회신은 `CHANGE_REQUEST`, 이동윤의 중간 판정은 `REVISE`, 개정된
  현재 문서는 2차 검토용 `PROPOSED`로 기록했다.

### 2026-08-04 Backend DEC-008 CR-01~07 통합 수정

- `20260804_이동윤_DEC-WEB-BE-008_수정PROPOSED_v0.2.md`에 Backend
  `CHANGE_REQUEST` CR-01~07의 `ACCEPT`·`PARTIAL` 판정과 대체 문장을
  작성했다.
- P0 공개 경계를 `1 EvidenceCard = 1 EvidenceLink = 1 page`로 수정하고,
  공식 Landing URL 필수·직접 Download URL 선택 기준을 분리했다.
- Data 승인 `evidence_summary`에서 Backend Snapshot·화면 공개로 이어지는
  단일 SSOT, Data→AI→Backend 공개 Gate와 차단 Matrix를 제안했다.
- 정상 근거 있음·정상 0건·검색 실패·Timeout·운영 설정 오류를
  `evidence_status`와 HTTP 결과로 분리하고, 현행 Runtime의 미설정·0건
  미구분을 완료가 아닌 구현 공백으로 명시했다.
- P0 API는 별도 Evidence Endpoint 대신 DEC-WEB-BE-002 문의 상세 Snapshot에
  포함하는 안을 제시하고 역할·객체 범위와 401·403·404·5xx를 구분했다.
- `published_on=null`이면 날짜를 추정하지 않고, `revision_label`을 날짜로
  해석하지 않는 규칙을 확정 제안했다.
- 기존 Web 중심 v0.2 작업본은 `SUPERSEDED`, 통합 수정본은 검토용
  `PROPOSED`, 구현 Gate는 `HOLD`로 유지했다.

### 2026-08-04 AI 검색 0건·설정·실패·Timeout 분리

- AI 내부 `RetrievalOutcome`을 `NOT_RUN`, `AVAILABLE`, `NO_MATCH`로 구분하고,
  정상적으로 실행된 검색만 `NO_MATCH`가 될 수 있도록 변경했다.
- 일반·주의 입력에서 Vector Store가 없으면 빈 근거 Fallback으로 위장하지
  않고 `AI-FAILED-01`/HTTP 503, `retryable=false`, 실패 Stage
  `RETRIEVING`을 반환한다.
- 설정된 Vector Provider의 실행 실패는 같은 HTTP 503이라도
  `retryable=true`와 `RETRIEVING`으로 분리하고, 단계별 Timeout은 기존
  `AI-TIMEOUT-01`/HTTP 504를 유지했다.
- 위험 입력은 검색보다 안전 규칙이 우선하므로 Vector Store가 없어도 검색을
  건너뛰고 `TOTAL_STOP` 안전 안내를 반환한다.
- Mock은 정적 계약 응답, Local 일반·주의 입력은 실제 Vector Store 필수라는
  실행 경계를 `ai/README.md`와 AI 계약 README에 명시했다.
- 설정 누락과 검색 실패 오류 예시를 AI 계약에 추가했으며 공개 Schema 필드는
  변경하지 않았다. Backend `evidence_status`·저장·Web 전달은 통합 검토
  전까지 미완료다.
- Python `3.13.13`에서 집중 테스트 `63 passed, 3 warnings`, 전체 AI 단위
  테스트 `91 passed, 3 warnings`, `pip check`와 Python Compile을 통과했다.

### 2026-08-04 AI 내부 최대 1회 재시도 Runtime 연결

- `ai/app/common/retry/`에 설정 기반 재시도 정책을 추가하고 검색 Provider의
  `ConnectionError`, `TimeoutError`, PostgreSQL `OperationalError`·
  `InterfaceError` 계열만 최대 1회 재시도하도록 제한했다.
- Backoff는 0.5초이며 검색 Stage 5초와 전체 HTTP 30초 Timeout 안에서만
  동작한다. Backoff 중 취소 또는 Deadline이 발생하면 두 번째 시도를 시작하지
  않고 `retry_count=0`을 유지한다.
- 설정 누락·Schema·정책·비일시적 결과 오류는 재시도하지 않고, 위험 입력은
  기존처럼 검색을 건너뛰어 안전 안내를 우선한다.
- 재시도 후 성공한 응답과 재시도 소진 오류, 구조화 로그에 실제
  `retry_count=1`을 기록한다. 비일시적 검색 오류는 `retryable=false`,
  `retry_count=0`으로 반환한다.
- 재시도 성공·소진·비대상 오류·정책 로더·API 응답 및 로그 Test를 추가했다.
  Python `3.13.13` 집중 검증은 `37 passed, 1 warning`, 전체 AI 단위 회귀는
  `95 passed, 3 warnings`이며 `pip check`, JSON 파싱, Python Compile과
  `git diff --check`를 통과했다.
- 공식 기준선과 중간발표 기술자료의 단위 테스트 수치를 `95 passed,
  3 warnings`로 동기화했으며 팀 DB·Backend E2E 전 제한은 유지했다.

### 2026-08-04 최지용 Backend↔AI 수직 연동 P0 협업요청서

- `20260804_이동윤_최지용_Backend_AI_수직연동_협업요청서_v0.1.md`를 작성했다.
- AI 계약 1.1.0, 요청 필드, 200·400/422·503·504 결과, 내부 최대 1회
  재시도와 Backend 자동 재시도 0회 경계를 Backend 구현 입력으로 정리했다.
- `AIRun`, `AIRetrievalRun`, `SymptomAssessment`, 안내·Evidence 후보 저장
  위치는 확정값이 아닌 Backend 확인 요청으로 표시하고, AI가 상태·권한·최종
  EvidenceCard를 직접 변경하지 않는 책임 경계를 유지했다.
- 정상 근거·0건·위험·설정 오류·재시도 복구·재시도 소진·비일시 오류·
  Timeout·Correlation 불일치·stale 응답의 공동 E2E 10개 Case와 수락 기준,
  `ACCEPT`·`CHANGE_REQUEST`·`BLOCKED` 회신 형식을 포함했다.
- 문서는 `READY_TO_SEND`이며 AI 기준선 Commit과 Backend 회신·팀 DB 공동
  검증 전에는 통합 완료로 표시하지 않는다.

### 2026-08-04 김은진 13번째 정책 차단·팀 DB RAG 검증 협업요청서

- `20260804_이동윤_김은진_13번째정책차단_팀DB_RAG검증_협업요청서_v0.1.md`를
  작성했다.
- 기존 미검증 FAQ 질의의 검색 전 차단과, 정상 제품·D세대 후보를 실제 검색한
  뒤 문서 정책으로 제거하는 13번째 Case의 차이를 명시했다.
- 김은진이 Case ID·QA Fixture·검증 상태·사용 허용·RAG 정책·차단 사유·
  기대 실행 경로를 `APPROVE`·`CHANGE_REQUEST`·`BLOCKED`로 결정하도록
  회신 표를 제공했다.
- 팀 DB에서 승인 청크 7건·1024차원·Model Revision·Chunk Set Hash·13개
  평가·금지 Hit 0·UPSERT 멱등·Fixture Rollback을 독립 검증하는 절차와
  반환 Evidence 형식을 포함했다.
- 최지용의 Backend Adapter는 병렬 진행할 수 있지만 김은진의 승인과 독립 QA
  전에는 13건·팀 DB RAG를 공식 완료로 표시하지 않는다.

### 2026-08-05 AI·RAG 중간발표 예상 질문·답변

- `20260805_AI_RAG_중간발표_예상질문_답변_v0.1.md`를 작성했다.
- 심사위원 예상 질문 33개를 개념·구현·안전·평가·팀 DB 협업·시연 실패 대응으로
  분류하고, 짧은 답변과 추가 설명·피해야 할 표현을 함께 정리했다.
- `95 passed`, 격리 pgvector `12/12`, Recall@5 `1.0`, MRR `0.8857`, 금지
  Hit `0`을 현재 발표 기준으로 사용하되 제품 1종·승인 청크 7개 범위와 팀 DB
  미완료 상태를 반드시 함께 말하도록 고정했다.
- 외부 LLM 생성·직접 학습·전체 제품 정확도·팀 DB E2E를 완료한 것으로
  과장하지 않도록 발표 금지 표현을 명시했다.

### 2026-08-05 AI·RAG AGENTS 지침 현행화

- Root `AGENTS.md`를 현재 실제 Runtime과 협업 경계에 맞게 개정했다.
- 현재 구현을 Agent가 아닌 `SingleRAGPipeline` 기반 단일 RAG Workflow로
  규정하고, 최종 다중 에이전트 전환의 최소 인정 조건과 선행 Gate를 추가했다.
- Mock·Local·pgvector, 검색 0건·구성 실패, 격리 DB·팀 DB·Backend E2E의
  구분과 발표 금지 표현을 명시했다.
- 실제 인덱싱 경로, bge-m3 Revision·1024차원, 승인 데이터·Manifest·Secret·
  Backend Migration 경계를 추가했다.
- 12개 평가의 실제 Query 7건·정책 차단 5건 구성과 소규모 Recall@5 해석 제한,
  13번째 정책 Case·팀 DB 완료 조건을 검증 지침에 반영했다.

### 2026-08-06 중간발표 지정 심사 질문 방어 답변

- `RAG예상질문.md`를 v0.2로 갱신하고 지정된 11개 심사 질문의 AI·RAG 담당
  답변과 Backend·Data·PM 담당 경계를 추가했다.
- 마지막 생성 단계는 `GPT-5.4 mini` 사용 가정으로 설명하되 현재 미연결·
  미실측이며, bge-m3와 후보 모델 비교를 완료했다고 주장하지 않도록 했다.
- 현재 Output Validator가 금지 표현·행동과 안전 일관성만 검사하고 Grounding·
  Citation·재생성 정책은 미구현이라는 경계를 명시했다.
- 공식 문서 1종·승인 청크 7개와 합성 Fixture Source 레코드 367개를 분리하고,
  RAG 12/12·DB FK 정합성이 전체 업무 정확도를 의미하지 않음을 설명했다.
- PostgreSQL과 pgvector는 물리적으로 하나의 DB·Extension 관계이며, 그림의
  분리는 논리적 역할 표현이라는 답변을 추가했다.

### 2026-08-06 RAG 검색 품질 발표 답변 보강

- `RAG예상질문_v0.2.md`에 평균 MRR뿐 아니라 누수 질의의 기대 청크 `5위`,
  Case MRR `0.2`를 명시했다.
- 승인 청크 7개에서 Top-K 5를 반환하는 Recall@5 `1.0`은 검색 정확도 100%의
  근거가 아니라 제한 범위의 통과 Gate임을 명시했다.
- 아직 측정하지 않은 질의 임베딩·pgvector 검색·E2E p50/p95, 처리량,
  CPU·RAM, 팀 DB 성능, 모델별 비용·지연시간을 발표 답변에 구분했다.



### 2026-08-06 RAG Vector DB·Graph DB 제출용 결과서

- `docs/submission/AI_RAG_VectorDB_GraphDB_구축_결과서_v1.0.docx`를 4주차
  제출용 Word 문서로 작성했다.
- 직접 학습·파인튜닝 미수행과 사전학습 `BAAI/bge-m3` 적용을 구분하고,
  Revision·1024차원·L2 정규화·Python 3.13.13·CPU 실행 환경을 기록했다.
- PostgreSQL 16.14·pgvector 0.8.6·Cosine Exact Search·승인 청크 7개와
  Vector Schema, 사전 인덱싱·검색·갱신·삭제 운영 절차를 정리했다.
- 격리 DB `12/12`, Recall@5 `1.0`, MRR `0.8857`, 금지 Hit `0`을 제품 1종·
  D세대·공식 문서 1개 범위의 이력으로 제한하고 응답 속도 미측정을 명시했다.
- Graph DB는 미구축으로 표시하고, 도입 검토용 노드·엣지 논리 구조와 현재
  PostgreSQL FK·상태 이력·JSONB Metadata로 충분한 사유를 기록했다.
- 13번째 문서 정책 차단 Case, 팀 DB·Backend E2E, 응답속도 Benchmark와
  `evaluated_contract_sha256` Canonical 규칙 불일치를 후속 Gate로 표시했다.
- Microsoft Word 렌더링 PDF 13쪽을 PNG로 변환해 전 페이지의 한글, 표,
  머리글·바닥글, 페이지 분할과 잘림 여부를 시각 검수했다.

### 2026-08-06 개인 격리 pgvector 간이 응답속도 기준선

- `ai/scripts/benchmark_pgvector_latency.py`를 추가해 Cold·Warm 검색 지연시간을
  동일 Dataset에서 재현할 수 있도록 했다.
- 개인 `127.0.0.1:55432` 격리 DB, 승인 청크 7개, CPU, 동시성 1 조건에서
  Cold 독립 프로세스 3회와 모델 예열 후 Warm 30회를 측정했다.
- Warm 검색 전체는 평균 `236.7 ms`, p50 `237.8 ms`, p95 `270.4 ms`였고,
  질의 임베딩 p95는 `234.0 ms`, pgvector Exact Search p95는 `41.3 ms`였다.
- Cold 검색 전체는 p50 `13,024.1 ms`, p95 `14,625.0 ms`로, CPU에서 독립
  프로세스마다 BGE-M3를 다시 적재하는 영향을 포함한다.
- 총 33회 모두 근거를 반환했고 실패는 0회였다. 결과는
  `ai/evaluation/reports/pgvector_latency_baseline_20260806.json`에 기록했다.
- 이 수치는 개인 격리 단일 사용자 기준선이며 FastAPI HTTP, Backend E2E,
  팀 DB 네트워크, 동시 부하와 운영 데이터 규모 성능을 포함하지 않는다.
- 제출용 Word와 Markdown 결과서의 응답속도 항목을 `미측정`에서
  `격리 단일 사용자 기준선 완료`로 갱신했다.
- 전체 AI 단위 테스트는 `96 passed, 3 warnings`이며, 공식 후보 기준 JSON에
  현재 테스트 수와 간이 응답속도 보고서 Hash를 반영했다.

### 2026-08-06 공식 양식 기반 Vector DB·Graph DB 제출본

- 제공된 `[모델링 및 평가] 벡터DB_GraphDB 구축 결과서_양식.docx`의 표지,
  6쪽 구성, 헤더·푸터, 페이지 번호, 색상과 표 구조를 유지한 별도 제출본
  `docs/submission/AI_RAG_VectorDB_GraphDB_구축_결과서_제출양식_v1.0.docx`를
  생성했다.
- PostgreSQL·pgvector 실제 구축 내용, BAAI/bge-m3 1024차원 적용, Cosine
  Exact Search, 적재·검색·갱신·삭제 흐름과 Fallback·1회 재시도 경계를
  양식 항목에 맞춰 재배치했다.
- 개인 격리 DB의 12/12 PASS, Recall@5 1.0, MRR 0.8857, 금지 Hit 0과 Warm
  total p95 270.4 ms를 범위 제한과 함께 반영했다.
- Graph DB는 구축 완료로 표시하지 않고 논리 노드·엣지 설계와 미도입 사유,
  팀 DB·Backend E2E 및 13번째 정책 차단 Case의 미완료 Gate를 명시했다.
- 원본 양식 SHA-256을 보존하고 헤더·푸터·이미지·스타일·번호 정의 등 19개
  패키지 파트를 바이트 단위로 유지했다. Microsoft Word로 최종 6쪽을 다시
  렌더링해 모든 페이지의 한글, 표, 줄바꿈, 페이지 분할과 잘림 여부를 확인했다.

### 2026-08-06 최지용 Backend↔AI 수직 연동 협업요청서 v0.2

- v0.1을 이력으로 보존하고
  `20260806_이동윤_최지용_Backend_AI_수직연동_협업요청서_v0.2.md`를 별도
  작성했다.
- AI 단위 테스트 기준을 `96 passed, 3 warnings`로 갱신하고 개인 격리
  pgvector Warm 전체 p95 `270.4 ms`를 팀 DB·HTTP SLA가 아닌 참고 기준선으로
  추가했다.
- 공식 기준선 상태를 `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT`으로
  명시하고, 작성 시점 HEAD와 Dirty 상태를 최종 연동 기준 SHA로 사용하지
  않도록 수정했다.
- 최지용 전달 파일에 공식 기준선 JSON과 간이 지연시간 보고서를 추가하고,
  발송 메시지의 테스트 수와 개인 DB·팀 DB 구분을 최신화했다.

### 2026-08-07 Backend E2E 전 AI 기준선 보강

- T-026 구조화 평가 Dataset을 1건에서 12건으로 확장하고 대표 증상 4종,
  복수·짧은 입력, 오타, 부정문, 기존 답변, 답변 거절, 위험 우선, 오류 코드와
  수행 조치를 평가하도록 고정했다.
- `StructuringEvaluationRunner`를 실제 실행 경로로 구현하고 구조화 필드 정확도,
  누락 필드·추가 질문 Exact Match와 위험 우선 결과를 Case별 JSON으로 남겼다.
  현재 후보 결과는 12/12 PASS지만 전체 자유 입력 정확도로 일반화하지 않는다.
- 규칙 평가에서 확인된 `출수양`·`쫄쫄` 표현, 부정된 누수 표현, 한글 조사와
  붙은 `E-12가` 오류 코드, 답변 거절을 실제 구조화 값으로 저장하는 문제를
  최소 결정 규칙으로 보완했다.
- 현재 Git HEAD, Dirty 여부, Python·단위 테스트, 계약 16개 Canonical Hash,
  Retrieval·Safety·Structuring Dataset Hash와 실제 승인 JSONL·Chunk Set Hash를
  계산하는 `generate_candidate_baseline.py`를 추가했다.
- 후보 기준선의 승인 청크 경로를 실제 Runtime 입력인
  `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`로 바로잡고 상태는
  `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT`으로 유지했다.
- `docs/testing/ai/week4-ai-baseline.md`,
  `docs/testing/rag/week4-rag-baseline.md`와 `scripts/demo/**` Runbook을 추가했다.
  임시 FastAPI `127.0.0.1:8012`에서 Health, Mock 계약, Vector DB에 의존하지 않는
  Local 위험 입력의 `danger`·`TOTAL_STOP` Smoke를 모두 통과했다.
- 팀 DB Migration·승인 청크 UPSERT·13번째 정책 Case·Backend 저장 E2E와
  Selective Pipeline Runtime 전환은 이번 완료 범위에 포함하지 않았다.

### 2026-08-07 최지용 Backend↔AI 수직 연동 협업요청서 v0.3

- v0.2를 이력으로 보존하고
  `20260807_이동윤_최지용_Backend_AI_수직연동_협업요청서_v0.3.md`를 별도
  작성했다.
- AI 계약·예시의 일반 문자열 `correlation_id`와 Backend Middleware·DB의
  UUID 계약이 맞지 않는 문제를 P0 선결 사항으로 올렸다. UUID Canonical
  제안과 AI 계약·Pydantic·예시·CHANGELOG 수정 책임, 계약 버전·Hash 재고정
  조건을 명시했다.
- `AI_RESULT`를 Event 이름으로 사용하던 표현을 제거하고 State 계약의
  `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE`와 실제 전이·Guard
  책임을 반영했다.
- 현재 증거를 `101 passed, 3 warnings`, 구조화 결정 규칙 12/12 PASS, 후보
  Source Commit `1590279b7c7aea66334b3436024a83b150e28610`으로 갱신했다.
- 추가 문진 답변·거절과 질문 비반복 왕복, 비UUID 외부 Header 정규화를 포함해
  공동 E2E를 12개 Case로 확장했다.
- 이번 연동 대상을 `SingleRAGPipeline` 기준선으로 고정하고 T-025 Selective
  Pipeline과 다중 에이전트 Runtime은 후속 범위로 분리했다.
- 전달 대상 19개 파일·디렉토리의 존재 여부와 문서의 기준선 SHA·계약 Hash·
  State Event·E2E ID를 로컬에서 대조했다. 문서만 변경했으므로 단위 테스트는
  다시 실행하지 않았다.

### 2026-08-10 Backend↔AI 수직 연동 P0·P1·AI Fixture Gate

- 최지용의 2026-08-08 수직 연동 회신 기준을 반영하여 모든 AI 공개 계약의
  `correlation_id`를 일반 문자열에서 UUID로 제한했다. 요청 범위를 좁히는
  호환성 파괴 변경이므로 계약 버전을 `2.0.0`으로 갱신했다.
- Request·Response·Error JSON Schema, Pydantic 모델, 상담 요약·기사 보고를
  포함한 모든 공개 예시를 같은 UUID 규칙으로 맞췄다.
- Header와 Body의 서로 다른 유효 UUID는 HTTP 400으로 거부하고, 비UUID Body
  입력은 HTTP 422로 거부하되 잘못된 값을 오류 Body·Header에 Echo하지 않고
  `correlation_id=null`로 반환하도록 오류 경계를 고정했다.
- Backend 동일 환경 제공물
  `ai/configs/backend_integration_environment.json`과 실행 가능한
  `ai/scripts/smoke_test.py`를 추가했다. 실제 Uvicorn Mock 실행에서 Health,
  Analyze HTTP 200, Header·Body 추적 ID Echo를 PASS했다.
- `ai/evaluation/datasets/backend_integration/fixture_manifest.json`에 F01~F12의
  입력 파일·실행 Driver·기대 HTTP·핵심 응답·책임자를 기록했다. 장애와
  Timeout은 운영 경로의 공개 스위치가 아니라 교체 가능한 테스트 Adapter로
  결정적으로 검증한다.
- Fixture 전용 검증은 `12 passed`다. 이는 Manifest 1개와 F01~F10·F12 AI 구간
  11개이며, F11 Backend stale 차단이나 실제 pgvector·Backend 저장 E2E 완료를
  의미하지 않는다.
- Metadata는 현재 응답 제공 필드와 미제공 필드를 분리한
  `20260810_이동윤_최지용_Backend_AI_선행제공물_및_Metadata_결정요청_v0.1.md`를
  작성했다. `execution_metadata` 추가는 Backend의 추가 계약 승인 전까지
  구현하지 않았다.
- Python `3.13.13`에서 전체 AI 단위 테스트 `115 passed, 3 warnings`, Prompt
  Registry 검증 Exit Code 0, `git diff --check` Exit Code 0을 확인했다.
- 검증 시점 Source HEAD는
  `f3c66b3cbfd41852440bf0726722438612d6885f`, Branch는 `dongyoon`, 변경분은
  아직 Commit되지 않아 Dirty 상태다.
- 주요 SHA-256은 Symptom Request
  `008D2066DD7CE6B84BAA633F4B913ED642ADD90CA0B11591378D2987D1F54FCA`,
  Symptom Response
  `E0BC73AAF1D0747F63E1229F351165D2BEB8563CF0386D31959D10BCF70AD5AE`,
  AI Error
  `127C9D7D14D7121E1965D5D78B29AD5831210C49E6362586D92F098DD9CB9A0E`,
  Fixture Manifest
  `36D0DDF12BD06CFC3A58FCBAF1E97F496B494EBA2C16E132C13F00B52F2A9F4E`,
  실행환경 Manifest
  `BD185D2ACC6ABFD95C8D0F64356BA6C178ACB9C497EBD3D196BC0B460EE3C88D`다.
- 잔여 Gate는 실제 pgvector F01·F02 Local HTTP, Backend Mock·Local 소비,
  F11 stale 저장 차단, F12 답변·거절 저장·버전 증가, Metadata 추가 계약 승인,
  팀 DB Migration·권한·canonical evidence 연결이다.
- 최지용 요청 문서의 AI 선행 제공물 필드 순서를 그대로 따른 전송용
  `sender=이동윤` 회신 블록을 협업 문서 0절에 추가했다. 공동 검증 후
  `reviewer=최지용`이 작성해야 하는 Backend 완료 회신은 대신 작성하지 않았다.

### 2026-08-10 Backend↔AI 추가확인 03·04·05 우선순위 구현

- 위험 자연어를 Backend가 임의 해석하지 않도록 안전 규칙에 안정적인
  `SAFETY-...-NNN` ID를 부여하고 `SafetyAssessment.matched_safety_rule_ids`를
  Pydantic·JSON Schema·예시·F03 Fixture에 필수로 추가했다. 필수 응답 필드가
  늘어난 호환성 파괴 변경이므로 AI 계약을 `3.0.0`으로 올렸다.
- 승인 RAG JSONL 7건의 `chunk_id`, 문서·페이지·모델·세대·검증 상태, Source
  Hash와 청크 본문 SHA-256을 `ai/configs/canonical_evidence_identity.json`에
  고정했다. AI는 Backend `DocumentChunk.public_id`를 생성하지 않으며 실제
  Crosswalk는 Backend·Database 책임으로 남겼다.
- 결정론적 단일 Workflow와 pgvector의 실제 실행 식별값을
  `ai/configs/runtime_identity.json`에 기록했다. 외부 LLM을 사용한다고 주장하지
  않으며, 값은 고객 응답이 아니라 Backend 환경 설정과 `AIRun` 감사 레코드로
  전달한다.
- 일반 안내 계약 예시의 구형 비공식 청크 ID를 승인 canonical ID로 교체했고,
  검색을 건너뛰는 위험 분기의 계약 예시는 근거 배열을 비워 실제 Runtime
  경계와 맞췄다.
- 03·04·05 전용 별도 회신
  `인계/20260810_이동윤_최지용_Backend_AI_수직연동_추가확인_회신_v0.1.md`를
  최지용의 원문 회신 필드 순서로 작성했다. Backend Crosswalk·계약 3.0.0 호환·
  실제 저장 E2E가 남아 있으므로 전체 `ready_for_joint_e2e`는 `NO`로 판정했다.
- Python `3.13.13`, `pip check` PASS, 전체 AI 단위 테스트 `121 passed,
  3 warnings`, Fixture Gate `12 passed`, 실제 Uvicorn Mock Health·Analyze·추적 ID
  Smoke PASS와 Local 위험 입력의 규칙 ID 2개·`TOTAL_STOP`·근거 0건을 확인했다.
  `backend/.venv`가 없어 Backend 단위 테스트 재실행은 수행하지 못했다.
- 후보 기준선 생성기의 계약 고정값을 `3.0.0`으로 맞추고 공식 후보 보고서를
  다시 생성했다. 상태는 팀 DB 재검증과 Commit이 남은
  `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT`이며 Source HEAD는
  `421e5590414a3addec62158b0b58ed37bbf97e41`, Dirty 상태다.
- 03·04·05 별도 회신 마지막에 최지용이 추가 요청한 실행값 블록을 넣었다.
  `103`은 Fixture 추가 전 중간값, `115`는 계약 2.0.0과 Fixture 12개를 포함한
  당시 최종값, `121`은 계약 3.0.0 안전 ID·근거 Identity·Runtime Identity
  검증까지 포함한 현재값으로 구분했다. 거절·모름 Payload 처리, Disposable DB
  확인값, 공동 Mock 준비 여부와 가용 시점도 함께 명시했다.

### 2026-08-10 5주차 AI 단독 선행 작업

- 현재 `dongyoon` Source HEAD
  `3485e0f1717f4afc6a5f76e469b4bb2d6bd0ecc1` 기준 환경·회귀·외부 차단을
  `docs/testing/ai/week5-ai-entry-gate.md`에 기록했다. 단일 RAG 기준선과 실제
  Multi-Agent·LLM·팀 DB·Backend HTTP 미완료를 분리하고 담당자·필요 입력·해제
  조건을 붙였다.
- `docs/testing/ai/week5-multi-agent-contract-draft.md`에 Supervisor와 6개 역할
  Agent의 책임, 입출력·State 쓰기 소유권, Routing Matrix, Handoff Log 최소
  필드, 최대 Hop 8, Timeout·Retry·Fallback과 활성화 Gate를 정의했다. 이 문서는
  목표 계약이며 현재 Runtime 구현 완료 증거가 아님을 명시했다.
- 설명 한 줄뿐이던 상담 요약 Generator·Formatter를 외부 LLM 없이 실행 가능한
  결정론적 Fallback으로 구현했다. 고객 진술·전달된 상담 기록·기존 안전 판정만
  사용하고 확정 진단, 방문 자동 확정, Backend 상태 변경은 수행하지 않는다.
- 상담 요약 정상·위험·위험 부정문·계약 길이 경계 Test 4건을 추가했다. 생성
  결과는 `ConsultationSummaryResponse` JSON Schema로도 검증한다.
- 상담 요약 위험 Test에서 자연스러운 표현 `물이 새고`가 구조화에는 누수로
  잡히지만 안전 키워드에는 일치하지 않는 공백을 발견했다. 안전 SSOT에 해당
  표현을 추가하고 `SAFETY-LEAK-001` 회귀 Test를 추가했으며 Runtime Identity의
  Safety 설정 Hash를 갱신했다.
- Python `3.13.13`, `pip check` PASS, 전체 AI 단위 Test `126 passed,
  3 warnings`, 실제 Uvicorn Mock Smoke PASS를 확인했다. Local 실제 HTTP에서
  `물이 새고` 입력이 `danger`, `SAFETY-LEAK-001`, `TOTAL_STOP`, 근거 0건으로
  반환되는 것도 확인했다.
- 공식 후보 보고서를 `126 passed`와 Source HEAD `3485e0f...`로 다시 생성했다.
  변경분은 아직 Commit되지 않았고 팀 DB 재검증도 남아 있어 상태는
  `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT`이다.
- 최지용 추가확인 회신의 최신 단위 Test 값을 `126 passed`로 갱신하고
  `103→115→121→126`의 각 증가 범위를 분리해 적었다.

### 2026-08-10 한예나 EvidenceCard 추가확인 회신

- 한예나의 공개 EvidenceCard JSON·필수/NULL·`page_refs`·Enum·Fallback·미지원
  제품·Crosswalk·일정 질문 순서를 유지한 별도 회신
  `인계/20260810_이동윤_to_한예나_AI_RAG_EvidenceCard_추가확인_회신_v0.1.md`를
  작성했다.
- 현재 승인 청크의 실제 값만 사용해 MVP 공개 Enum을
  `text_and_visual_verified`, `official_manual`, `official`로 닫고, 확장 값은
  계약 Version 변경 전까지 Web이 임의 수용하지 않도록 했다.
- `page_refs`는 1 이상의 정수 배열·오름차순·중복 없음으로 정의하고 단일
  `[37]`, 다중 `[38, 39]` 예시를 제공했다. Web 대표 페이지는 첫 항목을 쓰되
  전체 배열을 DTO에서 보존하도록 명시했다.
- AI `chunk_id`→Evidence Registry `source_id`→`evidence_id`까지는 AI 원천
  Mapping으로 확정하고, Backend `DocumentChunk.public_id` 연결·검증·최종 DTO
  조립은 최지용 책임으로 분리했다.
- 미지원 제품·세대는 현재 검색 전 정책 차단되지만 별도 공개 AI 오류 계약이
  없어 근거 0건 Fallback과 같은 외형이라는 공백을 기록했다. Backend 선차단
  HTTP Status·Error Code는 최지용 확정 전까지 임의 생성하지 않았다.
- Mock Projection·Mapper는 진행 가능하지만 실제 Backend Remote API와 Web E2E는
  Runtime Evidence 계약 확정 전까지 완료로 표시하지 않는다.

### 2026-08-10 P0 AI 독립 선행 Gate 재검증

- `dongyoon@9f28c1ca9c0f3dba8e29c2fb99de31bac6618b02`에서 Python
  `3.13.13`, `pip check=PASS`, AI Unit `126 passed, 3 warnings`를 다시
  확인했다. 작업 트리는 이 기록과 후보 기준선 갱신을 포함해 Dirty이므로 최종
  통합 PASS로 승격하지 않았다.
- 실제 Uvicorn에서 Health, Mock Analyze HTTP 200, Local 일반·주의의 Vector
  미설정 HTTP 503, Local 누수·전기 위험 HTTP 200을 검증했다. 위험 응답은
  `SAFETY-LEAK-001`, `SAFETY-ELECTRICAL-001`, `TOTAL_STOP`, Evidence 0건과
  `correlation_id` Header·Body 추적을 만족했다.
- Backend Integration Fixture F01~F12는 `12 passed, 1 warning`이다. 팀 DB
  pgvector Test는 Secret이 없어 `1 skipped`이며 개인 격리 DB 이력을 현재 팀 DB
  PASS로 대체하지 않았다.
- 일반 적재·검색 경로는 DDL을 실행하지 않고, Schema 초기화는 별도 Disposable
  명령과 `DISPOSABLE_ONLY`·DB 이름 Guard를 모두 통과해야만 실행되는 것을
  확인했다.
- `docs/testing/ai/week5-ai-entry-gate.md`의 Source HEAD와 증거를 갱신하고 팀 DB
  책임을 `최지용 제공·Migration / 이동윤 AI 실행 / 김은진 QA 판정`으로
  분리했다. 외부 LLM·Multi-Agent는 팀 DB·Backend E2E 기준선 이후 P1 비교
  대상으로 유지했다.
- `ai/evaluation/reports/official_mvp_baseline_20260803.json`은 현재 HEAD로 다시
  생성했으며 상태는 `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT`이다.

### 2026-08-10 AI venv·설치 방식 SSOT 확정

- 김은진의 `pip install .\ai` 실패 보고를 `--dry-run --no-deps
  --no-build-isolation`로 재현했다. Editable 설치도 `app`, `configs`, `prompts`,
  `evaluation` 복수 최상위 Package 자동 탐색으로 동일하게 실패했다.
- 저장소 Root의 `import ai.app.main`은 PASS하고 저장소 밖에서는 Import되지 않는
  것을 확인해 현재 실행 구조를 `MONOREPO_SOURCE_RUNTIME`으로 확정했다.
- 공식 설치 SSOT를 `ai/requirements.lock`으로 유지하고 Package·Editable·Wheel
  설치는 지원하지 않는다고 Root·AI README와 `ai/pyproject.toml`에 명시했다.
- pyproject·requirements.txt 직접 의존성 10건의 이름·Extra·Version과 Lock의
  직접·Extra 전이 Package를 비교하는 회귀 Test를 추가했다.
- Python `3.13.13`, `pip check=PASS`, 전체 AI Unit `127 passed, 3 warnings`를
  확인하고 김은진 회신
  `인계/20260810_이동윤_to_김은진_AI_venv_설치방식_SSOT_확인회신_v0.1.md`에
  재현 결과와 공식 명령을 기록했다.

### 2026-08-10 Backend·AI P0-2 공동 Mock 착수

- AI 변경 `b65a8bd...`와 최지용 회신 기준 Backend `57326cf...`가 Merge Commit
  `4d955116c00f715e1ba9e465104a381b858996b9`으로 통합된 것을 확인했다.
- 통합 Commit의 Clean 작업 트리에서 Python `3.13.13`, `pip check=PASS`, AI
  Unit `127 passed, 3 warnings`, Backend Integration Fixture `12 passed,
  1 warning`을 재검증했다.
- 실제 Uvicorn을 기동해 `/health`, Mock Analyze HTTP 200과 Body·Header
  `correlation_id` 추적을 검증한 뒤 Process를 종료했다.
- 원격 `main`, `jiyong`을 갱신해 확인했지만 Initial Symptom Wiring 후보는 아직
  없었다. 현재 Runtime에는 Follow-up 답변의 `transaction.on_commit` 재분석만
  있고 `SUBMIT_SYMPTOM`의 최초 AI 호출점은 없다.
- 최지용에게 전달할
  `인계/20260810_이동윤_to_최지용_Backend_AI_P0_2_공동Mock_착수회신_v0.1.md`를
  작성하고 후보 검토·공동 Mock 판정값을 고정했다.

### 2026-08-11 Experiment Lab B1 청킹 비교

- 실험 계획 v2.1의 A1·A2 재현 Gate를 다시 실행했다. Windows CRLF 체크아웃에서
  Canonical JSONL Hash가 달라지던 문제를 LF 정규화 SHA-256과 Git Attribute로
  고쳤다. Full Corpus 96건 Hash는 `6947CDE...`, Gold 60건 Hash는
  `DDB20527...`이며 Dataset QA는 `STRUCTURAL_PASS_HUMAN_REVIEW_PENDING`이다.
- Experiment Playground Router를 기본 AI Runtime에서 닫고
  `AI_ENABLE_EXPERIMENT_PLAYGROUND=true`를 명시한 LAB Process에서만 등록하도록
  바꿨다. 기본 Mock·Local App에서 Experiment 경로는 HTTP 404다.
- B1 청킹 Profile 6종을 정의했다. 현재·Page·Fixed 512·Section·Parent/Child
  5종은 실행 가능하고, `table_row_v1`은 원문에 표 행 경계 Metadata가 없어
  `BLOCKED_SOURCE_STRUCTURE_UNAVAILABLE`로 남겼다.
- BGE-M3 CPU에서 DEV 35건 × Profile 5종 × Product Filter 2모드, 총 350건을
  실행했다. Exact Filter Draft 결과에서 Parent/Child는 Hit@1 `0.703704`, MRR
  `0.790123`으로 가장 높았고, Section은 Hit@5 `0.925926`이지만 Hit@1
  `0.481481`, 최대 1,112 token, Cold Embed `256.835s`로 상위 근거가 약했다.
- 모든 Profile의 무근거 중단 정확도가 `0.25`였다. 가격·렌탈료·색상 3건은
  Retrieval 오탐, JAC104 제빙 3건은 Scope Filter 공백으로 자동 1차 분류했다.
  청킹을 운영 변경하지 않고 Retrieval·Policy·Reranker 실험을 다음 순서로 뒀다.
- 동일 Evidence의 중복 Child가 nDCG를 부풀리지 않도록 최초 적중 1회만 Gain으로
  계산한다. 콘텐츠 해시 기반 임베딩 Cache를 Git 제외 `tmp/`에 두어 Cold 실행
  약 `608.879s`, 동일 입력 Warm 재실행 약 `1.841s`를 구분했다.
- Source HEAD는 `b5c324b8299866b465aceed06c322a872dc2353a`, 변경분은 Dirty다.
  Python `3.13.13`, AI Unit `147 passed, 3 warnings`, `pip check=PASS`,
  Backend Integration Fixture `12 passed, 1 warning`을 확인했다. Gold 2인 검수,
  IAC425 양성 문항, PM 상위 후보 Gate와 Initial Symptom Backend 후보 Commit은
  여전히 미완료다.

### 2026-08-11 Experiment Lab B2-1 Threshold·Scope Policy 비교

- B1 Draft 후보 `fixed_512_v1`, `parent_child_v1`에 Exact Product Filter를 고정하고
  Threshold 7개와 Scope Policy 적용/미적용을 조합해 DEV 35건, 총 980개 결과를
  실제 BGE-M3로 실행했다.
- 운영 `scope_filter.py`가 Placeholder인 상태를 구현 완료로 취급하지 않았다.
  제품 코드와 명시적 기능어만 사용하는 Experiment 전용
  `ExperimentalQueryScopePolicy`를 별도로 만들고 Gold Label을 정책 입력에서
  배제했다.
- Parent/Child 기준 Scope 미적용은 Threshold `0.4~0.5`에서 Hit@1 `0.703704`,
  Hit@5 `0.888889`, MRR `0.790123`, 무근거 중단 `0.25`였다. Scope 적용 후 양성
  수치는 유지되고 무근거 중단은 `0.625`로 개선됐으며 양성 오차단은 0건이었다.
- Threshold `0.55`는 무근거 1건을 더 중단하지만 정상적인 맛·냄새·출수량 질의
  3건의 Top-5 근거를 잃었다. `0.6`은 무근거 중단 `1.0` 대신 양성 Hit@5가
  `0.518519`로 떨어져 Threshold 단독 상향은 부적합하다고 판정했다.
- 남은 오탐은 렌탈료·필터 판매 가격·외관 색상 3건이다. 단어를 운영 규칙에 바로
  Hard-code하지 않고 Knowledge Domain·Query Intent 표현 변형 Dataset과 담당자
  승인을 다음 Gate로 남겼다.
- Source HEAD는 `df96616d7010a2f61bddc91f8974235ba5ec92d3`, Dirty 상태이며 결과는
  `DRAFT_THRESHOLD_SCOPE_EXPERIMENT_COMPLETE`다. Gold 2인 검수·IAC425 양성
  문항·PM Gate 전에는 운영 Threshold나 Scope Policy를 변경하지 않는다.
- Python `3.13.13`, AI Unit `150 passed, 3 warnings`, `pip check=PASS`, Backend
  Integration Fixture `12 passed, 1 warning`을 확인했다. 실험용 Scope Policy는
  운영 FastAPI Pipeline과 Mock Fixture 호출 경로에 연결하지 않았다.

### 2026-08-11 Experiment Lab B2-2 Query Intent·Domain Policy 비교

- B2-1에서 남은 렌탈료·필터 판매 가격·외관 판매 색상 3종을 대상으로 계약·결제,
  부품 가격·구매, 상품 옵션 Intent Rule을 Experiment Lab에만 구현했다. 단일
  Keyword가 아니라 용어 Group의 결합과 명시적 예외를 사용하고 Gold Label은
  정책 입력에서 배제했다.
- 운영 Gold와 분리된 표현 변형 DEV 18건을 만들었다. 차단 9건과 렌탈 제품 고장,
  필터 교체, 외관 청소 같은 허용 Hard Negative 9건을 균형 구성했으며 전부
  `UNREVIEWED_DRAFT`, 승인자 0명이다.
- BGE-M3에서 `parent_child_v1`, Threshold `0.5`, Exact Product Filter,
  `MODEL_CAPABILITY_SCOPE_V1`을 임시 고정했다. 표현 변형 정책 판정은 18/18이었고
  오차단·누락은 0건이었다. 이는 정책과 함께 만든 미검수 DEV 결과이므로 독립
  일반화 성능으로 사용하지 않는다.
- Gold DEV 35건의 무근거 중단은 `0.625`에서 `1.0`으로 개선됐고 양성 오차단은
  0건이었다. Hit@1 `0.703704`, Hit@5 `0.888889`, MRR `0.790123`은 변하지 않아
  Intent Policy가 Retrieval 품질 자체를 개선한 것은 아니다.
- 남은 양성 실패는 Top-5 누락 3건과 순위 오류 5건이다. 다음 B2-3에서는
  Keyword/BM25와 Dense를 Case 단위로 비교해 누락 복구 가능성을 확인한 뒤
  Hybrid, Reranker 순서로 진행한다.
- 실행 결과는 `DRAFT_QUERY_INTENT_DOMAIN_EXPERIMENT_COMPLETE`이며 Gold·표현
  변형 2인 검수, IAC425 양성 문항, PM Gate 전에는 운영 `scope_filter.py`나
  FastAPI Pipeline에 연결하지 않는다.
- Python `3.13.13`, AI Unit `153 passed, 3 warnings`, `pip check=PASS`, Backend
  Integration Fixture `12 passed, 1 warning`, `git diff --check=PASS`를 확인했다.

### 2026-08-11 Experiment Lab B2-3 BM25·Dense 비교

- B1의 상위 Draft 청킹 후보 `fixed_512_v1`, `parent_child_v1`에서 Gold DEV 35건,
  Dense·BM25 2방식을 비교해 총 140개 Case 결과를 만들었다. Exact Product Filter,
  B2-1 Scope, B2-2 Intent Policy와 Top-K 5를 동일하게 고정했다.
- BM25는 외부 형태소 사전 없이 재현 가능한 단어·한글 문자 bigram Analyzer와
  `k1=1.5`, `b=0.75`를 사용하는 Experiment 전용 구현이다. 운영
  `keyword_search.py`와 `hybrid_search.py` Placeholder는 구현 완료로 바꾸거나
  Runtime에 연결하지 않았다.
- Parent/Child에서 Dense는 Hit@1 `0.703704`, Hit@5 `0.888889`, MRR `0.790123`,
  무근거 중단 `1.0`이었다. BM25는 Hit@1 `0.481481`, Hit@5 `0.666667`, MRR
  `0.540123`, 무근거 중단 `0.875`로 낮았다.
- BM25가 Dense 누락을 복구한 Case는 0건이었다. Dense만 성공한 Case는 6건이고
  양쪽이 함께 놓친 Case는 누수·무출수 간접 표현 3건이다. 따라서 현재 DEV에서
  Hybrid Oracle Union Hit@5도 Dense 단독과 같은 `0.888889`다.
- 단순 Hybrid·Reranker 착수는 보류했다. 양쪽 누락은 후보에 정답이 없으므로
  `물이 새다→누수`, `안 나오다→출수되지 않음`, `바닥이 흥건하다→누수` 같은
  검수 가능한 Alias Query Expansion을 B2-4 Draft로 먼저 비교한다.
- 실행 결과는 `DRAFT_RETRIEVAL_METHOD_COMPARISON_COMPLETE`이며 Gold 2인 검수,
  Alias 승인, IAC425 양성 문항, PM Gate 전에는 운영 검색 설정을 변경하지 않는다.
- Python `3.13.13`, AI Unit `156 passed, 3 warnings`, `pip check=PASS`, Backend
  Integration Fixture `12 passed, 1 warning`, `git diff --check=PASS`를 확인했다.

### 2026-08-11 Local RAG 격리 pgvector 및 HTTP Runtime 검증

- Docker의 격리 `pgvector/pgvector:pg16` 환경에서 Disposable Guard를 통과한 뒤
  Schema를 초기화하고 승인 청크 7건을 두 번 UPSERT했다. 두 실행 모두 저장 행은
  7건으로 유지되어 동일 청크 ID의 멱등성을 확인했다.
- PostgreSQL `16.14`, pgvector `0.8.6`, Embedding 1024차원, Chunk Set Hash
  `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958`을
  확인했다. 격리 평가 12/12는 실제 `PGVECTOR_QUERY` 7건과 검색 전 정책 차단
  5건이며, Recall@5 `1.0`, MRR `0.885714`, 금지 Hit 0이다. 이 수치는 팀 DB
  완료나 전체 제품 성능으로 확대하지 않는다.
- 최초 실제 `mode=local` HTTP 요청은 BGE-M3가 요청 안에서 초기화되어 약 30초
  후 HTTP 504 `AI-TIMEOUT-01`로 종료됐다. DB 검색 0건으로 처리하지 않고 Runtime
  객체 수명 문제로 분리했다.
- 동일 설정의 `VectorSearchService`와 Embedding Client를 Process에서 공유하고,
  `AI_VECTOR_DSN`이 설정된 경우 FastAPI 시작 단계에서 모델을 Warmup하도록
  수정했다. 모델 초기화와 Encode에 Lock을 적용해 동시 요청의 중복 초기화도
  차단했다. 계약의 전체 요청 Timeout 30초와 Backend 자동 재시도 0회는 변경하지
  않았다.
- 수정 후 실제 HTTP 2회는 각각 약 `479ms`, `158ms`에 HTTP 200 `SUCCEEDED`,
  `retry_count=0`, Evidence 5건으로 완료됐다. 첫 Evidence는
  `RAG-WPUJAC104DWH-COLD-TEMPERATURE-001`이고 Header·Body Correlation도
  일치했다.
- Python `3.13.13`, AI Unit `159 passed, 3 warnings`, 실제 pgvector Integration
  `1 passed`, 격리 평가 `12/12 PASS`를 확인했다. Canonical AI 청크 ID 7건은
  고정됐지만 Backend `knowledge_document_chunk.public_id` Crosswalk와 팀 DB
  Migration·최소권한 DSN 검증은 Backend/DB 담당 입력 전까지 미완료다.

### 2026-08-11 No Evidence Fallback 계약 정합성 수정

- 실제 AI 근거 없음 Runtime이 `FALLBACK`, `RETRIEVING`, 빈 Evidence와
  `PENDING_CONSULTATION`은 반환하지만 `SafetyAssessment.requires_consultation`을
  `false`로 유지해 Backend `NO_EVIDENCE` 불변식에서 거부되는 간극을 확인했다.
- `safety_rules.yaml`의 근거 없음 정책에 `caution`,
  `consultation_recommended`, `requires_consultation=true`와 안전 사유를 명시하고
  `SafetyRuleLoader`가 해당 고정값을 시작 시 검증하도록 했다. 설정 변경에 맞춰
  `runtime_identity.json`의 안전 규칙 SHA-256도 갱신했다.
- Generation Stage는 근거 없음이면서 danger가 아닌 경우 SafetyAssessment와
  UsageGuidance를 함께 정규화한다. Danger 우선 분기와 Vector 구성 실패의 HTTP
  503 경계는 변경하지 않았다.
- 실제 `PipelineRouter`의 근거 없음 출력을 Backend `map_success_response`에
  전달해 `NO_EVIDENCE`, `requires_consultation=true`,
  `PENDING_CONSULTATION` 통과를 확인했다.
- AI Unit `159 passed, 3 warnings`, Backend AI Integration `23 passed`,
  `pip check=PASS`, `git diff --check=PASS`다. Backend의 `DANGER_DETECTED` 무조건
  보류 문제는 Backend 담당 수정 항목으로 남아 있다.

### 2026-08-12 Retrieval Policy Identity Hash 정합성 수정

- D-03 Answerability·Capability Gate 추가 이후 `retrieval_policy.yaml`의 내용은
  변경됐지만 `runtime_identity.json`의 `configuration_sha256.retrieval_policy`가
  이전 값으로 남아 있던 불일치를 수정했다.
- 프로젝트 검증 규칙과 동일하게 CRLF를 LF로 정규화한 SHA-256
  `1AD4C4DB9E63233DE4694D77F078436095D83F2F41309DE382E9E48D128797D8`을
  기록했다. 파일 원본 바이트의 줄바꿈 차이는 Runtime Identity 변경으로
  취급하지 않는다.
- 설정·Schema 단위 테스트 `39 passed, 2 warnings`, AI 전체 단위 테스트
  `167 passed, 3 warnings`를 Python `3.13.13`에서 확인했다.

### 2026-08-12 P0-2 공동 Mock 후속 확인·회신

- 원격 `main@382ddc5933d0ec63a38778a0c78d037c351b7128`을 Fetch한 뒤 AI 작업
  Branch에 병합했다. AI 고유 No-Evidence Runtime 정합화와 Runtime Identity Hash
  수정은 제품 Runtime에 필요하므로 `MAIN_MERGE_REQUIRED`로 판정했다. 병합 Commit
  `c70e9f79c87db0b88c029e3fdcfa3018c6593d89`가 `origin/dongyoon`에 Push된 상태도
  원격 Fetch로 재확인했다.
- Python `3.13.13`, `pip check=PASS`, AI 전체 단위 테스트
  `167 passed, 3 warnings`를 최신 main 병합 상태에서 확인했다.
- 실제 Uvicorn Mock과 Backend Live HTTP Test를 재실행해 `/health` 200과 정상
  제출·Replay `1 passed`를 확인했다. 신규 AI 호출 1회, Replay 추가 호출 0회,
  계약 `3.0.0`, Correlation과 AIRun·Assessment·Guidance 저장을 함께 검증했다.
- 실제 공동 HTTP 503·Timeout은 실행하지 않아 `NOT_RUN`으로 유지하고, 기존
  결정적 오류 경계·독립 QA 증거를 사용하는 `KEEP_NOT_RUN`으로 회신했다.
- `docs/individual/dongyoon/인계/20260812_이동윤_to_최지용_P0-2_공동Mock_후속정보_회신_v0.1.md`에
  Branch·병합 상태, 명령·Exit, P0-2 완료 경계와 PM 결정 요청을 기록했다.

### 2026-08-12 Experiment Lab B2-4 Alias Query Expansion 비교

- B2-3의 양쪽 누락 가설을 이어 받아 Parent/Child Dense 원문 Query와 Draft Alias
  확장 Query를 동일 Gold DEV 35건에서 비교했다. B2-3 이후 Gold Dataset Hash가
  변경돼 B2-4 안에서 원문 Dense 대조군을 다시 실행했다.
- 누수 Alias는 `RAGV2-GOLD-0027`을 Top-5 밖에서 3위로 복구하고 `0021`을
  2위에서 1위로 개선했다. 무출수 Alias는 `0025`를 복구하지 못해 Rule별 판정을
  각각 `SUPPORTED_ON_DRAFT_DEV_PENDING_REVIEW`,
  `NOT_SUPPORTED_ON_CURRENT_DRAFT_DEV`로 분리했다.
- DEV Positive Hit@5는 `0.925926`에서 `0.962963`, MRR은 `0.783951`에서
  `0.814815`로 변했다. Positive 회귀 0, 무근거 8건 회귀 0, 잘못된 제품 Hit 0을
  확인했다.
- 부정형과 비제품·다른 원인의 문맥을 포함한 Hard Negative 7건을 추가했다. 초기
  과활성화 3건을 확인해 명시적 제외 조건을 보강했고 최종 예상 밖 활성화 0을
  확인했다.
- 결과는 `DRAFT_ALIAS_CANDIDATE_PARTIALLY_SUPPORTED_PENDING_REVIEW`이며 운영
  Pipeline·검색 정책·Corpus·Evidence·Backend 계약은 변경하지 않았다. 누수 Alias는
  Data Owner 검수와 Gold 승인 뒤 TEST·SAFETY 독립 검증이 필요하다.

### 2026-08-12 P0-2 AI main 병합 후 최종 ACK

- 원격 `main@78b4c45f47b58ce10f0415c804ae959aeeaaf0d7`에 승인된 No-Evidence
  Runtime Commit `50a135bb839ebaa753d11e891220cf793bd32bae`와 Runtime Identity Hash
  Commit `f001e7065c9c0af8604dc1295ffcbc690c883047`이 포함됐음을 확인했다.
- 과거 Branch 검증을 복사하지 않고 정확한 `origin/main` SHA를 Detached Checkout해
  Python `3.13.13`, `pip check=PASS`, AI 전체 `172 passed, 3 warnings,
  7 subtests passed`를 다시 실행했다.
- 같은 SHA에서 Uvicorn `/health` HTTP 200과 Backend→AI 정상 제출·Replay Live
  Smoke `1 passed`를 확인했다. 신규 AI 호출 1회와 Replay 추가 호출 0회,
  계약 `3.0.0`, Correlation, AIRun·Assessment·Guidance 저장을 함께 검증했다.
- 실제 공동 HTTP 503·Timeout은 합의대로 `NOT_RUN`을 유지하고 P0-2 최종 AI
  ACK를 `APPROVE`, 잔여 P0-2 Blocker를 `NONE`으로 회신했다.
- `docs/individual/dongyoon/인계/20260812_이동윤_to_최지용_P0-2_AI_main병합후_최종ACK_v0.1.md`에
  최종 main SHA, 명령·Exit, 완료·비완료 경계를 기록했다.

### 2026-08-12 B1 행 단위 Parent·Child 구조 결정 회신

- B1 데이터 전처리 보완안의 검색 후보, Evidence 판정과 Runner 연결 방식을 AI
  관점에서 검토하고 `Child 검색 → 선택 Child의 Parent Context 중복 제거 확장`을
  목표 구조로 결정했다. Top-K·Hit·MRR·`ANY`·`ALL`은 Child의 실제 Evidence만으로
  계산하고 Parent를 검색 정답으로 중복 계산하지 않는다.
- Parent와 Child 동시 검색은 동일 근거의 Top-K 중복 점유, Parent 다중 Evidence에
  의한 `ALL` 과대평가와 실패 원인 혼합 때문에 제외했다. Child-only는 검색 대조군으로
  유지하되 최종 Runtime 구조로 고정하지 않는다.
- 누수 5·7·38쪽은 대표 Evidence Group 하나와 페이지별 Source Variant로 분리하고,
  Group ID만 정답 판정에 사용하며 Variant ID는 출처 역추적에 사용하도록 결정했다.
- 기존 B1 v1을 즉시 변경하지 않고 experimental v2 Adapter로 검증한 뒤 행 경계,
  Child 단일 Evidence, Child→Parent 연결, 영향 11건과 정상 통제 표본을 검수한 경우에만
  정식 v2 승격을 검토한다.
- `docs/individual/dongyoon/인계/20260812_이동윤_to_김은진_B1_행단위ParentChild_구조결정_회신_v0.1.md`에
  대안별 제외 근거, Dataset 필수 필드, 평가 출력 계약과 실행 Gate를 기록했다.

### 2026-08-12 D04 행 단위 Parent·Child 부분 진단 실행

- D04 Parent 5건·Child 15건을 기존 Full Corpus v1의 대상 페이지 5건과 부분 교체한
  106개 후보에서 영향 11건과 정상 통제 5건을 BGE-M3 고정 Revision, Exact Product
  Filter, Top-K 5, Threshold 0.4로 실행했다. 결과 상태는 전체 B1이 아닌
  `PARTIAL_SCOPE_DIAGNOSTIC_COMPLETE`로 제한했다.
- 행 단위 Child는 기존 Top-5 밖이었던 무출수 `0025`를 2위, 바닥 누수 `0027`을
  4위로 복구했다. 선택 16건 Hit@5는 `0.875`에서 `1.0`, MRR은 `0.677083`에서
  `0.767708`로 변했고 정상 통제 Hit@5·순위 회귀는 0건이었다.
- 영향 Case 중 `0021`은 2위에서 5위, 복합 `0038`의 Completion Rank는 1에서 2로
  회귀했다. 평균 개선만으로 전체 성공을 판정하지 않고 Full Corpus v2 재검증
  대상으로 남겼다.
- Child와 동일 순위를 공유하는 페이지 Parent Context 확장은 평균 Context를
  342.2에서 825.9 whitespace token으로 늘렸다. 16건 중 15건에 다른 Evidence
  Group이, 12건에 제외된 미세입자 행이 포함돼 전체 페이지 Parent를 기본 Context로
  쓰는 안은 `NOT_SUPPORTED_AS_DEFAULT_PENDING_REDESIGN`으로 판정했다.
- 평가 계약, experimental Profile, Adapter, 단위 테스트와 실행 결과를 추가했다.
  운영 Pipeline·Corpus·`retrieval_policy.yaml`·Backend 계약은 변경하지 않았다.
- Python `3.13.13`에서 AI 전체 단위 테스트 `174 passed, 3 warnings,
  7 subtests passed`, `pip check=PASS`, `git diff --check=PASS`를 확인했다.
- `docs/testing/rag/d04-row-child-partial-diagnostic-result_20260812.md`에 Case별 결과,
  Context 비용, 제한과 다음 bounded Context 설계 Gate를 기록했다.
- 공유 시 부분 Corpus 106건을 Full Corpus v2로 오해하지 않도록 결과서에 Corpus
  경계를 보완했다. Full Corpus v1은 JAC104 44쪽과 IAC425 52쪽의 페이지 Chunk
  96건이며, 이번 후보는 그중 지정 5쪽을 선택 Child 15건으로 교체한 부분 진단
  Corpus다. 전체 검색 가능 원문 보존, 제품 범위 유지와 전체 Gold·NO_EVIDENCE
  재실행을 Full Corpus v2의 선행 조건으로 명시했다.

### 2026-08-13 Backend AI Timeout 상담 전환 Gate 회신

- 현재 Backend Timeout 경로를 코드·계약·테스트로 재검토해, HTTP Timeout이
  `AITimeoutError(http_status=504)`로 매핑되고 AIRun에는 `TIMED_OUT`,
  `AI-TIMEOUT-01`, 재시도·지연시간·완료시각이 저장되지만 상태 Event 없이
  반환되는 경계를 확인했다.
- Timeout 예외 분기는 `event_candidate=None`, `event_applied=None`이므로 현재
  `StateMachine`, Guard, `CONSULTATION_REQUIRED` 전이와 SYSTEM History에
  도달하지 않는다는 근거를 줄 번호 링크로 정리했다.
- 정상 검색 후 근거 0건인 HTTP 200 `NO_EVIDENCE`와 처리 미완료인 HTTP 504
  Timeout의 계약 의미가 다르므로, `NO_EVIDENCE` 임의 재사용 대신 Timeout SYSTEM
  Event·Guard 매핑 승인을 선행 Gate로 명시했다.
- Backend 담당을 최지용, 중요도를 P1 통합 완료 전 필수 Gate로 두고 AIRun 저장,
  상담 전환 1회, state_version·Guard, Replay·stale·History와 실제 HTTP 주입까지
  완료 조건과 회신 형식으로 고정했다.
- Python `3.13.13`에서 관련 기존 Backend 단위 테스트 3건을 실행해
  `3 passed in 5.95s`를 확인했다. Timeout 상담 자동 전환과 실제 공동 HTTP Timeout
  주입은 완료 증거가 아니므로 각각 `OPEN`, `NOT_RUN`으로 구분했다.
- 회신문과 근거표는
  `docs/individual/dongyoon/인계/20260813_이동윤_to_최지용_Backend_AI_Timeout_상담전환_Gate_회신_v0.1.md`에
  기록했다.

### 2026-08-13 GUIDANCE_ONLY OpenAI Runtime 구현

- PM 조건부 승인 기준선
  `1289d4b3673d9b061833fa94d45096bde1541a02`에서 Python `3.13.13`과 AI Unit
  `174 passed, 3 warnings, 7 subtests passed`를 변경 전 기준선으로 고정했다.
- OpenAI 공식 문서에서 `gpt-4.1-mini`의 Responses API·Structured Outputs 지원을
  확인하고, 기존 `httpx` 의존성을 사용하는 Provider Adapter를 구현했다. 공개
  Backend↔AI 계약 `3.0.0`은 변경하지 않았다.
- 내부 `GuidanceGenerationResult`는 `message`, `next_actions`만 허용한다. Safety,
  사용 안내 상태, 제한 기능, Evidence와 Correlation·요청 식별자는 결정적
  Rule·Runtime이 계속 소유한다. `next_actions`는 Runtime이 제공한
  `allowed_next_actions`의 정확한 문장만 선택할 수 있으며 새 행동을 만들면 결정적
  안내로 복귀한다.
- danger와 No-Evidence는 LLM 호출 0회로 기존 `TOTAL_STOP`과
  `PENDING_CONSULTATION` 경계를 유지한다. 공식 Evidence가 있는 일반·주의
  경로에서만 LLM을 호출하고 생성 뒤 금지 표현·행동 Validator를 적용한다.
- Provider 연결·일시 오류는 설정 SSOT에 따라 내부 최대 1회 재시도한다. 최종
  Timeout은 HTTP `504 AI-TIMEOUT-01`, `failure_stage=GENERATING`으로 반환하고,
  Schema·거부·구성 오류는 `503`으로 실패 폐쇄한다. Timeout을 HTTP 200 성공으로
  숨기지 않는다.
- 모델명, Prompt Version, 입력·출력·전체 Token, 지연시간, 재시도 횟수는 고객
  원문·Evidence 본문·Prompt·Secret 없이 구조화 로그에 기록한다.
- Fake Provider 기반 표적 테스트는 Strict Schema, Runtime 소유 필드 보존,
  danger·No-Evidence 호출 0회, 일시 오류 재시도, HTTP 504, 안전 위반 Fallback,
  Secret 부재 실패 폐쇄와 로그 비노출을 검증한다.
- 최종 검증은 AI Unit `185 passed, 3 warnings, 7 subtests passed`,
  `pip check=PASS`, `git diff --check=PASS`다. `OPENAI_API_KEY`와 팀
  `AI_VECTOR_DSN`이 아직 통합환경에 주입되지 않아 실제 Provider·팀 pgvector
  공동 HTTP 실행은 `NOT_RUN`이며 AI Runtime Gate 전체 PASS로 확대하지 않는다.

### 2026-08-13 GUIDANCE_ONLY P0 안전·팀 DB Runtime Gate 보강

- 작업 시작 기준은 Branch `codex/dongyoon-reconcile`, Commit
  `f1691df17dfdbc82283982379d9422d6a31e3c68`이다. 아래 결과는 아직 Commit되지
  않은 작업 트리 후보이며 새 통합 기준 SHA로 사용하지 않는다.
- LLM 자유 `message`가 PARTIAL_STOP과 충돌하거나 직접 분해·전선 점검, 근거 없는
  수질 안전 주장을 만들 수 있던 경로를 재현했다. 행동 지시는 `next_actions`
  Allowlist로만 허용하고, message의 상태 의미·금지 안전 주장과 승인 Evidence 문장
  일치를 최종 Gate에서 검증한다. 실제 Provider 출력이 이 Gate를 통과하지 못하면
  HTTP 성공이나 결정적 Rule 안내로 감추지 않고 Generation 실패로 종료한다.
  동일 정책을 Prompt에도 명시하고 활성 버전을 `customer_guidance/v2`로 올려
  변경 전 v1과 실행 식별자를 구분했다.
- Provider 직전 입력은 Allowlist를 통과한 증상 유형·출수 종류와 정규화된 오류
  코드만 조립하고, 전화번호·이메일·주민 식별형 번호·URL·장문 숫자를 다시
  제거한다. occurrence condition, occurrence time, 기존 조치와 자유 문진 답변에
  남을 수 있는 고객 원문은 Provider 입력에서 제외했다.
- OpenAI Responses 응답은 `status=completed`만 성공으로 인정한다. 공식 Data
  Controls 문서에 따라 요청에 `store=false`를 고정했고, 승인된 HTTPS
  `api.openai.com/v1` 이외 Base URL에는 API Key를 전달하지 않는다. 모델 Profile의
  temperature·max token도 실제 요청 Payload에 반영했다.
- OpenAI HTTP 408·504와 내부 Generation Stage 취소를 Timeout으로 보존해 최종
  HTTP 504 후보가 503으로 바뀌지 않도록 했다. 409·429·기타 5xx 연결 오류와
  Timeout의 typed 경계를 테스트로 분리했다.
- 팀 최소 권한 AI Role이 조회하는 `backend_ai_rag_chunks_v1`을
  `AI_VECTOR_TABLE_NAME`으로 선택하게 하고 검색 서비스 Cache Key에도 포함했다.
  Backend View가 소문자로 제공하는 SHA-256은 Hex 유효성을 유지하면서
  대소문자만 정규화해 Manifest와 비교한다. 팀 경로는 AI Index 적재가 아닌
  Backend 적재·Crosswalk·View 게시 후 읽기 전용 조회로 문서를 정렬했다.
  팀 Gate는 Read-only Transaction, Schema CREATE 금지, 핵심 Backend 원본 Table
  접근 금지까지 fail-closed로 확인하며 환경변수 부재를 SKIP으로 숨기지 않는다.
- Local Smoke는 HTTP 200만 확인하지 않고 계약 `3.0.0`, Inquiry·Correlation Echo,
  `SUCCEEDED`, `failure_stage=null`, 예상 Low-flow Chunk, Evidence
  개수·검증상태·HTTPS 공식 URL·페이지와 승인 Evidence 추출 문장을 확인한다.
  따라서 `FALLBACK` 200을 Runtime Gate PASS로 오판하지 않는다.
  별도 내부 Runtime Verifier는 실제 Provider 모델 계열, Prompt v2, Token 사용과
  Evidence 채택까지 확인하며, Backend 수직 E2E에서는 같은 Correlation의 AIRun에
  `openai / gpt-4.1-mini / customer_guidance/v2`가 저장됐는지 추가 대조한다.
- Python `3.13.13`에서 AI Unit `219 passed, 5 warnings, 7 subtests passed`,
  `pip check=PASS`, 독립 Interpreter의 Guidance Generator Import와 JSON Config
  Parse를 확인했다. 별도 Uvicorn Mock 실호출은 HTTP 200,
  `status=SUCCEEDED`, `failure_stage=null`, Correlation Echo를 PASS했다.
  실제 pgvector Integration은 필요한 환경변수 부재를 숨기지 않고
  `1 failed`로 종료했으며, `OPENAI_API_KEY`, `AI_VECTOR_DSN`,
  `AI_LLM_MODEL`, `AI_EMBEDDING_REVISION`, `AI_VECTOR_TABLE_NAME`이 모두
  미주입이므로 실제
  OpenAI·팀 DB·Local HTTP Gate는 계속 `NOT_RUN`이다.

### 2026-08-13 Backend-AI 실제 LLM Runtime 공동 작업 요청 회신

- 최지용의 실제 LLM·팀 pgvector·Backend 저장 공동 검증 요청을 현재
  `origin/dongyoon@7d07862e50a796e83701bda6ffd04dc974325b57`에서 재검토했다.
  이후 `origin/main@502570487510749e9e3cb4351610df5ca5e46f5f`를 Fast-forward로 반영했으며,
  검증 범위인 `ai/**`, `contracts/ai/**`, `backend/**`, `contracts/state-machine/**`에는 파일 차이가 없음을 확인했다.
- Python `3.13.13`에서 AI Unit `219 passed, 5 warnings, 7 subtests passed`,
  `pip check=PASS`, G1-A 표적 `43 passed`, Backend Evidence·Danger 표적
  `35 passed`를 확인했다.
- 실제 Runtime Verifier는 `OPENAI_API_KEY` 부재로 exit 1, 팀 pgvector Gate는
  `AI_VECTOR_DSN` 부재로 `1 failed`, exit 1을 확인했다. 환경 누락을 Skip이나
  성공으로 숨기지 않는 의도된 Fail-closed 결과이며 실제 OpenAI·팀 DB·Local
  HTTP·Backend 저장은 `NOT_RUN`이다.
- G1-A를 `BLOCKED`, G1-B를 `NOT_RUN`, 전체 Backend E2E를 `HOLD`로 회신했다.
  Secret·팀 DSN 주입 뒤 pgvector 최소권한 → 내부 LLM Runtime → Strict HTTP →
  Backend AIRun·EvidenceLink·Replay 순서로 공동 검증하도록 고정했다.
- 상세 회신은
  `docs/individual/dongyoon/인계/20260813_이동윤_to_최지용_Backend_AI_양방향로컬환경_실제LLM_Runtime_공동작업_회신_v0.1.md`에 기록했다.
### 2026-08-13 G1-A Embedding 연계·로컬 Runtime 사전 협업 회신

- 최신 `main@111da4bcd6fd8cb7e019e545254d55b3ad7406ca`로 Fast-forward한 뒤
  `rag_verified_sample.jsonl`, `canonical_evidence_identity.json`,
  `index_manifest.json`의 승인 7개 Chunk ID·Text Hash·Manifest를 재검증했다.
- 원문 SHA-256 7/7과 Chunk-set SHA-256
  `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958`의
  정본·Identity·Manifest 일치를 확인했다.
- `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`를 실제 로드해 Vector를
  메모리에서 재생성했다. 결과는 7개 모두 1024차원, L2 Normalize PASS이며
  Vector 값은 출력·저장하지 않았다.
- Backend Importer Schema·저장 경로가 아직 합의되지 않았으므로 승인 Export
  Fixture를 임의 생성하지 않고 `REPRODUCIBLE_GENERATION_ONLY`로 판정했다.
- AI 전체 Unit은 `219 passed, 5 warnings, 7 subtests passed`, `pip check=PASS`다.
  실제 OpenAI Key가 없어 Local Runtime Verifier는 의도대로 Exit 1이며
  `local_actual_llm=NOT_RUN`, 팀 G1-A는 `WAITING_ENVIRONMENT_READY`다.
- 회신:
  `docs/individual/dongyoon/인계/20260813_이동윤_to_최지용_AI_RAG_G1A_Embedding연계_로컬Runtime_사전협업_회신_v0.3.md`

### 2026-08-14 AI Canonical Embedding Fixture Exporter Phase A

- 최신 `origin/main@ab433c332229bc7c6fb0af764291d2376ea10df8`의 Clean 상태에서
  `codex/ai-canonical-fixture-exporter-g1a` 브랜치를 생성하고, AI 공식 Producer
  `ai/scripts/export_canonical_embedding_fixture.py`와 전용 계약 테스트를 추가했다.
  Backend Builder는 구현 입력으로 재사용하지 않고 계약 참고 검증기로만 대조했다.
- Exporter는 AI 소유 `canonical_evidence_identity.json`, `index_manifest.json`, 승인
  JSONL을 교차 검증한다. 고정 BGE-M3 Revision의 출력을 명시적으로 Float32로
  변환하고, 7x1024·Chunk Set Hash·Chunk Text Hash·Chunk ID ASC·중복 ID·NFC
  Validate-only를 fail-closed로 검사한다. Bool·문자열·NaN·Infinity와 Float32 변환
  후 비유한 값도 Artifact 작성 전에 거부한다.
- 출력은 repository root 기준
  `.runtime/backend-ai/canonical_embedding_fixture_v1.json` 아래로 제한하고, 임시
  파일 교체 방식으로 쓴다. JSON은 `ensure_ascii=false`, Key Sort, Compact
  Separator, `allow_nan=false`, trailing newline 없음으로 고정하며 `.runtime/`의
  기존 Git ignore 적용을 확인했다.
- Python `3.13.13`에서 Exporter 전용 `10 passed`, AI 전체 Unit
  `229 passed, 5 warnings, 7 subtests passed`, Backend 참고 Builder `6 passed`,
  `py_compile`, `git diff --check`를 확인했다. 실제 고정 Revision 모델 생성과 별도
  byte-level 검증도 PASS했으며 Candidate Fixture SHA-256은
  `759379308abdafbe66ef205e13cd829d8ad49714d0b824032eb0fbc58546d019`다. Fixture와
  Vector 본문은 Git·문서·채팅에 기록하지 않았다.
- `P1 Backend blocker`: 현재 main의 Backend Importer 회귀는 `31 passed, 19 failed`다.
  모든 실패는 Fixture 계약 평가 전
  `data/config/evidence/backend_ai_canonical_import_v1.json`의 Index Manifest 기대
  Byte SHA-256 `91027E88DEC6C3BFF1E590AAF4479CA021AC284EB0BDC8E1EEC6C76473DA667E`과
  실제 `ai/configs/index_manifest.json` SHA-256
  `C71488A7F0A9226D804FBE0BEE3C4B911B926B4F9EF39E026DC93420B8A03D66` 불일치에서
  시작한다. AI Exporter 변경과 무관하지만 Phase B Import를 막으므로 Backend
  Owner가 최종 병합 전에 정합성을 갱신하고 재검증해야 한다.
- 최종 Backend·AI 병합 main SHA와 승인된 김은진 Host 전달 경로가 아직 없어
  `fixture_generated_commit=PENDING_MERGE`, `artifact_delivery=BLOCKED`다.
  `ENVIRONMENT_READY`도 아직 수신하지 않았으므로 실제 pgvector·OpenAI G1-A는
  `NOT_RUN_WAITING_QA`이며 Unit·Health 결과로 대체하지 않는다.

### 2026-08-14 Canonical Identity 정본 승인·Fixture provenance 후속 확인

- 최신 `main@ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`과 로컬 `dongyoon`의
  SHA가 같은 상태에서 Canonical Identity·Index Manifest의 `text eol=lf` 계약과
  Backend Importer 보강을 확인했다.
- 기존 Windows checkout에 남은 `index_manifest.json` CRLF 때문에 첫 Backend
  Importer 회귀는 `25 passed, 19 failed`였으나, main LF blob으로 다시
  materialize한 뒤 `44 passed, 0 failed`를 재현했다. Identity SHA
  `925088a352a81180b51e5418eb3152a1244aba3da07569712c4d903468220b85`와 Index
  Manifest SHA `91027e88dec6c3bff1e590aaf4479ca021ac284eb0bdc8e1eec6c76473da667e`는
  Backend Manifest 기대값과 일치한다.
- Exporter Commit `626a7a4584d381085615d80b2269b8155322176d` 당시와 현재 main의 Identity
  SHA가 같고, Identity·Index Manifest·Exporter·승인 JSONL 내용 변경이 없음을
  확인했다. Fixture SHA는
  `759379308abdafbe66ef205e13cd829d8ad49714d0b824032eb0fbc58546d019`, 계약은
  `7x1024 / FLOAT32 / chunk_id_ASC / NFC 7/7`이다.
- AI Exporter 전용 테스트는 `10 passed`다. Identity·Exporter·Model Revision·Chunk
  Set과 Fixture SHA가 불변이므로 재생성·재전송은 `NO`로 판정했다. QA 수신 완료는
  요청서의 외부 ACK를 근거로 하며 AI가 Host 파일을 직접 확인한 것으로 확대하지
  않는다.
- 실제 G1-A Phase B는 김은진의 Importer `44 passed`, Readiness·Crosswalk·Readonly
  View와 `ENVIRONMENT_READY=YES` 회신 전까지 `WAITING_QA`다.
- 상세 회신은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_AI_CanonicalIdentity_정본승인_Fixture생성근거_후속확인_회신_v0.1.md`에 기록했다.

### 2026-08-14 G1-A Phase B 기술 사전검증 착수

- 고정 `main@ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`에서 QA의
  `environment_ready=YES`, `g1a_joint_execution_ready=YES`를 수신했지만,
  `source_policy_review=PENDING`, `APPROVE_WITH_POLICY_HOLD`를 실제 OpenAI 무조건
  실행 승인으로 확대하지 않았다.
- Backend Fixture Builder·Importer·Crosswalk·G1-B Readiness 계약 회귀는
  `81 passed in 12.54s`, exit 0이다. 이는 Unit·계약 증거이며 실제 팀 DB 결과가 아니다.
- AI pgvector Integration Gate는 현재 Codex Process에 `AI_VECTOR_DSN`이 없어
  `1 failed in 0.25s`, exit 1로 fail-closed 했다. QA Host 준비 회신과 현재 Process의
  Secret 미주입 상태를 분리하며, 검색 0건이나 PASS로 숨기지 않았다.
- 실제 OpenAI 요청은 공식 Evidence Summary를 Provider 입력에 포함하므로 Source
  Policy 승인 전까지 `NOT_RUN_POLICY_HOLD`다. Strict HTTP와 실제 Timeout 504도
  실행하지 않았다.
- 재개에는 김은진 Host에서의 직접 실행 또는 승인된 Process 환경 주입이 필요하다.
  실제 OpenAI는 `source_policy_review=APPROVED`와 Evidence Summary 외부 전송 허용
  ACK 후 실행한다.
- 상세 회신은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_김은진_최지용_AI_G1A_PhaseB_기술사전검증_착수회신_v0.1.md`에 기록했다.

### 2026-08-14 Backend `vector_dims(unknown)` Django 사전검증 경고 재현 회신

- `dongyoon@d6ab1e480e090369a03360aa385c74eff64720a6`, clean 상태의 이동윤 Host
  `LOCAL_QA_ISOLATED` PostgreSQL `16.15`, pgvector `0.8.6`에서 Canonical Import
  신규 Embedding 생성 경로의 `function vector_dims(unknown) is not unique` 경고를
  재현했다.
- 경고는 `CanonicalEvidenceImporter._get_or_create_exact()`가 신규
  `ChunkEmbedding`에 `full_clean()`을 호출할 때 Django CheckConstraint 검증 SQL의
  Vector Parameter Type이 `unknown`으로 평가되는 경계다. 최초 Dry-run·Apply는 Exit
  0이고 Chunk·Embedding 7건을 생성했으며 동일 입력 Replay는 Create·Update 0,
  Embedding Unchanged 7이다.
- Import 후 동일 Dry-run은 기존 Embedding 조회 경로라
  `VECTOR_DIMS_UNKNOWN_WARNING_COUNT=0`, Exit 0이었다. 따라서 Replay만으로 수정 여부를
  판정하지 않고 실제 신규 Embedding 생성 PostgreSQL 회귀가 필요하다.
- 저장 DB Constraint, Crosswalk 7/7, Page Link 8, Readonly View 7행, Readiness Audit
  `READY`, AI 실제 pgvector `1 passed in 9.97s`, Backend 표적 `81 passed in 11.88s`는
  통과했다. 현재 판정은 P0가 아닌 `P1_BACKEND_VALIDATION_WARNING_NON_BLOCKING`이다.
- 상세 재현·영향 경계·Backend 완료 조건과 회신 형식은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_Backend_pgvector_vector_dims_unknown_Django사전검증경고_재현회신_v0.1.md`에 기록했다.

### 2026-08-14 AI G1-A Phase B 이동윤 Host 기술재현 실행결과

- `dongyoon@d6ab1e480e090369a03360aa385c74eff64720a6`의
  `이동윤_HOST_LOCAL_TECHNICAL_REPRODUCTION`
  환경에서 실제 Readonly pgvector와 OpenAI Runtime을 검증했다. 요청 기준
  `main@ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`은 실행 HEAD의 조상이며, 두
  Commit 사이 AI·계약·Canonical 입력 차이는 없다.
- AI pgvector Integration은 `1 passed in 9.97s`, Runtime Verifier는 실제
  `gpt-4.1-mini-2025-04-14` 호출·Token 1180·예상 Low-flow Evidence Hit로 PASS했다.
  Local Strict HTTP Smoke도 HTTP 200, `SUCCEEDED`, `failure_stage=null`, Verified
  Evidence 5건, Guidance 일치와 Header·Body·로그 Correlation을 통과했다.
- 공개 `SymptomAnalysisResponse`의 `x-contract-version=3.0.0`,
  `additionalProperties=false`와 상태 전환·Evidence 승인 필드 부재를 확인해
  `GUIDANCE_ONLY` 경계를 PASS로 판정했다.
- 별도 실제 HTTP Process에서 `RETRIEVING` Pipeline Stage Timeout을 주입해 HTTP
  504, `AI-TIMEOUT-01`, Retryable·Failure Stage·Correlation Echo를 통과했다. 이는
  실제 HTTP 오류 계약 증거이며 OpenAI Provider 네트워크 장애 자체는 `NOT_RUN`이다.
- 이 결과는 이동윤 Host 기술재현이며 김은진 Host 공식 공동 실행, Backend 저장·Replay·
  상태 전환 E2E로 확대하지 않는다. 테스트 후 AI Process는 종료했고 PostgreSQL
  Container·Volume은 Healthy 상태로 보존했다.
- 상세 회신은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_AI_G1A_PhaseB_로컬기술재현_실행결과_회신_v0.1.md`에 기록했다.

### 2026-08-14 Customer Guidance G1-A·G1-B 실연결 진행 회신

- 이동윤 고유 문서를 `b516c06`에 보존한 뒤 새 브랜치 없이
  `main@a43fd2d6f27243935a5d92fed349cb3e19e8bd13`을 `dongyoon`에 병합했다. 현재
  실행 Commit은 `2119a4bdbf1d7c56501b0c0db81f659cb3b641bb`이며 AI·AI 계약·Canonical
  입력 충돌은 없다.
- Backend·계약 표적 회귀는 `123 passed, 3 skipped`, 최종 Schema의 Readiness는
  `READY`, 실제 AI Readonly pgvector는 `1 passed in 10.61s`다. 최종 main 동기화
  후 실제 OpenAI Runtime도 `gpt-4.1-mini-2025-04-14`, Token 1180, 예상 Low-flow
  Evidence Hit로 PASS했다.
- 실제 AI Runtime은 이동윤 Host `127.0.0.1:8001`에서 Health 200으로 유지했다.
  외부 Host 공개 바인딩이나 방화벽 변경은 수행하지 않았다.
- `evidence.0011` 적용과 권한 재조정 후 G1-B Seed를 시작했지만 DB에
  `support_inquiry.priority_code`가 없어 중단됐다. 전체 Plan에는 Inquiry·Workflow·
  Consultation 등을 포함한 19개 Migration이 남아 있어 명시 승인 전 적용하지 않았다.
- Migration 전 DB Custom-format Backup을
  `.runtime/g1b/20260814-main-a43/waterbridge-pre-a43-migrations.dump`에 생성했다. 이
  파일은 Git·전달 대상이 아니다.
- 현재 판정은 `g1a_final_baseline=PASS`, `g1b_joint_result=BLOCKED`다. Backend
  AIRun·Guidance·Evidence 저장과 Replay는 Migration 승인 후 새 Inquiry로 실행한다.
- 요청 양식에 맞춘 단일 진행 회신은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_AI_RAG_CustomerGuidance_G1A_G1B_실연결_진행회신_v0.1.md`에 기록했다.

### 2026-08-14 Customer Guidance G1-B 공동실행 준비 회신

- 최지용의 최신 회신에 따라 이동윤 Host의 미적용 Migration은 추가 적용하지 않고,
  김은진 QA 통합환경에서 최종 main을 재기동해 실제 Backend G1-B를 진행하는 것으로
  실행 범위를 조정했다.
- 김은진 작업자에게 보호 Loader와 Uvicorn을 같은 Process에서 실행하는 실제 AI
  Runtime 기동 명령, 필수 환경변수 이름, 같은 Host Backend의
  `AI_SERVICE_BASE_URL`·`AI_SERVICE_MODE=local` 설정을 전달했다.
- 공동검증은 새 합성 Inquiry Happy Path → AIRun·Assessment·Guidance·Evidence 저장 →
  Replay 추가 AI 호출·중복 저장 차단 → Backend·AI Log·DB Correlation 일치 순서로
  진행한다. NO_EVIDENCE와 DANGER는 Happy Path 결과 후 실행 여부를 결정한다.
- 상세 전달본은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_AI_RAG_CustomerGuidance_G1B_공동실행_준비회신_v0.1.md`에 기록했다.

### 2026-08-14 AI RAG G1-B 단독준비 마감·사전확인 회신

- 원격 `origin/main`을 갱신해 기준 SHA를
  `720573906c5cba166a7f8fb35c9ff17f359350ab`로 확인했다. 현재
  `dongyoon@237a9b525f64670e1afef4fbc9fa1db2545a3aa5`에 해당 main이 포함돼 있고,
  AI·AI 계약·Canonical 입력 차이는 0건이며 검증 시 Worktree는 clean이었다.
- QA Host용 보호 Loader·Uvicorn 기동 명령, AI Process 필수 환경변수 5개,
  `openai / gpt-4.1-mini / customer_guidance/v2 / local` Metadata와 Backend 저장
  설정을 코드·Runbook 기준으로 확인했다.
- 현재 AI Health는 HTTP 200이고 `analysis_started`, `llm_guidance_completed`,
  `analysis_completed` Correlation 로그 Event가 준비돼 있다. 기존 수용 결과와 입력이
  같으므로 실제 OpenAI·pgvector·HTTP 504를 반복 실행하지 않았다.
- AI 단독 준비는 `READY`, 남은 단독 작업은 `NONE`, 차단 사유는 `NONE`이다. 공동실행
  시간은 `협의 필요`이며, 김은진 `ENVIRONMENT_READY=YES`와 최지용의 새 Inquiry·
  Idempotency Key·Correlation ID 준비 ACK 수신 후 지원한다.
- 상세 회신은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_AI_RAG_G1B_단독준비_마감_사전확인_회신_v0.1.md`에 기록했다.

### 2026-08-14 Backend↔AI G1-B 비동기 연동 동일 Host 1차 준비 ACK

- Backend와 AI를 같은 Host에서 실행하는 방식으로 고정했다. AI Base URL은
  `http://127.0.0.1:8001`, Network Scope는 `SAME_HOST`이며 Public/LAN 바인딩과
  방화벽 변경은 수행하지 않는다.
- `main@720573906c5cba166a7f8fb35c9ff17f359350ab`과 Vector 수정
  `11d771ab71aa8adc01a72af45dfe9eff280c219e`이 현재
  `dongyoon@237a9b525f64670e1afef4fbc9fa1db2545a3aa5`에 포함된 것을 확인했다. AI·AI
  계약·Canonical 입력 차이는 0건이다.
- 실제 AI Runtime은 `127.0.0.1:8001` Listen, Health HTTP 200,
  `config_loaded=true` 상태이며 `openai / gpt-4.1-mini / customer_guidance/v2 /
  local / backend_ai_rag_chunks_v1` 준비 ACK를 확정했다.
- 다음 담당은 최지용이다. 같은 Host Backend에 Base URL과 Metadata를 반영하고 새 합성
  Inquiry를 제출한 뒤 공개 Inquiry ID·Correlation ID·제출시각·결과만 전달해야 한다.
  수신 후 이동윤이 AI 로그를 비동기로 대조해 2차 증거를 회신한다.
- 상세 1차 ACK는
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_Backend_AI_G1B_비동기연동_동일Host_1차준비ACK_v0.1.md`에 기록했다.

### 2026-08-14 Backend↔AI G1-B 동일 Host 실행차단

- 요청대로 AI Runtime은 `127.0.0.1:8001`에서 유지하고, 같은 Checkout의 별도
  PowerShell에서 Runtime Role을 주입했다. Django System Check는 Exit 0, G1-B
  Readiness는 `READY`, Exit 0이었다.
- Backend 기동 전 전체 `migrate --check --plan`을 추가 확인한 결과 Evidence 0011은
  적용돼 있지만 Inquiry·Workflow·Consultation 등을 포함한 19개 Migration이 미적용으로
  남아 Exit 1이었다. 이전 Seed에서 `support_inquiry.priority_code` 미존재가 실제
  `ProgrammingError`로 재현된 상태와 일치한다.
- 요청서의 중단 조건에 따라 임의 Migration·Import·SQL을 실행하지 않고 Backend
  Runserver, 새 Inquiry, Submit과 Replay를 모두 `NOT_RUN`으로 유지했다. AI Health는
  계속 HTTP 200이며 Backend 8000번 Port는 열지 않았다.
- 준비 ACK는 `BLOCKED`, 실제 G1-B 결과는 `BLOCKED_AT_BACKEND_PRESTART_MIGRATION_GATE`다.
  다음 결정은 현재 DB에 19개 Migration을 적용할지, 완전 적용된 QA DB·Volume을 사용할지
  최지용 Backend·DB 담당자가 내려야 한다.
- 상세 회신은
  `docs/individual/dongyoon/인계/20260814_이동윤_to_최지용_Backend_AI_G1B_동일Host_실행차단_회신_v0.1.md`에 기록했다.

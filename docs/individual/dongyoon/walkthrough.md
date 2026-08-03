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

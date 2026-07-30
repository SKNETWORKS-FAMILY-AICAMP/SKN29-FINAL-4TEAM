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

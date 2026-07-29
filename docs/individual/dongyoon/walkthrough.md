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

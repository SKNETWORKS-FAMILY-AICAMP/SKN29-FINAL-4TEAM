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

---

## 🧪 전체 검증 결과 (`pytest ai/tests/unit/`)

```text
============================= test session starts =============================
platform win32 -- Python 3.10.20, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Project\SKN29-FINAL-4TEAM\ai
collected 22 items

ai\tests\unit\test_api_routes.py ....                                    [ 18%]
ai\tests\unit\test_evaluation.py ...                                     [ 31%]
ai\tests\unit\test_pipeline.py ..                                        [ 40%]
ai\tests\unit\test_retrieval.py ...                                      [ 54%]
ai\tests\unit\test_safety_classifier.py ......                           [ 81%]
ai\tests\unit\test_schemas_and_configs.py ....                           [100%]

======================= 22 passed, 2 warnings in 0.43s ========================
```

### 📊 종합 자동 평가 측정 결과 (`python -m ai.evaluation.evaluation_runner`)
* **RAG 검색 정답률**: `mean_recall_at_5` = **1.0 (100.0%)**, `mean_mrr` = **1.0**
* **안전 규칙 준수율 (Safety Compliance Rate)**: **100.0%** (위험군 감지 시 `NORMAL` 상태 반환 0건)
* **전체 22개 단위 테스트 100% Pass**

# 4주차 AI 단일 Workflow 후보 기준선

> 실행일: 2026-08-07  
> 상태: `CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT`  
> 기준 HEAD: `1590279b7c7aea66334b3436024a83b150e28610`  
> Working Tree: Dirty — 이 문서와 후보 산출물이 아직 Commit되지 않음

## 1. 판정

Backend E2E를 시작할 AI 계약·FastAPI·단일 RAG Workflow·안전·Timeout 기준선은
준비됐다. 팀 DB RAG 재실행, Backend 저장 E2E와 후보 Commit이 없으므로 통합
완료나 다중 Agent 완료로 판정하지 않는다.

공식 후보 SSOT는
[`official_mvp_baseline_20260803.json`](../../../ai/evaluation/reports/official_mvp_baseline_20260803.json)이다.

## 2. 실행 환경과 명령

```powershell
.\ai\.venv\Scripts\python.exe --version
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -m ai.evaluation.runners.structuring_runner --output ai/evaluation/reports/structuring_evaluation_20260807.json
.\ai\.venv\Scripts\python.exe -m ai.evaluation.evaluation_runner
.\ai\.venv\Scripts\python.exe -m ai.scripts.generate_candidate_baseline --unit-test-result "101 passed, 3 warnings" --unit-test-exit-code 0
```

## 3. 결과

| 검증 | 결과 | 범위 |
| --- | --- | --- |
| Python | `3.13.13` | AI 전용 `.venv` |
| 의존성 | `pip check` PASS | Broken requirement 없음 |
| AI 단위 회귀 | `101 passed, 3 warnings` | 계약·안전·구조화·검색·Pipeline·HTTP |
| 구조화 평가 | `12/12 PASS` | 결정적 규칙, Backend·Vector DB 불필요 |
| 안전 평가 | `4/4`, 100% | 근거가 있다고 가정한 규칙 분류 |
| Offline RAG | `vector_store_not_configured` | 품질 수치 공개 금지 |

경고 3건은 Starlette TestClient 1건과 `jsonschema.RefResolver` 사용 2건이다.
테스트 실패는 아니지만 의존성 Upgrade 작업에서 제거해야 한다.

## 4. T-026 구조화 평가 범위

Dataset은
[`symptom_eval_dataset.json`](../../../ai/evaluation/datasets/structuring/symptom_eval_dataset.json)이며
다음을 포함한다.

- 대표 증상 4종과 복수 증상
- 짧은 자유 입력
- `출수양`, `쫄쫄` 오타 변형
- “누수는 아니고” 부정 표현
- 기존 답변 반영과 반복 질문 차단
- 답변 거절을 증상 값으로 저장하지 않으면서 같은 질문을 반복하지 않는 정책
- 위험 입력의 누락 질문 생략
- 오류 코드, 수행 조치와 복수 출수 종류

결과는
[`structuring_evaluation_20260807.json`](../../../ai/evaluation/reports/structuring_evaluation_20260807.json)에
Case별 실제 구조화 값과 Exact Match를 기록한다. 12건 통과는 이 Dataset의
결정적 규칙 기준선이며 전체 자유 입력 정확도나 모델 성능을 뜻하지 않는다.

## 5. 계약·추적 기준

- 계약 Version: `1.1.0`, JSON Schema Draft 2020-12
- 계약 Schema: 16개
- 계약 Canonical 규칙: 상대 경로 정렬 후 JSON Key 정렬, UTF-8 Compact JSON
- `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version`을 성공·Fallback·오류에 보존
- Backend 자동 재시도 0회, AI 내부 일시 검색 오류 최대 1회
- 전체 Timeout 30초

Canonical Hash는 후보 JSON의 `contract.evaluated_contract_sha256`을 사용한다.

## 6. 남은 Gate

- 후보 변경 Commit과 40자리 최종 SHA 고정
- Backend Client·Mapper·Validator와 저장 E2E
- 팀 DB Migration·승인 청크 UPSERT·RAG 재실행
- Data Owner가 승인한 13번째 검색 후 문서 정책 차단 Case
- stale `state_version`, 중복 요청, 상담 전환과 최종 EvidenceCard 저장 검증

Local·Mock 실행 절차는
[`scripts/demo/README.md`](../../../scripts/demo/README.md)를 따른다.

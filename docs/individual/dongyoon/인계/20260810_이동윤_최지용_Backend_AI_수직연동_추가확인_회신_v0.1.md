# 이동윤 → 최지용 Backend·AI 수직 연동 추가확인 회신 v0.1

> 작성일: 2026-08-10 KST  
> 발신자: 이동윤 / AI·RAG  
> 수신자: 최지용 / Backend·Database  
> 기준 문서: 03·04·05 회신 및 공동 E2E 문서  
> 관계: 01·02 선행 제공물 회신과 별도

## 1. 최지용에게 보낼 회신

계약 `3.0.0`에서 위험 규칙 ID를 필수 필드로 제공하도록 구현했다. AI 승인
청크 7개의 canonical `chunk_id`와 원문 해시도 고정했다. 실행 식별값은 고객
공개 응답에 추가하지 않고 공유 Manifest와 Backend 환경 설정을 통해 `AIRun`에
저장하는 방식으로 확정했다.

다만 AI `chunk_id`와 Backend `DocumentChunk.public_id`의 실제 Crosswalk는
Backend·Database 소유 값이므로 아직 완료가 아니다. Backend 계약 `3.0.0`
호환 검증, Crosswalk 생성, 실제 Backend 저장 E2E가 끝나기 전에는 전체 공동
E2E 준비 완료로 판정하지 않는다. Mock FastAPI HTTP 검증은 바로 시작할 수 있다.

```text
responder=이동윤
scope=AI_RUNTIME_FOR_BACKEND_VERTICAL_E2E

ai_environment=PASS
python_version=3.13.13
pip_check=PASS
ai_unit_tests=126 passed, 0 failed, 0 skipped, 3 warnings
start_command=.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
health_url=http://127.0.0.1:8001/health
analysis_url=http://127.0.0.1:8001/api/v1/ai/analyze?mode={mock|local}

correlation_id_uuid_contract=PASS
non_uuid_direct_call_status=HTTP 422, AI-VALIDATION-01, correlation_id=null
header_body_mismatch_status=HTTP 400, AI-VALIDATION-01

danger_rule_id_method=safety_assessment.matched_safety_rule_ids 필수 배열 (AI contract 3.0.0)
danger_fixture_path=ai/evaluation/datasets/backend_integration/fixture_manifest.json#F03

canonical_chunk_id_source=data/processed/structured/rag/mvp/rag_verified_sample.jsonl
backend_chunk_crosswalk=PENDING: Backend가 ai/configs/canonical_evidence_identity.json의 chunk_id를 knowledge_document_chunk.public_id에 매핑
evidence_fixture_path=ai/configs/canonical_evidence_identity.json

model_provider=waterbridge-local
model_name=single-rag-pipeline-v1
model_version=v1 (deterministic workflow, external LLM 미사용)
prompt_version=v1 (rule/template baseline)
pipeline_version=single-rag-pipeline-v1
retrieval_config_version=SHA256:5D399A937287585A8776F3730F03AD25478A274EF749FABB9365CEC321BACB19
embedding_model=BAAI/bge-m3
embedding_revision=5617a9f61b028005a4858fdac845db406aefb181
top_k=5

f01_f12_fixture_command=.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\test_backend_integration_fixtures.py -q
known_remaining_issue=Backend contract 3.0.0 호환 확인; Backend AIRun 환경값 적용; Backend DocumentChunk Crosswalk; 실제 Backend Mock·Local HTTP 저장 E2E; 격리 pgvector F01·F02 재검증; 공개 API Dispatch 결정
ready_for_joint_e2e=NO
```

## 2. 이번 회신에서 해소한 항목

| 요청 | 결과 | 검증 근거 |
|---|---|---|
| AI 환경 재현 | 완료 | Python 3.13.13, pip check PASS, 126 passed |
| UUID 직접 강제 | 완료 | 비UUID 422, Header·Body 불일치 400 |
| 위험 규칙 ID | 완료 | `matched_safety_rule_ids`, 계약 3.0.0 |
| AI canonical 청크 원천 | AI 범위 완료 | 승인 JSONL·Index Manifest·청크 텍스트 SHA parity |
| 실행 Metadata 전달 | AI 방식 확정 | `ai/configs/runtime_identity.json`, Backend env→`AIRun` |
| Backend Crosswalk | 미완료 | Backend `DocumentChunk.public_id` 매핑 필요 |

## 3. 다음 실행 순서

1. Backend가 AI 계약 `3.0.0`과 `matched_safety_rule_ids`를 호환 검증한다.
2. Backend가 canonical 청크 7개를 `DocumentChunk.public_id`와 매핑하고 결과를
   회신한다.
3. 동일 환경에서 Backend→실제 AI Mock HTTP를 호출해 저장·멱등·stale 경계를
   검증한다.
4. 격리 pgvector를 준비한 뒤 Local F01·F02와 F03~F12를 순서대로 검증한다.
5. 실제 결과가 나온 뒤 `ready_for_joint_e2e=YES`와 공동 체크리스트 판정을
   갱신한다.

## 4. 검증 결과

```text
Python: 3.13.13
pip check: No broken requirements found
AI unit: 126 passed, 3 warnings
AI fixture: 12 passed
Uvicorn mock smoke: PASS (health, analyze 200, correlation trace)
Uvicorn local danger: PASS (danger, 규칙 ID 2개, TOTAL_STOP, 근거 0건)
Backend unit rerun: NOT_RUN (backend/.venv 없음)
```

경고 3건은 `jsonschema.RefResolver` 2건과 Starlette TestClient 1건의 폐기 예정
API 경고이며 테스트 실패는 아니다. 실제 Local RAG·Backend 저장·팀 DB E2E
완료 증거로 확대 해석하지 않는다.

## 5. 03~05 문서 해결 결과 추가 회신

03~05문서 해결하고 밑에 내용 회신주세요.

```text
ai_unit_tests=126 passed, 3 warnings
ai_unit_tests_history=103은 F01~F12 Fixture 추가 전 중간값; 115는 Fixture 12개 포함 계약 2.0.0 당시 최종값; 121은 계약 3.0.0 안전 ID·canonical evidence·runtime identity 검증 추가값; 현재 126은 상담 요약 기준선 4건과 자연어 누수 안전 회귀 1건을 추가한 최신값
pip_check=PASS
danger_rule_id_method=safety_assessment.matched_safety_rule_ids 필수 배열; Backend는 detected_risks 자연어를 규칙 ID로 변환하지 않음
backend_chunk_crosswalk=PENDING_BACKEND_ACTION: ai/configs/canonical_evidence_identity.json의 canonical chunk_id 7개를 knowledge_document_chunk.public_id에 매핑하고 AI는 Backend ID를 생성하지 않음
refusal_or_unknown_payload_rule=Backend는 previous_answers[].question_id와 answer_text 원문을 보존; AI는 답변하지 않음|답변 거절|모름|모르겠음|확인 불가를 구조화 증상값으로 저장하지 않고 해당 question_id의 동일 질문을 다시 생성하지 않음
AI_VECTOR_DISPOSABLE_CONFIRM=격리 DB 초기화·검증 때만 DISPOSABLE_ONLY로 설정; DB 이름에 verify|test|tmp|disposable 중 하나가 있어야 하며 팀 공용 DB DDL·초기화에는 사용 금지
ready_for_joint_mock=YES
joint_mock_available_time=2026-08-10 KST 즉시 가능; 최지용 일정 확인 후 시작
```

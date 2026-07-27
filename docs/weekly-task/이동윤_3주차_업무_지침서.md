# 이동윤 3주차 업무 지침서

> 프로젝트: 정수기 구독 고객 케어 및 A/S 업무 지원 시스템
> 
> 
> 대상 기간: 2026년 7월 27일 ~ 7월 31일
> 
> 필수 산출물 목표 완료일: **2026년 7월 29일**
> 
> 7월 30일~31일 운영 원칙: 신규 AI 기능을 무리하게 확장하기보다 **검색·안전·계약 검증, 백엔드 연동 확인, 오류 수정과 다음 주 진입 준비**를 우선한다.
> 

---

# 1. 담당자 기본 정보

| 항목 | 내용 |
| --- | --- |
| 담당자 | 이동윤 |
| 담당 역할 | AI·RAG 개발 담당 |
| 주관할 영역 | `ai/**`, `contracts/ai/**` |
| 부관할·협업 영역 | `data/processed/**`, `data/schemas/processed/**`, `data/synthetic/expected/**`, `tests/contract/ai/**`, `tests/safety/**`, `tests/integration/backend-ai/**`, `tests/integration/backend-vector-store/**` |
| 주요 연계 영역 | `backend/integrations/ai/**`, `backend/apps/evidence/**`, Web·Mobile의 공식 근거·AI 안내 표시 영역 |
| 주요 협업 대상 | 최지용, 김은진, 윤승혁, 한예나, 양정현 |
| 3주차 핵심 책임 | Backend↔︎AI 계약, 안전 규칙, FastAPI 실행 기반, 임베딩·pgvector 검색, 단일 RAG 기준선, LangGraph 최소 골격, 검색 평가·연동 자료 제공 |
| 핵심 산출물 | AI JSON Schema·Pydantic 모델, 안전 규칙·테스트, 실행 가능한 AI 서버, 검색 모듈·평가 결과, 오케스트레이터 골격, 백엔드 요청·응답 예시 |

이동윤은 고객 문의 상태를 직접 변경하거나 상담·방문 결과를 확정하는 역할이 아니다. AI 서비스는 고객 입력을 구조화하고, 위험을 분류하고, 공식 문서를 검색하여 근거와 권고를 반환한다. 문의 상태 전환, 사용자 권한 검증, 업무 데이터 저장과 최종 `EvidenceCardDTO` 조립은 백엔드가 담당한다.

3주차에는 완성형 다중 에이전트를 구현하지 않는다. **동일한 입력·출력 계약을 사용하는 단일 RAG 기준선과 LangGraph 최소 실행 골격**을 만들고, 4주차 이후 기능을 안전하게 확장할 수 있는 기반을 확보하는 데 집중한다.

---

# 3. 3주차 필수 업무

## 3.1 Backend↔AI JSON Schema와 Pydantic 모델 확정

### 작업 목적

백엔드, AI, Web, Mobile이 위험도·현재 사용 안내·공식 근거·다음 행동을 같은 구조로 처리하도록 단일 계약을 만든다. JSON Schema와 Pydantic 모델이 다르면 AI 응답 저장, 화면 표시, 계약 테스트가 모두 달라지므로 검색·오케스트레이터 구현 전에 확정해야 한다.

Q-01 협의 결과에 따라 `contracts/ai/**`를 Backend↔AI 계약의 최종 기준본으로 사용하며, 계약 변경 PR은 해당 계약을 사용하는 AI 구현 PR보다 먼저 병합한다.

### 작업 위치

```
contracts/ai/
├─ analyze-request.schema.json
├─ analyze-response.schema.json
├─ common-context.schema.json
├─ evidence-reference.schema.json
├─ error-response.schema.json
└─ examples/
   ├─ general-guidance.json
   ├─ danger-detected.json
   ├─ no-evidence.json
   └─ validation-failed.json

ai/app/schemas/
├─ common.py
├─ symptom.py
├─ safety.py
├─ retrieval.py
├─ guidance.py
└─ pipeline.py

ai/app/interfaces/http/
├─ request_models.py
└─ response_models.py
```

연계 경로:

```
contracts/codes/risk-levels.*
contracts/codes/usage-guidance-statuses.*
contracts/error-codes/ai/**
contracts/CHANGELOG.md
data/synthetic/fixtures/**                # 김은진 주관 기준본
data/synthetic/expected/**
tests/contract/ai/**                      # 김은진과 협의 후 반영
```

### 세부 작업 지침

1. Q-01 협의 결과에 따라 계약과 구현의 순서를 관리한다.
    - `contracts/ai/**`를 Backend↔AI 계약의 최종 기준본으로 사용한다.
    - 설명 문서와 `contracts/ai/**`의 내용이 다르면 `contracts/ai/**`를 우선한다.
    - 계약 변경 PR은 Pydantic 모델·FastAPI API·Pipeline 구현 PR보다 먼저 병합한다.
    - 계약 병합 전에도 Mock·Stub 기반 작업은 진행할 수 있지만 실제 연동 완료로 판정하지 않는다.
2. 분석 요청에 필요한 최소 Context를 확정한다.
    - `inquiry_id`
    - `correlation_id`
    - 고객 원문 증상
    - 대표 증상 코드와 추가 답변
    - `model_code`
    - `manual_model`
    - `product_generation`
    - 필요한 경우 구독·케어 이력 참조 정보
3. Q-06 협의 결과에 따라 `inquiry_id`에는 Backend 내부 정수형 PK가 아니라 외부 공개 식별자를 사용한다.
    - `DEMO-INQ-002`와 같은 값은 별도 업무·시연 식별자로 취급한다.
    - AI 요청·응답에 Backend 내부 정수형 PK를 노출하지 않는다.
4. AI가 사용하지 않거나 알 필요가 없는 개인정보는 요청 모델에서 제외한다.
5. 분석 응답에 다음 필드를 타입과 Enum까지 명시한다.
    - 구조화 증상과 누락 필드
    - `risk_level`
    - `usage_guidance_status`
    - `usage_guidance_message`
    - `restricted_functions`
    - 검색 근거 참조 배열
    - 안전한 다음 행동
    - `requires_consultation`
    - AI 처리 상태와 실패 단계
6. Q-02 협의 결과에 따라 `usage_guidance_status`는 다음 네 값만 허용한다.
    - `NORMAL`
    - `PARTIAL_STOP`
    - `TOTAL_STOP`
    - `PENDING_CONSULTATION`
7. AI의 Pydantic Enum과 Backend의 Django `TextChoices`가 같은 문자열을 사용하도록 한다.
    - `NORMAL_USE`
    - `PARTIAL_RESTRICTION`
    - `FULL_RESTRICTION`
    
    위 세 코드는 최종 계약과 AI 구현에서 사용하지 않는다.
    
8. `evidence`는 AI가 검색한 근거 참조를 반환하는 구조로 제한한다. 고객 화면용 최종 `EvidenceCardDTO`를 AI에서 임의 조립하지 않는다.
9. 정상·위험·근거 없음·Schema 오류 예시를 작성한다.
    - 정상 업무 예시는 `data/synthetic/fixtures/**`를 기준으로 작성한다.
    - 서비스별 예시에서 고객·제품·문의·상태 정보가 서로 달라지지 않도록 한다.
10. JSON Schema를 Pydantic v2 모델에서 직렬화·역직렬화하고 Enum 불일치·필수 필드 누락을 검증한다.
11. 오류 응답에는 내부 예외 Trace나 Prompt를 노출하지 않고 오류 코드, 재시도 가능 여부, 실패 단계만 포함한다.
12. 계약 변경은 `contracts/CHANGELOG.md` 또는 AI 계약 변경 기록에 남긴다.
13. 한예나·양정현에게 화면 표시용 필드 설명을 전달하고, 화면이 내부 검색 필드에 의존하지 않는지 확인한다.
14. 최지용의 Backend Mapper가 예시 JSON을 입력·출력으로 검증할 수 있게 샘플을 제공한다.

### 완료 기준

- `contracts/ai/**`의 계약 변경 PR이 관련 AI 구현 PR보다 먼저 병합되어 있다.
- JSON Schema와 Pydantic 모델의 필드·타입·Enum이 일치한다.
- 정상·위험·근거 없음·검증 실패 예시가 모두 Schema 검증을 통과하거나 의도한 오류를 반환한다.
- 분석 요청의 `inquiry_id`에 Backend 내부 정수형 PK가 사용되지 않는다.
- 필수 6개 공통 필드가 누락되면 검증 오류가 발생한다.
- `usage_guidance_status`는 `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`만 허용한다.
- 위험도와 사용 안내 상태가 협의된 코드 외 값을 허용하지 않는다.
- AI 응답에 내부 파일 경로, Prompt 원문, 비밀값, 고객 개인정보가 포함되지 않는다.
- 정상 업무 예시가 `data/synthetic/fixtures/**`의 고객·제품·문의 정보와 일치한다.
- 최지용이 Backend Mapper 구현에 사용할 수 있는 요청·응답 예시를 확인한다.
- 한예나·양정현이 필요한 화면 필드를 확인하고 추가 필드 요구를 Issue로 기록한다.

### 산출물

- Backend↔AI 요청·응답 JSON Schema
- AI Pydantic 모델
- 정상·위험·근거 없음·오류 예시 JSON
- 코드·필드 설명과 변경 기록
- Backend·Web·Mobile 인계용 계약 요약

---

## 3.2 명시적 안전 규칙과 출력 가드레일 구현

### 작업 목적

누수·전기·화상·온수 관련 위험은 LLM 판단보다 명시적 규칙을 먼저 적용한다. 공식 근거가 없거나 안전을 보장할 수 없는 경우 자가조치 생성을 차단하고 상담 전환을 우선하도록 한다.

### 작업 위치

```
ai/app/safety/
├─ risk_classifier.py
├─ priority_classifier.py
├─ usage_guidance_classifier.py
├─ prohibited_action_guard.py
├─ diagnosis_expression_guard.py
├─ no_evidence_policy.py
└─ rule_loader.py

ai/app/validation/safety/
├─ prohibited_phrase_validator.py
└─ usage_guidance_validator.py

ai/configs/
├─ safety_rules.yaml
└─ prohibited_expressions.yaml

ai/prompts/common/
├─ grounding_rules.yaml
└─ safety_constraints.yaml

ai/tests/unit/safety/**
ai/tests/unit/validation/**
```

연계 경로:

```
data/synthetic/fixtures/**                # 김은진 주관 기준본
data/synthetic/expected/**                # 김은진 주관
tests/safety/**                           # 김은진 주관
```

### 세부 작업 지침

1. 안전 규칙을 코드에 직접 흩어 쓰지 않고 YAML과 Loader로 분리한다.
2. 다음 위험 범주를 최소 테스트 대상으로 포함한다.
    - 제품 하부·전원부 주변 누수
    - 전기 냄새·연기·스파크·감전 위험
    - 뜨거운 물·화상 위험
    - 온수 기능 이상과 과열 의심
3. 위험 분류와 현재 사용 안내 상태의 매핑을 명시한다.
    - 일반적인 정보 부족이 곧 `general`을 의미하지 않게 한다.
    - 위험도가 `danger`이면 `NORMAL`을 반환하지 않는다.
    - 일부 기능의 사용을 제한해야 하면 `PARTIAL_STOP`을 사용한다.
    - 제품 전체의 사용을 중지해야 하면 `TOTAL_STOP`을 사용한다.
    - 공식 근거 부족이면 `PENDING_CONSULTATION`과 상담 안내를 우선한다.
4. `restricted_functions`에 전체 사용 중지와 특정 기능 제한을 구분할 수 있게 한다.
5. 다음 안내를 생성하거나 통과시키지 않도록 Guard를 구현한다.
    - 제품 커버 분해
    - 전기·배선·내부 부품 직접 조작
    - 전문 장비 없이 수리·교체
    - “고장이 확실합니다”와 같은 확정 진단
    - “안전합니다”, “수질에 문제가 없습니다”와 같은 보증 표현
6. 검색 근거가 없을 때 `no_evidence_policy`가 일반 자가조치 생성기로 진행하지 않도록 한다.
7. LLM 생성 전 규칙 검사와 생성 후 문장 검사를 분리한다.
8. 정상·주의·위험·근거 없음·금지 문구 포함 사례를 단위 테스트로 작성한다.
9. 정상 업무 시나리오는 `data/synthetic/fixtures/**`를 기준으로 사용하고, 기대 결과는 `data/synthetic/expected/**`와 비교한다.
10. 김은진이 제공한 기대 결과와 AI 테스트 결과를 비교하고 불일치 원인을 기록한다.
11. 안전 규칙이 화면에 그대로 노출되는 내부 표현이 아니라 고객 친화적인 안내 메시지로 변환될 수 있게 결과 코드를 분리한다.

### 완료 기준

- 안전 규칙 YAML이 로딩되고 잘못된 규칙 형식은 시작 시 검증 오류를 발생시킨다.
- 합의된 위험 테스트 세트에서 누수·전기·화상·온수 위험이 기대 위험도와 사용 안내 상태로 분류된다.
- 위험도 `danger`와 `NORMAL`이 동시에 반환되지 않는다.
- 공식 근거가 없을 때 임의 자가조치와 정상 사용 판정이 차단된다.
- 일부 기능 제한과 전체 사용 중지가 `PARTIAL_STOP`과 `TOTAL_STOP`으로 구분된다.
- 제품 분해·직접 수리·확정 진단·안전 보증 표현이 출력 검증에서 차단된다.
- 차단 시 무응답이 아니라 상담 필요와 다음 행동이 구조화된 응답으로 반환된다.
- 테스트 결과와 미검증 Edge Case가 문서 또는 Issue에 기록된다.

### 산출물

- 안전 분기·사용 안내 규칙 YAML
- 위험 분류·사용 안내·금지 행동 Guard
- 생성 후 안전 검증기
- 안전 단위 테스트와 결과
- 미확정·추가 검증이 필요한 위험 사례 목록

---

## 3.3 FastAPI 실행 환경과 백엔드 연동용 최소 API 구성

### 작업 목적

백엔드가 AI 내부 구현을 알지 않고 HTTP 계약만으로 분석 기능을 호출할 수 있도록 독립 실행 서버를 만든다. 3주차에는 실제 모든 LLM 기능을 연결하기보다 Health Check, Schema 검증, Mock 또는 최소 분석 실행과 오류 처리를 먼저 안정화한다.

### 작업 위치

```
ai/
├─ app/
│  ├─ interfaces/http/
│  │  ├─ routes/
│  │  │  ├─ analysis_routes.py
│  │  │  └─ health_routes.py
│  │  ├─ request_models.py
│  │  ├─ response_models.py
│  │  └─ error_handlers.py
│  ├─ integrations/llm/
│  │  ├─ llm_client.py
│  │  ├─ model_router.py
│  │  └─ token_usage.py
│  ├─ common/config/**
│  ├─ common/errors/**
│  ├─ common/logging/**
│  ├─ common/retry/**
│  ├─ common/timeout/**
│  ├─ common/tracing/**
│  ├─ bootstrap.py
│  └─ main.py
├─ configs/{base,development,test}.yaml
├─ configs/retry_policy.yaml
├─ pyproject.toml
├─ .env.example
└─ README.md
```

### 세부 작업 지침

1. Python 버전과 FastAPI·Pydantic·LangChain·LangGraph·임베딩·PostgreSQL 관련 의존성을 고정한다.
2. 비밀값은 `.env`에서만 읽고 `.env.example`에는 변수명과 설명만 작성한다.
3. `GET /health`를 구현하고 최소한 다음을 구분한다.
    - 서버 Liveness
    - 설정 로딩 여부
    - 선택적으로 DB·Vector Store Readiness
4. 협의된 분석 Endpoint를 구현한다. 예시는 `POST /api/v1/ai/analyze`이며 최종 경로는 계약을 따른다.
5. 7월 29일까지는 다음 두 실행 모드를 구분한다.
    - `mock`: 계약과 화면 연동 검증용 고정 응답
    - `local`: 실제 안전 검사·검색 모듈을 호출하는 최소 실행
6. 요청의 `correlation_id`를 로그, 처리 Context, 응답에 연결한다.
7. 입력 검증, 지원 모델 오류, 검색 결과 없음, LLM Timeout, 출력 Schema 오류를 구분한다.
8. Q-07 협의 결과에 따라 Backend↔AI Timeout과 재시도 정책을 적용한다.
    - Backend의 전체 AI 호출 Timeout은 30초로 한다.
    - AI 서비스 내부에서만 재시도를 수행한다.
    - AI 내부 최대 재시도 횟수는 1회로 제한한다.
    - Backend는 AI 요청을 자동 재시도하지 않는다.
    - 최초 호출과 AI 내부 재시도는 모두 전체 Timeout 30초 안에 종료되도록 한다.
9. AI 내부 오류를 그대로 500 문자열로 노출하지 않고 공통 오류 모델로 변환한다.
10. LLM Client는 특정 공급자 호출을 라우트·오케스트레이터 코드에 직접 작성하지 않고 인터페이스 뒤로 분리한다.
11. OpenAI 호출은 실제 키가 없을 때 Mock으로 테스트할 수 있게 하고, 호출 횟수·지연·Token 사용량 기록 지점을 마련한다.
12. RunPod·vLLM·sLLM 구현은 3주차 필수 범위에서 제외한다. `model_router.py`의 인터페이스만 공급자 교체가 가능하도록 작성한다.
13. README에 설치, 환경변수, 실행, Health Check, Mock 분석, Timeout·재시도 정책, 테스트 명령을 기록한다.

### 완료 기준

- README 절차로 다른 팀원이 AI 서버를 실행할 수 있다.
- `/health`가 서버 상태를 일관된 JSON으로 반환한다.
- 분석 Endpoint가 계약 Schema에 맞는 요청을 받고 Mock 또는 최소 분석 응답을 반환한다.
- 잘못된 입력, 미지원 모델, 내부 오류가 합의된 오류 코드와 HTTP 상태로 변환된다.
- Backend 전체 호출 Timeout이 30초로 설정되어 있다.
- AI 내부 재시도는 최대 1회로 제한된다.
- Backend 자동 재시도 0회 정책과 충돌하지 않는다.
- `correlation_id`로 요청·로그·응답을 연결할 수 있다.
- API Key와 고객 원문 전체가 로그에 노출되지 않는다.
- 최지용이 Backend Mock Client 또는 수동 호출로 정상·오류·Timeout 응답을 확인한다.

### 산출물

- 실행 가능한 FastAPI 프로젝트
- `/health`와 분석 API
- Mock·최소 실행 모드
- Timeout·재시도 설정
- 공통 오류·로그·추적 기반
- `.env.example`, 의존성 파일, `ai/README.md`
- Backend 호출 예시와 실행 증빙

---

## 3.4 `bge-m3` 임베딩·pgvector 검색과 메타데이터 필터 구현

### 작업 목적

검증된 MVP 공식 문서 청크를 임베딩하고 제품·세대·문서 정책을 필터링한 뒤 관련 청크를 검색하는 재현 가능한 RAG 기반을 만든다. 단순 유사도만 사용해 S세대·후속 모델·미검증 FAQ가 섞이는 것을 방지한다.

Q-08 협의 결과에 따라 `BAAI/bge-m3`의 원본 출력 차원을 사용하고, MVP에서는 별도의 근사 최근접 인덱스 없이 Exact Search를 적용한다.

### 작업 위치

```
ai/app/retrieval/
├─ indexing/
│  ├─ chunk_loader.py
│  ├─ embedding_indexer.py
│  └─ index_manifest.py
├─ query/
│  └─ query_builder.py
├─ filters/
│  ├─ product_filter.py
│  ├─ generation_filter.py
│  ├─ scope_filter.py
│  └─ document_policy_filter.py
├─ search/
│  └─ vector_search.py
├─ verification/
│  ├─ model_scope_validator.py
│  ├─ evidence_policy_validator.py
│  ├─ page_reference_validator.py
│  └─ faq_usage_validator.py
└─ models/
   ├─ retrieval_query.py
   ├─ retrieved_chunk.py
   └─ verified_evidence.py

ai/app/integrations/embedding/embedding_client.py
ai/app/integrations/vector_store/{vector_store,collection_manager}.py
ai/configs/retrieval_policy.yaml
ai/scripts/build_vector_index.py
ai/tests/unit/retrieval/**
ai/tests/integration/vector_store/**
```

입력·연계 경로:

```
data/processed/**                         # 김은진 주관
data/schemas/processed/**                 # 김은진 주관
backend DB Migration·Vector Table          # 최지용 주관
```

### 세부 작업 지침

1. 김은진이 검증한 구조화 청크만 `chunk_loader.py`에서 읽는다.
2. 입력 Schema에서 다음 필드를 검증한다.
    - `chunk_id`
    - 문서 ID·버전
    - 페이지
    - `model_code`
    - `manual_model`
    - `product_generation`
    - 문서 검증 상태
    - `allowed_use`
    - 청크 텍스트와 해시
3. `BAAI/bge-m3` 임베딩 Client를 구성하고 문서·질의 임베딩 생성 경로를 분리한다.
4. Q-08 협의 결과에 따라 `BAAI/bge-m3`의 원본 출력 차원을 그대로 사용한다.
    - 임의로 축소된 차원을 사용하지 않는다.
    - 문서 임베딩, 질의 임베딩, PostgreSQL Vector 칼럼의 차원을 일치시킨다.
    - 실제 차원 값은 사용 모델 설정과 DB Migration에서 동일하게 관리한다.
5. 인덱싱 시 모델명, Embedding 버전, 출력 차원, 문서 해시, 생성 시각, 대상 청크 수를 Manifest에 기록한다.
6. `WPUJAC104DWH`, `WPU-JAC104D/JCC104D`, `product_generation=D`, 공식 검증 상태를 검색 전 필터에 적용한다.
7. 다음 데이터가 검색 후보에 포함되지 않는지 검증한다.
    - S세대 근거
    - `WPUIAC425SNW` 후속 확장 데이터
    - `WPU-IAC506` 제거 대상
    - 모델 코드가 없는 미검증 FAQ
    - `allowed_use`가 고객 안내를 허용하지 않는 근거
8. Q-08과 Q-09 협의 결과에 따라 Cosine 기반 Exact Search를 구현하고 기본 검색 결과는 Top-5로 반환한다.
    - MVP에서는 HNSW Index를 사용하지 않는다.
    - MVP에서는 IVFFlat Index를 사용하지 않는다.
    - 검색 결과 개수는 설정 파일에서 조절할 수 있게 한다.
9. 검색 결과에는 점수뿐 아니라 문서·페이지·모델·세대·검증 상태를 포함하여 후속 검증기가 판단할 수 있게 한다.
10. 같은 입력과 같은 데이터·Embedding 버전에서 검색 결과를 재현할 수 있도록 설정과 Manifest를 저장한다.
11. 벡터 적재 재실행 절차와 기존 벡터 데이터 교체·초기화 방법을 README에 기록한다.
12. 대량 최적화, Hybrid Search, 별도 재정렬 모델은 3주차 필수 범위가 아니다. 인터페이스만 확장 가능하게 둔다.

### 완료 기준

- 검증된 청크가 `bge-m3`로 임베딩되어 pgvector 저장소에 적재된다.
- `bge-m3` 원본 출력 차원이 임의로 축소되지 않는다.
- 문서 임베딩·질의 임베딩·DB Vector 칼럼의 차원이 일치한다.
- MVP 검색이 HNSW·IVFFlat 없이 Exact Search로 동작한다.
- Manifest에서 모델·버전·출력 차원·문서 해시·청크 수를 확인할 수 있다.
- `WPUJAC104DWH` 검색 결과에 다른 세대·후속 모델·제거 모델·미검증 FAQ가 포함되지 않는다.
- 검색 결과가 문서·페이지·모델·세대·검증 정보를 함께 반환한다.
- 빈 검색 결과와 DB 연결 오류가 구분되어 처리된다.
- 다른 팀원이 문서화된 명령으로 벡터 적재와 대표 Top-5 검색을 재현할 수 있다.

### 산출물

- `bge-m3` 임베딩 Client·Indexer
- pgvector Exact Search·필터·검증 모듈
- 인덱싱 Manifest와 생성 Script
- 검색 설정·실행 문서
- Vector Store 단위·통합 테스트

---

## 3.5 단일 RAG 기준선과 LangGraph 최소 오케스트레이터 구성

### 작업 목적

향후 선택형 책임 분리 구조와 비교할 수 있는 단일 RAG 기준선을 만들고, 같은 입력·출력 Schema로 단계별 처리 흐름을 실행하는 최소 LangGraph 골격을 확보한다. 3주차 목표는 완성형 다중 Agent가 아니라 **모듈 경계와 분기 가능성 검증**이다.

### 작업 위치

```
ai/app/orchestration/
├─ pipelines/
│  ├─ single_rag_pipeline.py
│  └─ selective_pipeline.py
├─ stages/
│  ├─ structuring_stage.py
│  ├─ safety_check_stage.py
│  ├─ retrieval_stage.py
│  ├─ generation_stage.py
│  └─ validation_stage.py
├─ pipeline_router.py
├─ pipeline_context.py
├─ pipeline_status.py
└─ pipeline_result.py

ai/app/generation/customer_guidance/
├─ guidance_generator.py
└─ guidance_formatter.py

ai/app/validation/schema/output_schema_validator.py
ai/app/validation/grounding/evidence_grounding_validator.py
ai/tests/integration/pipeline/**
ai/evaluation/runners/pipeline_comparison_runner.py
```

### 세부 작업 지침

1. `PipelineContext`에 단계 간 전달해야 할 최소 데이터를 정의한다.
    - 문의·추적 ID
    - 사용자 입력과 제품 정보
    - 구조화 증상
    - 위험도와 현재 사용 안내
    - 검색 Query와 검색 결과
    - 검증된 근거
    - 최종 안내
    - 실패 단계·오류
2. 단일 RAG 기준선은 다음 최소 순서로 구현한다.
    - 입력 검증
    - 명시적 안전 검사
    - 공식 문서 검색
    - 근거 범위 안의 안내 생성 또는 Template 응답
    - Schema·안전 검증
3. LangGraph 골격은 다음 Stage를 순서대로 호출할 수 있게 한다.
    - `structuring_stage`
    - `safety_check_stage`
    - `retrieval_stage`
    - `generation_stage`
    - `validation_stage`
4. 3주차에는 각 Stage의 고급 Agent 기능을 완성하지 않는다. 아직 구현되지 않은 Stage는 계약을 지키는 Stub 또는 규칙 기반 최소 구현으로 둔다.
5. 위험 입력은 일반 생성·자가조치 경로로 보내지 않고 안전 응답 또는 상담 필요 결과로 분기한다.
6. 검색 근거가 없으면 생성 단계를 건너뛰거나 근거 없음 정책만 실행한다.
7. 각 단계의 시작·종료·지연·실패 위치를 추적할 수 있도록 상태를 기록한다.
8. 단일 RAG와 LangGraph 최소 구조가 같은 요청 Schema를 받고 같은 응답 Schema를 반환하도록 한다.
9. 비교 Runner에는 최소한 다음 항목을 기록한다.
    - Schema 성공 여부
    - 검색 정답 포함 여부
    - 위험 분기 일치 여부
    - 근거 없음 처리 여부
    - 전체 응답 시간
10. Backend State Machine T-023이 동시에 진행되므로 실제 상태 변경 API에 강하게 결합하지 않는다. 협의된 Mock 상태 Context와 결과 코드만 사용한다.
11. 전체 다중 Agent, 역할별 상담 요약·기사 리포트, RunPod·vLLM 전환은 필수 업무에서 제외한다.
12. Pipeline 구조와 미구현 Stage를 README 또는 설계 문서에 표시한다.

### 완료 기준

- 단일 RAG 기준선이 대표 일반 입력을 받아 검색·안내·검증 흐름을 끝까지 실행한다.
- LangGraph 최소 구조가 `구조화 → 안전 → 검색 → 안내 → 검증` Stage를 순서대로 실행한다.
- 위험 입력과 근거 없음 입력이 일반 안내 경로와 다르게 분기된다.
- 두 구조가 동일한 요청·응답 Schema를 사용한다.
- 미구현 기능이 성공한 것처럼 숨겨지지 않고 Stub·Mock·미구현 상태로 표시된다.
- AI가 문의 상태를 직접 변경하지 않고 결과 코드만 반환한다.
- 최소 비교 결과와 다음 주 구현 대상이 기록된다.

### 산출물

- 단일 RAG 기준선 Pipeline
- LangGraph 최소 오케스트레이터
- Stage Interface와 Pipeline Context
- 일반·위험·근거 없음 통합 테스트
- 기준선·제안 구조 초기 비교 결과
- 미구현 기능과 4주차 확장 목록

---

## 3.6 검색 평가·계약 테스트·7월 29일 산출물 인계

### 작업 목적

AI·RAG 구현을 “실행된다”는 수준에서 끝내지 않고, 대표 질의의 정답 근거 검색과 안전 분기 결과를 재현 가능한 평가 자료로 남긴다. 동시에 데이터 전처리 결과서와 데이터베이스·저장소 설계 문서에 들어갈 실제 파일·설정·수치를 담당자에게 전달한다.

Q-09 협의 결과에 따라 대표 P0 질의는 모두 정답 문서·페이지가 Top-5에 포함되어야 통과한다.

### 작업 위치

```
ai/evaluation/
├─ datasets/
│  ├─ safety/
│  ├─ retrieval/
│  └─ end_to_end/
├─ runners/
│  ├─ safety_runner.py
│  ├─ retrieval_runner.py
│  └─ pipeline_comparison_runner.py
├─ metrics/
│  ├─ retrieval_metrics.py
│  ├─ safety_metrics.py
│  └─ performance_metrics.py
└─ reports/**

ai/tests/contract/**
ai/tests/integration/{pipeline,vector_store}/**
ai/scripts/run_evaluation.py

data/synthetic/fixtures/**
data/synthetic/expected/**

docs/technical/ai/**
docs/submission/**
```

공동 산출물 연계:

```
[데이터 전처리] 데이터 전처리 결과서
- 김은진 주관

[데이터 수집 및 저장] 데이터베이스·저장소 설계 문서
- 최지용 주관
```

### 세부 작업 지침

1. Q-10 협의 결과에 따라 `data/synthetic/fixtures/**`를 공통 합성 시나리오의 기준본으로 사용한다.
    - AI 평가용 Fixture는 공통 기준본에서 변환하여 사용한다.
    - AI용 정상 업무 Fixture를 별도로 수정하여 다른 서비스와 상태·고객·제품 정보가 달라지지 않게 한다.
2. 김은진의 평가 세트를 AI 평가 Runner가 읽을 수 있는 형식으로 연결한다.
3. 대표 시연 질의 `SYN-JAC104-002`와 합의된 대표 P0 질의에서 다음을 검증한다.
    - 대상 모델 `WPUJAC104DWH`
    - D세대 필터 적용
    - 공식 정답 문서·페이지가 Top-5에 포함
4. Q-09 협의 결과에 따라 대표 P0 질의는 모두 통과해야 한다.
    - 대표 P0 질의 중 하나라도 정답 문서·페이지가 Top-5에 포함되지 않으면 검색 평가를 완료 처리하지 않는다.
5. 정상·위험·근거 없음·모델 불일치 사례를 최소 평가 세트에 포함한다.
6. 정답 문서·페이지의 Top-5 포함 여부를 필수 판정 기준으로 사용한다.
7. Recall@5 또는 Hit@5는 참고 지표로 계산할 수 있다.
    - 전체 평가셋의 별도 최소 Recall@5 합격선은 두지 않는다.
    - 평가 데이터 수가 적을 경우 수치의 한계를 함께 기록한다.
8. 모델·세대 불일치 근거의 허용 건수는 0건으로 한다.
9. S세대·IAC425·IAC506·미검증 FAQ가 검색 결과에 혼입되는지 별도 오염 검사를 수행한다.
10. 계약 테스트에서 JSON Schema 정상 응답과 필수 필드 누락·Enum 오류를 확인한다.
11. Pipeline 테스트에서 안전 분기와 근거 없음 Fallback을 확인한다.
12. 실행 시간은 최소 평균·최댓값 또는 단계별 지연을 기록하되, 3주차의 소규모 로컬 결과를 운영 성능으로 과장하지 않는다.
13. 데이터 전처리 결과서에 다음 자료를 김은진에게 전달한다.
- 실제 입력 청크 파일과 Schema
- 인덱싱 대상·제외 대상 기준
- Embedding 모델·원본 출력 차원·버전
- 적재 성공·실패·제외 건수
- 대표 Top-5 검색 결과와 검증 방법
1. 데이터베이스·저장소 설계 문서에 다음 자료를 최지용에게 전달한다.
- Vector Table·연결 키·Embedding Metadata
- Exact Search·거리 함수·Manifest
- AI Process·검색 결과·근거 참조 저장 필요 필드
- AI 서비스가 직접 저장하지 않는 업무 데이터 범위
1. 7월 29일까지 검토 가능한 평가 결과와 문서 입력 자료를 전달한다.
2. 7월 30~31일에는 김은진·최지용·윤승혁의 검토 의견을 반영하고 계약·검색·문서 간 불일치를 수정한다.

### 완료 기준

- 대표 P0 질의 전부에서 공식 정답 문서·페이지가 Top-5에 포함된다.
- 대표 P0 질의 중 하나라도 실패하면 검색 평가를 완료 처리하지 않는다.
- 다른 세대·후속 모델·제거 모델·미검증 FAQ의 오염이 0건이다.
- 정상·위험·근거 없음·모델 불일치 사례가 자동 또는 반복 가능한 명령으로 평가된다.
- JSON Schema 계약 테스트와 주요 안전·검색 테스트가 통과한다.
- Recall@5·Hit@5가 필수 판정 기준이 아닌 참고 지표로 구분되어 기록된다.
- 평가 결과에 입력 데이터 버전, Embedding 버전, 실행 설정이 기록된다.
- 데이터 전처리 결과서와 DB·저장소 설계 문서에 필요한 AI 자료가 **7월 29일까지** 전달된다.
- 7월 30~31일 검토 의견과 수정 내역이 Issue·PR 또는 변경 기록에 남는다.

### 산출물

- RAG 평가 데이터 연결·Runner·지표
- 대표 P0 Top-5 검색 결과
- 모델·세대 오염 검사 결과
- 계약·안전·Pipeline 테스트 결과
- 데이터 전처리 결과서 AI·RAG 입력 자료
- DB·저장소 설계 문서 Vector·AI 저장 자료
- 7월 29일 인계 기록과 후속 수정 내역

---

# 4. 조기 완료 시 추가 업무

아래 업무는 4주차 이후 WBS 중, **공통 협의 결과 Q-01~Q-10과 `contracts/**`에서 확정된 계약 및 현재 AI 내부 구조**만으로 비교적 독립적으로 착수할 수 있는 작업이다.

3주차 필수 업무·문서 인계·연동 오류 수정이 모두 끝난 경우에만 진행한다.

## 4.1 `T-032 AI·검색 Timeout·재시도·Fallback` 선행 구현

### 해당 WBS

- `T-032 AI 안정성`
- 원래 일정: 2026년 8월 4일 ~ 8월 5일

### 착수 조건

- FastAPI 분석 API와 공통 오류 모델이 확정되어 있다.
- 단일 RAG Pipeline에서 검색·LLM·검증 단계가 분리되어 있다.
- 공통 협의 결과 Q-07과 `contracts/ai/**`에 다음 정책이 반영되어 있다.
    - Backend 전체 AI 호출 Timeout 30초
    - AI 내부 최대 재시도 1회
    - Backend 자동 재시도 0회

### 작업 위치

```
ai/app/common/retry/**
ai/app/common/timeout/**
ai/app/common/errors/**
ai/configs/retry_policy.yaml
ai/tests/integration/llm/**
ai/tests/integration/pipeline/**
```

### 작업 내용

1. 검색·LLM·검증 단계별 Timeout을 설정 파일로 분리한다.
2. 최초 호출과 AI 내부 재시도가 Backend 전체 Timeout 30초 안에 종료되도록 한다.
3. 재시도 가능한 오류와 재시도하면 안 되는 입력·정책 오류를 구분한다.
4. AI 내부 재시도는 최대 1회로 제한하고 Backend의 자동 재시도를 전제로 하지 않는다.
5. 최대 재시도 초과 시 고객 입력을 잃지 않는 구조화 오류를 반환한다.
6. 재시도 횟수, 실패 단계, 최종 오류 코드를 추적한다.
7. 무응답 대신 사용자 재시도 또는 상담 전환이 가능한 결과를 반환한다.
8. Timeout·일시 오류·Schema 반복 실패 테스트를 작성한다.

### 완료 기준

- 단계별 Timeout과 재시도 횟수가 설정으로 관리된다.
- 전체 처리가 Backend Timeout 30초 안에 종료된다.
- AI 내부 재시도는 최대 1회로 제한된다.
- Backend 자동 재시도 0회 정책과 충돌하지 않는다.
- 비재시도 오류가 반복 호출되지 않는다.
- 재시도 초과 시 실패 단계와 상담·재시도 안내가 구조화 응답으로 반환된다.
- Mock LLM·Vector Store로 실패 시나리오를 재현할 수 있다.

---

## 4.2 `T-026 증상 구조화·누락 정보 확인` 골격 선행 구현

### 해당 WBS

- `T-026 증상 확인·분류 Agent`
- 원래 일정: 2026년 8월 6일 ~ 8월 7일

### 착수 조건

- 증상 입력 Schema와 표준 증상 코드가 `contracts/ai/**`에서 확정되어 있다.
- AI Pipeline Context와 Stage Interface가 구현되어 있다.
- 한예나·양정현에게 전달할 `missing_fields` 형식이 `contracts/ai/**`에 반영되어 있다.

### 작업 위치

```
ai/app/structuring/
├─ symptom_structurer.py
├─ missing_field_checker.py
├─ followup_question_generator.py
├─ duplicate_question_guard.py
└─ symptom_normalizer.py

ai/app/orchestration/stages/
├─ structuring_stage.py
└─ missing_fields_stage.py

ai/tests/unit/structuring/**
ai/evaluation/datasets/structuring/**
```

### 작업 내용

1. 대표 증상 4종과 기타 입력을 표준 코드로 정규화한다.
2. 고객 원문에서 확인된 정보와 미확인 정보를 분리한다.
3. 이미 답한 질문을 다시 생성하지 않는 Guard를 작성한다.
4. 누락 정보가 있을 때 질문과 `missing_fields`를 고정 Schema로 반환한다.
5. LLM 없이도 테스트 가능한 규칙·Fixture 기반 최소 구현을 먼저 만든다.
    - 정상 업무 Fixture는 `data/synthetic/fixtures/**`에서 변환하여 사용한다.
6. 자유 입력, 복수 증상, 이미 답한 항목, 정보 부족 사례를 테스트한다.

### 완료 기준

- 대표 증상과 자연어 입력이 표준 구조로 변환된다.
- 미확인 필드만 추가 질문 대상으로 반환된다.
- 동일 질문이 반복되지 않는다.
- 결과가 3.1에서 확정한 JSON Schema를 통과한다.
- 공통 합성 Fixture와 AI 입력 데이터의 고객·제품·문의 정보가 일치한다.

---

## 4.3 `T-031 공식 근거 없음 Fail-safe` 선행 구현

### 해당 WBS

- `T-031 AI 안전성`
- 원래 일정: 2026년 8월 20일

### 착수 조건

- 검색 결과 모델과 근거 검증기가 구현되어 있다.
- `PENDING_CONSULTATION`, `requires_consultation`, `NO_EVIDENCE` 결과 기준이 `contracts/ai/**`에 확정되어 있다.
- 정상 검색과 빈 검색을 구분할 수 있다.

### 작업 위치

```
ai/app/safety/no_evidence_policy.py
ai/app/validation/grounding/evidence_grounding_validator.py
ai/app/validation/grounding/citation_reference_validator.py
ai/app/validation/scope/product_scope_validator.py
ai/tests/unit/validation/**
ai/evaluation/datasets/safety/**
```

### 작업 내용

1. 검색 결과 없음, 모델·세대 불일치, 검증 상태 실패, 허용 정책 위반을 구분한다.
2. 사용할 수 있는 공식 근거가 없으면 안내 생성 결과를 폐기하거나 생성 단계를 건너뛴다.
3. `usage_guidance_status=PENDING_CONSULTATION`과 상담 필요 결과를 반환한다.
4. 근거가 없는 상태에서 `NORMAL`, 자가조치, 확정 진단이 반환되지 않는지 검사한다.
5. 근거 참조의 문서·페이지가 실제 검색 결과와 일치하는지 검증한다.
6. 근거 없음·잘못된 페이지·S세대·미검증 FAQ 사례를 테스트한다.

### 완료 기준

- 근거 부재·불일치·정책 위반이 서로 구분된 오류 또는 결과 코드로 기록된다.
- 공식 근거가 없을 때 임의 안내와 `NORMAL` 판정이 차단된다.
- 상담 필요와 다음 행동이 유효한 응답 Schema로 반환된다.
- 검색 결과와 인용 문서·페이지가 일치하지 않으면 검증 실패가 발생한다.

---

# 5. 완료 기준 및 최종 체크리스트

## 5.1 7월 29일 필수 완료 기준

- [ ]  Backend↔︎AI 요청·응답 JSON Schema와 Pydantic 모델이 확정되었다.
- [ ]  `risk_level`과 4개 `usage_guidance_status` 값이 공통 코드와 일치한다.
- [ ]  정상·위험·근거 없음·검증 실패 예시 JSON이 준비되었다.
- [ ]  누수·전기·화상·온수 위험 규칙과 금지 행동·표현 Guard가 구현되었다.
- [ ]  FastAPI 서버가 실행되고 `/health`가 정상 응답한다.
- [ ]  분석 API가 Mock 또는 최소 실행 모드로 계약 응답을 반환한다.
- [ ]  `bge-m3` 임베딩과 pgvector 인덱싱·검색 모듈이 실행된다.
- [ ]  모델·세대·문서 검증·허용 정책 필터가 적용된다.
- [ ]  대표 저출수 질의에서 공식 사용설명서 38페이지가 합의된 Top-k에 포함된다.
- [ ]  S세대·IAC425·IAC506·미검증 FAQ 혼입 검사가 수행되었다.
- [ ]  단일 RAG 기준선과 LangGraph 최소 골격이 같은 Schema로 실행된다.
- [ ]  위험과 근거 없음 입력이 일반 안내 경로와 다르게 처리된다.
- [ ]  데이터 전처리 결과서와 DB·저장소 설계 문서에 필요한 자료를 담당자에게 전달했다.
- [ ]  실행 명령·설정·데이터·인덱스 버전·테스트 결과가 문서화되어 있다.
- [ ]  Mock·Stub·실제 구현이 명확히 구분되어 있다.

## 5.2 7월 30일~31일 최종 정리 기준

- [ ]  최지용의 Backend Client 또는 수동 호출로 AI 정상·오류 응답을 확인했다.
- [ ]  김은진과 검색 정답·안전 기대 결과를 교차 검증했다.
- [ ]  한예나·양정현의 DTO·화면 필드와 AI 예시 응답의 불일치를 수정했다.
- [ ]  계약 테스트·검색 테스트·안전 테스트의 실패 원인을 처리하거나 Issue로 남겼다.
- [ ]  `correlation_id`로 AI 요청·단계·응답을 추적할 수 있다.
- [ ]  내부 경로·원문 전체·비밀값·개인정보가 응답과 로그에 노출되지 않는다.
- [ ]  공식 산출물의 템플릿 문구·가짜 수치가 실제 프로젝트 정보로 교체되었다.
- [ ]  4주차 필수 구현, 조기 완료 작업, 미해결 의존성을 구분해 인계했다.
- [ ]  관련 PR에 실행·테스트 방법과 검토자를 기록했다.

## 5.3 AI·RAG 역할 수행 시 주의사항

- AI·RAG 서비스에서 Inquiry·Visit 상태를 직접 변경하지 않는다.
- “환각 0%”, “100% 안전”과 같이 검증 범위를 넘어서는 표현을 문서·발표·응답에 사용하지 않는다.
- 공식 근거가 없으면 그럴듯한 자가조치를 생성하지 않고 판단 보류·상담 필요로 처리한다.
- 미검증 FAQ를 공식 매뉴얼과 같은 수준의 근거로 사용하지 않는다.
- `WPUJAC104DWH`와 적용 매뉴얼·D세대 관계를 확인하고 모델 코드 문자열 유사성만으로 적용 범위를 판단하지 않는다.
- `WPUIAC425SNW`와 `WPU-IAC506` 데이터를 MVP 인덱스에 임의로 포함하지 않는다.
- `source_path`, 원문 전체, Prompt, API Key, 개인정보를 응답·로그·평가 보고서에 노출하지 않는다.
- `data/**`를 수정할 때는 김은진, DB·Backend 연동을 수정할 때는 최지용과 협의한다.
- 3주차에는 완성형 다중 Agent·RunPod·vLLM·sLLM 전환보다 계약·검색·안전·재현성을 우선한다.
- 로컬 소규모 평가 결과를 운영 환경 성능이나 일반화된 정확도로 과장하지 않는다.

---

# 6. 지침서 작성 시 참고 문서

| 문서명 | 참고한 내용 | 지침서 반영 위치 |
| --- | --- | --- |
| `(WBS_29기_4팀) 정수기 구독 고객 케어 및 AS 업무 지원 시스템.md` | T-006, T-011, T-015, T-025, T-026, T-031, T-032 일정·선행 관계·완료 기준 | 역할 목표, 필수 업무, 추가 업무, 체크리스트 |
| `(요구사항정의서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | 증상 구조화, 위험 분류, RAG 근거, 안내 생성, 안전·응답 시간·추적 요구사항 | Schema, 안전 규칙, 검색, 평가 기준 |
| `(화면설계서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | CUST-03·04, CONS-02, TECH-02, AI 처리 상태, EvidenceCardDTO, 사용 안내·상담 분기 | 협의 사항, 응답 필드, 인계 기준 |
| `(기획서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | MVP 대상 모델, 대표 증상, 단일 RAG와 선택형 책임 분리 비교, 공식 근거·안전 원칙 | 역할 범위, 검색·Pipeline 목표 |
| `(수집데이터보고서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템(1).md` | 공식 사용설명서·FAQ·근거 레지스트리, 모델·세대·문서 검증 기준 | RAG 입력·필터·평가 업무 |
| `RAG_기술스택_업무계획서_v1(1).md` | FastAPI, LangGraph, bge-m3, pgvector, 안전 규칙, 일자별 AI 작업 계획 | 필수 업무 3.1~3.6, 추가 업무 |
| `프로젝트 디렉토리 구조.md` | 최신 `ai/app/**`, `contracts/ai/**`, `evaluation/**`, `tests/**` 경로와 계층 책임 | 모든 작업 위치 |
| `팀원별 관할 영역.md` | AI·Contracts·Data·Tests·Backend 연동의 주관할·부관할 관계 | 담당자 정보, 협의·인계 기준 |
| `공통 개발 규칙.md` | 브랜치·Issue·커밋·PR·환경변수·보안·테스트 규칙 | 완료 기준, 인계 형식, 주의사항 |
| `[데이터 전처리] 데이터 전처리 결과서.docx` | 공식 3주차 산출물의 전처리·청크·Embedding·검증 항목 | 필수 업무 3.6 |
| `[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx` | Vector Store·AI Process·근거 저장·보안·백업 항목 | 필수 업무 3.4·3.6 |

---

본 지침서는 3주차 AI·RAG 업무의 기준 문서이다. 작업 중 계약·데이터·DB 구조가 변경되면 개인 판단으로 숨겨서 반영하지 않고, 관련 담당자와 합의한 뒤 계약 파일·Issue·PR·문서 변경 기록을 함께 갱신한다.
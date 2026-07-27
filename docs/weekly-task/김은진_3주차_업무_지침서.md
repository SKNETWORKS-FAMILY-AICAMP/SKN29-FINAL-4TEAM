# 김은진 3주차 업무 지침서

> 프로젝트: 정수기 구독 고객 케어 및 A/S 업무 지원 시스템  
> 대상 기간: 2026년 7월 27일 ~ 7월 31일  
> 필수 산출물 목표 완료일: **2026년 7월 29일**  
> 7월 30일~31일 운영 원칙: 새로운 데이터 범위나 배포 기능을 무리하게 확대하기보다 **산출물 검토, 데이터·계약 정합성 확인, 테스트 재현, 오류 수정과 다음 주 진입 준비**를 우선한다.

---

# 1. 담당자 기본 정보

| 항목 | 내용 |
| --- | --- |
| 담당자 | 김은진 |
| 담당 역할 | 데이터·QA·DevOps 담당 |
| 주관할 영역 | `data/**`, `tests/**`, `infra/**`, `.github/workflows/**`, `scripts/common/**`, `scripts/data/**`, `scripts/development/**`, `scripts/testing/**`, `scripts/deployment/**`, `scripts/release/**` |
| 주요 협업 영역 | `data/processed/**`·`data/schemas/processed/**`는 이동윤, `data/synthetic/fixtures/**`·`data/schemas/synthetic/**`는 최지용, `data/synthetic/scenarios/**`는 윤승혁, 각 서비스 테스트는 검증 대상 영역 담당자와 협업 |
| 주요 협업 대상 | 윤승혁, 이동윤, 최지용, 양정현, 한예나 |
| 3주차 핵심 책임 | 공식 문서·전처리 데이터 품질 확정, RAG 평가 세트, 합성 Seed·Fixture, P0 테스트 기준, 데이터 검증 자동화, 공식 산출물 작성·검수 |
| 핵심 산출물 | 데이터 전처리 결과서, 검증 완료 전처리 데이터·Schema·품질 리포트, RAG 평가 세트, DB Seed용 합성 Fixture, 테스트 기준·기대 결과, 데이터베이스·저장소 설계 문서 공동 작성 자료 |

김은진은 공식·합성 데이터의 기준본과 팀 공통 QA 조건을 관리한다. 3주차에는 파일 수를 늘리기보다 **출처·모델·세대·Schema·기대 결과가 연결되고 반복 검증 가능한 상태**를 만드는 데 집중한다.

전체 E2E, Kubernetes 배포, 운영 모니터링과 성능 부하 테스트는 후속 주차 범위이다. 개인 업무계획서가 없으므로 본 지침서는 WBS의 `T-007`, `T-012`, `T-013`, 기존 데이터 작업 `T-008~T-010`, `T-014`, 관할 규칙과 공식 산출물 양식을 기준으로 한다.

---

# 2. 3주차 역할 목표

1. **7월 29일까지 공식 데이터 전처리 결과와 품질 검증 근거를 확정한다.**  
   WPU-JAC104D·WPU-JCC104D REV.00 공식 매뉴얼과 조건부 FAQ의 출처·버전·해시·페이지·모델 계보를 다시 확인하고, 전처리 전후 건수·Schema·참조 무결성·MVP 범위 분리 결과를 데이터 전처리 결과서에 반영한다.

2. **AI·RAG와 백엔드가 동일하게 사용할 평가·Seed·Fixture 기준을 제공한다.**  
   대표 증상별 정답 문서·페이지, 정상·위험·근거 없음·모델 불일치 기대 결과, 역할별 가상 계정·제품·구독·케어·문의 데이터를 구조화하여 이동윤과 최지용이 바로 실행 가능한 형태로 전달한다.

3. **P0 기능의 QA 기준과 자동 검증의 최소 골격을 마련한다.**  
   API·AI Schema·State Machine·권한·중복 요청·EvidenceCard 비노출 항목에 대한 인수 기준을 정리하고, 데이터 검증·계약 테스트·CI에서 재사용할 Fixture와 실행 방법을 남긴다.

3주차 필수 완료의 기준은 문서 초안만 작성하는 것이 아니다. 실제 저장소 파일·검증 스크립트·실행 결과·기대값이 서로 일치하고, 다른 담당자가 해당 자료로 개발 또는 테스트를 시작할 수 있어야 한다.

---

# 3. 3주차 필수 업무

## 3.1 공식 원본·출처 Inventory·모델 계보 재검증

### 작업 목적

전처리·검색·평가의 출발점이 되는 공식 문서가 실제 대상 제품과 일치하는지 다시 확인하고, 원본 파일의 무결성과 MVP·확장·제외 범위를 명시적으로 고정한다. 이 단계가 틀리면 이후 RAG 검색이 정확하더라도 잘못된 모델 문서를 근거로 사용할 수 있다.

### 작업 위치

```text
data/raw/
├─ manuals/mvp/skmagic_wpu_jac104d_jcc104d_rev00.pdf    # Git 제외
├─ manuals/expansion/skmagic_wpu_iac425_rev02.pdf       # Git 제외
├─ faq/snapshots/**                                     # Git 정책 확인
├─ faq/source-lists/**
├─ .gitignore
└─ README.md

data/processed/metadata/
├─ source_inventory.csv
├─ model_document_lineage.csv
├─ collection_log.csv
├─ error_missing_list.csv
└─ dataset_manifest.json

scripts/data/
├─ build_source_inventory.py
├─ build_model_lineage.py
├─ check_model_scope.py
└─ check_legacy_exclusion.py
```

### 세부 작업 지침

1. MVP 공식 매뉴얼의 파일명, 공식 모델 코드, 버전 `REV.00`, 페이지 수, 파일 크기, 등록일과 SHA-256 해시를 확인한다.
2. 확장용 WPU-IAC425 매뉴얼도 동일한 방식으로 검증하되 `mvp_use=false`, 확장 전용 범위로 기록한다.
3. `source_inventory.csv`에 다음 항목이 실제 파일과 일치하는지 확인한다.
   - `document_id`
   - `exact_sales_code`
   - `manual_model_codes`
   - `version`
   - `page_count`
   - `sha256`
   - `source_url`
   - `published_at` 또는 확인 가능한 등록일
   - `collection_status`
4. `model_document_lineage.csv`에서 판매 코드·제품 계열·문서 세대·MVP 사용 가능 여부를 분리한다.
5. WPU-IAC425와 기존 IAC506 자료가 MVP 문서 목록·RAG 파일·합성 기본 제품에 혼입되지 않았는지 검사한다.
6. 모델 코드가 없거나 적용성이 불명확한 FAQ는 임의로 모델을 추정하지 않고 `unverified`, `conditional` 또는 합의된 상태로 분류한다.
7. 파싱 실패, 원본 미확보, 모델 불일치, URL 확인 실패는 `error_missing_list.csv`에 대상·사유·대체 처리·상태를 기록한다.
8. `dataset_manifest.json`에 데이터셋 버전, 생성 시각, 입력 파일 해시, 구성 파일, 실제 건수와 생성 스크립트 버전을 기록한다.
9. `data/raw/**`에 원본 PDF를 Commit하지 않도록 `.gitignore`와 Git 추적 상태를 확인한다. 이미 추적된 파일은 단순 `.gitignore` 추가만으로 해결되지 않으므로 PM과 협의하여 Git 추적 제거 여부를 처리한다.
10. 변경된 Inventory·Lineage·Manifest는 `data/catalog/CHANGELOG.md`에 변경 이유와 영향 범위를 기록한다.

### 완료 기준

- MVP·확장 원본의 해시·버전·페이지 수가 재현 가능한 명령으로 확인된다.
- `WPUJAC104DWH`와 WPU-JAC104D D세대 공식 문서의 연결이 명시되어 있다.
- JAC104 S세대, WPU-IAC425, WPU-IAC506가 MVP 검색 대상에서 차단된다.
- 모델 미확인 FAQ가 공식 1차 근거로 분류되어 있지 않다.
- `source_inventory.csv`, `model_document_lineage.csv`, `dataset_manifest.json`의 참조가 서로 일치한다.
- 원본 PDF와 원문 스냅샷의 Git 포함 여부가 정책에 맞다.
- 실패·미확보·불일치 항목이 누락 없이 기록되어 있다.

### 산출물

- 검증된 `source_inventory.csv`
- 검증된 `model_document_lineage.csv`
- 최신 `dataset_manifest.json`
- 수집·실패·미확보 기록
- MVP·확장·제외 범위 검사 결과
- 원본 데이터 Git 관리 확인 기록

---

## 3.2 전처리 파이프라인·Schema·품질 리포트 확정

### 작업 목적

공식 문서를 페이지·청크·근거 데이터로 변환하는 과정과 품질 검증을 자동화하고, 데이터 전처리 결과서에 실제 처리 전후 건수와 문제 처리 결과를 기록한다. 템플릿의 예시 데이터와 임의 숫자는 모두 현재 프로젝트 결과로 교체해야 한다.

### 작업 위치

```text
data/processed/
├─ documents/manuals/mvp/manual_pages_jac104d.jsonl
├─ documents/manuals/expansion/                 # IAC425 페이지 추출 후속 생성 예정
├─ documents/faq/faq_snapshot_normalized.jsonl
├─ metadata/manual_keyword_hits.csv
├─ structured/rag/mvp/rag_verified_sample.jsonl
├─ structured/rag/expansion/                    # IAC425 확장 RAG 후속 생성 예정
├─ structured/faq/selected_faq_candidates.jsonl
├─ structured/evidence/jac104_evidence_registry.jsonl
└─ validation/
   ├─ schema/latest_schema_report.json
   ├─ integrity/latest_integrity_report.json
   ├─ quality/latest_quality_report.json
   └─ README.md

data/schemas/processed/
├─ manualPage.schema.json
├─ sourceInventory.schema.json
├─ ragChunk.schema.json
├─ faqCandidate.schema.json
└─ evidenceRegistry.schema.json

scripts/data/
├─ extract_manual_pages.py
├─ normalize_faq_snapshots.py
├─ build_rag_chunks.py
├─ build_evidence_registry.py
└─ validate_processed_data.py

data/catalog/
├─ datasets.yaml
├─ field_dictionary.yaml
└─ CHANGELOG.md
```

### 세부 작업 지침

1. 원본→페이지 추출→정규화→범위 분류→청크 생성→근거 레지스트리→검증의 실행 순서를 `data/README.md`와 검증 스크립트에 일치시킨다.
2. `manual_pages_jac104d.jsonl`의 각 행에 문서 ID, 제품 모델, 페이지, 추출 텍스트, 버전, 세대와 필요한 출처 키가 존재하는지 확인한다.
3. 페이지 번호는 PDF 뷰어상의 물리 페이지와 매뉴얼 표기 페이지가 혼동되지 않도록 현재 프로젝트의 기준을 문서화한다.
4. RAG 청크는 다음 항목을 최소 검증한다.
   - 고유한 `chunk_id`
   - 존재하는 `document_id`
   - 유효한 `page_refs`
   - 정확한 판매 코드와 모델 세대
   - `applicability`
   - `allowed_use`
   - 증상 또는 사용 정책 메타데이터
   - 비어 있지 않은 검색 대상 텍스트
5. `jac104_evidence_registry.jsonl`은 공식·조건부·제외 근거의 사용 가능 범위를 명시하고, 실제 RAG 청크·FAQ ID를 참조하는지 확인한다.
6. 다음 품질 이슈를 실제 데이터 기준으로 집계한다.
   - 빈 본문·NULL 필수값
   - 중복 문서·중복 페이지·중복 청크 ID
   - 잘못된 인코딩 또는 제어문자
   - 잘못된 페이지 번호
   - 존재하지 않는 문서·청크·FAQ 참조
   - 모델·세대·MVP 범위 불일치
   - 허용 정책 누락
7. 결측 항목을 임의 값으로 채우지 않는다. 필수 식별자·출처·모델·페이지·검증 상태가 누락된 자료는 검증 실패 또는 검색 제외로 처리한다.
8. `latest_schema_report.json`, `latest_integrity_report.json`, `latest_quality_report.json`에는 다음을 기록한다.
   - 실행 시각
   - 데이터셋·Schema 버전
   - 검사 대상 파일
   - 전체·통과·실패·경고 건수
   - 오류 유형별 개수
   - 실패 레코드 식별자 또는 확인 경로
   - 실행 명령과 종료 코드
9. 전처리 전후 실제 건수와 제외 사유를 계산한다. 현재 기준은 공식 PDF 2파일·96쪽의 무결성 기록, FAQ 119건, 선별 후보 20건, MVP RAG 7건, 합성 문의 24건이다. IAC425 확장 RAG 4건은 후속 생성 예정이며 현재 완료 건수에 포함하지 않는다.
10. 검증 스크립트는 오류가 존재할 때 성공 종료 코드로 끝내지 않도록 한다. 경고와 차단 오류를 구분한다.

### 완료 기준

- 주요 JSON·JSONL·CSV 파일이 각 Schema와 일치한다.
- 문서→페이지→청크→근거 레지스트리 참조가 끊기지 않는다.
- 중복·결측·인코딩·페이지·모델 범위 오류의 실제 건수가 기록된다.
- MVP와 확장 데이터가 물리적 경로와 메타데이터에서 분리되어 있다.
- 검증 실패가 발생하면 원인 레코드와 차단 여부를 확인할 수 있다.
- `data/README.md`의 실행 순서로 다른 팀원이 결과를 재생성할 수 있다.
- 데이터 전처리 결과서의 수치가 검증 리포트와 일치한다.

### 산출물

- 검증 완료 전처리·구조화 데이터
- 전처리 데이터 JSON Schema
- Schema·참조 무결성·품질 리포트
- 전처리 전후 건수·제외 사유 집계
- 데이터 필드 사전·Dataset Manifest·변경 이력
- 재현 가능한 전처리·검증 실행 절차

---

## 3.3 RAG 정답 세트·검색 평가·오염 차단 검증

### 작업 목적

AI 담당자가 구축한 임베딩·pgvector 검색이 관련 문서를 반환하는지 객관적으로 판정할 수 있도록 대표 증상별 정답 문서·페이지와 부정 사례를 제공한다. 검색 결과의 유사도만 보지 않고 모델·세대·문서 정책을 함께 검증한다.

### 작업 위치

```text
ai/evaluation/datasets/retrieval/             # 이동윤 주관, 협의 후 편집
├─ jac104_retrieval_cases.jsonl
├─ jac104_negative_scope_cases.jsonl
└─ README.md

data/synthetic/expected/
├─ evidence_references.json
└─ safety_assessments.json

tests/integration/backend-vector-store/**
tests/integration/evidence-pipeline/**
tests/safety/model-scope/**
tests/safety/grounding/**
tests/safety/faq-policy/**

docs/testing/
└─ week3-rag-evaluation-criteria.md              # 권장 경로
```

### 세부 작업 지침

1. 평가 Case는 최소 다음 필드를 포함하도록 이동윤과 합의한다.
   - `case_id`
   - `scenario_id`
   - `query`
   - `exact_sales_code`
   - `manual_generation`
   - `symptom_type`
   - `expected_document_ids`
   - `expected_page_refs`
   - `expected_chunk_ids`
   - `forbidden_document_ids`
   - `forbidden_model_codes`
   - `top_k`
   - `pass_condition`
2. 대표 저출수 질의는 `SYN-JAC104-002` 또는 합의된 Case ID로 고정하고, `WPUJAC104DWH`, D세대, 공식 매뉴얼 REV.00 38쪽을 정답 근거로 설정한다.
3. 대표 증상 4종에 대해 확보된 공식 근거 범위 안에서 평가 Case를 만든다. 아직 공식 정답 구간이 충분하지 않은 증상은 억지로 정답 청크를 만들지 않고 `insufficient_evidence` 또는 상담 연결 기대값으로 분류한다.
4. 정상 검색 Case와 함께 다음 부정 Case를 포함한다.
   - JAC104 S세대 문서 혼입
   - WPU-IAC425 확장 문서 혼입
   - WPU-IAC506 제거 자료 혼입
   - 미검증 FAQ 단독 검색
   - 존재하지 않는 모델 코드
   - 제품 모델은 맞지만 문서 정책이 차단된 자료
5. 평가 기준은 단순 유사도 임계값보다 다음을 우선한다.
   - 합의된 Top-k 안에 정답 문서·페이지가 포함되는지
   - 금지 문서가 반환되지 않는지
   - 검색 결과의 모델·세대·허용 정책이 질의와 일치하는지
   - 근거가 없을 때 빈 결과 또는 안전한 Fallback으로 이어지는지
6. Recall@k, Hit@k 또는 정답 페이지 포함 여부 중 현재 평가 규모에 적합한 지표를 선택하고, 소규모 평가 데이터라는 한계를 결과에 기록한다.
7. 이동윤이 생성한 검색 결과에는 `case_id`, 실행 설정, Embedding 모델·버전, Index Manifest, Top-k, 필터 적용 여부와 결과 순위를 남기게 한다.
8. 김은진은 정답표와 실제 결과를 비교하고 통과·실패·수동 검토 필요를 구분한다.
9. 검색 점수만 높고 모델 정책이 틀린 경우 실패로 처리한다.
10. 평가 결과에 실패 Case가 있으면 데이터 오류, 필터 오류, Index 오류, 질의 구성 오류 중 추정 원인과 담당자를 기록한다.

### 완료 기준

- 대표 저출수 질의에서 공식 매뉴얼 REV.00 38쪽이 합의된 Top-k에 포함되는지 확인할 수 있다.
- JAC104 S세대·IAC425·IAC506·미검증 FAQ의 혼입 차단 Case가 존재한다.
- 근거 없음·모델 불일치 Case의 기대 결과가 명시되어 있다.
- 평가 세트와 실제 검색 결과가 동일한 `case_id`로 연결된다.
- 평가 입력·설정·Index 버전·결과가 반복 실행 가능하게 기록된다.
- 검색 실패의 원인이 데이터·필터·인덱스·질의 중 어디에 있는지 추적 가능하다.

### 산출물

- 대표 증상별 검색 평가 데이터
- 모델·세대·FAQ 오염 차단 Case
- 시나리오별 기대 Evidence 참조
- 검색 평가 기준 문서
- 실제 Top-k 결과 검수 기록
- AI 평가 Runner 연동용 데이터 인계

---

## 3.4 합성 업무 데이터·DB Seed Fixture·기대 결과 완성

### 작업 목적

Web·Mobile·Backend·AI가 서로 다른 임의 Mock을 사용하지 않도록 역할별 계정, 제품·구독·케어, 문의 시나리오와 기대 상태·안전·근거를 하나의 기준 데이터로 제공한다. 실제 개인정보 없이 대표 흐름을 반복 재현할 수 있어야 한다.

### 작업 위치

```text
data/synthetic/
├─ scenarios/
│  ├─ demo_scenarios.json
│  ├─ self_resolution.json
│  ├─ consultation_handoff.json
│  ├─ visit_handoff.json
│  ├─ danger_escalation.json
│  ├─ no_evidence_fallback.json
│  └─ reopened_inquiry.json
├─ fixtures/
│  ├─ users.json
│  ├─ products.json
│  ├─ customer_products.json
│  ├─ subscriptions.json
│  ├─ care_histories.json
│  ├─ inquiries.json
│  ├─ consultations.json
│  ├─ visits.json
│  ├─ followup_confirmations.json
│  ├─ inquiry_status_histories.json
│  └─ audit_events.json
├─ expected/
│  ├─ workflow_states.json
│  ├─ evidence_references.json
│  ├─ safety_assessments.json
│  └─ role_handoffs.json
└─ README.md

data/schemas/synthetic/
├─ demoScenario.schema.json
├─ syntheticInquiry.schema.json
├─ syntheticFollowupConfirmation.schema.json
└─ expectedWorkflow.schema.json

data/tools/pipeline.py qa --verify-rebuild
scripts/database/seed_demo_data.py           # 최지용 주관, 협의 후 사용
scripts/database/verify_demo_data.py         # 최지용 주관, 협의 후 사용
```

### 세부 작업 지침

1. 역할별 가상 사용자를 고객·상담사·방문기사·운영 담당자로 구분하고 역할 코드·활성 상태·가상 표시명을 저장한다.
2. `products.json`에는 MVP 제품과 확장 제품을 구분한다.
   - `WPUJAC104DWH`: MVP 기본 제품
   - `WPUIAC425SNW`: 확장 전용, 기본 화면·검색에서 제외
   - IAC506: 활성 Fixture에 포함하지 않음
3. `subscriptions.json`은 사용자·제품·사용 시작일·관리 유형·구독 상태를 참조 무결성이 있는 ID로 연결한다.
4. `care_histories.json`에는 필터 교체·살균·세척 등 대표 관리 이력과 공식 기준 또는 시연 규칙에 따른 다음 케어 예정일을 포함한다.
5. 시간대와 날짜 형식은 최지용·윤승혁과 확정한 기준을 사용한다. 임의의 로컬 문자열과 ISO-8601을 혼용하지 않는다.
6. 합성 문의 24건은 8개 주제 × 3개 변형으로 구성하고 다음 업무 유형을 포함하도록 확인한다.
   - 자가 해결
   - 상담 인계·상담 후 처리
   - 방문 인계·방문 후 처리
   - 위험 감지·사용 제한
   - 근거 없음·판단 보류
   - 후속 확인에서 미해결·문의 재개
7. 각 시나리오에 다음 기대값을 연결한다.
   - 대표 증상·고객 원문
   - 위험도
   - `usage_guidance_status`
   - `restricted_functions`
   - 공식 근거 문서·페이지·청크
   - 상담·방문 필요 여부
   - 상태·이벤트 순서
   - 현재 담당 주체
   - `allowed_actions`
   - 최종 해결 여부
8. `SYN-JAC104-002`와 `DEMO-INQ-002`는 대표 저출수 E2E 기준으로 고정하고, 다른 파일에서도 동일 ID를 사용한다.
9. Fixture ID는 중복되지 않고 다른 파일의 FK 참조가 모두 존재해야 한다.
10. Seed는 반복 실행해도 중복 행이 증가하지 않도록 최지용과 자연키·고유 ID·Upsert 정책을 확정한다.
11. `data/tools/pipeline.py qa --verify-rebuild`에서 Schema, ID 중복, FK 참조, 상태·코드 유효성, Evidence 참조, MVP 범위, 개인정보 패턴과 대표 E2E 문서 불변식을 검사한다.

### 완료 기준

- 역할별 계정과 제품·구독·케어 데이터가 DB에 적재 가능한 구조이다.
- 합성 문의 24건이 8개 주제 × 3개 변형의 서로 다른 업무 흐름과 기대 결과를 가진다.
- 모든 FK·상태·근거 참조가 유효하다.
- 동일 Seed를 반복 실행해도 중복 데이터가 생성되지 않는 정책이 확정되어 있다.
- 실제 개인정보·운영 연락처·실제 상담 기록이 포함되어 있지 않다.
- `SYN-JAC104-002`, `DEMO-INQ-002`, 공식 38쪽 근거가 일관되게 연결된다.
- Web·Mobile·Backend·AI 담당자가 같은 Fixture ID와 기대 결과를 사용할 수 있다.

### 산출물

- 역할별 가상 계정·제품·구독·케어 Fixture
- 합성 문의 24건 기준본
- 상태·근거·안전·인계 기대 결과
- Synthetic JSON Schema
- Seed 적재·검증 자료
- 화면·API 테스트용 최소 Mock Projection

---

## 3.5 P0 QA 기준·계약 테스트 Fixture·데이터 CI 최소 골격 구성

### 작업 목적

팀원별로 “동작한다”는 기준이 달라지지 않도록 P0 기능의 인수 기준을 작성하고, 계약·데이터 오류를 조기에 발견할 수 있는 테스트 구조를 마련한다. 3주차에는 전체 자동 테스트를 완성하기보다 핵심 계약과 데이터가 변경될 때 실패를 감지하는 최소 골격을 우선한다.

### 작업 위치

```text
tests/
├─ contract/
│  ├─ api/**
│  ├─ ai/**
│  ├─ state-machine/**
│  ├─ codes/**
│  └─ error-codes/**
├─ fixtures/
│  ├─ api/**
│  ├─ ai/**
│  ├─ errors/**
│  └─ mocks/**
├─ helpers/**
├─ config/local.yaml
├─ conftest.py
└─ README.md

scripts/testing/
├─ run_contract_tests.py
└─ collect_test_reports.py

.github/workflows/
├─ data-ci.yml
└─ contracts-ci.yml                    # 윤승혁·계약 주관자와 협의

docs/testing/
├─ week3-p0-acceptance-criteria.md      # 권장 경로
├─ test-case-matrix.md                  # 권장 경로
└─ results/**
```

### 세부 작업 지침

1. WBS `T-007`의 인수 기준을 기능·AI·RAG·안전·State Machine·권한·중복 요청·Evidence 비노출로 나눈다.
2. 테스트 Case에는 최소 다음 항목을 둔다.
   - Case ID
   - 관련 요구사항·WBS
   - 대상 기능·역할
   - 선행 상태·입력 Fixture
   - 실행 단계
   - 기대 HTTP 상태·업무 코드
   - 기대 데이터·상태·`allowed_actions`
   - Evidence·안전 기대값
   - 비노출·보안 확인
   - 자동·수동 구분
   - 담당자와 증빙 위치
3. 3주차 최소 인수 Case를 다음과 같이 구성한다.
   - 가상 로그인 정상·실패·역할 부족
   - 고객 본인 데이터만 조회
   - 기사 미배정 건 접근 차단
   - 문의 생성과 같은 `inquiry_id` 입력 누적
   - 필수값 누락·미지원 제품·차단 모델
   - Backend↔AI 정상 Schema와 필수 필드 누락
   - 일반·주의·위험·근거 없음 사용 안내
   - State Machine 허용·금지 이벤트
   - 동일 `idempotency_key` 재전송
   - 잘못된 `state_version` 충돌
   - EvidenceCard의 내부 경로·원문 전체·검색 점수 비노출
4. 실제 기능이 아직 미구현된 Case는 `blocked`, `not_implemented`, `fixture_ready`로 구분하고 실패를 숨기지 않는다.
5. API Contract Fixture는 최지용의 OpenAPI 예시를 복제하지 않고 가능한 경우 계약 파일을 직접 읽어 검증한다.
6. AI Contract Fixture는 이동윤의 Pydantic·JSON Schema와 동일한 Enum·필수 필드를 사용한다.
7. State Machine 테스트는 윤승혁이 확정한 상태·이벤트·가드·역할별 `allowed_actions`를 기준으로 한다.
8. 오류 Fixture는 400·401·403·404·409·422·5xx·Timeout·파싱 실패를 구분한다.
9. Data CI에는 다음 검사를 우선 포함한다.
   - `data/raw/` 원본 Git 포함 여부
   - JSON·JSONL·CSV 구문
   - JSON Schema 일치
   - ID·페이지·문서·근거 참조 무결성
   - MVP·확장 데이터 혼입
   - IAC506 활성 데이터 존재 여부
10. Contracts CI는 3주차에 계약 파일이 실제로 존재하고 실행 명령이 확정된 항목부터 시작한다. 비어 있는 Workflow를 성공으로 표시하지 않는다.
11. CI에서 원본 PDF·LLM API·외부 Vector Store가 없어도 기본 데이터·Schema 검증이 가능하도록 Mock 또는 저장소 내 구조화 데이터만 사용한다.
12. 각 개발 담당자에게 7월 29일까지 제공해야 할 최소 증빙 형식을 전달한다.
   - 실행 명령
   - 정상 결과
   - 오류·예외 결과
   - 사용 Fixture
   - 미구현·제한 사항
   - PR 또는 Commit

### 완료 기준

- P0 기능·AI·RAG·안전·State Machine·권한의 최소 인수 기준이 문서화되어 있다.
- 정상·오류·권한·근거 없음·모델 불일치 Fixture가 준비되어 있다.
- Data 검증 명령이 로컬에서 성공·실패를 올바른 종료 코드로 반환한다.
- 가능한 계약 항목은 자동 검증 골격 또는 실행 계획이 있다.
- 개발 담당자별 완료 증빙 형식이 통일되어 있다.
- 미구현 Case가 통과로 표시되지 않는다.
- 테스트 원시 결과와 승인된 요약 문서의 저장 위치가 구분된다.

### 산출물

- P0 테스트·인수 기준 문서
- 요구사항–테스트 Case 매트릭스
- 계약·오류·Mock Fixture
- Data·Contract Test 실행 스크립트 또는 최소 골격
- `data-ci.yml`과 필요한 계약 CI 초안
- 테스트 결과·증빙 저장 규칙

---

## 3.6 7월 29일 공식 산출물 작성·공동 검수·인계

### 작업 목적

3주차 코드와 데이터 작업을 공식 제출 양식에 실제 프로젝트 결과로 정리한다. 템플릿의 기수·팀명·예시 사용자·예시 테이블·예시 수치가 남아 있거나, 구현과 문서의 설명이 다르면 완료로 보지 않는다.

### 작업 위치

```text
[데이터 전처리] 데이터 전처리 결과서.docx                # 제공 템플릿
[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx  # 제공 템플릿

docs/submission/
├─ data-preprocessing-result.md                         # 권장 원본 경로
└─ database-storage-design.md                           # 최지용 주관, 공동 작성

docs/testing/results/**
data/README.md
tests/README.md
```

### 세부 작업 지침

1. 데이터 전처리 결과서의 작성 팀원, 제출일, GitHub 경로, 프로젝트명과 기수 정보를 실제 값으로 교체한다.
2. 원천 데이터 현황에는 실제 파일·페이지·FAQ·청크·시나리오 수와 출처·버전·사용 범위를 적는다.
3. 템플릿의 8,000건·79건·649건·512토큰·50 오버랩 등 예시 수치는 현재 프로젝트 실행 결과가 아니면 모두 제거한다.
4. 품질 이슈 표에는 실제로 확인한 결측·중복·인코딩·페이지·참조·모델 범위 문제와 처리 건수를 적는다.
5. 전처리 파이프라인 흐름도는 원본→페이지 추출→출처·계보→MVP·확장 분류→RAG 청크·근거 레지스트리→Schema·무결성 검증→인덱싱·Seed 활용 순서로 정리한다.
6. 학습·검증·테스트 80/10/10 분할을 기계적으로 사용하지 않는다. 현재 프로젝트는 학습 데이터셋보다 공식 RAG·정답 평가·합성 시나리오가 중심이므로, 목적별 데이터 분리 기준으로 재작성한다.
7. RAG 후속 활용에는 실제 청크 파일, Embedding 모델·설정, Vector Store, 인덱싱 대상·제외 건수, 대표 검색 결과와 재현 명령을 이동윤에게 받아 반영한다.
8. 재현성 항목에는 원본 해시, Dataset Manifest, Schema 버전, 생성 스크립트, 실행 명령, 평가 Case ID를 기록한다.
9. 데이터베이스·저장소 설계 문서에는 김은진 담당 영역을 다음과 같이 작성한다.
   - 관계형 DB·Vector Store·파일 저장소의 데이터 분류
   - 원본·전처리·합성·테스트 데이터 저장 위치
   - Seed·Fixture 적재와 초기화 원칙
   - Schema·참조·중복·모델 범위 품질 검증
   - 실제 개인정보·원본 PDF·비밀값 관리
   - 백업·복구 대상과 제외 대상
   - 테스트·시연 데이터 재현 절차
10. DB 설계 문서 템플릿의 `users`, `oauth_accounts`, `chat_rooms` 등 예시 테이블은 현재 ERD의 사용자·제품·구독·케어·문진·문의·상담·방문·상태 이력 구조로 최지용이 교체했는지 검수한다.
11. Vector Store 설명에는 업무 DB와 벡터 저장소의 책임을 구분하고, 청크 ID·문서 ID·페이지·모델·세대·사용 정책을 연결하는 방법을 기록한다.
12. 두 문서의 수치·파일 경로·필드명이 실제 저장소와 일치하는지 교차 확인한다.
13. 7월 29일까지 본문이 모두 작성되고 실제 증빙 링크가 연결된 검토본을 윤승혁에게 전달한다.

### 완료 기준

- 데이터 전처리 결과서가 실제 프로젝트 데이터·수치·경로·도구로 작성되어 있다.
- 템플릿의 다른 기수·다른 팀·예시 데이터가 남아 있지 않다.
- 데이터 전처리 결과서의 수치가 Manifest·품질 리포트·검색 평가 결과와 일치한다.
- 데이터베이스·저장소 설계 문서의 데이터 분류·Seed·품질·보안 항목이 실제 구조와 일치한다.
- 관계형 DB·Vector Store·파일 저장소의 책임과 연결 키가 구분되어 있다.
- 7월 29일까지 두 문서가 팀 검토 가능한 상태이다.
- 7월 30~31일 수정 사항과 미해결 이슈가 변경 기록에 남는다.

### 산출물

- 데이터 전처리 결과서 검토본·완료본
- 데이터베이스·저장소 설계 문서 공동 작성 내용
- 실제 건수·품질·검색 평가 결과표
- 산출물 검수 기록과 변경 이력
- 다음 주 인계 사항·미해결 Issue 목록

---

# 4. 조기 완료 시 추가 업무

필수 업무, 7월 29일 산출물 작성과 팀 검토 대응이 끝난 뒤에만 착수한다. 아래 업무는 3번에서 확정된 Schema·상태·Fixture만으로 비교적 독립적으로 진행할 수 있는 후속 작업을 선정한 것이다.

## 4.1 계약·데이터 CI 실행 범위 확대

### 해당 후속 업무

- 후속 통합·검증 단계의 `T-048`, `T-050`, `T-053` 준비
- `.github/workflows/data-ci.yml`, `contracts-ci.yml`의 실사용 골격

### 착수 조건

- 전처리·합성 Schema가 확정되어 있다.
- 계약 검증 명령과 저장 경로가 3번 협의에서 정해져 있다.
- 로컬 검증 스크립트가 안정적으로 성공·실패 종료 코드를 반환한다.

### 작업 위치

```text
.github/workflows/data-ci.yml
.github/workflows/contracts-ci.yml
scripts/testing/run_contract_tests.py
scripts/data/validate_processed_data.py
scripts/data/validate_synthetic_data.py
scripts/contracts/**
docs/technical/ci/**
```

### 작업 내용

- 변경 경로에 따라 데이터 또는 계약 검증을 실행한다.
- Python 버전과 의존성 설치 방법을 고정한다.
- JSON Schema·참조·모델 범위·Legacy 제외 검사를 Workflow에 연결한다.
- 테스트 결과 요약을 GitHub Actions Log 또는 Artifact로 남긴다.
- 원본 PDF·외부 LLM·실제 Vector Store가 없어도 기본 검증이 실행되게 한다.
- 실패를 허용해야 하는 미완성 검사는 별도 Job 또는 명시적 보류로 구분한다.

### 완료 기준

- 데이터 또는 계약 오류를 의도적으로 넣었을 때 CI가 실패한다.
- 정상 파일에서는 CI가 성공한다.
- 실행 명령이 로컬과 CI에서 동일하거나 차이가 문서화되어 있다.
- 원본·비밀값이 Artifact나 Log에 노출되지 않는다.

---

## 4.2 대표 E2E Scenario·Assertion 골격 선행 작성

### 해당 후속 업무

- `T-050` 역할별 화면·상태 검증
- `T-052` 대표 시연 Seed·초기화·대본 준비

### 착수 조건

- 대표 6개 시나리오와 `workflow_states.json`, `safety_assessments.json`, `evidence_references.json`이 확정되어 있다.
- API가 없어도 Mock Client 또는 Fixture만으로 기대값을 읽을 수 있다.

### 작업 위치

```text
tests/e2e/scenarios/**
tests/e2e/assertions/
├─ workflow_assertions.py
├─ evidence_assertions.py
├─ safety_assertions.py
└─ handoff_assertions.py

tests/fixtures/api/**
docs/testing/e2e-scenario-matrix.md
```

### 작업 내용

- 대표 6개 시나리오의 입력·상태·근거·인계 기대값을 공통 Assertion 함수로 검증할 수 있게 한다.
- 실제 API 호출 없이 Expected 파일만 검증하는 Dry-run 테스트부터 작성한다.
- `SYN-JAC104-002` 기준으로 고객→AI 안내→상담→방문→후속 확인의 예상 단계 목록을 정리한다.
- 위험·근거 없음·문의 재개 시나리오는 일반 흐름과 별도 Assertion을 둔다.
- 나중에 실제 Client가 붙을 위치와 현재 Mock 범위를 명시한다.

### 완료 기준

- Expected 파일의 상태·근거·안전·인계 참조 오류가 자동 검출된다.
- 대표 6개 시나리오의 Case ID와 기대 결과가 테스트에서 연결된다.
- 실제 API가 추가되어도 Assertion을 재사용할 수 있는 구조이다.
- 아직 실행하지 않은 E2E를 완료된 통합 테스트로 표현하지 않는다.

---

## 4.3 로컬 통합 환경·Smoke Test 준비 골격

### 해당 후속 업무

- `T-046` 통합 개발 준비
- `T-053` Docker 실행·초기화·Smoke Test 준비

### 착수 조건

- 각 서비스의 실행 명령과 Health Endpoint가 3번 협의에서 확인되어 있다.
- 실제 배포가 아니라 로컬 실행·준비 확인 범위로 제한한다.
- Docker 설정을 수정할 경우 최지용과 서비스 담당자의 확인을 받을 수 있다.

### 작업 위치

```text
infra/docker/**
scripts/development/
├─ check_environment.py
├─ start_local.py
├─ stop_local.py
├─ wait_for_services.py
└─ print_service_urls.py

tests/smoke/local/**
tests/config/local.yaml
docs/deployment/local-development.md
```

### 작업 내용

- Python·Node·JDK·Docker·환경변수의 설치·누락 상태를 검사하는 스크립트를 준비한다.
- DB·Backend·AI의 Health Endpoint를 기다리고 실패 원인을 구분한다.
- 대표 Seed 존재 여부와 기본 API 응답을 확인하는 로컬 Smoke Test 골격을 작성한다.
- 서비스가 아직 없는 경우 Mock·Skip 사유를 명확히 기록한다.
- 비밀값은 `.env.example`에 이름만 공개하고 실제 값은 Commit하지 않는다.
- 전체 Kubernetes 배포·Cloud IAM·운영 모니터링은 착수하지 않는다.

### 완료 기준

- 로컬 환경의 필수 도구·환경변수 누락을 한 명령으로 확인할 수 있다.
- 준비된 서비스에 대해 Health 확인과 기본 Smoke 실행이 가능하다.
- 미구현 서비스는 실패 또는 명시적 Skip으로 구분된다.
- 실행·종료·초기화 방법이 문서화되어 있다.

---

# 5. 완료 기준 및 최종 체크리스트

## 5.1 7월 29일 필수 완료 기준

- [ ] MVP·확장·제외 모델의 범위와 모델 계보가 확정되어 있다.
- [ ] 공식 원본의 버전·페이지 수·SHA-256 해시가 검증되어 있다.
- [ ] 원본 PDF·FAQ 원문이 Git 정책에 맞게 관리된다.
- [ ] 전처리 JSON·JSONL·CSV가 Schema 검증을 통과한다.
- [ ] 문서→페이지→청크→근거 참조 무결성이 확인되었다.
- [ ] 중복·결측·인코딩·페이지·모델 범위 품질 결과가 실제 건수로 기록되었다.
- [ ] 대표 저출수 검색 평가 Case와 공식 38쪽 정답이 준비되어 있다.
- [ ] JAC104 S세대·IAC425·IAC506·미검증 FAQ 혼입 차단 Case가 있다.
- [ ] 역할별 사용자·제품·구독·케어·문의 Seed Fixture가 준비되어 있다.
- [ ] 합성 문의 24건과 상태·안전·근거·인계 기대 결과가 연결되어 있다.
- [ ] Synthetic Fixture의 ID·FK·Schema·개인정보 검증이 완료되었다.
- [ ] P0 테스트 기준과 요구사항–테스트 Case 매트릭스가 작성되어 있다.
- [ ] Data 검증 명령 또는 최소 CI 골격이 실행 가능하다.
- [ ] 데이터 전처리 결과서가 실제 프로젝트 데이터와 수치로 작성되어 있다.
- [ ] 데이터베이스·저장소 설계 문서의 데이터·Seed·품질·보안 항목이 작성되어 있다.
- [ ] 7월 29일까지 검토 가능한 PR 또는 공유 산출물이 있다.

## 5.2 7월 30일~31일 최종 정리 기준

- [ ] 이동윤의 실제 인덱싱·검색 결과가 평가표와 전처리 결과서에 반영되었다.
- [ ] 최지용의 최신 Migration·ERD에 맞게 Seed Fixture와 DB 설계 문서가 수정되었다.
- [ ] Web·Mobile Mock이 공통 Fixture·표준 코드·비노출 기준과 일치한다.
- [ ] 데이터·AI·API·State Machine 계약 변경이 Expected 파일과 테스트 기준에 반영되었다.
- [ ] 검증 실패·차단 결함·후속 개선 사항이 Issue로 분리되어 있다.
- [ ] 다른 팀원이 README와 실행 명령으로 데이터 검증을 재현할 수 있다.
- [ ] 테스트 원시 결과와 사람이 승인한 요약 결과가 구분되어 있다.
- [ ] 공식 산출물의 템플릿 예시·더미 수치·다른 팀 정보가 제거되었다.
- [ ] PM 검토 의견과 수정 내역이 변경 기록에 남아 있다.
- [ ] 필수 업무와 리뷰 대응이 끝난 뒤에만 4장의 추가 업무를 시작했다.

## 5.3 데이터·QA·DevOps 역할 수행 시 주의사항

- 공식 원본은 수정하지 않고 `data/raw/**`에 전처리 결과를 저장하지 않는다.
- 공식 원본 PDF와 FAQ 원문은 Git 저장소에 올리지 않는다.
- 데이터 건수는 문서에 맞춰 임의로 작성하지 않고 스크립트 실행 결과를 사용한다.
- 모델·세대·문서 정책이 틀리면 유사도가 높아도 실패로 처리한다.
- 실제 개인정보·실제 상담·방문 기록·운영 비밀값을 Fixture와 Log에 넣지 않는다.
- `data/synthetic/**`는 서비스가 사용하는 기준 업무 데이터이고, `tests/fixtures/**`는 오류·Mock 등 테스트 도구용 소규모 입력이다.
- AI·API·State Machine 계약의 의미를 QA가 단독으로 변경하지 않는다.
- 테스트가 실패하면 원인을 기록하고 담당자와 해결하며, 검사를 삭제하거나 성공으로 우회하지 않는다.
- CI·Docker·Kubernetes 구조를 한꺼번에 만들지 않고 실제 실행 명령이 확보된 항목부터 자동화한다.
- 테스트 결과에는 실행 환경, Commit, 데이터·Schema 버전과 사용 Fixture를 남긴다.
- 원시 리포트는 `tests/reports/**`, 사람이 승인한 결과는 `docs/testing/results/**`에 구분한다.
- `contracts/**`, `scripts/database/**`, 서비스 고유 테스트를 수정할 때는 해당 주관할 담당자와 협의한다.

---

# 6. 지침서 작성 시 참고 문서

| 문서명 | 참고한 내용 | 지침서 반영 위치 |
| --- | --- | --- |
| `(WBS_29기_4팀) 정수기 구독 고객 케어 및 AS 업무 지원 시스템.md` | `T-007` 테스트 설계, `T-008~T-014` 데이터·평가·합성 데이터, `T-015` 안전 협업, `T-016~T-025` 개발 검수, `T-048·T-050·T-051·T-053` 후속 QA·DevOps 작업 | 1장 역할 범위, 2장 목표, 3장 필수 업무, 4장 추가 업무 |
| `(요구사항정의서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | 공식 근거·근거 부재·안전·Schema·응답 시간·중복 방지·권한·개인정보·추적·상태 가시성·데이터 요구사항 | 3.3~3.5 평가·테스트, 5장 체크리스트 |
| `(화면설계서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | CUST·CONS·TECH 화면의 데이터 필드, EvidenceCardDTO 공개·비노출 항목, 상태·`allowed_actions`, 정상·위험·근거 없음 시나리오 | 3.4 Fixture, 3.5 QA 기준 |
| `(기획서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템.md` | MVP 제품·대표 증상·역할별 흐름·공식 근거·안전 원칙·가상 데이터 사용 범위 | 1장 역할 해석, 2장 목표, 3.1·3.3·3.4 데이터 범위 |
| `(수집데이터보고서_29기_4팀) 정수기 구독 고객 케어 및 A_S 업무 지원 시스템(1).md` | 공식 매뉴얼·FAQ·합성 시나리오 현황, 파일·필드, 수집·전처리 절차, 품질·무결성 기준과 변경 이력 | 3.1 원본 검증, 3.2 전처리·수치, 3.6 공식 산출물 |
| `프로젝트 디렉토리 구조.md` | `data/**`, `scripts/**`, `tests/**`, `.github/**`, `infra/**`, `docs/**`의 권장 파일·책임·처리 흐름 | 1장 관할, 3장 작업 위치 전체, 4장 추가 업무 |
| `팀원별 관할 영역.md` | Data·Infra·Workflow·Script·Test의 주관할·부관할 관계와 공식 원본 수정 제한 | 1장 기본 정보, 5.3 주의사항 |
| `공통 개발 규칙.md` | 브랜치·Issue·커밋·PR, 환경변수·비밀값, API 계약, 로그·오류, 테스트·완료 기준 | 3.5 CI·테스트, 3.6 산출물 인계, 5장 체크리스트 |
| `[데이터 전처리] 데이터 전처리 결과서.docx` | 전처리 목적·원천 데이터·품질 이슈·파이프라인·분할·후속 활용·재현성·변경 이력 제출 양식 | 3.2 전처리 검증, 3.6 산출물 작성 |
| `[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx` | 관계형 DB·테이블·제약·무결성·저장소·변경 이력 제출 양식 | 3.4 Seed, 3.6 공동 작성 |
| `RAG_기술스택_업무계획서_v1(1).md` | 이동윤의 bge-m3·pgvector·FastAPI·LangGraph·검색 평가 일정과 필요한 데이터 입력 | 3.3 검색 평가 |
| `최지용_업무계획표_v0.1(1).md` | ERD·Migration·인증·Seed·ID·시간대·State Machine·API 결정 사항 | 3.4 Fixture |
| `이동윤_3주차_업무_지침서.md` | AI Schema·안전 규칙·RAG 검색·평가·7월 29일 산출물 인계 기준 | 3.2~3.3 전처리·평가 |
| `최지용_3주차_업무_지침서.md` | ERD·Migration·Seed·문의·State Machine·API·공식 산출물 인계 기준 | 3.4 Seed, 3.5 테스트, 3.6 DB 문서 검수 |
| `윤승혁_3주차_업무_지침서.md` | 7월 29일 산출물 완료 원칙, 데이터·계약·State Machine 승인, 차단 오류와 다음 주 진입 기준 | 문서 전체 일정·승인·완료 기준 통일 |

---

본 지침서의 필수 업무는 **7월 29일까지 실제 데이터·검증 결과·평가 세트·Seed Fixture·공식 문서를 검토 가능한 상태로 만드는 것**을 기준으로 한다. 7월 30일~31일에는 데이터·DB·AI·화면 계약 변경 반영, 검증 실패 수정, 산출물 수치·경로 재확인과 리뷰 의견 반영을 우선하며, 이 작업이 끝난 경우에만 4장의 추가 업무를 수행한다.

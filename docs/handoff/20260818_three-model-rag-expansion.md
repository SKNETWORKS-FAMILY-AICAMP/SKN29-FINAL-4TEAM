# 정수기 3모델 데이터 전처리·RAG 상세 인계서

## 1. 문서 목적과 현재 결론

이 문서는 기존 `WPUJAC104DWH` 단일 모델 RAG 범위를
`WPUIAC425SNW`, `WPUIAC606SNW`까지 확대하면서 수행한 원본 검증,
데이터 전처리, RAG 후보 생성, 평가 데이터 작성, QA 결과와 후속 담당자의
작업을 기록한다.

데이터 전처리와 RAG 인계 후보 준비는 완료됐다. 하지만 신규 두 모델은
Backend와 Public API 계약에서 아직 허용되지 않고 실제 Vector DB에도
적재되지 않았다. 따라서 현재 상태를 다음과 같이 구분한다.

- `WPUJAC104DWH`: 기존 MVP 데이터와 Runtime 상태를 유지한다.
- `WPUIAC425SNW`, `WPUIAC606SNW`: 제한된 범위의 RAG 데이터는 준비됐지만
  Backend 계약과 실제 인덱싱이 완료되지 않았다.
- 이 문서의 완료는 데이터 준비 완료를 의미하며 서비스 활성화 완료나
  RAG 성능 합격을 의미하지 않는다.

2026-08-19 재검증 기준 Git HEAD는
`2b251d8a3e1f72703a2fee0ec37003365d9a4b7f`다. 검증 시작과 종료 시 HEAD는
같았고, `backend/**`와 `ai/**`의 추적 파일은 이 데이터 작업에서 수정하지
않았다.

## 2. PM 결정의 적용 범위

PM 결정은 공식 매뉴얼과 판매코드의 정합성이 확인된 정수기를 추가해
RAG 활용성과 모델 간 검색 격리 성능을 검증한다는 의미로 적용했다.

이번 결정으로 승인된 범위는 다음과 같다.

- 신규 모델의 공식 원본 등록과 계보 관리
- 매뉴얼 페이지 전처리와 사람이 확인할 수 있는 보정 이력 기록
- 검색 후보 Child, 문맥용 Parent, Evidence Group 생성
- 모델 혼입을 검증하기 위한 평가 Case 작성
- AI 담당자가 적재·평가할 수 있는 `rag-expansion` 인계 프로필 제공

다음 항목은 이번 결정만으로 승인된 것으로 해석하지 않았다.

- Public API가 허용하는 제품코드 변경
- Backend Model, Migration, Importer 또는 업무 로직 변경
- PostgreSQL·pgvector 실제 적재
- 신규 제품의 고객제품, 구독 또는 문의 데이터 생성
- 실제 서비스 Runtime 활성화

## 3. 지원 모델과 활성화 경계

| 정확 판매코드 | 매뉴얼 모델 | 문서 ID | 데이터 상태 | Runtime 상태 |
|---|---|---|---|---|
| `WPUJAC104DWH` | WPU-JAC104(D) / WPU-JCC104(D) | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00` | `MVP_VERIFIED` | `INDEXED_MVP` |
| `WPUIAC425SNW` | WPU-IAC425 | `MAN-SKMAGIC-WPU-IAC425-REV02` | `RAG_READY_LIMITED_SCOPE` | `CONTRACT_BLOCKED_NOT_INDEXED` |
| `WPUIAC606SNW` | WPU-IAC606 | `MAN-SKMAGIC-WPU-IAC606-REV00` | `RAG_READY_LIMITED_SCOPE` | `CONTRACT_BLOCKED_NOT_INDEXED` |

공동 매뉴얼에 기재된 WPU-JCC104(D)는 정확 판매코드를 확인하지 못했으므로
활성 제품이 아니라 비활성 매뉴얼 별칭으로만 유지한다. WPU-IAC506,
존재하지 않는 모델, 판매코드가 확인되지 않은 제품과 모델 미검증 FAQ는
검색 대상에 포함하지 않는다.

지원 모델의 기계 판독 레지스트리는
`data/config/rag/supported_products.json`이다. 신규 두 모델을 Runtime에서
허용할 때도 표시명이나 모델군이 아니라 `exact_sales_code`를 기준으로
처리해야 한다.

## 4. 공식 원본과 계보

| Inventory ID | 판매코드 | 매뉴얼·리비전 | 페이지 | 파일 크기 | SHA-256 |
|---|---|---|---:|---:|---|
| `SRC-JAC104D-MANUAL` | `WPUJAC104DWH` | WPU-JAC104(D) / JCC104(D), REV.00 | 44 | 5,131,906 bytes | `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C` |
| `SRC-IAC425-MANUAL` | `WPUIAC425SNW` | WPU-IAC425, REV.02 | 52 | 8,571,676 bytes | `97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8` |
| `SRC-IAC606-MANUAL` | `WPUIAC606SNW` | WPU-IAC606, REV.00 | 48 | 8,448,650 bytes | `A062C0DD5C2ED17BC3734215C3106DCC82AB69346CF546BDDD9EDD328EA49572` |

세 매뉴얼은 외부 원본 디렉터리의 PDF를 직접 읽어 파일 크기, 전체
SHA-256과 페이지 수를 검증했다. 공식 원문 PDF는 저작권과 저장소 정책에
따라 Git에 추가하지 않았다. 저장소에는 원본을 다시 확인할 수 있도록
공식 URL, 외부 상대 위치, 리비전, 파일 크기, 페이지 수와 SHA-256만
`data/processed/metadata/source_inventory.csv`에 기록했다.

현재 `source_inventory.csv` 전체 파일 SHA-256은
`7DCB539727FD8E5E8CE235626D160065BFDA9898C3FBC6FE03EB62CFF040DB1D`다.
기존 JAC104 canonical import 설정도 이 변경된 Inventory 해시를 참조하도록
`data/config/evidence/backend_ai_canonical_import_v1.json`을 갱신했다.

Q&A 원본에는 119건이 있지만 신규 두 판매코드를 직접 지정한 FAQ가 없다.
따라서 FAQ 전체를 3모델 RAG 코퍼스에 자동 편입하지 않았고 참고 전용으로
남겼다. FAQ 문장이 제품 기능과 비슷하다는 이유만으로 특정 모델의 근거로
사용하면 안 된다.

## 5. 전처리 방식과 보정 이력

### 5.1 전체 페이지 보존

세 매뉴얼의 전체 144쪽은 페이지 단위 JSONL로 보존했다.

- JAC104: 44쪽
- IAC425: 52쪽
- IAC606: 48쪽

전체 페이지 데이터는 원문 확인과 재전처리를 위한 `REFERENCE_ONLY`다.
144쪽 전체를 검색 인덱스에 넣는 것이 아니다. 실제 검색 후보는 사람이
PDF 렌더링과 추출 문장을 대조한 15쪽으로 제한했다.

각 페이지에는 판매코드, 문서 ID, Inventory ID, 모델군, 리비전, 페이지,
추출 방법, 검수 상태, 본문 SHA-256과 원본 PDF SHA-256이 포함된다.

### 5.2 사람이 확인한 보정

텍스트 추출 결과를 임의로 덮어쓰지 않고 보정 또는 전사 이유를
`manual_correction_ids`와 `extraction_method`로 기록했다.

IAC425 보정 이력은 다음과 같다.

| 페이지 | ID | 처리 |
|---:|---|---|
| 1 | `IAC425-P001-CORRECTION-01` | 표지 텍스트 추출 오류를 원본 화면과 대조해 보정 |
| 40 | `IAC425-P040-CORRECTION-01` | 추출 중복·오인식 문구를 원본 화면과 대조해 보정 |
| 52 | `IAC425-P052-VISUAL-TRANSCRIPTION-01` | 빈 텍스트 레이어의 뒷표지를 화면에서 직접 전사 |

IAC606 보정 이력은 다음과 같다.

| 페이지 | ID | 처리 |
|---:|---|---|
| 1 | `IAC606-P001-CORRECTION-01` | `Water Puri/f_ier` 형태로 깨진 표지 문구를 원본 화면과 대조해 보정 |
| 39 | `IAC606-P039-CORRECTION-01` | `작은 홀작은 홀` 중복 추출을 원본 화면과 대조해 보정 |
| 48 | `IAC606-P048-VISUAL-TRANSCRIPTION-01` | 빈 텍스트 레이어의 뒷표지를 화면에서 직접 전사 |

보정된 문자열도 페이지 본문 해시 계산에 포함된다. 앞으로 같은 페이지를
수정해야 한다면 기존 ID를 삭제하거나 조용히 덮어쓰지 말고 새로운 보정
ID와 이유를 추가해야 한다.

## 6. RAG 산출물과 모델별 범위

### 6.1 모델별 핵심 페이지

| 판매코드 | Parent 대상 페이지 | Parent | Child | Evidence Group |
|---|---|---:|---:|---:|
| `WPUJAC104DWH` | 5, 7, 37, 38, 39 | 5 | 15 | 7 |
| `WPUIAC425SNW` | 5, 43, 44, 45, 46 | 5 | 19 | 18 |
| `WPUIAC606SNW` | 5, 40, 41, 42, 43 | 5 | 19 | 18 |
| 합계 | 15쪽 | 15 | 53 | 43 |

Parent 15건은 검색 결과의 앞뒤 문맥을 확장할 때만 사용한다. Parent 자체를
벡터 검색 후보로 넣으면 한 페이지의 여러 증상이 섞여 잘못된 답변 근거가
될 수 있으므로 검색 대상에서 제외한다.

Child 53건만 실제 검색 후보인 `INGEST_CANDIDATE`다. 각 Child에는 다음
추적 정보가 있다.

- `exact_sales_code`
- `document_id`, `page_id`, `parent_id`
- 증상 또는 조치 행의 라벨
- 원문 시작·종료 anchor
- 원문 span SHA-256
- 위험도와 즉시 안전조치
- 자가 확인 후 상담이 필요한 조건
- 정확히 하나의 Evidence Group 참조

누수 안전 안내와 고장조치 페이지처럼 같은 문제를 다루는 근거는 서로
다른 정답으로 중복하지 않았다. 하나의 Evidence Group 안에서 안전 페이지와
고장조치 페이지를 Source Variant로 연결했다. 답변은 질문 상황에 맞는
Variant를 사용하되 동일 증상의 근거 계보를 유지해야 한다.

### 6.2 주요 파일

| 파일 | 용도 |
|---|---|
| `data/processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl` | 문맥 확장용 Parent 15건 |
| `data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl` | 검색 후보 Child 53건 |
| `data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl` | Evidence Group 43건 |
| `data/config/rag/three_model_evaluation_cases.json` | 평가 Case 49건 |
| `data/config/rag/supported_products.json` | 지원 판매코드와 Runtime 상태 |
| `data/processed/metadata/rag_three_model_handoff_manifest.json` | 산출물 경로·건수·해시 Manifest |

## 7. 평가 데이터와 검색 안전 규칙

평가 초안은 총 49건이다.

- 양성 Case 43건: 각 Evidence Group에 대응하는 정상 질문
- 부정 Case 6건: 근거를 반환하면 안 되는 질문

모든 양성 Case는 정답 모델 외의 두 지원 모델을 금지 모델로 지정한다.
예를 들어 IAC425 질문이라면 JAC104와 IAC606 문서 또는 Child가 검색 결과에
포함되면 실패다.

부정 Case는 다음 경계를 확인한다.

- 정확 판매코드가 검증되지 않은 JCC104(D)
- 사용 금지 모델 WPU-IAC506
- 존재하지 않는 모델
- 모델을 지정하지 않은 FAQ
- IAC425와 IAC606의 모델별 조작부 차이
- 다른 지원 모델의 유사 고장조치로 fallback하는 경우

검색 구현은 유사도 점수를 계산하기 전에 `exact_sales_code` 필터를
적용해야 한다. IAC425와 IAC606은 서로 비슷한 매뉴얼 페이지가 많기 때문에
벡터 검색 후 모델을 걸러내는 방식은 허용하지 않는다. 대상 모델에 근거가
없으면 다른 모델로 fallback하지 말고 no-evidence로 종료해야 한다.

현재 평가 상태는 `DATA_READY_AI_NOT_RUN`, 사람 검수 상태는
`HUMAN_REVIEW_PENDING`이다. 실제 AI 평가 전에는 성능 PASS로 바꾸면 안 된다.

최종 AI 합격 조건은 다음과 같다.

1. 양성 43건에서 기대 Evidence의 Source Variant가 Top-5에 모두 포함된다.
2. 부정 6건은 전부 no-evidence다.
3. 금지 모델, 금지 문서 또는 다른 판매코드의 검색 hit가 0건이다.
4. Parent가 독립 검색 결과로 반환되는 사례가 0건이다.
5. 평가 실행에 사용한 BGE-M3 모델명, 고정 revision, pgvector 환경과
   산출물 Manifest 해시가 기록된다.

## 8. 합성 제품과 Backend handoff 경계

`data/synthetic/fixtures/products.json`에는 신규 제품 2건을 추가해 물리적인
제품 레코드가 총 3건이다. 전체 합성 Fixture는 367건에서 369건이 됐다.
신규 모델의 고객제품, 구독, 문의, 상담 또는 방문 데이터는 만들지 않았다.

신규 제품의 `support_scope`는 `RAG_READY_CONTRACT_BLOCKED`다. 이는 제품
식별과 RAG 데이터 준비를 위한 레코드이며 현재 Backend DB에 적재해도 된다는
뜻이 아니다.

기존 `db-smoke`, `db-full` handoff는 다음 경계를 유지해야 한다.

- 물리적 제품 Fixture: 3건
- 현재 Backend 적재 대상 제품: `WPUJAC104DWH` 1건
- 신규 두 제품: Backend 계약 확장 전까지 DB handoff에서 제외
- 기존 `db-full` closure: 367건 유지
- 제품 파일 역할: `LOAD_FILTERED`

데이터 Manifest와 프로필에는 이 필터 경계가 반영돼 있다. 그러나 현재
Backend Importer는 프로필 필터를 적용하기 전에 전체 `products.json`의
건수를 1건으로 검사한다. 이 소비자 구현 차이 때문에 Backend 전체 테스트
중 5건이 실패한다.

## 9. 2026-08-19 검증 결과

### 9.1 Backend 가상환경 복구

Backend 가상환경은 공식 Bootstrap 절차로 Python 3.13.13 기반으로
재생성했다.

- Python: 3.13.13
- pip: 26.0.1
- 제한 패키지: 32개
- 추가 패키지: 0개
- requirements fingerprint:
  `2bc6a96f5f135cd972687d5e70a33514a88a02382220a57b82547e7ffb8cb413`
- `pip check`: PASS
- Django system check: PASS
- Migration drift check: PASS

복구 전 가상환경은
`backend/.runtime/venv-backups/20260819-085158/.venv`에 보존했다. 복구
과정에서 Backend Production 코드나 테스트 코드는 수정하지 않았다.

### 9.2 데이터 검증

| 검증 | 결과 |
|---|---|
| 데이터 단위 테스트 | 83건 통과 |
| `pipeline.py qa --verify-rebuild` | PASS, 오류 0·경고 0 |
| 검사 파일·레코드 | 55개 파일·955개 레코드 |
| 합성 Fixture | 369건 |
| 결정적 재생성 | 변경 파일 0·canonical drift 0 |
| 3모델 RAG QA | Parent 15·Child 53·Group 43·Case 49 |
| 원본 PDF Git 유입 | 0건 |
| 계약 검증기 | OpenAPI·Code·Example·State Machine·Crosswalk 모두 PASS |
| 계약 pytest | 38건 통과 |
| `git diff --check` | 종료 코드 0 |

### 9.3 Backend 전체 테스트

Backend 전체 pytest 1,325건의 결과는 다음과 같다.

- 통과: 1,267건
- 건너뜀: 34건
- 실패: 24건
- 실행 시간: 297.41초

가상환경 복구 실패나 패키지 손상 때문에 실패한 테스트는 확인되지 않았다.
실패 24건은 다음 두 소비자 경계에 집중돼 있다.

#### Backend 합성 handoff 5건 실패

`backend/apps/operations/services/operations_service.py`의
`EXPECTED_FULL_COUNTS`가 제품 건수를 1로 고정한다. Importer는
`LOAD_FILTERED`를 적용하기 전에 물리 파일 건수를 검사하므로 현재 3건인
제품 Fixture를 읽으면 `Fixture count mismatch: products 3 != 1`로
중단한다.

영향받는 테스트는 다음과 같다.

- dry-run이 쓰기 없이 전체 패키지를 검증하는 테스트
- smoke import의 멱등성과 dirty field 복구 테스트
- full import의 provenance·history 보존 테스트
- demo seed와 full handoff가 충돌하지 않는지 확인하는 테스트
- 식별자 충돌 시 전체 rollback을 확인하는 테스트

마지막 식별자 충돌 테스트도 본래 검증 지점에 도달하기 전에 동일한 제품
건수 오류로 중단된다. 신규 두 제품이 DB에 일부 적재된 상태는 아니다.

#### AI canonical evidence 19건 실패

`ai/configs/canonical_evidence_identity.json`은 `.gitattributes` 정책상 LF여야
하지만 현재 작업 파일은 CRLF다. 내용은 같아도 줄바꿈 byte가 달라져
SHA-256 검증을 통과하지 못한다.

- 현재 CRLF 파일 SHA-256:
  `16514DA3DB18C5E2B28F3CD636D366AFBFADD1322C791AB7BFAA688BE366597F`
- LF 정규화 시 SHA-256:
  `925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85`
- canonical import가 기대하는 SHA-256:
  `925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85`

LF로 정규화한 해시가 기대값과 정확히 일치하므로 AI 데이터 내용이나
chunk identity가 달라진 문제가 아니다. 줄바꿈 검증과 identity 파일 해시
검증에서 먼저 중단되기 때문에 이후의 embedding 오류, rollback, 런타임
원본 검증을 확인하는 테스트들도 기대한 검증 지점에 도달하지 못해 함께
실패한다.

### 9.4 건너뛴 검증

Backend 전체 테스트의 34건은 실패가 아니라 환경 조건에 따른 skip이다.
주요 사유는 실제 PostgreSQL의 row lock, composite FK, pgvector catalog,
동시성 검증과 실제 AI HTTP 서버가 필요한 테스트다.

독립 QA DB와 DSN이 지정되지 않았기 때문에 PostgreSQL Migration과 실제
pgvector 검증은 실행하지 않았다. AI Uvicorn 서버와 외부 LLM Provider도
이번 데이터 작업 범위에서 실행하지 않았다.

## 10. 최지용 담당자 인계

### 현재 문제

Backend Importer가 `products.json`의 물리 건수를 1로 가정한다. 데이터
프로필은 3건 중 참조된 JAC104 한 건만 적재하는 `LOAD_FILTERED`를 선언하지만
Importer가 필터 전에 전체 건수를 검사해 5개 테스트가 실패한다.

### 요청 작업

1. `backend/apps/operations/services/operations_service.py`의 제품 건수 검사와
   프로필 선택 순서를 검토한다.
2. 물리적인 제품 Fixture 3건을 유효한 입력으로 받아들인다.
3. `db-smoke`, `db-full`에서는 `LOAD_FILTERED` 정책에 따라 현재 참조되는
   `WPUJAC104DWH` 한 건만 적재한다.
4. `WPUIAC425SNW`, `WPUIAC606SNW`는 계약 확장 전까지 ProductModel이나
   고객제품 관계로 적재하지 않는다.
5. 기존 JAC104 기준 367건 closure, provenance, history와 idempotency를
   유지한다.
6. 기존에 실패한 handoff 표적 테스트 5건과 Backend 전체 pytest를 다시
   실행한다.

테스트를 통과시키기 위해 `products.json`에서 신규 두 제품을 삭제하거나
데이터 QA의 기대 건수를 다시 1건으로 낮추면 안 된다. 신규 제품 레코드는
RAG 계보와 제품 레지스트리를 위한 의도된 데이터다.

### 완료 조건

- `products.json` 3건이 입력 검증을 통과한다.
- `db-full` 실제 적재 선택 결과에는 JAC104 제품 1건만 포함된다.
- 기존 367건 closure가 유지된다.
- 신규 두 모델의 DB 행, 고객제품, 구독 또는 문의가 생성되지 않는다.
- handoff 표적 테스트 5건이 본래 검증 지점까지 실행되어 통과한다.
- PostgreSQL 검증이 필요하면 독립 QA DB를 명시하고 기존 DB를 변경하지
  않는다.

Public API가 신규 판매코드를 허용하도록 변경하는 것은 별도 계약 작업이다.
최지용 담당자는 Backend 적재 범위를 확정한 뒤 계약 담당자 윤승혁과
Runtime 활성화 시점을 맞춰야 한다.

## 11. 이동윤 담당자 인계

### 선행 차단 해소

먼저 `ai/configs/canonical_evidence_identity.json`을 내용 변경 없이 LF로
정규화한다. 기존 chunk ID, document ID, hash 또는 BGE-M3 설정을 줄바꿈
문제를 해결한다는 이유로 다시 생성하면 안 된다.

LF 정규화 후 다음을 확인한다.

- 파일에 `\r` byte가 0개인지 확인
- 파일 SHA-256이
  `925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85`인지 확인
- canonical evidence 표적 테스트 44건 재실행
- 줄바꿈 문제 뒤에 숨겨져 있던 별도 실패가 있는지 확인

### 3모델 RAG 적재

1. `rag-expansion` 프로필과 Manifest를 읽고 `INGEST_CANDIDATE` 역할의
   Child 53건만 검색 인덱스에 적재한다.
2. Parent 15건은 `CONTEXT_ONLY`로 보관하고 검색 후보로 임베딩하거나 독립
   hit로 반환하지 않는다.
3. Evidence Group 43건과 Source Variant 관계를 보존한다.
4. 쿼리 시 `exact_sales_code` 필터를 유사도 계산 전에 적용한다.
5. 다른 지원 모델로 fallback하지 않는다.
6. 고정 BGE-M3 revision, embedding dimension, PostgreSQL·pgvector version,
   데이터 Manifest hash를 평가 결과에 기록한다.

기존 JAC104 `rag` 프로필은 그대로 유지한다. `rag-expansion`은 기존 인덱스가
이미 3모델로 갱신됐다는 표시가 아니라 신규 인덱싱 후보를 전달하는
프로필이다.

### 평가 실행

`data/config/rag/three_model_evaluation_cases.json`의 49건을 실행한다.

- 양성 43건: 기대 Evidence Source Variant가 Top-5에 포함되는지 확인
- 부정 6건: 전부 no-evidence인지 확인
- 모든 Case: 다른 판매코드·문서 hit가 0건인지 확인
- 모델별 조작부 질문: IAC425와 IAC606의 답변이 서로 섞이지 않는지 확인

실제 실행 전에는 `DATA_READY_AI_NOT_RUN`을 유지한다. 평가가 완료돼도
Backend/API 계약이 확장되기 전에는 신규 모델을 Runtime 활성 상태로
표시하지 않는다.

### 완료 조건

- AI canonical evidence 테스트가 줄바꿈 검증을 포함해 통과한다.
- Child 53건과 Parent 15건의 역할이 분리된다.
- 양성 43건이 Top-5 합격 조건을 충족한다.
- 부정 6건이 모두 no-evidence다.
- 금지 모델·문서 hit가 0건이다.
- 평가 환경과 실행 결과가 재현 가능한 보고서로 남는다.

## 13. 재현 명령

저장소 루트에서 Python 3.13.13 Backend 가상환경을 사용하는 기준 명령은
다음과 같다.

```powershell
# 3모델 산출물 재생성·검증
.\backend\.venv\Scripts\python.exe -B -m data.tools.rag_experiments.build_three_model_handoff
.\backend\.venv\Scripts\python.exe -B -m data.tools.rag_experiments.qa_three_model_handoff

# AI 인계 Manifest 확인
.\backend\.venv\Scripts\python.exe -B data/tools/pipeline.py handoff rag-expansion

# 데이터 전체 회귀와 결정적 재생성 확인
.\backend\.venv\Scripts\python.exe -B -m unittest discover -s data/tools/tests -v
.\backend\.venv\Scripts\python.exe -B data/tools/pipeline.py qa --verify-rebuild

# Backend handoff 표적 재현
.\backend\.venv\Scripts\python.exe -m pytest `
  backend/tests/integration/operations/test_synthetic_handoff_import.py `
  -q -p no:cacheprovider

# AI canonical evidence 표적 재현
.\backend\.venv\Scripts\python.exe -m pytest `
  backend/tests/unit/evidence/test_ai_canonical_evidence_import.py `
  -q -p no:cacheprovider
```

실제 PostgreSQL 검증은 독립 QA DB, DSN, PostgreSQL·pgvector version과
대상 Schema가 명확할 때만 실행한다. 기존 DB에 Migration이나 Seed를
적용해 검증하면 안 된다.

## 14. 인계 체크리스트

### 데이터 담당 완료

- [x] 공식 매뉴얼 3건의 크기·페이지 수·SHA-256 확인
- [x] 전체 144쪽 페이지 JSONL 생성
- [x] 보정·전사 ID 기록
- [x] Parent 15건과 Child 53건 생성
- [x] Evidence Group 43건 생성
- [x] 평가 Case 49건 생성
- [x] 지원 제품 레지스트리 작성
- [x] 합성 제품 3건과 전체 Fixture 369건 검증
- [x] 원본 PDF Git 유입 0건 확인
- [x] 데이터 단위 테스트와 결정성 QA 통과

### Backend 담당 대기

- [ ] 물리 제품 3건과 `LOAD_FILTERED` 처리 순서 정합화
- [ ] JAC104 한 건만 DB 적재되는지 검증
- [ ] 기존 367건 closure 유지 확인
- [ ] handoff 실패 테스트 5건 재실행
- [ ] 신규 모델 Runtime 지원 범위 확정

### AI 담당 대기

- [ ] canonical identity 파일 LF 정규화
- [ ] canonical evidence 테스트 44건 재실행
- [ ] Child 53건 pgvector 적재
- [ ] Parent 15건 검색 후보 제외 확인
- [ ] 평가 Case 49건 실행
- [ ] 금지 모델·문서 hit 0건 확인
- [ ] 실행 환경과 성능 결과 기록

## 15. 최종 주의사항

- 신규 두 모델은 데이터 준비 상태이지 서비스 활성 상태가 아니다.
- 실제 AI 적재 전에는 `INDEXED`, 평가 전에는 성능 `PASS`로 표시하지 않는다.
- Backend 계약 확장 전에는 신규 제품을 DB handoff에 포함하지 않는다.
- 모델을 확인할 수 없는 FAQ를 정답 근거로 사용하지 않는다.
- WPU-IAC506과 정확 판매코드가 없는 JCC104(D)를 검색 대상으로 만들지
  않는다.
- IAC425와 IAC606은 반드시 검색 점수 계산 전에 판매코드로 격리한다.
- 공식 PDF, 고객 원문, 비밀값과 실제 개인정보를 저장소나 평가 로그에
  남기지 않는다.

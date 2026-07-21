# 팀원 D - 데이터 구조 확인 가이드

## 목적

공식 자료, 팀 설계 상태, 합성 시연 데이터를 구분하고 모델·문서·청크·문의 사이의 참조 관계를 설계한다.

## 필수 확인 파일

1. `data/processed/metadata/model_scope.csv`
2. `data/processed/metadata/source_inventory.csv`
3. `data/processed/structured/rag_verified_sample.jsonl`
4. `data/processed/structured/selected_faq_candidates.jsonl`
5. `data/synthetic/demo_scenarios.json`
6. `data/processed/metadata/error_missing_list.csv`
7. `data/processed/metadata/model_document_lineage.csv`
8. `data/processed/structured/jac104_evidence_registry.jsonl`

## 권장 엔터티와 키

| 엔터티 | 기본 키 | 주요 참조 |
|---|---|---|
| ProductModel | `exact_model` | `manual_document_id`, `scope_role` |
| Document | `document_id` | `exact_sales_code`, `product_model`, `source_landing_url`, `source_direct_download_url`, `version` |
| DocumentChunk | `chunk_id` | `document_id`, `page_refs`, `topic_code` |
| FAQCandidate | `faq_id` | `target_models`, `applicability` |
| InquiryScenario | `scenario_id` | `product_model`, `chunk_id` |

## 분류 필드

- `official`: 공식 문서에서 확인한 사실·조치·상담 조건
- `team_designed`: 상태·우선순위·방문 후보·담당 주체
- `synthetic`: 시연용 문의·가상 식별자

세 분류를 동일한 공식 사실로 합치지 않는다.

## 모델 상태

- `mvp_primary`: 현재 구현 대상
- `expansion_secondary`: 후속 확장, 기본 검색과 분리
- `removed_legacy`: 저장소에서 삭제된 이전 모델, 신규 구현 참조 금지

`WPU-IAC506`은 `removed_legacy`로 취급하며 운영 테이블과 검색 인덱스에 레코드를 만들지 않는다.

## 결측·제한 처리

- 미확인 오류 코드는 의미를 추정하지 않고 원문과 상담 필요 상태를 저장한다.
- FAQ 개별 URL이 없으면 목록 URL·FAQ 번호·제목을 함께 저장한다.
- 게시자가 명시한 모델 코드와 프로젝트가 후보로 연결한 모델 코드를 각각 `publisher_model_codes`, `project_candidate_models`로 분리한다.
- 페이지가 없는 웹 FAQ는 `official_page_number=null`과 `source_locator`를 함께 저장한다.
- `image_only_unverified`의 빈 `answer_text`는 오류가 아니라 사용 보류 상태다.
- 관리 일정·방문 확정은 공식 정책이 아니므로 `team_designed`로 저장한다.

## 완료 기준

- 모델 변경 후 IAC506 참조가 현재 운영 테이블에 없음
- 공식·설계·합성 구분 필드가 필수값으로 정의됨
- `risk_level`과 현재 사용 가능 여부를 독립 필드로 관리함
- 출처 URL·문서·페이지까지 역추적 가능함

# 팀원 B - RAG 데이터 확인 가이드

## 목적

WPU-JAC104D 기본 MVP의 검색·답변 근거를 구성하고, 모델이 다른 FAQ나 검증 전 자료가 검색 결과에 섞이지 않도록 한다.

## 필수 확인 파일

1. `data/processed/structured/rag_verified_sample.jsonl`
2. `data/processed/structured/selected_faq_candidates.jsonl`
3. `data/processed/metadata/preprocessing_spec.md`
4. `data/processed/metadata/source_coverage_matrix.csv`
5. `data/processed/metadata/source_inventory.csv`

## 적재 범위

### 기본 MVP 인덱스

- `scope_role == "mvp_primary"`
- `product_model == "WPU-JAC104D"`
- `verification_status == "text_and_visual_verified"`
- `applicability == "model_exact"`

검증 청크 7건이 조회돼야 한다.

### FAQ 보조 인덱스

- `model_family_direct`: 사용 가능, D 세대 매뉴얼 우선
- `category_common_safety`: 매뉴얼과 일치하는 안전 분기에만 사용

다음 값은 적재하거나 답변 근거로 노출하지 않는다.

- `category_common_unverified`
- `image_only_unverified`
- `other_model_only`
- `other_product_family`

### 후속 확장

`scope_role == "expansion_secondary"`인 WPU-IAC425 청크 4건은 기본 MVP 인덱스와 분리한다. PM이 확장 시작을 승인하기 전 검색 대상에 포함하지 않는다.

## 필수 메타데이터

- `chunk_id`, `document_id`, `product_model`, `version`
- `page_refs`, `topic_code`, `risk_level`
- `requires_consultation`, `applicability`
- `safe_actions`, `escalation_conditions`, `prohibited_actions`
- `source_url`, `verification_status`

## 안전 확인

- 누수 청크는 원수 밸브 잠금·전원 분리·상담 연결을 유지한다.
- 순간온수 모듈 점검 청크는 출수된 물 음용 금지를 유지한다.
- 물맛·냄새 답변에서 수질 안전을 임의로 확정하지 않는다.

## 완료 기준

- JAC104 7개 청크만 기본 인덱스에 적재됨
- 제외 applicability 검색 결과 0건
- 모든 답변에 모델·문서·버전·페이지 출처 표시 가능
- 위험 청크의 금지·상담 조건이 답변 생성 단계까지 보존됨


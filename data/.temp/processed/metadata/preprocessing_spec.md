# WPU-JAC104D 기본 MVP 데이터 전처리 기준

## 1. 적용 범위

- 기본 MVP: `WPU-JAC104D`
- 후속 확장: `WPU-IAC425`
- 제외 모델: `WPU-IAC506` 및 FAQ에 명시된 다른 모델

상품 코드와 매뉴얼 계열 코드를 별도로 저장한다.

- `exact_model`: `WPUJAC104DWH`
- `product_model`: `WPU-JAC104D`
- `document_id`: `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00`

## 2. 출처 우선순위

1. 모델 정확 일치 공식 매뉴얼 (`model_exact`)
2. 모델 계열 직접 언급 FAQ (`model_family_direct`)
3. 매뉴얼과 내용이 일치하는 공통 안전 FAQ (`category_common_safety`)
4. 공통 미검증 FAQ는 검색 후보로만 보존

다음 적용 상태는 RAG 적재에서 제외한다.

- `category_common_unverified`
- `image_only_unverified`
- `other_model_only`
- `other_product_family`

## 3. 청크 필수 필드

- `chunk_id`, `document_id`, `product_model`, `scope_role`
- `version`, `page_start`, `page_end`, `page_refs`
- `topic_code`, `symptom_category`, `risk_level`
- `applicability`, `evidence_summary`
- `safe_actions`, `escalation_conditions`, `prohibited_actions`
- `source_path`, `source_url`, `verification_status`

## 4. 답변 안전 규칙

- 누수는 원수 밸브 잠금·전원 분리·고객상담센터 연결을 우선한다.
- 순간온수 모듈 점검 문구가 표시되면 출수된 물을 음용하지 않도록 한다.
- 물맛·냄새 문의에서 수질 안전을 임의로 확정하지 않는다.
- 제품 분해·배관 수리·냉각부·히터 직접 수리를 안내하지 않는다.
- `requires_consultation=true`이면 자가조치만으로 문의 종료 처리하지 않는다.

## 5. 검증 상태

- `text_and_visual_verified`: 텍스트와 렌더링 페이지 대조 완료, RAG 사용 가능
- `text_extracted_visual_review_pending`: 텍스트만 추출, 청킹 전 시각 검수 필요
- `image_only_unverified`: 이미지 OCR 및 공식 근거 대조 전 사용 금지

## 6. 공식·설계·합성 분리

- 공식 문서에서 확인한 조치만 `official`로 저장한다.
- 상담 상태·방문 후보·담당 주체는 `team_designed`로 저장한다.
- 고객 문의와 처리 예시는 `synthetic`으로 표시하며 실제 개인정보를 포함하지 않는다.


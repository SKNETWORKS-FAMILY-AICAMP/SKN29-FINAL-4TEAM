# WaterCare ERD v3.0.0 교차검증 및 생성 보고서

## 결론

`모바일프레임워크_양정현.md`의 CUST-01~06과 `화면설계서 v1.docx`의
고객·상담사·방문기사 흐름 사이에 ERD 생성을 중단할 충돌은 없었다.
화면설계서의 CUST-02 임시 저장·제출 요구와 최신 테이블 명세서의
`support_questionnaire_session`이 일치하므로 서버 문진 세션을 ERD에 반영했다.

Room은 단말 임시 저장·입력 복구용 로컬 DB로 분리한다. 서버 ERD에는
Room 구현 테이블을 추가하지 않았다. 화면설계서는 채널을 고정하지 않으므로
기존 웹 프로토타입 호환을 위해 `channel_code`의 WEB 기본값은 유지하되,
Android 앱 API가 MOBILE을 명시해야 한다는 연동 주석을 추가했다.

## 원본 검증

- 모바일 문서 SHA-256: `5582E0E73134B1CD208A514CAA44C446A67F78D2057CF9F7CA598C78FAC09E6E (이전 교차검증값, 생성 시점 원본 경로 없음)`
- 화면설계서 SHA-256: `B016633DB40D5C257F05CC15002421E3D249A01C2C28AAC16985BEE0E8362A7A`
- 화면설계서 구조 검증: Word 기준 14쪽, 문단 103개, 표 21개,
  패키지 내 이미지 5개를 확인했다. PDF 내보내기는 Word에서 지연되어 중단했으나,
  DOCX XML·표 전체와 포함된 흐름도·아키텍처·통합 와이어프레임은 직접 점검했다.
- 테이블 명세: `01`~`32` 전체 재수집

## 최신 스키마 집계

| 항목 | v2.1.0 | v3.0.0 |
|---|---:|---:|
| 테이블 | 31 | 32 |
| 컬럼 | 475 | 526 |
| 물리 FK | 69 | 85 |
| 논리 공통코드 참조 | 50 | 57 |

## 기존 ERD 대비 변경 테이블

| 테이블 | 컬럼 수 | 추가 컬럼 | 제거 컬럼 |
|---|---:|---|---|
| `customers_customer_profile` | 14 → 15 | deleted_by_id | - |
| `subscriptions_customer_subscription` | 13 → 14 | management_type_code | - |
| `subscriptions_care_record` | 13 → 14 | visit_result_id | - |
| `support_inquiry` | 17 → 28 | current_owner_id, current_owner_role_code, usage_guidance_message, restricted_functions, next_action, requires_consultation, customer_action_required, completion_route_code, required_finalizer_role_code, required_finalizer_user_id, deleted_by_id | - |
| `support_inquiry_qa` | 14 → 14 | - | - |
| `support_guidance` | 14 → 14 | - | - |
| `support_customer_action_result` | 11 → 10 | - | inquiry_id |
| `support_consultation` | 17 → 20 | cancellation_reason, deleted_at, deleted_by_id | - |
| `field_service_visit` | 18 → 20 | deleted_at, deleted_by_id | - |
| `field_service_visit_result` | 16 → 17 | next_care_on | - |
| `support_followup_confirmation` | 16 → 19 | guidance_id, consultation_id, visit_id | - |
| `support_inquiry_status_history` | 15 → 16 | questionnaire_session_id | - |
| `knowledge_source_document` | 25 → 26 | deleted_by_id | - |
| `knowledge_data_quality_issue` | 17 → 18 | chunk_id | - |
| `aiops_ai_run` | 26 → 29 | model_config_version, model_config, input_sha256 | - |
| `aiops_retrieval_run` | 20 → 23 | embedding_model_version, error_code, error_message | - |
| `knowledge_evidence_link` | 24 → 29 | retrieval_hit_id, retrieval_run_id, selection_origin_code, section_snapshot, product_model_codes_snapshot | - |
| `support_questionnaire_session` | 0 → 15 | id, session_no, subscription_id, inquiry_id, questionnaire_type_code, status_code, questionnaire_version, answers_payload, state_version, started_at, submitted_at, linked_at, creation_idempotency_key, created_at, updated_at | - |

## 생성 파일 무결성

| 파일 | 바이트 | SHA-256 |
|---|---:|---|
| `WaterCare_ERD_상세_v3.html` | 276,994 | `16255EC8105B3301B341D9ADE2654557D0C8D1367A4551A117DDC2D0F291F1A6` |
| `WaterCare_ERD_계층형_v3.html` | 328,153 | `2C7AFF8AD2BB4D13190403514E18FB6142332227CA11AB7BDD596634D235DDFD` |
| `WaterCare_ERD_계층형_v3.svg` | 122,665 | `1043E993832227BB59FCDE0B2BCE63C1AEBEACF903A7D16269A62F4B18C241EE` |
| `WaterCare_ERD_계층형_v3.png` | 323,387 | `CBCD9411ACE892E7D6F3FEC641A0053D7606D2DBE05BB948B429F2C88EC08936` |
| `WaterCare_ERD_전체_v3.svg` | 122,665 | `1043E993832227BB59FCDE0B2BCE63C1AEBEACF903A7D16269A62F4B18C241EE` |
| `WaterCare_ERD_전체_v3.png` | 323,387 | `CBCD9411ACE892E7D6F3FEC641A0053D7606D2DBE05BB948B429F2C88EC08936` |
| `WaterCare_ERD_v3.mmd` | 21,947 | `7D2DF9651BA90582547AF4AFED9AFD69DDCD4E519CA263ACF0446ADC1929BF9E` |
| `WaterCare_schema_sqlite_v3.sql` | 25,896 | `4841CF3F5EF03107C01E2C325A01BF6DDB548EC834F4FF8713D81E2163D5905E` |
| `WaterCare_ERD_v3.sqlite3` | 389,120 | `2D33537D7E7FA08EE8C33B1BBD8891699D33BF72ED957392980D0ED513619C69` |
| `WaterCare_ERD_v3_스키마.json` | 208,812 | `D53C3E46770C1A7DF43B10943DE3F53A5629978F34FE8DA2533AAA8612C54724` |
| `WaterCare_ERD_계층형_v3_설명.md` | 1,671 | `F391F0E18A5D13D59973B821BA8C2F39E1F18E0D96AE5F9903960C4B159D4F5D` |

## 검증 기준

- 두 HTML의 내장 TABLES 데이터 완전 일치
- 테이블 32개, 컬럼 526개, 물리 FK 85개
- 모든 물리 FK 대상 테이블·컬럼 존재
- HTML 외부 리소스 자동 로드·네트워크 호출 없음
- 중복 DOM id 및 인라인 이벤트 속성 없음
- SQLite `PRAGMA integrity_check=ok`
- 원본 v2.1.0 산출물 보존

# WaterCare 데이터 P0 Test Case 매트릭스

| Case | 요구사항 | 기준 데이터·계약 | 자동 검증 | 증빙 |
|---|---|---|---|---|
| DATA-CONTRACT-001 | State Machine v1.0.0 source 고정 | service contract mapping | `test_contract_sources_and_vocabularies_are_current` | QA error category |
| DATA-T005-001 | 대상 FK 정확히 하나 | 상태이력 Schema·fixture | `test_status_history_has_exactly_one_matching_target` | Integrity report |
| DATA-T005-002 | 대상별 version 유일·연속 | 상태이력·Audit | version·audit 대응 테스트 | Integrity report |
| DATA-IDEM-001 | 동일 키·동일 payload replay 0건 | API idempotency cases | replay/conflict 테스트 | Business report |
| DATA-IDEM-002 | Inquiry·Visit 동일 요청 키 공유 | 복합 방문 이벤트 | compound history 테스트 | Business report |
| DATA-ID-001 | PK·Public UUID·업무 코드 분리 | 전체 synthetic fixture | identifier/FK 테스트 | Quality report |
| DATA-PROJ-001 | 원본 24·활성 22·차단 2 | alignment registry | projection·registry 테스트 | Business report |
| DATA-RAG-001 | 승인 청크 7개 양성 Case | RAG evaluation contract | RAG evaluation contract 테스트 | AI 결과 pending |
| DATA-RAG-002 | 범위 밖·미검증 자료 차단 | 부정 Case 5개 | negative scope 테스트 | AI 결과 pending |
| DATA-DB-001 | Fixture PK 직접 주입 금지 | Backend crosswalk | crosswalk 테스트 | DB 증빙 pending |
| DATA-DB-002 | 반복 적재 중복 0건 | Backend 실행 결과 | 담당자 DB 검증 | DB 증빙 pending |
| DATA-REPRO-001 | byte 결정성·manifest 정합 | 전체 생성 산출물 | pipeline safety·QA | Reproducibility report |

자동 테스트의 개별 함수 수보다 요구사항 연결을 우선한다. 관할 밖
Runtime Case는 빈 테스트로 완료 처리하지 않고 담당자 증빙을 연결한다.

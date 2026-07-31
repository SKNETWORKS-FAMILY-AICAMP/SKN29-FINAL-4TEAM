# 데이터 계약 정합화 진행 기록

## 작업 정보

- 담당 역할: 김은진 — 데이터·QA·DevOps
- 작업 시작일: 2026-07-28 (Asia/Seoul)
- 수정 범위: `data/**`, `data/tools/tests/**`, 공동 문서 `docs/**`
- 우선 기준: 현재 저장소의 `contracts/codes/**`, `contracts/state-machine/**`
- 참고 자료: WaterCare ERD v0.5, 2026-07-27 API 명세 v0.5

## 범위 제한

이번 작업은 합의 없이 정합화할 수 있는 역할·상태·이벤트·데이터 projection과
QA를 대상으로 한다.

다음 업무 정책은 데이터 담당자가 결정하지 않는다.

- `DEC-RESOLVED-REOPEN-001`: `RESOLVED` 문의를 같은 ID로 재개할지,
  관련 새 문의를 만들지
- `DEC-PRODUCT-VALIDATION-001`: `PRODUCT_VALIDATION_FAILED`에서 고객 직접
  수정·재검증을 지원할지

두 항목은 기존 시나리오를 삭제하지 않고 결정 대기 상태로 분리한다.
`contracts/**`, `backend/**`, Web·Mobile·AI 구현과 외부 참고 문서는 수정하지 않는다.

## 진행 기록

### 2026-07-28 — 기준선 확인

- 작업 전 `git status --short`: 기존 사용자 변경 `.gitignore` 1건
- 데이터 관련 기존 diff: 없음
- 데이터 도구 테스트
  - 명령: `python -m unittest discover -s data/tools/tests -v`
  - 결과: 26개 통과
- 데이터 QA
  - 명령: `python data/tools/pipeline.py qa --verify-rebuild`
  - 결과: PASS
  - 검증: 42파일, 697레코드
  - 대표 E2E: 17/17 통과
  - 재생성 변경 및 canonical drift: 0건

### 2026-07-28 — 계약 매핑 설정 완료

- `data/config/workflow/service_contract_mapping.json`을 추가했다.
- 현행 역할·문의 상태·방문 상태와 기존 데이터 별칭을 분리했다.
- 두 미결 정책을 차단 결정으로 명시했다.
- 계약 원본 경로와 SHA-256을 기록해 QA에서 기준 문서 변경을 감지하도록
  연결했다.
- 자동 검증
  - 명령: `python -m unittest data.tools.tests.test_service_contract_mapping data.tools.tests.test_data_vocabulary.DataVocabularyTests.test_all_declarative_configs_match_static_schemas -v`
  - 결과: 4개 통과
  - 검증 범위: 계약 원본 해시, vocabulary 동기화, canonical 역할,
    차단 결정 유지, 설정 스키마

### 2026-07-28 — 역할 정규화 완료

- 활성 합성 데이터와 스키마의 역할 값을 `COUNSELOR`에서 `CONSULTANT`로
  정규화했다.
- 상담 FK 필드명을 `counselor_id`에서 `consultant_id`로 정규화했다.
- 레거시 용어는 계약 매핑 파일의 명시적 별칭과 해당 테스트에만 남겼다.
- 단계 검증
  - 명령: `python -m unittest data.tools.tests.test_service_contract_mapping data.tools.tests.test_data_vocabulary.DataVocabularyTests.test_all_declarative_configs_match_static_schemas -v`
  - 결과: 5개 통과
- 전체 테스트 중간 실행: 29개 중 24개 통과, 5개 실패
  - 예상된 다음 단계 실패: 기존 Inquiry 상태 4종이 새 vocabulary에 남아 있음
  - 예상된 최종 단계 실패: 생성 파일 변경 후 manifest 해시 미갱신
  - 역할 또는 스키마 정규화 자체의 실패는 없음

### 2026-07-28 — Inquiry·Visit 상태 분리 완료

- 구 상태를 현행 canonical 상태로 정규화했다.
  - `AI_GUIDANCE_READY` → `AI_GUIDANCE`
  - `CONSULTATION_PENDING` → `CONSULTATION_REQUIRED`
  - Inquiry의 `VISIT_PENDING`·`VISIT_IN_PROGRESS` → `VISIT_SCHEDULED`
- 방문 처리 흐름을 계약 순서로 복구했다.
  - `VISIT_REVIEW_REQUIRED`
  - `VISIT_NEEDED` — Visit `ASSIGNING` 생성
  - `UPDATE_VISIT_SCHEDULE` — Visit `SCHEDULING`
  - `CONFIRM_VISIT` — Inquiry `VISIT_SCHEDULED`, Visit `CONFIRMED`
  - `START_VISIT` — Inquiry 유지, Visit `IN_PROGRESS`
  - `VISIT_COMPLETED` — Inquiry `COMPLETION_PENDING`, Visit `COMPLETED`
- `VISIT_REVIEW_PENDING`인 SYN-JAC104-008의 선행 생성 Visit 1건을 제거했다.
- 대표 E2E는 12단계에서 14단계로 갱신했으며 Inquiry와 Visit 상태를 함께
  검증한다.
- 단계 검증: 계약 매핑·상태 분리·설정 스키마 8개 통과
- 전체 테스트 중간 실행: 30개 중 26개 통과
  - 실패 4개는 모두 최종 manifest count·hash 미갱신에서 파생됨

### 2026-07-28 — 결정 대기 시나리오 격리 완료

- `synthetic/expected/contract_alignment_registry.json` 생성 경로를 추가했다.
- 24개 중 22개는 `ALIGNED`, SYN-JAC104-012·016은
  `BLOCKED_DECISION`으로 표시했다.
- 차단된 2개 시나리오는 원본을 보존하지만 계약 DB projection에서는 제외한다.
- `PRODUCT_VALIDATION_FAILED`는 활성 Inquiry 상태로 생성하지 않는다.
- 차단 결정과 registry 정합성 검증 7개 통과

### 2026-07-28 — ERD projection 일시 중단

새 구조 충돌을 발견해 승인 전 projection 생성을 중단했다.

- 현행 전이 계약의 TR-INQ-019, TR-INQ-022, TR-INQ-026은 하나의 업무
  요청에서 Inquiry 상태 이력과 Visit 상태 이력을 각각 기록하도록 요구한다.
- 외부 ERD v0.5의 통합 `support_inquiry_status_history`는
  `idempotency_key`를 UNIQUE로 설명한다.
- 동일 요청 키를 두 이력 행에 그대로 저장하면 UNIQUE 제약과 충돌한다.
- 현행 `backend/**`에는 해당 상태 이력 Model·Migration 구현이 없어 실제 DB
  제약으로 해소된 증거도 없다.

승인 권고안은 글로벌 UNIQUE 대신
`(target_type_code, target_id, idempotency_key)` 범위의 복합 유일성으로
정의하는 것이다. 같은 업무 요청 키를 Inquiry·Visit 양쪽 이력에 보존하면서
대상 Aggregate 내부 중복만 차단할 수 있다.

계약·ERD·Backend 제약에 영향을 주므로 데이터 담당자가 임의 확정하지 않는다.

## 단계별 상태

| 단계 | 상태 | 결과 |
|---|---|---|
| 기준선 확인 | 완료 | 테스트·QA PASS, 기존 데이터 diff 없음 |
| 계약 매핑·blocker 설정 | 완료 | 계약 해시·vocabulary·차단 결정 자동 검증 |
| 역할 정규화 | 완료 | 활성 데이터·스키마에 레거시 역할/필드 없음 |
| Inquiry·Visit 상태 분리 | 완료 | canonical 흐름·독립 Visit 상태·대표 E2E 반영 |
| 결정 대기 시나리오 격리 | 완료 | 22건 포함, 2건 차단 registry 생성 |
| ERD projection 최소 골격 | 중단 | 상태 이력 idempotency 유일성 승인 필요 |
| 최종 QA·diff 검토 | 대기 | |

## 중단 조건

- 새 업무 규칙을 확정해야 하는 항목을 발견하면 수정하지 않고 이 문서에
  blocker와 영향 범위를 기록한 뒤 사용자에게 보고한다.
- 기존 미결 항목이 필수 생성 경로를 차단하면 정상 데이터로 임의 변환하지 않는다.
## 2026-07-29 — ADR 승인 후 T-005 데이터 projection 재개·완료

2026-07-28의 중단 사유는 ADR 0010·0011과 T-005 Physical Contract v1.2가 기준으로 추가되면서 데이터 영역에서 해소됐다. 다만 Backend Model·Migration·Service가 완료됐다는 의미는 아니다.

- `idempotency_key`는 상태이력 UNIQUE가 아니라 요청과 이력을 연결하는 추적값으로 반영했다.
- 한 요청이 Inquiry와 Visit을 함께 바꾸면 두 Aggregate의 이력을 별도 생성하고 같은 `idempotency_key`, `correlation_id`를 공유한다.
- 중복 차단은 대상별 연속 `state_version`으로 검증한다.
- 범용 `target_id` 없이 `questionnaire_session_id`, `inquiry_id`, `consultation_id`, `visit_id` 중 하나만 설정한다.
- Fixture 식별자는 정수 local PK, Public UUID, `DEMO-*`·`SYN-*` 업무 코드의 3계층으로 분리했다.
- 원본 24개는 보존하고 012·016을 제외한 22개만 활성 projection으로 생성한다.
- CustomerProfile fixture와 Backend import crosswalk를 추가했으며 fixture PK 직접 주입을 금지했다.
- Care의 미확정 코드는 `BLOCKED_OWNER_CONFIRMATION`으로 유지하고 직접 load 후보에서 제외했다.
- API 멱등성 expected data는 내부 Guard 코드와 Public API 409 코드를 분리했다.

이 projection 종료 시점의 데이터 기준은 Inquiry 22건, Consultation 12건,
Visit 4건, 통합 상태이력 125건, Audit 125건, subset 33건이다. 상세 QA
리포트와 manifest는 파이프라인이 실데이터에서 재생성한다.

당시 상태는 데이터 QA `PASS`까지만 기록했다.
`service_contracts_used=false`, Service mapping pending, 비-`DB_VERIFIED`
상태를 유지했고 Backend import 실증은 Backend 담당자의 후속 범위였다.

## 2026-07-29 — State Machine v1.0.0 승인 후속 정합화

- 계약 담당자의 `2c93fd1` 커밋에서 State Machine `1.0.0`이
  `TEAM_APPROVED`로 채택된 사실을 확인했다.
- 네 핵심 계약 SHA와 신규 `data-state-crosswalk.yaml`, 대표 E2E 계약을
  데이터 매핑 source로 고정했다.
- 이 정합화 시점의 `service_contracts_used=false`는 Backend Runtime 연동
  미검증을 뜻하는 호환 필드로 유지하고, 데이터 projection의 승인 계약
  소비 상태를 별도 metadata로 기록했다.
- DB handoff의 dependency 명칭도 `BACKEND_RUNTIME_MAPPING_PENDING`으로
  바꿔 승인된 State Machine 계약과 미검증 Runtime mapping을 구분했다.
- `SYN-JAC104-012`, `016`은 terminal 동일 ID 재개 금지와 충돌하므로
  새 관련 문의 방식의 시나리오 재설계 승인 전까지 `BLOCKED_DECISION`과
  활성 projection 제외를 유지한다.
- Backend DB 적재는 사용자 확인상 성공했지만 commit·Migration·건수·
  재적재 로그를 받기 전까지 `DOCUMENTED_NOT_DB_VERIFIED`를 유지했다.
- RAG는 승인 청크 7건의 양성 Case와 범위 밖 자료 부정 Case 5건을
  데이터 평가 계약으로 제공하며 실제 Index 결과는 AI 담당자 대기다.
- 이 정합화 시점의 로컬 검증은 단위 테스트 55/55, 계약 검증 PASS,
  QA 48개 파일·740개 레코드, 오류·경고·재생성 drift 0건이다.
- 최종 Manifest 154개 항목을 검사했고 `.temp`·`.work` 잔존물은 없다.

## 2026-07-29 — Backend Import 후속 통합 완료

앞선 `service_contracts_used=false`, `DOCUMENTED_NOT_DB_VERIFIED`
기록은 데이터 projection 단계 종료 당시의 범위를 보존한 역사
기록이다. 이후 정식 Importer·원장·Model/Migration을 구현하고 격리
PostgreSQL에서 smoke 37건과 full 367건을
`dry-run → 최초 적재 → 동일 입력 재실행` 순으로 검증했다.

- 현재 Consumer Handoff는 `service_contracts_used=true`다.
- `db-smoke`는 `DB_SMOKE_VERIFIED`, `db-full`은
  `DB_FULL_VERIFIED`다.
- Care 25건은 확정된 유형·결과 코드 계약으로 full load한다.
- `SYN-JAC104-012`·`SYN-JAC104-016`은 여전히 활성 projection과
  DB 적재에서 제외한다.
- 이 완료 표식은 합성 Handoff 12종에만 적용하며 T-005 계약
  32테이블 전체 완료를 뜻하지 않는다.

현행 기계 근거는
[Backend Import Crosswalk](../../data/config/handoff/backend_import_crosswalk.json),
실행·안전·재현 절차는
[합성 데이터 Schema·Importer·PostgreSQL 검증 가이드](../individual/jiyong/technical/backend/합성_데이터_스키마_적재기_postgresql_검증_가이드.md)를
따른다.

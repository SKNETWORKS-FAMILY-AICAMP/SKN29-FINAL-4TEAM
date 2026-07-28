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

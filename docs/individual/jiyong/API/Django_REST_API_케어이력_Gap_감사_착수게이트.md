# T-019 케어 이력 Runtime 구현·검증 가이드

## 1. 최신 판정

- 작성일: 2026-08-12 KST
- 기준: origin/main@8b5bb6292e087fd15558f53c530b06653edc4d29
- 상태: AUTHOR_SQLITE_VERIFIED / POSTGRESQL_QA_PENDING
- 소비자 연결: HOLD
- 공식 WBS: 독립 QA·PM 판정 전 진행 중 유지

기존 Gap 문서를 PM 결정 이후의 구현 문서로 최신화했다. 고객 본인 ACTIVE
지원 구독의 완료 케어 이력 목록·상세·승인 셀프 케어 등록을 구현했고,
다음 케어일 계산은 T-020으로 분리했다.

## 2. 계약과 Runtime

| Method | Path | 동작 |
|---|---|---|
| GET | /api/v1/me/subscriptions/{subscription_id}/care-records | COMPLETED 목록·페이지 |
| POST | 같은 Path | 승인 셀프 케어 등록·Replay |
| GET | .../care-records/{care_record_id} | COMPLETED 상세 |

공개 V1 등록 유형은 기존 CARE_TYPE 중 고객이 직접 수행 가능한
FILTER_REPLACEMENT, CLEANING으로 제한한다. 카트리지·살균을 새 코드나
다른 코드에 임의 매핑하지 않았다.

## 3. 권한·객체·날짜 경계

- 미인증 401, CUSTOMER가 아닌 역할 403
- 본인 ACTIVE WPUJAC104DWH 지원 구독만 허용
- 타인·비활성·미지원·미존재 구독과 비공개 이력은 동일 404
- 공개 이력은 COMPLETED만, 최신 관리일 순
- 날짜는 Date-only이며 미래·구독 시작일 전 등록은 422
- 알 수 없는 Body·Query와 미지원 유형은 422
- 내부 ID, 계약번호, Serial, 주소, 자유 Summary·PII는 비노출

## 4. 저장·멱등성

- Scope: actor + createMyCareRecord + Idempotency-Key
- 같은 Key·같은 요청은 최초 저장 결과 Replay
- 같은 Key·다른 날짜·유형·대상은 409 DUPLICATE-EVENT-01
- Customer Profile과 Subscription Row Lock 뒤 이력을 1건 저장
- 결과·수행자·출처는 서버가 정규화
  - FILTER_REPLACEMENT → FILTER_REPLACED
  - CLEANING → NORMAL
- 신규 Model·Migration 없이 기존 CareRecord·IdempotencyRecord 사용

## 5. 안전 Projection

- 고객 목록·상세는 최소 안전 DTO만 반환
- 담당 상담사는 배정된 Inquiry를 통해서만 같은 안전 Projection 조회
- AI 내부 Context는 최근 COMPLETED 최대 5건만 사용
- AI 필드: care_type_code, performed_on, result_code
- 자유 Summary와 고객정보는 AI Projection에 포함하지 않음
- Operator 공개 Endpoint는 열지 않았으며 역할 전체 허용도 하지 않음

## 6. 구현·계약 증거

- [Route](../../../../backend/apps/care/api/urls.py)
- [View](../../../../backend/apps/care/api/views.py)
- [Serializer](../../../../backend/apps/care/api/serializers.py)
- [Service](../../../../backend/apps/care/services/care_history_service.py)
- [Repository](../../../../backend/apps/care/repositories/care_history_repository.py)
- [OpenAPI Path](../../../../contracts/api/paths/care.yaml)
- [공개 Item](../../../../contracts/api/components/schemas/care/CareHistoryItem.yaml)
- [등록 Schema](../../../../contracts/api/components/schemas/care/CareHistoryCreateRequest.yaml)
- [Runtime Test](../../../../backend/tests/api/test_t019_care_history_runtime.py)
- [Contract Test](../../../../backend/tests/api/test_t019_care_history_contract.py)

## 7. 작성자 검증

| 검증 | 결과 |
|---|---:|
| T-019 Runtime·Contract | 16 passed / 0 failed |
| T-005~T-020 통합 표적 | 177 passed / 0 failed |
| OpenAPI | 124 YAML / 513 refs / 36 paths / 40 operations |
| Example | 61/61 referenced |
| Code Registry | 28 files / 144 codes |
| Django Check | 0 issue |
| Migration drift | No changes detected |
| 전체 Backend 회귀 | 1076 passed / 19 skipped / 0 failed |

재현 위치는 backend다.

    .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/api/test_t019_care_history_runtime.py tests/api/test_t019_care_history_contract.py tests/api/test_openapi_runtime_coverage.py
    .\.venv\Scripts\python.exe -B ..\scripts\contracts\validate_openapi.py
    .\.venv\Scripts\python.exe -B ..\scripts\contracts\validate_examples.py
    .\.venv\Scripts\python.exe -B ..\scripts\contracts\validate_codes.py

## 8. 남은 Gate

- 셀프 케어 2종 allowlist를 계약 Owner가 최종 후보에서 확인한다.
- 격리 PostgreSQL에서 동시 Create Replay·Conflict를 재현한다.
- 김은진 독립 QA 뒤 PM이 소비자 연결과 WBS 상태를 판정한다.
- 다음 예정일은 T-020, 방문 결과 중복 반영은 T-044에서 처리한다.
- 현재 결과를 Web·Mobile·T-019 전체 완료로 확대하지 않는다.

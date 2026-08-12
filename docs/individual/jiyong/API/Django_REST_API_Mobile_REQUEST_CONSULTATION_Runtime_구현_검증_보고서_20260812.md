# Mobile REQUEST_CONSULTATION Runtime 구현·검증 보고서

> 작성일: 2026-08-12 KST
> 작성자: 최지용(Backend·DB·Public API)
> 작업 브랜치: `jiyong`
> 작업 기준선: `main@8b5bb6292e087fd15558f53c530b06653edc4d29`
> 현재 상태: `IMPLEMENTED / POSTGRESQL_SOCKET_PASS / PM_MAIN_MERGE_PENDING`

## 1. 결론

PM이 P0로 승인하고 화면설계서가 사용하는 고객 상담 요청 Operation을
실제 Backend Runtime으로 구현했다.

```text
POST /api/v1/inquiries/{inquiry_id}/request-consultation
operationId=requestConsultation
actor=CUSTOMER
scope=OWN_INQUIRY
```

- 신규 Model·Migration: 없음
- 기존 State·Event·Guard 코드 변경: 없음
- Request Body: `state_version`만 허용
- 필수 Header: `Idempotency-Key`, `X-Correlation-ID`
- 공개 응답 `resource`: `null`
- 타 고객과 미존재 Inquiry: 동일 `404`

## 2. 구현한 세 전이

| Rule | 이전 상태 | 이후 상태 | 상담 레코드 처리 |
| --- | --- | --- | --- |
| `TR-INQ-012` | `AI_GUIDANCE` | `CONSULTATION_REQUIRED` | 미배정 `WAITING` 생성 |
| `TR-INQ-013` | `CONSULTATION_REQUIRED` | 동일 | 기존 WAITING·ASSIGNED 재사용 |
| `TR-INQ-031` | `COMPLETION_PENDING` | `CONSULTATION_REQUIRED` | 완료 이력 보존 후 새 순번 생성 |

첫 요청과 재요청 모두 Inquiry `state_version`을 1 증가시키고
`REQUEST_CONSULTATION` TransitionHistory를 기록한다. 고객의 요청 단계에서는
상담사 내부 레코드와 배정 정보를 공개하지 않는다.

## 3. 멱등·동시성 정책

- 같은 Actor·Operation·Key와 같은 요청은 저장된 `200`을 Replay한다.
- 같은 Key를 다른 `state_version`에 재사용하면 `409 DUPLICATE-EVENT-01`이다.
- 다른 Key지만 오래된 `state_version`이면 `409 STATE-CONFLICT-01`과 최신
  `current_status`, `current_state_version`, `allowed_actions`를 반환한다.
- 새 Key·최신 Version으로 `CONSULTATION_REQUIRED`에서 재확인하면 새 상담
  행을 만들지 않고 기존 대기 레코드와 업무 이벤트만 갱신한다.

## 4. 권한·오류 경계

| 조건 | 결과 |
| --- | --- |
| 미인증 | `401` |
| CUSTOMER가 아닌 역할 | `403` |
| 타 고객·미존재 Inquiry | `404 RESOURCE_NOT_FOUND` |
| 상태·Version 충돌 | `409` |
| 미지원 필드·Header 누락 | `422 VALIDATION_ERROR` |
| 계약·저장 무결성 오류 | `500`, 공개 세부정보 비노출 |

현재 State에서 실행 가능 여부는 `allowed_actions`와 서버 State Machine이
단일 원천이다. 클라이언트가 상태를 임의 계산하지 않는다.

## 5. Runtime 파일

- `backend/apps/inquiries/api/urls.py`
- `backend/apps/inquiries/api/views.py`
- `backend/apps/inquiries/api/serializers/request_consultation.py`
- `backend/apps/inquiries/services/consultation_request_service.py`
- `backend/apps/consultations/repositories/consultation_repository.py`
- `contracts/api/paths/workflow.yaml`
- `contracts/api/action-operation-crosswalk.yaml`

## 6. 공식 합성 Fixture

```powershell
python manage.py seed_demo_accounts
python manage.py seed_demo_products
python manage.py seed_demo_subscriptions
python manage.py seed_demo_request_consultation --json
```

| 항목 | 값 |
| --- | --- |
| Fixture | `mobile-request-consultation-v1` |
| Demo Login | `DEMO-CUSTOMER-001` |
| 공개 Inquiry UUID | `d0a62012-3b89-5d39-8cd4-4c1d8c366201` |
| 초기 상태 | `AI_GUIDANCE` |
| 초기 Version | `3` |

Fixture는 소비 전에는 멱등 재실행된다. Runtime으로 소비된 뒤에는 상태와
이력을 강제 초기화하지 않고 명시적으로 실패하므로, 재실행 검증은 새 격리
DB에서 수행한다.

## 7. 검증 결과

### 자동 검증

| 묶음 | 결과 |
| --- | --- |
| 신규 Runtime·Seed·계약 1차 | `22 passed` |
| Inquiry·Workflow·CONS-04·상담·방문 회귀 | `139 passed, 3 skipped` |
| Backend 전체 회귀 | `1031 passed, 19 skipped` |
| Data QA·결정적 재빌드 | `740 records, 0 errors, 0 warnings, changed_files=[]` |
| Django Check | PASS |
| Migration drift | `No changes detected` |

3개 Skip은 기존 PostgreSQL Row Lock 전용 테스트이며 이번 Runtime 실패가
아니다.

### PostgreSQL 실제 Socket

로컬 공식 DB `waterbridge.public`에서 실제 WSGI Socket을 열고 다음을
확인했다.

| 검사 | 결과 |
| --- | --- |
| Demo CUSTOMER 로그인 | `200` |
| 상담 요청 | `200`, `CONSULTATION_REQUIRED`, Version `4` |
| 동일 Key Replay | `200`, `idempotent_replay=true` |
| 같은 Key·다른 Body | `409 DUPLICATE-EVENT-01` |
| 오래된 Version | `409 STATE-CONFLICT-01` |
| Customer Snapshot 재조회 | `200`, 최신 State·Version 일치 |
| CONSULTANT 호출 | `403` |
| WAITING 상담 1건 | PASS |
| TransitionHistory·Idempotency 각각 1건 | PASS |
| Header·Body·JSON Log Correlation | PASS |

실제 검증 Correlation ID는
`b3a3d32d-8249-41db-a5be-11eb555906f8`이며, 과거 증거이므로 Mobile 공동
Smoke에서는 새 ID를 사용한다.

## 8. 계약 현행화

- OpenAPI `x-runtime-status`: `IMPLEMENTED`
- Action Crosswalk: `RUNTIME_IMPLEMENTED`
- 집계: `13 / 6 / 0 / 4`
- `AllowedActionResolver`: 세 승인 상태에서 `REQUEST_CONSULTATION`을 노출

계약 버전과 State Machine 버전, Request·Response Shape는 변경하지 않았다.
OpenAPI에 누락돼 있던 `TR-INQ-031 / COMPLETION_PENDING` 메타데이터만 이미
승인된 화면·State Machine 기준에 맞춰 보완했다.

## 9. 남은 Gate

1. 이 로컬 변경을 의도한 파일만 Commit·Push한다.
2. PM이 `jiyong → main` 병합 여부를 결정한다.
3. 양정현이 최신 main을 Pull하고 Mobile Remote Adapter를 연결한다.
4. 동일 Fixture로 실제 단말 200·Replay·409·404·Correlation을 확인한다.

Commit·Push·PM 병합 전에는 Mobile에 `Backend Runtime 게시 완료`로 전달하면
안 된다.

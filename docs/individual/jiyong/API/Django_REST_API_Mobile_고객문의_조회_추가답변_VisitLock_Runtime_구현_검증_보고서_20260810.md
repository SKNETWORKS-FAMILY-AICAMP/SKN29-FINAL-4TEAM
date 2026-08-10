# Django REST API Mobile 고객 문의 조회·추가답변·Visit Lock Runtime 구현·검증 보고서

> 작성일: 2026-08-10 KST
> 담당: 최지용 — Backend·DB
> 게시 브랜치: `jiyong`
> 작업 시작 기준선: `origin/jiyong f445c173702f988a14ca53598fb247eac65c1b8b`
> 통합 기준선: `origin/jiyong 7cff0178d42342f2ffc9002f1f323fb3d60d8e8d`
> 구현 Commit: `1897afda916985a10e1257ba38bdf659839d020a`, `ede0e2cc57165113e5ab45eb609133bd0327bdef`, `31a0325bbf4bac76a638994de98090d7df8bc689`
> 상태: `AUTHOR_VERIFIED / SHARED_ON_JIYONG / MAIN_NOT_MERGED / MOBILE_REMOTE_PENDING`

## 1. 한 문장 결론

Mobile 고객이 본인 문의 상태와 미답변 질문을 조회하고 추가답변을 제출할 수 있는 Backend Runtime을 구현했으며, 답변 저장 뒤 AI 재평가 요청과 PostgreSQL 행 잠금까지 검증했다.

4개 Commit으로 분리해 기존 `jiyong` 이력 위에 공유했으며, `main` 병합과 공유 DB Migration, 독립 QA, Mobile 실제 Remote 연결은 남아 있다.

## 2. 이번에 구현한 API

| 대상 | Method·Path | Actor | 결과 |
| --- | --- | --- | --- |
| 고객 문의 Snapshot | `GET /api/v1/me/inquiries/{inquiry_id}` | 본인 CUSTOMER | 상태·Version·구독 UUID·모델코드 |
| 고객 미답변 질문 | `GET /api/v1/me/inquiries/{inquiry_id}/questions` | 본인 CUSTOMER | 지원 질문·선택지 |
| 고객 추가답변 | `POST /api/v1/inquiries/{inquiry_id}/answers` | 본인 CUSTOMER | 답변 저장·Version 증가·AI 재평가 요청 |

공통 경계는 다음과 같다.

- 타 고객 문의와 없는 문의는 같은 `404 RESOURCE_NOT_FOUND`다.
- CONSULTANT·TECHNICIAN·ADMIN은 CUSTOMER 전용 API를 사용할 수 없다.
- GET은 상태·담당자·질문·답변을 변경하지 않는다.
- 고객 원문, 내부 문의 코드, 계약번호, Serial, 주소, 이름, 전화번호, 위험도, 담당자, Evidence 내부 ID는 노출하지 않는다.

## 3. 고객 문의 Snapshot

예시:

```json
{
  "inquiry_id": "uuid",
  "status_code": "QUESTIONNAIRE_IN_PROGRESS",
  "state_version": 2,
  "subscription_id": "uuid",
  "product": {
    "model_code": "WPUJAC104DWH"
  },
  "updated_at": "2026-08-10T08:00:00Z"
}
```

용도는 앱 재시작, `409` 복구, 추가답변 이후 최신 상태 확인이다.

상담사용 상세 API와 다르게 고객 본인에게 필요한 최소 필드만 반환한다.

## 4. 고객 미답변 질문

예시:

```json
{
  "inquiry_id": "uuid",
  "state_version": 2,
  "questions": [
    {
      "question_id": "uuid",
      "question_type": "SINGLE_CHOICE",
      "prompt": "필터를 최근 교체하셨나요?",
      "required": true,
      "options": [
        {"value": "YES", "label": "YES"}
      ]
    }
  ]
}
```

질문 공개 규칙:

- 아직 고객 답변 원장이 없는 질문만 반환한다.
- `sequence_no`, 공개 UUID 순으로 정렬한다.
- `FREE_TEXT`와 선택지가 있는 `SINGLE_CHOICE`만 공개한다.
- 아직 계약하지 않은 `MULTI_CHOICE`, `BOOLEAN`, `NUMBER`와 선택지 없는 `SINGLE_CHOICE`는 답변 불가능한 필수 질문으로 노출하지 않는다.
- 선택지는 공백 제거·최대 200자·최대 10개로 GET과 POST가 같은 정규화 규칙을 사용한다.
- `required=true`는 개별 질문이 답변 대상이라는 뜻이다. 한 POST에서 열린 질문 전부를 보내야 한다는 뜻은 아니다.
- 부분 제출 후 남은 질문은 다음 GET에서 다시 반환된다.
- `question_code`, `target_field`, AI Run, 답변 값·시각·작성자는 공개하지 않는다.

## 5. 추가답변 제출

필수 Header:

```http
Authorization: Bearer <customer_access_token>
Idempotency-Key: <1~128자 고유 키>
X-Correlation-ID: <공백 없는 UUID>
```

요청 예시:

```json
{
  "state_version": 2,
  "answers": [
    {
      "question_id": "uuid",
      "answer_text": "이틀 전부터 발생했습니다."
    },
    {
      "question_id": "uuid",
      "answer_payload": {
        "selected_option": "YES"
      }
    }
  ]
}
```

검증 규칙:

- `answers`는 1~50개다.
- 같은 `question_id`를 한 요청에 중복할 수 없다.
- `answer_text`와 `answer_payload` 중 정확히 하나만 허용한다.
- 텍스트는 공백만 입력할 수 없고 최대 1,000자다.
- 구조화 답변은 `selected_option` 한 필드만 허용한다.
- 선택값은 GET에서 공개한 정규화 선택지와 일치해야 한다.
- 미존재·타 문의·이미 답변한 질문은 저장하지 않는다.
- `X-Correlation-ID` 누락·오류·앞뒤 공백은 `422`다.

성공 시:

- Inquiry 상태는 `QUESTIONNAIRE_IN_PROGRESS`를 유지한다.
- `state_version`은 1 증가한다.
- 각 답변에는 수락 당시 `accepted_state_version`을 기록한다.
- 답변·Inquiry Version·Business Event·Idempotency 결과를 한 Transaction으로 저장한다.
- 같은 Key·같은 요청은 재저장 없이 `idempotent_replay=true`로 응답한다.
- 같은 Key·다른 요청은 `409 DUPLICATE-EVENT-01`이다.
- 오래된 Version은 `409 STATE-CONFLICT-01`이며 최신 상태 복구 후 재시도한다.
- 응답 직렬화가 실패하면 모든 저장과 AI 콜백 등록을 Rollback한다.

## 6. 답변 이후 AI 재평가

State Machine `TR-INQ-003`의 `REQUEST_AI_REEVALUATION` 효과를 반영했다.

- 답변 Transaction Commit 전에는 AI를 호출하지 않는다.
- Commit 뒤 `transaction.on_commit(..., robust=True)`로 `InquiryAIService.analyze_inquiry()`를 호출한다.
- AI 요청 ID는 해당 `IdempotencyRecord.public_id`로 고정한다.
- 같은 멱등 Key Replay는 AI를 다시 예약하지 않는다.
- AI 모델·Prompt·판정 정책은 수정하지 않았다.

현재 제한:

- Durable Outbox·Worker가 아니므로 Commit 직후 프로세스 종료 시 콜백이 유실될 수 있다.
- AI 호출은 요청 Process에서 실행되어 설정된 Timeout만큼 응답이 늦어질 수 있다.
- AI가 즉시 다음 상태로 전환하면 POST 응답 Version보다 DB Version이 앞설 수 있으므로 Mobile은 성공 후 Snapshot을 재조회해야 한다.
- 운영 재시도 내구성이 필요해지면 별도 Outbox·Worker 계약이 필요하다.

## 7. DB·Migration

Migration:

`backend/apps/inquiries/migrations/0011_split_followup_question_metadata_and_answers.py`

핵심 원칙:

- T-005 불변 계약 테이블 `support_inquiry_qa`의 기존 컬럼·제약·Index를 제거하지 않는다.
- 질문 Metadata는 기존 `answer_payload`의 `question_options`, `target_field` 키를 계속 사용한다.
- 고객 답변은 새 지원 원장 `support_followup_answer`에 저장한다.
- 원장은 Question One-to-One, 작성자, 답변 시각, 수락 State Version을 기록한다.
- 텍스트와 구조화 답변은 XOR DB Constraint로 보호한다.
- 0011 이전 원형 `answer_text`, 범용 JSON Payload, 공백 포함 값도 기존 컬럼에 그대로 보존한다.
- 이전 답변은 새 원장으로 복사하되 과거 수락 Version을 알 수 없어 `accepted_state_version=null`이다.
- 0011 이후 신규 답변은 양의 `accepted_state_version`을 기록한다.
- Reverse Migration은 기존 Legacy 값을 덮어쓰지 않고, 0011 이후 생성된 답변만 빈 Legacy 경계에 복원한다.
- PostgreSQL의 Pending Trigger Event를 피하기 위해 DDL 경계를 분리하고 Data Copy만 원자적으로 실행한다.

`support_followup_answer`는 불변 32개 계약에 더하지 않는 다섯 번째 승인 Runtime 지원 테이블이다.

보존정책은 연결 Inquiry·Question과 동일하며 FK `PROTECT`를 사용한다. Runtime Hard Delete는 금지하고 승인된 Data Lifecycle로만 삭제한다.

## 8. Visit PostgreSQL 행 잠금 수정

원인:

- Visit의 배정 기사는 nullable 관계다.
- `select_related("technician")`가 PostgreSQL OUTER JOIN을 만든다.
- 기존 `select_for_update()`가 nullable JOIN까지 잠그려 해 500을 만들 수 있었다.

수정:

- `VisitRepository.lock_latest()`
- `VisitRepository.lock_by_public_id()`
- 두 메서드 모두 `select_for_update(of=("self",))`로 Visit 행만 잠근다.

결과:

- 기사 정보 조회는 유지한다.
- 변경 대상 Visit 행의 잠금은 유지한다.
- nullable 기사 JOIN에는 잠금을 요청하지 않는다.
- 추가답변의 미답변 질문 잠금도 `InquiryQA` 자체 행만 대상으로 한다.
- Visit 기능 수정은 통합 기준선에 이미 포함되어 있어 중복 커밋하지 않고 회귀 테스트만 보강했다.

## 9. 기존 소비자 호환

- AI 질문 생성은 Metadata를 기존 InquiryQA JSON에 저장한다.
- AI Request Mapper는 새 `customer_answer` 관계에서 이전 답변을 읽는다.
- 상담사 문의 상세도 새 답변 원장에서 Text 또는 선택값만 읽는다.
- AI 내부 `target_field`와 선택지 Metadata는 상담사·고객 응답에 누출하지 않는다.
- Mobile·Web 소스, AI Schema·Prompt, Model 판정 정책은 수정하지 않았다.

## 10. 계약 상태

- OpenAPI: `32 paths / 33 operations`
- Action Crosswalk: `RUNTIME_IMPLEMENTED=12`, `OPENAPI_CONFIRMED=7`, `CONTRACT_ONLY=0`, `DEFERRED=4`
- `SUBMIT_ANSWERS`: `CONFIRMED + IMPLEMENTED`
- 고객 Snapshot·질문 GET: `CONFIRMED + IMPLEMENTED`
- State Machine: `1.0.0`, 전이 의미 변경 없음
- 나머지 후반 7개 Action Runtime은 구현하지 않았다.

## 11. 작업·검증 반복 결과

| 단계 | 실제 결과 | 판정 |
| --- | --- | --- |
| 최종 표적 Runtime / 관련 계약 | `60 passed` / `30 passed` | PASS |
| 최신 PostgreSQL 표적 반복 1 | `19 passed` (`25.30s`) | PASS |
| 최신 PostgreSQL 표적 반복 2 | `19 passed` (`23.89s`) | PASS |
| Root 계약 | `12 passed` | PASS |
| Backend 전체 | `933 passed, 15 skipped` | PASS |
| Django Check | `System check identified no issues` | PASS |
| Migration Drift | `No changes detected` | PASS |
| `git diff --check` | 출력 없음 | PASS |

PostgreSQL은 원본 `.env` 값을 출력하지 않고 Process에서만 읽은 뒤, 매 실행마다 별도 임시 DB 이름으로 덮어썼다. `--create-db`를 사용했고 공유·운영 DB에는 Migration·Seed를 적용하지 않았다.

## 12. 완료하지 않은 범위

- `main` 병합
- 팀 공유 PostgreSQL Migration
- 비작성자 독립 QA
- Mobile Retrofit·DTO·Mapper·화면·실기기 Remote
- Durable AI Outbox·Worker
- `모름/답변 거절` 공개 계약값
- 고객 Guidance·Evidence GET
- `REQUEST_CONSULTATION`
- 기사 Visit 목록·상세·시작·완료
- 해결 피드백·최종 완료·미해결 재개
- 전체 고객→AI→상담→방문 E2E

## 13. Mobile 담당자에게 전달할 내용

`jiyong`의 위 구현 Commit을 받은 뒤 다음 순서로 연동한다.

1. Snapshot GET으로 현재 상태와 Version을 복구한다.
2. Questions GET에서 반환된 지원 질문만 화면에 표시한다.
3. Text 또는 `selected_option` 중 하나로 답변을 제출한다.
4. `409`이면 Snapshot을 다시 읽고 사용자의 답변을 보존한 채 재시도 안내한다.
5. `422`는 Header·Payload·선택지 오류를 구분해 입력을 수정한다.
6. 성공 후 Snapshot을 다시 조회해 AI 재평가 이후 최신 상태를 받는다.

현재 판정은 `jiyong 공유 및 Backend 작성자 검증 완료`다. `main 병합 완료`, `Mobile 연동 완료`, `독립 QA 완료`로 확대 해석하지 않는다.

## 14. 다음 Backend 작업

1. 팀원이 `jiyong`의 4개 Commit과 본 보고서를 검토한 뒤 `main` 병합 여부를 판단한다.
2. 승인된 절차로 공유 DB 0011 Migration Dry-run·Backup·적용·Rollback 증거를 남긴다.
3. Mobile 세 Endpoint의 Remote Smoke를 지원한다.
4. AI 재평가의 Durable Outbox 필요성을 결정한다.
5. 고객 Guidance·Evidence GET 계약과 Runtime을 확정한다.
6. `REQUEST_CONSULTATION` Runtime을 구현한다.
7. 기사 Visit 목록·상세 계약을 확정한 뒤 Runtime을 구현한다.
8. Visit 시작·완료와 후반 Action을 WBS 순서로 진행한다.

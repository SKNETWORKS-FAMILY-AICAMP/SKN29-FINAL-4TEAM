# Backend 단독 회귀·HITL·T-051 작성자 검증 결과

## 1. 결론

- 최신 보완 기준선: `jiyong=origin/main@7d5b5b71609c2aff951528bd9a08b1e524097d96`
- 독립 QA 재현 기준: `main@3dce9b83473a345ad5086de9d0b8ff0c6209a841`
- T-021 Commit: `6bd8bf1311faf2fd4cf0a2271cd4bb012b6478ae`
- HITL Commit: `e88cb8b7e57aa488681fd0028ec4557838047cde`
- 이번 결과: 기존 3건 보완에 더해 T-023 PostgreSQL nullable Outer Join
  Row Lock 결함을 최신 main에서도 재현하고 수정했다.
- 범위: Repository Lock Query, T-023 회귀 Test, 본 개발문서만 변경했다.
- Git 상태: `jiyong`에만 반영하며 main 병합·AWS 배포는 하지 않는다.

이번 결과는 독립 QA나 WBS 완료 판정이 아니다. AWS OTP·배포, 실제 AI Resume,
Web·Mobile 소비 연결, RDS·공용 DB 변경은 범위에서 제외했다.

## 2. 보완한 결함

### 2.1 T-021 CARE_PRECHECK 요청 계약 엄격화

OpenAPI 요청은 `additionalProperties: false`였지만 DRF Serializer가 알 수 없는
필드를 조용히 무시하고 있었다. START·SAVE·SUBMIT 요청에 공통 검증을 적용해
계약에 없는 필드는 `422 VALIDATION_ERROR`로 거부하도록 보완했다.

검증한 경계:

- 잘못된 START 요청은 Session과 멱등 레코드를 만들지 않는다.
- 잘못된 SAVE·SUBMIT 요청은 상태·버전·답변을 바꾸지 않는다.
- 거부된 요청의 멱등 레코드도 남지 않는다.

### 2.2 HumanReview MODIFY 고객 공개문 정합화

상담사가 AI 초안을 MODIFY하면 새 승인 Guidance가 생성되지만, 고객 Guidance
조회는 과거 AI Payload의 문구와 조치를 다시 읽고 있었다. 이 경우 상담사가
거절·수정한 초안이 고객에게 노출될 수 있다.

공개 문구와 행동은 승인된 최신 Guidance와 GuidanceItem을 읽도록 변경했다.
위험도·사용 제한·제한 기능 검증은 감사 가능한 기존 AI Payload에서 유지했다.

검증한 경계:

- MODIFY 승인 문구와 행동만 고객 GET에 반환된다.
- 수정 전 AI 문구와 행동은 고객 응답에 포함되지 않는다.
- HumanReview 원장과 기존 AI Payload는 감사 목적으로 보존된다.

### 2.3 HumanReview MODIFY 공개 길이 계약 정합화

상담사 수정 입력은 안내문 4,000자·행동 2,000자까지 허용했지만 고객 Guidance
계약은 각각 3,000자·1,000자였다. 기존에는 수정 결정이 200으로 저장된 뒤 고객
조회만 409가 될 수 있었다.

MODIFY 입력을 고객 공개 계약과 같은 3,000자·1,000자로 제한했다. 초과 요청은
서비스와 DB 쓰기 전에 `422 VALIDATION_ERROR`로 거부되며 HumanReview 상태·버전,
Guidance, 멱등 레코드가 바뀌지 않음을 검증했다.

### 2.4 T-023 PostgreSQL Row Lock 범위 교정

`select_for_update()`가 nullable `assigned_user`·`consultant`·`technician` 관계를
`select_related()`로 Outer Join한 전체 Query를 잠그려 해 PostgreSQL이 아래 오류를
반환했다.

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

SQLite는 실제 Row Lock을 수행하지 않아 이 결함을 발견하지 못한다. Inquiry,
Consultation, Visit에서 실제로 상태·버전이 변경되는 본체 Row만 잠그도록 네 Query에
`select_for_update(of=("self",))`를 적용했다. 관련 사용자 정보는 기존처럼 함께
조회하지만 User·Profile Row를 불필요하게 잠그지 않는다.

Completed 처리 Row는 DB lifecycle Constraint상 담당자가 필수다. nullable 경계는
정상 상태인 미배정 WAITING Consultation과 ASSIGNING Visit을 추가한 회귀로 고정했고,
최신 완료 처리 선택 순서 `-completed_at`, `-id`도 유지했다.

## 3. 수정 파일

아래 앞 7개는 이 문서가 기존에 기록한 T-021·HITL Commit 범위다. 이번 T-023
Commit의 실제 변경 대상은 마지막 Repository·Test와 본 문서뿐이다.

| 파일 | 변경 내용 |
|---|---|
| `backend/apps/questionnaires/api/serializers.py` | 알 수 없는 요청 필드 거부 |
| `backend/tests/api/test_t021_care_precheck_runtime.py` | START·SAVE·SUBMIT 무변경 회귀 |
| `backend/apps/inquiries/repositories/customer_inquiry_repository.py` | 승인 GuidanceItem 정렬 조회 |
| `backend/apps/inquiries/services/customer_inquiry_service.py` | 승인된 공개문을 SSOT로 사용 |
| `backend/tests/api/test_customer_inquiry_read_runtime.py` | MODIFY 후 고객 재조회 E2E |
| `backend/apps/inquiries/api/serializers/human_review.py` | MODIFY 공개 길이를 고객 계약과 일치 |
| `backend/tests/api/test_human_review_runtime.py` | 초과 길이 422·무기록 경계 검증 |
| `backend/apps/inquiries/repositories/resolution_repository.py` | 네 Row Lock을 본체 Row로 제한 |
| `backend/tests/api/test_t023_resolution_runtime.py` | nullable 관계·동시 Replay·409·Rollback 회귀 |

## 4. 검증 결과

| 검증 | 결과 |
|---|---|
| T-023 SQLite | `14 passed / 2 PostgreSQL-only skipped` |
| T-023 격리 PostgreSQL | `16 passed / 0 failed / 0 skipped` |
| T-019~T-023·HITL 확대 PostgreSQL | `263 passed / 0 failed / 0 skipped` |
| T-021·HumanReview 핵심 PostgreSQL | `65 passed / 0 failed / 0 skipped` |
| 전체 Backend SQLite | `1610 passed / 43 expected skipped / 0 failed` |
| Web G4 `tmp_path` 환경 분리 재검증 | `6 passed` |
| Django System Check | `0 issues` |
| Migration drift | `No changes detected` |
| `git diff --check` | PASS |

격리 PostgreSQL은 `PostgreSQL 16 / pgvector 0.8.6` 일회용 컨테이너로만
사용했고 기존 P1·OTP 컨테이너는 건드리지 않았다. 검증 후 격리 컨테이너는
종료·자동 제거했다.

PostgreSQL 표적 검증은 `--nomigrations`로 현재 Model Schema를 생성했다. 따라서
Row Lock·Replay·409·Rollback의 작성자 Runtime 증거이며, 공식 Migration Allowlist
적용 증거로 확대 해석하지 않는다. 기존 DB·Volume은 변경하지 않았고
`visits.0005`도 적용하지 않았다.

동시 Finalize 검증은 다음을 확인했다.

- 같은 Key·같은 Payload: `200` 2건, 실제 쓰기 1건, Replay 1건
- 서로 다른 Key·같은 버전: `200` 1건, `409 STATE-CONFLICT-01` 1건
- 두 경우 모두 Finalize History와 IdempotencyRecord는 1건만 생성
- 강제 응답 직렬화 실패 전후 Domain·History·Idempotency 총 Row 수 변화 0건

## 5. 전체 Backend 회귀 해석

공식 실행 위치인 `backend`에서 전체 테스트를 실행했다. 최초 샌드박스 실행은
`test_web_g4_db_evidence.py`의 `tmp_path` 생성 전에 Windows ACL이 pytest 임시폴더
접근을 막아 5개 Setup Error와 Session cleanup Error가 발생했다. 제품 Assertion에는
진입하지 못한 환경 오류였다.

같은 파일을 권한이 정상인 격리 임시경로에서 실행해 `6 passed`를 확인했다. 이어
전체 Suite를 같은 조건으로 한 번에 재실행해 `1610 passed / 43 skipped`, Exit 0을
확인했다. Skip은 PostgreSQL Row Lock·Constraint와 실제 Socket 등 환경 전용이다.

저장소 루트에서 pytest를 실행하면 일회성 보정 스크립트까지 수집돼 강제 종료된다.
Backend 전체 회귀는 반드시 `backend/pyproject.toml`이 적용되는 `backend` 폴더에서
실행해야 한다.

## 6. 현재 완료 범위

- T-019: JAC104 최소 케어 이력 LIST·DETAIL·CREATE 기반 유지
- T-020: 승인 Rule 기반 내부 일정 계산·Row Lock 기반 유지
- T-021: 수동 Session START·SAVE·SUBMIT·문의 1회 연결 및 요청 계약 엄격화
- T-022·T-023: 상담 기반 해결 피드백·재개·최종 완료 흐름 유지
- HITL: HumanReview 원장·결정 API와 승인 공개문 정합화
- T-051: Replay·409·Correlation의 기존 작성자 증거 확인

## 7. 완료로 판정하지 않은 범위

- 방문 시작·완료 API와 `visits.0005`: P1 HOLD
- 방문 완료 후 미해결 문의의 상담사 재배정·재개 정책
- T-020 `CONFIRMATION_REQUIRED` 공개 DTO와 기존 구독 재산정
- T-021 자동 생성 Scheduler와 공식 질문 Catalog
- AI 프로세스 재시작 후 HumanReview Resume 복구
- HumanReview 승인 공개 시점: 현재 Runtime은 승인 즉시 공개하며, 이를 유지할지
  AI Resume 완료 후 공개할지는 PM 계약 확정 필요
- 상담사 수정 문구·행동과 기존 AI 위험도·상담 필요 여부의 의미 정합성 규칙
- AI 원본 Guidance가 고객 공개 길이를 넘을 때의 상류 계약과 승인 차단 기준
- 승인 Guidance 이력이 크게 증가할 때 Item Prefetch 성능 Baseline
- HumanReview 실제 PostgreSQL 동시 결정·동시 MODIFY 독립 증거
- T-051 공식 p95·실패율 Baseline과 독립 QA
- AWS OTP·배포·실제 메일 수신 Smoke

## 8. 다음 단계

1. PM이 잔여 상태·Actor·공개 계약을 결정한다.
2. 현재 T-023 수정 Commit을 main에 병합한다.
3. 병합된 단일 SHA에서 김은진이 독립 PostgreSQL QA를 재수행한다.
4. 독립 QA는 실제 Migration Allowlist, `visits.0005` HOLD, T-023 16건,
   확대 263건, T-021·HumanReview 65건과 무기록 경계를 확인한다.
5. AI Resume는 이동윤, Web·Mobile 소비는 각 Frontend 담당자가 연결한다.
6. T-051은 측정 조건과 완료 기준 확정 후 별도 Slice로 수행한다.

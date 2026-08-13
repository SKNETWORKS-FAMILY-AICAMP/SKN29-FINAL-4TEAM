# Web CONS-04 상담사 전화 문의 등록 Runtime 구현·검증 보고서

> 작성일: 2026-08-11
> 현행화: 2026-08-12
> 작성자: 최지용(Backend·DB·Public API)
> 상태: `BACKEND_MAIN_MERGED / WEB_MAIN_MERGED / BACKEND_POSTGRESQL_SOCKET_PASS / SHARED_BROWSER_SMOKE_PENDING`
> 작업 시작 기준선: `origin/jiyong@e146d2349d82c964ca57baa4c77b501f8e84c1ab`
> 최신 공유 기준선: `main@8b5bb6292e087fd15558f53c530b06653edc4d29`

## 1. 결론

기존 CUSTOMER 문의 생성 API는 변경하지 않고, CONSULTANT가 합성 고객의
활성 구독을 검색한 뒤 전화 문의를 등록하는 전용 API 2개를 구현했다.

- Backend 계약·Runtime·Migration 작성자 검증: PASS
- PostgreSQL 격리 검증: PASS, 동일 묶음 2회
- Backend 전체 회귀: PASS
- Web Remote Adapter·화면: `main` 병합 및 작성자 회귀 PASS
- Backend PostgreSQL 실제 Socket: PASS
- Web↔Backend 공동 Browser Smoke: 아직 미수행
- 신규 테이블: 없음
- 기존 테이블 변경: `support_inquiry.priority_code` 1개 컬럼 추가

Backend와 Web 구현은 현재 `main`에 함께 존재한다. 남은 완료 Gate는
접근 가능한 Backend 실행 주소에서 양측이 같은 `main`을 사용해 수행하는
공동 Browser Smoke다.

## 2. 승인 범위와 보호선

근거는 [CHANGE_BACKLOG CR-001](../../../planning/CHANGE_BACKLOG.md)이다.

| 구분 | 이번 결과 |
| --- | --- |
| CUSTOMER `POST /api/v1/inquiries` | Path·DTO·권한 유지 |
| CONSULTANT 고객·구독 검색 | 신규 구현 |
| CONSULTANT 전화 문의 등록 | 신규 구현 |
| Web 소스 | 수정하지 않음 |
| Mobile 소스·API | 수정하지 않음 |
| AI Schema·Prompt·RAG 정책 | 수정하지 않음 |
| 신규 고객 생성·문의 제목·콜백 | 제외 |

## 3. Public API

상세 계약은 [상담사 전화 문의 API](../../../api/consultant_phone_inquiry_api.md)와
[OpenAPI Path](../../../../contracts/api/paths/consultant-phone-inquiries.yaml)를
정본으로 사용한다.

| Method | Path | operationId | Runtime |
| --- | --- | --- | --- |
| POST | `/api/v1/consultant/customer-subscriptions/search` | `searchConsultantCustomerSubscriptions` | IMPLEMENTED |
| POST | `/api/v1/consultant/phone-inquiries` | `registerConsultantPhoneInquiry` | IMPLEMENTED |

### 3.1 검색

- CONSULTANT 전용이다.
- 검색어를 URL이 아니라 JSON Body로 받아 URL·History 노출을 줄였다.
- 고객명은 trim 후 2자 이상이다.
- 연락처 형태는 숫자 정규화 후 4자리 이상이다.
- 합성·비삭제·활성 User의 ACTIVE 구독만 반환한다.
- 전화번호는 마스킹 값만 반환한다.
- 결과 없음은 200과 빈 배열이다.

### 3.2 등록

- CONSULTANT 전용이다.
- `X-Correlation-ID`와 `Idempotency-Key`가 필수다.
- 검색에서 선택한 `subscription_id`만 받고 고객·제품 관계는 서버가 다시
  검증한다.
- 같은 키·같은 요청은 기존 201 결과를 재생한다.
- 같은 키·다른 요청은 409다.
- 비활성·비합성·삭제·미존재 구독은 404로 존재를 숨긴다.

## 4. 저장·상태전이

등록 결과는 다음과 같다.

```text
channel_code=PHONE
initiated_by=<현재 상담사>
assigned_user=<현재 상담사>
assigned_role_code=CONSULTANT
priority_code=<LOW|NORMAL|HIGH|URGENT>
status_code=CONSULTATION_REQUIRED
state_version=1
```

- `support_inquiry`와 `support_inquiry_symptom`을 재사용한다.
- `REGISTER_PHONE_INQUIRY` 이벤트와 `TR-INQ-035` 초기 전이를 기록한다.
- 등록 뒤 `START_CONSULTATION`을 기존 상담 Workflow로 제공한다.
- AI·RAG 자동 호출과 `support_ai_run` 생성은 하지 않는다.

State 정본:

- [이벤트](../../../../contracts/state-machine/inquiry-events.yaml)
- [전이](../../../../contracts/state-machine/transition-rules.yaml)
- [Guard](../../../../contracts/state-machine/transition-guards.yaml)
- [역할 권한](../../../../contracts/state-machine/role-permissions.yaml)

## 5. DB 결정

새 테이블을 만들지 않았다. 전화 문의도 기존 Inquiry 원장이므로 기존
테이블에 우선순위 컬럼을 추가하는 것이 가장 작은 변경이다.

| 항목 | 결정 |
| --- | --- |
| Migration | `inquiries.0013_inquiry_priority_code` |
| 추가 컬럼 | `support_inquiry.priority_code varchar(40)` |
| 기본값 | `NORMAL` |
| 허용값 | `LOW`, `NORMAL`, `HIGH`, `URGENT` |
| DB 제약 | `ck_inquiry_priority_code` |
| 기존 행 | Migration 시 `NORMAL`로 Backfill |
| Reverse | 컬럼·제약 제거, 기존 Inquiry 행 유지 |

파일:

- [Inquiry 모델](../../../../backend/apps/inquiries/models/inquiry.py)
- [Migration 0013](../../../../backend/apps/inquiries/migrations/0013_inquiry_priority_code.py)

## 6. Runtime 파일 지도

- [Route](../../../../backend/apps/inquiries/api/urls.py)
- [View](../../../../backend/apps/inquiries/api/views.py)
- [Serializer](../../../../backend/apps/inquiries/api/serializers/consultant_phone_inquiry.py)
- [Repository](../../../../backend/apps/inquiries/repositories/consultant_phone_inquiry_repository.py)
- [Service](../../../../backend/apps/inquiries/services/consultant_phone_inquiry_service.py)
- [기존 상담사 조회 우선순위 Projection](../../../../backend/apps/inquiries/repositories/consultant_inquiry_repository.py)

## 7. 검증 결과

### 7.1 Backend·계약

| 검증 | 결과 |
| --- | ---: |
| CONS-04 표적 Runtime·계약·Migration | `19 passed` |
| Migration 순서 격리 회귀 | `39 passed` |
| API·Inquiry·Workflow 묶음 | `435 passed, 5 skipped` |
| Backend 전체 | `1016 passed, 19 skipped` |
| Root 계약 테스트 | `38 passed` |
| Data 도구 테스트 | `76 tests OK` |
| Data QA·결정적 재빌드 | `740 records, 0 errors, 0 warnings, PASS` |
| Django Check | PASS |
| `makemigrations --check --dry-run` | `No changes detected` |
| compileall | PASS |
| Source hash refresh check | PASS, `changed=0` |
| `git diff --check` | PASS |
| Ruff | NOT_RUN, 현재 Backend venv에 패키지 없음 |

19개 skip은 PostgreSQL·pgvector·실제 AI HTTP·TEAM_INTEGRATION Role 등
명시적 별도 환경 검증이며, CONS-04 Runtime 실패가 아니다.

### 7.2 PostgreSQL 격리 검증

원본 DB명을 사용하지 않고 아래 두 격리명을 사용했다.

```text
codex_cons04_20260811_r1
codex_cons04_20260811_r2
```

각 회차에서 다음 4개 파일을 실행했다.

- `test_consultant_phone_inquiry_runtime.py`
- `test_consultant_inquiry_runtime.py`
- `test_migration_0013_priority_code.py`
- `test_t022_models.py`

| 회차 | 결과 |
| --- | ---: |
| PostgreSQL R1 | `23 passed` |
| PostgreSQL R2 | `23 passed` |

두 회차 종료 후 `codex_cons04_20260811` 패턴의 잔여 DB는 0건이다.

검증 대상은 forward/reverse Migration, DB Check, 검색·등록 권한, 404,
멱등 replay·409, 상태 이력, 기존 상담사 조회 우선순위 호환이다.

## 8. CI 해시 정합성

정본 변경으로 아래 소스 해시가 바뀌어 제공 스크립트로 갱신했다.

- `inquiry-events.yaml`
- `transition-rules.yaml`
- `Inquiry model`

Data 설정·Manifest·검증 보고서의 연쇄 SHA만 재계산됐고, 합성 데이터 값,
RAG Chunk, AI 정책은 변경하지 않았다. 재빌드 결과 `changed_files=[]`다.

첫 게시 직후 Data CI에서 기능 Commit 생성 전 값인 `d2cd69a5...`가
`latest_qa_summary.json`의 `source_commit`에 남아 1개 Assertion이 실패했다.
정식 Pipeline으로 기능 Commit `1362bc9c...`를 기준 삼아 검증 보고서와
Manifest 8개를 재생성했다. 이후 Data 도구 `76 tests OK`, 결정적 재빌드
`740 records / 0 errors / 0 warnings / changed_files=[]`를 다시 통과했다.
이는 파생 메타데이터 정합화이며 합성 데이터·RAG 내용 변경이 아니다.

## 9. Web 인계 시 필수 확인

1. 게시된 Backend SHA와 실행 SHA를 동일하게 기록한다.
2. Migration 0013 적용 후 Backend를 실행한다.
3. `VITE_USE_MOCK_API=false`에서 두 API를 호출한다.
4. 검색 중·빈 결과·오류·복수 구독·선택 완료 상태를 분리한다.
5. 등록 전 고객·구독 선택을 강제한다.
6. 401·403·404·409·422·500을 계약대로 처리한다.
7. 오류 시 Mock·LocalStorage 성공 경로로 자동 전환하지 않는다.
8. 요청·응답·Backend Log의 Correlation ID를 대조한다.

## 10. 미완료·다음 Gate

- PM의 main 병합
- 대상 공용 PostgreSQL Migration 0013 적용
- 한예나 Web Remote Adapter·Unit·Build
- Web↔Backend 공동 실제 Socket Smoke
- 비작성자 QA와 최종 회귀 판정

위 Gate 전까지 최종 상태는
`BACKEND_AND_WEB_MAIN_MERGED / SHARED_BROWSER_SMOKE_PENDING`이다.

Commit·Push 여부와 게시 SHA는 이 문서의 현재형 문구가 아니라 Git 이력을
단일 근거로 확인한다.

## 11. 2026-08-12 공용 Fixture·실제 Socket 현행화

기존 `DEMO-CUSTOMER-001`의 전화번호는 빈 값이므로 이름 검색은 가능하지만
전화번호 일부 검색의 공동 재현값으로 사용할 수 없다. 기존 Demo 고객을
변경하지 않고 별도 합성 Fixture를 추가했다.

```powershell
python manage.py seed_demo_accounts
python manage.py seed_demo_products
python manage.py seed_demo_cons04_phone_inquiry --json
```

| 항목 | 값 |
| --- | --- |
| Fixture | `cons04-phone-inquiry-v1` |
| 상담사 Login Code | `DEMO-CONSULTANT-001` |
| 이름 검색어 | `전화문의 고객 001` |
| 전화번호 검색어 | `1204` |
| 공개 Subscription UUID | `c0a50412-3b89-5d39-8cd4-4c1d8c360401` |
| 기대 마스킹 | `010-****-1204` |

로컬 공식 PostgreSQL `waterbridge.public`에서 다음을 실제 Socket으로
확인했다.

| 검증 | 결과 |
| --- | --- |
| 이름 일부 검색 | `200` |
| 전화번호 일부 검색 | `200` |
| 전화번호 원문 비노출 | PASS |
| 전화 문의 등록 | `201` |
| 동일 키·동일 요청 Replay | `201` |
| Header·Body·JSON Log Correlation | PASS |
| Migration `inquiries.0013` | APPLIED |
| Migration drift | PASS |

현재 `127.0.0.1`의 임시 Socket은 검증 종료 후 닫았으므로 공용 URL이 아니다.
공동 Smoke 당일에는 접근 가능한 Runtime 주소를 별도로 합의해야 한다.

Web `main@9a670fb` 재검증 결과는 `33 files / 144 tests`, ESLint,
TypeScript, Production Build `142 modules` 모두 PASS다. 다만 CONS-04 전용
Debounce·최신 응답·빈 결과·409·422·중복 클릭·멱등 재시도 자동 Test와
실제 Browser Smoke는 별도 Gate로 유지한다.

이후 반영된 `main@8b5bb62` 변경은 RAG 실험 데이터·문서 범위이며
`web/` 경로 차이는 없다.

같은 작업선의 Backend 전체 회귀는 `1031 passed, 19 skipped`, Data QA는
`740 records / 0 errors / 0 warnings / changed_files=[]`로 PASS했다.

# 4주차 Web–Backend 실제 연결 QA 보고서

> 실행일: 2026-08-10 KST
> 기준 Commit: `8854ca7b5226df9766b24ba616067ab27d5add99`
> 실행 역할: 김은진 — 데이터·QA·DevOps
> 종합 판정: `PARTIAL_WITH_RUNTIME_BLOCKERS`

## 1. 판정 요약

인증, 고객 본인 구독 조회, 문의 생성, 증상 제출, PostgreSQL 저장,
멱등 Replay, 중복 키 충돌, 입력 오류, 역할 권한, 상태 버전 충돌과
`correlation_id` 추적은 실제 Django·PostgreSQL 환경에서 확인했다.

상담사 문의 목록·상세, 상담 시작·저장·완료, 방문 검토·생성·일정 저장은
성공 응답이 한 건도 없었다. Backend API 루트에 상담·방문·Evidence 모듈이
연결되지 않았으며 각 URL 파일도 빈 골격이다. 따라서 Web의 예시 화면과
117개 테스트 통과를 실제 상담·방문 연결 완료로 판정하지 않는다.

공개 Evidence DTO도 확정되지 않았다. Public API의 `EvidenceCard`,
`EvidenceSource`, `EvidenceVerification` Schema가 모두 빈 객체이고 Evidence
Path 계약도 `{}`다. 반면 AI 계약의 `EvidenceReference`에는 내부용
`chunk_id`, `similarity_score`가 있다. Backend 공개 Projection과 비노출
테스트가 생기기 전까지 공식 근거 전달은 `NOT_READY`다.

## 2. 실행 환경

| 항목 | 결과 |
| --- | --- |
| 저장소 venv | `backend/.venv` 실행 불가. 이전 경로를 가리켜 Python 프로세스 생성 실패 |
| 대체 환경 | Conda `watercare-bootstrap`, Python 3.13.13 |
| 설치 | `requirements/local.txt` + `constraints-py313.txt` 고정 버전 설치 |
| Django | 5.2.16 |
| DRF | 3.17.1 |
| pytest | 9.1.1 |
| PostgreSQL | 16.14, database `watercare`, schema `public`, timezone UTC |
| 실행 데이터 | 실제 개인정보가 없는 canonical `db-smoke` 합성 데이터 |

로컬 `.env`는 읽거나 출력하지 않았다. 현재 로컬 설정만으로는
`SYN-CUSTOMER-001` 로그인이 401이었으므로, 라이브 서버 프로세스에만
`.env.example`의 공개 합성 계정 allowlist를 환경변수로 적용했다.

## 3. 데이터·계약·회귀 Gate

| 검증 | 현재 실행 결과 | 판정 |
| --- | --- | --- |
| Django `check` | 문제 0 | `PASS` |
| Migration Drift | `No changes detected` | `PASS` |
| Backend 전체 SQLite Test | 835 passed, PostgreSQL 전용 13 skipped | `PASS_WITH_EXPECTED_SKIPS` |
| PostgreSQL 대상 Test | 관련 파일 126 passed, skip 0 | `PASS` |
| Data 단위 Test | 69 passed | `PASS` |
| Data QA 결정적 재생성 | 오류 0, 경고 0, Drift 0, 48 files, 740 records | `PASS` |
| Data Finalize | Manifest 155, temp/work 잔여 없음 | `PASS` |
| State Machine | 상태 13, 이벤트 30, 전이 34, Guard 39, Action 23 | `PASS` |
| Contract Crosswalk | Runtime 2, OpenAPI 9, Contract-only 2, Deferred 10 | `PASS` |
| Code Registry | Registry 28, Code 144 | `PASS` |
| OpenAPI | YAML 101, Ref 303, Path 22, Operation 23 | `PASS` |
| Contract Example | API JSON 34/34, 통합 예시 5, Wrapper 25 | `PASS` |
| Root Contract Test | 8 passed | `PASS` |
| Web Test | 28 files, 117 tests | `PASS` |
| Web Lint | 오류 없음 | `PASS` |
| Web Build | TypeScript + Vite, 124 modules | `PASS` |

PostgreSQL 대상 Test는 SQLite Gate에서 제외됐던 pgvector 구조, 복합 FK,
PostgreSQL catalog, 방문 결과 구조와 문의 제출 row-lock Case를 포함한 관련
테스트 파일을 `config.settings.local`로 실행한 결과다.

## 4. PostgreSQL 합성 데이터 적재

`db-smoke` 프로필을 Dry-run, 실제 적재, Replay 순서로 실행했다.

| 실행 | created | updated | unchanged | projected | 결과 |
| --- | ---: | ---: | ---: | ---: | --- |
| Dry-run | 31 | 0 | 0 | 6 | 모든 검증 후 Rollback |
| 첫 적재 | 31 | 0 | 0 | 6 | 저장 완료 |
| Replay | 0 | 0 | 31 | 6 | 중복 변경 없음 |

공통 입력은 Dataset `0.9.0`, Source 37건, Fixture Set SHA-256
`7C407CB6F013BE584011E446650BACD4A6A958895F88448B17EE523AA5B9D068`이다.
검증 후 PostgreSQL 컨테이너는 중지했고 합성 데이터가 있는 Docker Volume은
삭제하지 않았다.

별도 Demo Seed에는 정합성 문제가 있다. `seed_demo_products`는
`DEMO-PMD-001`을 생성하지만 구독 조회 Repository는 `WPUJAC104DWH`만
노출한다. 따라서 Demo Seed만 실행한 직후 `DEMO-CUSTOMER-001`의 공개 구독
목록은 0건이었다. Runtime 코드는 수정하지 않고 canonical `db-smoke`
handoff로 검사 데이터를 준비했다.

## 5. 실제 HTTP·DB 흐름

### 5.1 확인된 흐름

| 검사 | 실제 결과 |
| --- | --- |
| Health·CORS | 200, correlation 발급·재사용, 허용 Origin만 CORS Header 반환 |
| Demo Auth | Login·Me·Refresh rotation·Logout·폐기 Token 거부 통과 |
| 개인정보 Projection | `Me` 응답에 password, phone, address, token Key 없음 |
| 고객 구독 목록 | canonical 합성 고객의 `WPUJAC104DWH` ACTIVE 구독 조회 |
| 문의 생성 | 201, `DRAFT`, `state_version=1`, `allowed_actions` 반환 |
| 같은 키·같은 입력 | 201 Replay, 같은 Inquiry, 추가 Side Effect 없음 |
| 같은 키·다른 입력 | 409 `DUPLICATE-EVENT-01` |
| 입력 오류 | 422 `VALIDATION_ERROR` |
| 역할 오류 | 상담사의 고객 문의 생성 403 `FORBIDDEN` |
| 동시 수정 기준 | 오래된 `state_version` 제출 409 `STATE-CONFLICT-01` |
| 증상 제출 | 200, `QUESTIONNAIRE_IN_PROGRESS`, `state_version=2` |
| 제출 Replay | 200, `idempotent_replay=true` |

### 5.2 상담·방문 Probe

| 기능 | Method·Path | 실제 응답 | 판정 |
| --- | --- | ---: | --- |
| 상담사 목록 | `GET /api/v1/inquiries` | 403 `FORBIDDEN` | 고객 문의 생성 View와 경로 충돌, 목록 미구현 |
| 상담사 상세 | `GET /api/v1/inquiries/{id}` | 404 `RESOURCE_NOT_FOUND` | Route 미연결 |
| 상담 시작 | `POST /api/v1/inquiries/{id}/start-consultation` | 403, 공통 JSON 오류 코드 없음 | Route 미연결, CSRF가 catch-all 이전 차단 |
| 상담 저장 | `PATCH /api/v1/inquiries/{id}/consultation-summary` | 403, 공통 JSON 오류 코드 없음 | Route 미연결 |
| 상담 완료 | `POST /api/v1/inquiries/{id}/complete-consultation` | 403, 공통 JSON 오류 코드 없음 | Route 미연결 |
| 방문 검토 | `POST /api/v1/inquiries/{id}/visit-review` | 403, 공통 JSON 오류 코드 없음 | Route 미연결 |
| 방문 생성 | `POST /api/v1/inquiries/{id}/visits` | 403, 공통 JSON 오류 코드 없음 | Route 미연결 |
| 방문 일정 저장 | `PATCH /api/v1/visits/{visit_id}/schedule` | 403, 공통 JSON 오류 코드 없음 | Route 미연결 |

8개 Probe 중 성공 응답은 0개다. `backend/config/api_urls.py`에는 accounts,
subscriptions, inquiries만 include되어 있고 consultations, visits, evidence의
API URL 파일에는 설명 문자열만 있다.

## 6. 요청 추적 확인

라이브 문의 생성 한 건에서 다음 연결을 확인했다.

```text
correlation_id=23963565-a026-4642-a80c-e83fc4eda7b1
HTTP response header/body metadata=일치
PostgreSQL TransitionHistory=START_INQUIRY, state_version 1, 1건
PostgreSQL completed IdempotencyRecord=1건
최종 Inquiry=QUESTIONNAIRE_IN_PROGRESS, state_version 2
구조화 Backend Log 동일 correlation_id=3건
```

화면이 실제 서버를 호출하지 않으므로 Web 화면 요청과의 연결은 확인하지
못했다. 위 결과는 라이브 Smoke Client→Backend Log→PostgreSQL의 연결이다.

## 7. 공개 근거·개인정보 기준 검토

현재 확인된 소비자 기준은 다음과 같다.

- Web은 문서명, 버전, 페이지, 요약, HTTPS 공식 Landing URL과 검증 Label만
  표시한다.
- Web 테스트는 `chunk_id`, 검색 점수, 내부 경로, 직접 다운로드와 원문 전체가
  Evidence Card에 표시되지 않음을 확인한다.
- 전화번호 표시는 가운데 자리를 Masking한다.
- 인증 `Me` Projection은 전화번호, 주소, Token과 Password Key를 노출하지
  않는다.

그러나 이 기준은 Backend–AI 간 최종 공개 DTO 계약이 아니다. 다음 항목이
비어 있어 이동윤·최지용의 승인 완료로 판정할 수 없다.

- `contracts/api/components/schemas/evidence/EvidenceCard.yaml`
- `contracts/api/components/schemas/evidence/EvidenceSource.yaml`
- `contracts/api/components/schemas/evidence/EvidenceVerification.yaml`
- `contracts/api/paths/evidence.yaml`
- Backend Evidence Route와 공개 Projection Test

AI `EvidenceReference`의 `chunk_id`, `similarity_score`는 내부 처리용으로만
유지하고 Public API DTO에서 제거해야 한다. 원문 전체, 내부 파일 경로,
Vector 식별자와 검색 점수도 Public DTO에 포함하지 않는다.

## 8. 실행하지 못한 검사

| 검사 | 이유 | 판정 |
| --- | --- | --- |
| Web 실제 목록·상세 | Backend Route 미구현 | `BLOCKED` |
| 상담 시작·저장·완료 DB 결과 | Backend Route·Service 미연결 | `BLOCKED` |
| 방문 요청·기사·일정 DB 결과 | Backend Route·Service 미연결 | `BLOCKED` |
| AI 오류 Live 처리 | Backend–AI Live Route 없음 | `BLOCKED` |
| 공식 Evidence Live 응답·비노출 | Public Schema·Route 없음 | `BLOCKED` |
| 고객→상담사→기사→고객 전체 E2E | 위 선행 Runtime 부재 | `BLOCKED` |
| 실제 Web 화면 correlation 연결 | Web이 Mock Repository 사용 | `BLOCKED` |

## 9. 관할 밖 발견 문제와 인계

### [최지용 — Backend·DB](../../handoffs/week5/20260810_김은진_to_최지용_Backend_DB_실연동_인계.md)

- `backend/config/api_urls.py`에 상담·방문·Evidence Runtime Route가 없다.
- `backend/apps/consultations/api/urls.py`, `backend/apps/visits/api/urls.py`,
  `backend/apps/evidence/api/urls.py`가 빈 골격이다.
- `GET /api/v1/inquiries`는 고객 문의 생성 View와 충돌해 상담사에게 403을
  반환한다. 계약상 상담사 목록 200 구현이 필요하다.
- Demo Product Seed 코드와 구독 조회 지원 모델 필터가 불일치한다.
- 미등록 POST/PATCH가 공통 JSON 404 대신 CSRF 403 HTML을 반환한다.
- 각 Mutation에서 동일 correlation ID로 HTTP·로그·상태 이력·업무 레코드가
  이어지는 통합 Test를 추가해야 한다.

### [이동윤 — AI·RAG](../../handoffs/week5/20260810_김은진_to_이동윤_AI_Evidence_오류처리_인계.md)

- AI `EvidenceReference`에서 Public DTO로 전달할 allowlist를 확정해야 한다.
- `chunk_id`, `similarity_score`, 내부 경로와 원문 전체의 외부 비노출을
  Backend와 함께 검증해야 한다.
- Timeout, 검색 실패, 근거 없음의 실제 Backend 전달과 저장 결과가 필요하다.

### [윤승혁 — PM·계약](../../handoffs/week5/20260810_김은진_to_윤승혁_PM_계약_일정승인_인계.md)

- 빈 Evidence Public Schema·Path를 Backend 구현과 함께 확정해야 한다.
- 상담·방문 11개 계약 전용 Operation의 구현 순서와 목표일을 승인해야 한다.
- `allowed_actions`, 상태 전환과 공개 근거 필드의 최종 책임 경계를 승인해야
  한다.

### [한예나 — Web](../../handoffs/week5/20260810_김은진_to_한예나_Web_실제API_전환_인계.md)

- Backend가 목록·상세·상담·방문·Evidence Route와 Example을 제공한 뒤 Mock
  Repository를 실제 API Adapter로 교체해야 한다.
- 현재 입력 보호·409 UI·Evidence 비노출 테스트는 유지하되, 라이브 오류
  Wrapper와 correlation ID를 소비하는 통합 Test를 추가해야 한다.

## 10. 재현 명령

아래 `<python-3.13>`은 Conda `watercare-bootstrap`의 Python 3.13.13 실행
파일을 뜻한다. 실제 경로와 `.env` 값은 보고서에 기록하지 않는다.

```powershell
<python-3.13> -m pip install -r backend/requirements/local.txt -c backend/requirements/constraints-py313.txt

Set-Location backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.test'
<python-3.13> manage.py check
<python-3.13> manage.py makemigrations --check --dry-run
<python-3.13> -m pytest -q

Set-Location ..
<python-3.13> -B -m unittest discover -s data/tools/tests -v
<python-3.13> -B data/tools/pipeline.py qa --verify-rebuild
<python-3.13> -B data/tools/pipeline.py finalize

Set-Location backend
<python-3.13> manage.py import_synthetic_handoff --profile db-smoke --dry-run
<python-3.13> manage.py import_synthetic_handoff --profile db-smoke

# 서버 실행 후 별도 Terminal
Set-Location ..
<python-3.13> scripts/smoke/check_backend_auth.py
# check_week4_service_runtime.py는 2026-08-31 폐기됨. 아래 결과는 당시의 기록임.
```

## 11. 최종 결론

고객 인증·구독·문의 생성·증상 제출 Slice는 실제 PostgreSQL과 로그까지
추적 가능하다. 오류 검사 중 권한, 중복 저장, 입력, 상태 버전 충돌도 실제
응답으로 확인했다.

상담사 목록·상세, 상담, 방문, AI 오류, 공개 Evidence와 전체 사용자 흐름은
Runtime 부재로 확인하지 못했다. 그러므로 요청 문서의 김은진 필요 결과 중
`오류 검사 결과`와 부분 `실제 연결 검사 결과`는 확보했지만, 상담·방문을
포함한 최종 통합 결과는 `BLOCKED`이며 4주차 Web 업무를 100% 완료로 처리할
수 없다.

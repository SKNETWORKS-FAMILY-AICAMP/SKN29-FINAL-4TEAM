# 최지용 담당 Backend·DB 실연동 인계

> 발신: 김은진 — 데이터·QA·DevOps
> 수신: 최지용 — Backend·DB
> 작성일: 2026-08-10 KST
> 검증 기준 Commit: `8854ca7b5226df9766b24ba616067ab27d5add99`
> 현재 상태: `ACTION_REQUIRED / CONSULTATION_VISIT_RUNTIME_BLOCKED`
> TEAM_INTEGRATION 추가 판정: `PACKAGE_QA_APPROVE / REMOTE_NOT_PROVISIONED`

## 1. 인계 목적

고객 인증·구독·문의 생성·증상 제출까지 확인된 Runtime 다음에 상담사
목록·상세, 상담, 방문, Evidence를 실제 Django Route·DB 저장으로 연결해
달라는 요청이다. 김은진은 Backend Production 코드를 수정하지 않았으며,
아래 내용은 실제 PostgreSQL·HTTP 재현 결과에 근거한다.

전체 실행 증거와 명령은
[Web–Backend 실제 연결 QA 보고서](../../testing/results/week4-web-backend-live-verification-20260810.md)를
기준으로 한다.

## 2. 현재 검증 현황

| 항목 | 현재 결과 | 판정 |
| --- | --- | --- |
| Django Check·Migration Drift | 문제 0, 변경 0 | `PASS` |
| Backend 전체 SQLite Test | 835 passed, PostgreSQL 전용 13 skipped | `PASS_WITH_EXPECTED_SKIPS` |
| PostgreSQL 대상 Test | 관련 파일 126 passed, skip 0 | `PASS` |
| 실제 PostgreSQL | 16.14 연결, Migration·합성 Seed·`db-smoke` 적재 성공 | `PASS` |
| Auth·구독·문의 생성·증상 제출 | 실제 HTTP·DB 저장 성공 | `VERIFIED_RUNTIME` |
| 멱등·입력·권한·상태 충돌 | Replay, 409, 422, 403 확인 | `VERIFIED_RUNTIME` |
| HTTP→로그→DB 추적 | 동일 correlation ID 연결 | `VERIFIED_RUNTIME` |
| 상담·방문 Probe | 8개 중 성공 0 | `BLOCKED` |
| Evidence Runtime | Public Schema·Path·Route 없음 | `BLOCKED` |

검증된 고객 Slice는 `DRAFT state_version=1` 문의 생성 후 증상 제출로
`QUESTIONNAIRE_IN_PROGRESS state_version=2`까지 전환된다. 같은 키·같은
입력은 Replay되고, 같은 키·다른 입력은 `DUPLICATE-EVENT-01`, 오래된
버전은 `STATE-CONFLICT-01`을 반환했다.

## 3. 재현된 Backend 결함

| 우선 | 실제 현상 | 계약상 기대 | 관련 파일 |
| ---: | --- | --- | --- |
| P0 | `GET /api/v1/inquiries`가 상담사에게 403 `FORBIDDEN` | 배정 문의 목록 200 | `backend/config/api_urls.py`, `backend/apps/inquiries/api/urls.py` |
| P0 | `GET /api/v1/inquiries/{id}`가 404 | 배정 문의 상세 200 또는 객체 권한 404 | 위 Route와 조회 Service·Repository |
| P0 | 상담 시작·저장·완료 Route 성공 0 | 계약된 상태 전환·요약 저장 | `backend/apps/consultations/**`, `backend/apps/workflow/**` |
| P0 | 방문 검토·생성·일정 Route 성공 0 | Visit와 상태 이력 원자 저장 | `backend/apps/visits/**`, `backend/apps/workflow/**` |
| P1 | 미등록 POST/PATCH가 공통 JSON 404 대신 CSRF 403 HTML | 공통 Wrapper·오류 코드 | `backend/config/urls.py`, 공통 오류 경계 |
| P1 | Demo Seed 제품은 `DEMO-PMD-001`, 구독 조회는 `WPUJAC104DWH`만 공개 | 공식 Setup 직후 조회 가능한 합성 구독 | 제품·구독 Seed와 조회 Repository |
| P1 | Evidence URL과 Public Projection 없음 | 내부 필드가 제거된 EvidenceCardDTO | `backend/apps/evidence/**` |

`backend/apps/consultations/api/urls.py`, `backend/apps/visits/api/urls.py`,
`backend/apps/evidence/api/urls.py`는 현재 설명 문자열만 있고
`backend/config/api_urls.py`에도 include되지 않는다.

## 4. 요청사항

### P0 — 상담사 목록·상세

- `GET /api/v1/inquiries`를 고객 POST View와 분리해 상담사 배정 범위만
  반환한다.
- 검색·상태·위험도·우선순위·기간·정렬·페이지 Query를 OpenAPI와 맞춘다.
- 비배정·타인 문의는 존재 여부를 숨기는 계약대로 처리한다.
- 상세 응답은 승인된 합성 Section만 포함하고 Evidence 미확정 필드는
  임의 추가하지 않는다.

### P0 — 상담·방문 Mutation

- 상담 시작, 사용자 실행 저장, 요약 확정, 상담 완료 Route를 연결한다.
- 방문 검토, 방문 생성, 방문 불필요, 일정 저장, 방문일 확정을 구현한다.
- 모든 쓰기에서 `state_version`, `Idempotency-Key`, correlation ID와
  `allowed_actions`를 계약대로 처리한다.
- 업무 레코드, 상태 이력과 멱등 레코드를 한 트랜잭션으로 저장한다.
- 409 발생 시 최신 상태·버전·허용 행동을 반환하고 기존 입력을 덮어쓰지
  않도록 소비자가 판단할 수 있게 한다.

### P1 — 오류·Seed·Evidence

- 미등록 API Method·Path도 JSON Wrapper와 `X-Correlation-ID`를 유지한다.
- 공식 Setup의 Demo Seed와 조회 지원 모델 필터를 같은 기준으로 맞춘다.
- 이동윤의 내부 AI Evidence에서 Public allowlist만 조립하는
  `EvidenceCardDTO`를 구현하고 비노출 테스트를 추가한다.

## 5. 완료 증거 요청

- [ ] 구현한 Method·Path와 변경 파일 목록
- [ ] Model·Migration 변경 여부와 `makemigrations --check --dry-run` 결과
- [ ] PostgreSQL에서 목록·상세·상담·방문 정상 흐름 결과
- [ ] 비배정 404, 역할 403, 입력 422, 상태 409, 멱등 충돌 결과
- [ ] 같은 correlation ID의 HTTP Header·로그·업무 행·상태 이력 연결
- [ ] 같은 Idempotency-Key Replay 시 중복 업무 행 0건
- [ ] 실패 시 트랜잭션 Rollback 결과
- [ ] 전체 Backend Test 집계와 PostgreSQL 전용 Test 집계
- [ ] Public Evidence 비노출 필드 테스트

## 6. 회신 형식

```text
owner=최지용
decision=ACCEPT | CHANGE_REQUEST | BLOCKED
target_commit=<SHA>
implemented_operations=<operationId 목록>
changed_files=<경로 목록>
migrations=<없음 또는 Migration 목록>
commands=<실행 명령>
test_results=<집계와 Exit code>
postgresql_results=<정상·오류·Replay·Rollback>
trace_evidence=<HTTP·로그·DB 연결>
contract_diff=<없음 또는 경로·필드·영향>
remaining_blockers=<없음 또는 담당자·필요 입력>
target_date=<YYYY-MM-DD>
```

Route·Model·Migration·실행 테스트 증거가 모두 준비되기 전에는 상담·방문
Runtime을 `VERIFIED`로 회신하지 않는다.

## 7. TEAM_INTEGRATION DB 패키지 QA 인계

[독립 QA 결과](../../testing/results/team-integration-db-package-qa-20260810.md)에서
후보 파일 17/17, 패키지 56 passed, 격리 DB 전체 Forward Migration,
Seed Replay, T-005 `READY`, 실제 4-Role Matrix와 Backend 882 passed/14 skipped를
확인했다. 후보 구현 Commit `94ad7b9`도 현재 원격 브랜치들에 포함돼 있다.

최지용 담당 후속 조치는 다음과 같다.

- 원격 Migrator 실행 창구와 단일 실행자를 지정한다.
- 원격 Migration 후 Admin 권한 재조정 순서를 유지한다.
- Backend 실행에는 Runtime Role만 주입하고 Migrator Credential을 상시
  Runtime에 제공하지 않는다.
- 원격 Endpoint·DNS·CA·Secret 준비 뒤 김은진에게 Migration·Role·API
  Smoke 재검증 입력을 전달한다.
- 현재 로컬 QA 임시 비밀번호는 폐기됐으므로 이 DB를 팀 공유 대상으로
  전환하지 말고, 재사용 필요 시 승인된 보안 경로에서 명시 회전한다.

원격 `verify-full`, `connection_ssl=true`와 Backend API Smoke 전에는
`TEAM_INTEGRATION_APPROVE`로 회신하지 않는다.

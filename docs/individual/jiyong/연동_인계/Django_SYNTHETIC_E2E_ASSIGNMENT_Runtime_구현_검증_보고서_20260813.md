# Django SYNTHETIC_E2E_ASSIGNMENT Runtime 구현·검증 보고서

## 0. 문서 정보

| 항목 | 내용 |
| --- | --- |
| 작업일 | 2026-08-13 KST |
| 담당 | 최지용 — Backend·DB |
| 상태 | `LOCAL_COMMIT_VERIFIED / PUSH_PENDING / WEB_G4_PENDING` |
| 착수 기준 | `origin/main@df9c01ccc4f6de748dec4503bb08f53aa42efe76` |
| 게시 기준 | `origin/jiyong@b4dbddbde1c5fe3fa57ab30e2d62d0b324bf2dce` |
| 구현 Commit | `fce4cef6d6dea866f529d0b4bdd0144448bde1fd` |
| 작업 Branch | `codex/jiyong-web-e2e-assignment-20260813` |
| 작업공간 | AI 작업과 분리한 전용 Git Worktree |
| 승인 범위 | 대표 합성 E2E 문의 1건을 `DEMO-CONSULTANT-001`에 결정적으로 배정 |

## 1. 한 문장 결론

Mobile에서 새로 만든 대표 합성 문의를 정확한 UUID로 준비한 뒤 기존
`REQUEST_CONSULTATION` Transaction 안에서만 Demo 상담사에게 배정하도록
구현했고, 최신 게시 기준에서 신규·관련 회귀 43건과 실제 PostgreSQL 신규
14건을 두 번 실패 없이 통과했다. 착수 기준의 Backend 전체 회귀 기록은
`1114 passed, 19 skipped`이며, 최신 전체 회귀는 게시 필수 Gate에서 제외했다.

아직 실제 Mobile Inquiry와 Web Browser를 사용한 공동 G4는 실행하지 않았다.

## 2. 해결한 연결 공백

기존 Runtime은 고객이 상담을 요청하면 다음 두 작업까지만 수행했다.

1. Inquiry를 `CONSULTATION_REQUIRED`로 전환한다.
2. `WAITING`, `consultant=null`인 Consultation을 생성한다.

그러나 Inquiry의 `assigned_user`가 비어 있어 상담사 Web 목록에는 보이지 않았다.
Web 목록·상세는 본인에게 배정된 문의만 공개하므로, 같은 Inquiry가 Mobile에서
Web으로 넘어가는 대표 E2E를 끝낼 수 없었다.

이번 작업은 이 공백만 연결한다.

```text
Mobile Inquiry가 AI_GUIDANCE 도달
→ Backend가 정확한 inquiry_id를 안전하게 준비
→ Mobile이 기존 REQUEST_CONSULTATION 호출
→ 같은 Transaction에서 Inquiry를 DEMO-CONSULTANT-001에 배정
→ 기존 WAITING Consultation과 State 전이 실행
→ 기존 Web 목록·상세에 동일 Inquiry 노출
→ 실제 START_CONSULTATION 때만 Consultation.consultant 지정
```

## 3. 구현 범위

### 3.1 준비 명령

새 관리 명령:

```powershell
python backend/manage.py prepare_synthetic_e2e_assignment --inquiry-id <MOBILE_CREATED_INQUIRY_UUID> --json
```

이 명령은 지정한 UUID의 한 행을 잠근 뒤 다음을 모두 확인한다.

- 공식 Demo 고객 `DEMO-CUSTOMER-001` 소유
- 고객 계정·Profile 모두 합성 데이터이며 활성 상태
- Mobile 채널
- 활성 구독
- 활성 MVP 지원 제품 `WPUJAC104DWH`
- 고객 확인 대표 증상 `LOW_FLOW`(출수량 저하)
- 문의 상태 `AI_GUIDANCE`
- 기존 담당자 없음
- 기존 Consultation 없음
- 활성 합성 상담사 `DEMO-CONSULTANT-001` 존재
- 다른 Scenario Marker 없음

통과하면 `scenario_code=SYN-JAC104-002-RUNTIME-E2E`만 기록한다.
상태·버전·담당자·Consultation은 이 단계에서 바꾸지 않는다.

`--json` 출력은 Secret 없이 다음 인계값만 제공한다.

- Inquiry UUID와 표시 코드
- 현재 상태와 `state_version`
- 배정 대상 상담사 코드
- 적용 Operation과 합성 E2E 방식

### 3.2 상담 요청 Transaction 연결

기존 상담 요청 Service가 Idempotency 새 요청을 확정한 뒤, 기존 Consultation 생성과
State 전이 전에 합성 Marker를 확인한다.

- Marker가 없으면 기존 동작 그대로 미배정 상태를 유지한다.
- Marker가 있으면 정확한 Demo 상담사만 잠그고 Inquiry를 배정한다.
- 이미 같은 상담사면 재배정하지 않는다.
- 다른 담당자가 있으면 `409`로 실패하고 덮어쓰지 않는다.
- Demo 상담사가 없거나 비활성이면 `500` Fail-closed 처리한다.
- 이후 오류가 발생하면 배정·상담·상태·이력·Idempotency가 모두 Rollback된다.

배정 이후에도 Consultation은 `WAITING`, `consultant=null`이다.
상담사가 기존 Start API를 실행할 때만 `IN_PROGRESS`와 consultant가 기록된다.

## 4. 변경 파일과 책임

| 파일 | 변경 | 책임 |
| --- | --- | --- |
| [합성 배정 Service](../../../../backend/apps/inquiries/services/synthetic_e2e_assignment_service.py) | 신규 | 경계 검증·Demo 상담사 잠금·배정·Fail-closed |
| [준비 관리 명령](../../../../backend/apps/inquiries/management/commands/prepare_synthetic_e2e_assignment.py) | 신규 | 정확한 Inquiry UUID 준비·Marker·공개 Crosswalk |
| [기존 상담요청 Service](../../../../backend/apps/inquiries/services/consultation_request_service.py) | 수정 | 기존 Transaction 안에서 합성 배정 호출 |
| [Runtime 자동검증](../../../../backend/tests/api/test_synthetic_e2e_assignment_runtime.py) | 신규 | 준비·배정·권한·Replay·Rollback 회귀 |

## 5. 변경하지 않은 영역

다른 담당자 작업과 충돌하지 않도록 다음은 수정하지 않았다.

- `web/**`
- `mobile/**`
- `ai/**`
- OpenAPI·DTO·State Machine·Action Crosswalk
- `data/synthetic/fixtures/**`
- Model·Table·Column·Migration
- Queue·Claim API·운영 자동배정 정책
- 상담 시작·기록·요약·완료 기존 Runtime

기존 canonical `SYN-JAC104-002 / DEMO-INQ-002` 행도 수정하거나 초기화하지 않았다.
해당 행은 이미 완료 이력이므로 최종 E2E에는 Mobile이 새로 만든 Inquiry를 사용한다.

## 6. 작업·검증 반복 결과

### 6.1 실패 우선 검증

구현 전 신규 테스트를 먼저 실행했다.

```text
ModuleNotFoundError:
apps.inquiries.services.synthetic_e2e_assignment_service
```

기능이 실제로 없어서 실패함을 확인한 뒤 최소 구현을 추가했다.

### 6.2 신규 Slice 반복

| 반복 | 결과 | 확인 내용 |
| ---: | ---: | --- |
| 최초 구현 | `10 passed` | 준비·배정·권한·Replay·기본 Rollback |
| 대표 조건 강화 | `12 passed` | LOW_FLOW·다른 상담사 Start 404·후기 실패 Rollback |
| 최종 경계 강화 | `14 passed` | 공식 Demo 고객·중복 Marker 거부 포함 |

신규 테스트가 확인한 핵심은 다음과 같다.

- 준비 명령의 동일 Inquiry 재실행은 같은 결과를 반환한다.
- 제품·채널·상태·고객·증상이 다르면 Marker를 기록하지 않는다.
- 두 번째 활성 Marker는 거부한다.
- 표시된 Inquiry만 Demo 상담사에게 배정한다.
- 일반 상담 요청은 기존처럼 미배정 상태를 유지한다.
- Consultation은 Start 전까지 `WAITING`, `consultant=null`이다.
- Demo 상담사는 목록·상세를 볼 수 있다.
- 다른 상담사는 목록에서 제외되고 상세·Start가 모두 `404`다.
- Demo 상담사의 Start 후 기존 Runtime이 `IN_PROGRESS`로 전환한다.
- 같은 Idempotency Key Replay는 배정·상담·이력을 중복 생성하지 않는다.
- 비활성 Demo 상담사와 기존 타 담당자 배정은 Fail-closed 처리한다.
- 후기 DB 오류 시 모든 쓰기가 Rollback된다.

### 6.3 기존 Runtime 회귀

다음 기존 영역과 신규 테스트를 함께 실행했다.

- 고객 상담 요청
- 기존 상담요청 Demo Seed
- 상담사 목록·상세
- 상담 시작·기록·요약·확정·완료
- 신규 합성 E2E 배정

결과:

```text
43 passed, 1 skipped
```

Skip 1건은 PostgreSQL 전용 Row Lock 검증이어서 SQLite 회귀 실패가 아니다.

### 6.4 실제 PostgreSQL 반복검증

원래 DB 이름을 사용하지 않고 서로 다른 격리 Test DB로 두 번 실행했다.

| 격리 실행 | 결과 |
| --- | ---: |
| `codex_synthetic_e2e_assignment_20260813_r3` | `14 passed` |
| `codex_synthetic_e2e_assignment_20260813_r4` | `14 passed` |

두 실행 모두 테스트 종료 후 Django가 Test DB를 정리했다.
DSN·비밀번호·Token은 출력하거나 문서에 기록하지 않았다.

### 6.5 구조·전체 회귀

| 검증 | 결과 |
| --- | ---: |
| Django System Check | PASS, issue 0 |
| `makemigrations --check --dry-run` | `No changes detected` |
| Python compileall | PASS |
| `git diff --check` | PASS |
| Backend 전체 — 착수 기준 | `1114 passed, 19 skipped` |
| Backend 전체 — 게시 기준 | `NOT_COMPLETED / NON_BLOCKING` |

착수 기준 전체 Skip 19건은 PostgreSQL 전용 구조 검사, 외부 AI 실제 Socket,
TEAM_INTEGRATION Role처럼 별도 실행 조건이 명시된 항목이다. 게시 기준 전체
회귀는 10분 실행 제한으로 88%에서 종료됐고, 사용자 요청에 따라 재실행을
중단했다. 기능 실패는 보고되지 않았으며, 이번 합성 배정과 직접 관련된 회귀와
PostgreSQL 검증은 최신 기준에서 모두 통과했다.

## 7. 왜 다른 담당자 작업에 영향을 주지 않는가

### 완료 시점 최신 Branch 교차점검

`origin/main`은 `920176ebd77c9b5285ca62aea5f76671f9816997`,
`origin/jiyong`은 `b4dbddbde1c5fe3fa57ab30e2d62d0b324bf2dce`까지
전진했다. 후보 5개 경로와 원격 변경의 교집합이 0개임을 확인한 뒤, 기존
`jiyong` 이력을 그대로 보존하면서 후보 두 Commit만 최신 `origin/jiyong` 위에
재배치했다. Force Push나 기존 Commit 재작성은 사용하지 않는다.

### AI

AI 호출·Schema·Prompt·Evidence·Danger 코드를 읽거나 수정하지 않는다.
AI가 Inquiry를 `AI_GUIDANCE`까지 만든 뒤 UUID만 전달받는다.

### Mobile

기존 API Path·Request·Response·DTO가 바뀌지 않는다.
Mobile은 상담 요청 직전에 잠시 멈추고 Inquiry UUID를 전달한 뒤 기존
`REQUEST_CONSULTATION`을 그대로 호출하면 된다.

### Web

기존 assigned-only 목록·상세와 기존 상담 Action을 그대로 사용한다.
Web Adapter를 Backend가 대신 수정하지 않는다.

### QA·DB

새 Migration이나 Schema 변경이 없다. 실제 공용 환경 반영 전에는 QA가 아니라
작성자 격리 DB에서만 검증했다. 독립 QA 판정은 별도 단계로 남는다.

## 8. 실행 제한

고정 Marker는 한 격리 DB에서 대표 Inquiry 한 건만 허용한다.

```ini
assignment_run_policy=ONE_SHOT_PER_ISOLATED_DB
retry_policy=REPLAY_SAME_INQUIRY
new_inquiry_retry=FRESH_ISOLATED_DB_REQUIRED
direct_db_reset=FORBIDDEN
canonical_fixture_reset=FORBIDDEN
```

상담 요청 전에는 같은 Inquiry의 준비 명령 재실행을 허용한다. 상담 요청 후에는
준비 명령이 거부되며, 같은 Idempotency Key로 기존 요청 결과만 Replay한다.
완료된 Inquiry를 직접 Update로 되돌리거나 Marker를 다른 행으로 수동 이동하지 않는다.

## 9. 실제 공동 G4 전 남은 입력

이번 작성자 검증은 완료됐지만 다음 값이 아직 없어 실제 공동 G4는 대기한다.

1. `DEMO-CUSTOMER-001`의 `WPUJAC104DWH` ACTIVE 구독
2. Mobile이 실제로 새로 만든 `LOW_FLOW` Inquiry UUID
3. 해당 Inquiry가 `AI_GUIDANCE`에 도달했다는 상태·버전
4. 최신 통합 Backend SHA와 접근 가능한 Base URL
5. 준비 명령 JSON Crosswalk
6. Mobile 상담 요청 응답의 최신 상태·버전·Correlation ID
7. 한예나 Web에서 같은 Inquiry 목록·상세·상담 Action 결과

대표 구독이 없다면 `seed_demo_mobile_followup` 또는 동등한 공식 준비 절차를 먼저
사용한다. 기존 `seed_demo_request_consultation`은 `DEMO-PMD-001` 기반이므로
`WPUJAC104DWH` 대표 E2E 입력으로 대체하면 안 된다.

## 10. 다음 실행 순서

1. 후보 두 Commit을 `jiyong`에 Fast-forward Push하고 원격 SHA를 확인한다.
2. 대표 WPU 구독을 공식 Seed/준비 절차로 확인한다.
3. Mobile이 새 Inquiry를 `AI_GUIDANCE`까지 진행하고 잠시 멈춘다.
4. 최지용이 정확한 UUID로 준비 명령을 실행하고 JSON을 기록한다.
5. Mobile이 기존 상담 요청 API를 호출한다.
6. 같은 Inquiry가 Demo 상담사 Web 목록·상세에 보이는지 공동 G4를 실행한다.
7. 상담 Start·기록·요약·완료와 새로고침 지속성을 확인한다.
8. 그 뒤에만 PM main 병합·독립 QA·전체 E2E 판정을 진행한다.

## 11. 현재 판정

```ini
backend_slice=SYNTHETIC_E2E_ASSIGNMENT
implementation=PASS
author_tests=PASS
postgresql_repeat=PASS
backend_full_regression_latest=NOT_COMPLETED_NON_BLOCKING
contract_change=NONE
migration_change=NONE
other_owner_source_change=NONE
commit_push=LOCAL_COMMIT_ONLY
actual_mobile_inquiry_prepare=NOT_RUN
web_same_inquiry_g4=WAITING
overall=BACKEND_CANDIDATE_READY
```

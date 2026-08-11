# Django·PostgreSQL Backend 작성자 회귀검증 보고서

> 최초 검증일: 2026-08-08 KST
> 현재화: 2026-08-09 KST
> 기준선: 2026-08-08 22:00 KST 기준 `origin/main`(data-ci.yml 충돌 처리 반영) 기반 별도 안전 Worktree
> 판정: `LOCAL_AUTHOR_VERIFIED` — 비작성자 QA·PM 완료 판정 전
> 게시 범위: `origin/jiyong` 검토 후보

## 1. 결론

원래 `jiyong` 작업 트리의 미커밋 파일을 덮어쓰지 않고 별도 안전
Worktree에서 Backend 작성자 Gate를 검증했다.

| 범위 | 작성자 결과 | 공식 완료 경계 |
| --- | --- | --- |
| T-005·T-016 기반 | Schema·Migration·Seed·HTTP·전체 회귀 PASS | 비작성자 QA·PM 판정 필요 |
| T-017B | Migration·Admin·Rollback·PostgreSQL PASS | 김은진 독립 QA 42건·WBS 완료 반영 |
| T-018 R1 조회 | 계약·Runtime·PostgreSQL PASS | 목록·상세만 해당, 쓰기 기능 미포함 |
| T-022 기존 Runtime | 생성·제출·취소와 Readiness PASS | 추가 누적 API 계약 공백 5개 |
| T-023 기존 Runtime | 기존 Action·Replay·409·이력 회귀 PASS | 신규 상담·방문·완료 Event 미구현 |
| W5-G05·T-028B 준비 | Mapping·비노출·Fail-closed Test PASS | 공동 확인·선행 Gate 전 Runtime 금지 |

작성자 검증 결과는 WBS의 `완료` 또는 독립 QA `APPROVE`와 같지 않다.

## 2. 검증 당시 Git 안전 경계

- 원래 `jiyong` checkout은 수정·미추적 파일이 있어 검증 중 Pull·Rebase하지 않았다.
- 2026-08-08 22:00 KST 기준 `origin/main`과 일치하는 별도 안전 Worktree를 사용했다.
- 검증 단계에서는 원래 checkout의 파일·Stage·Commit·원격 Branch를 변경하지 않았다.
- 검증 완료 뒤 지정된 코드·Test·문서만 `origin/jiyong` 검토 후보로 분리했다.
- 문서에는 Commit SHA를 식별 필수값으로 사용하지 않는다.

## 3. 순차 검증 결과

작은 Slice 검증 후 관련 회귀와 전체 회귀를 반복했다.

| 단계 | 결과 |
| --- | --- |
| T-005 Schema Validator | PASS, 역사 계약 32개 |
| T-005 Implementation Readiness | `READY`, blocker 0 |
| Django System Check | PASS |
| Migration Drift | `No changes detected` |
| 8/8 기반 전체 Backend | `838 passed, 13 skipped` |
| T-017B·T-018 관련 회귀 | `57 passed` |
| PostgreSQL Admin·T-018 R1 | `16 passed` |
| T-017B Migration 0004→0003→0004 | Rollback·재적용 PASS |
| T-022 Readiness 단위 Test | `35 passed` |
| T-023 기존 Action 관련 회귀 | `117 passed, 2 skipped` |
| HTTP·로그·후행 Gate 반영 후 전체 | `844 passed, 13 skipped` |
| AI·State·Evidence 관련 회귀 | `240 passed, 8 skipped` |
| 최종 전체 Backend | `850 passed, 13 skipped` |

최종 수치는 2026-08-09 업무계획표와 같은 작성자 실행 증거다.

## 4. PostgreSQL 증거 분리

| 시점·범위 | 결과 |
| --- | --- |
| 8/8 격리 DB 전체 Migration | PASS, 미적용 0 |
| 기본 Seed 5종 2회 | 2회차 비의도 신규 생성 0 |
| T-017B Rollback·재적용 | PASS |
| T-017B Admin·T-018 R1 | `16 passed` |
| T-016 실제 HTTP Slice | 격리 PostgreSQL PASS |
| AI Mapping·Evidence 준비 Slice | Docker 미실행으로 신규 PostgreSQL `NOT_RUN` |

AI Mapping·Evidence 준비는 Model·Migration·DB Runtime을 변경하지 않았다.
따라서 앞선 PostgreSQL PASS를 이 후속 Slice의 신규 PASS로 확대 기록하지
않는다.

## 5. T-022 추가 누적 Runtime Gate

다음 두 Operation은 OpenAPI-only 상태다.

- `PATCH /inquiries/{id}/questionnaire`
- `POST /inquiries/{id}/action-results`

Readiness가 탐지하는 계약 공백은 다음 다섯 개다.

1. Questionnaire Path ID의 UUID 미확정
2. Questionnaire `Idempotency-Key` 미선언
3. `answers`의 저장 가능한 Typed Schema 미확정
4. Action Result Path ID의 UUID 미확정
5. Action Result `Idempotency-Key` 미선언

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python .\backend\apps\inquiries\readiness.py `
  --require-deferred-runtime-contracts
```

현재 계약에서는 의도한 종료코드 `3`을 반환한다. 이는 기존 Runtime 장애가
아니라 후속 쓰기 Runtime 착수 차단을 뜻한다.

## 6. 유지한 차단선

| 차단 범위 | 해제 조건 |
| --- | --- |
| T-017C | 선행 T-017A/B 완료, 별도 구현·PostgreSQL·독립 QA 필요 |
| T-018 등록·수정·기본 선택 | 쓰기 계약·권한·멱등 정책 확정 |
| T-019~T-021 Runtime | 직전 선행 WBS 완료와 공개 계약 확정 |
| T-022 후속 쓰기 | 본 문서 5장의 계약 공백 해소 |
| T-023 신규 Event | Workflow 계약·역할·Guard 확정 |
| Backend–AI 공개 Dispatch | AI 담당자 공동 확인·실 환경 Gate |
| T-028B Runtime | W5-G04·T-028A·Evidence API 계약 완료 |

## 7. 재현 순서

후보 파일을 포함한 동일 checkout의 저장소 루트에서 실행하며 `.env`, Token,
DSN과 개인정보를 출력하지 않는다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python .\backend\manage.py check --settings=config.settings.test
& $python .\backend\manage.py makemigrations --check --dry-run `
  --settings=config.settings.test
& $python -m pytest .\backend\tests -q -p no:cacheprovider
```

PostgreSQL 검증은 개발 DB가 아닌 격리 DB에서 수행하고, 종료 뒤 Base DB와
pytest Test DB가 모두 제거됐는지 확인한다.

## 8. 관련 문서

- [Django Admin 합성계정 구현·검증 가이드](../인증_권한/Django_Admin_합성계정_구현_검증_가이드.md)
- [Django REST API 구독·제품조회 Runtime 구현·검증 가이드](../API/Django_REST_API_구독_제품조회_Runtime_구현_검증_가이드.md)
- [HTTP Smoke·로그 보안·후행 작업 차단 검증 보고서](../API/Django_REST_API_HTTP_Smoke_로그보안_후행작업_차단검증_보고서_20260809.md)
- [문의 AI 결과 저장·상태 전이·후속 API 검증 보고서](../API/Django_REST_API_문의_AI결과저장_상태전이_후속API_검증보고서_20260809.md)
- [AI 상태 이벤트·EvidenceCard 계약 준비 검증 보고서](../API/Django_REST_API_AI_상태이벤트_EvidenceCard_계약준비_검증보고서_20260809.md)

## 9. 다음 진행

1. 독립 QA 회신은 작성자 후보와 같은 범위인지 먼저 대조한다.
2. 승인되지 않은 Route·Model·Migration을 추측 추가하지 않는다.
3. 각 Gate가 열리면 한 Slice씩 구현하고 표적→PostgreSQL→전체 회귀 순으로
   다시 검증한다.

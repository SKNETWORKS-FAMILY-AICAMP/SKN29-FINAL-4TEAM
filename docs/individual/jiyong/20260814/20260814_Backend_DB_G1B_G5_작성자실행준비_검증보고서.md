# Backend·DB G1-B~G5 작성자 실행 준비·검증 보고서

## 1. 기준과 범위

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-08-14 KST |
| 작업자 | 최지용 — Backend·DB |
| 기준 SHA | `720573906c5cba166a7f8fb35c9ff17f359350ab` |
| Branch | `jiyong`, 작성 시 `origin/main`과 동일 |
| 현재 판정 | `BACKEND_DB_AUTHOR_READY / ACTUAL_AI_WAITING` |

이 작업은 이동윤의 AI Runtime·Provider·pgvector·Schema 작업을 변경하지 않는다. `ai/**`, `contracts/**`, State Machine, Migration, Seed 데이터, Mobile·Web Production도 수정하지 않았다.

## 2. 현재 실행환경 확인

| 항목 | 결과 |
| --- | --- |
| Backend `127.0.0.1:8000/health` | 200 |
| Web `127.0.0.1:5173` | 200 |
| AI `127.0.0.1:8001` | 미기동 |
| PostgreSQL | `127.0.0.1:5432` Local |
| Galaxy | `SM_X610`, ADB device |
| ADB reverse | `tcp:8000 → tcp:8000` |
| 설치 앱 | Customer·Technician 모두 확인 |
| Galaxy Local connected gate | `11 tests / 0 failures / 4 Remote expected skips` |

현재 Backend는 저장소의 `backend/.venv`와 `config.settings.local`로 실행 중이지만 로컬 `waterbridge`를 사용한다. 실제 공동 E2E는 김은진의 `waterbridge_team_integration` Process 환경에서 진행해야 한다.

## 3. G1 Readiness 재확인

실행:

```powershell
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\database\audit_backend_ai_g1b_readiness.py `
  --require-ready --require-team-database
```

결과: Exit 1, `BLOCKED`.

- DB identity가 `waterbridge_team_integration`이 아님
- `evidence.0011` 미적용
- Local `migrate --check` Exit 1이며 `visits.0005`도 미적용이다. `visits.0005`는 기존 결정대로 HOLD하고 임의 적용하지 않았다.
- Crosswalk `0/7`, Baseline Embedding `0/7`
- Page Link `0/8`, View `0/7`
- AI Readonly Default Readonly·View SELECT 미준비

이는 최지용 PC의 Local 환경 판정이며 과거 팀 QA READY를 취소하는 판정이 아니다. 실패 AIRun·멱등 원장 오염을 막기 위해 새 Inquiry는 만들지 않았다.

## 4. 새 읽기 전용 Inquiry 감사 명령

추가 파일:

- `backend/apps/inquiries/management/commands/audit_synthetic_e2e_inquiry.py`
- `backend/tests/unit/inquiries/test_synthetic_e2e_inquiry_audit.py`

명령은 DB를 변경하지 않고 공개 UUID 하나를 기준으로 다음만 JSON 출력한다.

- Inquiry 상태·버전·합성 소유자·배정·제품 코드
- AIRun 상태·Schema·Model Identity·Correlation
- Assessment·Guidance·검증된 내부 EvidenceLink 수
- Consultation 상태·확정·완료 정보
- 상태이력·Idempotency Operation·Correlation
- PII 원문·Secret 출력 여부는 항상 `false`

Gate별 사용:

```powershell
$py='.\backend\.venv\Scripts\python.exe'
& $py .\backend\manage.py audit_synthetic_e2e_inquiry `
  --inquiry-id <UUID> --expect-stage G1 --require-ready
& $py .\backend\manage.py audit_synthetic_e2e_inquiry `
  --inquiry-id <UUID> --expect-stage G3 --require-ready
& $py .\backend\manage.py audit_synthetic_e2e_inquiry `
  --inquiry-id <UUID> --expect-stage G4 --require-ready
& $py .\backend\manage.py audit_synthetic_e2e_inquiry `
  --inquiry-id <UUID> --expect-stage G5 --require-ready
```

## 5. 작성자 검증

| 검증 | 결과 |
| --- | --- |
| Django Check | 0 issue |
| `makemigrations --check --dry-run` | No changes |
| 신규 명령 Unit | 4 PASS |
| Backend G1·G3·G4 핵심 회귀 묶음 | 79 PASS / 1 PostgreSQL-only Skip |
| Galaxy `connectedDebugAndroidTest` | 11건 중 Local UI 7 PASS, Remote 4건은 실제 AI Inquiry 입력 전 의도적 Skip, 실패 0 |
| Local PostgreSQL 역사 Inquiry 관찰 실행 | BLOCKED JSON 정상, PII 원문 미출력 |
| `git diff --check` | PASS |

회귀 묶음은 Customer Guidance, Request Consultation, Synthetic Assignment, 상담사 상세 Projection, Consultation Start·Save·Confirm·Complete를 포함한다.

Galaxy 첫 실행에서 Android JUnit 메서드가 `Int`를 반환하던 표현식 본문과 과거 UI 태그·기대값 때문에 실패했다. Production Mobile은 변경하지 않고 아래 AndroidTest 두 파일만 현재 계약에 정렬한 뒤 전체 기기 테스트를 재실행했다.

- `mobile/customer-app/src/androidTest/java/com/skn29/watercare/customer/CustomerRemoteBackendSmokeTest.kt`
- `mobile/customer-app/src/androidTest/java/com/skn29/watercare/customer/CustomerMinimumFlowTest.kt`

Remote 4건의 Skip은 실패가 아니다. AI READY 뒤 `runRemoteSmoke=true`와 새 Inquiry UUID를 넣은 G1·G2·G3 실행에서는 반드시 Skip 0이어야 한다.

## 6. AI READY 후 최지용 실행 순서

1. 최종 SHA와 팀 DB Readiness Exit 0을 기록한다.
2. Galaxy G1 AndroidTest로 새 Inquiry를 하나만 생성·제출한다.
3. `CustomerG1SubmitSmoke`의 UUID로 G1 감사 명령을 실행한다.
4. G1 READY 뒤 `prepare_synthetic_e2e_assignment` Marker를 적용한다.
5. Galaxy G2·G3 AndroidTest 후 G3 감사 명령을 실행한다.
6. 동일 UUID로 Web 무수정 G4를 실행하고 G4 감사 명령을 실행한다.
7. Galaxy G5 재조회 뒤 G5 감사 명령을 실행한다.
8. 결과 JSON·Network·Logcat·Backend/AI Log를 김은진에게 한 묶음으로 전달한다.

## 7. 중단조건

- AI 8001 또는 G1 Readiness가 READY가 아님
- 다른 SHA·DB·Inquiry가 섞임
- Mock·Fake로 실제 AI를 대체해야 함
- 수동 DB UPDATE·DELETE·상태 Reset이 필요함
- G1 감사가 BLOCKED인데 Marker·G2·G3로 진행하려 함

이 경우 새 Inquiry를 반복 생성하지 않고 마지막 성공 Gate와 Blocker JSON만 공유한다.

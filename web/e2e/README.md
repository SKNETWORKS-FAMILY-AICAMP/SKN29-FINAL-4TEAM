# Web Playwright E2E

상담사 Web의 실제 Backend 상담 처리 구간만 검증합니다. Mobile→AI 전체 흐름이
아니므로 Backend Fixture의 `g3_audit_result=NOT_APPLICABLE`이 정상입니다.

## 실행 전 조건

- 최신 `main` 기준 Backend가 실행 중이어야 합니다.
- 로컬 PostgreSQL은 `operations.0002` 적용, `visits.0005` 미적용 HOLD 상태여야
  합니다.
- Demo 계정·제품·구독 Seed가 준비돼 있어야 합니다.
- 실제 고객 DB, 공용 DB, RDS에서는 실행하지 않습니다.

Playwright의 `globalSetup`이 실행마다 새로운 `run_id`를 만들고 다음 Backend 명령의
공개 JSON만 읽습니다.

자동 생성은 Backend·Web 주소와 PostgreSQL Host가 모두 로컬 주소일 때만
허용됩니다. 원격·공용 DB로 판단되면 문의를 만들기 전에 즉시 중단합니다.

```powershell
python manage.py create_web_consultation_e2e_fixture `
  --run-id "web-e2e-<build>-<attempt>" --json
```

이미 Backend가 JSON 파일을 만들었다면 `E2E_FIXTURE_JSON_PATH`로 경로만 전달할 수
있습니다. 이 모드는 로컬 관리 명령과 로컬 Migration 검사를 실행하지 않습니다.
JSON 문자열, Token, 비밀번호는 환경변수나 로그에 넣지 않습니다.

## 실행

```powershell
Set-Location .\web
npm run test:e2e:install
npm run test:e2e
```

기본 정책은 `workers=1`, `retries=0`입니다. 정상 흐름은 로그인 → 상담 시작 → 상담
내용 저장 → AI 요약 확정 → 상담 완료 → `COMPLETION_PENDING` → 새로고침 후 기록
유지입니다. 미존재 문의 404와 오래된 `state_version` 409도 함께 검증합니다.

현재 Backend Fixture에는 비배정 문의 ID가 없으므로, 비배정 404까지 실행하려면
Backend·QA가 제공한 합성 ID를 `E2E_UNASSIGNED_INQUIRY_ID`로 전달해야 합니다.
값이 없으면 나머지 상담 흐름을 검증한 뒤 전체 E2E 결과를 실패로 처리합니다.

## 실패 결과물

실패 결과는 `web/.runtime/playwright/test-results/`에 저장됩니다.

- Screenshot: 민감 영역을 Mask한 뒤 저장
- Video: 테스트 시작 전 민감 영역을 흐림 처리
- Trace: Network와 Resource를 제거하고 Token·이메일·전화번호를 정제한 뒤 저장

정제에 실패하면 안전하지 않은 원본을 삭제하고 테스트를 실패 처리합니다.

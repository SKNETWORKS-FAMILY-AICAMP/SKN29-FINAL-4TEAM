# Web Playwright E2E

상담사 Web과 실제 Backend를 Chromium으로 연결해 E11 Browser User E2E를 검증합니다.
Mobile→AI 전체 흐름은 범위가 아니므로 상담 Fixture의
`g3_audit_result=NOT_APPLICABLE`은 정상입니다.

검증 범위는 다음 네 가지입니다.

- E11-01: 로그인부터 상담 시작·저장·요약 확정·상담 완료까지의 정상 흐름
- E11-02: 오래된 `state_version` 요청의 409 충돌 경계
- E11-03: 타 상담사 배정 문의와 미존재 문의의 404 접근 경계
- E11-04: 방문 전환 후 Dashboard의 실제 합성 기사를 선택해 일정 저장

Product React UI, Backend 상담·방문 업무 로직, 인증을 Patch하거나 Mock하지 않습니다.

## 실행 전 조건

- Backend는 `http://127.0.0.1:8000` 등 Loopback 주소에서 실행합니다.
- Web도 Loopback 주소에서 실행하며 기본 Playwright Web 주소는
  `http://127.0.0.1:4173`입니다.
- PostgreSQL은 실제 고객·공용·RDS가 아닌 E2E 전용 로컬 격리 DB를 사용합니다.
- Migration은 `operations.0002_consultant_dashboard_projection` 적용,
  `visits.0005_replace_visit_result_assignment_fk` 미적용 `P1_HOLD`, 예상 외 미적용
  0건이어야 합니다.
- Demo 계정·제품·구독 합성 Seed가 준비돼 있어야 합니다.
- Chromium이 설치돼 있어야 합니다. 최초 한 번 `npm run test:e2e:install`을
  실행합니다.

로컬 자동 Fixture 모드에서는 `globalSetup`이 Migration Gate 통과 후 공식
`seed_consultant_dashboard` 명령을 멱등 실행합니다. 이 Seed가 제공한 Dashboard
기사 목록에서 E11-04의 방문기사를 선택하므로 기사 ID를 테스트에 하드코딩하지
않습니다.

## 상담사 비밀번호

비밀번호는 소스·Fixture·명령 인자·로그에 넣지 않고 Playwright 실행 프로세스의
`E2E_CONSULTANT_PASSWORD` 환경변수로만 전달합니다. 로컬 자동 Fixture 모드에서 이
환경변수가 제공되면 `globalSetup`이 DEBUG 로컬 합성 계정 전용 공식 명령
`set_synthetic_consultant_password`를 호출합니다. 명령에는 비밀번호 값이 아니라
환경변수 이름만 전달됩니다.

```powershell
$secureE2ePassword = Read-Host "합성 상담사 비밀번호" -AsSecureString
$e2eCredential = [System.Management.Automation.PSCredential]::new(
  "fixture-consultant",
  $secureE2ePassword
)
$env:E2E_CONSULTANT_PASSWORD = $e2eCredential.GetNetworkCredential().Password
```

실행 후에는 비밀번호 환경변수를 제거합니다.

```powershell
Remove-Item Env:E2E_CONSULTANT_PASSWORD -ErrorAction SilentlyContinue
```

## 로컬 자동 Fixture 모드

`globalSetup`은 매 실행마다 서로 다른 세 `run_id`를 만들고 다음 공식 Backend 관리
명령의 공개 JSON만 읽습니다.

```powershell
python manage.py create_web_consultation_e2e_fixture `
  --run-id "<primary-run-id>" --json

python manage.py create_web_consultation_e2e_fixture `
  --run-id "<visit-run-id>" --json

python manage.py create_web_concealed_e2e_fixture `
  --run-id "<concealed-run-id>" --json
```

첫 Fixture는 E11-01~03의 정상 상담·충돌 경계, 두 번째 Fixture는 E11-04 방문 흐름에
사용합니다. 세 번째 Fixture는 다른 합성 상담사에게 배정된 문의를 만들어 E11-03의
접근 경계를 검증합니다. 각 명령은 같은 미소비 `run_id`로 재실행해 멱등성과 동일 ID
반환을 확인합니다.

Runtime 파일에는 공개 Crosswalk만 기록합니다. Concealed Runtime 파일에는
`inquiry_id` 하나만 저장하며 Token, Cookie, 비밀번호, 고객 개인정보를 저장하지
않습니다.

자동 실행의 Vite 환경은 다음처럼 고정됩니다.

- `VITE_USE_MOCK_API=false`
- `VITE_MOCK_AUTHENTICATED=false`
- `VITE_ENABLE_DESIGN_MOCK_FALLBACK=false`
- Backend Proxy는 `E2E_BACKEND_BASE_URL` 또는 기본 Loopback Backend

## 외부 Fixture 모드

Backend가 공식 관리 명령으로 공개 JSON 파일을 미리 만들었다면 다음 세 경로를 모두
제공해야 합니다. 일부만 제공하면 시작 전에 실패합니다.

```powershell
$env:E2E_FIXTURE_JSON_PATH = '<primary-public-fixture.json>'
$env:E2E_VISIT_FIXTURE_JSON_PATH = '<visit-public-fixture.json>'
$env:E2E_CONCEALED_FIXTURE_JSON_PATH = '<concealed-public-fixture.json>'
```

외부 모드에서는 로컬 Seed·비밀번호 설정·Migration 명령을 실행하지 않습니다. 모든
모드에서 Backend·Web·PostgreSQL Loopback 검사는 유지됩니다. 세 파일은 서로 다른
합성 문의여야 하고, 공식 공개 필드 계약·크기 제한·민감정보 차단 검사를 통과해야
합니다. 실제 고객 데이터나 원격 운영 Backend에는 사용하지 않습니다.

## 실행

```powershell
Set-Location .\web
npm run typecheck:e2e
npm run test:e2e -- `
  e2e/specs/consultation-workflow.spec.ts `
  e2e/specs/technician-selection.spec.ts
```

기본 정책은 Chromium, `workers=1`, `retries=0`입니다. 정상 상담 Fixture는 한 번
소비되므로 성공한 실행에 같은 `run_id`를 재사용하지 않습니다.

## 결과물 보안

실패 결과는 `web/.runtime/playwright/test-results/`에 저장됩니다.

- Screenshot: 입력·민감 영역을 Mask한 뒤 저장
- Video: 테스트 시작 전 민감 영역을 흐림 처리
- Trace: Network와 Resource를 제거하고 Token·이메일·전화번호를 정제한 뒤 저장

정제에 실패하면 안전하지 않은 원본을 삭제하고 테스트를 실패 처리합니다. Fixture
JSON 문자열, Token, Cookie, 비밀번호는 환경변수 출력이나 CI 로그에 남기지 않습니다.

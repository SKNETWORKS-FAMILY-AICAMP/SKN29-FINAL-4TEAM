# Web Playwright G4 한예나 PC 격리 Docker Bootstrap 구현·검증

- 작성일: 2026-08-23
- 담당: 최지용(Backend·DB)
- 최초 구현 기준: `main@46c2eeab`
- 대상: 한예나 PC의 합성 데이터 전용 Web G4 로컬 실행

## 1. 결론

기존 r3·r4 자료는 과거 실행 증거이고 최신 PC 환경을 생성하는 Bootstrap은
아니다. 최신 Web G4는 정상 상담·방문 Fixture를 자동 생성하지만, 타 상담사
배정 문의의 404 권한 경계 ID는 Backend·QA가 별도로 제공하도록 되어 있었다.

이에 Web 코드는 변경하지 않고 다음 Backend·DB 도구만 추가했다.

- `bootstrap_web_g4_local.ps1`: 새 격리 PostgreSQL·Migration·Seed 준비
- `create_web_concealed_e2e_fixture`: 타 상담사 배정 404 Fixture 생성
- 단위 테스트: 실제 상담사별 목록·상세·상담 시작 접근 경계 검증

## 2. 안전 경계

- 기본 실행은 Plan이며 `-Apply`가 없으면 DB·Docker를 변경하지 않는다.
- Apply는 clean 최신 main과 정확한 `origin/main` 일치에서만 허용한다.
- 전용 Container·Volume만 사용한다.
  - Container: `waterbridge-web-g4-local-postgres`
  - Volume: `waterbridge-web-g4-local-postgres-data`
  - Port: `127.0.0.1:55444`
- 기존 Volume을 자동 삭제·초기화·재사용하지 않는다.
- 일반 `manage.py migrate`를 사용하지 않고 승인 Allowlist만 적용한다.
- `visits.0005`는 계속 미적용 HOLD다.
- RDS·팀 공용 DB·기존 G0~G6 증거에는 접근하지 않는다.
- Secret은 `.runtime/web-g4-local/**`에만 저장되고 Git에서 제외된다.
- 종료 시 PostgreSQL만 중지하며 `down -v`를 실행하지 않는다.

## 3. Bootstrap 처리 순서

1. Docker CLI·Compose와 Git 기준 확인
2. 보호 Runtime 환경파일 생성
3. 전용 pgvector PostgreSQL Container·Volume 기동
4. Admin Provision
5. Migrator Allowlist Plan·Apply
6. Migration 후 Admin 재Provision
7. Demo 계정·제품·구독·Dashboard Seed
8. 타 상담사 배정 404 Fixture 생성
9. Migration 재검사와 공개 상태 JSON 저장

공개 결과는 다음 경로에 기록된다.

```text
.runtime/web-g4-local/evidence/web-g4-concealed-fixture.json
.runtime/web-g4-local/evidence/web-g4-bootstrap-status.json
```

## 4. 404 Fixture 계약

- 로그인 상담사: `DEMO-CONSULTANT-001`
- 실제 배정 상담사: `SYN-WEB-G4-CONSULTANT-404`
- 문의 상태: `CONSULTATION_REQUIRED`
- 현재 배정 상담사 권한: `START_CONSULTATION`
- Demo 상담사의 상세·상담 시작 기대값: `404 RESOURCE_NOT_FOUND`
- 동일 미소비 `run_id`: 같은 문의를 재조회
- 소비된 `run_id`: 이력을 되돌리지 않고 실패

이 Fixture는 랜덤 미존재 UUID가 아니라 DB에 실제 존재하고 다른 상담사에게
배정된 합성 문의다. 따라서 존재 여부와 소유권 은닉을 함께 검증한다.

## 5. G2·G3 및 기존 G6 영향

이 Web G4 Fixture는 Mobile→AI 문의가 아니라 Web 상담 처리 전용 합성
Fixture다. 따라서 `g2_g3=NOT_APPLICABLE_FOR_WEB_G4`가 맞으며 G2·G3 PASS를
새 로컬 DB의 선행조건으로 만들지 않는다.

전용 Volume과 신규 `run_id`만 사용하므로 기존 G2~G6 실행 증거를 수정하거나
대체하지 않는다. 새 결과는 최신 main Web G4 회귀 증거로 별도 보관한다.

## 6. 검증 결과

| 검증 | 결과 |
|---|---|
| PowerShell 7 Parser | PASS |
| Windows PowerShell 5.1 Parser | PASS |
| Windows PowerShell 5.1 Plan 무변경 실행 | PASS |
| Windows PowerShell 5.1 신규 Volume Bootstrap | PASS |
| Bootstrap 계약·Web Fixture 표적 테스트 | `23 passed` |
| Demo 상담사 상세·상담 시작 404 | PASS |
| 실제 배정 상담사 상세 조회 200 | PASS |
| 동일 `run_id` 멱등성 | PASS |
| 잘못된 `run_id`·의존 Seed 누락 차단 | PASS |
| 신규 전용 Docker Bootstrap | Windows PowerShell 5.1 PASS |
| 승인 Migration | `91/91`, 예상 밖 적용 0건 |
| `visits.0005` | `NOT_APPLIED_P1_HOLD` |
| Bootstrap 명시적 재사용 | Windows PowerShell 5.1 PASS, 초기화 0건 |
| Backend `/health` | HTTP 200 |
| Web E2E TypeScript | PASS |
| Chromium Playwright | `2 passed` |

위 Docker·Browser 검증은 전용 이름의 신규 합성 Volume에서 수행했다. 첫 실행과
`-ReuseLocalRuntime` 재실행 모두 통과했고 기존 팀 DB·RDS에는 접근하지 않았다.
한예나 PC에서는 Docker Desktop 준비 후 인계 가이드와 최신 main으로 독립
재실행하며, 그 결과를 담당자 PC Runtime 증거로 별도 남긴다.

## 7. Windows PowerShell 신규 Volume 호환성 보완

한예나 PC의 Windows PowerShell 5.1에서 신규 Volume 미존재 확인이
`NativeCommandError`로 중단되는 문제가 확인됐다. 원인은 전역
`$ErrorActionPreference = 'Stop'` 상태에서 `docker volume inspect`가 출력한
정상적인 `no such volume` 메시지가 종료 오류로 승격된 것이다.

신규 Volume이 없는 것은 첫 Bootstrap의 정상 조건이므로 존재 확인을
`docker volume ls --quiet`의 정상 종료 결과에서 정확한 이름을 찾는 방식으로
교체했다. Docker 목록 조회 자체가 실패할 때만 중단하며 다음 안전 경계는
그대로 유지한다.

- Runtime과 Volume이 모두 없으면 새 격리 환경 생성
- Runtime만 있거나 Volume만 있으면 자동 복구·삭제 없이 중단
- 둘 다 있으면 `-ReuseLocalRuntime` 명시 시에만 재사용
- 기존 Volume 삭제·초기화·이름 추정 금지

회귀 방지를 위해 `test_web_g4_local_bootstrap_contract.py`에 Windows PowerShell
호환 Volume 조회 계약과 금지 명령 검사를 추가했다.

호환성 보완본은 Windows PowerShell 5.1에서 Volume이 없는 첫 실행과 전용
Volume이 있는 명시적 재실행을 모두 실제 수행했다. 첫 실행은 전용 Container와
Volume을 새로 만들었고, 재실행은 같은 `run_id` Fixture를 초기화하지 않고
재조회했다. 이어서 Backend Health 200과 Chromium G4 2건까지 통과했다.

따라서 기존 `main@46c2eeab`에서 Runtime 생성 전에 멈춘 결과는 한예나의 실행
순서 오류가 아니다. 호환성 보완이 병합된 최신 main을 받은 뒤 기존 실패 환경을
삭제하지 않고 첫 Apply 명령을 그대로 다시 실행하면 된다.

## 8. 담당자 인계

한예나는 Backend·Migration·Seed·Fixture 코드를 수정하지 않고 제공된 Bootstrap을
실행한다. 실패 시 Volume 삭제나 일반 Migration을 시도하지 말고, 비밀값을
제외한 오류 단계와 메시지만 Backend 담당자에게 전달한다.

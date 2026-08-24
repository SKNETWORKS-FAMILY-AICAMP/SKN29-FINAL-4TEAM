# Web Playwright G4 실행 환경 준비 요청

- 작성일: 2026-08-23
- 요청자: 한예나(Web)
- 수신: Backend·DB 담당자
- 실행 기준: 최신 `main@3eeb51ab`

## 한 줄 요약

최신 main에서 Web Playwright G4를 실행할 수 있도록 격리 PostgreSQL·Backend 상태와 404 검증용 합성 문의를 확인해 주세요.

## 현재 상태

- Web Playwright·Chromium과 Backend Python 환경은 준비돼 있습니다.
- 현재 PowerShell에서는 `docker` 명령이 인식되지 않습니다.
- `team-integration` Runtime 환경파일과 기존 PostgreSQL Volume 상태를 확인하지 못했습니다.
- DB·Migration·Seed·Volume은 변경하지 않았습니다.

## 요청 사항

1. 기존 `waterbridge-team-integration-postgres-data` Volume 존재 여부와 Docker 실행 방법을 확인해 주세요.
2. 기존 Volume과 연결할 수 있는 Runtime 환경파일의 준비·복구 방법을 알려주세요.
3. 아래 DB 준비 상태를 확인해 주세요.
   - 최신 승인 Migration 전체 적용
   - `visits.0005`만 미적용 HOLD 유지
   - 예상 밖 Pending·Applied Migration 0건
   - Demo 계정·제품·구독 Seed 준비
4. 같은 SHA·DB 환경에서 G2·G3가 완료됐는지 알려주세요.
5. Backend `/health` HTTP 200과 비밀정보를 제외한 로컬 Base URL을 전달해 주세요.
6. 같은 격리 DB에 있는 타 상담사 배정 404 검증용 합성 `inquiry_id`를 전달해 주세요.

정상 상담용·방문용 Fixture는 Web Playwright가 서로 다른 신규 `run_id`로 자동 생성하므로 미리 만들 필요는 없습니다.

## 준비 완료 후 Web에서 진행할 작업

- 상담용·방문용 신규 `run_id` 생성
- 신규 합성 Inquiry 2건 자동 생성
- Mock을 끄고 `workers=1`, `retries=0`으로 G4 실행
- 상담 시작 → 저장 → 요약 확정 → 완료 → 새로고침 복구와 404·409 확인
- Screenshot·Trace와 실행 결과 정리

## 안전 조건

- 기존 완료 Inquiry, 공용 DB, RDS를 재사용하지 않습니다.
- DB Reset, 일반 `migrate`, 임의 Seed, Volume 초기화를 하지 않습니다.
- Password·Token·DSN 등 민감정보는 문서나 채팅에 기록하지 않습니다.
- 준비가 불가능하면 변경을 시도하지 말고 오류 내용만 전달해 주세요.

## 회신 요청 형식

```text
execution_sha=<SHA>
docker_cli=READY/BLOCKED
postgres_volume=EXISTS/MISSING/BLOCKED
runtime_env=READY/BLOCKED
migration_gate=READY/BLOCKED
visits_0005=NOT_APPLIED_P1_HOLD/BLOCKED
demo_seed=READY/BLOCKED
g2_g3=PASS/BLOCKED
backend_health=200/BLOCKED
backend_base_url=<민감정보 없는 로컬 URL>
unassigned_inquiry=READY/BLOCKED
blocker=NONE/<오류 요약>
```

# 4주차 Web API 연동 상태표

## 한 줄 결론

2026-08-04 현재 상담사 업무 화면은 `MOCK_ONLY`다. Web 재검토 회신은 완료했지만 PM `FINAL_APPROVED`와 Active OpenAPI가 없어 실제 API 연결은 `BACKEND_BLOCKED / IMPLEMENTATION_HOLD`다.

## 2026-08-04 검토 상태

| 결정 | Web 회신 | 구현 상태 |
| --- | --- | --- |
| DEC-WEB-BE-001 P0 실제 연결 범위 | `REVIEWED` | 승인·계약 대기 |
| DEC-WEB-BE-004 방문 Action 수정안 | `REVIEWED` | 승인·계약 대기 |
| DEC-WEB-BE-009 재로그인·Draft 복구 | `REVIEWED` | 승인 대기 |

회신 파일은 [20260804 Web 재검토 회신](./handoffs/20260804_한예나_DEC-WEB-BE-001_004_009_Web_회신_v0.1.md)이다. 구현 준비는 [실제 API 구현 준비표](./week4-web-implementation-readiness.md), 오류·검증 준비는 [계약 테스트 계획](./week4-web-contract-test-plan.md)을 따른다.

## 기능별 상태

| 기능 | 계약·호출 상태 | Web 처리 | 다음 담당 |
| --- | --- | --- | --- |
| Demo 로그인·토큰 갱신·로그아웃·현재 사용자 | API Client 구현 | Mock/API 모드 분리 | Backend와 실제 E2E 확인 |
| Backend 상태 확인 | `/health` 호출 구현 | 연결 상태만 표시 | Backend 실행 환경 확인 |
| 상담사 문의 목록 | 제안 검토 완료, Active 계약 없음 | Mock Repository 사용 | PM 승인·Active URL·Query·DTO 제공 |
| 상담사 문의 상세 | 제안 검토 완료, Active 계약 없음 | Mock Repository 사용 | PM 승인·상세 Section·오류 계약 제공 |
| 상담 시작·저장·완료 | `consultations.yaml = {}` | 계약형 Mock으로 403·409·422 검증 | PM 승인·행동별 Active 계약 확정 |
| 방문 요청·일정 저장 | `visits.yaml = {}` | Mock 저장 | PM 승인·방문·기사·일정 Active 계약 제공 |
| 운영 대시보드 | `operations.yaml = {}` | 합성 Mock 집계 | 상담사 P0 이후 협의 |

`inquiries.yaml`의 현재 Endpoint는 고객 문의 생성·문진·자가조치·제출용이다. 상담사용 목록·상세 주소로 추측해서 사용하지 않는다.

## 실제 연동에 반드시 필요한 값

### 목록·상세

- URL과 HTTP Method
- 검색·상태·위험도·우선순위·기간·정렬·페이지 Query
- 공개 문의 ID, 상태, 위험도, 우선순위, 담당자, 대기 시간
- `state_version`, `allowed_actions`
- 401·403·404·422·5xx·부분 실패 응답
- 개인정보 마스킹과 Evidence 공개 필드

### 상담 저장

- 상담 시작·초안 저장·완료·방문 검토별 URL과 Payload
- `state_version`, `Idempotency-Key`, `X-Correlation-ID`
- 성공 후 최신 상태와 `allowed_actions`
- 409 상태 충돌과 멱등 키 충돌의 공식 Error Code

### 방문 저장

- 기사 후보 조회, 방문 요청, 일정 수정·확정 URL
- 희망일과 확정일의 필드 구분
- 성공 후 문의·방문 상태와 `allowed_actions`

## Web 원칙

1. 실제 Endpoint를 임의로 만들지 않는다.
2. 실제 API와 Mock은 Repository·Adapter 경계에서 분리한다.
3. 실제 응답의 상태·위험도·우선순위·담당자·허용 행동을 Web이 다시 계산하지 않는다.
4. Mock 성공을 실제 Backend 저장 성공으로 기록하지 않는다.

# Web·Mobile API 소비 확인 가이드

> 관련 업무: Backend Public API 소비
> 원칙: Mock 화면과 실제 Backend 연결을 구분한다.

## 1. 역할 경계

| 담당 | 책임 |
| --- | --- |
| Backend | Method·Path·DTO·오류·권한·DB 저장 |
| Web | 상담사 Remote Adapter·UI 상태 |
| Mobile | 고객·기사 Remote Adapter·UI 상태 |
| QA | 같은 환경에서 독립 재현 |

Frontend가 Backend 응답을 추측하거나 DB에 직접 연결하지 않는다.

## 2. 연동 전 Backend 전달 정보

- 접근 가능한 `BACKEND_BASE_URL`
- PostgreSQL·Migration 준비 상태
- 지원 Method·Path·operationId
- 합성 Account·Product·Subscription 공개 식별자
- 정상·403·404·409·422 Example
- 현재 Blocker와 Mock 허용 범위

Secret·Password·JWT 원문은 전달하지 않는다.

## 3. 데이터 소스 상태

| 상태 | 의미 |
| --- | --- |
| `MOCK` | 화면 개발용 데이터 |
| `BACKEND_BLOCKED` | 계약 또는 Runtime 미제공 |
| `REMOTE` | 실제 Backend HTTP 소비 |
| `PRE_SMOKE` | 개발자 사전 연결 확인 |
| `E2E_PASS` | 같은 환경·같은 데이터 흐름 재현 |

Mock 성공을 Remote 또는 E2E 완료로 표시하지 않는다.

## 4. 소비 순서

1. Health·Login
2. 구독·제품 조회
3. 문의 생성·상세
4. 증상·추가문진·상담 요청
5. AI Guidance 조회
6. 상담사 목록·상세·상담 Write
7. 방문 일정·기사 흐름

각 Slice가 준비될 때 관련 소비자만 확인한다. 모든 담당자의 ACK를 한 번에
받는 직렬 인계를 만들지 않는다.

## 5. DTO·오류 경계

- 공개 UUID만 사용
- Enum·Null·Date-only 규칙 준수
- `state_version`과 `allowed_actions`를 UI 상태에 반영
- 409는 최신 Snapshot으로 복구
- 403·404를 동일한 빈 화면으로 숨기지 않음
- PII·내부 AI Trace·DB 필드 비노출

## 6. 최종 Smoke

Backend 수정이 병합된 최종 기준에서 Mock을 끄고 실제 합성 계정으로 실행한다.
Frontend Build 성공만으로 DB 저장이나 상태 전이를 증명하지 않는다.

## 7. 판정

Web·Mobile의 소비 완료는 각 담당자가 확인한다. Backend 문서는 API 제공 상태만
기록하며 타 담당자의 구현 완료를 대신 선언하지 않는다.

# 4주차 Web 실제·Mock 계약 테스트 계획

기준일: 2026-08-04
현재 상태: `TEST_PLAN_READY / IMPLEMENTATION_HOLD`

## 테스트 분리 원칙

| 구분 | 목적 | 증거 이름 원칙 |
| --- | --- | --- |
| Mock UI | 화면·입력·Fallback 회귀 | Suite와 결과에 `Mock` 명시 |
| Contract | 승인된 DTO·Mapper·오류 Schema 검증 | Suite에 `Contract` 명시 |
| Remote Integration | Backend Runtime·DB 저장 확인 | Suite와 캡처에 `Actual API` 명시 |

Mock 성공을 실제 API 성공으로 기록하지 않는다. Remote Integration은 Active OpenAPI·Backend Runtime·Demo DB가 준비된 뒤 실행한다.

## 목록·상세 테스트

- 목록 Loading·Empty·검색 결과 없음
- Query·Pagination·정렬과 URL 복귀 상태
- 401·403·5xx·Network 오류
- 상세 404와 권한 없는 403 구분
- 기본 상세 성공과 AI·Evidence·Timeline 부분 실패 분리
- `snake_case`·소문자 Enum Mapper
- Backend가 제공한 위험도·우선순위·담당자·`allowed_actions`를 그대로 소비
- DEC-008 보류·Evidence 오류에서도 기본 상세·상담 영역 유지

## 상담 Action 테스트

- 허용된 4 Action만 버튼으로 표시
- 중복 클릭 방지
- 같은 네트워크 재시도에서 같은 멱등 키 유지
- 새 사용자 행동·변경 Payload에서 새 멱등 키 생성
- 성공 Snapshot 반영 뒤 상세 재조회
- 422 필드 오류를 입력 항목에 연결
- 403·404·409·422·5xx·Network 오류 구분
- AI 원본·수정본·확정본 분리와 확정 뒤 잠금

## 409 테스트

| Error 종류 | 기대 Web 행동 |
| --- | --- |
| `STATE_VERSION_CONFLICT` | 입력 보존, 최신 Snapshot 반영, 자동 재제출 금지 |
| `IDEMPOTENCY_KEY_REUSE_CONFLICT` | 최신 상태로 오해하지 않고 새 요청 안내 |
| 성공 Replay | `idempotent_replay`를 표시하되 중복 성공 Effect 금지 |
| 알 수 없는 Action Code | 화면을 종료하지 않고 안전한 안내·상세 재조회 제공 |

## 방문 테스트

- `visit: null`과 계약상 Key 누락 구분
- `preferred_date`와 `confirmed_date` 분리
- `ASSIGNING` 미배정 표시
- `SCHEDULING` 기사 필수 검증
- `CONFIRMED` 기사·확정일 필수 검증
- 방문 필요·불필요 분기와 `allowed_actions` 버튼 제어
- 일정 저장 409 후 입력 보존과 최신 Visit Snapshot 반영
- 실제 자동 배정·예약·알림처럼 표현하지 않음

## 재로그인·Draft 테스트

- 최종 401과 명시적 로그아웃 구분
- 안전한 내부 `returnTo`만 허용
- 동일 사용자·동일 역할·동일 문의·15분 이내만 복구
- 최신 상세 GET 뒤 `state_version`이 같을 때만 입력 복구
- 상태 충돌 시 자동 복구·제출 금지
- 다른 사용자·역할, 로그아웃, 저장·취소, 권한 상실, TTL 만료 시 폐기
- 새로고침·탭 종료 뒤 복구되지 않음을 안내
- Token·Draft가 URL·Router State·Web Storage에 남지 않음

## 실행 명령

승인 전 현재 Mock 회귀 기준:

```powershell
npm.cmd test -- --run
npm.cmd run lint
npm.cmd run build
```

승인 후에는 실제 API용 별도 Suite와 실행 명령을 추가하고, Backend URL·계정·비밀값은 공개 문서에 기록하지 않는다.

## 완료 증거 체크리스트

- [ ] 실행 Commit SHA
- [ ] Node.js·npm Version
- [ ] Mock Test File·Case 수
- [ ] Contract Test File·Case 수
- [ ] Actual API 성공 Endpoint 수
- [ ] 목록·상세 Network 캡처
- [ ] 상담 저장 뒤 DB·상세 재조회 증거
- [ ] 방문 저장 뒤 최신 Visit Snapshot
- [ ] 409 입력 보존 화면과 Backend `correlation_id`
- [ ] 미완료·차단 기능 목록

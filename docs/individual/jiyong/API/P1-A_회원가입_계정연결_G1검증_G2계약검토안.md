# P1-A 회원가입·계정연결 G1 검증 및 G2 계약 검토안

> 작성일: 2026-08-24 KST
>
> 작성자: 최지용 (Backend·DB)
>
> 기준 소스: `origin/main@2df06b2091b1c32f73dfac8162abf9586dd1a496`
> 판정: `G1_CANDIDATE_PASS / G2_REVIEW_READY / G3_NOT_STARTED`

## 1. 이 문서의 목적

P1-A는 실제 고객이 아닌 합성 계약고객 한 명으로 회원가입·계정연결 흐름을 만드는 후속 기능이다.
이번 작업은 합성 Candidate가 안전한지 확인하고, 구현 전에 Mobile·PM이 검토할 API 계약안을 준비한 범위다.

아직 다음 항목은 완료되지 않았다.

- Candidate의 Backend DB 적재
- 회원가입 모델·Migration
- OTP 발송·검증 Runtime
- `User`·`CustomerAccountLink` 생성
- 로그인·계정 복구·마이페이지 수직 E2E

## 2. PM 승인 경계

승인된 최소 흐름은 다음과 같다.

```text
합성 계약고객 확인
→ 계약 이메일 OTP
→ 단회성 claim_ticket
→ WaterBridge ID/PW 생성
→ CustomerAccountLink
→ JWT·일반 로그인
→ 아이디 찾기·비밀번호 재설정
→ 마이페이지·기존 문의 진입
```

P1-B 카카오 로그인, 실제 고객 원장·개인정보, 중복 이메일 자동 연결은 포함하지 않는다.

## 3. G1 Candidate 검증 결과

대상 파일:

- `data/synthetic/candidates/p1_account_link_candidates.json`
- `data/schemas/p1-account-link-candidates.schema.json`

확인 결과:

| 확인 항목 | 결과 |
|---|---|
| Candidate 수 | 1건 |
| 실제 개인정보·Secret | 0건 |
| 계약 이메일 | `.invalid` 합성 주소 |
| 제품 | `WPUJAC104DWH` |
| 계약·구독 | 활성 상태 |
| 기존 `User` | `ABSENT` |
| 기존 `CustomerAccountLink` | `ABSENT` |
| Backend Import 상태 | `NOT_IMPORTED` 유지 |
| Runtime 검증 상태 | `NOT_VERIFIED` 유지 |

검증 수치:

- P1-A 표적 테스트: `7 passed`
- Data 전체 단위 테스트: `114 passed`
- Data QA: `60 files / 990 records / errors 0 / warnings 0`
- 결정적 재생성: `PASS`, 변경 파일 0건

따라서 G1은 **Candidate 데이터 수준에서만 PASS**다. Backend DB 적재와 PostgreSQL 검증은 G3 이후 범위다.

## 4. G2 API 계약 검토안

아래 경로는 검토안이며 양정현(Mobile) 검토와 윤승혁(PM) 승인 전까지 `CONFIRMED`가 아니다.

| 순서 | Method·Path 제안 | 목적 | 인증 |
|---|---|---|---|
| 1 | `POST /api/v1/auth/contract-verification/challenges` | 계약번호·고객번호로 합성 계약 후보 확인, OTP Challenge 생성 | 없음 |
| 2 | `POST /api/v1/auth/contract-verification/challenges/{challenge_id}/verify` | OTP 검증 후 단회성 `claim_ticket` 발급 | 없음 |
| 3 | `POST /api/v1/auth/signup` | ID/PW 생성과 계약고객 연결 | `claim_ticket` |
| 4 | `POST /api/v1/auth/login` | 일반 ID/PW 로그인과 JWT 발급 | 없음 |
| 5 | `POST /api/v1/auth/account-recovery/username/challenges` | 아이디 찾기 OTP Challenge 생성 | 없음 |
| 6 | `POST /api/v1/auth/account-recovery/username/verify` | 마스킹된 로그인 ID 확인 | 없음 |
| 7 | `POST /api/v1/auth/password-reset/challenges` | 비밀번호 재설정 OTP Challenge 생성 | 없음 |
| 8 | `POST /api/v1/auth/password-reset/verify` | 단회성 `reset_ticket` 발급 | 없음 |
| 9 | `POST /api/v1/auth/password-reset/confirm` | 비밀번호 변경·`auth_version` 증가 | `reset_ticket` |
| 10 | `GET /api/v1/me` | 로그인 사용자·안전한 고객 Projection | Bearer JWT |

## 5. 공통 요청·응답 원칙

- 모든 응답은 기존 `ApiResponse` Envelope와 `X-Correlation-ID`를 사용한다.
- 전체 이메일·계약번호·고객번호를 응답하지 않는다.
- OTP, Password, JWT, claim/reset ticket 원문을 로그·감사 이벤트에 저장하지 않는다.
- Challenge 응답은 `challenge_id`, 마스킹된 대상, 만료 초, 재전송 가능 시점만 공개한다.
- OTP 성공 응답은 단기·단회성·목적 고정 ticket만 반환한다.
- 회원가입 Transaction 안에서 `User`, `CustomerAccountLink`, 동의·감사 이벤트를 함께 저장한다.
- Transaction Commit 전에는 JWT를 발급하지 않는다.
- OTP·인증 데이터는 AI Prompt, RAG Context, Inquiry Context에 포함하지 않는다.

## 6. 핵심 요청 필드

### 계약 확인

- `customer_number`
- `contract_number`
- `idempotency_key`는 Header `Idempotency-Key` 사용

### OTP 검증

- `challenge_id`
- `otp_code`

### 회원가입

- `claim_ticket`
- `username`
- `password`
- 필수 약관 동의 목록

### 일반 로그인

- `username`
- `password`

## 7. 오류 계약 검토안

| HTTP | 상황 | 외부 메시지 원칙 |
|---|---|---|
| 400 | 형식상 처리 불가능한 요청 | 안전한 공통 오류 |
| 401 | 로그인 실패·만료/소비된 ticket | 인증 실패 정보만 반환 |
| 404 | 계약 후보 없음·식별값 불일치 | 동일한 비노출형 응답 |
| 409 | 이미 연결된 계약, username 중복, Idempotency 충돌, 동시 Claim 경합 | 현재 상태와 새 행동 안내 |
| 422 | 필수 필드·Password 정책·약관 검증 실패 | 허용된 필드 오류만 반환 |
| 429 | OTP 요청·검증 횟수 초과 | 재시도 가능 시점만 반환 |

계약 후보 존재 여부, 전체 이메일, 다른 계정 연결 여부를 공격자가 구분할 수 있게 응답하지 않는다.

## 8. Replay·동시성 규칙

- 동일 `Idempotency-Key`·동일 Payload는 최초 응답을 Replay한다.
- 동일 Key·다른 Payload는 `409`로 거부한다.
- OTP Challenge와 ticket은 목적·후보·만료시각에 묶는다.
- ticket 소비는 원자적으로 한 번만 성공해야 한다.
- 두 회원가입 요청이 경합하면 `CustomerAccountLink`는 최종 1건이어야 한다.
- 실패 Transaction에서는 `User`, Link, 동의, 감사 이벤트가 모두 Rollback되어야 한다.

## 9. G2 동결 전에 필요한 확인

양정현(Mobile):

- 위 경로와 화면 단계가 Android Route에 맞는지
- 404·409·422·429를 화면에서 구분할 수 있는지
- 앱이 전체 이메일·ticket을 영속 저장하지 않는지

윤승혁(PM):

- Endpoint 이름과 단계 수 승인
- OTP 만료·재전송·최대 실패 횟수 정책 승인
- Password 정책과 필수 약관 범위 승인
- 계정 존재 여부 비노출 정책 승인

## 10. 다음 Gate

1. Mobile 검토와 PM 승인을 받아 G2 계약을 동결한다.
2. 동결된 계약만 `contracts/api`와 OpenAPI에 반영한다.
3. G3에서 Additive Model·Migration·Seed를 구현한다.
4. 기존 Migration을 수정하지 않고 `visits.0005` HOLD도 유지한다.

G2 승인 전에는 Model·Migration·OTP Runtime을 선행 구현하지 않는다.

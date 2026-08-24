# P1-A 회원가입·계정연결 G1 검증 및 G2 계약 검토안

> 작성일: 2026-08-24 KST
>
> 작성자: 최지용 (Backend·DB)
>
> 동결 기준선: `origin/main@64a0539d1ec816ac3ec4a77480dbecd68a7ae927`
> 판정: `G1_CANDIDATE_PASS / G2_FROZEN / CONTRACT_CONFIRMED / G3_WAITING_FOR_MAIN_MERGE`

## 1. 이 문서의 목적

P1-A는 실제 고객이 아닌 합성 계약고객 한 명으로 회원가입·계정연결 흐름을 만드는 후속 기능이다.
이번 작업은 합성 Candidate가 안전한지 확인하고, Mobile 호환성 ACK와 PM 최종
승인을 반영해 G2 API 계약을 동결한 범위다.

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
- `data/schemas/synthetic/p1AccountLinkCandidate.schema.json`

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

## 4. G2 API 계약 최종 검토안

양정현(Mobile)의 Android 호환성 ACK와 윤승혁(PM)의 최종 정책 승인을
반영했다. 아래 신규 경로는 OpenAPI에서 `CONFIRMED`로 동결했지만 Runtime은
아직 `NOT_IMPLEMENTED`다.

| 순서 | Method·Path 제안 | 목적 | 인증 |
|---|---|---|---|
| 1 | `POST /api/v1/auth/contract-verification/challenges` | 계약번호·고객번호로 합성 계약 후보 확인, OTP Challenge 생성 | 없음 |
| 2 | `POST /api/v1/auth/contract-verification/challenges/{challenge_id}/verify` | OTP 검증 후 단회성 `claim_ticket` 발급 | 없음 |
| 3 | `POST /api/v1/auth/signup` | ID/PW 생성과 계약고객 연결 | `claim_ticket` |
| 4 | `POST /api/v1/auth/login` | 일반 ID/PW 로그인과 JWT 발급 | 없음 |
| 5 | `POST /api/v1/auth/account-recovery/username/challenges` | 아이디 찾기 OTP Challenge 생성 | 없음 |
| 6 | `POST /api/v1/auth/account-recovery/username/challenges/{challenge_id}/verify` | 마스킹된 로그인 ID 확인 | 없음 |
| 7 | `POST /api/v1/auth/password-reset/challenges` | 비밀번호 재설정 OTP Challenge 생성 | 없음 |
| 8 | `POST /api/v1/auth/password-reset/challenges/{challenge_id}/verify` | 단회성 `reset_ticket` 발급 | 없음 |
| 9 | `POST /api/v1/auth/password-reset/confirm` | 비밀번호 변경·`auth_version` 증가 | `reset_ticket` |
| 10 | `GET /api/v1/me` | 로그인 사용자·안전한 고객 Projection | Bearer JWT |

## 5. 확정 정책값

| 정책 | 값 |
|---|---|
| OTP 유효시간 | 300초 |
| OTP 재전송 대기 | 60초 |
| OTP 최대 실패 | 5회, 초과 시 Challenge 폐기 |
| 비밀번호 | 12~64자, 영문과 숫자 필수, 특수문자 선택 |
| 필수 약관 | 이용약관, 개인정보 수집·이용 |
| 선택 약관 | 마케팅 동의 |
| 계약·계정 존재 여부 | 외부 비노출 |
| P1-A 범위 | 합성 고객 ID/PW·OTP·계정연결·로그인·복구 |

## 6. 공통 요청·응답 원칙

- 모든 응답은 기존 `ApiResponse` Envelope와 `X-Correlation-ID`를 사용한다.
- 전체 이메일·계약번호·고객번호를 응답하지 않는다.
- OTP, Password, JWT, claim/reset ticket 원문을 로그·감사 이벤트에 저장하지 않는다.
- Challenge 생성은 계약·계정 존재 여부와 관계없이 동일한 HTTP `202`, 동일한
  Envelope와 일반 안내 문구를 반환한다.
- Challenge 응답은 `challenge_id`, `expires_in=300`, `resend_after=60`만
  공개하고 전체 또는 마스킹 이메일은 공개하지 않는다.
- OTP 성공 응답은 단기·단회성·목적 고정 ticket만 반환한다.
- `claim_ticket`, `reset_ticket`은 Authorization Header가 아니라 해당 요청
  Body에 넣고 JWT와 분리한다.
- 로그인 성공 응답은 기존 `LoginResponse`를 그대로 재사용한다.
- 회원가입 Transaction 안에서 `User`, `CustomerAccountLink`, 동의·감사 이벤트를 함께 저장한다.
- Transaction Commit 전에는 JWT를 발급하지 않는다.
- OTP·인증 데이터는 AI Prompt, RAG Context, Inquiry Context에 포함하지 않는다.

## 7. 핵심 요청 필드

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

## 8. 오류 계약 최종 검토안

| HTTP | 상황 | 외부 메시지 원칙 |
|---|---|---|
| 400 | 형식상 처리 불가능한 요청 | 안전한 공통 오류 |
| 401 | 로그인 실패·OTP 실패·만료/소비된 ticket | 존재 여부를 구분하지 않는 공통 인증 실패 |
| 409 | Idempotency 충돌·가입 처리 충돌·사용 불가능한 ID | 계약·계정 존재 원인을 직접 노출하지 않는 안전한 공개 코드 |
| 422 | 필수 필드·Password 정책·약관 검증 실패 | `details.fields`에 필드명과 안전한 사유만 반환 |
| 429 | OTP 재전송 대기·요청/검증 횟수 초과 | `Retry-After`와 `details.retry_after_seconds` 반환 |

계약 후보 없음은 `404`로 응답하지 않는다. Challenge 생성 단계에서 존재하는
계약과 존재하지 않는 계약을 HTTP Status, 응답 Schema, 메시지, 이메일 힌트로
구분할 수 없어야 한다.

공개 오류 코드는 다음 경계를 따른다.

- 허용: `AUTH_VERIFICATION_FAILED`, `AUTH_LOGIN_FAILED`,
  `DUPLICATE-EVENT-01`, `AUTH_SIGNUP_CONFLICT`,
  `AUTH_IDENTIFIER_UNAVAILABLE`, `AUTH_RATE_LIMITED`
- 금지: 계약 또는 다른 계정의 실제 존재를 직접 알리는 코드·문구
- `422`는 입력값 원문을 되돌려주지 않고 필드명과 정책 위반 사유만 제공한다.

## 9. Replay·동시성 규칙

- 동일 `Idempotency-Key`·동일 Payload는 최초 응답을 Replay한다.
- 동일 Key·다른 Payload는 `409`로 거부한다.
- OTP Challenge와 ticket은 목적·후보·만료시각에 묶는다.
- ticket 소비는 원자적으로 한 번만 성공해야 한다.
- 두 회원가입 요청이 경합하면 `CustomerAccountLink`는 최종 1건이어야 한다.
- 실패 Transaction에서는 `User`, Link, 동의, 감사 이벤트가 모두 Rollback되어야 한다.

## 10. 담당자 검토 반영 결과

양정현(Mobile) 최종 ACK 반영:

- 계약 확인→OTP→ID/PW 생성→로그인 Route는 구현 가능하다.
- 아이디 찾기와 비밀번호 재설정도 같은 Challenge 규칙으로 구현 가능하다.
- 세 OTP 확인 API를 `{challenge_id}/verify` 규칙으로 통일했다.
- 기존 `LoginResponse`를 재사용한다.
- `422` 필드 오류, `429` 재시도 초, 안전한 `409` 공개 코드를 제공한다.
- 전체 이메일·OTP·claim/reset ticket을 영속 저장하지 않는다.
- 최신 앱 빌드와 기존 기능 회귀가 통과했다.
- 로그인 응답·`422`·`429` Mobile 표적 테스트 3건이 통과했다.
- G2 계약 기준 Backend 추가 수정사항이 없음을 확인했다.

윤승혁(PM) 최종 승인 반영:

- Endpoint 이름과 단계 수를 승인했다.
- OTP·Password·필수/선택 약관 값을 본 문서 5절대로 확정했다.
- 계약·계정 존재 여부 비노출 정책을 적용했다.
- 계약 후보 없음 `404`를 제거하고 동일 `202` 응답으로 수정했다.
- P1-A를 합성 고객 ID/PW·OTP·계정연결·로그인·복구로 제한했다.

## 11. 다음 Gate

1. `CONFIRMED / NOT_IMPLEMENTED` 경계를 Contract·Backend Test로 검증한다.
2. 계약 승격 Commit을 `jiyong`에 게시하고 PM의 `main` 병합을 요청한다.
3. 승격 Commit이 `main`에 반영된 뒤 G3 Additive Model·Migration·Seed를
   구현한다.
4. 기존 Migration을 수정하지 않고 `visits.0005` HOLD도 유지한다.

승격 Commit이 `main`에 병합되기 전에는 Model·Migration·Seed·OTP Runtime을
선행 구현하지 않는다.

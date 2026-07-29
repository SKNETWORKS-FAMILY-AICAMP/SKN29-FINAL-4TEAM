# errors examples

Runtime 공통 오류 Wrapper 예시를 저장한다.

- `invalid-request.json`: 400 대표 요청 형식 오류
- `auth-required.json`: 401 인증 오류
- `forbidden.json`: 403 권한 오류
- `resource-not-found.json`: 404 미존재·접근 은닉
- `body-validation-error.json`: 422 요청 본문 검증
- `idempotency-key-validation-error.json`: 422 필수 Header 검증
- `internal-error.json`: 500 대표 내부 오류

오류 예시의 `correlation_id`는 팀원 간 로그 추적 키이며 실제 요청마다
새 값이 사용된다.

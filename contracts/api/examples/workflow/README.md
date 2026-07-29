# workflow examples

구현된 `POST /api/v1/inquiries/{id}/cancel`의 요청·성공·멱등 Replay와
Workflow 409 오류 예시를 저장한다.

- `cancel-inquiry-request.json`: DRAFT 문의 취소 요청
- `cancel-inquiry-success-response.json`: 최초 취소 성공
- `cancel-inquiry-replay-response.json`: 동일 Key·동일 요청 재사용
- `state-version-conflict.json`: 낙관적 잠금 `state_version` 충돌
- `idempotency-key-reuse-conflict.json`: 동일 멱등 키의 다른 요청 재사용

호출할 때 JSON 본문과 별도로 `Authorization`과 새
`Idempotency-Key` Header가 필요하다.

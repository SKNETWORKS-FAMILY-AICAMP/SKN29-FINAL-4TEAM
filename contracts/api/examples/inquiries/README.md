# inquiries examples

구현된 `POST /api/v1/inquiries`의 요청·생성·멱등 Replay 예시를
저장한다.

- `start-inquiry-request.json`
- `start-inquiry-success-response.json`
- `start-inquiry-replay-response.json`

호출할 때 JSON 본문과 별도로 `Authorization`과 새
`Idempotency-Key` Header가 필요하다. Replay 예시는 동일 Key와 동일
요청의 저장 결과 재사용이며 새 문의를 생성하지 않는다.

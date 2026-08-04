# inquiries examples

구현된 문의 생성·제출 예시와 G2 계약 전용 상담사 목록·상세 합성 예시를 저장한다.

- `start-inquiry-request.json`
- `start-inquiry-success-response.json`
- `start-inquiry-replay-response.json`
- `consultant-inquiry-list-success.json`
- `consultant-inquiry-detail-success.json`

호출할 때 JSON 본문과 별도로 `Authorization`과 새
`Idempotency-Key` Header가 필요하다. Replay 예시는 동일 Key와 동일
요청의 저장 결과 재사용이며 새 문의를 생성하지 않는다.

상담사 조회 예시는 `is_synthetic=true`인 시연 정보만 포함하며 DEC-008 Evidence와 실제 개인정보를 포함하지 않는다. 두 조회 Operation의 Runtime 상태는 `NOT_IMPLEMENTED`이다.

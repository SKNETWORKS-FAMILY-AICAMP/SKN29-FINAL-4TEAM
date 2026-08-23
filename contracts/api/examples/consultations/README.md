# consultations examples

G2 상담 계약의 정상·오류 API 예시 JSON을 저장한다.

- `save-consultation-request.json`: 상담사가 명시적으로 저장하는 DEC-003 요청
- `claim-consultation-success.json`: 상담 시작 없이 미배정 상담을 현재 상담사에게 배정한 결과

이 예시는 타이머 자동저장이나 서버 Draft 복구를 의미하지 않는다. DEC-009의 같은 탭 Draft와 이탈 경고는 Web Runtime 후속 범위다.

Claim 성공의 `resource`는 `null`이다. 배정 결과는 이후 목록·상세 조회와
`START_CONSULTATION` 허용 Action으로 확인하며, Claim 자체는 상담 시작 시각을
기록하지 않는다.

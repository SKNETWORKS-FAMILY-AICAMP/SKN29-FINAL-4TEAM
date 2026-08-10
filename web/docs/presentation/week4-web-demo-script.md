# Water Bridge 4주차 Web 시연 순서

## 시작 전

1. `.env.local`에서 `VITE_USE_MOCK_API=true`, `VITE_MOCK_ROLE=CONSULTANT`를 확인한다.
2. `npm.cmd run dev`를 실행한다.
3. `http://localhost:5173/consultant/inquiries`를 연다.
4. 화면 데이터가 합성 Mock임을 먼저 말한다.

## 상담사 시연

1. 공식 대표 문의 `DEMO-INQ-002` 상세 주소를 연다.
   - `http://localhost:5173/consultant/inquiries/bcb70ef6-01ac-5e0e-8a8d-fe5af43e8bde`
2. `출수량 저하`, 처리 완료 상태와 공식 매뉴얼 38쪽 근거를 확인한다.
3. 상담 행동 시연용 `INQ-20260704-0013`을 열고 상담 내용을 입력한다.
4. Mock 응답을 `409 상태 충돌`로 선택한다.
5. 409 안내와 함께 입력이 남고 자동 재전송되지 않는지 보여준다.
6. 방문 행동 시연용 `INQ-20260703-0008`을 연다.
7. 방문 전환 화면에서 희망일·기사·확정일 입력 흐름을 보여준다.

`DEMO-INQ-002`는 공식 대표 E2E의 최종 `RESOLVED` Snapshot이므로 발표를 위해 상태를 바꾸지 않는다. 409와 방문 행동은 각 행동이 허용된 합성 문의로 재현한다고 먼저 설명한다.

## 반드시 함께 말할 내용

- 상담 목록·상세·저장·방문 일정은 현재 Mock이다.
- 실제 Backend 저장이 완료됐다고 설명하지 않는다.
- 실제 연동은 Backend 계약이 준비된 뒤 Repository의 Remote 구현으로 교체한다.

실행이 어려우면 [Fallback 계획](./week4-web-fallback-plan.md)에 따라 캡처 5장을 같은 순서로 보여 준다.

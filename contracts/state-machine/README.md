# State Machine Contracts

문의·상담·방문 업무의 상태·이벤트·가드·허용 행동을 관리한다.
백엔드 State Machine 구현이 단일 실행 기준이며, Web·Mobile은 반환된 `allowed_actions`를 사용한다.

- Inquiry 상태는 `inquiry-states.yaml`의 12개 값만 사용한다.
- 추가 답변 이벤트는 `SUBMIT_ANSWERS`이며 별칭을 허용하지 않는다.
- 상담·방문 완료 뒤 고객 피드백은 `COMPLETION_PENDING`을 유지한다.
- 상담·방문 경로의 최종 `RESOLVED` 전환은 snapshot 담당자가 수행한다.

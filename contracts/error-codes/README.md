# Error Codes

업무 오류 코드는 `CATEGORY-REASON-NUMBER` 형식으로 관리한다.
각 항목은 HTTP 상태, 재시도 가능 여부, 사용자 문구와 권장 행동을 포함한다.

Runtime 공통 호환 코드는 기존 공개 이름(`INVALID_REQUEST`,
`RESOURCE_NOT_FOUND`, `VALIDATION_ERROR`, `INTERNAL_ERROR`)을 유지한다.
`http_status`는 각 코드의 대표 HTTP 상태다. Registry 최상위의
`runtime_http_mapping`은 기존 항목 소비자를 깨지 않는 가산 계약이며,
공통 Handler의 실제 선택 순서를 기록한다.

1. `BackendError` 공개 값 통과
2. 예외 유형 override
3. 서버 오류 상태군 fallback
4. 개별 HTTP 상태 override
5. 클라이언트 오류 상태군 fallback
6. 처리되지 않은 예외

Handler 정책을 바꿀 때는 Registry와 Runtime 예외 응답 계약 테스트를
같은 변경에서 갱신한다.

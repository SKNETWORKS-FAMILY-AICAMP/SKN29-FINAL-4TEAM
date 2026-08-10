# 한예나 → 최지용: 상담사 문의 조회 API Runtime 회신

## 1. 검토 결과

상담사 문의 목록·상세 API의 주소, 응답 형식, 개인정보 범위를 확인했습니다.
Frontend에서 혼자 준비할 수 있는 작업은 완료했습니다.

- `GET /api/v1/inquiries` 목록 연결 구조 완료
- `GET /api/v1/inquiries/{id}` 상세 연결 구조 완료
- API 응답을 화면 형식으로 바꾸는 처리 완료
- `LOW` 우선순위와 위험도 값 처리 완료
- 빈 값, 403, 404, 재시도 화면 처리 완료
- 개인정보와 내부 정보가 추가로 표시되지 않도록 처리 완료
- 관련 Web 테스트, Lint, Build 통과

최신 `main`에서 상담사 문의 조회 Backend 코드가 반영된 것도 확인했습니다.

## 2. 실제 연결 확인 요청

목록·상세 조회만 실제 Backend로 확인하려고 합니다.
아래 정보를 전달해 주세요.

1. Backend 실행 주소
2. 테스트용 상담사 계정 또는 로그인 방법
3. 해당 상담사에게 배정된 문의 UUID 1개
4. 정상 목록·상세 응답을 확인할 수 있는 테스트 데이터
5. 오류 확인 시 사용할 Backend 로그 확인 방법
6. `X-Correlation-ID`로 요청을 찾는 방법
7. PostgreSQL 환경에서 조회 기능이 확인됐는지 여부

정보를 받으면 다음 항목을 함께 확인하겠습니다.

- 목록 조회 `200`
- 상세 조회 `200`
- 다른 상담사의 문의 조회 `404`
- 잘못된 검색 조건 `422`
- Web의 확인 번호와 Backend 로그 연결

## 3. 현재 유지할 내용

- 기본 화면의 Mock은 바로 삭제하지 않습니다.
- 실제 연결은 목록·상세 조회에만 적용합니다.
- 상담 시작·완료와 방문 관련 버튼은 실제 API에 연결하지 않습니다.
- 상담·방문 쓰기 API가 준비되기 전까지 해당 기능은 대기합니다.
- 실제 확인이 끝나기 전에는 전체 연동 완료로 처리하지 않습니다.

## 4. 회신 상태

```text
sender=한예나
receiver=최지용
review_scope=CONSULTANT_INQUIRY_READ_RUNTIME

endpoint_contract=OK
list_dto=OK
detail_dto=OK
product_and_care_mapping=OK
null_handling=OK
error_handling=OK
privacy_boundary=OK
mock_field_gap=Mock 전용 주소·상담·방문·Evidence 정보는 실제 응답에 섞지 않음
consumer_start_request=SELECTIVE_START_REQUESTED
consumer_scope=GET /api/v1/inquiries, GET /api/v1/inquiries/{id}
shared_code_status=MAIN_CONFIRMED
runtime_information=REQUESTED
consultation_visit_write=HOLD
notes=Frontend 준비 완료. 실행 주소·상담사 계정·배정 문의 UUID를 전달받은 뒤 목록·상세 조회만 실제 연결 확인 예정
```

## 5. 요청 답변 형식

아래 형식으로 답변 부탁드립니다.

```text
backend_base_url=<실행 주소>
consultant_login=<계정 또는 로그인 방법>
assigned_inquiry_id=<배정 문의 UUID>
expected_list_status=<예: 200>
expected_detail_status=<예: 200>
correlation_log_check=<확인 방법>
postgresql_verification=<PASS | NOT_TESTED>
available_time=<함께 확인 가능한 시간>
notes=<추가 안내>
```

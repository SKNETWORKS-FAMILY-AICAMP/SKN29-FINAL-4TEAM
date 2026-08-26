# Web 전화 문의 Backend 계약 보완 요청

- 요청자: 한예나 (Web)
- 수신자: 최지용 (Backend)
- 작성일: 2026-08-26
- 기준 SHA: `a8e7929d7d759b361de9055fcc7ed9c74eaedaa9`

## 한 줄 요약

전화 문의를 상담 완료 건으로 안전하게 저장하고 완료 목록에서 따로 조회할 수 있도록 등록·목록 API 계약 보완을 부탁드립니다.

## 요청 배경

Web 전화 문의 화면은 고객·제품 선택, 대표 증상, 문의 내용 입력과 등록 성공 화면까지 연결되어 있습니다. 상담 내용 영역은 별도로 배치했지만, 현재 Backend 계약에서 저장할 수 없어 안내와 함께 비활성화했습니다. 아래 기능은 Web이 정확하게 구현할 수 없습니다.

1. 긴급도 선택 UI는 제거했지만 등록 요청의 `priority_code`가 필수라 Web이 임시로 `NORMAL`을 전송하고 있습니다.
2. 전화 문의 등록 결과가 항상 `CONSULTATION_REQUIRED`라 `처리 완료된 문의`에 들어가지 않습니다.
3. DB에는 `channel_code=PHONE`이 저장되지만 문의 목록 응답과 필터에는 공개되지 않아 `전화 문의` 탭을 만들 수 없습니다.
4. 등록 API에는 `raw_text`만 있고 별도 `consultation_note`가 없어 고객 문의 내용과 상담 기록을 나눠 저장할 수 없습니다.
5. P1 승인 고객 6명은 활성 구독이 있지만 `customer.user_id=None`이고, 검색 API는 활성 합성 Customer User가 연결된 구독만 조회하므로 현재 P1 환경에서는 고객 검색 결과가 항상 0건입니다.

Web에서 상태나 채널을 임의로 만들면 실제 DB와 화면이 달라지므로 고정값·로컬 완료 처리로 대신하지 않고 있습니다.

## Backend 보완 요청

### 1. 긴급도 서버 기본값 지원

`POST /api/v1/consultant/phone-inquiries`에서 `priority_code`를 선택 입력으로 변경하고, 생략 시 Backend가 공식 기본값을 적용해 주세요.

- 권장 기본값: `NORMAL`
- 성공 응답 또는 상세 조회에서 최종 적용된 값을 확인할 수 있어야 합니다.
- 계약 확정 후 Web의 임시 `NORMAL` 전송을 제거하겠습니다.

### 2. 전화 상담 완료용 공식 처리 방식 제공

제품 요구사항은 상담사가 통화를 마치고 등록한 전화 문의를 처리 완료 건으로 저장하는 것입니다. 현재는 등록 후 `START_CONSULTATION`부터 기존 Workflow를 다시 진행해야 하며, `RESOLVED`까지는 고객 해결 확인과 `FINALIZE_INQUIRY` 조건이 필요합니다.

Web이 여러 상태 변경 API를 임의로 연속 호출하지 않도록 아래 중 공식 방식을 정해 주세요.

- 권장: 전화 문의 등록·상담 기록 저장·완료 처리를 하나의 원자적 Backend 작업으로 제공
- 대안: 기존 Workflow를 유지해야 한다면 전화 문의가 완료되기 위한 정확한 단계와 Web 버튼 정책을 확정

상태 전이 규칙을 변경해야 한다면 PM 승인과 공용 계약 반영도 함께 부탁드립니다.

### 3. 전화 문의 목록 구분값과 필터 제공

상담사 문의 목록에 아래 항목을 추가해 주세요.

- 목록 Item: `channel_code`
- 허용값에 `PHONE` 포함
- Query Filter 예시: `GET /api/v1/inquiries?status=RESOLVED&channel_code=PHONE`
- 필터 적용 시 `items`, `page_info.total`, `status_counts`가 같은 기준으로 계산

이 계약이 제공되면 Web의 처리 완료 화면에만 `전체 문의 | 긴급 문의 | 주의 문의 | 일반 문의 | 전화 문의` 탭을 추가하겠습니다.

### 4. 고객 문의 원문과 상담 기록 분리 저장

전화 문의 등록 시 아래 두 값을 구분해 저장할 수 있도록 계약을 보완해 주세요.

- `raw_text`: 고객이 말한 문의·증상 원문
- `consultation_note`: 상담사가 기록한 확인 내용과 안내 사항

두 번째 요청의 원자적 처리 API에 `consultation_note`를 포함하는 방식도 가능합니다.

### 5. P1 전화 문의 검색용 고객 연결 절차 제공

현재 P1 Bootstrap의 승인 고객은 OTP 가입 전 상태로 보존되며, 전화 문의 고객 검색 조건에는 활성 합성 Customer User 연결이 필요합니다. 기존 P1 보호 범위를 깨뜨리지 않는 공식 절차를 제공해 주세요.

- 권장: 승인 고객 1명의 OTP 가입·계정 연결을 완료한 뒤 검색과 전화 문의 등록에 사용하는 절차 제공
- 대안: P1 전용 검색 가능 합성 고객 Fixture를 Bootstrap 계약에 명시적으로 포함
- 기존 G4·CONS-04 Seed를 P1 DB에 임의 적용하지 않도록 P1 전용 명령과 완료 기준 명시

## 성공 응답에 필요한 정보

- `inquiry_id`
- `inquiry_code`
- `channel_code`
- 최종 `status_code`
- `state_version`
- `allowed_actions`
- `idempotent_replay`

## 완료 확인 기준

1. Web이 숨겨진 긴급도 고정값 없이 전화 문의를 등록할 수 있음
2. 상담 기록이 문의 원문과 별도로 저장·조회됨
3. 공식 정책에 따른 최종 상태와 `state_version`, `allowed_actions`가 반환됨
4. 완료 목록을 `channel_code=PHONE`으로 조회할 수 있음
5. 동일 요청 Replay에서 중복 Inquiry·Consultation이 생성되지 않음
6. 오래된 `state_version`은 기존 정책대로 409를 반환함
7. OpenAPI·Backend 계약 테스트·Runtime 테스트가 함께 반영됨
8. P1 격리 환경에서 승인된 고객 이름 2자 이상 또는 연락처 숫자 4자리 이상으로 검색 결과가 1건 이상 반환됨

## Web 후속 작업

Backend와 공용 계약이 main에 반영되면 최신 main을 받은 뒤 다음 작업을 진행하겠습니다.

1. 임시 `priority_code=NORMAL` 전송 제거
2. 전화 문의 등록·상담 기록·완료 흐름 연결
3. 처리 완료 화면의 전화 문의 탭과 필터 연결
4. Web Test·Lint·TypeCheck·E2E TypeCheck·Build 및 Playwright 재검증

Backend·DB·Migration·공용 계약 파일은 Web 작업에서 수정하지 않았습니다.

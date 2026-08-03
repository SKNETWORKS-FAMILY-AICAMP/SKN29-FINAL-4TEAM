# 실제 API 연결 준비 체크리스트

이 문서는 **지금의 연습용 데이터(Mock)를 실제 서버 데이터로 바꿀 때** 보는 목록입니다.

## 아주 쉽게 말하면

- 지금 화면과 버튼은 작동합니다.
- 하지만 상담·방문·운영 데이터는 아직 연습용입니다.
- 서버 주소와 데이터 모양을 팀에서 정한 뒤에만 실제 연결을 시작합니다.

## 내가 먼저 할 수 있는 확인

- [ ] `npm.cmd run test`가 성공한다.
- [ ] `npm.cmd run lint`가 성공한다.
- [ ] `npm.cmd run build`가 성공한다.
- [ ] 상담사 화면에서 문의 선택 → 상담 시작 → 상담 완료가 된다.
- [ ] 방문 필요를 선택하면 기사 배정 → 방문 확정이 된다.
- [ ] 관리자 화면의 필터와 초기화가 된다.
- [ ] 화면에 실제 고객 이름·전화번호 같은 개인정보가 없다.

## 팀에서 계약이 정해진 뒤 바꿀 6곳

| 화면 기능 | 지금 사용하는 연습용 파일 | 확인할 계약 파일 |
| --- | --- | --- |
| 상담사 문의 목록 | `consultantWorkspaceMock.ts` | `contracts/api/paths/inquiries.yaml` |
| 상담사 문의 상세 | `consultantWorkspaceMock.ts` | `contracts/api/paths/inquiries.yaml` |
| 상담 기록 저장·완료 | `consultationMockApi.ts` | `contracts/api/paths/consultations.yaml` |
| 방문기사 배정 | `visitTransitionMock.ts` | `contracts/api/paths/visits.yaml` |
| 방문 일정 저장·확정 | `visitTransitionMock.ts` | `contracts/api/paths/visits.yaml` |
| 관리자 운영 집계 | `consultantWorkspaceMock.ts` | `contracts/api/paths/operations.yaml` |

코드의 같은 목록은 `src/features/runtime-status/model/apiIntegrationReadiness.ts`에 있습니다. 화면의 API 연동 현황 숫자도 이 목록을 사용합니다.

## 담당자에게 꼭 받아야 하는 답

각 기능마다 아래 7개가 있어야 합니다.

1. 어느 주소로 보내는지
2. `GET`, `POST`, `PATCH` 중 어떤 방식인지
3. 보낼 데이터의 이름과 모양
4. 받을 데이터의 이름과 모양
5. 성공했을 때 다음 상태와 가능한 버튼(`state_version`, `allowed_actions`)
6. 실패했을 때 번호와 뜻(401, 403, 404, 409, 422)
7. 개인정보를 어디까지 숨길지

## 연결할 때 지킬 순서

1. 계약 파일이 비어 있지 않은지 확인한다.
2. 계약 예시 데이터로 테스트를 먼저 만든다.
3. Mock 파일을 바로 지우지 말고 실제 API 파일을 따로 만든다.
4. 한 기능씩 실제 API로 바꾸고 테스트한다.
5. 상담사와 관리자 담당자가 화면 결과를 확인한다.
6. 모두 확인한 뒤에만 Mock 기본값을 끈다.

> 서버 주소나 데이터 이름을 모르면 추측해서 만들지 않습니다. 그때는 담당자에게 확인합니다.

# WaterCare API 문서 안내

> 문서 상태: **OWNER_CONFIRMED DESIGN BASELINE**
>
> 이 디렉토리는 외부 개발자와 프로젝트 팀원이 Public API 계약을 빠르게 이해하도록 만든 사람용 설명 문서다.
>
> 작성·개정 책임: **최지용(Backend·API OWNER)**

최지용의 41개 API 작성·설계 기준선은 확정됐다. OpenAPI 정합화,
Runtime 구현과 소비 검증 성숙도는 항목별 상태로 별도 관리한다.

## 문서 구성

- [WaterCare API 명세](watercare_api_specification.md): Public Endpoint, 공통 요청·응답, 오류, 권한, 상태 전이와 검토 상태
- [API 계약 개발·인계 가이드](../individual/jiyong/technical/backend/api_contract_handover_guide.md): 변경 절차, 검증 기준과 역할별 인계 내용
- [OpenAPI 계약](../../contracts/api/openapi.yaml): 도구와 테스트에서 사용하는 기계 기준본. 개별 operation의 `x-contract-status`로 구현 성숙도를 구분

## 계약 우선순위

`contracts/api/**`는 최지용이 작성·갱신하는 기계 기준본이다. 최지용은
v0.5 기준선과 현재 Runtime을 대조해 Method·Path·Schema를 정합화하고,
사람용 명세·구현·예시·계약 테스트를 같은 변경에서 갱신한다.

State Machine 업무 규칙은 윤승혁(PM)의 `contracts/state-machine/**`,
AI 입출력 Schema는 이동윤의 `contracts/ai/**`를 입력으로 소비한다.
Web·Mobile·QA 검토는 작성 후 소비 호환성·재현·PR 품질을 확인하는
단계이며 API 작성의 선행 승인이 아니다.

현행 Django 구현은 `backend/**`만을 기준으로 한다. 루트
`WaterCareBackend/**`는 구형 Android 연동 starter 참고본이며 이
문서의 Method·Path·DTO·Migration·State 또는 AI 계약을 덮어쓰는
권위 원본이 아니다.

## 상태 해석

| 상태 | 의미 |
|---|---|
| `RUNTIME_IN_PROGRESS` | Runtime과 OpenAPI 후보가 있으나 구현·테스트·리뷰 인수가 끝나지 않음 |
| `OPENAPI_CONFIRMED` | OWNER 기계 계약이 확정됐으나 실행 route가 없음 |
| `DESIGN_BASELINE_ONLY` | OWNER 사람용 설계 기준선에만 있고 OpenAPI·Runtime이 없음 |
| `BLOCKED` | 선행 데이터 모델이나 정책 결정 없이는 구현할 수 없는 항목 |
| `VERIFIED` | 구현·자동 테스트·리뷰·검증 결과가 모두 확인된 계약 |

문서에 Endpoint가 존재하는 것만으로 구현 완료를 의미하지 않는다.
세부 항목이 미완성인 경우 `OWNER 정합화`, `PM State 입력`,
`AI 계약 입력`, `소비 호환성 검토`로 원인과 책임을 구분한다. 이는
API 작성 권한 승인이 아니라 계약 완성도를 나타낸다. `OWNER 정합화`는
최지용이 계약·Runtime을 직접 맞추는 후속 작업이며 팀 승인 대기가
아니다.

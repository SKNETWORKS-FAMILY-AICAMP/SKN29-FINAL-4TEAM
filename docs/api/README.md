# WaterBridge API 문서 안내

> 기준일: 2026-08-02
>
> 문서 상태: 팀 공용 API 설계·Runtime 현황
>
> 유지관리 역할: Backend·API 담당

이 디렉터리는 WaterBridge Public API의 사람용 설계, 기계 계약과 실제
Django Runtime 지원 범위를 구분해 제공한다. 문서에 Endpoint가 있다는
사실만으로 Runtime 구현 또는 팀 검증 완료를 의미하지 않는다.

## 문서 구성

- [WaterBridge Public API 명세](waterbridge_api_specification.md): 공통 규칙,
  현재 기계 계약 10개와 설계 백로그의 상태
- [API Runtime 구현 상태](runtime_implementation_status.md): OpenAPI 10개,
  Django Runtime 8개와 OpenAPI-only 2개의 Route·View·검증 경계
- [OpenAPI 계약](../../contracts/api/openapi.yaml): Method·Path·Schema를
  도구와 계약 테스트가 읽는 기계 기준본
- [Django REST API·OpenAPI 계약·구현·보안검증 가이드](../individual/jiyong/API/Django_REST_API_OpenAPI_계약_구현_보안검증_가이드.md):
  Backend 작성자 검증, 오류·예시와 변경 절차의 상세 기록

## 기준 원본과 책임 경계

| 범위 | 기준 원본 | 유지관리·검토 역할 |
|---|---|---|
| Public REST Method·Path·Schema | `contracts/api/**` | Backend·API 담당 |
| 상태·전이·Guard·허용 행동 | `contracts/state-machine/**` | PM·기술 통합 담당 |
| AI 입출력 Schema | `contracts/ai/**` | AI·RAG 담당 |
| 실행 Route·View·Serializer | `backend/**` | Backend 담당 |
| 소비 호환성 | Web·Mobile 구현과 계약 테스트 | Web·Mobile·QA 담당 |

사람용 명세, OpenAPI, Runtime, 예시와 계약 테스트는 같은 변경 단위에서
정합화한다. State와 AI 계약은 해당 기준 원본을 입력으로 사용하며,
소비자 검토는 구현 이후 DTO 호환성과 재현 가능성을 확인한다.

현행 Django 구현 기준은 `backend/**`다. 루트의 `WaterCareBackend/**`는
구형 Android 연동 starter이므로 현재 Method·Path·DTO·Migration 또는
State 계약의 기준으로 사용하지 않는다.

## 현재 지원 경계

| 구분 | 수량 | 의미 |
|---|---:|---|
| 사람용 API 카탈로그 | 42 | 기계 계약·백로그·폐기 설계를 포함한 추적 목록 |
| OpenAPI Operation | 10 | 현재 기계 계약에 등록 |
| Django Runtime | 8 | 실제 Route·View 존재 |
| OpenAPI-only | 2 | 계약은 있으나 실행 Route 없음 |
| 설계 백로그 | 31 | OpenAPI 미등록, `BLOCKED` 4개 포함 |
| 폐기 설계 | 1 | generic `/events`; 현재 행동별 Endpoint 원칙과 불일치 |

## 상태 해석

| 상태 | 의미 |
|---|---|
| `RUNTIME_REVIEW_PENDING` | Route·View와 작성자 검증은 있으나 독립 재현·팀 검토 전 |
| `OPENAPI_ONLY` | Method·Path·Schema는 등록됐으나 실행 Route가 없음 |
| `DESIGN_BACKLOG` | 요구사항 추적용 설계이며 OpenAPI·Runtime 계약이 아님 |
| `BLOCKED` | 저장 모델이나 정책 결정 전에는 구현하면 안 되는 백로그 |
| `RETIRED` | 현재 계약 방향에서 제외된 역사 설계 |
| `VERIFIED` | 구현·자동 테스트·독립 재현·팀 검토가 모두 확인됨 |

세부 구현 여부는 [API Runtime 구현 상태](runtime_implementation_status.md)를
우선 확인한다. `x-contract-status: CONFIRMED`는 기계 계약의
Method·Path·Schema가 정해졌다는 뜻이며 Runtime 완료 표시가 아니다.

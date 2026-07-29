# API 계약 개발·인계 가이드

> 기준일: 2026-07-27
> 담당: 최지용
> 적용 원칙: API 명세는 최지용 확정 기준선이며, 구현은 `작업 → 검증` 단위로 진행한다.

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | 현행 API 계약 개발·인계 기준 |
| 관련 WBS | `T-016`, `T-017`, `T-022`, `T-023` |
| 작성·유지 책임 | 최지용 |
| 산출물/내용 의사결정자 | 최지용: API Method·Path·DTO·오류 계약과 Django·PostgreSQL 반영 기준. 윤승혁(PM): State Machine 업무 규칙. 이동윤: Backend↔AI Schema·실패 경계 |
| 협업 책임 | 윤승혁(PM): 계약·State 연계, 김은진: Contract·Integration QA, 이동윤: AI Schema, 한예나: Web Client, 양정현: Mobile Client |
| 검토 요청 대상 | 윤승혁(PM): 계약·State 통합, 김은진: 계약·PostgreSQL 통합 재현, 이동윤·한예나·양정현: 각 소비 영역 호환성 |
| 검토 상태 | 미요청 또는 증거 미확인 |
| PR 병합 담당 | 윤승혁(PM), 비작성자 1명 이상 리뷰 후 |
| 인계 대상 | 윤승혁(PM), 김은진, 이동윤, 한예나, 양정현 |

위 검토는 최지용의 ERD·테이블 명세·API 명세·Django·PostgreSQL
작성이나 구현을 시작하기 위한 선행 승인이 아니다. 확정 기준을 각
영역이 통합·재현·소비할 수 있는지 확인하고, 불일치가 있으면 재현
사례를 남기는 절차다.

## 1. 문서 목적

이 문서는 확정 API 명세를 OpenAPI, Django URL, Serializer, Service,
Model과 테스트로 옮기는 절차를 정의한다. 구현 여부와 실행 검증
여부를 분리해 표시한다.

## 2. 단일 원본

| 구분 | 원본 | 용도 |
| --- | --- | --- |
| Public API 설명 | [WaterCare API 명세](../../../../api/watercare_api_specification.md) | Public 후보 42개의 Method·Path·입출력 기준 |
| 기획 기준 | [API 명세서](../../../../planning/md/API명세서.md) | 업무 요구사항과 API ID 연결 |
| 기계 계약 | [OpenAPI](../../../../../contracts/api/openapi.yaml) | 자동 검증 가능한 Path·Schema·Header |
| 공통 코드 | [공통 코드 계약](../../../../../contracts/codes) | 역할·상태·위험도·사용 안내 코드 |
| 오류 코드 | [오류 코드 계약](../../../../../contracts/error-codes) | 공개 오류 코드와 HTTP 상태 |
| Django Runtime | [Backend](../../../../../backend) | URL·Serializer·Service·Repository·Model |

사람용 명세와 OpenAPI를 별도 후보안으로 운영하지 않는다. 확정 명세를
먼저 읽고 OpenAPI와 Runtime을 같은 필드·코드·제약으로 맞춘다.

## 3. 현재 상태와 실행 증거의 단일 원본

이 가이드에는 수시로 변하는 Endpoint 수, 테스트 수와 다음 작업 순서를
복제하지 않는다. 현재 구현 상태와 실행 증거는 목적별 문서에서 확인한다.

| 확인 목적 | 단일 원본 |
| --- | --- |
| Auth 계약·Route·Token 동작·HTTP 검증 | [Auth 계약·Runtime 정합화 보고서](../../manuals/20260727_최지용_Auth_API_계약_Runtime_정합화_보고서_v1.0.md) |
| PostgreSQL·Migration·Seed 구현 경계 | [Migration 검증 보고서](../../manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md) |
| 새 환경 실행·재현 순서 | [Django·PostgreSQL 공유 패키지 인계서 v1.2](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md) |
| OpenAPI·Runtime 현재 지원 경계 | [API Runtime 구현 상태](../../../../api/runtime_implementation_status.md) |
| 오류 Registry·JSON 예시·최종 회귀 증거 | [Backend API 계약 정합화 검증보고서](../../manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md) |
| 문의 API 구현 Gap | [T-022 문의 관리 구현 준비도](t-022-inquiry-readiness.md) |
| 상태 전이 구현 Gap·PM 입력 경계 | [T-023 Workflow 구현 준비도](t-023-workflow-readiness.md) |

이 문서는 위 결과를 다시 요약하는 보고서가 아니라, 어떤 API에도 반복
적용하는 계약 작성·구현·검증 절차의 단일 원본으로 유지한다.

## 4. 계약 상태 표기

| 상태 | 의미 |
| --- | --- |
| `SPEC_CONFIRMED` | 최지용 확정 명세에 Method·Path·필드가 정의됨 |
| `OPENAPI_DEFINED` | 기계 계약과 `$ref`가 작성됨 |
| `RUNTIME_IMPLEMENTED` | Django URL부터 저장 계층까지 구현됨 |
| `RUNTIME_VERIFIED` | 실제 PostgreSQL·HTTP·자동 회귀를 통과함 |
| `NOT_IMPLEMENTED` | 명세는 확정됐지만 Runtime이 아직 없음 |

`OPENAPI_DEFINED`를 Runtime 완료로 계산하지 않는다. Runtime이 없는
항목은 다음 구현 순서에 배치한다.

## 5. 작업·검증 절차

실제 PostgreSQL·HTTP 검증을 시작하기 전에
[공유 패키지 인계서 v1.2](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md)의
5장에 따라 PostgreSQL과 Django를 실행한다. 이 가이드에는 서버
시작·종료 명령을 중복하지 않는다.

### 5.1 작업

1. 확정 API 명세에서 Method·Path·역할·필수 필드·오류를 확인한다.
2. OpenAPI Path와 Schema를 같은 이름과 제약으로 작성한다.
3. Model·Migration을 먼저 구현해 저장 원장을 확정한다.
4. Repository·Service에 조회 범위, Transaction과 업무 규칙을 둔다.
5. Serializer·View·URL을 연결한다.
6. 상태 변경 API는 State Machine과 멱등성 경계를 함께 적용한다.

### 5.2 즉시 검증

1. OpenAPI 문법, `$ref`, operation ID 중복을 검사한다.
2. `makemigrations --check --dry-run`으로 Model drift를 검사한다.
3. 실제 PostgreSQL에서 `migrate --check`를 실행한다.
4. 정상·검증 실패·401·403·404·409 시나리오를 실행한다.
5. Runtime 응답과 OpenAPI Schema를 비교한다.
6. 관련 테스트를 통과한 뒤 전체 Backend 회귀를 실행한다.

저장소 루트 기준 예시는 다음과 같다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe -m pytest -q
```

## 6. Endpoint 구현 체크리스트

- [ ] `/api/v1` Prefix와 복수형 `kebab-case` Path를 사용한다.
- [ ] 내부 PK·비밀값·개인정보를 Public DTO에 노출하지 않는다.
- [ ] Request 필수·선택·조건부 필드를 OpenAPI와 Serializer에 같이 둔다.
- [ ] 공통 성공·오류 Wrapper와 `X-Correlation-ID`를 유지한다.
- [ ] 목록은 `page >= 1`, `1 <= size <= 100`, `total >= 0`을 지킨다.
- [ ] 고객 소유·기사 배정 범위를 서버에서 검사한다.
- [ ] 상태 변경은 Service를 통해 수행하고 상태 이력을 남긴다.
- [ ] 중복 요청은 `idempotency_key`와 Payload 일치 여부를 검사한다.
- [ ] Token·Authorization·Cookie·요청 본문을 로그에 남기지 않는다.
- [ ] 실제 PostgreSQL과 전체 회귀 결과를 기록한다.

## 7. 인증 회귀 기준

인증 변경 시 최소한 다음을 다시 검증한다.

| 영역 | 시나리오 |
| --- | --- |
| 로그인 | 합성 사용자 성공, 잘못된 코드·비활성 사용자 거부 |
| Access | 정상 `/me`, 미인증·만료·변조 Token 거부 |
| Refresh | 새 Pair 발급, 기존 Refresh 즉시 폐기 |
| Logout | 제출 Refresh 폐기, 폐기 Token 재사용 거부 |
| 권한 | 고객 본인 객체와 기사 배정 객체만 허용 |
| 응답 | Password·전화·주소·Token 비노출 |
| 로그 | Secret·Token·개인정보 비노출 |

인증의 현재 테스트 수와 실행 결과는 이 가이드에 복제하지 않고
[Auth 계약·Runtime 정합화 보고서](../../manuals/20260727_최지용_Auth_API_계약_Runtime_정합화_보고서_v1.0.md)를
기준으로 한다. 변경 PR에는 과거 수치를 재사용하지 않고 해당 변경에서
실제로 다시 실행한 결과만 기록한다.

## 8. 업무별 구현 상태 관리

| 업무 | 현재 상태의 단일 원본 |
| --- | --- |
| DB Model·Migration 선행 작업 | [DB Schema 개발·인계 가이드](database_schema_handover_guide.md)와 [Migration 검증 보고서](../../manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md) |
| T-022 문의 최소 수직 흐름 | [문의 관리 구현 준비도](t-022-inquiry-readiness.md) |
| T-023 Workflow·이력·멱등성 | [Workflow 구현 준비도](t-023-workflow-readiness.md) |

구체적인 우선순위와 완료 수치는 위 업무 문서와 승인된 WBS에서 관리한다.
이 공통 가이드에는 별도의 작업 Queue를 만들어 같은 상태를 이중 관리하지
않는다.

## 9. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 윤승혁(PM) | Method·Path·DTO·오류 계약, State 영향 Endpoint, 미구현 범위 | State 업무 규칙과 API 경계를 대조하고 비작성자 리뷰 후 PR 병합 | 계약·State 불일치 0건 또는 재현 사례·결정 기록 | 검토 미요청 또는 증거 미확인 |
| 김은진 | OpenAPI 변경, Contract·PostgreSQL 통합 명령, 정상·오류 Fixture와 최신 테스트 결과 | 계약·DB 통합 테스트를 같은 변경 기준으로 재현 | 실행 명령·환경·결과가 기록되고 핵심 테스트 통과 | 검토 미요청 또는 증거 미확인 |
| 이동윤 | Backend↔AI Request·Response Schema, Timeout·Fallback·오류 경계 | AI Schema와 Adapter 필드·Enum·실패 응답을 대조 | Schema 검증과 정상·누락·실패 Fixture 통과 | 검토 미요청 또는 증거 미확인 |
| 한예나 | Web용 Method·Path·목록 DTO·오류·`409` 예시 | Web Mock을 동일 계약으로 교체하고 호환성 차이를 사례로 보고 | Web 요청·응답과 오류 처리가 OpenAPI와 일치 | Runtime별 인계 전 또는 증거 미확인 |
| 양정현 | Mobile용 인증 Header·문의 DTO·상태·`allowed_actions`·오류 예시 | Mobile Mock을 동일 계약으로 교체하고 호환성 차이를 사례로 보고 | Mobile 요청·응답과 오류 처리가 OpenAPI와 일치 | Runtime별 인계 전 또는 증거 미확인 |

각 인계에는 Runtime 구현 파일과 변경 Migration, 역할·객체 범위,
상태·동시성·멱등성 영향, 실행 명령, 해당 변경에서 다시 실행한 테스트
결과와 의도적으로 미구현한 범위를 포함한다. 명세 확정을 다시 요청하지
않고, 소비자는 OpenAPI와 Runtime의 동일 버전을 사용한다.

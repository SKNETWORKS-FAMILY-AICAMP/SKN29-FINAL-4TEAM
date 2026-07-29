# T-022 문의 관리 구현 준비도 — 착수 전 스냅샷

> 기준일: 2026-07-27
> Backend·API 담당: 최지용
> 문서 시점 판정: 2026-07-27 당시 명세 기준선 작성 완료, Runtime 미구현

> **현재 상태 안내:** 이 문서의 구현 수치와 `미구현` 판정은 착수 전
> 기록이므로 현행 완료 판정에 사용하지 않는다. 2026-07-29 현재
> `POST /api/v1/inquiries` START Runtime은 구현돼 있다. 현재 상태는
> [API Runtime 구현 상태](../../../../api/runtime_implementation_status.md),
> 실행 증거는
> [Backend API 계약 정합화 검증보고서](../../manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md)를
> 따른다.

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | 명세 기준선 작성 완료, T-022 Runtime 미구현 |
| 관련 WBS | `T-005`, `T-017`, `T-022`, `T-023` |
| 작성·유지 책임 | 최지용 |
| 산출물/내용 의사결정자 | 최지용: 문의 DB·API·Django·PostgreSQL 구현 기준. 윤승혁(PM): 상태·이벤트·Guard·`allowed_actions` 업무 규칙. 이동윤: AI Request·Response·실패 경계 |
| 협업 책임 | 윤승혁(PM): State 규칙 입력, 이동윤: AI·Fallback 입력, 김은진: 인증·PostgreSQL 수직 QA, 한예나·양정현: DTO·오류 소비 |
| 검토 요청 대상 | 윤승혁(PM), 이동윤, 김은진, 한예나, 양정현 |
| 검토 상태 | 미요청 또는 증거 미확인 |
| PR 병합 담당 | 윤승혁(PM), 비작성자 1명 이상 리뷰 후 |
| 인계 대상 | 윤승혁(PM), 이동윤, 김은진, 한예나, 양정현 |

위 검토는 최지용의 ERD·테이블 명세·API 명세·Django·PostgreSQL
작성을 시작하기 위한 선행 승인이 아니다. State·AI 입력의 통합 여부,
PostgreSQL 재현성, Web·Mobile의 DTO·오류 소비 호환성을 확인하는
절차다.

## 1. 구현 목표

동일한 `inquiry_id` 아래에 최초 문의, 문진 보완과 자가조치 결과를
누적하고 고객 본인 범위를 지키는 최소 수직 흐름을 구현한다. 문의
상태 변경은 T-023 State Machine의 업무 규칙을 소비하되, T-022의
저장·API 구현과 혼합하지 않는다.

## 2. 현재 증거

| 항목 | 현재 값 |
| --- | --- |
| Inquiry Runtime 구현 파일 | 0 |
| 실질 Django Model | 0 |
| 번호 Migration | 0 |
| Django App 등록 | 없음 |
| `/api/v1` Route 등록 | 없음 |
| Inquiry Runtime 테스트 | 0 |
| 실제 PostgreSQL 공통 환경 | 연결·Migration 기준선 검증 완료 |

[Inquiry 앱 디렉터리](../../../../../backend/apps/inquiries)의 도메인
Model·Repository·Service·API 파일은 현재 Placeholder다.
`readiness.py`는 누락을 진단하는 검사기이지 문의 Runtime이 아니다.
공통 PostgreSQL이 동작한다는 사실도 T-022 Model·Migration 완료로
계산하지 않는다.

## 3. 확정 API 기준선

[Inquiry OpenAPI Path](../../../../../contracts/api/paths/inquiries.yaml)에
다음 세 operation이 `CONFIRMED`로 작성되어 있다.

| Method | Path | 계약 상태 | 역할 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/inquiries` | `CONFIRMED` | 신규 문의 생성 |
| `PATCH` | `/api/v1/inquiries/{id}/questionnaire` | `CONFIRMED` | 원문·문진 누적 |
| `POST` | `/api/v1/inquiries/{id}/action-results` | `CONFIRMED` | 자가조치 결과 누적 |

세 API는 최지용 확정 명세를 구현하기 위한 기준선이다. 남은 과제는
Model·Migration·Service·Route·테스트 구현과 Runtime 정합성
검증이다.

## 4. 현재 미구현 항목

1. `Inquiry`, `SymptomEntry`, `FollowupAnswer`,
   `CustomerActionResult` 실질 Model
2. 번호 Migration과 App 등록
3. 고객 본인 범위 Repository·Permission
4. 동일 `inquiry_id` 누적 Service와 Transaction
5. Serializer·View·URL
6. Runtime 단위·API·PostgreSQL 테스트

생성 요청의 대표 증상은 단수 선택 필드
`representative_symptom_code`로 확정되었으며 선택 입력이다. 채널·결과
코드와 DateTime 표현도 확정 API 명세와 테이블 명세를 같은 값으로
옮기면서 정합화한다. 과거 후보였던 복수 `symptom_codes` 같은 임시
필드를 별도 표준처럼 추가하지 않는다.

## 5. 착수 순서

업무계획에 따라 T-005 Wave 1과 Wave 2 검증을 마친 뒤 T-022를
착수한다.

| 순서 | 작업 | 즉시 검증 |
| ---: | --- | --- |
| 1 | Inquiry Model·Constraint | Model 단위 테스트 |
| 2 | 번호 Migration·App 등록 | `makemigrations --check`, 빈 DB Migration |
| 3 | Repository·Service | 동일 ID 누적·Rollback 테스트 |
| 4 | 고객 본인 Permission | 본인 성공·타인 차단 테스트 |
| 5 | Serializer·View·URL | 세 API 계약·오류 응답 테스트 |
| 6 | PostgreSQL 수직 Smoke | 생성→문진→자가조치 누적 확인 |
| 7 | 전체 회귀 | Backend 전체 테스트 |

## 6. 완료 기준

- 자연어 문의가 비어 있지 않은 원문으로 저장된다.
- 문진과 자가조치 결과가 동일 `inquiry_id`에 누적된다.
- 다른 고객의 문의는 조회·수정할 수 없다.
- 제품 차단 조건에서는 AI·RAG 호출이 발생하지 않는다.
- 실패 시 반쪽 데이터가 남지 않는다.
- 세 Runtime Route가 OpenAPI와 일치한다.
- 실제 PostgreSQL에서 Migration과 수직 Smoke가 통과한다.

현재 변경의 저장소 전체 Backend 회귀는 `239 passed`다. 다만 이 수치의
T-022 검사는 계약·준비도 검사이며 Inquiry Runtime 구현 파일은 여전히
0개이므로 T-022 Runtime 완료 증거로 사용하지 않는다.

## 7. 연결 문서

- [API 계약 개발·인계 가이드](api_contract_handover_guide.md)
- [DB Schema 개발·인계 가이드](database_schema_handover_guide.md)
- [T-023 Workflow 구현 준비도](t-023-workflow-readiness.md)
- [T-022 준비도 검사](../../../../../backend/apps/inquiries/readiness.py)
- [T-022 준비도 테스트](../../../../../backend/tests/unit/inquiries/test_t022_readiness.py)

## 8. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 윤승혁(PM) | 문의 생성·문진·자가조치 후 호출할 이벤트와 필요한 `allowed_actions` | 확정된 T-023 상태·이벤트·Guard·역할 규칙과 T-022 연결 지점을 소비 검증 | 계약 값 존재, Loader·참조 무결성 검사 통과 | PM 계약 입력 존재·기계 검증 통과, Runtime 연결 전 |
| 이동윤 | 문의·제품·증상 입력 DTO, AI Timeout·오류·Fallback 저장 경계 | AI Schema·오류 응답·Fixture를 확정 필드와 정렬 | 정상·누락·Timeout·Fallback 계약 검사 통과 | 검토 미요청 또는 증거 미확인 |
| 김은진 | 인증·소유권·Transaction·Migration·PostgreSQL 수직 시나리오 | 생성→문진→자가조치, 타 고객 차단, Rollback을 실제 PostgreSQL에서 검증 | 수직 Smoke와 관련 자동 테스트 통과 | Runtime 미구현으로 실행 전 |
| 한예나 | Web용 문의 DTO·오류·상태·`409` 예시 | Web Client에서 계약을 소비하고 차이를 재현 사례로 전달 | Web 요청·응답·오류 처리가 OpenAPI와 일치 | Runtime 인계 전 |
| 양정현 | Mobile용 문의·문진·자가조치 DTO와 인증·오류 예시 | Mobile Mock을 Runtime 계약으로 교체하고 차이를 재현 사례로 전달 | Mobile 요청·응답·오류 처리가 OpenAPI와 일치 | Runtime 인계 전 |

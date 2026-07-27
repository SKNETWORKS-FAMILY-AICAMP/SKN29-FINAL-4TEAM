# 최지용 개발문서

> 기준일: 2026-07-27
> 작성·유지 책임: 최지용
> 산출물 범위: Backend · Database · API 계약
> 검토 상태: 미요청 또는 검토 증거 미확인
> 문서 정책: 현재 실행 기준과 검증 근거가 있는 최신본만 유지한다.

## 문서 범위

이 README는 개인 개발문서의 진입점만 제공한다. Runtime 수치, 테스트
결과, 구현 테이블 수와 다음 작업 순서는 이 파일에 중복 기록하지 않고
아래 목적별 최신 문서에서 확인한다. API·DB·ADR·인계의 팀 공용 기준선은
공용 경로에 유지하고 이 디렉터리에서는 상대 링크로만 참조한다.

`docs/**`는 공용 편집 영역이다. 따라서 이 디렉터리를 최지용의 배타적
소유 경로로 해석하지 않고, 아래 문서의 **작성·유지 책임과 산출물
주담당이 최지용**임을 뜻한다.

## 지침 적용 우선순위

겹치는 내용은 문서 전체에 하나의 순위를 기계적으로 적용하지 않고,
판단 항목별로 다음 순서를 사용한다.

| 판단 항목 | 1순위 | 보조 기준 |
| --- | --- | --- |
| 현재 작업 순서·완료 경계 | `최지용_업무계획표_v0.5.md` | 같은 버전의 Excel 시트, 3주차 업무 지침서 |
| 역할·협업자·검토자 | `팀원별 관할 영역.md`의 가장 구체적인 경로 규칙 | v0.5에서 확정한 최지용 산출물 책임 |
| PR·리뷰·보안·테스트 절차 | `공통 개발 규칙.md` | 저장소의 실제 설정과 자동화 결과 |
| 디렉터리·계약 원본 위치 | 현재 저장소 구조와 `프로젝트 디렉토리 구조.md` | 가장 가까운 상위 경로의 관할 |
| Runtime·진행도·테스트 수치 | 최신 실행 결과와 아래 검증 보고서 | 계획 문서의 수치는 목표 또는 당시 스냅샷으로만 사용 |

동일한 v0.5 파일끼리 충돌하면 더 나중에 수정된 Markdown의 실행 방향을
우선하고, Excel의 `확정_실행기준`·`연동_공유` 시트는 역할 및 인계
매트릭스를 보완하는 자료로 사용한다. `최지용_3주차_업무_지침서.md`의
WBS 목적은 유지하되, 현재 순서와 상태는 v0.5 및 실제 검증 결과로
갱신한다.

## 책임·협업·검토 원칙

| 구분 | 책임 |
| --- | --- |
| ERD·테이블·API 명세, Django, 로컬 PostgreSQL | 최지용이 작성·구현·내용 의사결정 |
| State Machine 업무 규칙 | 윤승혁(PM)이 내용 의사결정, 최지용이 Backend 반영 |
| AI Schema·AI 연동 계약 | 이동윤이 주담당, 최지용이 DB/API 경계 교차 검토 |
| Migration·Fixture·통합·재현 QA | 김은진이 검토, 최지용이 결과 반영 |
| Web 소비 호환성 | 한예나가 검토·연동 |
| Mobile 소비 호환성 | 양정현이 검토·연동 |
| PR 병합 | 작성자 외 1명 이상 리뷰 후 윤승혁(PM)이 `main` 병합 |

팀원의 검토는 통합·재현·소비 호환성을 확인하는 절차이며, 최지용이
담당 산출물을 작성하기 위한 선행 승인 절차가 아니다. 실제 PR·Issue·
커밋 등 검토 증거가 연결되기 전에는 `검토 완료`로 기록하지 않는다.
현재 이 디렉터리의 문서는 모두 `미요청 또는 검토 증거 미확인` 상태를
기본값으로 삼는다.

## 최신 문서

| 구분 | 문서 | 용도 |
| --- | --- | --- |
| 실행·인계 | [Django·PostgreSQL 공유 패키지 인계서 v1.0](<manuals/20260727_최지용_Django_PostgreSQL_공유패키지_인계서_v1.0.md>) | 환경 구성부터 팀원 재현까지의 단일 실행 순서 |
| DB 검증 | [Django·PostgreSQL Migration 검증 보고서 v1.0](<manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md>) | PostgreSQL 적용 증거와 2/32 구현 경계 |
| Auth 검증 | [Auth API 계약·Runtime 정합화 보고서 v1.0](<manuals/20260727_최지용_Auth_API_계약_Runtime_정합화_보고서_v1.0.md>) | Auth 4개 계약·Route·보안·테스트 근거 |
| API 공통 | [API 계약 개발·인계 가이드](<technical/backend/api_contract_handover_guide.md>) | 계약·Route·테스트 동시 갱신 절차 |
| DB 공통 | [DB 스키마 개발·인계 가이드](<technical/backend/database_schema_handover_guide.md>) | Model·Migration·Seed의 Wave별 구현 절차 |
| DB↔AI | [T-005/T-006 정합성 검토](<technical/contracts/t-005-t-006-alignment-review.md>) | 확정 DB 계약과 남은 AI Schema 차이 |
| T-022 | [문의 관리 현재 준비도](<technical/backend/t-022-inquiry-readiness.md>) | 구현된 것과 미구현 Runtime 범위 |
| T-023 | [Workflow 현재 준비도](<technical/backend/t-023-workflow-readiness.md>) | PM 입력과 Backend 구현 경계 |

## 공용 기준 문서

| 기준 | 링크 |
| --- | --- |
| Public API 명세 | [WaterCare API 명세](<../../api/watercare_api_specification.md>) |
| 기계 판독 API 계약 | [OpenAPI](<../../../contracts/api/openapi.yaml>) |
| PM State 업무 규칙 | [State Machine 계약](<../../../contracts/state-machine/README.md>) |
| AI 입출력 Schema | [AI 계약](<../../../contracts/ai/README.md>) |
| ERD·테이블 명세 패키지 | [T-005 데이터 설계](<../../database/t-005/README.md>) |
| 공개 테이블 사전 | [WaterCare 테이블 명세](<../../database/watercare_table_dictionary.md>) |
| 데이터 계약 결정 | [ADR 0008](<../../adr/0008-t005-data-contract-decisions.md>) |
| JWT·RBAC 결정 | [ADR 0009](<../../adr/0009-t017-jwt-rbac-owner-baseline.md>) |
| 팀 인계 진입점 | [현재 작업 인계](<../../handoffs/README.md>) |

## 문서 사용 순서

1. 새 환경에서는 공유 패키지 인계서만 따라 PostgreSQL·Django·Seed·Smoke를 재현한다.
2. DB 작업은 DB 스키마 가이드의 한 Wave를 구현하고 Migration 보고서 기준으로 즉시 검증한다.
3. API 작업은 API 계약 가이드대로 명세·OpenAPI·Route·테스트를 한 변경 단위로 맞춘다.
4. T-022와 T-023은 각 준비도 문서의 미구현 항목을 한 수직 흐름씩 처리한다.
5. 새 누적 일지나 중복 인계서를 만들지 않고 위 최신 문서에 현재 결과만 갱신한다.

## 인계 라우팅

| 산출물 | 작성·내용 책임 | 협업·검토 요청 대상 | 인계 대상과 완료 확인 |
| --- | --- | --- | --- |
| Django·PostgreSQL 공유 패키지 | 최지용 | 윤승혁(PM)·김은진 | 전 팀원이 같은 Git 기준에서 실행하고, 담당 영역의 재현 결과 또는 이슈를 회신 |
| Migration 검증 | 최지용 | 김은진, 윤승혁(PM), 이동윤 | 김은진의 빈 PostgreSQL 재현, 윤승혁(PM)의 Workflow 영향 확인, 이동윤의 Vector/Evidence 경계 확인 |
| Auth 계약·Runtime | 최지용 | 윤승혁(PM)·김은진 | 한예나·양정현이 4개 Endpoint·JWT Header·오류 예시를 소비하고 호환성 결과를 회신 |
| API 계약 가이드 | 최지용 | 윤승혁(PM)·김은진·이동윤 | 한예나·양정현에게 Method·Path·DTO·오류·예시·테스트 계정을 함께 전달 |
| DB 스키마 가이드 | 최지용 | 김은진·윤승혁(PM)·이동윤 | Migration·Fixture·Workflow·Vector/Evidence 영향과 재현 결과를 각각 회신 |
| T-005/T-006 정합성 | DB 측 최지용, AI Schema 측 이동윤 | 김은진, 충돌 시 윤승혁(PM) | 최지용 확정 필드·Enum → 이동윤 Schema·Fixture → 최지용 재검사 → 김은진 계약 테스트 |
| T-022 문의 관리 | 최지용 | 윤승혁(PM)·이동윤·김은진 | 한예나·양정현에게 3개 API·DTO·오류를 전달하고 수직 흐름 재현 결과를 회신 |
| T-023 Workflow | 업무 규칙 윤승혁(PM), Backend 최지용 | 김은진·이동윤 | 한예나·양정현에게 `allowed_actions`·`state_version`·409 예시를 전달하고 동시성·소비 호환성 확인 |

각 인계에는 다음 정보를 빠짐없이 포함한다.

1. 기준 Branch·Commit 또는 PR과 변경 범위
2. 계약·Migration·환경 변수 이름의 상대 링크
3. 재현 명령, 기대 결과, 실제 테스트 결과
4. 구현 완료 범위, 미구현 범위, 알려진 위험
5. 수신자의 다음 행동과 완료 확인 방법
6. 오류가 있으면 재현 명령·응답 코드·Correlation ID

비밀값과 실사용 계정은 전달하지 않는다. 수신자 확인은 인계 완료
증거이지만 산출물 작성의 선행 조건은 아니며, 회신된 호환성 문제는
최지용이 해당 최신 문서와 구현에 다시 반영한다.

현행 Django Runtime은 `backend/**`, 기계 계약은 `contracts/**`를
기준으로 한다. 루트 `WaterCareBackend/**`와 구형 BAT 파일은 과거
Android 연동 starter 참고본이며 현재 구현·Migration·API·State·AI
계약의 원본으로 인계하지 않는다.

## 중복 방지 기준

- `docs/api`, `docs/database`, `contracts`, `docs/adr`의 팀 공용 기준선은
  이 디렉터리에 복사하지 않고 위 상대 링크로만 참조한다.
- 재현 가능한 실행 절차는 공유 패키지 인계서, DB 실행 증거는 Migration
  검증 보고서, Auth 실행 증거는 Auth 정합화 보고서를 각각 단일 원본으로
  유지한다.
- 반복 적용할 개발 방법은 `technical/` 가이드에, 특정 실행 결과는
  `manuals/` 보고서에 기록해 같은 내용을 두 파일에 병렬로 누적하지 않는다.
- 새 버전이 현재 기준이 되면 이전 내용을 최신 문서에 병합하고 README의
  진입 링크도 함께 갱신한다.
- 다른 `docs/**` 문서에서 이 개발문서를 안내할 때는 복제본을 만들지 않고
  이 디렉터리의 단일 원본을 상대경로로 연결한다.

## 경로 규칙

- Markdown 링크는 이 문서가 있는 저장소를 기준으로 한 상대 경로만 사용한다.
- `C:\...`, `C:/...`, `file://...` 형식의 개인 PC 파일 링크를 사용하지 않는다.
- 링크 대상도 같은 저장소와 PR에 포함해 다른 팀원이 Git Pull 직후 열 수 있게 한다.
- `http://127.0.0.1` 같은 로컬 서비스 주소는 실행 Endpoint이므로 파일
  하이퍼링크 금지 규칙과 구분한다.
- 실행 명령은 저장소 루트 또는 `backend` 기준으로 작성하며 개인 PC 절대경로를 기록하지 않는다.
- `.env`의 실제 비밀값은 문서·로그·Git에 남기지 않는다. 변수 목록은 [`.env.example`](<../../../backend/.env.example>)을 기준으로 한다.

현재 검증 결과:

| 검사 | 결과 |
| --- | ---: |
| 개인 개발문서 | 9개 |
| 저장소 내부 파일 링크 | 117개 |
| 고유 링크 대상 | 66개 (파일 62·디렉터리 4) |
| 절대 파일 하이퍼링크 | 0개 |
| 깨진 상대 링크 | 0개 |

상대경로 형식과 로컬 대상 존재 여부는 모두 정상이다. 새 문서와 새 링크
대상은 이 문서들과 같은 PR 또는 선행 PR에 포함해야 다른 팀원의 Git
Pull 환경에서도 실제로 열린다.

## 2026-07-27 정리 기록

- 29개였던 개인 문서를 현재 유효한 9개로 축약했다.
- 구형 T-016/T-017 준비도, 과거 인계서, 단계별 환경·Seed·Smoke 문서는 최신 3개 매뉴얼에 병합했다.
- 명세 작성을 불필요하게 멈추던 표현, 과거 테스트 수치와 현재 구현에 맞지 않는 착수 차단 기록을 제거했다.
- 저장소 밖 링크와 개인 PC 절대경로를 남은 문서에서 제거했다.

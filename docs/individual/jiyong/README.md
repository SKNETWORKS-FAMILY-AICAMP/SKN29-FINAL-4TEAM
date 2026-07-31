# 최지용 개발문서

> 기준일: 2026-07-31
> 작성·유지 책임: 최지용
> 산출물 범위: Backend · Database · API 계약
> 검토 상태: WaterBridge 전환·T-005 계약 테이블 32/32·Active 13·Target-only 19·Seed·격리 Importer·전체 회귀 로컬 검증 완료 / 비작성자 독립 재현·계약 완료 승인·PM 병합 대기
> 문서 정책: 현재 실행 기준과 검증 근거가 있는 최신본만 유지한다.

## 2026-07-31 WaterBridge 현재 실행 기준

아래 기준이 이 README의 2026-07-29~30 `watercare` 실행 이력보다
우선한다. 현재 PostgreSQL **database는 `waterbridge`**, 그 안의
**schema는 `public`**이다. Docker Volume
`watercare-postgres-data`와 과거 검증 DB·문서의 `watercare` 명칭은
역사·인프라 식별자이므로 일괄 변경하지 않는다.

| 항목 | 현재 검증 결과 |
| --- | --- |
| Python 패키지 기준 | Python 3.13.13·constraints **32개** |
| PostgreSQL | `waterbridge.public`, PostgreSQL 16.14, pgvector 0.8.6 |
| T-005 물리 계약 | **32/32**, Auditor `READY`, blocker 0 |
| Active MVP | 13개 테이블·총 369행 — 현재 데이터 생성·조회 범위 |
| Target-only | 19개 테이블을 물리적으로 유지, 각 테이블 **0행** |
| 기본 DB Seed | 5종 2회, 2회차 비의도 신규 생성 0 |
| 격리 Importer | Source 367, 1차 Created 355·Projected 12, Replay Unchanged 355·Projected 12 |
| Backend 회귀 | 표적 API 21 passed·SQLite 740 passed/11 skipped·PostgreSQL 751 passed |
| Data·Smoke | Data 67 tests OK·E2E 17/17 PASS·Health/Auth Smoke PASS |
| 공식 완료 | **PENDING** — 비작성자 독립 재현·외부 소비 검증·PM 완료 리뷰 필요 |

Active 13은 32개 중 현재 데이터가 있는 테이블을 뜻한다. Target-only
19개를 삭제하거나 Migration을 되돌리거나 별도 schema로 분리하지
않는다. 데이터·기능·소비 계약이 준비된 순서대로 하나씩 활성화한다.

전환 범위, 백업·실제 Restore, 32/13/19 행 수, 복구 절차와 팀 실행
명령은
[WaterBridge DB 전환·Active 범위 검증서](technical/backend/20260731_waterbridge_database_transition_and_active_scope_validation.md)를
현재 단일 기준으로 사용한다. T-005는 기술적으로 준비됐지만 위 공식
승인 증거가 기록되기 전에는 `TECHNICALLY_COMPLETE_REVIEW_PENDING`이다.

## 2026-07-31 다음 Backend P0 기준

WaterBridge 전환 뒤에는 32개 물리 테이블을 다시 변경하지 않고,
기능별 작은 Slice를 `설계 → 검토 → 구현 → 즉시 검증` 순서로
진행한다.

| 순서 | 현재 산출물 | 판정 | 다음 담당 |
| ---: | --- | --- | --- |
| 1 | [Backend 구조화 로그 민감정보 비노출 감사](technical/backend/20260731_backend_log_security_audit.md) | 현재 Request·Exception 로그 `PASS`; T-024 전체는 미구현 | 최지용 유지·김은진 통합 환경 검토 |
| 2 | [T-017A 합성 사용자 계정 관리 OWNER 설계](technical/backend/20260731_t017a_account_management_owner_design.md) | `OWNER_DESIGN_READY_REVIEW_PENDING`; T-017B/C는 미구현 | 윤승혁 정책 검토·김은진 Migration/QA 검토 |
| 3 | `SUBMIT_SYMPTOM` 첫 수직 Slice 설계·구현 | 현재 Runtime 미구현 | PM State 계약과 OpenAPI를 유지해 최지용이 순차 구현 |

T-017A 설계 문서의 `is_synthetic`, `auth_version`, 계정 감사 원장과
오류 코드는 모두 **제안·후속 구현 대상**이다. 현재 Model·Migration·
Machine Contract에 이미 존재한다고 간주하지 않는다. T-017B·T-017C
일정을 앞당겨 한 Commit에 섞지 않는다.

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
| 현재 작업 순서·완료 경계 | 2026-07-31 `최지용_업무계획표_v0.9.md` | 같은 버전의 Excel 시트, 3주차 업무 지침서 |
| 역할·협업자·검토자 | `팀원별 관할 영역 v2.md`의 가장 구체적인 경로 규칙 | v0.6에서 확정한 최지용 산출물 책임 |
| PR·리뷰·보안·테스트 절차 | `공통 개발 규칙.md` | 저장소의 실제 설정과 자동화 결과 |
| 디렉터리·계약 원본 위치 | 현재 저장소 구조와 `프로젝트 디렉토리 구조 v2.md` | 가장 가까운 상위 경로의 관할 |
| Runtime·진행도·테스트 수치 | 최신 실행 결과와 아래 검증 보고서 | 계획 문서의 수치는 목표 또는 당시 스냅샷으로만 사용 |

동일한 v0.9 파일끼리 충돌하면 더 나중에 수정된 Markdown의 실행 방향을
우선하고, Excel 시트는 역할 및 인계 매트릭스를 보완하는 자료로
사용한다. `최지용_3주차_업무_지침서.md`의 WBS 목적은 유지하되,
현재 순서와 상태는 v0.9 및 실제 검증 결과로
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
현재 Backend·PostgreSQL·Data 자동 검증은 완료했지만, 비작성자의
독립 PostgreSQL·Seed 재현과 계약 완료 리뷰, PM 병합은 남아 있다.
따라서 현재 문서는 `로컬 기술 검증 완료`와 `팀 검토·공식 완료`를
구분한다.

## 2026-07-30 T-005 32/32 최종 로컬 기술 검증

아래 상태가 이 README의 과거 10/32·12/32·13/32 절보다 우선한다.
과거 Wave 절은 문제 해결과 증가 과정을 보존하는 실행 이력이다.

| 항목 | 현재 판정 |
| --- | --- |
| 계약 테이블 | **32/32** Model·App Registry·Migration |
| T-005 Auditor | `READY`, blocker 0 |
| Accounts | 내부 BigInt PK·공개 UUID·업무 코드 분리 |
| JWT | UUID-only subject, Legacy 문자열 fallback 제거 |
| PostgreSQL | 빈 DB 전체 Migration·5종 Seed 2회, 기본 `watercare` 백업·24개 Migration 동기화 |
| 합성 Handoff | 367건 2회, 2회차 355 unchanged·12 projected |
| Vector | pgvector 0.8.6·`vector(1024)`·Exact Search |
| Backend 전체 회귀 | SQLite `740 passed, 11 skipped`·PostgreSQL `751 passed` |
| Data QA | 오류·경고 0, 대표 E2E 17/17, 67 tests OK |
| 직접 실행 | Health 200·Demo Login·UUID JWT·`/me` PASS |
| 공식 완료 | `PENDING` — 비작성자·외부 리뷰와 계약 완료 승인 필요 |

작업 범위, PostgreSQL 건수, 연쇄 오류와 해결, 남은 공식 Gate, 팀 인계는
[T-005 최종 검증 보고서](technical/backend/t005_final_32_table_postgresql_seed_importer_validation_report.md)를
단일 원본으로 사용한다.

## 2026-07-30 공통코드 Local Wave — 역사 스냅샷

> 아래 값은 해당 Wave 직후 수치다. 현재 판정은 위 32/32 최종 로컬
> 기술 검증 절과 최종 보고서를 우선한다.

| 항목 | 당시 Wave 판정 |
| --- | --- |
| 구현 테이블 | `common_code_group`, `common_code` |
| T-005 | `12/32`, 미구현 20 — 전체 `NOT_READY` |
| 식별자 | Group 자연키 예외, Code 내부 bigint PK + 공개 UUID |
| PostgreSQL | 빈 DB 전체 Migration·기본 DB 백업 후 적용 통과 |
| Seed | 10 Group·43 Code, 2회차 신규 0 |
| 관련 검증 | 63 passed |
| Backend 전체 회귀 | 418 passed |
| 공유 상태 | `LOCAL_VERIFIED`, Push·독립 QA·PM 병합 전 |
| 차단 | 위험도 소문자 계약, AI Stage Group Mapping |

실행·제약·차단·인계의 단일 기술 원본은
[T-005 공통코드 Registry 구현·재현 가이드](<technical/backend/t005_common_code_registry_implementation.md>)다.

## 2026-07-30 T-005 Wave 1A — 문진 세션 역사 스냅샷

> 아래 값은 Wave 1A 직후 수치다. 현재 판정은 위 32/32 최종 로컬
> 기술 검증 절과 최종 보고서를 우선한다.

| 항목 | 당시 Wave 판정 |
| --- | --- |
| 구현 테이블 | `support_questionnaire_session` |
| T-005 | `13/32`, 미구현 19 — 전체 `NOT_READY` |
| 식별자 | 내부 bigint PK + 공개 UUID + 업무 번호 |
| PostgreSQL | 빈 DB 전체 Migration, JSON object 물리 CHECK 실측 통과 |
| Seed | 기존 5종 2회, 2회차 신규 0, 문진 행 0 |
| 집중 검증 | 50 passed |
| Backend 전체 회귀 | 426 passed |
| Data 전체 회귀 | 67 passed·4 subtests passed, `data/**` 수정 없음 |
| 공유 상태 | `LOCAL_VERIFIED`, Push·독립 QA·PM 병합 전 |
| Wave 1A 당시 P0 | 동일 구독 복합 FK는 아래 Wave 1B에서 로컬 해결, 번호 생성 규칙·API·상태 전이는 잔여 |

구현·Migration·PostgreSQL 실측·알려진 계약 공백·인계의 단일 원본은
[T-005 Wave 1A 문진 세션 구현·재현 가이드](<technical/backend/t005_wave_1a_support_questionnaire_session_implementation.md>)다.

## 2026-07-30 T-005 Wave 1B — 문진·문의 동일 구독 복합 FK 역사 스냅샷

> 아래 값은 Wave 1B 직후 수치다. 현재 판정은 위 32/32 최종 로컬
> 기술 검증 절과 최종 보고서를 우선한다.

| 항목 | 당시 Wave 판정 |
| --- | --- |
| 구현 범위 | `support_inquiry(id, subscription_id)` UNIQUE + 문진 복합 FK |
| T-005 | 신규 테이블 없음, `13/32`, 미구현 19 — 전체 `NOT_READY` |
| PostgreSQL | 빈 DB 전체 Migration·catalog·rollback·재적용 통과 |
| 우회 차단 | ORM·raw SQL·부모 update 3종 모두 정확한 복합 FK 위반 |
| Seed | 기존 5종 2회, 2회차 신규 0, 문진 행 0 |
| 집중 검증 | 100 passed + PostgreSQL 전용 1 passed |
| Backend 전체 회귀 | 428 passed, PostgreSQL 전용 1 skipped |
| Data 전체 회귀 | 67 passed, Inquiry Crosswalk hash 공식 동기화 |
| 공유 상태 | `LOCAL_VERIFIED`, Push·독립 QA·PM 병합 전 |
| 후속 P0 | 번호 생성 규칙, API·상태 전이, UUID Bridge |

구현·실제 제약명·우회 검증·Data hash 연쇄 보정·rollback·인계의 단일
원본은 [T-005 Wave 1B 복합 FK 구현·재현 가이드](<technical/backend/t005_wave_1b_questionnaire_inquiry_composite_fk.md>)다.

## 2026-07-29 통합 후보 이력

아래 값은 2026-07-29 당시 공유 후보의 역사 증거다. 현재 값은 위의
2026-07-30 T-005 32/32 최종 로컬 기술 검증 절과 최종 보고서를
우선하며, 아래 10/32·397개 수치를 현재 완료율로 사용하지 않는다.

| 항목 | 당시 판정 |
| --- | --- |
| 기준 `main` | `0bcb8b514f2b0d1476882d926b667dbdb5d8c06a` |
| Crosswalk | v2.0.0, Backend Source 17개·Fixture Mapping 12개, `DB_FULL_VERIFIED` |
| PostgreSQL | 16.14, Smoke 37·Full 367·Replay 중복 생성 0 |
| Backend | `397 passed` |
| Data | `61 passed` |
| QA | 2회 연속 PASS, 오류 0·경고 0·대표 E2E 17/17 |
| T-005 | 32개 중 10개 구현, 22개 미구현 — `NOT_READY` |
| 다음 Gate | 김은진 Data Owner Review → 최지용 재검증 → PM `main` 병합 |

위 `DB_FULL_VERIFIED`는 합성 Handoff 367행의 격리 DB Import 범위다.
T-005 전체 완료를 뜻하지 않는다. 팀원은 현재 로컬 후보가 아니라
윤승혁 PM이 병합 후 전달한 40자리 `main` SHA를 공용 기준으로 사용한다.

## 최신 문서

| 구분 | 문서 | 용도 |
| --- | --- | --- |
| WaterBridge 현재 실행 기준 | [DB 전환·Active 범위 검증서](<technical/backend/20260731_waterbridge_database_transition_and_active_scope_validation.md>) | `waterbridge.public`, T-005 32/32·Active 13·Target-only 19, 백업·Restore·Seed·격리 Importer·전체 회귀·Rollback |
| T-005 최종 검증 | [32개 테이블·PostgreSQL·Seed·Importer 최종 보고서](<technical/backend/t005_final_32_table_postgresql_seed_importer_validation_report.md>) | 32/32 Auditor READY, 빈 DB·5종 Seed·367건 Replay·전체 회귀·공식 승인 대기 Gate |
| 문진 동일 구독 제약 | [T-005 Wave 1B 복합 FK 구현·재현 가이드](<technical/backend/t005_wave_1b_questionnaire_inquiry_composite_fk.md>) | 부모 UNIQUE·문진 복합 FK·PostgreSQL 우회 차단·rollback·Data hash 보정 |
| 문진 세션 Runtime | [T-005 Wave 1A 문진 세션 구현·재현 가이드](<technical/backend/t005_wave_1a_support_questionnaire_session_implementation.md>) | `support_questionnaire_session` Model·Migration·PostgreSQL CHECK와 Wave 1A 완료 경계 |
| 공통코드 Runtime | [T-005 공통코드 Registry 구현·재현 가이드](<technical/backend/t005_common_code_registry_implementation.md>) | 공통코드 2개 Model·Migration, 10 Group·43 Code Seed, PostgreSQL 재현과 차단 계약 |
| 합성 데이터 Runtime | [PostgreSQL 합성 Handoff Runtime 검증·인계서](<manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md>) | 격리 DB 367행 Import 검증과 기본 `watercare` 10개 Migration·Seed 후속 실측을 분리한 누적 증거 |
| 합성 데이터 Importer | [합성 Handoff Importer 개발 인계서](<technical/backend/20260729_synthetic_handoff_importer.md>) | 빈 격리 DB 전용 관리 명령, UUID 충돌 차단, 원장·멱등성과 dry-run Sequence 주의 |
| 합성 데이터 Schema | [합성 데이터 도메인 Schema·Migration 인계서](<technical/backend/20260729_synthetic_domain_schema_migration.md>) | 상담·방문·후속확인·Care·감사·Operations 원장과 `workflow.0003` 보정 Migration 체인 |
| 합성 데이터 QA | [Fixture Hash·Crosswalk 강화 인계서](<technical/contracts/20260729_data_qa_fixture_hash_hardening.md>) | 367건 불변식, semantic text hash, 계약·Crosswalk 정합성 |
| 합성 고객 Auth | [합성 고객 Demo Login 별칭 가이드](<manuals/20260729_synthetic_customer_auth_alias.md>) | `SYN-CUSTOMER-001` 공개 별칭과 내부 `CUS-*` 직접 로그인 차단 |
| 실행·인계 | [Django·PostgreSQL 공유 패키지 인계서 v1.3](<manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>) | 기본 DB Migration·Seed·복구와 격리 Import 경계를 포함한 현재 실행 절차의 단일 원본 |
| 환경 설계 | [Backend `.venv` 재현성과 VS Code 환경 설계](<technical/backend/backend_venv_reproducibility_guide.md>) | 서비스 경계·버전 잠금·자동화·검증·복구 기준 |
| DB 검증 | [Django·PostgreSQL Migration 검증 보고서 v1.0](<manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md>) | 2026-07-27 당시 PostgreSQL 적용과 2/32 구현의 역사 증거 |
| Auth 검증 | [Auth API 계약·Runtime 정합화 보고서 v1.0](<manuals/20260727_최지용_Auth_API_계약_Runtime_정합화_보고서_v1.0.md>) | Auth 4개 계약·Route·보안·테스트 근거 |
| API 현행 상태 | [API Runtime 구현 상태](<../../api/runtime_implementation_status.md>) | OpenAPI 9·Runtime 7·OpenAPI-only 2의 팀 공용 현재 상태 |
| API 정합 검증 | [Backend API 계약 정합화 검증보고서 v1.0](<manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md>) | 오류 Registry·JSON 22개·계약·권한·전체 회귀 실행 증거 |
| API 공통 | [API 계약 개발·인계 가이드](<technical/backend/api_contract_handover_guide.md>) | 계약·Route·테스트 동시 갱신 절차 |
| DB 공통 | [DB 스키마 개발·인계 가이드](<technical/backend/database_schema_handover_guide.md>) | Model·Migration·Seed의 Wave별 구현 절차 |
| DB↔AI | [T-005/T-006 정합성 검토](<technical/contracts/t-005-t-006-alignment-review.md>) | 확정 DB 계약과 남은 AI Schema 차이 |
| T-022 | [문의 관리 현재 준비도](<technical/backend/t-022-inquiry-readiness.md>) | 구현된 것과 미구현 Runtime 범위 |
| T-023 | [Workflow 착수 전 스냅샷](<technical/backend/t-023-workflow-readiness.md>) | 2026-07-27 역사 기록. 현재 상태는 API Runtime 상태표와 팀 인계 문서를 참조 |

## 팀원별 실행 인계

팀 공용 순서와 현재 Blocker는 [팀 인계 허브](<../../handoffs/README.md>)를
기준으로 한다. 아래 문서는 각 담당자가 자신의 Branch에서 실행하고
최지용에게 반환할 명령·증거·금지사항을 상세화한 보조 문서다.

| 대상 | 문서 | 현재 요청 |
| --- | --- | --- |
| 김은진 | [Data·QA Owner Review 인계](<team_handover/20260729_최지용_김은진_인계및요청사항.md>) | 기능·Data 기준 SHA의 19개 Data 소유 경로 검토와 QA 결과 반환 |
| 윤승혁(PM) | [병합 Gate·다음 Wave 결정 인계](<team_handover/20260729_최지용_윤승혁PM_인계및요청사항.md>) | Data Owner Review 확인 후 `main` 병합과 T-005·T-023 결정 |
| 한예나 | [Web Runtime 소비 인계](<team_handover/20260729_최지용_한예나_인계및요청사항.md>) | Runtime 7개 범위의 Auth·식별자·오류 처리 검증 |
| 양정현 | [Mobile DTO·Network 인계](<team_handover/20260729_최지용_양정현_인계및요청사항.md>) | 3모듈 기준 Auth·문의 START/CANCEL 연동과 두 App 검증 |
| 이동윤 | [AI Runtime·Schema 인계](<team_handover/20260729_최지용_이동윤_인계및요청사항.md>) | 재현 가능한 AI 실행 환경·Schema·Commit SHA 반환 |

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

1. 새 환경에서는 환경 설계 가이드로 Python·`.venv` 경계를 확인하고 공유 패키지 인계서 v1.3의 신규 환경 순서로 PostgreSQL·Django·Migration·Seed·Smoke를 재현한다.
2. 설치가 끝난 PC에서는 공유 패키지 인계서 v1.3의 일상 실행·종료 절차를 사용한다.
3. DB 작업은 DB 스키마 가이드의 한 Wave를 구현하고 현재 Runtime 검증서 기준으로 즉시 검증한다. 2026-07-27 Migration 보고서는 당시 기준선의 역사 증거로만 사용한다.
4. API 작업은 API 계약 가이드대로 명세·OpenAPI·Route·테스트를 한 변경 단위로 맞춘다.
5. T-022와 T-023은 각 준비도 문서의 미구현 항목을 한 수직 흐름씩 처리한다.
6. 합성 Importer는 현행 기본 `waterbridge`와 legacy 기본명 `watercare`에서 dry-run을 포함해 실행하지 않고 새 빈 격리 PostgreSQL에서만 검증한다.
7. 새 누적 일지나 중복 인계서를 만들지 않고 위 최신 문서에 현재 결과만 갱신한다.

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
| 개인 개발문서 | 51개 |
| Markdown 링크 | 692개 |
| 고유 저장소 내부 대상 | 309개 (파일 291·디렉터리 18) |
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

## 2026-07-28 환경 재현 기록

- Backend Python 3.13.13·pip 26.0.1·constraints 31개를 고정했다.
- 실제 `backend/.venv`를 안전 재생성하고 전체 `239 passed`를 확인했다.
- 환경 설계는 기술 가이드, 당시 팀 실행은 공유 패키지 인계서 v1.1로
  분리했으며 현재 유효 내용은 v1.3의 통합 버전 이력에 보존했다.

## 2026-07-29 환경·API 재검증 기록

- requirements fingerprint를 현재 입력과 동기화하고 빠른 환경 검사를 Exit code `0`으로 재확인했다.
- 전체 Backend `353 passed`, PostgreSQL 16.14 `healthy`, 적용 Migration 누락 없음과 Health·Auth Smoke `PASSED`를 확인했다.
- v1.1·v1.2의 별도 파일은 v1.3으로 통합했으며, 당시 실행 절차·검증
  수치·정책 변화는 v1.3의 통합 버전 이력에 보존한다.
- 위 `353 passed`와 v1.2 전환은 현재 기준이 아니라 같은 날의 이전
  검증 스냅샷이다.
- 후속 로컬 통합에서는 SQLite Backend `397 passed`와 PostgreSQL 16.14 읽기 전용 연결·적용 Migration 누락 0을 확인했다.
- 기본 `watercare`에 기존 미적용 9개와 `workflow.0003`을 적용하면서 기존 row count를 보존하고 Workflow `changed_at` 11건을 보정했으며, Demo Seed 4종을 2회 실행해 비의도 중복 0을 확인했다.
- 당시 실행 단일 원본은 v1.3이었으며, 기본 DB의 예상 UUID mismatch를 우회하지 않고 합성 Importer를 빈 격리 DB 전용으로 분리했다.

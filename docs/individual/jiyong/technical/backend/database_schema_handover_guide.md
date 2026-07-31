# Database Schema 개발·인계 가이드

> 기준일: 2026-07-31
> 담당: 최지용
> 적용 원칙: ERD와 테이블 명세는 확정 기준선이며, Model·Migration을 Wave별로 구현하고 즉시 검증한다.
> 현재 상태: 기본 PostgreSQL `waterbridge/public`, 계약 테이블 32/32,
> Active 데이터 13·Target-only 19(0행) 로컬 기술 검증 완료 /
> 비작성자·외부 리뷰와 공식 완료 승인 대기

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | 현행 Database Schema 개발·인계 기준 |
| 관련 WBS | `T-005`, `T-016`, `T-022`, `T-023` |
| 작성·유지 책임 | 최지용 |
| 산출물/내용 의사결정자 | 최지용: ERD·테이블 명세와 Model·Migration·Seed·PostgreSQL 반영 기준. 윤승혁(PM): Workflow 업무 규칙. 이동윤: Vector·Evidence·AI Schema |
| 협업 책임 | 김은진: Migration·Fixture·PostgreSQL Integration QA, 윤승혁(PM): Workflow 관계, 이동윤: Vector·Evidence 관계 |
| 검토 요청 대상 | 김은진: Migration·Seed·통합 재현, 윤승혁(PM): Workflow 관계 정합성, 이동윤: Vector·Evidence 연결 정합성 |
| 검토 상태 | 미요청 또는 증거 미확인 |
| PR 병합 담당 | 윤승혁(PM), 비작성자 1명 이상 리뷰 후 |
| 인계 대상 | 김은진, 윤승혁(PM), 이동윤 |

위 검토는 최지용의 ERD·테이블 명세·API 명세·Django·PostgreSQL
작성이나 구현을 시작하기 위한 선행 승인이 아니다. 각 담당자가
Migration 재현, Workflow 관계, Vector·Evidence 소비 호환성을
확인하는 절차다.

## 1. 단일 원본

| 산출물 | 원본 | 역할 |
| --- | --- | --- |
| DB 문서 안내 | [Database 문서](../../../../database/README.md) | 데이터 산출물 진입점 |
| 테이블 명세 | [WaterCare 테이블 명세](../../../../database/watercare_table_dictionary.md) | 컬럼·키·제약·Index 기준 |
| T-005 패키지 | [T-005 데이터 설계](../../../../database/t-005/README.md) | Manifest·논리/물리 계약·검증 절차 |
| 대화형 ERD | [WaterCare ERD](../../../../database/erd/watercare_erd.html) | 관계와 전체 컬럼 탐색 |
| 정적 ERD | [WaterCare ERD 이미지](../../../../database/erd/watercare_erd.png) | Git 미리보기 |
| API 설명 | [Public API 명세](../../../../api/watercare_api_specification.md) | DB 필드의 Public Projection |
| 기계 API 계약 | [OpenAPI](../../../../../contracts/api/openapi.yaml) | Serializer·응답 계약 |

ERD·테이블 명세·API 명세는 최지용 확정 산출물이다. 이 원본을
Model·Migration·Serializer에 순차 반영한다.

## 2. 현재 구현 상태와 실행 증거의 단일 원본

이 가이드에는 구현 Model 수, 적용 Migration, Seed 건수와 테스트 수를
복제하지 않는다. 현재 상태는 다음 문서에서 확인한다.

| 확인 목적 | 단일 원본 |
| --- | --- |
| 현재 DB 전환·32/13/19·복구·회귀 | [WaterBridge DB 전환 및 Active 범위 검증](20260731_waterbridge_database_transition_and_active_scope_validation.md) |
| 32/32 최종 구현·PostgreSQL·Seed·Importer·회귀 | [T-005 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md) |
| 설계 테이블·계약·결정 상태 | [T-005 데이터 설계](../../../../database/t-005/README.md) |
| 2026-07-27 Model·Migration 역사 기준 | [Migration 검증 보고서](../../manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md) |
| 현재 합성 Schema·Migration 체인 | [합성 데이터 도메인 Schema·Migration 인계서](20260729_synthetic_domain_schema_migration.md) |
| 현재 PostgreSQL 적용·Seed·Importer 경계 | [PostgreSQL 합성 Handoff Runtime 검증·인계서](../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md) |
| 환경 구성·Migration·Seed·Smoke 재현 순서 | [Django·PostgreSQL 공유 패키지 인계서 v1.3](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md) |
| 공통코드 구현·재현 | [T-005 공통코드 Registry 구현 가이드](t005_common_code_registry_implementation.md) |
| 문진 세션 Model·초기 Migration 구현·재현 | [T-005 Wave 1A 문진 세션 구현 가이드](t005_wave_1a_support_questionnaire_session_implementation.md) |
| 문진·문의 동일 구독 복합 제약 구현·재현 | [T-005 Wave 1B 복합 FK 구현 가이드](t005_wave_1b_questionnaire_inquiry_composite_fk.md) |

이 문서는 실행 결과 보고서가 아니라, 설계를 Model·Migration·Seed로
옮기고 검증하는 반복 절차의 단일 원본으로 유지한다.

## 3. 확정 데이터 기준

ID, 코드, Legacy 변환, 방문 일정, Enum과 Seed의 구체 값은 이 가이드에
복사하지 않는다. 활성
[결정 등록부 v0.3](../../../../database/t-005/t005_decision_register_v0.3.json)과
[물리 계약 v1.3](../../../../database/t-005/t005_physical_contract_v1.3.json)을
구현 입력으로 사용하고, 값이 바뀌면 해당 계약만 갱신한다. v0.1·v1.0은
역사본이며 신규 구현 입력으로 사용하지 않는다.

## 4. Wave별 구현 순서

2026-07-30의 잔여 20개는 활성 물리 계약의 FK 의존성을 기준으로 아래
순서로 구현했다. 새 스키마 증분도 같은 원칙으로 부모·Bridge·직접
자식·다중 관계 순서를 따른다.

| Gate·Wave | 대상 | 완료 검증 | 현재 |
| ---: | --- | --- | --- |
| Accounts Gate | User·CustomerProfile 내부 정수 PK, 공개 UUID, UUID-only JWT | Migration·Backfill·Auth 회귀 | 완료 |
| 1 | AI Run, Ingestion Batch, Visit Result, Questionnaire Session | 부모 FK·Bridge·번호 Migration | 완료 |
| 2 | Retrieval Run, Source Document, Guidance, Handoff, Inquiry QA, Status History, Assessment | 직접 자식 FK·이력 정렬 | 완료 |
| 3 | Document Model Scope, Document Page, Guidance Item | 상위 문서·안내 관계·순서 UNIQUE | 완료 |
| 4 | Document Chunk | Page·Chunk 원문·순서 정책 | 완료 |
| 5 | Retrieval Hit, Data Quality Issue, Chunk Embedding | 검색 Rank·품질 대상·pgvector 1024 | 완료 |
| 6 | Customer Action Result, Evidence Link | 고객 조치·최종 다중 FK·부분 UNIQUE | 완료 |
| Final Gate | 빈 PostgreSQL, Seed 2회, 367건 Import 2회, 전체 회귀 | Auditor READY·Data QA | 로컬 완료 |

한 Wave를 구현한 뒤 다음 순서로 검증하고, 통과하기 전에는 다음
Wave로 이동하지 않는다. 실행 전 PostgreSQL 상태는
[공유 패키지 인계서 v1.3](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)의
일상 실행 절차로 확인하며, 이 가이드에는 서버 시작·종료
명령을 중복하지 않는다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe -m pytest -q
```

## 5. Model·Migration 규칙

- 테이블·컬럼명과 nullability는 확정 테이블 명세를 따른다.
- Public ID를 내부 자동 증가 PK로 대체하지 않는다.
- FK·UNIQUE·CHECK·Index는 문서 설명에만 두지 않고 Migration에 둔다.
- Enum 값은 [공통 코드 계약](../../../../../contracts/codes)과 Django
  `TextChoices`를 일치시킨다.
- 상태 변경 Model은 이력과 `state_version`을 함께 고려한다.
- 개인정보·Token·비밀값을 Seed·Fixture·로그에 넣지 않는다.
- Django 내부 테이블은 32개 도메인 테이블 구현 개수에 포함하지 않는다.

## 6. Seed 규칙

- 실제 개인정보가 아닌 합성 데이터만 사용한다.
- 고정 합성 ID와 `update_or_create`로 반복 실행을 보장한다.
- 1차 실행은 생성 수, 2차 실행은 신규 0개와 갱신 수를 확인한다.
- Password·Token·DSN을 출력하지 않는다.
- 입력 계약이 달라지면 변환 규칙을 명시하고 Silent Dual-write를 금지한다.

현재 Demo Seed 결과와 재현 절차는
[Django·PostgreSQL 공유 패키지 인계서 v1.3](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)을
따른다.

Wave 1 공통코드는 Migration 통과 후 다음 명령을 두 번 실행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py seed_common_codes
.\.venv\Scripts\python.exe manage.py seed_common_codes
```

현재 확정 범위와 정상 경고, 기대 건수는
[공통코드 Registry 구현 가이드](t005_common_code_registry_implementation.md)를
따른다. 위험도 소문자 계약을 임의 변환하지 않으며, 계약에서 제거된
관리 Code는 삭제하지 않고 비활성화한다.

2026-07-31 현행 기본 DB는 `waterbridge`, Schema는 `public`이다.
T-005 계약 테이블 32개를 모두 유지하고 현재 데이터가 있는 13개만
Active 범위로 사용한다. Target-only 19개는 0행 상태로 보존하며
Migration에서 제외하거나 삭제하지 않는다.

기본 `waterbridge`에서는 Demo Seed 5종을 2회 실행해 2회차 신규 생성
0을 확인했다. 이 기본 DB에는 canonical fixture와 공개 UUID가 다른 기존
레코드가 있으므로 합성 Importer와 `--dry-run`은 실행하지 않는다.
Importer는 새 빈 격리 PostgreSQL 전용이며, dry-run도 Sequence 값을
변경할 수 있다. Legacy `watercare`도 안전상 기본 DB로 취급하여
Importer 실행 대상에서 제외한다.

2026-07-29 기본 `watercare`에서 Demo Seed 4종을 2회 실행한 기록은
당시 실행 증거이며 변경하지 않는다. 현재 명령과 결과는
[WaterBridge DB 전환 및 Active 범위 검증](20260731_waterbridge_database_transition_and_active_scope_validation.md)을
따른다.

## 7. 검증 체크리스트

아래는 매 변경에서 다시 사용하는 체크리스트다. 2026-07-30 현재
32/32 구현에 대한 실제 통과 항목과 공식 승인 대기 항목은
[최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)의
최종 체크리스트를 사용한다.

- [ ] Model 수와 대상 테이블을 기록했다.
- [ ] Model과 Migration 사이에 변경 누락이 없다.
- [ ] `operations.0001`, 불변 복원된 `workflow.0004`, 증분
  `workflow.0005`를 포함한 현재 Migration graph를 적용했다.
- [ ] 빈 PostgreSQL에서 Migration이 처음부터 적용된다.
- [ ] PK·FK·UNIQUE·CHECK·Index가 명세와 일치한다.
- [ ] Seed 2회 후 비의도 중복이 없다.
- [ ] API Schema·Serializer가 같은 필드와 Enum을 사용한다.
- [ ] 실제 개인정보·Token·비밀값이 없다.
- [ ] 현재 구현 개수와 남은 테이블 개수를 분리해 기록했다.
- [ ] 기본 `waterbridge` Migration·Demo Seed와 빈 격리 DB Import 검증을 분리했다.
- [ ] 계약 테이블 32개, Active 데이터 13개, Target-only 19개(0행)를
  서로 다른 의미로 기록했다.

현재 테스트 수, PostgreSQL 적용 범위와 미구현 테이블 수는 이 가이드에
복제하지 않고
[PostgreSQL 합성 Handoff Runtime 검증·인계서](../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md)를
참조한다. 이전 [Migration 검증 보고서](../../manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md)의
수치는 2026-07-27 역사 기록으로 보존한다. 변경 PR에는 해당 Wave에서
다시 실행한 결과만 기록한다.

상태 이력 Migration의 과거 파일 불변성과 증분 복구 근거는
[Migration 불변성 복구 보고서](t005_wave_2e_migration_immutability_repair.md)와
[workflow.0005](../../../../../backend/apps/workflow/migrations/0005_status_history_contract_names_indexes.py)를
따른다.

## 8. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 김은진 | 영향 테이블·컬럼, Model·Migration, 적용 순서, Seed·Rollback, PostgreSQL 결과 | 빈 PostgreSQL Migration, Seed 2회, 제약·통합 테스트를 재현 | Migration drift 0, 비의도 중복 0, 실행 증거 기록 | Wave별 인계 전 또는 증거 미확인 |
| 윤승혁(PM) | 문의·상담·방문·상태 이력 관계와 Workflow 영향 | State 업무 규칙이 DB 관계·이력·완료 정책과 충돌하지 않는지 확인 | 관계 불일치 0건 또는 결정 기록 반영 | 검토 미요청 또는 증거 미확인 |
| 이동윤 | Knowledge·Document·Page·Chunk·Embedding·Evidence·AI Run 연결 키와 Enum | Vector·Evidence·AI Schema에서 동일 키·버전·Enum을 소비 | DB↔AI 필드·Enum·참조 무결성 검사 통과 | 관련 Wave 구현 전 또는 증거 미확인 |

인계 시 확정 명세 링크, 이번 Wave에서 의도적으로 구현하지 않은 범위,
API·상태·AI 계약 영향을 함께 전달한다. 팀원은 같은 상대경로 원본과
명령으로 재현하며 개인 PC 절대경로나 비밀값을 문서에 추가하지 않는다.

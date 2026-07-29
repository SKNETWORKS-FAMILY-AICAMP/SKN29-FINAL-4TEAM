# Database Schema 개발·인계 가이드

> 기준일: 2026-07-27
> 담당: 최지용
> 적용 원칙: ERD와 테이블 명세는 확정 기준선이며, Model·Migration을 Wave별로 구현하고 즉시 검증한다.

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
| 설계 테이블·계약·결정 상태 | [T-005 데이터 설계](../../../../database/t-005/README.md) |
| 실제 Model·Migration·PostgreSQL 적용 범위 | [Migration 검증 보고서](../../manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md) |
| 환경 구성·Seed·Smoke 재현 순서 | [Django·PostgreSQL 공유 패키지 인계서 v1.2](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md) |

이 문서는 실행 결과 보고서가 아니라, 설계를 Model·Migration·Seed로
옮기고 검증하는 반복 절차의 단일 원본으로 유지한다.

## 3. 확정 데이터 기준

ID, 코드, Legacy 변환, 방문 일정, Enum과 Seed의 구체 값은 이 가이드에
복사하지 않는다. [결정 등록부](../../../../database/t-005/t005_decision_register_v0.1.json)와
[물리 계약](../../../../database/t-005/t005_physical_contract_v1.0.json)을
구현 입력으로 사용하고, 값이 바뀌면 해당 계약만 갱신한다.

## 4. Wave별 구현 순서

| Wave | 대상 | 완료 검증 |
| ---: | --- | --- |
| 1 | 공통 코드, User, CustomerProfile | Migration·PK·UNIQUE·CHECK·Seed |
| 2 | ProductModel, CustomerSubscription, CareRecord | FK·삭제 정책·중복 방지 |
| 3 | Inquiry, Symptom, QA, Assessment, Guidance | 단일 Inquiry 추적·입력 누적 |
| 4 | Consultation, Handoff, Visit, Follow-up, 상태 이력 | Transaction·상태 전이·멱등성 |
| 5 | Knowledge, Document, Chunk, Embedding, Evidence, AI Run | pgvector·근거 추적·버전 |

한 Wave를 구현한 뒤 다음 순서로 검증하고, 통과하기 전에는 다음
Wave로 이동하지 않는다. 실행 전 PostgreSQL 상태는
[공유 패키지 인계서 v1.2](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md)
6장의 일상 실행 절차로 확인하며, 이 가이드에는 서버 시작·종료
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
[Django·PostgreSQL 공유 패키지 인계서 v1.2](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md)를
따른다.

## 7. 검증 체크리스트

- [ ] Model 수와 대상 테이블을 기록했다.
- [ ] Model과 Migration 사이에 변경 누락이 없다.
- [ ] 빈 PostgreSQL에서 Migration이 처음부터 적용된다.
- [ ] PK·FK·UNIQUE·CHECK·Index가 명세와 일치한다.
- [ ] Seed 2회 후 비의도 중복이 없다.
- [ ] API Schema·Serializer가 같은 필드와 Enum을 사용한다.
- [ ] 실제 개인정보·Token·비밀값이 없다.
- [ ] 현재 구현 개수와 남은 테이블 개수를 분리해 기록했다.

현재 테스트 수, PostgreSQL 적용 범위와 미구현 테이블 수는 이 가이드에
복제하지 않고
[Migration 검증 보고서](../../manuals/20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md)를
참조한다. 변경 PR에는 해당 Wave에서 다시 실행한 결과만 기록한다.

## 8. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 김은진 | 영향 테이블·컬럼, Model·Migration, 적용 순서, Seed·Rollback, PostgreSQL 결과 | 빈 PostgreSQL Migration, Seed 2회, 제약·통합 테스트를 재현 | Migration drift 0, 비의도 중복 0, 실행 증거 기록 | Wave별 인계 전 또는 증거 미확인 |
| 윤승혁(PM) | 문의·상담·방문·상태 이력 관계와 Workflow 영향 | State 업무 규칙이 DB 관계·이력·완료 정책과 충돌하지 않는지 확인 | 관계 불일치 0건 또는 결정 기록 반영 | 검토 미요청 또는 증거 미확인 |
| 이동윤 | Knowledge·Document·Page·Chunk·Embedding·Evidence·AI Run 연결 키와 Enum | Vector·Evidence·AI Schema에서 동일 키·버전·Enum을 소비 | DB↔AI 필드·Enum·참조 무결성 검사 통과 | 관련 Wave 구현 전 또는 증거 미확인 |

인계 시 확정 명세 링크, 이번 Wave에서 의도적으로 구현하지 않은 범위,
API·상태·AI 계약 영향을 함께 전달한다. 팀원은 같은 상대경로 원본과
명령으로 재현하며 개인 PC 절대경로나 비밀값을 문서에 추가하지 않는다.

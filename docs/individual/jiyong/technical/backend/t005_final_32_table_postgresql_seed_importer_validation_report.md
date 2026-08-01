# T-005 32개 테이블 구현·PostgreSQL 최종 검증 보고서

> 기준일: 2026-07-31
> 작성·구현 책임: 최지용  
> 범위: Django Model·App 로딩·번호 Migration, Accounts 식별자/JWT 전환,
> 빈 PostgreSQL Migration·Seed·367건 Importer, Backend·Data 회귀  
> 판정: **작성자 격리 기술 검증 완료 / 비작성자·PM 공식 승인 대기**

## 1. 결론

활성 T-005 계약의 32개 테이블은 모두 실제 Django Model로 선언되고,
Runtime App Registry에 로딩되며, 번호 Migration과 연결됐다. 최종
Auditor는 실제 PostgreSQL 설정에서 `READY`, 구현 매핑 `32/32`,
차단 사유 0건을 반환했다.

완전히 빈 PostgreSQL에는 전체 Migration을 처음부터 적용했고, 5종
Seed를 두 번 실행했으며, 합성 Handoff 367건을 두 번 적재했다.
두 번째 적재에서는 기존 355건이 `UNCHANGED`, 계약상 투영 전용 12건이
`PROJECTED`로 기록돼 비의도 중복 생성이 없었다. SQLite 전체 회귀는
`740 passed, 11 skipped`, PostgreSQL 전체 회귀는 `751 passed`,
Data QA 테스트는 `67 tests, OK`다.

이 결과는 구현과 로컬 기술 검증의 완료를 뜻하지만, 자동으로 공식
WBS 완료 승인을 뜻하지 않는다. 활성 물리 계약 v1.3의 완료 리뷰 상태는
`NON_AUTHOR_REVIEW_PENDING`이고 `completion_claim_allowed=false`다. 비작성자
리뷰와 외부 재현이 기록되고 계약 담당자가 완료 상태를 승인하기 전에는
T-005를 공식 `완료`로 표시하지 않는다.

2026-07-31 작성자 격리 재현의 후보 SHA·환경·수치는
[T-005 작성자 격리 재현 증거](../../../../database/t-005/t005_author_isolated_reproduction_evidence_20260731.json)에
고정했다. 이 증거는 비작성자 리뷰를 대신하지 않는다.

## 2. 작업 전후 비교

| 항목 | 작업 전 | 작업 후 | 검증 |
| --- | ---: | ---: | --- |
| 계약 테이블 구현 | 12/32 | **32/32** | Auditor `READY` |
| 잔여 테이블 | 20 | **0** | Model·등록·Migration 매핑 |
| Accounts 내부 PK | 문자열 업무 코드와 혼용 | **`BigAutoField` 내부 PK** | Model·Migration·Auth 회귀 |
| 외부 사용자 ID | 전환 Bridge | **공개 UUID** | JWT `sub`·`/me` 일치 |
| Legacy JWT subject fallback | 허용 | **제거** | 문자열 subject 401 |
| Vector 저장 | 미구현 | **`vector(1024)`** | pgvector 0.8.6·Exact Search |
| 빈 PostgreSQL 전체 Migration | 최종 증거 없음 | **처음부터 적용 성공** | `migrate --check` |
| Seed 반복 실행 | 부분 증거 | **5종 2회** | 2회차 신규 0 |
| 367건 운영 적재 | Model·Importer 공백 | **2회 적재 완료** | 355 unchanged·12 projected |
| Data QA 소스 해시 | Backend 변경 후 6건 stale | **changed 0** | QA·재현성 PASS |

## 3. 구현 Wave

| Wave | 구현 범위 | 최종 결과 | 상세 문서 |
| --- | --- | --- | --- |
| 1A·1B | 문진 세션, 문의·문진 동일 구독 복합 FK | Model·Migration·PostgreSQL 제약 완료 | [Wave 1A](t005_wave_1a_support_questionnaire_session_implementation.md), [Wave 1B](t005_wave_1b_questionnaire_inquiry_composite_fk.md) |
| Accounts Gate | User·CustomerProfile 정수 PK, 공개 UUID, UUID-only JWT | 인증 전환 완료 | [Accounts PK·JWT Gate](t005_accounts_integer_pk_and_uuid_jwt_gate.md) |
| 1 | AI Run, Ingestion Batch, Visit Result | FK Root 완료 | [AI Run](t005_wave_1c_aiops_ai_run_implementation.md), [Ingestion Batch](t005_wave_1d_knowledge_ingestion_batch_implementation.md), [Visit Result](t005_wave_1e_field_service_visit_result_implementation.md) |
| 2 | Retrieval Run, Symptom Assessment, Source Document, Handoff Report, Status History, Inquiry QA, Guidance | 직접 자식 7개 완료 | [Wave 2 문서 목록](#10-관련-개발문서) |
| 3 | Document Model Scope, Document Page, Guidance Item | 상세·항목 3개 완료 | [Wave 3A](t005_wave_3a_knowledge_document_model_scope_implementation.md), [Wave 3B](t005_wave_3b_knowledge_document_page_implementation.md), [Wave 3C](t005_wave_3c_support_guidance_item_implementation.md) |
| 4 | Document Chunk | Chunk 원문·순서 제약 완료 | [Wave 4A](t005_wave_4a_knowledge_document_chunk_implementation.md) |
| 5 | Retrieval Hit, Data Quality Issue, Chunk Embedding | 검색·품질·Vector 완료 | [Wave 5A](t005_wave_5a_aiops_retrieval_hit_implementation.md), [Wave 5B](t005_wave_5b_knowledge_data_quality_issue_implementation.md), [Wave 5C](t005_wave_5c_knowledge_chunk_embedding_pgvector_implementation.md) |
| 6 | Customer Action Result, Evidence Link | 최종 다중 관계 완료 | [Wave 6A](t005_wave_6a_support_customer_action_result_implementation.md), [Wave 6B](t005_wave_6b_knowledge_evidence_link_implementation.md) |

## 4. 최종 PostgreSQL 검증

최종 검증 DB는 `watercare_t005_final_verify_20260730_01`이다. 사용자가
Runtime을 직접 확인할 수 있도록 현재 보존했으며, 임시
`watercare_t005_wave5c_embedding_01`은 검증 종료 후 삭제했다.

| 순서 | 실행·검증 | 결과 |
| ---: | --- | --- |
| 1 | 완전히 빈 DB 생성 후 전체 `migrate` | 전체 Migration 적용 성공 |
| 2 | `migrate --check` | 추가 적용 대상 없음 |
| 3 | T-005 Validator `--verify-postgresql` | 연결·`makemigrations`·Migration PASS |
| 4 | 5종 Seed 1차 | Group 16, Code 72, Demo Account 4, Product 1, Subscription 1, Care 3 |
| 5 | 같은 Seed 2차 | 비의도 신규 생성 0 |
| 6 | Importer dry-run | 입력 367, 생성 예상 355, 투영 12, 원장 저장 0 |
| 7 | Importer 1차 | `CREATED 355`, `PROJECTED 12` |
| 8 | Importer 2차 | `UNCHANGED 355`, `PROJECTED 12` |
| 9 | Import 원장 | Batch 2, Item 734, Batch별 Source 367 UNIQUE |
| 10 | 상태·감사 | Status History 125, Audit Event 125 |
| 11 | Vector | pgvector 0.8.6, `vector(1024)`, ANN Index 없음 |

공통코드 Seed가 출력하는 `BLOCKED_CONTRACT_MAPPING`은 실패가 아니다.
승인되지 않은 위험도·AI Stage 매핑을 임의 생성하지 않았다는 정상
차단 기록이며 명령은 exit code 0으로 완료됐다.

### 기본 `watercare` 개발 DB 동기화

최종 격리 DB 검증 뒤 사용자가 평소 `.env` 그대로 실행하는 기본
`watercare`도 별도 안전 절차로 동기화했다.

1. 11MB 기존 DB를 PostgreSQL custom-format으로 백업했다.
2. 백업 파일 크기와 SHA-256을 확인했다.
3. 미적용 Migration 24개를 모두 적용했다.
4. 기존 User 4·Profile 1·Inquiry 6·상태이력 11건 보존을 확인했다.
5. 5종 Seed를 두 번 실행했다.
6. 합성 Handoff 367건을 dry-run·1차·Replay 순서로 적재했다.
7. Auditor·Validator·전체 회귀·Health·Demo Login을 다시 검증했다.

기본 DB의 최종 핵심 건수는 User 20, Profile 13, Common Code Group 16,
Common Code 72, Import Batch 2, Import Item 734, Audit Event 125다.
상태이력은 기존 11건을 삭제하지 않고 합성 125건을 추가해 136건이다.
복구 백업은
`Daily_Process/20260730/.local_db_backups/watercare_before_t005_sync_20260730-235107.dump`
에 있으며 Git 공유 대상이 아니다.

## 5. 회귀·품질 검증

| 검증 계층 | 최종 결과 | 비고 |
| --- | --- | --- |
| Django system check | 문제 0 | local 설정 |
| Migration drift | `No changes detected` | Model·Migration parity |
| T-005 Auditor | `READY`, 32/32, blocker 0 | 지원 Runtime 4개 allowlist |
| T-005 Schema Validator | 구조 유효, 오류 0 | 공식 완료 Gate 3개는 별도 |
| SQLite Backend 전체 | `740 passed, 11 skipped` | Seed 업그레이드 회귀 포함, Skip은 PostgreSQL 전용 |
| PostgreSQL Backend 전체 | `751 passed` | Seed 업그레이드 회귀 포함, local 설정·격리 테스트 DB |
| Data Pipeline QA | 48개 파일·740개 레코드, 오류 0·경고 0 | 대표 E2E 17/17 |
| Data 재현성 | 변경 파일 0·canonical drift 0 | 고정 생성 시각 사용 |
| Data 단위 테스트 | `Ran 67 tests`, `OK` | 실제 사용자 권한 Temp에서 실행 |
| Source Hash | `PASS`, `changed=0` | CRLF/LF 정규화 정책 적용 |
| Git whitespace | `git diff --check` 출력 없음 | 현재 작업 트리 기준 |
| 개발·인계 문서 | 56개 MD·765개 링크, 절대경로·누락·깨진 anchor 0 | 과거 Wave 수치는 역사 배너로 분리 |
| 업무계획표 v0.8 | 11개 시트·수식 2개·수식 오류 0 | 전 시트 렌더링 검토 |

Data QA의 첫 샌드박스 실행에서 임시 디렉터리 ACL 때문에 파일 쓰기
안전성 테스트 2개가 실패했지만, 같은 코드를 실제 사용자 권한
환경에서 재실행해 67개가 모두 통과했다. 이는 데이터 로직 실패가
아니며, 접근 불가 임시 폴더는 검증 후 제거했다.

## 6. Health·Demo Login 직접 검증

기본 `watercare`와 최종 격리 DB를 각각 연결한 Django 개발 서버는
현재 다음 주소로 실행했다.

- 기본 `watercare` Health: `http://127.0.0.1:8000/health`
- 최종 격리 DB Health: `http://127.0.0.1:8001/health`
- Demo Login: `POST /api/v1/auth/demo-login`
- 현재 사용자: `GET /api/v1/me`

| 항목 | 결과 |
| --- | --- |
| Health | HTTP 200, Body 0 byte |
| Demo 사용자 코드 | `DEMO-CUSTOMER-001` |
| Login | 성공, Bearer Token 발급 |
| JWT `sub` | UUID 형식 |
| JWT `sub`와 응답 User ID | 일치 |
| `/me` ID와 JWT `sub` | 일치 |
| Role | `CUSTOMER` |
| Customer No | `DEMO-CUSTOMER-001` |
| `CUS-0001` 직접 Demo Login | 접두사 계약에 따라 계속 거부 |

`CUS-*`는 내부 Import 사용자명이고 공개 Demo Login 입력이 아니다.
합성 고객은 `DEMO-*` 또는 승인된 `SYN-*` 별칭을 사용한다.

## 7. 작업 중 발견·해결한 연쇄 오류

| 문제 | 원인 | 해결 | 재검증 |
| --- | --- | --- | --- |
| Chunk Embedding 복합 FK 위반이 Commit까지 지연 | FK가 `DEFERRABLE INITIALLY DEFERRED` | 즉시 제약으로 변경 | PostgreSQL 집중 테스트 16 passed |
| PostgreSQL 전체 회귀 최초 5건 실패 | Demo/CORS 환경 격리 3건, 중첩 pytest DB 충돌 1건, 과거 `NOT_READY` 기대값 1건 | 테스트 환경 명시·중첩 설정 격리·현재 READY 기대값 반영 | 중간 `750 passed`; Seed 업그레이드 회귀 추가 후 최종 `751 passed` |
| Data QA 소스 해시 6건 불일치 | Backend Model·Importer·Auth가 실제 변경됐지만 Crosswalk 해시가 이전 값 | 공식 해시 갱신 도구로 승인된 6개만 갱신 | QA PASS·Source Hash changed 0 |
| Docker 기본 PostgreSQL에 Vector 확장 없음 | 일반 PostgreSQL 이미지 | pgvector PostgreSQL 16 이미지로 전환 | 기존 DB 건수 보존·extension 0.8.6 확인 |
| Demo Login에서 `CUS-0001` 401 | 공개 Demo 입력과 내부 Import username 혼용 | `DEMO-*`·`SYN-*` 공개 별칭 계약 유지 | Demo Login·UUID JWT·`/me` PASS |
| 기본 DB Demo Seed의 Profile UNIQUE 충돌 | 기존 Demo User의 Profile이 과거 `SYN-CUSTOMER-001` 업무키를 사용했는데 Seed가 새 고객번호만 조회 | Profile을 고객번호가 아니라 고유 User 기준으로 Upsert하고 업무키를 `DEMO-CUSTOMER-001`로 전환 | SQLite·PostgreSQL 집중 2 passed, 기본 DB Seed 2회, 전체 740/751 PASS |

## 8. 공식 완료를 아직 선언하지 않는 이유

Schema Validator의 구현·PostgreSQL·Seed 기술 Gate는 모두 통과했다.
남은 항목은 작성자가 임의로 채울 수 없는 검토·계약 승인 Gate다.

| 남은 Gate | 현재 | 필요한 행동 | 주담당·협업 |
| --- | --- | --- | --- |
| `non_author_review_confirmed` | false | 비작성자가 동일 SHA에서 빈 PostgreSQL·Seed·회귀를 재현하고 결과 기록 | 김은진 또는 지정 리뷰어 |
| `three_layer_identifier_runtime_complete` | false | Runtime은 구현됐고 v1.3은 `TECHNICALLY_COMPLETE_REVIEW_PENDING`이다. 비작성자 증거와 PM 승인 후에만 후속 계약을 `COMPLETE`로 승격 | 최지용 근거 제공, 윤승혁(PM)·계약 리뷰 |
| `external_review_verified` | false | PR/리뷰 또는 독립 검증 증거를 완료 Evidence에 연결 | 비작성자 리뷰어·PM |

현재 물리 계약의 `completion_review_status=NON_AUTHOR_REVIEW_PENDING`,
`completion_claim_allowed=false`를 코드 구현만으로 임의 변경하지
않는다. 승인 전 판정은 다음처럼 분리한다.

- 로컬 기술 구현: **완료**
- 32개 Model·App·Migration: **완료**
- 빈 PostgreSQL·Seed·Importer·회귀: **완료**
- 공식 T-005 WBS 상태: **진행 중**
- 팀 검토·병합: **대기**

## 9. 팀 인계

| 대상 | 전달 내용 | 확인 요청 |
| --- | --- | --- |
| 김은진 | 최종 DB 생성·Migration·5종 Seed 2회·367건 2회 Import·Data QA | 새 DB 독립 재현과 건수·Hash 확인 |
| 윤승혁(PM) | 32/32 Auditor READY와 공식 완료 Gate 3개 | 계약 완료 리뷰·병합 Gate 결정 |
| 이동윤 | AI Run·Retrieval·Hit·Embedding·Evidence 관계, `vector(1024)` | AI Schema·Embedding 모델/차원 소비 정합 |
| 한예나·양정현 | 공개 UUID, UUID-only JWT, Demo/Synthetic 로그인 경계 | Web·Mobile DTO와 인증 오류 처리 |

인계 시 `.env`, Token, DB 비밀번호, 개인 DB Dump는 공유하지 않는다.
공유 대상은 소스·Migration·계약·검증 명령·비식별 집계 결과다.

## 10. 관련 개발문서

Wave 2의 상세 근거는 다음 문서를 따른다.

- [Retrieval Run](t005_wave_2a_aiops_retrieval_run_implementation.md)
- [Symptom Assessment](t005_wave_2b_support_symptom_assessment_implementation.md)
- [Source Document](t005_wave_2c_knowledge_source_document_implementation.md)
- [Handoff Report](t005_wave_2d_support_handoff_report_implementation.md)
- [Migration 불변성 복구](t005_wave_2e_migration_immutability_repair.md)
- [Status History 계약 정렬](t005_wave_2e_status_history_contract_alignment.md)
- [Inquiry QA](t005_wave_2f_support_inquiry_qa_implementation.md)
- [Guidance](t005_wave_2g_support_guidance_implementation.md)

공통 기준과 기계 증거는 다음 경로에 있다.

- [T-005 데이터 설계 패키지](../../../../database/t-005/README.md)
- [로컬 기술 완료 Evidence](../../../../database/t-005/t005_local_technical_completion_evidence_20260730.json)
- [Runtime 지원 테이블 Auditor 분류](t005_runtime_support_table_auditor_classification.md)
- [DB Schema 개발·인계 가이드](database_schema_handover_guide.md)
- [Backend 환경 재현 가이드](backend_venv_reproducibility_guide.md)

## 11. 최종 체크리스트

- [x] 계약 테이블 32개 Model 선언
- [x] 32개 Runtime App Registry 로딩
- [x] 32개 번호 Migration 매핑
- [x] Accounts 정수 PK·공개 UUID 분리
- [x] Legacy JWT subject fallback 제거
- [x] 빈 PostgreSQL 전체 Migration
- [x] 5종 Seed 2회·비의도 신규 0
- [x] 367건 Importer 2회·Replay 멱등성
- [x] pgvector 0.8.6·`vector(1024)` 실측
- [x] SQLite·PostgreSQL Backend 전체 회귀
- [x] Data QA·재현성·67개 테스트
- [x] Health·Demo Login·UUID JWT 직접 검증
- [x] 기본 `watercare` 백업·24개 Migration·Seed·367건 동기화
- [ ] 비작성자 독립 재현
- [ ] 계약 완료 리뷰
- [ ] 외부 리뷰 증거 연결
- [ ] PM 병합 승인

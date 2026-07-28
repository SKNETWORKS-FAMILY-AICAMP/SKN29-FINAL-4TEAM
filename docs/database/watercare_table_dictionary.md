# WaterCare Table Dictionary

> 문서 상태: **HISTORICAL_SNAPSHOT — v0.5 설계 초안 보존본**
> 설계 Snapshot: `v0.5` / 기준일: 2026-07-27
> 범위: 32개 설계 테이블 · 526개 필드 · 85개 물리 FK · 57개 논리 코드 참조
> 현행 우선 원천: [ADR-0008](../adr/0008-t005-data-contract-decisions.md)과
> [T-005 Physical Contract v1.0](t-005/t005_physical_contract_v1.0.json)
> 이 문서는 사람이 읽는 과거 설계 스냅샷이며, 현행 계약·Django Migration 또는 운영 PostgreSQL 검증 결과를 대신하지 않는다.

## 1. 문서 해석

- `PK`: 설계상 기본키 후보
- `NN`: `NOT NULL` 후보
- `물리 FK`: 다른 테이블 컬럼을 직접 참조하는 관계
- `논리 코드`: `common_code(group=...)`를 통한 코드 의미 참조이며 물리 FK가 아님
- 각 테이블의 `설계 상태: Design Draft`는 이 v0.5 스냅샷을 만들 당시의
  상태를 보존한 표기다.
- `팀 결정 필요`: 당시 초안에서 미결 후보를 표시한 **역사 주석**이다.
  현재 구현 착수 전 팀 승인이나 최지용 Owner 작업의 차단 조건을 뜻하지
  않는다. 현재 값은 ADR-0008과 Physical Contract v1.0을 우선 적용하고,
  외부 담당 입력이 필요한 항목만 해당 담당 계약에서 후속 정합화한다.
- 타입·기본값·제약은 과거 설계값이다. 현행 구현은 ADR-0008과 Physical
  Contract v1.0을 우선하며, 운영 스키마 판정은 Django Migration과 실제
  PostgreSQL 검증 증거를 따른다.

## 2. 도메인 요약

| 도메인 | 테이블 | 필드 | 물리 FK | 논리 코드 참조 |
|---|---:|---:|---:|---:|
| 공통 | 2 | 17 | 1 | 0 |
| 계정·권한 | 1 | 15 | 0 | 1 |
| 제품 | 1 | 12 | 0 | 0 |
| 고객 | 1 | 15 | 2 | 0 |
| 구독·케어 | 2 | 28 | 5 | 5 |
| 고객 지원 | 12 | 191 | 40 | 29 |
| 현장 방문 | 2 | 37 | 6 | 2 |
| 지식·근거 | 8 | 145 | 26 | 14 |
| AI 운영 | 3 | 66 | 5 | 6 |

## 3. 테이블 목록

| 번호 | 도메인 | 테이블 | 한글명 | 필드 | 물리 FK | 논리 코드 |
|---:|---|---|---|---:|---:|---:|
| 1 | 공통 | [`common_code_group`](#1-common-code-group--공통코드-그룹) | 공통코드 그룹 | 7 | 0 | 0 |
| 2 | 공통 | [`common_code`](#2-common-code--공통코드) | 공통코드 | 10 | 1 | 0 |
| 3 | 계정·권한 | [`accounts_user`](#3-accounts-user--사용자-계정) | 사용자 계정 | 15 | 0 | 1 |
| 4 | 제품 | [`catalog_product_model`](#4-catalog-product-model--제품-모델) | 제품 모델 | 12 | 0 | 0 |
| 5 | 고객 | [`customers_customer_profile`](#5-customers-customer-profile--고객-프로필) | 고객 프로필 | 15 | 2 | 0 |
| 6 | 구독·케어 | [`subscriptions_customer_subscription`](#6-subscriptions-customer-subscription--고객-구독) | 고객 구독 | 14 | 2 | 2 |
| 7 | 구독·케어 | [`subscriptions_care_record`](#7-subscriptions-care-record--제품-케어-이력) | 제품 케어 이력 | 14 | 3 | 3 |
| 8 | 고객 지원 | [`support_inquiry`](#8-support-inquiry--고객-문의) | 고객 문의 | 28 | 6 | 8 |
| 9 | 고객 지원 | [`support_inquiry_symptom`](#9-support-inquiry-symptom--문의-증상-구조화) | 문의 증상 구조화 | 15 | 3 | 1 |
| 10 | 고객 지원 | [`support_inquiry_qa`](#10-support-inquiry-qa--문의-추가-문진) | 문의 추가 문진 | 14 | 3 | 2 |
| 11 | 고객 지원 | [`support_symptom_assessment`](#11-support-symptom-assessment--증상-위험도-판정) | 증상 위험도 판정 | 13 | 2 | 4 |
| 12 | 고객 지원 | [`support_guidance`](#12-support-guidance--고객-안내) | 고객 안내 | 14 | 3 | 2 |
| 13 | 고객 지원 | [`support_guidance_item`](#13-support-guidance-item--고객-안내-단계) | 고객 안내 단계 | 9 | 1 | 1 |
| 14 | 고객 지원 | [`support_customer_action_result`](#14-support-customer-action-result--고객-자가조치-결과) | 고객 자가조치 결과 | 10 | 2 | 1 |
| 15 | 고객 지원 | [`support_consultation`](#15-support-consultation--상담-처리) | 상담 처리 | 20 | 3 | 2 |
| 16 | 고객 지원 | [`support_handoff_report`](#16-support-handoff-report--방문기사-인계-리포트) | 방문기사 인계 리포트 | 18 | 4 | 1 |
| 17 | 현장 방문 | [`field_service_visit`](#17-field-service-visit--현장-방문) | 현장 방문 | 20 | 4 | 1 |
| 18 | 현장 방문 | [`field_service_visit_result`](#18-field-service-visit-result--현장-방문-결과) | 현장 방문 결과 | 17 | 2 | 1 |
| 19 | 고객 지원 | [`support_followup_confirmation`](#19-support-followup-confirmation--후속-해결-확인) | 후속 해결 확인 | 19 | 6 | 2 |
| 20 | 고객 지원 | [`support_inquiry_status_history`](#20-support-inquiry-status-history--업무-상태-전이-이력) | 업무 상태 전이 이력 | 16 | 5 | 3 |
| 21 | 지식·근거 | [`knowledge_ingestion_batch`](#21-knowledge-ingestion-batch--지식-수집-배치) | 지식 수집 배치 | 18 | 1 | 3 |
| 22 | 지식·근거 | [`knowledge_source_document`](#22-knowledge-source-document--공식-원본-문서) | 공식 원본 문서 | 26 | 4 | 3 |
| 23 | 지식·근거 | [`knowledge_document_model_scope`](#23-knowledge-document-model-scope--문서-적용-제품-범위) | 문서 적용 제품 범위 | 11 | 3 | 0 |
| 24 | 지식·근거 | [`knowledge_document_page`](#24-knowledge-document-page--문서-페이지) | 문서 페이지 | 13 | 2 | 2 |
| 25 | 지식·근거 | [`knowledge_document_chunk`](#25-knowledge-document-chunk--문서-검색-청크) | 문서 검색 청크 | 19 | 1 | 1 |
| 26 | 지식·근거 | [`knowledge_chunk_embedding`](#26-knowledge-chunk-embedding--청크-임베딩) | 청크 임베딩 | 11 | 1 | 0 |
| 27 | 지식·근거 | [`knowledge_data_quality_issue`](#27-knowledge-data-quality-issue--지식-데이터-품질-이슈) | 지식 데이터 품질 이슈 | 18 | 5 | 3 |
| 28 | AI 운영 | [`aiops_ai_run`](#28-aiops-ai-run--AI-실행-이력) | AI 실행 이력 | 29 | 1 | 3 |
| 29 | AI 운영 | [`aiops_retrieval_run`](#29-aiops-retrieval-run--RAG-검색-실행) | RAG 검색 실행 | 23 | 2 | 2 |
| 30 | AI 운영 | [`aiops_retrieval_hit`](#30-aiops-retrieval-hit--RAG-검색-결과) | RAG 검색 결과 | 14 | 2 | 1 |
| 31 | 지식·근거 | [`knowledge_evidence_link`](#31-knowledge-evidence-link--업무-결과-근거-연결) | 업무 결과 근거 연결 | 29 | 9 | 2 |
| 32 | 고객 지원 | [`support_questionnaire_session`](#32-support-questionnaire-session--사전-문진-세션) | 사전 문진 세션 | 15 | 2 | 2 |

## 4. 상세 명세

### 1. `common_code_group` — 공통코드 그룹

- 도메인: 공통
- 목적: 업무 상태, 위험도, 역할 등 공통코드의 상위 그룹을 관리한다. [공통 설계 원칙] 안정된 설정 자연키 예외를 적용하며 group_code 변경·물리 삭제를 금지하고 비활성화로 관리한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `group_code` | 그룹코드 | `varchar(40)` | Y | Y | — | — | 공통코드 그룹의 영문 대문자 코드 · 예: INQUIRY_STATUS |
| 2 | `group_name` | 그룹명 | `varchar(100)` | — | Y | — | — | 공통코드 그룹의 한글 명칭 |
| 3 | `description` | 설명 | `text` | — | — | — | — | 그룹의 사용 목적과 적용 범위 |
| 4 | `display_order` | 표시순서 | `integer` | — | Y | `0` | — | 관리 화면 표시 순서 · CHECK display_order >= 0 |
| 5 | `is_active` | 사용여부 | `boolean` | — | Y | `true` | — | 신규 입력에서 사용할 수 있는지 여부 |
| 6 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 7 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_common_code_group` | BTREE | Y | group_code |
| 2 | `ix_common_code_group_active` | BTREE | N | is_active, display_order |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_common_code_group_code_format` | CHECK | group_code ~ '^[A-Z][A-Z0-9_]*$' |

</details>

---

### 2. `common_code` — 공통코드

- 도메인: 공통
- 목적: 상태·역할·위험도 등 화면과 API가 함께 사용하는 코드 값을 관리한다. [공통 설계 원칙] 표시명·정렬·메타데이터용 코드 레지스트리다. 업무 *_code 컬럼은 Django TextChoices와 DB CHECK로 검증하며 code 단독 물리 FK로 사용하지 않는다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `group_code` | 그룹코드 | `varchar(40)` | — | Y | — | 물리 FK: common_code_group.group_code | 소속 공통코드 그룹 · ON DELETE RESTRICT |
| 3 | `code` | 코드 | `varchar(40)` | — | Y | — | — | 그룹 안에서 유일한 코드 값 |
| 4 | `code_name` | 코드명 | `varchar(100)` | — | Y | — | — | 사용자에게 표시할 코드 명칭 |
| 5 | `description` | 설명 | `text` | — | — | — | — | 코드의 업무 의미와 적용 조건 |
| 6 | `display_order` | 표시순서 | `integer` | — | Y | `0` | — | 그룹 안에서의 표시 순서 · CHECK display_order >= 0 |
| 7 | `is_active` | 사용여부 | `boolean` | — | Y | `true` | — | 신규 입력에서 선택할 수 있는지 여부 |
| 8 | `metadata` | 확장속성 | `jsonb` | — | Y | `'{}'::jsonb` | — | 색상, 아이콘 등 비업무 확장 속성 |
| 9 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 10 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_common_code` | BTREE | Y | id |
| 2 | `ux_common_code_group_code` | BTREE | Y | group_code, code |
| 3 | `ix_common_code_active` | BTREE | N | group_code, is_active, display_order |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_common_code_code_format` | CHECK | code ~ '^[A-Z][A-Z0-9_]*$' |
| 2 | `ck_common_code_metadata_object` | CHECK | jsonb_typeof(metadata)='object' |

</details>

---

### 3. `accounts_user` — 사용자 계정

- 도메인: 계정·권한
- 목적: 고객, 상담사, 방문기사, 운영자의 인증 계정과 단일 기본 역할을 관리한다. [공통 설계 원칙] Django 인증 계정은 is_active로 비활성화하고 물리 삭제하지 않는다. 고객 업무정보 원본은 고객 프로필에 둔다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `username` | 로그인아이디 | `varchar(150)` | — | Y | — | — | 사용자 로그인 식별자 · UNIQUE, Django USERNAME_FIELD |
| 3 | `password` | 비밀번호해시 | `varchar(128)` | — | Y | — | — | Django 비밀번호 해시 문자열 · 평문 저장 금지 |
| 4 | `email` | 이메일 | `varchar(254)` | — | — | — | — | 알림 및 계정 식별 보조 이메일 |
| 5 | `full_name` | 표시이름 | `varchar(100)` | — | Y | — | — | 계정 공통 표시명. CUSTOMER의 업무상 고객명 원본은 customers_customer_profile.customer_name |
| 6 | `phone` | 연락처 | `varchar(30)` | — | — | — | — | 직원 업무 연락처 또는 로그인 보조 연락처. 고객 연락처 원본은 고객 프로필에서 관리 · MVP 실제 개인정보 저장 금지 |
| 7 | `role_code` | 기본역할코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=USER_ROLE) | CUSTOMER, CONSULTANT, TECHNICIAN, OPERATOR · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 8 | `employee_no` | 사번 | `varchar(40)` | — | — | — | — | 상담사·기사·운영자 사번 · 조건부 UNIQUE |
| 9 | `last_login` | 최종로그인일시 | `timestamptz` | — | — | — | — | 최종 인증 성공 일시 |
| 10 | `is_superuser` | 슈퍼유저여부 | `boolean` | — | Y | `false` | — | 전체 권한 보유 여부 |
| 11 | `is_staff` | 관리자접근여부 | `boolean` | — | Y | `false` | — | Django Admin 접근 가능 여부 |
| 12 | `is_active` | 활성여부 | `boolean` | — | Y | `true` | — | 로그인 가능한 활성 계정인지 여부 |
| 13 | `date_joined` | 가입일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 계정 가입 일시 |
| 14 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 15 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_accounts_user` | BTREE | Y | id |
| 2 | `ux_accounts_user_username` | BTREE | Y | username |
| 3 | `ux_accounts_user_employee_no` | BTREE | Y | employee_no / WHERE employee_no IS NOT NULL |
| 4 | `ix_accounts_user_role_active` | BTREE | N | role_code, is_active |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `policy_accounts_user_no_physical_delete` | APPLICATION POLICY | Django service에서 물리 DELETE를 금지하고 is_active=false로 비활성화; DB 권한 테스트로 DELETE 권한 미부여 검증 |
| 2 | `ck_accounts_user_role_code_allowed` | CHECK | role_code IN ('CUSTOMER','CONSULTANT','TECHNICIAN','OPERATOR') |

</details>

---

### 4. `catalog_product_model` — 제품 모델

- 도메인: 제품
- 목적: RAG 적용 범위와 구독 상품을 연결하는 정수기 모델·세대 정보를 관리한다. [공통 설계 원칙] model_code는 변경하지 않는 업무 식별자이며 is_active와 is_supported_mvp의 역할을 분리한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `model_code` | 모델코드 | `varchar(60)` | — | Y | — | — | 제조사 제품 모델 코드 · UNIQUE, 예: WPU-JAC104D |
| 3 | `model_name` | 모델명 | `varchar(150)` | — | Y | — | — | 사용자 화면 표시용 모델명 |
| 4 | `generation_code` | 세대코드 | `varchar(40)` | — | — | — | — | 동일 계열 제품의 세대·리비전 구분 |
| 5 | `manufacturer` | 제조사 | `varchar(100)` | — | Y | `'SK매직'` | — | 제품 제조사 또는 브랜드 |
| 6 | `launched_on` | 출시일 | `date` | — | — | — | — | 제품 출시일 |
| 7 | `discontinued_on` | 단종일 | `date` | — | — | — | — | 제품 단종일 |
| 8 | `features` | 제품특성 | `jsonb` | — | Y | `'{}'::jsonb` | — | 냉수·온수·정수 등 검색 필터용 특성 |
| 9 | `is_supported_mvp` | MVP지원여부 | `boolean` | — | Y | `false` | — | 현재 MVP의 검색·안내 지원 대상인지 여부 · MVP 검색·시연 지원 범위 |
| 10 | `is_active` | 사용여부 | `boolean` | — | Y | `true` | — | 신규 구독과 문서 연결에 사용할지 여부 · 신규 구독 연결 허용 여부 |
| 11 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 12 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_catalog_product_model` | BTREE | Y | id |
| 2 | `ux_catalog_product_model_code` | BTREE | Y | model_code |
| 3 | `ix_product_model_supported` | BTREE | N | is_supported_mvp, is_active |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_product_model_lifecycle_dates` | CHECK | discontinued_on IS NULL OR launched_on IS NULL OR discontinued_on >= launched_on |
| 2 | `ck_product_model_features_object` | CHECK | jsonb_typeof(features)='object' |

</details>

---

### 5. `customers_customer_profile` — 고객 프로필

- 도메인: 고객
- 목적: 고객 계정에 연결된 가명·합성 고객번호, 연락처, 설치 주소를 관리한다. [공통 설계 원칙] customer_name을 포함한 가명·합성 고객정보의 원본이며 논리 삭제와 권한별 마스킹을 적용한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `user_id` | 사용자식별자 | `uuid` | — | Y | — | 물리 FK: accounts_user.id | 고객 역할의 사용자 계정 · UNIQUE, ON DELETE RESTRICT |
| 3 | `customer_no` | 고객번호 | `varchar(40)` | — | Y | — | — | 화면과 상담 업무에서 사용하는 가명 고객번호 · UNIQUE |
| 4 | `customer_name` | 고객명 | `varchar(100)` | — | Y | — | — | 상담·방문 화면에 표시하는 가명·합성 고객명 · MVP 실제 개인정보 저장 금지; 권한별 API 마스킹 적용 |
| 5 | `phone` | 고객연락처 | `varchar(30)` | — | — | — | — | 가명·합성 연락처 · 실제 개인정보 사용 금지 |
| 6 | `postal_code` | 우편번호 | `varchar(10)` | — | — | — | — | 설치 주소 우편번호 |
| 7 | `address_line1` | 기본주소 | `varchar(255)` | — | — | — | — | 가명·합성 설치 기본 주소 |
| 8 | `address_line2` | 상세주소 | `varchar(255)` | — | — | — | — | 가명·합성 설치 상세 주소 |
| 9 | `consent_version` | 동의버전 | `varchar(40)` | — | — | — | — | 테스트용 개인정보·서비스 동의 버전 |
| 10 | `consented_at` | 동의일시 | `timestamptz` | — | — | — | — | 동의가 기록된 일시 |
| 11 | `is_synthetic` | 합성데이터여부 | `boolean` | — | Y | `true` | — | 가명·합성 데이터 여부 · MVP는 true만 허용하는 운영규칙 검토 |
| 12 | `deleted_at` | 삭제일시 | `timestamptz` | — | — | — | — | 고객 프로필을 화면·일반 조회에서 제외한 논리 삭제 시각 · 물리 삭제 금지; 보존기간 종료 시 별도 익명화 절차 |
| 13 | `deleted_by_id` | 삭제처리자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 논리 삭제를 수행한 사용자 · ON DELETE RESTRICT |
| 14 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 15 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_customer_profile` | BTREE | Y | id |
| 2 | `ux_customer_profile_user` | BTREE | Y | user_id |
| 3 | `ux_customer_profile_no` | BTREE | Y | customer_no |
| 4 | `ix_customer_profile_active` | BTREE | N | customer_no / WHERE deleted_at IS NULL |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_customer_consent_pair` | CHECK | (consent_version IS NULL) = (consented_at IS NULL) |
| 2 | `ck_customer_synthetic_mvp` | CHECK | is_synthetic = true |
| 3 | `ck_customer_deleted_pair` | CHECK | (deleted_at IS NULL) = (deleted_by_id IS NULL) |
| 4 | `policy_customer_synthetic_only` | APPLICATION POLICY | MVP는 가명·합성 데이터만 허용; 실제 개인정보 전환은 별도 보안·동의 설계 승인 필요 |

</details>

---

### 6. `subscriptions_customer_subscription` — 고객 구독

- 도메인: 구독·케어
- 목적: 고객과 정수기 모델·제품 일련번호·구독 상태·다음 케어 일정을 연결한다. [공통 설계 원칙] 계약 기간·상태·활성 기기 일련번호의 일관성을 보장하고 종료 이력은 물리 삭제하지 않는다. 화면의 관리 유형은 management_type_code를 기준으로 제공한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `contract_no` | 계약번호 | `varchar(50)` | — | Y | — | — | 가명·합성 구독 계약번호 · UNIQUE |
| 3 | `customer_id` | 고객식별자 | `uuid` | — | Y | — | 물리 FK: customers_customer_profile.id | 구독 고객 · ON DELETE RESTRICT |
| 4 | `product_model_id` | 제품모델식별자 | `uuid` | — | Y | — | 물리 FK: catalog_product_model.id | 구독 대상 정수기 모델 · ON DELETE RESTRICT |
| 5 | `serial_no` | 제품일련번호 | `varchar(80)` | — | Y | — | — | 설치 제품의 가명·합성 일련번호 · 조건부 UNIQUE: ux_customer_subscription_serial 참조 |
| 6 | `management_type_code` | 관리유형코드 | `varchar(40)` | — | Y | `'VISIT_CARE'` | 논리 코드: common_code(group=MANAGEMENT_TYPE) | 자가관리 또는 방문관리 유형 · 설계 제안: Django TextChoices + DB CHECK 제안; Enum 저장 방식·값 집합은 팀 결정 필요 |
| 7 | `status_code` | 구독상태코드 | `varchar(40)` | — | Y | `'ACTIVE'` | 논리 코드: common_code(group=SUBSCRIPTION_STATUS) | ACTIVE, SUSPENDED, CANCELLED, EXPIRED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 8 | `started_on` | 구독시작일 | `date` | — | Y | — | — | 구독 계약 시작일 |
| 9 | `ended_on` | 구독종료일 | `date` | — | — | — | — | 구독 계약 종료일 |
| 10 | `installed_at` | 설치일시 | `timestamptz` | — | — | — | — | 제품 설치 완료 일시 |
| 11 | `installation_address` | 설치주소스냅샷 | `varchar(500)` | — | — | — | — | 계약 시점 가명·합성 설치 주소 |
| 12 | `next_care_on` | 다음케어예정일 | `date` | — | — | — | — | 미완료 care_record의 가장 빠른 scheduled_on을 트랜잭션에서 동기화한 조회용 캐시 |
| 13 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 14 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_customer_subscription` | BTREE | Y | id |
| 2 | `ux_customer_subscription_contract` | BTREE | Y | contract_no |
| 3 | `ux_customer_subscription_serial` | BTREE | Y | serial_no / WHERE status_code IN ('ACTIVE','SUSPENDED') AND serial_no IS NOT NULL |
| 4 | `ix_subscription_customer_status` | BTREE | N | customer_id, status_code |
| 5 | `ix_subscription_next_care` | BTREE | N | next_care_on / WHERE status_code='ACTIVE' AND next_care_on IS NOT NULL |
| 6 | `ix_subscription_product_model` | BTREE | N | product_model_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_subscription_period` | CHECK | ended_on IS NULL OR ended_on >= started_on |
| 2 | `ck_subscription_ended_consistency` | CHECK | status_code NOT IN ('CANCELLED','EXPIRED') OR ended_on IS NOT NULL |
| 3 | `policy_subscription_next_care_recalculation` | APPLICATION POLICY | next_care_on은 케어 이력 변경과 같은 Django transaction에서 재계산하고 관리 명령으로 정합성을 재검증 |
| 4 | `ck_sub_customer_subscription_management_type_code_allowed` | CHECK | management_type_code IN ('SELF_MANAGED','VISIT_CARE') |
| 5 | `ck_subscriptions_customer_subscription_status_code_allowed` | CHECK | status_code IN ('ACTIVE','SUSPENDED','CANCELLED','EXPIRED') |

</details>

---

### 7. `subscriptions_care_record` — 제품 케어 이력

- 도메인: 구독·케어
- 목적: 구독 제품의 정기관리·필터교체·점검 일정과 완료 결과를 관리한다. [공통 설계 원칙] 예약·완료·취소 상태를 시간 정보와 함께 관리하며 구독 삭제와 분리해 케어 이력을 보존한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `subscription_id` | 구독식별자 | `uuid` | — | Y | — | 물리 FK: subscriptions_customer_subscription.id | 관리 대상 고객 구독 · ON DELETE RESTRICT |
| 3 | `visit_result_id` | 방문결과식별자 | `uuid` | — | — | — | 물리 FK: field_service_visit_result.id | TECH-03 방문 결과로 생성된 케어 이력의 원본 · ON DELETE RESTRICT; 한 방문 결과에서 복수 케어 항목 생성 가능, 수동·정기 이력은 NULL |
| 4 | `care_type_code` | 케어유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=CARE_TYPE) | 정기관리, 필터교체, 위생점검 등 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `status_code` | 케어상태코드 | `varchar(40)` | — | Y | `'SCHEDULED'` | 논리 코드: common_code(group=CARE_STATUS) | DUE, SCHEDULED, COMPLETED, OVERDUE, CANCELLED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 6 | `scheduled_on` | 예정일 | `date` | — | Y | — | — | 케어 수행 예정일 |
| 7 | `completed_at` | 완료일시 | `timestamptz` | — | — | — | — | 케어 작업이 실제 완료된 일시 |
| 8 | `cancelled_at` | 취소일시 | `timestamptz` | — | — | — | — | 케어 일정이 취소된 일시 |
| 9 | `cancellation_reason` | 취소사유 | `text` | — | — | — | — | 고객 요청·일정 변경 등 취소 사유 |
| 10 | `summary` | 처리요약 | `text` | — | — | — | — | 수행 내용과 고객 특이사항 요약 |
| 11 | `performed_by_id` | 수행자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 케어를 수행한 기사 또는 담당자 · ON DELETE RESTRICT |
| 12 | `source_code` | 데이터출처코드 | `varchar(40)` | — | Y | `'SYSTEM'` | 논리 코드: common_code(group=DATA_SOURCE) | CUSTOMER, CONSULTANT, TECHNICIAN, SYSTEM, IMPORT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 13 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 14 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_care_record` | BTREE | Y | id |
| 2 | `ix_care_record_subscription` | BTREE | N | subscription_id, completed_at DESC |
| 3 | `ix_care_record_schedule` | BTREE | N | status_code, scheduled_on |
| 4 | `ix_care_record_visit_result` | BTREE | N | visit_result_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_care_record_completion` | CHECK | status_code <> 'COMPLETED' OR (completed_at IS NOT NULL AND performed_by_id IS NOT NULL) |
| 2 | `ck_care_record_cancellation` | CHECK | status_code <> 'CANCELLED' OR (cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) |
| 3 | `ck_care_record_single_outcome` | CHECK | NOT (completed_at IS NOT NULL AND cancelled_at IS NOT NULL) |
| 4 | `ck_care_record_status_fields` | CHECK | (status_code='COMPLETED' AND completed_at IS NOT NULL AND performed_by_id IS NOT NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR (status_code='CANCELLED' AND completed_at IS NULL AND performed_by_id IS NULL AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) OR (status_code IN ('DUE','SCHEDULED','OVERDUE') AND completed_at IS NULL AND performed_by_id IS NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL) |
| 5 | `policy_care_record_visit_subscription_match` | APPLICATION POLICY | visit_result_id가 있으면 visit_result→visit→inquiry→subscription_id와 care_record.subscription_id가 같은지 Django transaction에서 검증하고 통합 테스트 |
| 6 | `ck_subscriptions_care_record_care_type_code_allowed` | CHECK | care_type_code IN ('FILTER_REPLACEMENT','PERIODIC_CHECK','CLEANING','OTHER') |
| 7 | `ck_subscriptions_care_record_status_code_allowed` | CHECK | status_code IN ('DUE','SCHEDULED','COMPLETED','OVERDUE','CANCELLED') |
| 8 | `ck_subscriptions_care_record_source_code_allowed` | CHECK | source_code IN ('CUSTOMER','CONSULTANT','TECHNICIAN','SYSTEM','IMPORT') |

</details>

---

### 8. `support_inquiry` — 고객 문의

- 도메인: 고객 지원
- 목적: 고객 입력부터 상담·방문·후속 해결까지 동일 inquiry_id로 이어지는 최상위 업무 건이다. [공통 설계 원칙] 문의 Aggregate Root로서 state_version 낙관적 잠금과 논리 삭제를 적용하고 모든 상태 전이는 이력 원장에 기록한다. [설계 상태: 상태·이벤트·제약은 팀 승인 전]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_no` | 문의번호 | `varchar(50)` | — | Y | — | — | 화면과 업무 인계에 사용하는 문의번호 · UNIQUE |
| 3 | `subscription_id` | 구독식별자 | `uuid` | — | Y | — | 물리 FK: subscriptions_customer_subscription.id | 문의 대상 고객·제품 구독 · ON DELETE RESTRICT |
| 4 | `initiated_by_id` | 접수사용자식별자 | `uuid` | — | Y | — | 물리 FK: accounts_user.id | 문의를 최초 접수한 사용자 · ON DELETE RESTRICT |
| 5 | `assigned_consultant_id` | 담당상담사식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 현재 담당 상담사 · ON DELETE RESTRICT |
| 6 | `current_owner_id` | 현재담당자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 현재 고객 행동·상담·방문 단계를 담당하는 사용자 snapshot · ON DELETE RESTRICT; 시스템 처리 중에는 NULL |
| 7 | `current_owner_role_code` | 현재담당역할코드 | `varchar(40)` | — | — | — | 논리 코드: common_code(group=USER_ROLE) | CUSTOMER, CONSULTANT, TECHNICIAN · 담당자 ID와 함께 설정 |
| 8 | `channel_code` | 접수채널코드 | `varchar(40)` | — | Y | `'WEB'` | 논리 코드: common_code(group=INQUIRY_CHANNEL) | WEB, MOBILE, PHONE, OPERATOR · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 · 모바일 앱은 API 요청에서 MOBILE을 명시하고 WEB 기본값에 의존하지 않는다. |
| 9 | `raw_text` | 고객원문 | `text` | — | — | — | — | 고객이 최초 입력한 자연어 증상. 선택 증상만 있는 경우 null 허용 · APPLICATION VALIDATION: 연결된 증상 선택이 없으면 raw_text trim 후 nonblank. 배열명·최대 선택 수는 팀 결정 필요 |
| 10 | `status_code` | 문의상태코드 | `varchar(40)` | — | Y | `'DRAFT'` | 논리 코드: common_code(group=INQUIRY_STATUS) | DRAFT, QUESTIONNAIRE_IN_PROGRESS, PRODUCT_VALIDATION_FAILED, AI_GUIDANCE_READY, CONSULTATION_PENDING, CONSULTATION_IN_PROGRESS, VISIT_REVIEW_PENDING, VISIT_PENDING, VISIT_IN_PROGRESS, COMPLETION_PENDING, RESOLVED, REOPENED · State Machine으로만 변경; 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 11 | `state_version` | 상태버전 | `integer` | — | Y | `1` | — | 상태 전환 시마다 1 증가하는 낙관적 잠금 버전 · CHECK state_version > 0 |
| 12 | `priority_code` | 우선순위코드 | `varchar(40)` | — | Y | `'NORMAL'` | 논리 코드: common_code(group=PRIORITY) | 상담 처리 우선순위 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 13 | `risk_level_code` | 현재위험도코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=RISK_LEVEL) | 평가 완료 후 저장하는 현재 위험도 캐시: general, caution, danger. 정보 부족·근거 없음은 general이 아님 · 기본값 없음; 위험 평가 전 null. 근거 없음은 PENDING_CONSULTATION 처리하며 정확한 상태 계약은 팀 결정 필요 |
| 14 | `usage_guidance_status` | 사용안내코드 | `varchar(40)` | — | — | — | 논리 코드: common_code(group=USAGE_GUIDANCE_STATUS) | NORMAL, PARTIAL_STOP, TOTAL_STOP, PENDING_CONSULTATION · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 15 | `usage_guidance_message` | 사용안내메시지 | `text` | — | — | — | — | 역할별 화면에 표시하는 검증된 사용 안내 문장 |
| 16 | `restricted_functions` | 제한기능목록 | `jsonb` | — | Y | `'[]'::jsonb` | — | 제한 출수·기능 코드, 범위, 사유 배열 |
| 17 | `next_action` | 다음행동 | `jsonb` | — | Y | `'{}'::jsonb` | — | code, message, owner_role을 포함한 다음 행동 object |
| 18 | `requires_consultation` | 상담필요여부 | `boolean` | — | — | — | — | 안전·근거·미해결 조건으로 상담이 필요한지 여부 |
| 19 | `customer_action_required` | 고객행동필요여부 | `boolean` | — | Y | `true` | — | 현재 고객 입력·확인·조치가 필요한지 여부 |
| 20 | `completion_route_code` | 완료경로코드 | `varchar(40)` | — | — | — | 논리 코드: common_code(group=COMPLETION_ROUTE) | SELF_HELP, CONSULTATION, VISIT · 완료 경로 확정 전 NULL |
| 21 | `required_finalizer_role_code` | 최종완료담당역할코드 | `varchar(40)` | — | — | — | 논리 코드: common_code(group=USER_ROLE) | CONSULTANT 또는 TECHNICIAN · 상담·방문 경로에서만 설정 |
| 22 | `required_finalizer_user_id` | 최종완료담당자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | COMPLETION_PENDING 진입 시 snapshot한 상담사 또는 기사 · ON DELETE RESTRICT |
| 23 | `opened_at` | 접수일시 | `timestamptz` | — | — | — | — | SUBMIT_SYMPTOM으로 최초 증상이 접수된 일시 |
| 24 | `closed_at` | 종결일시 | `timestamptz` | — | — | — | — | 문의가 해결 또는 종결된 일시 |
| 25 | `deleted_at` | 삭제일시 | `timestamptz` | — | — | — | — | 사용자 화면에서 숨긴 논리 삭제 시각 · 상태·AI·검색·근거 이력 물리 삭제 금지 |
| 26 | `deleted_by_id` | 삭제처리자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 논리 삭제를 수행한 사용자 · ON DELETE RESTRICT |
| 27 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 28 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_support_inquiry` | BTREE | Y | id |
| 2 | `ux_support_inquiry_no` | BTREE | Y | inquiry_no |
| 3 | `ix_inquiry_queue` | BTREE | N | status_code, risk_level_code, priority_code, opened_at / WHERE deleted_at IS NULL AND closed_at IS NULL |
| 4 | `ix_inquiry_assignee` | BTREE | N | assigned_consultant_id, status_code, opened_at |
| 5 | `ix_inquiry_subscription` | BTREE | N | subscription_id, opened_at DESC |
| 6 | `ix_inquiry_active` | BTREE | N | opened_at DESC / WHERE deleted_at IS NULL |
| 7 | `ux_inquiry_id_subscription` | BTREE | Y | id, subscription_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_inquiry_state_version` | CHECK | state_version > 0 |
| 2 | `ck_inquiry_time_order` | CHECK | closed_at IS NULL OR closed_at >= COALESCE(opened_at, created_at) |
| 3 | `ck_inquiry_terminal_fields` | CHECK | (status_code='RESOLVED' AND closed_at IS NOT NULL) OR (status_code<>'RESOLVED' AND closed_at IS NULL) |
| 4 | `ck_inquiry_deleted_pair` | CHECK | (deleted_at IS NULL) = (deleted_by_id IS NULL) |
| 5 | `ck_inquiry_owner_pair` | CHECK | (current_owner_id IS NULL AND current_owner_role_code IS NULL) OR (current_owner_id IS NOT NULL AND current_owner_role_code IN ('CUSTOMER','CONSULTANT','TECHNICIAN')) |
| 6 | `ck_inquiry_guidance_snapshot` | CHECK | jsonb_typeof(restricted_functions)='array' AND jsonb_typeof(next_action)='object' AND ((usage_guidance_status IS NULL AND usage_guidance_message IS NULL AND requires_consultation IS NULL) OR (usage_guidance_status IS NOT NULL AND usage_guidance_message IS NOT NULL AND requires_consultation IS NOT NULL)) |
| 7 | `ck_inquiry_guidance_ready` | CHECK | status_code<>'AI_GUIDANCE_READY' OR (usage_guidance_status IS NOT NULL AND usage_guidance_message IS NOT NULL AND requires_consultation IS NOT NULL AND next_action<>'{}'::jsonb) |
| 8 | `ck_inquiry_usage_guidance_semantics` | CHECK | (risk_level_code<>'caution' OR usage_guidance_status IN ('PARTIAL_STOP','TOTAL_STOP','PENDING_CONSULTATION')) AND (usage_guidance_status IS NULL OR usage_guidance_status<>'PENDING_CONSULTATION' OR requires_consultation=true) AND (usage_guidance_status IS NULL OR usage_guidance_status<>'PARTIAL_STOP' OR jsonb_array_length(restricted_functions)>0) |
| 9 | `ck_inquiry_danger_safety` | CHECK | risk_level_code<>'danger' OR (usage_guidance_status='TOTAL_STOP' AND requires_consultation=true) |
| 10 | `ck_inquiry_completion_route` | CHECK | (completion_route_code IS NULL AND required_finalizer_role_code IS NULL AND required_finalizer_user_id IS NULL) OR (completion_route_code='SELF_HELP' AND required_finalizer_role_code IS NULL AND required_finalizer_user_id IS NULL) OR (completion_route_code='CONSULTATION' AND required_finalizer_role_code='CONSULTANT' AND required_finalizer_user_id IS NOT NULL) OR (completion_route_code='VISIT' AND required_finalizer_role_code='TECHNICIAN' AND required_finalizer_user_id IS NOT NULL) |
| 11 | `ck_inquiry_completion_state` | CHECK | (status_code<>'COMPLETION_PENDING' OR (completion_route_code IN ('CONSULTATION','VISIT') AND required_finalizer_user_id IS NOT NULL)) AND (status_code<>'RESOLVED' OR completion_route_code IS NOT NULL) |
| 12 | `ck_inquiry_resolved_snapshot` | CHECK | status_code<>'RESOLVED' OR (current_owner_id IS NULL AND current_owner_role_code IS NULL AND customer_action_required=false) |
| 13 | `policy_inquiry_owner_and_finalizer_roles` | APPLICATION POLICY | current_owner와 required_finalizer의 계정 role·실제 상담/방문 배정을 Django State Machine에서 검증 |
| 14 | `policy_inquiry_product_validation_gate` | APPLICATION POLICY | PRODUCT_VALIDATION_FAILED에서는 FastAPI·RAG 호출 0회; 제품·필수값 수정 후 SUBMIT_SYMPTOM만 허용 |
| 15 | `policy_inquiry_guidance_ready_evidence` | APPLICATION POLICY | AI_GUIDANCE_READY 진입 전 PASSED AI schema, APPROVED guidance, 검증된 EvidenceLink 1건 이상과 안전 guard를 같은 Django transaction에서 검증 |
| 16 | `ck_support_inquiry_current_owner_role_code_allowed` | CHECK | (current_owner_role_code IS NULL OR current_owner_role_code IN ('CUSTOMER','CONSULTANT','TECHNICIAN','OPERATOR')) |
| 17 | `ck_support_inquiry_channel_code_allowed` | CHECK | channel_code IN ('WEB','MOBILE','PHONE','OPERATOR') |
| 18 | `ck_support_inquiry_status_code_allowed` | CHECK | status_code IN ('DRAFT','QUESTIONNAIRE_IN_PROGRESS','PRODUCT_VALIDATION_FAILED','AI_GUIDANCE_READY','CONSULTATION_PENDING','CONSULTATION_IN_PROGRESS','VISIT_REVIEW_PENDING','VISIT_PENDING','VISIT_IN_PROGRESS','COMPLETION_PENDING','RESOLVED','REOPENED') |
| 19 | `ck_support_inquiry_priority_code_allowed` | CHECK | priority_code IN ('LOW','NORMAL','HIGH','URGENT') |
| 20 | `ck_support_inquiry_risk_level_code_allowed` | CHECK | risk_level_code IN ('general','caution','danger') |
| 21 | `ck_support_inquiry_usage_guidance_status_allowed` | CHECK | (usage_guidance_status IS NULL OR usage_guidance_status IN ('NORMAL','PARTIAL_STOP','TOTAL_STOP','PENDING_CONSULTATION')) |
| 22 | `ck_support_inquiry_completion_route_code_allowed` | CHECK | (completion_route_code IS NULL OR completion_route_code IN ('SELF_HELP','CONSULTATION','VISIT')) |
| 23 | `ck_support_inquiry_required_finalizer_role_code_allowed` | CHECK | (required_finalizer_role_code IS NULL OR required_finalizer_role_code IN ('CUSTOMER','CONSULTANT','TECHNICIAN','OPERATOR')) |

</details>

---

### 9. `support_inquiry_symptom` — 문의 증상 구조화

- 도메인: 고객 지원
- 목적: 고객 자연어를 유형·발생 조건·동반 증상으로 구조화한 현재 증상 요약을 저장한다. [공통 설계 원칙] 검증된 구조화 payload와 AI 실행·고객 확인 주체를 추적하는 문의별 현재 증상 스냅샷이다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 구조화 대상 문의 · UNIQUE, ON DELETE RESTRICT |
| 3 | `symptom_type_code` | 증상유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=SYMPTOM_TYPE) | 누수, 출수불량, 온도이상 등 대표 유형 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 4 | `occurrence_condition` | 발생조건 | `text` | — | — | — | — | 언제·어떤 동작에서 발생하는지 구조화한 설명 |
| 5 | `accompanying_symptoms` | 동반증상 | `text` | — | — | — | — | 냄새, 소음, 표시등 등 함께 나타난 현상 |
| 6 | `duration_text` | 발생기간 | `varchar(100)` | — | — | — | — | 발생 시작 시점 또는 지속 기간 |
| 7 | `location_text` | 발생위치 | `varchar(200)` | — | — | — | — | 누수·소음 등 증상이 나타난 위치 |
| 8 | `structured_payload` | 구조화원문 | `jsonb` | — | Y | — | — | Pydantic 출력 전체를 보존하는 버전형 JSON |
| 9 | `schema_version` | 스키마버전 | `varchar(30)` | — | Y | `'v1'` | — | FastAPI 구조화 DTO 버전 |
| 10 | `source_ai_run_id` | 원천AI실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_ai_run.id | 구조화 결과를 생성한 AI 실행 · ON DELETE RESTRICT |
| 11 | `is_customer_confirmed` | 고객확인여부 | `boolean` | — | Y | `false` | — | 고객이 구조화 결과를 확인했는지 여부 |
| 12 | `confirmed_by_id` | 확인자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 구조화 증상을 확인한 고객 또는 대리 기록자 · ON DELETE RESTRICT |
| 13 | `confirmed_at` | 확인일시 | `timestamptz` | — | — | — | — | 고객 확인이 완료된 일시 |
| 14 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 15 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_inquiry_symptom` | BTREE | Y | id |
| 2 | `ux_inquiry_symptom_inquiry` | BTREE | Y | inquiry_id |
| 3 | `ix_inquiry_symptom_type` | BTREE | N | symptom_type_code |
| 4 | `ix_inquiry_symptom_ai_run` | BTREE | N | source_ai_run_id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_inquiry_symptom_payload` | CHECK | jsonb_typeof(structured_payload)='object' AND structured_payload <> '{}'::jsonb |
| 2 | `ck_inquiry_symptom_confirmation` | CHECK | (is_customer_confirmed=false AND confirmed_by_id IS NULL AND confirmed_at IS NULL) OR (is_customer_confirmed=true AND confirmed_by_id IS NOT NULL AND confirmed_at IS NOT NULL) |
| 3 | `fk_inquiry_symptom_ai_run_inquiry` | FOREIGN KEY | (source_ai_run_id, inquiry_id) REFERENCES aiops_ai_run(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 4 | `policy_inquiry_symptom_ai_source` | APPLICATION POLICY | source_ai_run_id가 있으면 aiops_ai_run.task_type_code='STRUCTURE_SYMPTOM' AND schema_validation_status_code='PASSED' 검증 |
| 5 | `ck_support_inquiry_symptom_symptom_type_code_allowed` | CHECK | symptom_type_code IN ('NO_WATER','LOW_FLOW','LEAK','ODOR','TASTE','TEMPERATURE_ABNORMAL','NOISE','DISPLAY_ERROR','OTHER') |

</details>

---

### 10. `support_inquiry_qa` — 문의 추가 문진

- 도메인: 고객 지원
- 목적: 문의별 정적·규칙·AI·상담사 질문과 고객 답변을 순서대로 누적하고 AI 생성 출처를 같은 inquiry_id로 보존한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 추가 질문·답변을 누적하는 문의 · ON DELETE RESTRICT |
| 3 | `sequence_no` | 문진순번 | `smallint` | — | Y | — | — | 문의 안에서 질문·답변 표시 순서 · CHECK sequence_no > 0 |
| 4 | `question_code` | 질문코드 | `varchar(80)` | — | — | — | — | 규칙 기반 질문의 안정 식별자 |
| 5 | `question_text` | 질문내용 | `text` | — | Y | — | — | 고객에게 표시한 질문 문장 |
| 6 | `answer_type_code` | 답변유형코드 | `varchar(40)` | — | Y | `'FREE_TEXT'` | 논리 코드: common_code(group=ANSWER_TYPE) | SINGLE_CHOICE, MULTI_CHOICE, FREE_TEXT, BOOLEAN, NUMBER · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `answer_text` | 답변내용 | `text` | — | — | — | — | 표시·검색용 정규화 답변 |
| 8 | `answer_payload` | 답변원문 | `jsonb` | — | — | — | — | 다중선택·단위 포함 값 등 원형 답변 |
| 9 | `asked_by_type_code` | 질문생성주체코드 | `varchar(40)` | — | Y | `'RULE'` | 논리 코드: common_code(group=QUESTION_ORIGIN) | STATIC, RULE, AI, CONSULTANT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 10 | `source_ai_run_id` | 원천AI실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_ai_run.id | AI가 생성한 질문인 경우의 실행 식별자 · ON DELETE RESTRICT |
| 11 | `answered_by_id` | 답변자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 고객 직접 답변 또는 상담사 대리 입력 계정 · ON DELETE RESTRICT |
| 12 | `answered_at` | 답변일시 | `timestamptz` | — | — | — | — | 고객 답변 제출 일시 |
| 13 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 질문 생성 일시 |
| 14 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_inquiry_qa` | BTREE | Y | id |
| 2 | `ux_inquiry_qa_sequence` | BTREE | Y | inquiry_id, sequence_no |
| 3 | `ix_inquiry_qa_answered` | BTREE | N | inquiry_id, answered_at |
| 4 | `ux_inquiry_qa_question` | BTREE | Y | inquiry_id, question_code / WHERE question_code IS NOT NULL |
| 5 | `ix_inquiry_qa_ai_run` | BTREE | N | source_ai_run_id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_inquiry_qa_answer_consistency` | CHECK | answered_at IS NULL OR (answered_by_id IS NOT NULL AND (answer_text IS NOT NULL OR answer_payload IS NOT NULL)) |
| 2 | `ck_inquiry_qa_sequence` | CHECK | sequence_no > 0 |
| 3 | `ck_inquiry_qa_ai_origin` | CHECK | (asked_by_type_code='AI' AND source_ai_run_id IS NOT NULL) OR (asked_by_type_code<>'AI' AND source_ai_run_id IS NULL) |
| 4 | `fk_inquiry_qa_ai_run_inquiry` | FOREIGN KEY | (source_ai_run_id, inquiry_id) REFERENCES aiops_ai_run(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 5 | `policy_inquiry_qa_ai_task` | APPLICATION POLICY | AI 질문이면 aiops_ai_run.task_type_code='GENERATE_QUESTIONS' AND schema_validation_status_code='PASSED' 검증 |
| 6 | `ck_support_inquiry_qa_answer_type_code_allowed` | CHECK | answer_type_code IN ('SINGLE_CHOICE','MULTI_CHOICE','FREE_TEXT','BOOLEAN','NUMBER') |
| 7 | `ck_support_inquiry_qa_asked_by_type_code_allowed` | CHECK | asked_by_type_code IN ('STATIC','RULE','AI','CONSULTANT') |

</details>

---

### 11. `support_symptom_assessment` — 증상 위험도 판정

- 도메인: 고객 지원
- 목적: 규칙과 AI가 산출한 위험도·우선순위·사용 제한·상담 전환 판정 이력을 버전별로 저장한다. [공통 설계 원칙] 판정 버전과 안전 규칙 세트를 함께 저장하는 append-only 결과이며 수정 대신 새 버전을 생성한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 판정 대상 문의 · ON DELETE RESTRICT |
| 3 | `assessment_version` | 판정버전 | `integer` | — | Y | `1` | — | 문의 안의 판정 버전 · CHECK assessment_version > 0 |
| 4 | `ruleset_version` | 안전규칙세트버전 | `varchar(40)` | — | Y | — | — | 판정에 적용한 코드 기반 안전 규칙 세트 버전 |
| 5 | `risk_level_code` | 위험도코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=RISK_LEVEL) | general, caution, danger · contracts/codes/risk-levels.yaml과 일치 |
| 6 | `priority_code` | 우선순위코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=PRIORITY) | LOW, NORMAL, HIGH, URGENT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `usage_guidance_status` | 사용안내코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=USAGE_GUIDANCE_STATUS) | NORMAL, PARTIAL_STOP, TOTAL_STOP, PENDING_CONSULTATION · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 8 | `requires_consultation` | 상담필요여부 | `boolean` | — | Y | `false` | — | 자가안내보다 상담 전환을 우선할지 여부 |
| 9 | `reason` | 판정사유 | `text` | — | Y | — | — | 판정 근거와 고객에게 설명할 핵심 사유 |
| 10 | `rule_result` | 규칙판정결과 | `jsonb` | — | Y | `'{}'::jsonb` | — | 적용된 안전 규칙과 명중 조건 |
| 11 | `assessed_by_type_code` | 판정주체코드 | `varchar(40)` | — | Y | `'RULE'` | 논리 코드: common_code(group=ASSESSMENT_ORIGIN) | RULE, AI, CONSULTANT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 12 | `ai_run_id` | AI실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_ai_run.id | AI가 관여한 경우의 실행 이력 · ON DELETE RESTRICT |
| 13 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 판정이 확정된 일시 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_symptom_assessment` | BTREE | Y | id |
| 2 | `ux_assessment_version` | BTREE | Y | inquiry_id, assessment_version |
| 3 | `ix_assessment_risk` | BTREE | N | risk_level_code, created_at |
| 4 | `ix_assessment_ai_run` | BTREE | N | ai_run_id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_assessment_version_positive` | CHECK | assessment_version > 0 |
| 2 | `ck_assessment_rule_result_object` | CHECK | jsonb_typeof(rule_result)='object' |
| 3 | `ck_assessment_ai_origin` | CHECK | assessed_by_type_code <> 'AI' OR ai_run_id IS NOT NULL |
| 4 | `fk_assessment_ai_run_inquiry` | FOREIGN KEY | (ai_run_id, inquiry_id) REFERENCES aiops_ai_run(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 5 | `ck_assessment_danger_safety` | CHECK | risk_level_code<>'danger' OR (usage_guidance_status='TOTAL_STOP' AND requires_consultation=true) |
| 6 | `ck_assessment_caution_safety` | CHECK | risk_level_code<>'caution' OR usage_guidance_status IN ('PARTIAL_STOP','TOTAL_STOP','PENDING_CONSULTATION') |
| 7 | `ck_assessment_danger_priority` | CHECK | risk_level_code<>'danger' OR priority_code='URGENT' |
| 8 | `ck_assessment_pending_consultation` | CHECK | usage_guidance_status<>'PENDING_CONSULTATION' OR requires_consultation=true |
| 9 | `policy_assessment_ai_task` | APPLICATION POLICY | ai_run_id가 있으면 aiops_ai_run.task_type_code='ASSESS_RISK' AND schema_validation_status_code='PASSED'인지 Django에서 검증 |
| 10 | `ck_support_symptom_assessment_risk_level_code_allowed` | CHECK | risk_level_code IN ('general','caution','danger') |
| 11 | `ck_support_symptom_assessment_priority_code_allowed` | CHECK | priority_code IN ('LOW','NORMAL','HIGH','URGENT') |
| 12 | `ck_support_symptom_assessment_usage_guidance_status_allowed` | CHECK | usage_guidance_status IN ('NORMAL','PARTIAL_STOP','TOTAL_STOP','PENDING_CONSULTATION') |
| 13 | `ck_support_symptom_assessment_assessed_by_type_code_allowed` | CHECK | assessed_by_type_code IN ('RULE','AI','CONSULTANT') |

</details>

---

### 12. `support_guidance` — 고객 안내

- 도메인: 고객 지원
- 목적: 검증된 공식 근거로 생성한 고객 안내, 안전문구, 근거 충분성 및 검토 상태를 버전별로 저장한다. [공통 설계 원칙] 안내 버전과 검토 상태를 분리하고 승인 후 수정 대신 새 guidance_version을 생성한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 안내 대상 문의 · ON DELETE RESTRICT |
| 3 | `guidance_version` | 안내버전 | `integer` | — | Y | `1` | — | 문의 안의 고객 안내 버전 · CHECK guidance_version > 0 |
| 4 | `review_status_code` | 검토상태코드 | `varchar(40)` | — | Y | `'PENDING'` | 논리 코드: common_code(group=GUIDANCE_REVIEW_STATUS) | PENDING, APPROVED, REJECTED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `title` | 안내제목 | `varchar(200)` | — | Y | — | — | 고객 화면에 표시할 안내 제목 |
| 6 | `summary_text` | 안내요약 | `text` | — | Y | — | — | 증상과 다음 행동을 설명하는 요약 |
| 7 | `safety_notice` | 안전주의문구 | `text` | — | — | — | — | 위험 신호와 사용 제한·중지 안내 |
| 8 | `evidence_sufficiency_code` | 근거충분성코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=EVIDENCE_SUFFICIENCY) | SUFFICIENT, PARTIAL, INSUFFICIENT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 9 | `requires_consultation` | 상담전환여부 | `boolean` | — | Y | `false` | — | 안내 후 상담 연결이 필요한지 여부 |
| 10 | `generated_by_ai_run_id` | 생성AI실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_ai_run.id | 안내 초안을 생성한 AI 실행 · ON DELETE RESTRICT |
| 11 | `reviewed_by_id` | 검토자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 안내를 검토한 상담사 또는 운영자 · ON DELETE RESTRICT |
| 12 | `reviewed_at` | 검토일시 | `timestamptz` | — | — | — | — | 사람 검토가 완료된 일시 |
| 13 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 안내 버전 생성 일시 |
| 14 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_support_guidance` | BTREE | Y | id |
| 2 | `ux_guidance_version` | BTREE | Y | inquiry_id, guidance_version |
| 3 | `ix_guidance_review_queue` | BTREE | N | review_status_code, created_at / WHERE review_status_code='PENDING' |
| 4 | `ix_guidance_ai_run` | BTREE | N | generated_by_ai_run_id, inquiry_id |
| 5 | `ux_guidance_id_inquiry` | BTREE | Y | id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_guidance_review_fields` | CHECK | (review_status_code='PENDING' AND reviewed_by_id IS NULL AND reviewed_at IS NULL) OR (review_status_code IN ('APPROVED','REJECTED') AND reviewed_by_id IS NOT NULL AND reviewed_at IS NOT NULL) |
| 2 | `ck_guidance_insufficient_handoff` | CHECK | evidence_sufficiency_code <> 'INSUFFICIENT' OR requires_consultation=true |
| 3 | `fk_guidance_ai_run_inquiry` | FOREIGN KEY | (generated_by_ai_run_id, inquiry_id) REFERENCES aiops_ai_run(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 4 | `policy_guidance_approved_immutable` | APPLICATION POLICY | APPROVED 안내는 UPDATE/DELETE 금지; 변경은 새 guidance version 생성으로만 처리하고 통합 테스트 |
| 5 | `ck_support_guidance_review_status_code_allowed` | CHECK | review_status_code IN ('PENDING','APPROVED','REJECTED') |
| 6 | `ck_support_guidance_evidence_sufficiency_code_allowed` | CHECK | evidence_sufficiency_code IN ('SUFFICIENT','PARTIAL','INSUFFICIENT') |

</details>

---

### 13. `support_guidance_item` — 고객 안내 단계

- 도메인: 고객 지원
- 목적: 고객 안내를 안전한 확인·조치 단계로 나누고 각 단계의 주의사항과 확인 여부를 관리한다. [공통 설계 원칙] 부모 안내의 버전 단위 조치 단계이며 승인 전만 수정하고 단계 순서를 고유하게 유지한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `guidance_id` | 고객안내식별자 | `uuid` | — | Y | — | 물리 FK: support_guidance.id | 단계가 속한 고객 안내 버전 · ON DELETE RESTRICT |
| 3 | `step_no` | 단계순번 | `smallint` | — | Y | — | — | 안내 안의 표시 순서 · CHECK step_no > 0 |
| 4 | `action_type_code` | 조치유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=GUIDANCE_ACTION) | CHECK, CLEAN, RESET, RESTRICT_USE, CONTACT_SUPPORT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `instruction_text` | 안내내용 | `text` | — | Y | — | — | 고객이 수행할 안전한 확인 또는 다음 행동 |
| 6 | `caution_text` | 주의사항 | `text` | — | — | — | — | 단계 수행 전후의 금지·주의 문구 |
| 7 | `requires_confirmation` | 결과확인필요여부 | `boolean` | — | Y | `true` | — | 고객 수행 결과를 받아야 하는지 여부 |
| 8 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 안내 단계 생성 일시 |
| 9 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_guidance_item` | BTREE | Y | id |
| 2 | `ux_guidance_item_step` | BTREE | Y | guidance_id, step_no |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_guidance_item_step` | CHECK | step_no > 0 |
| 2 | `ck_guidance_item_instruction` | CHECK | btrim(instruction_text) <> '' |
| 3 | `policy_guidance_item_approved_immutable` | APPLICATION POLICY | 부모 guidance가 APPROVED이면 항목 UPDATE/DELETE 금지; 새 안내 버전에서만 변경 |
| 4 | `ck_support_guidance_item_action_type_code_allowed` | CHECK | action_type_code IN ('CHECK','CLEAN','RESET','RESTRICT_USE','CONTACT_SUPPORT') |

</details>

---

### 14. `support_customer_action_result` — 고객 자가조치 결과

- 도메인: 고객 지원
- 목적: 고객이 안내 단계별로 수행한 결과와 의견을 저장하여 상담·방문에서 재사용한다. [공통 설계 원칙] 고객 제출을 idempotency_key로 중복 방지하는 append-only 시도 이력이다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `guidance_item_id` | 안내단계식별자 | `uuid` | — | Y | — | 물리 FK: support_guidance_item.id | 고객이 수행한 안내 단계 · ON DELETE RESTRICT |
| 3 | `attempt_no` | 시도순번 | `smallint` | — | Y | `1` | — | 동일 단계의 수행 시도 순번 · CHECK attempt_no > 0 |
| 4 | `result_code` | 조치결과코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=ACTION_RESULT) | RESOLVED, IMPROVED, UNCHANGED, WORSE, NOT_PERFORMED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `result_text` | 조치결과설명 | `text` | — | — | — | — | 고객이 입력한 수행 결과 설명 |
| 6 | `performed_at` | 수행일시 | `timestamptz` | — | — | — | — | 고객이 해당 단계를 수행한 일시 |
| 7 | `customer_comment` | 고객의견 | `text` | — | — | — | — | 추가로 전달할 고객 의견 |
| 8 | `submitted_by_id` | 제출자식별자 | `uuid` | — | Y | — | 물리 FK: accounts_user.id | 고객 직접 제출 또는 상담사 대리 입력 계정; 역할·대리입력 사유는 Django AuditLog로 추적 · ON DELETE RESTRICT |
| 9 | `idempotency_key` | 멱등성키 | `varchar(128)` | — | Y | — | — | 중복 제출을 동일 결과로 처리하기 위한 요청 키 · UNIQUE; API 전달 위치(Header/Body/Metadata)와 생성 주체는 팀 결정 필요 |
| 10 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 결과 제출 일시 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_customer_action_result` | BTREE | Y | id |
| 2 | `ux_action_result_attempt` | BTREE | Y | guidance_item_id, attempt_no |
| 3 | `ux_action_result_idempotency` | BTREE | Y | idempotency_key |
| 4 | `ix_action_result_guidance_item` | BTREE | N | guidance_item_id, created_at |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_action_result_performed` | CHECK | (result_code='NOT_PERFORMED' AND performed_at IS NULL) OR (result_code<>'NOT_PERFORMED' AND performed_at IS NOT NULL) |
| 2 | `ck_action_result_attempt` | CHECK | attempt_no > 0 |
| 3 | `policy_action_result_append_only` | APPLICATION POLICY | 조치 결과는 INSERT 전용; 정정은 새 attempt_no 행으로 추가하고 UPDATE/DELETE 권한 미부여 |
| 4 | `ck_support_customer_action_result_result_code_allowed` | CHECK | result_code IN ('RESOLVED','IMPROVED','UNCHANGED','WORSE','NOT_PERFORMED') |

</details>

---

### 15. `support_consultation` — 상담 처리

- 도메인: 고객 지원
- 목적: 상담사가 문의를 검토하고 고객 응대·방문 필요 여부·다음 행동을 확정한 기록이다. [공통 설계 원칙] 상담 배정·진행·완료를 state_version으로 동시성 제어하고 상태 전이를 원장에 기록한다. [설계 상태: 상태·이벤트·제약은 팀 승인 전]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 상담 대상 문의 · ON DELETE RESTRICT |
| 3 | `consultant_id` | 상담사식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 상담을 담당한 사용자 · ON DELETE RESTRICT |
| 4 | `assigned_at` | 배정일시 | `timestamptz` | — | — | — | — | 상담사가 문의에 배정된 일시 |
| 5 | `status_code` | 상담상태코드 | `varchar(40)` | — | Y | `'WAITING'` | 논리 코드: common_code(group=CONSULTATION_STATUS) | WAITING, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 6 | `state_version` | 상태버전 | `integer` | — | Y | `1` | — | 상담 상태 전환의 낙관적 잠금 버전 · CHECK state_version > 0 |
| 7 | `started_at` | 상담시작일시 | `timestamptz` | — | — | — | — | 상담사가 처리를 시작한 일시 |
| 8 | `ended_at` | 상담종료일시 | `timestamptz` | — | — | — | — | 상담 종료 또는 취소 확정 시각 |
| 9 | `customer_summary` | 고객요약 | `text` | — | Y | — | — | 제품·증상·문진·자가조치 구조화 요약 |
| 10 | `consultant_notes` | 상담사메모 | `text` | — | — | — | — | 상담 중 확인한 추가 사실과 판단 |
| 11 | `disposition_code` | 상담결과코드 | `varchar(40)` | — | — | — | 논리 코드: common_code(group=CONSULTATION_DISPOSITION) | 안내완료, 방문전환, 추가확인 등 결과 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 12 | `visit_required` | 방문필요여부 | `boolean` | — | Y | `false` | — | 방문 A/S로 전환할지 여부 |
| 13 | `ai_summary_draft` | AI상담요약초안 | `text` | — | — | — | — | AI가 생성한 고정 스키마 상담 요약 초안 |
| 14 | `final_summary` | 상담최종요약 | `text` | — | — | — | — | 상담사가 검토·수정한 최종 요약 |
| 15 | `next_action` | 다음조치 | `text` | — | — | — | — | 고객·기사·운영자가 수행할 다음 행동 |
| 16 | `cancellation_reason` | 취소사유 | `text` | — | — | — | — | 상담 취소 사유 · CANCELLED 상태에서 필수 |
| 17 | `deleted_at` | 삭제일시 | `timestamptz` | — | — | — | — | 업무 원장 논리 삭제 시각 · 물리 삭제 금지 |
| 18 | `deleted_by_id` | 삭제처리자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 논리 삭제를 수행한 사용자 · ON DELETE RESTRICT |
| 19 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 20 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_support_consultation` | BTREE | Y | id |
| 2 | `ix_consultation_inquiry` | BTREE | N | inquiry_id, created_at DESC |
| 3 | `ix_consultation_queue` | BTREE | N | status_code, created_at / WHERE status_code IN ('WAITING','ASSIGNED','IN_PROGRESS') |
| 4 | `ix_consultation_consultant` | BTREE | N | consultant_id, status_code, updated_at DESC |
| 5 | `ux_consultation_id_inquiry` | BTREE | Y | id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_consultation_state_version` | CHECK | state_version > 0 |
| 2 | `ck_consultation_time_order` | CHECK | ended_at IS NULL OR (status_code='CANCELLED' AND ended_at>=created_at) OR (started_at IS NOT NULL AND ended_at>=started_at) |
| 3 | `ck_consultation_assignment` | CHECK | (status_code='WAITING' AND consultant_id IS NULL AND assigned_at IS NULL) OR (status_code='CANCELLED' AND ((consultant_id IS NULL AND assigned_at IS NULL) OR (consultant_id IS NOT NULL AND assigned_at IS NOT NULL))) OR (status_code NOT IN ('WAITING','CANCELLED') AND consultant_id IS NOT NULL AND assigned_at IS NOT NULL) |
| 4 | `ck_consultation_in_progress` | CHECK | status_code <> 'IN_PROGRESS' OR started_at IS NOT NULL |
| 5 | `ck_consultation_completed` | CHECK | status_code <> 'COMPLETED' OR (ended_at IS NOT NULL AND disposition_code IS NOT NULL AND final_summary IS NOT NULL) |
| 6 | `ck_consultation_cancelled` | CHECK | status_code <> 'CANCELLED' OR (ended_at IS NOT NULL AND cancellation_reason IS NOT NULL) |
| 7 | `ck_consultation_visit_disposition` | CHECK | (disposition_code IS NULL AND visit_required=false) OR (disposition_code='VISIT_REQUIRED' AND visit_required=true) OR (disposition_code IN ('SELF_CARE','ESCALATED','CLOSED') AND visit_required=false) |
| 8 | `ck_consultation_deleted_pair` | CHECK | (deleted_at IS NULL) = (deleted_by_id IS NULL) |
| 9 | `ck_support_consultation_status_code_allowed` | CHECK | status_code IN ('WAITING','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED') |
| 10 | `ck_support_consultation_disposition_code_allowed` | CHECK | (disposition_code IS NULL OR disposition_code IN ('SELF_CARE','VISIT_REQUIRED','ESCALATED','CLOSED')) |

</details>

---

### 16. `support_handoff_report` — 방문기사 인계 리포트

- 도메인: 고객 지원
- 목적: 상담 결과·제품·케어·위험도·공식 근거·우선 점검 항목을 기사에게 전달하는 버전형 리포트다. [공통 설계 원칙] AI 초안과 상담사 확정본의 상태를 분리한 버전형 인계 리포트다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 리포트 대상 문의 · ON DELETE RESTRICT |
| 3 | `consultation_id` | 상담식별자 | `uuid` | — | Y | — | 물리 FK: support_consultation.id | 인계 리포트의 기준 상담 기록 · ON DELETE RESTRICT |
| 4 | `report_version` | 리포트버전 | `integer` | — | Y | `1` | — | 문의 안의 기사 인계 리포트 버전 · CHECK report_version > 0 |
| 5 | `report_status_code` | 리포트상태코드 | `varchar(40)` | — | Y | `'DRAFT'` | 논리 코드: common_code(group=HANDOFF_STATUS) | DRAFT, CONFIRMED, SUPERSEDED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 6 | `product_summary` | 제품요약 | `text` | — | Y | — | — | 모델·설치·구독·케어 이력 요약 |
| 7 | `symptom_summary` | 증상요약 | `text` | — | Y | — | — | 고객 원문과 구조화 증상 요약 |
| 8 | `action_summary` | 조치요약 | `text` | — | Y | — | — | 자가조치와 상담 처리 결과 요약 |
| 9 | `risk_summary` | 위험요약 | `text` | — | Y | — | — | 위험도, 사용 제한, 안전 주의사항 |
| 10 | `evidence_summary` | 근거요약 | `text` | — | — | — | — | 공식 문서 근거와 적용 가능성 요약 |
| 11 | `priority_check_items` | 우선점검항목 | `jsonb` | — | Y | `'[]'::jsonb` | — | 기사가 현장에서 우선 확인할 순서형 항목 |
| 12 | `ai_draft` | AI리포트초안 | `text` | — | — | — | — | AI가 생성한 리포트 초안 |
| 13 | `consultant_final` | 상담사확정본 | `text` | — | — | — | — | 상담사가 검토·수정한 최종 인계 내용 |
| 14 | `generated_by_ai_run_id` | 생성AI실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_ai_run.id | 리포트 초안을 생성한 AI 실행 · ON DELETE RESTRICT |
| 15 | `confirmed_by_id` | 확정자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 리포트를 확정한 상담사 · ON DELETE RESTRICT |
| 16 | `confirmed_at` | 확정일시 | `timestamptz` | — | — | — | — | 상담사가 인계 리포트를 확정한 일시 |
| 17 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 리포트 버전 생성 일시 |
| 18 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_handoff_report` | BTREE | Y | id |
| 2 | `ux_handoff_report_version` | BTREE | Y | inquiry_id, report_version |
| 3 | `ix_handoff_report_consultation` | BTREE | N | consultation_id, inquiry_id |
| 4 | `ix_handoff_report_status` | BTREE | N | report_status_code, created_at |
| 5 | `ix_handoff_report_ai_run` | BTREE | N | generated_by_ai_run_id, inquiry_id |
| 6 | `ux_handoff_id_inquiry` | BTREE | Y | id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_handoff_report_version` | CHECK | report_version > 0 |
| 2 | `ck_handoff_report_confirmation` | CHECK | (report_status_code='DRAFT' AND confirmed_by_id IS NULL AND confirmed_at IS NULL) OR (report_status_code IN ('CONFIRMED','SUPERSEDED') AND consultant_final IS NOT NULL AND confirmed_by_id IS NOT NULL AND confirmed_at IS NOT NULL) |
| 3 | `ck_handoff_priority_items_array` | CHECK | jsonb_typeof(priority_check_items)='array' |
| 4 | `fk_handoff_consultation_inquiry` | FOREIGN KEY | (consultation_id, inquiry_id) REFERENCES support_consultation(id, inquiry_id) ON DELETE RESTRICT |
| 5 | `fk_handoff_ai_run_inquiry` | FOREIGN KEY | (generated_by_ai_run_id, inquiry_id) REFERENCES aiops_ai_run(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 6 | `policy_handoff_confirmation_transition` | APPLICATION POLICY | CONFIRMED는 동일 inquiry의 COMPLETED 상담과 실제 담당 상담사만 허용; SUPERSEDED는 기존 CONFIRMED 행에서만 전이 |
| 7 | `ck_support_handoff_report_report_status_code_allowed` | CHECK | report_status_code IN ('DRAFT','CONFIRMED','SUPERSEDED') |

</details>

---

### 17. `field_service_visit` — 현장 방문

- 도메인: 현장 방문
- 목적: 문의의 기사 배정, 일정 조율, 방문 진행·완료 상태와 연락·주소 스냅샷을 관리한다. [공통 설계 원칙] 화면용 visit_no와 state_version을 사용하고 일정·취소·완료 상태를 전이 원장과 함께 관리한다. [설계 상태: 상태·이벤트·제약은 팀 승인 전]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `visit_no` | 방문번호 | `varchar(50)` | — | Y | — | — | 고객·상담사·기사 화면에 표시하는 방문 업무번호 · Django 서비스 생성; UNIQUE |
| 3 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 방문 대상 문의 · ON DELETE RESTRICT |
| 4 | `handoff_report_id` | 인계리포트식별자 | `uuid` | — | Y | — | 물리 FK: support_handoff_report.id | 기사에게 제공할 확정 인계 리포트 · ON DELETE RESTRICT |
| 5 | `technician_id` | 방문기사식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 배정된 방문기사 · ON DELETE RESTRICT |
| 6 | `visit_status_code` | 방문상태코드 | `varchar(40)` | — | Y | `'ASSIGNING'` | 논리 코드: common_code(group=VISIT_STATUS) | ASSIGNING, SCHEDULING, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `state_version` | 상태버전 | `integer` | — | Y | `1` | — | 방문 상태 전환의 낙관적 잠금 버전 · CHECK state_version > 0 |
| 8 | `scheduled_start_at` | 방문예정시작일시 | `timestamptz` | — | — | — | — | 고객과 합의한 방문 예정 시작 |
| 9 | `scheduled_end_at` | 방문예정종료일시 | `timestamptz` | — | — | — | — | 고객과 합의한 방문 예정 종료 |
| 10 | `address_snapshot` | 방문주소스냅샷 | `varchar(500)` | — | Y | — | — | 방문 확정 시점의 가명·합성 주소 |
| 11 | `contact_snapshot` | 연락처스냅샷 | `varchar(100)` | — | — | — | — | 방문 확정 시점의 가명·합성 연락 정보 |
| 12 | `assigned_at` | 배정일시 | `timestamptz` | — | — | — | — | 기사 배정 일시 |
| 13 | `started_at` | 방문시작일시 | `timestamptz` | — | — | — | — | 현장 방문 처리 시작 일시 |
| 14 | `completed_at` | 방문완료일시 | `timestamptz` | — | — | — | — | 현장 방문 처리 완료 일시 |
| 15 | `cancelled_at` | 취소일시 | `timestamptz` | — | — | — | — | 방문이 취소된 일시 |
| 16 | `cancellation_reason` | 취소사유 | `text` | — | — | — | — | 고객 요청·기사 일정 등 방문 취소 사유 |
| 17 | `deleted_at` | 삭제일시 | `timestamptz` | — | — | — | — | 방문 업무 원장 논리 삭제 시각 · 물리 삭제 금지 |
| 18 | `deleted_by_id` | 삭제처리자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 논리 삭제를 수행한 사용자 · ON DELETE RESTRICT |
| 19 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 20 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_field_service_visit` | BTREE | Y | id |
| 2 | `ix_visit_inquiry` | BTREE | N | inquiry_id, created_at DESC |
| 3 | `ix_visit_technician_queue` | BTREE | N | technician_id, visit_status_code, scheduled_start_at |
| 4 | `ix_visit_schedule` | BTREE | N | visit_status_code, scheduled_start_at |
| 5 | `ux_visit_no` | BTREE | Y | visit_no |
| 6 | `ix_visit_handoff` | BTREE | N | handoff_report_id, inquiry_id |
| 7 | `ux_visit_id_inquiry` | BTREE | Y | id, inquiry_id |
| 8 | `ux_visit_id_technician` | BTREE | Y | id, technician_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_visit_state_version` | CHECK | state_version > 0 |
| 2 | `ck_visit_schedule_pair` | CHECK | (scheduled_start_at IS NULL) = (scheduled_end_at IS NULL) |
| 3 | `ck_visit_schedule_order` | CHECK | scheduled_end_at IS NULL OR scheduled_end_at > scheduled_start_at |
| 4 | `ck_visit_completion_order` | CHECK | completed_at IS NULL OR (started_at IS NOT NULL AND completed_at >= started_at) |
| 5 | `ck_visit_cancellation` | CHECK | visit_status_code <> 'CANCELLED' OR (cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) |
| 6 | `fk_visit_handoff_inquiry` | FOREIGN KEY | (handoff_report_id, inquiry_id) REFERENCES support_handoff_report(id, inquiry_id) ON DELETE RESTRICT |
| 7 | `ck_visit_assignment_schedule` | CHECK | visit_status_code NOT IN ('CONFIRMED','IN_PROGRESS','COMPLETED') OR (technician_id IS NOT NULL AND scheduled_start_at IS NOT NULL AND scheduled_end_at IS NOT NULL) |
| 8 | `ck_visit_in_progress` | CHECK | visit_status_code <> 'IN_PROGRESS' OR started_at IS NOT NULL |
| 9 | `ck_visit_completed` | CHECK | visit_status_code <> 'COMPLETED' OR (started_at IS NOT NULL AND completed_at IS NOT NULL) |
| 10 | `ck_visit_assignment_pair` | CHECK | (technician_id IS NULL AND assigned_at IS NULL) OR (technician_id IS NOT NULL AND assigned_at IS NOT NULL) |
| 11 | `ck_visit_assignment_state` | CHECK | (visit_status_code='ASSIGNING' AND technician_id IS NULL AND assigned_at IS NULL) OR (visit_status_code='CANCELLED' AND ((technician_id IS NULL AND assigned_at IS NULL) OR (technician_id IS NOT NULL AND assigned_at IS NOT NULL))) OR (visit_status_code IN ('SCHEDULING','CONFIRMED','IN_PROGRESS','COMPLETED') AND technician_id IS NOT NULL AND assigned_at IS NOT NULL) |
| 12 | `ck_visit_terminal_fields` | CHECK | (visit_status_code='COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR (visit_status_code='CANCELLED' AND completed_at IS NULL AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) OR (visit_status_code IN ('ASSIGNING','SCHEDULING','CONFIRMED','IN_PROGRESS') AND completed_at IS NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL) |
| 13 | `ck_visit_deleted_pair` | CHECK | (deleted_at IS NULL) = (deleted_by_id IS NULL) |
| 14 | `policy_visit_confirmed_handoff` | APPLICATION POLICY | 방문 생성·확정 시 handoff_report.report_status_code='CONFIRMED'와 동일 inquiry를 Django transaction에서 검증 |
| 15 | `ck_field_service_visit_visit_status_code_allowed` | CHECK | visit_status_code IN ('ASSIGNING','SCHEDULING','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED') |

</details>

---

### 18. `field_service_visit_result` — 현장 방문 결과

- 도메인: 현장 방문
- 목적: 기사의 현장 점검, 조치, 고객 안내, 해결·재방문 여부를 방문 건별로 확정 저장한다. [공통 설계 원칙] 방문별 결과를 한 번만 생성하고 idempotency_key로 방문 완료 요청의 중복을 방지한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `visit_id` | 방문식별자 | `uuid` | — | Y | — | 물리 FK: field_service_visit.id | 결과가 속한 방문 · UNIQUE, ON DELETE RESTRICT |
| 3 | `cause_category_code` | 원인분류코드 | `varchar(40)` | — | — | — | 논리 코드: common_code(group=CAUSE_CATEGORY) | 확정 진단이 아닌 업무용 원인 범주 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 4 | `inspection_summary` | 점검요약 | `text` | — | Y | — | — | 현장에서 확인한 상태와 점검 내용 |
| 5 | `action_summary` | 조치요약 | `text` | — | Y | — | — | 현장에서 수행한 안전한 조치 요약 |
| 6 | `parts_used_text` | 사용부품 | `text` | — | — | — | — | 시연용 부품 사용 내역 · MVP 재고·결제 연동 없음 |
| 7 | `customer_guidance` | 고객안내 | `text` | — | — | — | — | 방문 후 고객에게 전달한 사용·관리 안내 |
| 8 | `resolved_on_site` | 현장해결여부 | `boolean` | — | Y | `false` | — | 방문 중 고객 증상이 해결되었는지 여부 |
| 9 | `revisit_required` | 재방문필요여부 | `boolean` | — | Y | `false` | — | 추가 방문이 필요한지 여부 |
| 10 | `revisit_reason` | 재방문사유 | `text` | — | — | — | — | 재방문이 필요한 구체적 사유 |
| 11 | `technician_note` | 기사메모 | `text` | — | — | — | — | 후속 상담·운영 확인용 메모 |
| 12 | `submitted_by_id` | 제출자식별자 | `uuid` | — | Y | — | 물리 FK: accounts_user.id | 방문 결과를 제출한 기사 계정 · ON DELETE RESTRICT |
| 13 | `idempotency_key` | 멱등성키 | `varchar(128)` | — | Y | — | — | 방문 완료 결과 중복 생성을 막는 요청 키 · UNIQUE; API 전달 위치(Header/Body/Metadata)와 생성 주체는 팀 결정 필요 |
| 14 | `completed_at` | 결과확정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 기사가 방문 결과를 확정한 일시 |
| 15 | `next_care_on` | 다음케어예정일 | `date` | — | — | — | — | TECH-03에서 확정한 다음 케어 예정일; 구독 캐시 갱신 근거 |
| 16 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 17 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_visit_result` | BTREE | Y | id |
| 2 | `ux_visit_result_visit` | BTREE | Y | visit_id |
| 3 | `ix_visit_result_resolution` | BTREE | N | resolved_on_site, revisit_required, completed_at |
| 4 | `ux_visit_result_idempotency` | BTREE | Y | idempotency_key |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_visit_result_revisit_reason` | CHECK | revisit_required=false OR revisit_reason IS NOT NULL |
| 2 | `fk_visit_result_assigned_technician` | FOREIGN KEY | (visit_id, submitted_by_id) REFERENCES field_service_visit(id, technician_id) ON DELETE RESTRICT |
| 3 | `policy_visit_result_completion_transaction` | APPLICATION POLICY | Visit COMPLETED 전이·VisitResult INSERT·CareRecord 생성·상태 이력 INSERT를 하나의 Django transaction.atomic()으로 처리 |
| 4 | `ck_field_service_visit_result_cause_category_code_allowed` | CHECK | (cause_category_code IS NULL OR cause_category_code IN ('PRODUCT','INSTALLATION','WATER_SUPPLY','USER_ENVIRONMENT','UNKNOWN')) |

</details>

---

### 19. `support_followup_confirmation` — 후속 해결 확인

- 도메인: 고객 지원
- 목적: 상담 또는 방문 이후 고객의 최종 해결 여부, 미해결 사유와 다음 행동을 관리한다. [공통 설계 원칙] 고객 응답과 담당자 최종 확인을 분리하고 미해결 사유·응답 멱등성을 관리한다. [설계 상태: 상태·이벤트·제약은 팀 승인 전]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 후속 확인 대상 문의 · ON DELETE RESTRICT |
| 3 | `guidance_id` | 고객안내식별자 | `uuid` | — | — | — | 물리 FK: support_guidance.id | 자가조치 후속 확인 대상 안내 · ON DELETE RESTRICT; 대상 중 하나 |
| 4 | `consultation_id` | 상담식별자 | `uuid` | — | — | — | 물리 FK: support_consultation.id | 상담 후속 확인 대상 · ON DELETE RESTRICT; 대상 중 하나 |
| 5 | `visit_id` | 방문식별자 | `uuid` | — | — | — | 물리 FK: field_service_visit.id | 방문 후속 확인 대상 · ON DELETE RESTRICT; 대상 중 하나 |
| 6 | `channel_code` | 확인채널코드 | `varchar(40)` | — | Y | `'WEB'` | 논리 코드: common_code(group=FOLLOWUP_CHANNEL) | WEB, PHONE, SMS 등 후속 확인 채널 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `requested_at` | 확인요청일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 고객에게 해결 여부 확인을 요청한 일시 |
| 8 | `responded_at` | 응답일시 | `timestamptz` | — | — | — | — | 고객이 응답한 일시 |
| 9 | `resolution_status_code` | 해결상태코드 | `varchar(40)` | — | Y | `'PENDING'` | 논리 코드: common_code(group=RESOLUTION_STATUS) | PENDING, RESOLVED, UNRESOLVED, REOPENED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 10 | `state_version` | 상태버전 | `integer` | — | Y | `1` | — | 후속 확인 갱신의 낙관적 잠금 버전 · CHECK state_version > 0 |
| 11 | `customer_response` | 고객응답 | `text` | — | — | — | — | 고객이 입력하거나 상담사가 기록한 응답 |
| 12 | `response_recorded_by_id` | 응답기록자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 고객 직접 응답 또는 상담사 대리 기록 계정 · ON DELETE RESTRICT |
| 13 | `response_idempotency_key` | 응답멱등성키 | `varchar(128)` | — | — | — | — | 후속 응답 중복 기록을 방지하는 요청 키 · NULL 제외 UNIQUE |
| 14 | `unresolved_reason` | 미해결사유 | `text` | — | — | — | — | 미해결 또는 부분 해결의 사유 |
| 15 | `next_action` | 후속조치 | `text` | — | — | — | — | 재상담·재방문 등 다음 행동 |
| 16 | `confirmed_by_id` | 확인자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 후속 결과를 확인한 상담사·운영자 · ON DELETE RESTRICT |
| 17 | `confirmed_at` | 최종확인일시 | `timestamptz` | — | — | — | — | 담당자가 해결 여부를 최종 확인한 일시 |
| 18 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 후속 확인 레코드 생성 일시 |
| 19 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_followup_confirmation` | BTREE | Y | id |
| 2 | `ix_followup_inquiry` | BTREE | N | inquiry_id, requested_at DESC |
| 3 | `ix_followup_pending` | BTREE | N | requested_at / WHERE responded_at IS NULL |
| 4 | `ux_followup_response_idempotency` | BTREE | Y | response_idempotency_key / WHERE response_idempotency_key IS NOT NULL |
| 5 | `ix_followup_guidance` | BTREE | N | guidance_id, inquiry_id |
| 6 | `ix_followup_consultation` | BTREE | N | consultation_id, inquiry_id |
| 7 | `ix_followup_visit` | BTREE | N | visit_id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_followup_response` | CHECK | (resolution_status_code='PENDING' AND responded_at IS NULL) OR (resolution_status_code<>'PENDING' AND responded_at IS NOT NULL AND response_recorded_by_id IS NOT NULL) |
| 2 | `ck_followup_unresolved_reason` | CHECK | resolution_status_code NOT IN ('UNRESOLVED','REOPENED') OR unresolved_reason IS NOT NULL |
| 3 | `ck_followup_confirmation_pair` | CHECK | (confirmed_by_id IS NULL) = (confirmed_at IS NULL) |
| 4 | `ck_followup_exactly_one_source` | CHECK | num_nonnulls(guidance_id, consultation_id, visit_id)=1 |
| 5 | `ck_followup_state_version` | CHECK | state_version > 0 |
| 6 | `fk_followup_guidance_inquiry` | FOREIGN KEY | (guidance_id, inquiry_id) REFERENCES support_guidance(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 7 | `fk_followup_consultation_inquiry` | FOREIGN KEY | (consultation_id, inquiry_id) REFERENCES support_consultation(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 8 | `fk_followup_visit_inquiry` | FOREIGN KEY | (visit_id, inquiry_id) REFERENCES field_service_visit(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 9 | `ck_followup_resolved_confirmation` | CHECK | resolution_status_code<>'RESOLVED' OR (confirmed_by_id IS NOT NULL AND confirmed_at IS NOT NULL) |
| 10 | `ck_followup_confirmation_time` | CHECK | confirmed_at IS NULL OR (responded_at IS NOT NULL AND confirmed_at>=responded_at) |
| 11 | `policy_followup_source_terminal` | APPLICATION POLICY | 후속 확인 생성 시 안내 APPROVED, 상담 COMPLETED 또는 방문 COMPLETED 중 선택한 원본의 완료 상태를 검증 |
| 12 | `ck_support_followup_confirmation_channel_code_allowed` | CHECK | channel_code IN ('WEB','SMS','PHONE') |
| 13 | `ck_support_followup_confirmation_resolution_status_code_allowed` | CHECK | resolution_status_code IN ('PENDING','RESOLVED','UNRESOLVED','REOPENED') |

</details>

---

### 20. `support_inquiry_status_history` — 업무 상태 전이 이력

- 도메인: 고객 지원
- 목적: 사전 문진·문의·상담·방문의 이벤트 기반 상태 전이를 대상별 버전과 멱등키로 기록하는 append-only 원장이다. [설계 상태: 상태·이벤트·제약은 팀 승인 전]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `questionnaire_session_id` | 사전문진세션식별자 | `uuid` | — | — | — | 물리 FK: support_questionnaire_session.id | 사전 문진 상태 전이 대상인 경우의 세션 · ON DELETE RESTRICT |
| 3 | `inquiry_id` | 문의식별자 | `uuid` | — | — | — | 물리 FK: support_inquiry.id | 문의 상태 전이 대상인 경우의 문의 · ON DELETE RESTRICT |
| 4 | `consultation_id` | 상담식별자 | `uuid` | — | — | — | 물리 FK: support_consultation.id | 상담 상태 전이 대상인 경우의 상담 · ON DELETE RESTRICT |
| 5 | `visit_id` | 방문식별자 | `uuid` | — | — | — | 물리 FK: field_service_visit.id | 방문 상태 전이 대상인 경우의 방문 · ON DELETE RESTRICT |
| 6 | `target_type_code` | 대상유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=STATUS_TYPE) | QUESTIONNAIRE, INQUIRY, CONSULTATION, VISIT · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `event_code` | 전이이벤트코드 | `varchar(60)` | — | Y | — | 논리 코드: common_code(group=STATE_EVENT) | 상태 변경을 유발한 업무 이벤트 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 8 | `from_status_code` | 이전상태코드 | `varchar(40)` | — | — | — | — | 변경 전 상태 |
| 9 | `to_status_code` | 변경상태코드 | `varchar(40)` | — | Y | — | — | 변경 후 상태 |
| 10 | `state_version` | 전이후상태버전 | `integer` | — | Y | — | — | 전이 완료 후 대상 Aggregate의 상태 버전 · CHECK state_version > 0 |
| 11 | `change_reason` | 변경사유 | `text` | — | — | — | — | 상태 전환의 업무 사유 또는 예외 설명 |
| 12 | `changed_by_id` | 변경자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 전환을 수행한 사용자 · 시스템 전환이면 NULL; 사용자 계정은 ON DELETE RESTRICT |
| 13 | `changed_by_type_code` | 변경주체코드 | `varchar(40)` | — | Y | `'USER'` | 논리 코드: common_code(group=CHANGE_ORIGIN) | USER, SYSTEM · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 14 | `correlation_id` | 상관관계식별자 | `uuid` | — | Y | — | — | Django 요청·상태 전이·AI·로그를 연결하는 상관관계 ID |
| 15 | `idempotency_key` | 멱등성키 | `varchar(128)` | — | Y | — | — | 동일 상태 전이 요청을 한 번만 처리하기 위한 키 · UNIQUE; API 전달 위치(Header/Body/Metadata)와 생성 주체는 팀 결정 필요 |
| 16 | `changed_at` | 변경일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 상태 전환이 확정된 일시 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_inquiry_status_history` | BTREE | Y | id |
| 2 | `ux_status_hist_idempotency` | BTREE | Y | idempotency_key |
| 3 | `ux_status_hist_inquiry_version` | BTREE | Y | inquiry_id, state_version / WHERE target_type_code='INQUIRY' |
| 4 | `ux_status_hist_consultation_version` | BTREE | Y | consultation_id, state_version / WHERE target_type_code='CONSULTATION' |
| 5 | `ux_status_hist_visit_version` | BTREE | Y | visit_id, state_version / WHERE target_type_code='VISIT' |
| 6 | `ix_status_hist_target_event` | BTREE | N | target_type_code, event_code, changed_at DESC |
| 7 | `ix_status_hist_correlation` | BTREE | N | correlation_id |
| 8 | `ux_status_hist_questionnaire_version` | BTREE | Y | questionnaire_session_id, state_version / WHERE target_type_code='QUESTIONNAIRE' |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_status_history_exactly_one_target` | CHECK | num_nonnulls(questionnaire_session_id, inquiry_id, consultation_id, visit_id)=1 |
| 2 | `ck_status_history_target_type` | CHECK | (target_type_code='QUESTIONNAIRE' AND questionnaire_session_id IS NOT NULL) OR (target_type_code='INQUIRY' AND inquiry_id IS NOT NULL) OR (target_type_code='CONSULTATION' AND consultation_id IS NOT NULL) OR (target_type_code='VISIT' AND visit_id IS NOT NULL) |
| 3 | `ck_status_history_changed_by` | CHECK | (changed_by_type_code='USER' AND changed_by_id IS NOT NULL) OR (changed_by_type_code='SYSTEM' AND changed_by_id IS NULL) |
| 4 | `policy_status_history_append_only` | APPLICATION POLICY | INSERT 전용; UPDATE/DELETE 권한 미부여 및 정정은 새 상태 이력으로 추가 |
| 5 | `ck_status_history_version_positive` | CHECK | state_version > 0 |
| 6 | `ck_status_history_version_origin` | CHECK | (state_version=1 AND from_status_code IS NULL) OR (state_version>1 AND from_status_code IS NOT NULL) |
| 7 | `ck_status_history_status_values` | CHECK | (target_type_code='QUESTIONNAIRE' AND (from_status_code IS NULL OR from_status_code IN ('UNANSWERED','IN_PROGRESS','SUBMITTED')) AND to_status_code IN ('UNANSWERED','IN_PROGRESS','SUBMITTED')) OR (target_type_code='INQUIRY' AND (from_status_code IS NULL OR from_status_code IN ('DRAFT','QUESTIONNAIRE_IN_PROGRESS','PRODUCT_VALIDATION_FAILED','AI_GUIDANCE_READY','CONSULTATION_PENDING','CONSULTATION_IN_PROGRESS','VISIT_REVIEW_PENDING','VISIT_PENDING','VISIT_IN_PROGRESS','COMPLETION_PENDING','RESOLVED','REOPENED')) AND to_status_code IN ('DRAFT','QUESTIONNAIRE_IN_PROGRESS','PRODUCT_VALIDATION_FAILED','AI_GUIDANCE_READY','CONSULTATION_PENDING','CONSULTATION_IN_PROGRESS','VISIT_REVIEW_PENDING','VISIT_PENDING','VISIT_IN_PROGRESS','COMPLETION_PENDING','RESOLVED','REOPENED')) OR (target_type_code='CONSULTATION' AND (from_status_code IS NULL OR from_status_code IN ('WAITING','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED')) AND to_status_code IN ('WAITING','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED')) OR (target_type_code='VISIT' AND (from_status_code IS NULL OR from_status_code IN ('ASSIGNING','SCHEDULING','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED')) AND to_status_code IN ('ASSIGNING','SCHEDULING','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED')) |
| 8 | `policy_status_history_transition_graph` | APPLICATION POLICY | Django State Machine 단일 전이표로 target·event·from·to·actor·이전 version 연속성을 검증하고 Aggregate 변경과 같은 transaction에 저장 |
| 9 | `ck_support_inquiry_status_history_target_type_code_allowed` | CHECK | target_type_code IN ('QUESTIONNAIRE','INQUIRY','CONSULTATION','VISIT') |
| 10 | `ck_support_inquiry_status_history_event_code_allowed` | CHECK | event_code IN ('START_CARE_PRECHECK','SAVE_CARE_PRECHECK','SUBMIT_CARE_PRECHECK','LINK_INQUIRY','START_INQUIRY','SUBMIT_SYMPTOM','PRODUCT_VALIDATION_FAILED','SAFE_GUIDANCE_READY','DANGER_DETECTED','NO_EVIDENCE','REQUEST_CONSULTATION','ASSIGN_CONSULTATION','START_CONSULTATION','CONSULTATION_COMPLETED','VISIT_NEEDED','ASSIGN_TECHNICIAN','UPDATE_VISIT_SCHEDULE','CONFIRM_VISIT','START_VISIT','VISIT_COMPLETED','SUBMIT_RESOLUTION_FEEDBACK','RESUME_CONSULTATION','FINALIZE_INQUIRY','CANCEL') |
| 11 | `ck_support_inquiry_status_history_changed_by_type_code_allowed` | CHECK | changed_by_type_code IN ('USER','SYSTEM') |

</details>

---

### 21. `knowledge_ingestion_batch` — 지식 수집 배치

- 도메인: 지식·근거
- 목적: 공식 문서 수집·파싱·검수·적재 실행 단위를 건수와 결과 상태로 관리한다. [공통 설계 원칙] 수집 실행의 범위·멱등성·상관관계·건수·오류를 보존하며 실행 상태만 갱신한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `batch_no` | 배치번호 | `varchar(50)` | — | Y | — | — | 수집 보고서와 로그에서 사용하는 배치번호 · UNIQUE |
| 3 | `dataset_scope_code` | 데이터범위코드 | `varchar(30)` | — | Y | `'MVP'` | 논리 코드: common_code(group=DATASET_SCOPE) | MVP 또는 EXPANSION 데이터 범위 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 4 | `source_type_code` | 소스유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=INGESTION_SOURCE_TYPE) | LOCAL_FILE, HTTP_DOWNLOAD, WEB_PAGE, MANUAL_UPLOAD · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `status_code` | 배치상태코드 | `varchar(40)` | — | Y | `'QUEUED'` | 논리 코드: common_code(group=INGESTION_STATUS) | QUEUED, RUNNING, SUCCEEDED, PARTIAL, FAILED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 6 | `idempotency_key` | 멱등성키 | `varchar(128)` | — | Y | — | — | 동일 수집 배치의 중복 실행을 방지하는 키 · UNIQUE |
| 7 | `correlation_id` | 상관관계식별자 | `uuid` | — | Y | — | — | 수집·파싱·검수·적재 로그 연결 ID |
| 8 | `started_by_id` | 실행자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 수집·적재를 실행한 담당자 · ON DELETE RESTRICT |
| 9 | `started_at` | 시작일시 | `timestamptz` | — | — | — | — | 수집 배치 시작 일시 |
| 10 | `completed_at` | 완료일시 | `timestamptz` | — | — | — | — | 수집 배치 완료 일시 |
| 11 | `total_count` | 전체건수 | `integer` | — | Y | `0` | — | 처리 대상 문서 수 · CHECK total_count >= 0 |
| 12 | `success_count` | 성공건수 | `integer` | — | Y | `0` | — | 검증 가능한 상태로 처리된 문서 수 · CHECK success_count >= 0 |
| 13 | `failure_count` | 실패건수 | `integer` | — | Y | `0` | — | 파싱·검증 실패 문서 수 · CHECK failure_count >= 0 |
| 14 | `pipeline_version` | 파이프라인버전 | `varchar(50)` | — | Y | — | — | 수집·정제 스크립트 버전 또는 커밋 |
| 15 | `log_uri` | 로그경로 | `varchar(500)` | — | — | — | — | 상세 실행 로그 파일 또는 객체 경로 |
| 16 | `error_summary` | 오류요약 | `text` | — | — | — | — | 실패·부분 성공 시 민감정보를 제거한 오류 요약 |
| 17 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 배치 등록 일시 |
| 18 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_ingestion_batch` | BTREE | Y | id |
| 2 | `ux_ingestion_batch_no` | BTREE | Y | batch_no |
| 3 | `ix_ingestion_batch_status` | BTREE | N | status_code, created_at DESC |
| 4 | `ux_ingestion_batch_idempotency` | BTREE | Y | idempotency_key |
| 5 | `ix_ingestion_batch_correlation` | BTREE | N | correlation_id |
| 6 | `ux_ingestion_batch_id_scope` | BTREE | Y | id, dataset_scope_code |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_ingestion_counts` | CHECK | total_count>=0 AND success_count>=0 AND failure_count>=0 AND success_count+failure_count<=total_count |
| 2 | `ck_ingestion_time_order` | CHECK | completed_at IS NULL OR (started_at IS NOT NULL AND completed_at>=started_at) |
| 3 | `ck_ingestion_terminal` | CHECK | (status_code='QUEUED' AND started_at IS NULL AND completed_at IS NULL) OR (status_code='RUNNING' AND started_at IS NOT NULL AND completed_at IS NULL) OR (status_code='SUCCEEDED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND success_count=total_count AND failure_count=0) OR (status_code='PARTIAL' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND success_count>0 AND failure_count>0 AND success_count+failure_count=total_count) OR (status_code='FAILED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND success_count=0 AND failure_count=total_count) |
| 4 | `ck_ingestion_error_summary` | CHECK | status_code NOT IN ('PARTIAL','FAILED') OR error_summary IS NOT NULL |
| 5 | `ck_knowledge_ingestion_batch_dataset_scope_code_allowed` | CHECK | dataset_scope_code IN ('MVP','EXPANSION') |
| 6 | `ck_knowledge_ingestion_batch_source_type_code_allowed` | CHECK | source_type_code IN ('LOCAL_FILE','HTTP_DOWNLOAD','WEB_PAGE','MANUAL_UPLOAD') |
| 7 | `ck_knowledge_ingestion_batch_status_code_allowed` | CHECK | status_code IN ('QUEUED','RUNNING','SUCCEEDED','PARTIAL','FAILED') |

</details>

---

### 22. `knowledge_source_document` — 공식 원본 문서

- 도메인: 지식·근거
- 목적: 공식 매뉴얼·FAQ의 출처, 리비전, 수집일, 파일 해시, 파싱·검증 상태를 관리한다. [공통 설계 원칙] 공식 원문 리비전·출처·이용조건·해시·MVP 범위를 관리하고 파일은 내부 저장소 키로 참조한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `ingestion_batch_id` | 수집배치식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_ingestion_batch.id | 문서가 최초 등록된 수집 배치 · ON DELETE RESTRICT |
| 3 | `document_code` | 문서코드 | `varchar(80)` | — | Y | — | — | 내부에서 사용하는 안정 문서 식별 코드 · UNIQUE |
| 4 | `dataset_scope_code` | 데이터범위코드 | `varchar(30)` | — | Y | `'MVP'` | 논리 코드: common_code(group=DATASET_SCOPE) | MVP 또는 EXPANSION 원문 범위 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `supersedes_document_id` | 이전문서식별자 | `uuid` | — | — | — | 물리 FK: knowledge_source_document.id | 현재 리비전이 대체하는 이전 문서 레코드 · ON DELETE RESTRICT |
| 6 | `title` | 문서명 | `varchar(300)` | — | Y | — | — | 공식 문서 제목 |
| 7 | `source_org` | 출처기관 | `varchar(150)` | — | Y | — | — | 문서를 발행한 공식 기관 또는 브랜드 |
| 8 | `document_type_code` | 문서유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=DOCUMENT_TYPE) | MANUAL, FAQ, PRODUCT_DATA · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 9 | `official_source_url` | 공식출처URL | `varchar(1000)` | — | Y | — | — | 공식 원본을 확인할 수 있는 URL |
| 10 | `usage_terms_url` | 이용조건URL | `varchar(1000)` | — | Y | — | — | 수집 허용 범위·이용조건을 확인할 공식 URL |
| 11 | `license_note` | 라이선스메모 | `text` | — | Y | — | — | 저작권·사용 범위·재배포 제한 검토 결과 |
| 12 | `original_file_uri` | 원본파일경로 | `varchar(1000)` | — | Y | — | — | 로컬 절대경로나 만료 URL이 아닌 내부 저장소 객체 키 · dataset_scope별 prefix가 포함된 내부 저장소 객체 키 |
| 13 | `file_name` | 파일명 | `varchar(300)` | — | — | — | — | 수집한 원본 파일명 |
| 14 | `mime_type` | MIME유형 | `varchar(100)` | — | — | — | — | application/pdf, text/html 등 |
| 15 | `file_size_bytes` | 파일크기바이트 | `bigint` | — | — | — | — | 원본 파일 크기 · CHECK file_size_bytes >= 0 |
| 16 | `sha256_hash` | SHA256해시 | `varchar(64)` | — | Y | — | — | 중복·변경 검출용 원본 SHA-256 · UNIQUE |
| 17 | `revision_label` | 리비전표기 | `varchar(100)` | — | — | — | — | 문서 버전·개정번호·발행판 |
| 18 | `published_on` | 발행일 | `date` | — | — | — | — | 공식 문서 발행 또는 개정일 |
| 19 | `collected_at` | 수집일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 원본을 수집한 일시 |
| 20 | `collected_by_id` | 수집자식별자 | `uuid` | — | Y | — | 물리 FK: accounts_user.id | 원문을 수집·등록한 담당자 · ON DELETE RESTRICT |
| 21 | `status_code` | 문서상태코드 | `varchar(40)` | — | Y | `'COLLECTED'` | 논리 코드: common_code(group=DOCUMENT_STATUS) | COLLECTED, PARSED, REVIEWED, APPROVED, EXCLUDED, FAILED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 22 | `parser_version` | 파서버전 | `varchar(50)` | — | — | — | — | 텍스트 추출 스크립트 버전 |
| 23 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 24 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |
| 25 | `deleted_at` | 삭제일시 | `timestamptz` | — | — | — | — | 일반 검색·관리 화면에서 제외한 논리 삭제 시각 · 물리 원문·근거 이력 삭제 금지 |
| 26 | `deleted_by_id` | 삭제처리자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 논리 삭제를 수행한 사용자 · ON DELETE RESTRICT |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_source_document` | BTREE | Y | id |
| 2 | `ux_source_document_code` | BTREE | Y | document_code |
| 3 | `ux_source_document_sha256` | BTREE | Y | sha256_hash |
| 4 | `ix_source_document_status` | BTREE | N | document_type_code, status_code, collected_at DESC |
| 5 | `ix_source_document_revision` | BTREE | N | official_source_url, revision_label |
| 6 | `ix_source_document_supersedes` | BTREE | N | supersedes_document_id |
| 7 | `ix_source_document_active_status` | BTREE | N | status_code, collected_at DESC / WHERE deleted_at IS NULL |
| 8 | `ix_source_document_batch` | BTREE | N | ingestion_batch_id |
| 9 | `ux_source_document_id_scope` | BTREE | Y | id, dataset_scope_code |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_source_document_sha256` | CHECK | sha256_hash ~ '^[0-9a-f]{64}$' |
| 2 | `policy_source_document_storage` | APPLICATION POLICY | DB에는 scope별 객체 키·해시·메타데이터만 저장하고 원문 bytes·만료 URL은 저장하지 않음 |
| 3 | `fk_source_document_batch_scope` | FOREIGN KEY | (ingestion_batch_id, dataset_scope_code) REFERENCES knowledge_ingestion_batch(id, dataset_scope_code) ON DELETE RESTRICT |
| 4 | `fk_source_document_supersedes_scope` | FOREIGN KEY | (supersedes_document_id, dataset_scope_code) REFERENCES knowledge_source_document(id, dataset_scope_code) MATCH SIMPLE ON DELETE RESTRICT |
| 5 | `ck_source_document_not_self_supersede` | CHECK | supersedes_document_id IS NULL OR supersedes_document_id<>id |
| 6 | `ck_source_document_deleted_pair` | CHECK | (deleted_at IS NULL) = (deleted_by_id IS NULL) |
| 7 | `ck_knowledge_source_document_dataset_scope_code_allowed` | CHECK | dataset_scope_code IN ('MVP','EXPANSION') |
| 8 | `ck_knowledge_source_document_document_type_code_allowed` | CHECK | document_type_code IN ('MANUAL','FAQ','PRODUCT_DATA','SAFETY_NOTICE') |
| 9 | `ck_knowledge_source_document_status_code_allowed` | CHECK | status_code IN ('COLLECTED','PARSED','REVIEWED','APPROVED','EXCLUDED','FAILED') |

</details>

---

### 23. `knowledge_document_model_scope` — 문서 적용 제품 범위

- 도메인: 지식·근거
- 목적: 공식 문서가 적용되는 제품 모델·세대와 적용 기간을 사람이 검증한 관계로 관리한다. [공통 설계 원칙] 문서와 제품 모델의 적용 기간·검증 여부를 명시하고 검증 전 검색 필터에 사용하지 않는다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `document_id` | 문서식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_source_document.id | 적용 범위를 정의할 공식 문서 · ON DELETE RESTRICT |
| 3 | `product_model_id` | 제품모델식별자 | `uuid` | — | Y | — | 물리 FK: catalog_product_model.id | 문서가 적용되는 제품 모델 · ON DELETE RESTRICT |
| 4 | `applicable_from` | 적용시작일 | `date` | — | — | — | — | 문서 적용 시작일 |
| 5 | `applicable_to` | 적용종료일 | `date` | — | — | — | — | 문서 적용 종료일 · CHECK applicable_to >= applicable_from |
| 6 | `applicability_note` | 적용범위설명 | `text` | — | — | — | — | 세대·옵션·리비전 등 추가 적용 조건 |
| 7 | `is_verified` | 검증여부 | `boolean` | — | Y | `false` | — | 제품 모델과 문서 리비전의 적용 관계를 사람이 확인했는지 여부 |
| 8 | `verified_by_id` | 검증자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 제품·문서 일치를 확인한 담당자 · ON DELETE RESTRICT |
| 9 | `verified_at` | 검증일시 | `timestamptz` | — | — | — | — | 적용 범위를 검증한 일시 |
| 10 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 적용 범위 등록 일시 |
| 11 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_document_model_scope` | BTREE | Y | id |
| 2 | `ux_document_model_scope` | BTREE | Y | document_id, product_model_id |
| 3 | `ix_model_scope_model` | BTREE | N | product_model_id, is_verified, applicable_from, applicable_to |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_model_scope_period` | CHECK | applicable_to IS NULL OR applicable_from IS NULL OR applicable_to>=applicable_from |
| 2 | `ck_model_scope_verification` | CHECK | (is_verified=true AND verified_by_id IS NOT NULL AND verified_at IS NOT NULL) OR (is_verified=false AND verified_by_id IS NULL AND verified_at IS NULL) |

</details>

---

### 24. `knowledge_document_page` — 문서 페이지

- 도메인: 지식·근거
- 목적: 공식 문서의 페이지별 추출 텍스트, 해시, 파싱·검수·RAG 사용 가능 상태를 관리한다. [공통 설계 원칙] 페이지 파싱·검수·RAG 승인 상태와 제외 사유를 함께 관리한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `document_id` | 문서식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_source_document.id | 페이지가 속한 공식 문서 · ON DELETE RESTRICT |
| 3 | `page_no` | 페이지번호 | `integer` | — | Y | — | — | 원본 문서의 1부터 시작하는 페이지 · CHECK page_no > 0 |
| 4 | `extracted_text` | 추출텍스트 | `text` | — | — | — | — | 페이지에서 추출한 정규화 텍스트 |
| 5 | `text_sha256` | 텍스트해시 | `varchar(64)` | — | — | — | — | 페이지 텍스트 변경 검출용 SHA-256 |
| 6 | `parse_status_code` | 파싱상태코드 | `varchar(40)` | — | Y | `'PENDING'` | 논리 코드: common_code(group=PARSE_STATUS) | PENDING, PARSED, OCR_REQUIRED, FAILED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `review_status_code` | 검수상태코드 | `varchar(40)` | — | Y | `'PENDING'` | 논리 코드: common_code(group=REVIEW_STATUS) | PENDING, APPROVED, REJECTED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 8 | `is_rag_eligible` | RAG사용가능여부 | `boolean` | — | Y | `false` | — | 검수 완료 후 검색 인덱스에 포함할지 여부 |
| 9 | `exclusion_reason` | 검색제외사유 | `text` | — | — | — | — | RAG 검색에서 제외된 구체적 품질·적용성 사유 |
| 10 | `reviewer_id` | 검수자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 페이지를 검수한 담당자 · ON DELETE RESTRICT |
| 11 | `reviewed_at` | 검수일시 | `timestamptz` | — | — | — | — | 페이지 검수 완료 일시 |
| 12 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 페이지 레코드 생성 일시 |
| 13 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_document_page` | BTREE | Y | id |
| 2 | `ux_document_page_no` | BTREE | Y | document_id, page_no |
| 3 | `ix_document_page_rag` | BTREE | N | document_id, page_no / WHERE is_rag_eligible=true |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_document_page_no` | CHECK | page_no > 0 |
| 2 | `ck_document_page_sha256` | CHECK | text_sha256 IS NULL OR text_sha256 ~ '^[0-9a-f]{64}$' |
| 3 | `ck_document_page_rag_eligibility` | CHECK | is_rag_eligible=false OR (parse_status_code='PARSED' AND review_status_code='APPROVED' AND extracted_text IS NOT NULL AND text_sha256 IS NOT NULL) |
| 4 | `ck_document_page_review_fields` | CHECK | (review_status_code='PENDING' AND reviewer_id IS NULL AND reviewed_at IS NULL) OR (review_status_code IN ('REVIEWED','APPROVED','REJECTED') AND reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL) |
| 5 | `policy_rag_eligible_parent_scope` | APPLICATION POLICY | RAG QuerySet은 부모 문서 APPROVED·deleted_at NULL·dataset_scope 일치·유효기간·검증된 document_model_scope를 모두 적용 |
| 6 | `ck_knowledge_document_page_parse_status_code_allowed` | CHECK | parse_status_code IN ('PENDING','PARSED','OCR_REQUIRED','FAILED') |
| 7 | `ck_knowledge_document_page_review_status_code_allowed` | CHECK | review_status_code IN ('PENDING','REVIEWED','APPROVED','REJECTED') |

</details>

---

### 25. `knowledge_document_chunk` — 문서 검색 청크

- 도메인: 지식·근거
- 목적: 검수된 페이지를 검색 단위로 분할하고 증상 태그·메타데이터·청킹 버전을 관리한다. [공통 설계 원칙] 청크 유형·섹션·해시·토크나이저·버전을 기록하고 승인된 본문은 새 버전으로만 교체한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `page_id` | 문서페이지식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_document_page.id | 청크가 속한 문서 페이지 · ON DELETE RESTRICT |
| 3 | `chunk_no` | 청크순번 | `integer` | — | Y | — | — | 페이지 안의 청크 순서 · CHECK chunk_no > 0 |
| 4 | `chunk_type_code` | 청크유형코드 | `varchar(40)` | — | Y | `'PARAGRAPH'` | 논리 코드: common_code(group=CHUNK_TYPE) | HEADING, PARAGRAPH, PROCEDURE, FAQ, TABLE · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 5 | `section_path` | 섹션경로 | `varchar(500)` | — | — | — | — | 제목·절·문단 계층을 복원할 수 있는 경로 |
| 6 | `chunk_text` | 청크텍스트 | `text` | — | Y | — | — | 검색·인용에 사용하는 원문 구간 |
| 7 | `chunk_text_sha256` | 청크텍스트해시 | `varchar(64)` | — | Y | — | — | 청크 본문 변경 검출용 SHA-256 |
| 8 | `start_offset` | 시작오프셋 | `integer` | — | — | — | — | 페이지 텍스트 안의 시작 문자 위치 · CHECK start_offset >= 0 |
| 9 | `end_offset` | 종료오프셋 | `integer` | — | — | — | — | 페이지 텍스트 안의 종료 문자 위치 · CHECK end_offset >= start_offset |
| 10 | `token_count` | 토큰수 | `integer` | — | — | — | — | 사용한 토크나이저 기준 토큰 수 · CHECK token_count >= 0 |
| 11 | `tokenizer_name` | 토크나이저명 | `varchar(120)` | — | — | — | — | 토큰 수 계산에 사용한 토크나이저 |
| 12 | `tokenizer_version` | 토크나이저버전 | `varchar(50)` | — | — | — | — | 토크나이저 또는 전처리 규칙 버전 |
| 13 | `symptom_tags` | 증상태그 | `jsonb` | — | Y | `'[]'::jsonb` | — | 누수·소음·온도 등 검색 보조 태그 배열 |
| 14 | `metadata` | 검색메타데이터 | `jsonb` | — | Y | `'{}'::jsonb` | — | 섹션명, 표제, 언어 등 검색 필터 속성 |
| 15 | `search_vector` | 키워드검색벡터 | `tsvector` | — | — | — | — | PostgreSQL Full Text Search용 파생 벡터 · GENERATED ALWAYS AS (to_tsvector('simple', coalesce(chunk_text,''))) STORED |
| 16 | `chunking_version` | 청킹버전 | `varchar(50)` | — | Y | — | — | 청킹 규칙·스크립트 버전 |
| 17 | `is_active` | 활성여부 | `boolean` | — | Y | `true` | — | 현재 검색 인덱스에서 사용할지 여부 |
| 18 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 청크 생성 일시 |
| 19 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_document_chunk` | BTREE | Y | id |
| 2 | `ux_document_chunk_version` | BTREE | Y | page_id, chunk_no, chunking_version |
| 3 | `ix_document_chunk_active` | BTREE | N | page_id, is_active |
| 4 | `ix_document_chunk_fts` | GIN | N | search_vector |
| 5 | `ux_document_chunk_id_hash` | BTREE | Y | id, chunk_text_sha256 |
| 6 | `ux_document_chunk_active_position` | BTREE | Y | page_id, chunk_no / WHERE is_active=true |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_document_chunk_text` | CHECK | length(btrim(chunk_text)) > 0 |
| 2 | `ck_document_chunk_hash` | CHECK | chunk_text_sha256 ~ '^[0-9a-f]{64}$' |
| 3 | `ck_document_chunk_offsets` | CHECK | (start_offset IS NULL AND end_offset IS NULL) OR (start_offset>=0 AND end_offset>start_offset) |
| 4 | `ck_document_chunk_json` | CHECK | jsonb_typeof(symptom_tags)='array' AND jsonb_typeof(metadata)='object' |
| 5 | `policy_document_chunk_active_version` | APPLICATION POLICY | 페이지별 활성 청크는 하나의 chunking_version만 사용하도록 기존 세트 비활성화와 새 세트 활성화를 같은 transaction으로 처리 |
| 6 | `ck_knowledge_document_chunk_chunk_type_code_allowed` | CHECK | chunk_type_code IN ('HEADING','PARAGRAPH','PROCEDURE','FAQ','TABLE') |

</details>

---

### 26. `knowledge_chunk_embedding` — 청크 임베딩

- 도메인: 지식·근거
- 목적: pgvector로 생성한 청크 임베딩을 모델·차원별로 버전 관리한다. 차원은 모델 확정 후 마이그레이션에서 고정한다. [공통 설계 원칙] 모델 차원을 임의 고정하지 않고 차원 없는 vector와 차원 검증을 사용하며 ANN 인덱스는 모델 확정 후 생성한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `chunk_id` | 문서청크식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_document_chunk.id | 임베딩 대상 검색 청크 · ON DELETE RESTRICT |
| 3 | `embedding_model` | 임베딩모델 | `varchar(120)` | — | Y | — | — | 임베딩 공급자와 모델 식별자 |
| 4 | `embedding_model_version` | 임베딩모델버전 | `varchar(80)` | — | Y | — | — | 공급자 모델의 고정 버전 또는 배포 식별자 |
| 5 | `embedding_dimension` | 임베딩차원 | `integer` | — | Y | — | — | 벡터 차원 수 · 팀 결정 필요: BAAI/bge-m3 채택 시 1024; 승인 전 vector(n) 고정 금지 |
| 6 | `source_text_sha256` | 원천텍스트해시 | `varchar(64)` | — | Y | — | — | 임베딩 생성에 사용한 chunk_text_sha256 |
| 7 | `embedding` | 임베딩벡터 | `vector` | — | Y | — | — | pgvector 벡터 값 · dimensionless vector 유지; MVP Exact Search. 승인 후 vector(1024) Migration, HNSW/IVFFlat 제외 |
| 8 | `embedded_at` | 임베딩생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 임베딩을 생성한 일시 |
| 9 | `is_active` | 활성여부 | `boolean` | — | Y | `true` | — | 현재 검색에서 사용할 임베딩인지 여부 |
| 10 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 임베딩 레코드 생성 일시 |
| 11 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_chunk_embedding` | BTREE | Y | id |
| 2 | `ux_chunk_embedding_model` | BTREE | Y | chunk_id, embedding_model, embedding_model_version |
| 3 | `ix_chunk_embedding_active` | BTREE | N | embedding_model, is_active |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_chunk_embedding_dimension` | CHECK | embedding_dimension>0 AND vector_dims(embedding)=embedding_dimension |
| 2 | `ck_chunk_embedding_source_hash` | CHECK | source_text_sha256 ~ '^[0-9a-f]{64}$' |
| 3 | `policy_chunk_embedding_ann_index` | APPLICATION POLICY | 팀 결정 필요: 모델·차원 승인 전 ANN 인덱스 생성 금지; MVP는 Exact Search |
| 4 | `fk_chunk_embedding_source_hash` | FOREIGN KEY | (chunk_id, source_text_sha256) REFERENCES knowledge_document_chunk(id, chunk_text_sha256) ON DELETE RESTRICT |

</details>

---

### 27. `knowledge_data_quality_issue` — 지식 데이터 품질 이슈

- 도메인: 지식·근거
- 목적: 파싱 실패, 모델 불일치, 출처·페이지 오류, 필수 메타데이터 누락을 추적하고 RAG 제외 근거로 사용한다. [공통 설계 원칙] 배치·문서·페이지 중 하나 이상의 대상과 검증 규칙 버전을 남기고 해결 상태를 추적한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `ingestion_batch_id` | 수집배치식별자 | `uuid` | — | — | — | 물리 FK: knowledge_ingestion_batch.id | 이슈가 발견된 수집 배치 · ON DELETE RESTRICT |
| 3 | `document_id` | 문서식별자 | `uuid` | — | — | — | 물리 FK: knowledge_source_document.id | 이슈가 속한 공식 문서 · ON DELETE RESTRICT |
| 4 | `page_id` | 문서페이지식별자 | `uuid` | — | — | — | 물리 FK: knowledge_document_page.id | 페이지 단위 이슈인 경우의 대상 · ON DELETE RESTRICT |
| 5 | `chunk_id` | 청크식별자 | `uuid` | — | — | — | 물리 FK: knowledge_document_chunk.id | 청크 단위 품질 이슈인 경우의 대상 · ON DELETE RESTRICT |
| 6 | `issue_type_code` | 이슈유형코드 | `varchar(40)` | — | Y | — | 논리 코드: common_code(group=QUALITY_ISSUE_TYPE) | MISSING_METADATA, HASH_MISMATCH, PARSE_FAILURE, MODEL_SCOPE_MISMATCH, SOURCE_NOT_OFFICIAL, PAGE_REFERENCE_INVALID · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 7 | `validation_rule_code` | 검증규칙코드 | `varchar(80)` | — | — | — | — | 실패한 수집·파싱·검수 규칙 식별자 |
| 8 | `validator_version` | 검증기버전 | `varchar(50)` | — | — | — | — | 검증 스크립트 또는 규칙 세트 버전 |
| 9 | `severity_code` | 심각도코드 | `varchar(40)` | — | Y | `'ERROR'` | 논리 코드: common_code(group=SEVERITY) | INFO, WARNING, ERROR, CRITICAL · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 10 | `issue_message` | 이슈내용 | `text` | — | Y | — | — | 담당자가 이해할 수 있는 오류 설명 |
| 11 | `details` | 상세정보 | `jsonb` | — | Y | `'{}'::jsonb` | — | 검증 규칙, 원본 값, 스택 정보 등 상세 |
| 12 | `status_code` | 처리상태코드 | `varchar(40)` | — | Y | `'OPEN'` | 논리 코드: common_code(group=ISSUE_STATUS) | OPEN, IN_REVIEW, RESOLVED, WAIVED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 13 | `detected_at` | 발견일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 이슈가 발견된 일시 |
| 14 | `resolved_by_id` | 해결자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 이슈 해결을 확인한 담당자 · ON DELETE RESTRICT |
| 15 | `resolved_at` | 해결일시 | `timestamptz` | — | — | — | — | 이슈 처리가 완료된 일시 |
| 16 | `resolution_note` | 해결내용 | `text` | — | — | — | — | 수정·제외·보류 등 처리 결과 |
| 17 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 이슈 레코드 생성 일시 |
| 18 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_data_quality_issue` | BTREE | Y | id |
| 2 | `ix_quality_issue_open` | BTREE | N | severity_code, detected_at / WHERE status_code IN ('OPEN','IN_REVIEW') |
| 3 | `ix_quality_issue_document` | BTREE | N | document_id, page_id |
| 4 | `ix_quality_issue_page` | BTREE | N | page_id |
| 5 | `ix_quality_issue_chunk` | BTREE | N | chunk_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_quality_issue_target` | CHECK | num_nonnulls(document_id, page_id, chunk_id)=1 |
| 2 | `ck_quality_issue_resolution` | CHECK | (status_code IN ('RESOLVED','WAIVED') AND resolved_by_id IS NOT NULL AND resolved_at IS NOT NULL AND resolution_note IS NOT NULL) OR (status_code NOT IN ('RESOLVED','WAIVED') AND resolved_by_id IS NULL AND resolved_at IS NULL AND resolution_note IS NULL) |
| 3 | `ck_quality_issue_details_object` | CHECK | jsonb_typeof(details)='object' |
| 4 | `ck_knowledge_data_quality_issue_issue_type_code_allowed` | CHECK | issue_type_code IN ('MISSING_METADATA','HASH_MISMATCH','PARSE_FAILURE','MODEL_SCOPE_MISMATCH','SOURCE_NOT_OFFICIAL','PAGE_REFERENCE_INVALID') |
| 5 | `ck_knowledge_data_quality_issue_severity_code_allowed` | CHECK | severity_code IN ('INFO','WARNING','ERROR','CRITICAL') |
| 6 | `ck_knowledge_data_quality_issue_status_code_allowed` | CHECK | status_code IN ('OPEN','IN_REVIEW','RESOLVED','WAIVED') |

</details>

---

### 28. `aiops_ai_run` — AI 실행 이력

- 도메인: AI 운영
- 목적: 증상 구조화·판정·안내·요약·리포트 생성의 모델, 프롬프트, 입출력, 지연, 오류를 실행별로 기록한다. [공통 설계 원칙] 원시 출력과 검증된 출력, 요청·응답 스키마, 프롬프트·모델·검증 오류·멱등성·상관관계를 실행별로 저장한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | AI 실행이 속한 문의 · ON DELETE RESTRICT |
| 3 | `task_type_code` | AI작업유형코드 | `varchar(50)` | — | Y | — | 논리 코드: common_code(group=AI_TASK_TYPE) | 구조화, 판정, 안내, 상담요약, 기사리포트 등 · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 4 | `request_schema_version` | 요청계약버전 | `varchar(30)` | — | Y | `'v1'` | — | Django-FastAPI Pydantic DTO 버전 |
| 5 | `response_schema_version` | 응답스키마버전 | `varchar(30)` | — | Y | — | — | 검증된 출력 DTO의 스키마 버전 |
| 6 | `model_provider` | 모델공급자 | `varchar(80)` | — | — | — | — | LLM 또는 규칙 엔진 공급자 |
| 7 | `model_name` | 모델명 | `varchar(120)` | — | — | — | — | 실행에 사용한 정확한 모델 식별자 |
| 8 | `model_config_version` | 모델설정버전 | `varchar(64)` | — | Y | `'v1'` | — | temperature·출력 제한 등 모델 설정 버전 |
| 9 | `model_config` | 모델설정 | `jsonb` | — | Y | `'{}'::jsonb` | — | 실행 당시 비민감 모델 설정 스냅샷 |
| 10 | `prompt_version` | 프롬프트버전 | `varchar(50)` | — | — | — | — | 프롬프트 템플릿 또는 규칙 버전 |
| 11 | `input_payload` | 입력데이터 | `jsonb` | — | Y | `'{}'::jsonb` | — | AI 입력 DTO의 마스킹·최소화 스냅샷 · 실제 개인정보·비밀값 저장 금지 |
| 12 | `input_sha256` | 입력해시 | `varchar(64)` | — | Y | — | — | 정규화·마스킹 입력 payload의 SHA-256 · 원문 개인정보·비밀값 제외 |
| 13 | `idempotency_key` | 멱등성키 | `varchar(128)` | — | Y | — | — | 동일 AI 작업의 중복 실행을 방지하는 요청 키 · UNIQUE |
| 14 | `raw_output_text` | 원시출력텍스트 | `text` | — | — | — | — | 민감정보를 최소화하여 보존한 모델 원시 응답 |
| 15 | `validated_output_payload` | 출력데이터 | `jsonb` | — | — | — | — | Pydantic 스키마 검증을 통과한 구조화 출력 |
| 16 | `schema_validation_status_code` | 스키마검증상태코드 | `varchar(40)` | — | Y | `'NOT_RUN'` | 논리 코드: common_code(group=AI_SCHEMA_VALIDATION_STATUS) | NOT_RUN, PASSED, FAILED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 17 | `schema_validation_errors` | 스키마검증오류 | `jsonb` | — | Y | `'[]'::jsonb` | — | Pydantic 검증 실패 경로·코드·메시지 배열 |
| 18 | `status_code` | 실행상태코드 | `varchar(40)` | — | Y | `'QUEUED'` | 논리 코드: common_code(group=AI_RUN_STATUS) | QUEUED, RUNNING, SUCCEEDED, NO_EVIDENCE, FAILED, TIMED_OUT, RETRYING, CANCELLED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 19 | `started_at` | 시작일시 | `timestamptz` | — | — | — | — | AI 처리 시작 일시 |
| 20 | `completed_at` | 완료일시 | `timestamptz` | — | — | — | — | AI 처리 완료 일시 |
| 21 | `latency_ms` | 처리지연밀리초 | `integer` | — | — | — | — | 시작부터 완료까지의 처리 시간 · CHECK latency_ms >= 0 |
| 22 | `input_tokens` | 입력토큰수 | `integer` | — | — | — | — | 모델 입력 토큰 수 · CHECK input_tokens >= 0 |
| 23 | `output_tokens` | 출력토큰수 | `integer` | — | — | — | — | 모델 출력 토큰 수 · CHECK output_tokens >= 0 |
| 24 | `error_code` | 오류코드 | `varchar(80)` | — | — | — | — | 재시도·분석에 사용할 정규화 오류 코드 |
| 25 | `error_message` | 오류내용 | `text` | — | — | — | — | 민감정보를 제거한 오류 설명 |
| 26 | `retry_count` | 재시도횟수 | `smallint` | — | Y | `0` | — | 동일 실행의 재시도 횟수 · CHECK retry_count >= 0 |
| 27 | `correlation_id` | 상관관계ID | `uuid` | — | Y | — | — | Django 요청, FastAPI 실행, 로그 연결 ID |
| 28 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | AI 실행 레코드 생성 일시 |
| 29 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_ai_run` | BTREE | Y | id |
| 2 | `ix_ai_run_inquiry_task` | BTREE | N | inquiry_id, task_type_code, created_at DESC |
| 3 | `ix_ai_run_status` | BTREE | N | status_code, created_at |
| 4 | `ix_ai_run_correlation` | BTREE | N | correlation_id |
| 5 | `ux_ai_run_idempotency` | BTREE | Y | idempotency_key |
| 6 | `ux_ai_run_id_inquiry` | BTREE | Y | id, inquiry_id |
| 7 | `ux_ai_run_id_inquiry_correlation` | BTREE | Y | id, inquiry_id, correlation_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_ai_run_schema_errors_array` | CHECK | jsonb_typeof(schema_validation_errors)='array' |
| 2 | `ck_ai_run_success` | CHECK | status_code<>'SUCCEEDED' OR (schema_validation_status_code='PASSED' AND validated_output_payload IS NOT NULL AND completed_at IS NOT NULL) |
| 3 | `ck_ai_run_failure` | CHECK | status_code NOT IN ('FAILED','TIMED_OUT') OR (error_code IS NOT NULL AND completed_at IS NOT NULL) |
| 4 | `ck_ai_run_time_order` | CHECK | completed_at IS NULL OR (status_code='CANCELLED' AND started_at IS NULL AND completed_at>=created_at) OR (started_at IS NOT NULL AND completed_at>=started_at) |
| 5 | `ck_ai_run_input_hash` | CHECK | input_sha256 ~ '^[0-9a-f]{64}$' |
| 6 | `ck_ai_run_model_config` | CHECK | jsonb_typeof(model_config)='object' |
| 7 | `ck_ai_run_no_evidence` | CHECK | status_code<>'NO_EVIDENCE' OR (schema_validation_status_code='PASSED' AND completed_at IS NOT NULL AND validated_output_payload IS NOT NULL) |
| 8 | `ck_ai_run_nonnegative_metrics` | CHECK | retry_count>=0 AND (latency_ms IS NULL OR latency_ms>=0) AND (input_tokens IS NULL OR input_tokens>=0) AND (output_tokens IS NULL OR output_tokens>=0) |
| 9 | `ck_ai_run_reproducibility` | CHECK | (status_code IN ('QUEUED','CANCELLED') AND started_at IS NULL) OR (model_provider IS NOT NULL AND model_name IS NOT NULL AND prompt_version IS NOT NULL) |
| 10 | `ck_ai_run_lifecycle` | CHECK | (status_code='QUEUED' AND started_at IS NULL AND completed_at IS NULL) OR (status_code IN ('RUNNING','RETRYING') AND started_at IS NOT NULL AND completed_at IS NULL) OR (status_code IN ('SUCCEEDED','NO_EVIDENCE','FAILED','TIMED_OUT') AND started_at IS NOT NULL AND completed_at IS NOT NULL) OR (status_code='CANCELLED' AND completed_at IS NOT NULL) |
| 11 | `ck_ai_run_json_objects` | CHECK | jsonb_typeof(input_payload)='object' AND (validated_output_payload IS NULL OR jsonb_typeof(validated_output_payload)='object') |
| 12 | `ck_ai_run_schema_failure` | CHECK | schema_validation_status_code<>'FAILED' OR (raw_output_text IS NOT NULL AND jsonb_array_length(schema_validation_errors)>0) |
| 13 | `ck_aiops_ai_run_task_type_code_allowed` | CHECK | task_type_code IN ('STRUCTURE_SYMPTOM','GENERATE_QUESTIONS','ASSESS_RISK','RETRIEVE_EVIDENCE','GENERATE_GUIDANCE','SUMMARIZE_CONSULTATION','DRAFT_HANDOFF') |
| 14 | `ck_aiops_ai_run_schema_validation_status_code_allowed` | CHECK | schema_validation_status_code IN ('NOT_RUN','PASSED','FAILED') |
| 15 | `ck_aiops_ai_run_status_code_allowed` | CHECK | status_code IN ('QUEUED','RUNNING','SUCCEEDED','NO_EVIDENCE','FAILED','TIMED_OUT','RETRYING','CANCELLED') |

</details>

---

### 29. `aiops_retrieval_run` — RAG 검색 실행

- 도메인: AI 운영
- 목적: 제품·세대 필터, 검색 질의, top-k, 재정렬, 지연과 근거 부족 사유를 검색 실행별로 기록한다. [공통 설계 원칙] 가명화 검색문 해시·검색 설정 버전·거리함수·근거 없음 사유를 실행별로 보존한다. [검색 정책 초안: RAG 담당 지침 목표는 bge-m3 원본 차원·Cosine Exact Top-5·ANN 제외. 상위 모델 매핑·Migration 승인 전 운영 기본값은 팀 결정 필요]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `ai_run_id` | AI실행식별자 | `uuid` | — | Y | — | 물리 FK: aiops_ai_run.id | 검색을 요청한 AI 실행 · ON DELETE RESTRICT |
| 3 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 검색 대상 문의 · ON DELETE RESTRICT |
| 4 | `query_text` | 검색질의 | `text` | — | Y | — | — | 구조화 증상과 질문으로 만든 검색 질의 |
| 5 | `query_sha256` | 검색문해시 | `varchar(64)` | — | Y | — | — | 가명화·정규화 검색문 변경 검출용 SHA-256 |
| 6 | `filter_payload` | 검색필터 | `jsonb` | — | Y | `'{}'::jsonb` | — | 제품 모델, 세대, 문서 상태 등 적용 필터 |
| 7 | `retrieval_config_version` | 검색설정버전 | `varchar(50)` | — | Y | — | — | 검색·필터·임계값 설정 버전. Hybrid는 향후 확장 후보 · 현재 설계 단계 Exact Search와 향후 확장 Profile을 구분; 운영 Profile은 팀 결정 필요 |
| 8 | `retrieval_config` | 검색설정 | `jsonb` | — | Y | `'{}'::jsonb` | — | 제품·세대·문서 버전 필터와 검색 설정 Snapshot · 키워드·벡터 가중치와 reranker는 확장 후보이며 현재 설계 단계 Exact Search 기본값이 아님 |
| 9 | `embedding_model` | 임베딩모델 | `varchar(120)` | — | — | — | — | 벡터 검색에 사용한 모델 |
| 10 | `embedding_model_version` | 임베딩모델버전 | `varchar(80)` | — | — | — | — | 검색에 사용한 고정 임베딩 모델 버전 |
| 11 | `distance_metric_code` | 거리함수코드 | `varchar(30)` | — | — | — | 논리 코드: common_code(group=VECTOR_DISTANCE_METRIC) | 현재 설계 단계 목표 COSINE; L2·INNER_PRODUCT는 설계 제안 후보 · 운영 거리함수와 코드값 집합은 팀 결정 필요 |
| 12 | `top_k` | 검색결과수 | `smallint` | — | Y | — | — | 1차 검색 청크 수. RAG 담당 지침 검토 목표는 5 · 운영 기본값 없음; 정확한 값은 팀 결정 필요 |
| 13 | `reranker_name` | 재정렬기 | `varchar(120)` | — | — | — | — | 향후 재정렬 확장 후보 식별자; 현재 설계 단계 Exact Search에서는 미사용 · 활성화 시점·모델 매핑은 팀 결정 필요 |
| 14 | `status_code` | 검색상태코드 | `varchar(40)` | — | Y | `'QUEUED'` | 논리 코드: common_code(group=RETRIEVAL_STATUS) | QUEUED, RUNNING, SUCCEEDED, NO_EVIDENCE, FAILED · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 15 | `started_at` | 시작일시 | `timestamptz` | — | — | — | — | 검색 실행 시작 일시; QUEUED는 NULL |
| 16 | `completed_at` | 완료일시 | `timestamptz` | — | — | — | — | 검색 완료 일시 |
| 17 | `latency_ms` | 검색지연밀리초 | `integer` | — | — | — | — | 검색·재정렬 총 처리 시간 · CHECK latency_ms >= 0 |
| 18 | `no_evidence_reason` | 근거부족사유 | `text` | — | — | — | — | 모델 불일치, 점수 미달 등 검색 보류 사유 |
| 19 | `error_code` | 오류코드 | `varchar(80)` | — | — | — | — | FAILED 검색 실행의 안정적인 오류 분류 코드 |
| 20 | `error_message` | 오류메시지 | `text` | — | — | — | — | FAILED 검색 실행의 진단 메시지; 개인정보·비밀값 저장 금지 |
| 21 | `correlation_id` | 상관관계식별자 | `uuid` | — | Y | — | — | Django 요청·AI 실행·검색 로그를 연결하는 ID |
| 22 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 검색 실행 레코드 생성 일시 |
| 23 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_retrieval_run` | BTREE | Y | id |
| 2 | `ix_retrieval_ai_run` | BTREE | N | ai_run_id, inquiry_id |
| 3 | `ix_retrieval_inquiry` | BTREE | N | inquiry_id, created_at DESC |
| 4 | `ix_retrieval_status` | BTREE | N | status_code, created_at |
| 5 | `ix_retrieval_correlation` | BTREE | N | correlation_id |
| 6 | `ux_retrieval_id_ai_inquiry` | BTREE | Y | id, ai_run_id, inquiry_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_retrieval_top_k` | CHECK | top_k BETWEEN 1 AND 100 |
| 2 | `ck_retrieval_no_evidence` | CHECK | status_code<>'NO_EVIDENCE' OR no_evidence_reason IS NOT NULL |
| 3 | `ck_retrieval_time_order` | CHECK | completed_at IS NULL OR (started_at IS NOT NULL AND completed_at>=started_at) |
| 4 | `fk_retrieval_ai_run_context` | FOREIGN KEY | (ai_run_id, inquiry_id, correlation_id) REFERENCES aiops_ai_run(id, inquiry_id, correlation_id) ON DELETE RESTRICT |
| 5 | `ck_retrieval_terminal` | CHECK | (status_code='QUEUED' AND started_at IS NULL AND completed_at IS NULL) OR (status_code='RUNNING' AND started_at IS NOT NULL AND completed_at IS NULL) OR (status_code IN ('SUCCEEDED','NO_EVIDENCE','FAILED') AND started_at IS NOT NULL AND completed_at IS NOT NULL) |
| 6 | `ck_retrieval_query_hash` | CHECK | query_sha256 ~ '^[0-9a-f]{64}$' |
| 7 | `ck_retrieval_json_objects` | CHECK | jsonb_typeof(filter_payload)='object' AND jsonb_typeof(retrieval_config)='object' |
| 8 | `ck_retrieval_embedding_context` | CHECK | (embedding_model IS NULL AND embedding_model_version IS NULL AND distance_metric_code IS NULL) OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL AND distance_metric_code IS NOT NULL) |
| 9 | `ck_retrieval_failure` | CHECK | status_code<>'FAILED' OR (error_code IS NOT NULL AND error_message IS NOT NULL) |
| 10 | `policy_retrieval_terminal_hit_count` | APPLICATION POLICY | SUCCEEDED는 selected_for_answer=true·APPLICABLE 검색 결과가 1건 이상이고 NO_EVIDENCE·FAILED는 선택 결과가 0건인지 같은 Django transaction에서 검증 |
| 11 | `ck_aiops_retrieval_run_distance_metric_code_allowed` | CHECK | (distance_metric_code IS NULL OR distance_metric_code IN ('COSINE','L2','INNER_PRODUCT')) |
| 12 | `ck_aiops_retrieval_run_status_code_allowed` | CHECK | status_code IN ('QUEUED','RUNNING','SUCCEEDED','NO_EVIDENCE','FAILED') |

</details>

---

### 30. `aiops_retrieval_hit` — RAG 검색 결과

- 도메인: AI 운영
- 목적: 검색 실행별 후보 청크의 순위, 벡터·키워드·재정렬 점수, 적용성, 답변 선택 여부를 저장한다. [공통 설계 원칙] 벡터·키워드·하이브리드·재정렬 점수와 적용성 판단·선택 사유를 후보별로 저장한다. [검색 정책 초안: 현재 설계 단계 Exact Search에서는 vector_score를 사용하고 hybrid_score·rerank_score는 미사용 확장 후보. 전환 시점은 팀 결정 필요]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `retrieval_run_id` | 검색실행식별자 | `uuid` | — | Y | — | 물리 FK: aiops_retrieval_run.id | 결과가 속한 검색 실행 · ON DELETE RESTRICT |
| 3 | `chunk_id` | 문서청크식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_document_chunk.id | 검색된 공식 문서 청크 · ON DELETE RESTRICT |
| 4 | `rank_no` | 검색순위 | `smallint` | — | Y | — | — | 최종 검색 순위 · CHECK rank_no > 0 |
| 5 | `vector_score` | 벡터점수 | `numeric(10,6)` | — | — | — | — | 벡터 유사도 또는 거리 변환 점수 |
| 6 | `keyword_score` | 키워드점수 | `numeric(10,6)` | — | — | — | — | PostgreSQL FTS 기반 키워드 점수 |
| 7 | `hybrid_score` | 하이브리드점수 | `numeric(10,6)` | — | — | — | — | 향후 Hybrid 확장 후보 점수; 현재 설계 단계 Exact Search에서는 null · 사용 여부·가중치는 팀 결정 필요 |
| 8 | `rerank_score` | 재정렬점수 | `numeric(10,6)` | — | — | — | — | 향후 reranker 확장 후보 점수; 현재 설계 단계 Exact Search에서는 null · 사용 여부·모델 매핑은 팀 결정 필요 |
| 9 | `applicability_status_code` | 적용성상태코드 | `varchar(40)` | — | Y | `'PENDING'` | 논리 코드: common_code(group=EVIDENCE_APPLICABILITY) | PENDING, APPLICABLE, PARTIAL, NOT_APPLICABLE · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 10 | `applicability_reason` | 적용성판단사유 | `text` | — | — | — | — | 제품·리비전·내용 불일치 등 사후 검증 사유 |
| 11 | `selected_for_answer` | 답변선택여부 | `boolean` | — | Y | `false` | — | 안내·요약의 실제 근거로 선택했는지 여부 |
| 12 | `selected_at` | 답변선택일시 | `timestamptz` | — | — | — | — | 실제 답변 근거로 선택된 일시 |
| 13 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 검색 결과 저장 일시 |
| 14 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_retrieval_hit` | BTREE | Y | id |
| 2 | `ux_retrieval_hit_rank` | BTREE | Y | retrieval_run_id, rank_no |
| 3 | `ux_retrieval_hit_chunk` | BTREE | Y | retrieval_run_id, chunk_id |
| 4 | `ix_retrieval_hit_selected` | BTREE | N | retrieval_run_id, rank_no / WHERE selected_for_answer=true |
| 5 | `ix_retrieval_hit_chunk` | BTREE | N | chunk_id |
| 6 | `ux_retrieval_hit_id_chunk` | BTREE | Y | id, chunk_id |
| 7 | `ux_retrieval_hit_id_run_chunk` | BTREE | Y | id, retrieval_run_id, chunk_id |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_retrieval_hit_score` | CHECK | num_nonnulls(vector_score, keyword_score, hybrid_score, rerank_score)>=1 |
| 2 | `ck_retrieval_hit_selected` | CHECK | (selected_for_answer=true AND applicability_status_code='APPLICABLE' AND selected_at IS NOT NULL) OR (selected_for_answer=false AND selected_at IS NULL) |
| 3 | `ck_retrieval_hit_rank` | CHECK | rank_no > 0 |
| 4 | `ck_retrieval_hit_applicability_reason` | CHECK | applicability_status_code NOT IN ('PARTIAL','NOT_APPLICABLE') OR applicability_reason IS NOT NULL |
| 5 | `policy_retrieval_hit_rag_scope` | APPLICATION POLICY | 검색·선택 시 현재 active 청크, RAG 적격 페이지, APPROVED·미삭제 문서, 검증된 모델 범위를 동일 QuerySet으로 적용 |
| 6 | `policy_retrieval_hit_selection_transaction` | APPLICATION POLICY | 검색 실행 terminal 전환과 selected_for_answer·applicability_status_code 확정을 한 Django transaction에서 처리하고 선택 건수 규칙을 통합 테스트 |
| 7 | `ck_aiops_retrieval_hit_applicability_status_code_allowed` | CHECK | applicability_status_code IN ('PENDING','APPLICABLE','PARTIAL','NOT_APPLICABLE') |

</details>

---

### 31. `knowledge_evidence_link` — 업무 결과 근거 연결

- 도메인: 지식·근거
- 목적: 고객 안내·상담·기사 리포트에 사용된 공식 청크와 페이지 인용 스냅샷을 연결하여 추적 가능성을 보장한다. [공통 설계 원칙] 정확히 한 업무 결과에 연결하고 EvidenceCardDTO를 재현할 문서·출처·인용 스냅샷을 보존한다.
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 레코드 고유 식별자 · Django UUIDField 기본값 |
| 2 | `inquiry_id` | 문의식별자 | `uuid` | — | Y | — | 물리 FK: support_inquiry.id | 근거가 사용된 문의 · ON DELETE RESTRICT |
| 3 | `guidance_id` | 고객안내식별자 | `uuid` | — | — | — | 물리 FK: support_guidance.id | 고객 안내의 근거인 경우 대상 · ON DELETE RESTRICT |
| 4 | `consultation_id` | 상담식별자 | `uuid` | — | — | — | 물리 FK: support_consultation.id | 상담 요약의 근거인 경우 대상 · ON DELETE RESTRICT |
| 5 | `handoff_report_id` | 인계리포트식별자 | `uuid` | — | — | — | 물리 FK: support_handoff_report.id | 기사 리포트의 근거인 경우 대상 · ON DELETE RESTRICT |
| 6 | `ai_run_id` | AI실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_ai_run.id | 근거를 선택·검증한 AI 실행 · ON DELETE RESTRICT |
| 7 | `chunk_id` | 문서청크식별자 | `uuid` | — | Y | — | 물리 FK: knowledge_document_chunk.id | 실제 사용한 공식 문서 청크 · ON DELETE RESTRICT |
| 8 | `retrieval_hit_id` | 검색결과식별자 | `uuid` | — | — | — | 물리 FK: aiops_retrieval_hit.id | 자동 검색으로 선택한 경우의 원본 검색 결과 · ON DELETE RESTRICT; 수동 근거는 NULL |
| 9 | `retrieval_run_id` | 검색실행식별자 | `uuid` | — | — | — | 물리 FK: aiops_retrieval_run.id | 자동 검색 근거의 실행 문맥 · ON DELETE RESTRICT; 수동 근거는 NULL |
| 10 | `selection_origin_code` | 선택출처코드 | `varchar(40)` | — | Y | `'AUTO_RETRIEVAL'` | 논리 코드: common_code(group=EVIDENCE_SELECTION_ORIGIN) | AUTO_RETRIEVAL, MANUAL · 설계 제안: Django TextChoices + DB CHECK 제안; Enum 저장 방식·값 집합은 팀 결정 필요 |
| 11 | `evidence_role_code` | 근거역할코드 | `varchar(40)` | — | Y | `'SUPPORTING'` | 논리 코드: common_code(group=EVIDENCE_ROLE) | PRIMARY, SUPPORTING, CONTRAINDICATION · 설계 제안: Django TextChoices + CheckConstraint 제안; Enum 저장 방식·값 집합은 팀 결정 필요, 물리 FK 아님 |
| 12 | `display_order` | 표시순서 | `smallint` | — | Y | `1` | — | 동일 업무 결과 안에서 근거 카드 표시 순서 · CHECK display_order > 0 |
| 13 | `citation_label` | 인용표시 | `varchar(200)` | — | Y | — | — | 화면에 표시할 문서명·페이지 라벨 |
| 14 | `document_code_snapshot` | 문서코드스냅샷 | `varchar(80)` | — | Y | — | — | 근거 선택 시점의 문서 코드 |
| 15 | `document_title_snapshot` | 문서명스냅샷 | `varchar(300)` | — | Y | — | — | 근거 선택 시점의 공식 문서명 |
| 16 | `source_org_snapshot` | 발행기관스냅샷 | `varchar(150)` | — | Y | — | — | 근거 선택 시점의 공식 발행 기관 |
| 17 | `revision_label_snapshot` | 리비전스냅샷 | `varchar(100)` | — | — | — | — | 근거 선택 시점의 문서 리비전 |
| 18 | `official_source_url_snapshot` | 공식URL스냅샷 | `varchar(1000)` | — | Y | — | — | 근거 선택 시점의 공식 랜딩 페이지 URL |
| 19 | `document_sha256_snapshot` | 문서해시스냅샷 | `varchar(64)` | — | Y | — | — | 근거 선택 시점의 원문 SHA-256 |
| 20 | `evidence_summary` | 근거요약 | `text` | — | Y | — | — | 사용자 역할에 맞게 검증된 짧은 근거 요약 |
| 21 | `cited_text_snapshot` | 인용문스냅샷 | `text` | — | Y | — | — | 업무 결과 생성 시점의 실제 인용 구간 |
| 22 | `page_no_snapshot` | 페이지번호스냅샷 | `integer` | — | Y | — | — | 업무 결과 생성 시점의 원본 페이지 번호 · CHECK page_no_snapshot > 0 |
| 23 | `section_snapshot` | 섹션스냅샷 | `varchar(500)` | — | — | — | — | 인용 당시 청크의 section_path |
| 24 | `product_model_codes_snapshot` | 적용모델코드스냅샷 | `jsonb` | — | Y | — | — | 인용 당시 검증된 적용 제품 모델코드 배열 |
| 25 | `is_verified` | 검증여부 | `boolean` | — | Y | `false` | — | 제품·문서·인용 일치가 검증되었는지 여부 |
| 26 | `verified_by_id` | 검증자식별자 | `uuid` | — | — | — | 물리 FK: accounts_user.id | 근거를 검증한 상담사·운영자 · ON DELETE RESTRICT |
| 27 | `verified_at` | 검증일시 | `timestamptz` | — | — | — | — | 근거 검증 완료 일시 |
| 28 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 근거 연결 생성 일시 |
| 29 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_evidence_link` | BTREE | Y | id |
| 2 | `ix_evidence_link_inquiry` | BTREE | N | inquiry_id, created_at |
| 3 | `ix_evidence_link_guidance` | BTREE | N | guidance_id, inquiry_id |
| 4 | `ix_evidence_link_consultation` | BTREE | N | consultation_id, inquiry_id |
| 5 | `ix_evidence_link_handoff` | BTREE | N | handoff_report_id, inquiry_id |
| 6 | `ix_evidence_link_chunk` | BTREE | N | chunk_id |
| 7 | `ux_evidence_guidance_chunk` | BTREE | Y | guidance_id, chunk_id, evidence_role_code / WHERE guidance_id IS NOT NULL |
| 8 | `ux_evidence_consultation_chunk` | BTREE | Y | consultation_id, chunk_id, evidence_role_code / WHERE consultation_id IS NOT NULL |
| 9 | `ux_evidence_handoff_chunk` | BTREE | Y | handoff_report_id, chunk_id, evidence_role_code / WHERE handoff_report_id IS NOT NULL |
| 10 | `ix_evidence_link_ai_run` | BTREE | N | ai_run_id, inquiry_id |
| 11 | `ix_evidence_link_retrieval_hit` | BTREE | N | retrieval_hit_id, retrieval_run_id, chunk_id |
| 12 | `ux_evidence_guidance_order` | BTREE | Y | guidance_id, display_order / WHERE guidance_id IS NOT NULL |
| 13 | `ux_evidence_consultation_order` | BTREE | Y | consultation_id, display_order / WHERE consultation_id IS NOT NULL |
| 14 | `ux_evidence_handoff_order` | BTREE | Y | handoff_report_id, display_order / WHERE handoff_report_id IS NOT NULL |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_evidence_exactly_one_target` | CHECK | num_nonnulls(guidance_id, consultation_id, handoff_report_id)=1 |
| 2 | `ck_evidence_display_order` | CHECK | display_order>0 |
| 3 | `ck_evidence_verification` | CHECK | (is_verified=true AND verified_by_id IS NOT NULL AND verified_at IS NOT NULL) OR (is_verified=false AND verified_by_id IS NULL AND verified_at IS NULL) |
| 4 | `ck_evidence_document_hash` | CHECK | document_sha256_snapshot ~ '^[0-9a-f]{64}$' |
| 5 | `ck_evidence_product_models` | CHECK | jsonb_typeof(product_model_codes_snapshot)='array' AND jsonb_array_length(product_model_codes_snapshot)>0 |
| 6 | `fk_evidence_guidance_inquiry` | FOREIGN KEY | (guidance_id, inquiry_id) REFERENCES support_guidance(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 7 | `fk_evidence_consultation_inquiry` | FOREIGN KEY | (consultation_id, inquiry_id) REFERENCES support_consultation(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 8 | `fk_evidence_handoff_inquiry` | FOREIGN KEY | (handoff_report_id, inquiry_id) REFERENCES support_handoff_report(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 9 | `fk_evidence_ai_run_inquiry` | FOREIGN KEY | (ai_run_id, inquiry_id) REFERENCES aiops_ai_run(id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 10 | `fk_evidence_retrieval_hit_context` | FOREIGN KEY | (retrieval_hit_id, retrieval_run_id, chunk_id) REFERENCES aiops_retrieval_hit(id, retrieval_run_id, chunk_id) MATCH SIMPLE ON DELETE RESTRICT |
| 11 | `fk_evidence_retrieval_run_context` | FOREIGN KEY | (retrieval_run_id, ai_run_id, inquiry_id) REFERENCES aiops_retrieval_run(id, ai_run_id, inquiry_id) MATCH SIMPLE ON DELETE RESTRICT |
| 12 | `ck_evidence_selection_origin` | CHECK | (selection_origin_code='AUTO_RETRIEVAL' AND retrieval_hit_id IS NOT NULL AND retrieval_run_id IS NOT NULL AND ai_run_id IS NOT NULL) OR (selection_origin_code='MANUAL' AND retrieval_hit_id IS NULL AND retrieval_run_id IS NULL) |
| 13 | `policy_evidence_snapshot_source` | APPLICATION POLICY | AUTO_RETRIEVAL은 같은 inquiry·ai_run의 selected_for_answer=true·APPLICABLE hit만 허용하고 서버가 chunk→page→document→verified model scope snapshot을 직접 복사하며 클라이언트 임의 입력 금지 |
| 14 | `ck_knowledge_evidence_link_selection_origin_code_allowed` | CHECK | selection_origin_code IN ('AUTO_RETRIEVAL','MANUAL') |
| 15 | `ck_knowledge_evidence_link_evidence_role_code_allowed` | CHECK | evidence_role_code IN ('PRIMARY','SUPPORTING','CONTRAINDICATION') |

</details>

---

### 32. `support_questionnaire_session` — 사전 문진 세션

- 도메인: 고객 지원
- 목적: CARE_PRECHECK 사전 문진을 Inquiry 없이 생성·임시 저장·제출하고, 상담이 필요할 때 동일 구독의 새 문의를 1회 연결한다. [설계 상태: 상태·이벤트·제약은 팀 승인 전]
- 설계 상태: Design Draft

| No. | Column | 컬럼명 | Type | PK | NN | Default | Reference | 정의·비고 |
|---:|---|---|---|:---:|:---:|---|---|---|
| 1 | `id` | 식별자 | `uuid` | Y | Y | `uuid.uuid4` | — | 문진 세션 고유 식별자 · Django UUIDField 기본값 |
| 2 | `session_no` | 문진세션번호 | `varchar(40)` | — | Y | — | — | 화면·API에 노출하는 문진 세션번호 · UNIQUE |
| 3 | `subscription_id` | 구독식별자 | `uuid` | — | Y | — | 물리 FK: subscriptions_customer_subscription.id | 문진 대상 고객 구독 · ON DELETE RESTRICT |
| 4 | `inquiry_id` | 문의식별자 | `uuid` | — | — | — | 물리 FK: support_inquiry.id | SUBMITTED 후 LINK_INQUIRY로 1회 연결한 동일 구독 문의 · UNIQUE, ON DELETE RESTRICT; 연결 전 NULL |
| 5 | `questionnaire_type_code` | 문진유형코드 | `varchar(40)` | — | Y | `'CARE_PRECHECK'` | 논리 코드: common_code(group=QUESTIONNAIRE_TYPE) | CARE_PRECHECK · 설계 제안: Django TextChoices + DB CHECK 제안; Enum 저장 방식·값 집합은 팀 결정 필요 |
| 6 | `status_code` | 문진상태코드 | `varchar(40)` | — | Y | `'UNANSWERED'` | 논리 코드: common_code(group=QUESTIONNAIRE_STATUS) | UNANSWERED, IN_PROGRESS, SUBMITTED · 설계 제안: Django TextChoices + DB CHECK 제안; Enum 저장 방식·값 집합은 팀 결정 필요 |
| 7 | `questionnaire_version` | 문진버전 | `varchar(40)` | — | Y | — | — | 질문 세트 버전 |
| 8 | `answers_payload` | 답변스냅샷 | `jsonb` | — | Y | `'{}'::jsonb` | — | CARE_PRECHECK 답변 전체; 질문 코드별 JSON object · 서버 문진 스냅샷이다. Android Room의 로컬 임시 저장 엔티티와 분리한다. |
| 9 | `state_version` | 상태버전 | `integer` | — | Y | `1` | — | 낙관적 잠금 버전 |
| 10 | `started_at` | 시작일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 문진 시작 시각 |
| 11 | `submitted_at` | 제출일시 | `timestamptz` | — | — | — | — | 문진 제출 시각 |
| 12 | `linked_at` | 문의연결일시 | `timestamptz` | — | — | — | — | LINK_INQUIRY 성공 시각 |
| 13 | `creation_idempotency_key` | 생성멱등키 | `varchar(128)` | — | Y | — | — | START_CARE_PRECHECK 중복 생성을 막는 멱등성 키; API 전달 위치는 팀 결정 필요 · UNIQUE; 저장·제출·연결 키는 상태 이력에 기록 |
| 14 | `created_at` | 생성일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 생성 일시 |
| 15 | `updated_at` | 수정일시 | `timestamptz` | — | Y | `CURRENT_TIMESTAMP` | — | 레코드 최종 수정 일시 · Django auto_now 적용 |

<details>
<summary>Index 설계</summary>

| No. | Index | Type | Unique | 구성 컬럼·비고 |
|---:|---|---|:---:|---|
| 1 | `pk_questionnaire_session` | BTREE | Y | id |
| 2 | `ux_questionnaire_session_no` | BTREE | Y | session_no |
| 3 | `ux_questionnaire_session_inquiry` | BTREE | Y | inquiry_id / WHERE inquiry_id IS NOT NULL |
| 4 | `ux_questionnaire_session_idempotency` | BTREE | Y | creation_idempotency_key |
| 5 | `ix_questionnaire_session_subscription` | BTREE | N | subscription_id, status_code, created_at DESC |

</details>

<details>
<summary>Constraint·Policy 설계</summary>

| No. | 이름 | Type | 표현식·구현 비고 |
|---:|---|---|---|
| 1 | `ck_questionnaire_state_version` | CHECK | state_version > 0 |
| 2 | `ck_questionnaire_answers_object` | CHECK | jsonb_typeof(answers_payload)='object' |
| 3 | `ck_questionnaire_submission` | CHECK | (status_code IN ('UNANSWERED','IN_PROGRESS') AND submitted_at IS NULL) OR (status_code='SUBMITTED' AND submitted_at IS NOT NULL AND submitted_at>=started_at) |
| 4 | `ck_questionnaire_inquiry_link` | CHECK | (inquiry_id IS NULL AND linked_at IS NULL) OR (status_code='SUBMITTED' AND inquiry_id IS NOT NULL AND linked_at IS NOT NULL AND linked_at>=submitted_at) |
| 5 | `fk_questionnaire_inquiry_subscription` | FOREIGN KEY | (inquiry_id, subscription_id) REFERENCES support_inquiry(id, subscription_id) MATCH SIMPLE ON DELETE RESTRICT |
| 6 | `ck_sup_questionnaire_session_questionnaire_type_code_allowed` | CHECK | questionnaire_type_code IN ('CARE_PRECHECK') |
| 7 | `ck_support_questionnaire_session_status_code_allowed` | CHECK | status_code IN ('UNANSWERED','IN_PROGRESS','SUBMITTED') |

</details>

---

## 5. 변경 원칙

1. DB 변경은 승인된 Django Migration으로 재현한다.
2. 스키마 변경 시 데이터 사전, ERD, API 계약과 테스트 영향을 함께 검토한다.
3. PK·Public ID·Enum·Seed·시간대 등 미정 정책을 작성자가 임의로 확정하지 않는다.
4. 실제 개인정보나 운영 비밀값을 예시 데이터로 추가하지 않는다.
5. 구현·Migration·무결성 테스트·리뷰가 완료되기 전에는 이 문서를 운영 스키마로 표시하지 않는다.

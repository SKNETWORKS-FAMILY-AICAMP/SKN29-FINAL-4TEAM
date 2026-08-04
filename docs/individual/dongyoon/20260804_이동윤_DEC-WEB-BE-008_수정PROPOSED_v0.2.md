# DEC-WEB-BE-008 공식 근거 공개 계약 수정 PROPOSED v0.2

> 프로젝트: WaterBridge Final Project 4팀
> 결정 ID: `DEC-WEB-BE-008`
> 배포 대응: `BE-HANDOFF-20260804-R1`
> 회신자·도메인 결정 책임자: 이동윤(AI·RAG)
> 작성일: 2026-08-04
> 현재 상태: `PROPOSED v0.2`
> 검토 상태: Backend `CHANGE_REQUEST` / Web 재검토 대기 / Data·QA 검토 대기
> 구현 상태: `HOLD`
> PM 최종 승인: 윤승혁 `NOT_REVIEWED`

## 1. 회신 목적과 효력

최지용의 `DEC-WEB-BE-008` 수정 제안 요청 CR-01~07과 앞선 Web
`CHANGE_REQUEST`를 하나의 수정안으로 통합한다. AI가 반환하는 근거 후보,
Backend가 보존하는 검증 Snapshot과 Web에 공개할 EvidenceCard의 경계를
확정하기 위한 제안이다.

이 문서는 Active 계약이나 구현 승인이 아니다. 최지용·한예나·김은진의
검토, 이동윤의 `DOMAIN_APPROVED`, 윤승혁 PM의 `FINAL_APPROVED` 전에는 다음
작업을 시작하거나 완료로 처리하지 않는다.

- OpenAPI·AI JSON Schema 변경
- Backend DTO·Serializer·Route·DB Migration 변경
- AI Adapter·Vector Runtime 변경
- Web Evidence UI 실제 API 전환
- Contract·통합·E2E Test 기준선 변경
- 공용 Branch 게시·병합

## 2. CR-01~07 판정 요약

| CR | 판정 | 수정 결정·대체안 |
| --- | --- | --- |
| CR-01 필드 통일 | `PARTIAL` | 전체 매핑과 최종 공개 후보를 제시한다. 다만 Active `EvidenceCard.yaml`과 Serializer가 빈 골격이므로 최지용이 이름·배치를 확정해야 한다. |
| CR-02 요약 SSOT | `ACCEPT` | Data Owner가 승인한 `evidence_summary`를 원천으로 하고 Backend `EvidenceLink.evidence_summary` Snapshot을 화면 공개 기준으로 사용한다. |
| CR-03 페이지·URL | `ACCEPT` | P0에서 `1 EvidenceCard = 1 EvidenceLink = 1 page`를 수용한다. 공식 Landing URL은 필수, 직접 Download URL은 조건부 선택으로 한다. |
| CR-04 검증 상태 | `ACCEPT` | Data→AI→Backend→공개 허용·차단 매핑을 본 문서 6장으로 고정 제안한다. |
| CR-05 0건·장애 분리 | `ACCEPT` | 정상 0건은 HTTP 200 Fallback, 검색 실패·설정 장애는 503, Timeout은 504로 분리한다. 현재 Runtime 공백은 승인 후 수정한다. |
| CR-06 API·권한 | `PARTIAL` | P0 배치와 역할·객체 권한을 제안한다. Active Path와 최종 Guard는 Backend·State 관할에서 DEC-WEB-BE-002·005와 함께 확정한다. |
| CR-07 날짜 공백 | `ACCEPT` | `published_on=null`이면 추정하지 않고 숨긴다. `revision_label`로 날짜를 만들지 않으며 별도 개정일은 P0에 추가하지 않는다. |

## 3. P0 최종 공개 객체 제안

### 3.1 객체 단위

P0에서는 다음 관계를 사용한다.

```text
1 EvidenceCard = 1 EvidenceLink = 1 DocumentChunk = 1 DocumentPage
```

따라서 최종 공개 객체는 단일 `page_no`를 사용한다. AI 후보가 여러
`page_refs`를 반환하면 Backend Adapter가 그대로 한 카드에 저장하지 않는다.
승인된 페이지 단위 청크로 분할하여 각 페이지에 별도 EvidenceLink와
EvidenceCard를 생성해야 한다.

현재 D세대 순간 온수 청크처럼 `[38, 39]`를 가진 데이터는 팀 DB 적재 전에
페이지 단위 청크로 분할하고, 분할 후에도 원문 Hash·문서 Revision·조치 의미가
보존되는지 Data·QA가 확인한다. 단순히 첫 페이지 하나만 남기지 않는다.

이 결정은 Web의 기존 `page_refs` 배열 요청을 변경하므로 한예나의 재검토가
필요하다.

### 3.2 최종 공개 필드 후보

모든 필드는 응답 객체의 고정 Shape를 위해 필드 자체는 항상 포함한다.
Nullable 필드는 값이 없을 때 JSON `null`을 반환한다.

| 최종 공개 필드 | 형식·제약 | 필수/Nullable | 공개 기준 |
| --- | --- | --- | --- |
| `evidence_id` | UUID string | 필수 | `EvidenceLink.public_id`, 내부 PK·`chunk_id` 사용 금지 |
| `display_order` | integer `1..3` | 필수 | 한 응답 내 유일, 오름차순 |
| `document_title` | string, 최대 300자 | 필수 | Backend 문서 제목 Snapshot |
| `source_organization` | string, 최대 150자 | 필수 | Backend 발행기관 Snapshot |
| `document_version` | string, 최대 100자 | 필수·Nullable | `revision_label_snapshot`, 없으면 `null` |
| `published_on` | `YYYY-MM-DD` | 필수·Nullable | `SourceDocument.published_on` 그대로 사용, 없으면 `null` |
| `page_no` | integer, 최소 1 | 필수 | `EvidenceLink.page_no_snapshot` |
| `evidence_summary` | string, 최대 500자 | 필수 | 사람이 검수한 Backend Snapshot |
| `official_url` | HTTPS URL, 최대 1000자 | 필수·Non-null | 공식 Landing URL Snapshot |
| `link_status` | `AVAILABLE` 또는 `UNAVAILABLE` | 필수 | Backend의 허용 도메인·접근성 검사 결과 |
| `download_url` | HTTPS URL, 최대 1000자 | 필수·Nullable | 공식 직접 Download 조건 충족 시만 제공 |
| `verification_label` | `공식 근거 확인` | 필수 | 공개 허용 Gate 통과 시에만 카드가 존재 |

공개 카드는 한 응답에 최대 3개다. Backend는 검증·업무 관련도 순으로 선택한
뒤 `display_order`를 부여한다. Web은 `evidence_id`를 렌더링 Key로 사용하고
별도 의미 기반 중복 제거 또는 순서 재계산을 하지 않는다.

### 3.3 최종 공개 예시

```json
{
  "evidence_id": "018f2f9b-7c30-7981-b541-1a987c88b208",
  "display_order": 1,
  "document_title": "WPU-JAC104D / WPU-JCC104D 사용설명서",
  "source_organization": "SK매직",
  "document_version": "REV.00",
  "published_on": null,
  "page_no": 38,
  "evidence_summary": "누수 발생 시 급수와 전원을 차단하고 즉시 상담으로 전환하는 안전 우선 조치입니다.",
  "official_url": "https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUJAC104DWH&tabIndex=3",
  "link_status": "AVAILABLE",
  "download_url": null,
  "verification_label": "공식 근거 확인"
}
```

위 예시는 수정 제안이며 아직 Active OpenAPI Schema가 아니다.

## 4. 기존→AI→Backend→공개 필드 매핑

| 의미 | Data·기존 원천 | AI 후보 | Backend Snapshot·SSOT | 최종 공개 | 처리 |
| --- | --- | --- | --- | --- | --- |
| 공개 ID | 없음 | 없음 | `EvidenceLink.public_id` | `evidence_id` | Backend 생성 UUID |
| 표시 순서 | 검색 Rank 후보 | 없음 | `EvidenceLink.display_order` | `display_order` | Backend가 1~3 부여 |
| 문서 식별 | `document_id` | 공개하지 않음 | `document_code_snapshot` | 비공개 | 내부 추적 전용 |
| 문서 제목 | 문서 Metadata·현재 `section_title` | `document_title` 후보 | `document_title_snapshot` | `document_title` | Backend 문서 제목을 최종 기준으로 사용 |
| 발행 기관 | `provider` | 현재 없음 | `source_org_snapshot` | `source_organization` | Backend Snapshot 기준 |
| 문서 버전 | `version` | `document_version` | `revision_label_snapshot` | `document_version` | 없으면 `null` |
| 발행일 | 현재 승인 청크에 없음 | 없음 | `SourceDocument.published_on` | `published_on` | 없으면 `null`, 추정 금지 |
| 페이지 | `page_start`, `page_refs` | `page`, `page_refs` | `page_no_snapshot` | `page_no` | P0 단일 페이지로 분할·저장 |
| 검수 요약 | `evidence_summary` | `summary` | `EvidenceLink.evidence_summary` | `evidence_summary` | 5장의 단일 SSOT 적용 |
| 공식 Landing | `source_url` | `official_url` | `official_source_url_snapshot` | `official_url` | 필수·Non-null |
| 직접 Download | 승인된 별도 URL이 있을 때만 | 현재 없음 | 별도 공개 Snapshot 필요 | `download_url` | 없으면 `null`, 내부 파일 URI 사용 금지 |
| 검증 상태 | Data 상태 3종 조합 | `verification_status` | `is_verified`·검증자·시각 | `verification_label` | 원시 코드는 비공개 |
| 링크 상태 | 수집·검사 결과 | 없음 | Backend 검사 결과 | `link_status` | 응답 중 실시간 외부 호출 금지 |
| 유사도 | 없음 | `similarity_score` | Retrieval Hit | 비공개 | 정확도·안전 보증 오해 방지 |
| 청크 ID | `chunk_id` | `chunk_id` | 내부 Chunk FK | 비공개 | 내부 구조 노출 방지 |

현재 AI `document_title`이 `section_title`을 사용하고 `summary`가
`chunk.content`를 전달하는 구현은 이 목표 매핑과 다르다. 승인 후 AI Adapter와
Indexing을 수정하고 Contract Test로 고정한다.

## 5. `evidence_summary` 단일 SSOT

### 5.1 기준 흐름

```text
Data Owner 승인 evidence_summary
  → AI는 내용을 변경하지 않은 근거 후보 summary로 전달
  → Backend가 원천 Hash·문서·페이지와 대조
  → EvidenceLink.evidence_summary에 Snapshot 저장
  → EvidenceCard.evidence_summary로 그대로 공개
```

화면 공개 시점의 단일 기준값은 `EvidenceLink.evidence_summary` Snapshot이다.
AI가 새 요약을 생성하거나 Backend가 청크 원문을 자동 절단해 만들지 않는다.
Data 승인 요약이 500자를 초과하거나 의미가 불명확하면 카드 생성 전에 Data
Owner에게 반환하여 다시 검수한다.

### 5.2 변경·재검증

- 원천 문서 Revision·Hash·페이지가 바뀌면 기존 Snapshot을 덮어쓰지 않는다.
- 새 Revision 청크와 EvidenceLink를 생성해 변경 이력을 보존한다.
- `chunk_text`, `cited_text_snapshot`, 고객 원문을 공개 요약으로 대체하지
  않는다.
- 요약이 없거나 원천과 불일치하면 해당 카드를 공개하지 않는다.

## 6. 검증 상태와 공개 허용 매핑

P0 공개는 아래 모든 단계가 통과된 경우만 허용한다.

| Data 상태 | AI 판정 | Backend 판정 | 공개 결과 |
| --- | --- | --- | --- |
| `verification_status=TEXT_AND_VISUAL_VERIFIED`, `scope_role=mvp`, `rag_policy=INCLUDE`, 정확 모델·D세대·공식 분류·Hash 일치 | `official_verified`, `allowed_use=true`로 검색 후보 반환 | 문서·페이지·Hash·URL 재검증, `is_verified=true`와 검증자·시각 Bundle 완성 | `ALLOW` |
| Data 공식 검증은 통과했지만 모델·세대·Hash·URL 중 하나 불일치 | 검색 전·후 정책 필터에서 제외 | EvidenceLink 생성 금지 | `BLOCK` |
| `allowed_use=CONDITIONAL_SUPPORT` 또는 `rag_policy=EXCLUDE_*` | 고객 안내 근거로 반환하지 않음 | 카드 생성 금지 | `BLOCK` |
| 미검증·OCR만 검증·정확 모델 미확인 | `official_verified`로 승격 금지 | 카드 생성 금지 | `BLOCK` |
| AI `team_verified`만 존재 | P0 공개 후보에서 제외 | `is_verified=true`로 자동 변환 금지 | `BLOCK` |
| AI는 `official_verified`이나 Backend Snapshot 검증 Bundle 미완성 | 후보 전달까지만 인정 | 카드 공개 금지 | `BLOCK` |

`verification_label`은 위 `ALLOW` 결과를 사용자용으로 표시한 문구일 뿐이며
Data·AI·Backend 원시 상태를 대체하지 않는다.

## 7. 정상 0건·검색 장애·Timeout·설정 오류 분리

`evidence_status`는 Evidence 처리 상태이며 문의 업무 `status_code`와 다른
필드다. Web은 카드 배열을 보고 상태를 추론하지 않는다.

| 실행 결과 | AI HTTP·계약 | `evidence_status` | EvidenceCard | Backend·Web 처리 |
| --- | --- | --- | --- | --- |
| 정상 근거 있음 | `200`, `SUCCEEDED`, 근거 1건 이상 | `AVAILABLE` | 1~3개 | 카드 표시 |
| 정상 검색 완료·결과 0건 | `200`, `FALLBACK`, `failure_stage=RETRIEVING` | `NO_MATCH` | `[]` | `PENDING_CONSULTATION`, 상담 전환 |
| PostgreSQL·pgvector·Embedding 검색 실패 | `503`, `AI-FAILED-01`, `retryable=true`, 실패 Stage 기록 | `RETRIEVAL_FAILED` | 현재 실행 신규 카드 없음 | 장애 안내·재시도 정책 적용, 0건으로 기록 금지 |
| 검색·Embedding·Pipeline Timeout | `504`, `AI-TIMEOUT-01`, 실제 실패 Stage | `RETRIEVAL_TIMEOUT` | 현재 실행 신규 카드 없음 | Timeout 안내·상담 전환, 0건으로 기록 금지 |
| 팀 운영 Profile의 DSN·Revision·Manifest 누락 | Readiness 실패 또는 `503`, `AI-FAILED-01` | `NOT_CONFIGURED` | 현재 실행 신규 카드 없음 | 운영 오류, 정상 Fallback으로 처리 금지 |

실패 실행에서 이전 성공 카드가 존재하더라도 현재 결과처럼 묵시적으로
재사용하지 않는다. 이전 결과를 보여줄 필요가 있으면 `source_run_id`와 생성
시각을 포함한 별도 Stale 정책 승인을 받아야 한다.

AI 관할 Runtime에서는 Vector Store 미설정과 정상 0건을 분리하는 로컬
후보 구현과 단위 테스트를 추가했다. 정상 0건은 200 Fallback, 설정 누락은
503·`retryable=false`, 검색 실행 실패는 503·`retryable=true`, Timeout은
504로 구분한다. Backend `evidence_status` 저장·공개와 팀 DB E2E는 아직
구현·완료 증거가 아니며 통합 Gate는 계속 `HOLD`다.

## 8. P0 API 배치·역할·객체 권한 제안

### 8.1 API 배치

- P0에서는 별도 `/evidence` 목록 Endpoint를 추가하지 않는다.
- DEC-WEB-BE-002에서 확정할 `GET /inquiries/{id}` 상세 Snapshot의
  `evidence_status`와 `evidence_cards`에 포함한다.
- 상담 Action 성공 응답은 최신 `status_code`, `state_version`,
  `allowed_actions`를 반환하고, 화면은 필요 시 문의 상세를 다시 조회한다.
- Endpoint·Response Wrapper의 최종 위치는 최지용이 OpenAPI 초안으로
  확정하고 윤승혁 PM 승인을 받는다.

### 8.2 역할·객체 범위

| 역할 | P0 조회 범위 | 결과 |
| --- | --- | --- |
| `CUSTOMER` | 본인 소유 Inquiry의 `official_evidence_display` | 공개 필드만 허용, 내부 AI·Vector 필드 금지 |
| `CONSULTANT` | 본인에게 배정된 Inquiry | 공개 EvidenceCard와 검증된 AI 초안 허용 |
| `TECHNICIAN` | P0 문의 상세 EvidenceCard 직접 조회는 기본 거부 | 승인된 방문 인계·사전 리포트 계약을 통해 필요한 근거만 별도 제공 |
| `OPERATOR` | 명시적 운영 Permission과 객체 범위가 승인된 경우만 | 기본 거부, 포괄 조회 금지 |
| `SYSTEM` | Backend 내부 서비스 Context | 외부 API 응답 주체로 사용 금지 |

### 8.3 HTTP 오류

| HTTP | 조건 | 공개 처리 |
| ---: | --- | --- |
| `401` | 인증 Token 없음·만료·무효 | 로그인 필요 응답 |
| `403` | 인증됐지만 해당 역할에 Evidence 조회 Capability 없음 | 권한 없음 응답 |
| `404` | 역할은 가능하지만 대상 Inquiry가 객체 범위 밖이거나 존재를 공개할 수 없음 | Resource 존재 여부를 숨김 |
| `409` | 수정 Action의 `state_version` 충돌 | 최신 버전·`allowed_actions`로 복구, 단순 조회에는 사용하지 않음 |
| `500` | 예상하지 못한 Backend 조립·저장 오류 | 내부 상세 비노출, Correlation ID 제공 |
| `503` | AI·DB·검색 Provider 일시 장애 또는 필수 설정 누락 | 재시도 가능 여부와 장애 코드 제공 |
| `504` | AI 검색·Pipeline Timeout | Timeout 코드와 Correlation ID 제공 |

Web은 `evidence_cards=[]`만 보고 문의 상태나 버튼을 계산하지 않는다.
Backend가 확정한 `status_code`, `state_version`, `allowed_actions`와 별도
`evidence_status`를 사용한다. State Enum과 Action 계산은
DEC-WEB-BE-003~005 및 State 계약을 따른다.

## 9. 공식 Landing·Download URL 정책

### 9.1 공식 Landing URL

- 공개 EvidenceCard에는 `official_url`을 반드시 포함한다.
- `EvidenceLink.official_source_url_snapshot`과 일치해야 한다.
- HTTPS, 승인된 공식 도메인, 개인정보·Token·내부 경로 미포함을 검증한다.
- URL 형식·도메인 검증이 실패하면 EvidenceCard 자체를 공개하지 않는다.
- 접근성 검사는 API 응답 중 임의 외부 URL에 실시간 요청하지 않고 적재·배치
  또는 별도 검증 과정에서 수행한다.
- 최근 접근성 실패 시 URL Snapshot은 보존하되 `link_status=UNAVAILABLE`로
  내려 Web이 링크를 비활성화한다.

### 9.2 직접 Download URL

`download_url`은 다음 조건을 모두 만족할 때만 제공한다.

1. 공식 기관이 제공한 HTTPS 직접 Download URL이다.
2. 현재 문서 Revision과 파일 Hash가 일치한다.
3. 접근 권한·만료·저작권상 화면 공개가 허용된다.
4. 내부 `original_file_uri`, 저장 경로, 서명 Token을 재사용하지 않는다.

조건을 확인할 수 없으면 `download_url=null`로 반환하며 Landing URL은 유지한다.

## 10. 발행일·개정일 공백 처리

Backend `SourceDocument.published_on`이 존재하므로 “날짜 필드가 없다”고
표현하지 않는다. 다음 문장을 P0 기준으로 사용한다.

> `published_on`은 Backend SourceDocument에 검증된 값이 있을 때만 그대로
> 공개한다. 값이 `null`이면 발행일을 추정하거나 `revision_label`, 수집일,
> 파일명, URL에서 날짜를 만들어내지 않으며 Web은 날짜 영역을 숨긴다.

현재 별도 `revised_on` SSOT는 없다. `REV.00` 같은 `revision_label`은 버전
표시이며 날짜가 아니다. Data Owner와 Backend가 별도 개정일 필드와 원천을
승인하기 전에는 `revised_on`을 P0 공개 필드에 추가하지 않는다.

## 11. 공개·비공개 경계

### 11.1 공개 가능

- 본 문서 3.2의 최종 EvidenceCard 필드
- Backend가 계산한 `evidence_status`
- 문의 Snapshot의 `status_code`, `state_version`, `allowed_actions`

### 11.2 비공개

- 내부 DB 정수 PK, `chunk_id`, 문서 내부 Code·Case ID
- Retrieval Run·Hit·AI Run ID와 `similarity_score`
- Embedding Vector·Revision, Index Version, Hash 원문
- 내부 파일 경로·`original_file_uri`·서명 Token
- 검증자 ID·개인정보와 내부 실패 상세
- 고객 상담 원문·전화번호·주소
- 전체 원문·긴 `cited_text_snapshot`
- 원시 검증 상태 Code

## 12. 미해결 조건과 담당자 검토 요청

### 12.1 최지용 Backend·DB

- 빈 Active `EvidenceCard.yaml`과 Serializer에 적용할 최종 필드명 확인
- `GET /inquiries/{id}` 상세 배치와 Response Wrapper 확인
- `evidence_status`, `link_status`, `download_url` 저장·계산 위치
- P0 페이지 단위 Chunk·EvidenceLink 적재 가능성
- 역할·객체 Guard와 401·403·404·5xx Matrix 확인

### 12.2 한예나 Web

- 기존 `page_refs` 배열 대신 단일 `page_no` 사용 가능 여부
- 필수 `official_url`과 `link_status=UNAVAILABLE`일 때 비활성화 UX
- Nullable `document_version`, `published_on`, `download_url` 처리
- `evidence_status`와 Backend `allowed_actions` 소비 가능성

### 12.3 김은진 Data·QA

- 다중 페이지 청크를 페이지 단위로 분할한 뒤 의미·Hash 검증
- `evidence_summary` 승인 원천과 500자 제한 검증
- Data→AI→Backend 공개 Gate 및 차단 Case 재현
- 정상 0건·503·504·설정 오류의 독립 E2E
- Landing·Download URL 공식성·접근성·개인정보 검증

## 13. 회신·결정 현황

| 단계 | 담당자 | 상태 | 기록 |
| --- | --- | --- | --- |
| Backend 1차 검토 | 최지용 | `CHANGE_REQUEST` | CR-01~07 수정 요청 / 2026-08-04 |
| Web 이전 검토 | 한예나 | `CHANGE_REQUEST` | Nullable·다중 페이지·링크 상태·공개 ID·제약 요청 |
| 제안 수정 | 이동윤 | `PROPOSED` | Backend·Web 요청 통합 v0.2 / 2026-08-04 |
| Backend 재검토 | 최지용 | `NOT_REVIEWED` |  |
| Web 재검토 | 한예나 | `NOT_REVIEWED` |  |
| Data·QA 검토 | 김은진 | `NOT_REVIEWED` |  |
| 도메인 결정 | 이동윤 | `NOT_REVIEWED` | 세 검토 반영 후 `DOMAIN_APPROVED` 또는 `REVISE` |
| PM 최종 승인 | 윤승혁 | `NOT_REVIEWED` | `FINAL_APPROVED`, `HOLD`, `CHANGE_REQUEST` |

## 14. Backend 전달 문구

안녕하세요. `BE-HANDOFF-20260804-R1`의 DEC-WEB-BE-008
`CHANGE_REQUEST` CR-01~07을 반영한 수정 `PROPOSED v0.2`를 전달드립니다.

- CR-02·03·04·05·07은 수용했습니다.
- CR-01은 Active EvidenceCard DTO가 빈 골격이므로 최종 필드명 확인이 필요해
  `PARTIAL`로 회신합니다.
- CR-06은 P0 배치·권한안을 제시했으나 Active Path와 Guard가 Backend·State
  관할이므로 `PARTIAL`로 회신합니다.
- Web의 다중 `page_refs` 요구와 P0 단일 페이지 제약 충돌은 단일 `page_no`
  제안으로 수정했으며 Web 재검토가 필요합니다.
- 구현 Gate는 계속 `HOLD`입니다.

최지용은 Backend 재검토 결과를 `REVIEWED` 또는 `CHANGE_REQUEST`로 회신해
주세요. 이후 한예나·김은진 검토를 반영하고 이동윤이 도메인 판정을
기록하겠습니다.

## 15. 근거

- `BE-HANDOFF-20260804-R1 / 05_이동윤_AI_RAG_DEC008_수정제안요청.md`
- `contracts/ai/common/EvidenceReference.schema.json`
- `ai/app/retrieval/indexing/chunk_loader.py`
- `ai/app/orchestration/stages/retrieval_stage.py`
- `ai/app/orchestration/pipeline_router.py`
- `ai/app/orchestration/pipeline_result.py`
- `backend/apps/evidence/models/source_document.py`
- `backend/apps/evidence/models/document_chunk.py`
- `backend/apps/evidence/models/evidence_link.py`
- `contracts/api/components/schemas/evidence/EvidenceCard.yaml`
- `contracts/api/paths/evidence.yaml`
- `contracts/state-machine/role-permissions.yaml`

## 16. 문서 변경 기록

| 버전 | 날짜 | 변경 내용 | 상태 |
| --- | --- | --- | --- |
| Web 대응 작업본 | 2026-08-03~04 | Web 1차 요청 중심 공개 필드 제안 | `SUPERSEDED` |
| v0.2 | 2026-08-04 | Backend CR-01~07과 Web 요청 통합, 단일 페이지·URL·상태·권한·날짜 정책 수정 | `PROPOSED` |

# DEC-WEB-BE-008 공식 근거·문서 링크 공개 계약 제안

> 프로젝트: WaterBridge Final Project 4팀  
> 결정 ID: `DEC-WEB-BE-008`  
> 제안작성자·단일 결정 책임자: 이동윤(AI·RAG)  
> 최초 작성일: 2026-08-03
> 최종 개정일: 2026-08-04
> 문서 버전: `v0.2`
> 현재 상태: `SUPERSEDED` — 2026-08-04 Backend CR 통합 수정본으로 대체
> 필수 검토자: 최지용(Backend), 한예나(Web), 김은진(Data·QA)  
> PM 최종 승인: 윤승혁  
> 기준 요청서: `Web_Backend_상담_방문_연동_담당자별_컨펌요청서_v0.2.md`

> 최신 기준본:
> `20260804_이동윤_DEC-WEB-BE-008_수정PROPOSED_v0.2.md`

## 1. 제안 목적과 효력

이 문서는 Web 1차 검토 대응 이력으로만 보존한다. Backend CR-01~07을
통합한 최신 수정본을 검토 기준으로 사용한다.

상담사 화면에 AI·RAG 안내와 함께 표시할 공식 근거의 공개 범위, 공개 금지
필드, 링크 실패 시 동작과 담당자별 책임을 확정하기 위한 제안이다.

이 문서는 검토를 시작하기 위한 `PROPOSED` 초안이다. 필수 검토자의
`REVIEWED`, 이동윤의 `DOMAIN_APPROVED`, 윤승혁 PM의 `FINAL_APPROVED` 전에는
다음 작업의 승인 근거로 사용하지 않는다.

- `contracts/ai/**` 또는 Active OpenAPI Schema 변경
- Backend `EvidenceCardDTO`·Serializer·Route 구현
- Web Mock을 실제 Evidence API로 교체
- DB Migration, 공용 기준선 반영, 완료 또는 병합 처리

## 2. 제안 결정문

상담사 화면에는 Backend가 권한과 검증 상태를 다시 확인하여 조립한
`EvidenceCardDTO`만 표시한다. 기본 공개 정보는 **공식 문서명, 발행 기관,
문서 버전, 근거 페이지, 짧은 근거 요약, 공식 HTTPS 링크, 사용자용 검증
표시**로 제한한다. 카드에는 공개 UUID `evidence_id`와 양의 정수
`display_order`를 포함하며 한 응답의 카드는 최대 3개로 제한한다.

AI의 `evidence_references`는 근거 후보이며 최종 화면 DTO가 아니다. Backend는
저장된 문서·검색 이력과 대조하여 최종 EvidenceCard를 조립하고, Web은 해당
DTO를 그대로 표시한다. 공식성, 제품·세대 적용 범위 또는 고객 안내 사용
허용을 확인할 수 없는 자료는 공개하지 않는다.

발행일·개정일은 현재 AI 계약과 데이터에 신뢰할 수 있는 별도 날짜 필드가
없으므로 이번 P0의 필수 공개값으로 확정하지 않는다. Data Owner가 날짜의
SSOT와 의미를 확정한 뒤 계약 변경 절차로 추가한다.

문서 버전과 공식 링크는 응답 객체에서 생략하지 않는다. 값이 없으면 각각
JSON `null`을 반환하여 Web이 필드 존재 여부를 추론하지 않게 한다.

## 3. P0 공개 필드 제안

| 화면 의미 | 제안 공개 필드 | 현재 출처 | 필수 여부 | 표시 규칙 |
| --- | --- | --- | --- | --- |
| 공개 근거 ID | `evidence_id` | Backend `EvidenceLink.public_id` | 필수 | UUID, 한 응답 내 중복 금지, 내부 `chunk_id`를 사용하지 않음 |
| 표시 순서 | `display_order` | Backend `EvidenceLink.display_order` | 필수 | `1..3`, 오름차순, 한 응답 내 중복 금지 |
| 공식 문서명 | `document_title` | AI `EvidenceReference` / Backend Snapshot | 필수 | 빈 값이면 카드 공개 금지 |
| 발행 기관 | `source_organization` | Backend `source_org_snapshot` 후보 | 필수 | P0 MVP는 `SK매직`; AI 계약에는 아직 없음 |
| 문서 버전 | `document_version` | AI / Backend `revision_label_snapshot` | 필수·Nullable | 항상 전달, 값이 없으면 `null`, Web은 라벨 숨김 |
| 근거 페이지 | `page_refs` | AI `page_refs` | 필수 배열 | 정수 배열, 중복 제거·오름차순, 매뉴얼은 1개 이상 |
| 짧은 근거 | `evidence_summary` | 승인 청크의 검수 요약 / Backend Snapshot | 필수 | 원문 복제가 아닌 검증된 요약만 표시 |
| 공식 링크 | `official_url` | AI / Backend Snapshot | 필수·Nullable | 항상 전달, `AVAILABLE`이 아니면 `null` |
| 링크 상태 | `link_status` | Backend URL 검증 결과 | 필수 | `AVAILABLE`, `UNAVAILABLE`, `NOT_PROVIDED` |
| 검증 표시 | `verification_label` | 내부 검증 상태의 화면용 변환 | 필수 | 내부 Enum 원문 대신 `공식 근거 확인` 표시 |

### 3.1 개수·길이·정렬 제한

| 항목 | 제한 | 초과 시 처리 |
| --- | ---: | --- |
| `evidence_cards` | 최대 3개 | Backend가 검증·관련도·`display_order` 기준 상위 3개만 반환 |
| `document_title` | 최대 300자 | 적재·DTO 검증 실패로 처리하며 Web에서 임의 절단하지 않음 |
| `source_organization` | 최대 150자 | 적재·DTO 검증 실패 |
| `document_version` | 최대 100자 또는 `null` | 적재·DTO 검증 실패 |
| `evidence_summary` | 최대 500자 | 승인된 요약을 다시 작성하고 재검증, 원문 단순 절단 금지 |
| `official_url` | 최대 1000자 또는 `null` | 공개 링크 제외 및 `link_status` 조정 |

Backend는 `display_order` 오름차순으로 반환하고 같은 응답에서
`evidence_id`와 `display_order`를 각각 유일하게 보장한다. Web은
`evidence_id`를 렌더링 Key로 사용하되 별도 의미 기반 중복 제거를 수행하지
않는다.

### 3.2 공개 예시

```json
{
  "evidence_id": "018f2f9b-7c30-7981-b541-1a987c88b208",
  "display_order": 1,
  "document_title": "WPU-JAC104D / WPU-JCC104D 사용설명서",
  "source_organization": "SK매직",
  "document_version": "REV.00",
  "page_refs": [38, 39],
  "evidence_summary": "순간 온수의 정상 현상과 점검이 필요한 조건을 구분합니다.",
  "official_url": "https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUJAC104DWH&tabIndex=3",
  "link_status": "AVAILABLE",
  "verification_label": "공식 근거 확인"
}
```

위 JSON은 화면 공개안의 예시이며 아직 Active OpenAPI Schema가 아니다.

## 4. 공개하지 않을 필드

다음 정보는 추적·검증·운영에는 필요하지만 상담사 화면의 기본 카드에는
노출하지 않는다.

| 비공개 정보 | 이유 |
| --- | --- |
| `chunk_id`, 내부 문서 PK·Case ID | 내부 구조와 식별자 노출 방지 |
| `similarity_score` | 검색 점수를 답변 정확도나 안전 보증으로 오해할 수 있음 |
| Embedding Revision·Index Version·Hash | 재현용 운영 Metadata이며 화면 정보가 아님 |
| `retrieval_run_id`, `retrieval_hit_id`, `ai_run_id` | 내부 추적 정보 |
| `verified_by`, 내부 사용자 식별자 | 개인정보·권한 정보 |
| 원문 전체·긴 `cited_text_snapshot` | 저작권·과다 노출·문맥 오해 위험 |
| 내부 파일 경로·비공개 저장소 링크 | 접근권한과 내부 구조 노출 방지 |
| 고객 상담 원문·전화번호·주소 | Evidence 근거가 아니며 개인정보에 해당 |
| 원시 `verification_status` | 화면이 내부 코드에 결합되지 않도록 사용자용 문구로 변환 |

원문 인용이 필요하면 짧은 범위와 페이지를 함께 표시하는 별도 계약을
검토한다. 이번 P0 기본 카드에는 원문 전체 공개를 포함하지 않는다.

## 5. 근거 공개 허용 조건

Backend가 아래 조건을 모두 확인한 Evidence만 카드로 공개한다.

1. P0에서는 `official_verified` 공식 문서로 검증되어 있다.
2. 요청 제품 코드와 세대의 적용 범위가 일치한다.
3. `allowed_use`가 고객 안내에 허용된 상태다.
4. 문서 버전·Hash와 검색 시점 Snapshot의 일관성을 확인할 수 있다.
5. 근거 페이지와 요약이 비어 있지 않다.
6. URL 공개 시 공식 도메인의 HTTPS 링크이며 개인정보·인증정보를 포함하지
   않는다.

현재 MVP의 JAC104 검색은 정확 판매 코드 `WPUJAC104DWH`, D세대,
`REV.00` 공식 매뉴얼 범위로 제한한다. 정확 모델이 검증되지 않은 FAQ와
공식 매뉴얼 내용이 충돌하는 FAQ는 단독 근거 및 공개 카드에서 제외한다.
`team_verified`는 공식 출처 확인과 공개 기준이 별도로 승인되기 전까지 내부
검토 상태로만 취급하고 P0 공개 카드에서는 제외한다.

## 6. 링크·Fallback 정책

| `link_status` | `official_url` | 화면 처리 | Backend 판정 |
| --- | --- | --- | --- |
| `AVAILABLE` | 검증된 HTTPS URL | 새 탭 링크 표시 | 허용 도메인·형식·최근 접근성 검사 통과 |
| `UNAVAILABLE` | `null` | `현재 링크를 열 수 없습니다` 표시 | URL은 있으나 최근 접근성 검사 실패 |
| `NOT_PROVIDED` | `null` | 링크 영역 숨김 | 공개 가능한 URL이 없음 |

Backend는 허용 목록에 등록된 공식 도메인만 검사하고, API 응답 요청 중 임의
외부 URL에 실시간 접속하지 않는다. 링크 상태는 적재·배치 또는 별도 검증
과정의 최근 결과를 사용한다. 검사 시각과 실패 상세는 운영 Metadata로
보존하되 P0 화면 필수 필드에는 포함하지 않는다.

| 근거 상황 | 화면 처리 | 업무 처리 |
| --- | --- | --- |
| 공식 근거 0건 | EvidenceCard 미표시 | `PENDING_CONSULTATION` 및 상담 전환 |
| 비공식·적용 범위 불일치 | 화면 공개 금지 | 근거 후보에서 제외 |

링크를 열 수 없다는 사실만으로 이미 Snapshot 검증된 근거 내용을 삭제하지는
않는다. 다만 링크가 공식 출처라는 표시를 유지할 수 있는지는 QA 재검증을
거친다.

## 7. 담당자별 책임과 검토 요청

### 7.1 이동윤 — 제안작성자·도메인 결정 책임자

- AI `EvidenceReference`와 검색 정책에 맞는 공개 후보를 제안한다.
- 공식 근거, 제품·세대 범위, 고객 안내 허용 여부를 정의한다.
- 검토 의견을 반영하여 `DOMAIN_APPROVED` 또는 `REVISE`를 기록한다.
- AI 응답은 후보만 반환하며 Backend 상태·권한·최종 저장을 변경하지 않는다.

### 7.2 최지용 — Backend 필수 검토

다음을 `REVIEWED` 또는 `CHANGE_REQUEST`로 회신한다.

- AI 필드와 `EvidenceLink` Snapshot, 화면용 `EvidenceCardDTO`의 매핑
- 역할·담당자 권한 Guard와 내부 필드 비노출 가능성
- 다중 `page_refs` 보존 방식
- `evidence_id`, `display_order`, 카드 최대 3개와 중복 방지
- 공식 URL 허용 목록, 비동기 검사, `link_status` 매핑
- 제목 300자·요약 500자 DTO 제약
- 근거 0건과 Vector DB 연결 실패를 구분할 수 있는지
- 문의 Snapshot의 `status_code`·`state_version`·`allowed_actions` 포함 여부를
  DEC-WEB-BE-002·005와 함께 확정할 수 있는지

### 7.3 한예나 — Web 필수 검토

다음을 `REVIEWED` 또는 `CHANGE_REQUEST`로 회신한다.

- 문서명·기관·버전·페이지·요약·링크의 화면 소비 가능성
- 링크 없음·접속 실패·근거 없음 상태의 UX
- 긴 제목·다중 페이지·복수 EvidenceCard 표시 방식
- `evidence_id` Key, `display_order`, 최대 3개 제한의 소비 가능성
- Web에서 검증 상태나 공개 가능 여부를 자체 계산하지 않는지

### 7.4 김은진 — Data·QA 필수 검토

다음을 `REVIEWED` 또는 `CHANGE_REQUEST`로 회신한다.

- 공식성·최신성·제품 적용 범위·Hash의 재현 검증 가능성
- 비공식 FAQ·충돌 자료·근거 0건의 차단 Test
- 개인정보·내부 ID·원문 과다 노출이 없는지
- URL 정상·없음·형식 오류·접속 실패의 E2E 검증 기준

### 7.5 윤승혁 — PM 최종 승인

필수 검토와 이동윤의 도메인 결정을 확인한 뒤 공개 범위, P0 포함 범위,
공용 계약 반영 여부를 `FINAL_APPROVED`, `HOLD`, `CHANGE_REQUEST` 중 하나로
판정한다.

## 8. 현재 확인된 계약 공백

| 항목 | 현재 상태 | 제안 후속 조치 | 소유자 |
| --- | --- | --- | --- |
| Backend `EvidenceCard` Schema | `properties: {}` 골격 | 검토 승인 후 DTO 필드 확정 | 최지용 |
| Backend Evidence Serializer | 골격만 존재 | DTO·권한·Fallback 구현 | 최지용 |
| 발행 기관 | Backend Snapshot에는 있으나 AI 계약에는 없음 | Backend SSOT 사용 또는 AI 계약 추가 여부 결정 | 이동윤·최지용 |
| 발행일·개정일 | 신뢰 가능한 날짜 필드 없음 | Data Owner가 값과 의미를 확정하기 전 공개하지 않음 | 김은진·이동윤 |
| 짧은 근거 요약 | 현재 Runtime은 AI `summary`에 `chunk.content`를 전달 | 승인 데이터의 `evidence_summary` 매핑 또는 Backend 검수 Snapshot 사용 | 이동윤·최지용 |
| 다중 페이지 | AI는 `page_refs`, Backend Snapshot은 대표 페이지 중심 | 손실 없는 DTO·저장 방식 확정 | 최지용 |
| 공개 ID·순서 | Backend `EvidenceLink.public_id`·`display_order`는 존재 | EvidenceCard에 `evidence_id`·`display_order`로 매핑 | 최지용 |
| 공통 검증 상태 Registry | `verification-statuses.yaml`이 비어 있음 | 기존 Enum의 공통 코드 편입 여부 결정 | 최지용·이동윤 |
| 공식 링크 접근성 | 정적 URL은 있으나 접근성 상태 저장·응답 계약 미확정 | 허용 도메인·검사 주기·`link_status` 저장 위치 확정 | 최지용·김은진 |
| 문의 상태 Snapshot | 기존 일부 응답에는 `status_code`·`state_version`·`allowed_actions`가 존재 | Evidence 소비 응답에도 포함하는 범위를 DEC-WEB-BE-002·005에서 확정 | 최지용·윤승혁 |

이 공백을 숨긴 채 현재 AI 응답을 그대로 화면 계약으로 확정하지 않는다.

## 9. 검토 후 착수 Gate

1. 최지용·한예나·김은진이 각각 `REVIEWED` 또는 `CHANGE_REQUEST`를 기록한다.
2. `CHANGE_REQUEST`가 있으면 이동윤이 반영 여부와 근거를 기록한다.
3. 이동윤이 최종 계약 문장을 `DOMAIN_APPROVED` 또는 `REVISE`로 판정한다.
4. 윤승혁 PM이 `FINAL_APPROVED`해야 Active 계약 작업을 시작한다.
5. 승인된 필드만 AI Schema·OpenAPI·Backend DTO 후보에 반영한다.
6. Contract Test 후 Backend Runtime, Web Adapter, QA·E2E 순으로 검증한다.

### 9.1 Web 상태 계산 금지 의존 조건

근거 유무에 따른 AI 안내 상태는 AI가 제안하지만 문의 업무 상태와
`allowed_actions`의 최종 계산은 Backend·State Machine 책임이다. Web은
EvidenceCard 배열이 비었다는 이유로 문의 상태나 가능한 Action을 계산하지
않는다.

실제 Evidence 소비 응답에는 Backend가 확정한 `status_code`, `state_version`,
`allowed_actions`를 포함해야 한다. 이 세 필드의 Enum·Action·전이 규칙은
DEC-WEB-BE-008에서 새로 정의하지 않고 DEC-WEB-BE-002·005 및 State 계약의
결정을 참조한다. 해당 계약이 확정되지 않으면 Web 실제 연동은 `HOLD`한다.

## 10. 담당자별 회신란

| 단계 | 담당자 | 현재 상태 | 회신 의견·필수 변경 | 담당자·일시 |
| --- | --- | --- | --- | --- |
| 제안작성 | 이동윤 | `PROPOSED` | Web 1차 변경 요청을 반영한 v0.2 재제출 | 이동윤 / 2026-08-04 |
| Backend 검토 | 최지용 | `NOT_REVIEWED` |  |  |
| Web 검토 | 한예나 | `NOT_REVIEWED` |  |  |
| Data·QA 검토 | 김은진 | `NOT_REVIEWED` |  |  |
| 도메인 결정 | 이동윤 | `NOT_REVIEWED` | 검토 반영 후 `DOMAIN_APPROVED` 또는 `REVISE` |  |
| PM 최종 승인 | 윤승혁 | `NOT_REVIEWED` | `FINAL_APPROVED`, `HOLD`, `CHANGE_REQUEST` |  |

### 10.1 1차 검토·개정 이력

| 단계 | 담당자 | 상태 | 판단과 반영 결과 | 일시 |
| --- | --- | --- | --- | --- |
| Web 1차 검토 | 한예나(Web) | `CHANGE_REQUEST` | Nullable, 다중 페이지, 링크 상태, 공개 ID·순서, 길이·개수, Backend 상태 Snapshot 확정 요청 | 2026-08-04 |
| 도메인 중간 판정 | 이동윤 | `REVISE` | 1~5번 수용. 6번은 Web 상태 계산 금지 원칙을 수용하되 DEC-WEB-BE-002·005·State 관할 의존 조건으로 분리 | 2026-08-04 |
| 제안 재작성 | 이동윤 | `PROPOSED` | 본 v0.2에 반영하고 세 필수 검토자에게 2차 검토 요청 | 2026-08-04 |

## 11. 검토자 전달 문구

안녕하세요. `DEC-WEB-BE-008` 공식 근거·문서 링크 공개 계약의 Web 1차
`CHANGE_REQUEST`를 반영한 v0.2 `PROPOSED` 초안을 전달드립니다.

- 최지용: Evidence DTO·권한·내부 필드 비노출·다중 페이지 매핑 검토
- 한예나: 요청한 Nullable·`page_refs`·`link_status`·공개 ID·순서·길이·개수
  반영 여부와 상태 Snapshot 의존 조건 재검토
- 김은진: 공식성·최신성·개인정보·링크·E2E 검증 가능성 검토
- 회신 상태: `REVIEWED` 또는 `CHANGE_REQUEST`

세 담당자의 회신을 반영한 뒤 이동윤이 `DOMAIN_APPROVED` 또는 `REVISE`로
판정하고, 윤승혁 PM의 `FINAL_APPROVED` 이후에만 공용 계약 반영을
요청하겠습니다.

## 12. 근거

- `contracts/ai/common/EvidenceReference.schema.json`
- `ai/app/schemas/retrieval.py`
- `ai/app/orchestration/stages/retrieval_stage.py`
- `data/config/rag/jac104_chunks.json`
- `contracts/api/components/schemas/evidence/EvidenceCard.yaml`
- `backend/apps/evidence/models/evidence_link.py`
- `contracts/codes/verification-statuses.yaml`

## 13. 문서 변경 기록

| 버전 | 날짜 | 변경 내용 | 상태 |
| --- | --- | --- | --- |
| v0.1 | 2026-08-03 | 최초 공개 필드·비공개 필드·Fallback 제안 | `PROPOSED` |
| v0.2 | 2026-08-04 | Web 1차 `CHANGE_REQUEST` 6개 항목 반영, 상태 Snapshot은 Backend·State 의존 조건으로 분리 | `PROPOSED` |

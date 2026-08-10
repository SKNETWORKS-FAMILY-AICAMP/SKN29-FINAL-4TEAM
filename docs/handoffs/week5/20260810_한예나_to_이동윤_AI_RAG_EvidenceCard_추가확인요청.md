# 한예나 → 이동윤: AI·RAG EvidenceCard 추가 확인 요청

## 1. 확인 완료

공개·비공개 항목과 화면 표시 원칙을 확인했습니다.

- AI 결과는 `AI 상담 요약 초안`으로 표시합니다.
- 공식 근거는 AI 초안과 분리해서 표시합니다.
- 근거가 없으면 상담 검토 필요 상태를 표시합니다.
- AI 또는 근거 조회 오류는 별도 오류로 표시합니다.
- `chunk_id`, 검색 점수, 원문, Prompt 등 내부 정보는 Web에 노출하지 않습니다.

Web에도 위 원칙은 반영되어 있습니다.

## 2. 추가 확인 요청

최종 EvidenceCard 화면 작업을 위해 아래 내용을 확인 부탁드립니다.

1. Web에 전달될 공식 EvidenceCard JSON 예시
2. 각 공개 필드의 필수 여부와 빈 값 가능 여부
3. `page_refs`의 정확한 형식
4. `verification_status`, `source_type`, `data_classification`에 들어올 수 있는 값
5. 근거 0건일 때의 FALLBACK 전체 응답 예시
6. 지원하지 않는 제품·세대가 들어왔을 때의 차단 응답 예시
7. AI `chunk_id`와 공개용 `evidence_id`의 연결 방식과 담당 범위
8. AI → Backend 전달 형식이 확정되는 예상 일정

## 3. 현재 Web 상태

- 내부 정보 차단 완료
- AI 초안 표시 완료
- 공식 근거 분리 표시 완료
- 근거 없음 상태 처리 완료
- AI·근거 오류 상태 처리 완료
- 현재 EvidenceCard는 공개 항목 일부만 지원

최종 DTO와 응답 예시가 전달되면 공개 필드 추가와 Mapper 작업을 진행하겠습니다.

Backend → Web 실제 API 연결과 E2E 검증은 Runtime API가 확정된 후 진행하겠습니다.

## 4. 답변 요청 형식

```text
evidence_card_json=<JSON 예시 또는 문서 경로>
required_nullable_fields=<필수·빈 값 가능 항목>
page_refs_format=<형식>
verification_status_values=<값 목록>
source_type_values=<값 목록>
data_classification_values=<값 목록>
fallback_example=<응답 예시 또는 문서 경로>
unsupported_product_example=<응답 예시 또는 문서 경로>
evidence_id_crosswalk=<연결 방식과 담당자>
ai_backend_contract_eta=<예상 일정>
notes=<추가 안내>
```

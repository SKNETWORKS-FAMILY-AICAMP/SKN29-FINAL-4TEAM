# 한예나 → 이동윤: AI·RAG EvidenceCard 확인 회신

## 1. 확인 결과

AI·RAG EvidenceCard 공개 형식과 필드 규칙을 확인했습니다.

확인·동의한 내용은 다음과 같습니다.

- `page_refs`는 정수 배열 전체를 보존합니다.
- AI 공식 EvidenceCard는 `official`만 표시합니다.
- `source_type`은 `official_manual`만 허용합니다.
- `verification_status`는 `text_and_visual_verified`만 허용합니다.
- `section_title`과 `source_landing_url`만 비어 있을 수 있습니다.
- 출처 링크는 HTTPS인 경우에만 표시합니다.
- 필수값이 없거나 알 수 없는 값이면 Card를 표시하지 않습니다.
- 근거가 0건이면 가짜 Card를 만들지 않고 상담 검토 필요 상태를 표시합니다.
- `chunk_id`, 검색 점수, 원문, Prompt, 내부 PK 등은 Web에 노출하지 않습니다.

## 2. Web 진행 예정 작업

1. EvidenceCard DTO에 전체 공개 필드 반영
2. `page_refs` 다중 페이지 표시
3. `evidence_summary`와 `verification_status`를 화면용 문구로 변환
4. 알 수 없는 값과 필수값 누락 시 표시 차단
5. 공식 근거와 AI 상담 요약 초안 분리 유지
6. 근거 없음 FALLBACK 화면 처리 유지

## 3. 협업 대기 항목

- Backend 최종 EvidenceCardDTO 확정
- `DocumentChunk.public_id` Crosswalk 완료
- 미지원 제품·세대의 HTTP Status와 오류 코드 확정
- Backend Runtime API 제공
- Backend → Web 실제 E2E 검증

현재 AI 공개 Projection은 Web Mock·Mapper 준비 기준으로만 사용하겠습니다.
실제 Runtime 계약 완료로 처리하지 않겠습니다.

AI 담당자에게 현재 추가로 요청할 작업은 없습니다.
Backend 계약이 확정되면 Joint Mock과 실제 응답 검증 일정에 함께 참여 부탁드립니다.

## 4. 전달 상태

```text
sender=한예나
receiver=이동윤
scope=AI_RAG_EVIDENCE_CARD

ai_public_projection=RECEIVED
field_rules=ACCEPTED
web_mock_mapper=READY_TO_UPDATE
multi_page_support=READY_TO_UPDATE
internal_field_exposure=BLOCKED
runtime_contract=WAITING_BACKEND
remote_api_connection=HOLD
backend_web_e2e=NOT_STARTED
notes=Backend 최종 DTO 확정 후 Web Mapper와 EvidenceCard 표시를 마무리하고 공동 검증 예정
```

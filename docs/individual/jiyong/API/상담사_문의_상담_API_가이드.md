# 상담사 문의·상담 API 구현 가이드

> 관련 업무: 상담사 Workspace·전화 문의·상담 처리

## 1. 기능 범위

- 배정 문의 목록·상세 조회
- 검색·필터·정렬·Pagination
- 역할·배정 기반 최소 Projection
- 상담사 전화 문의 등록
- 상담 시작·기록 저장·요약 확정·상담 완료
- 완료 후 동일 문의 재조회

## 2. 주요 경로

- `backend/apps/inquiries/**`
- `backend/apps/consultations/**`
- `contracts/api/paths/inquiries.yaml`
- `contracts/api/paths/consultations.yaml`
- `backend/tests/api/test_consultant_inquiry_runtime.py`
- `backend/tests/api/test_consultation_visit_runtime.py`

## 3. 조회 경계

- CONSULTANT 역할과 본인 배정을 모두 확인한다.
- 미배정 문의와 타 상담사 문의는 존재를 노출하지 않는다.
- 목록·상세에 `allowed_actions`와 최신 `state_version`을 제공한다.
- 내부 사용자 ID·전체 연락처·주소·AI 내부 Trace를 노출하지 않는다.
- `select_related`·`prefetch_related`로 Query 수 상한을 검증한다.

## 4. 전화 문의 등록

상담사가 승인된 합성 고객·구독을 선택해 문의와 최초 상태·이력·멱등 원장을
원자적으로 생성한다. 일반 고객 데이터나 임의 제품을 생성하지 않는다.

## 5. 상담 Write

```text
startConsultation
→ saveConsultationSummary
→ confirmConsultationSummary
→ completeConsultation
```

작성 중 기록과 확정 기록을 구분한다. 서버 자동저장·Draft 기능은 승인 없이
확대하지 않는다.

## 6. 검증

| 구간 | 확인 |
| --- | --- |
| 목록·상세 | 배정·Projection·Pagination·N+1 |
| 전화 문의 | 합성 고객·구독·Transaction·Replay |
| 상담 Write | 권한·상태·Version·History |
| 오류 | 403·404·409·422 |
| Rollback | 문의·상담·이력·멱등 원자성 |

## 7. 판정

실제 PostgreSQL과 HTTP에서 조회·등록·상담 흐름이 재현되면 Backend 구현
완료다. Web 화면 소비 완료는 한예나 담당 결과로 별도 판정한다.

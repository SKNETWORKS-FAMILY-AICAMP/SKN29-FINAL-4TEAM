# ADMIN-01 운영 대시보드 구현·연동 계획

- 담당: 한예나(Web)
- 화면 상태: P1 Mock 구현 완료
- 데이터 상태: 공식 합성 문의 24건 기반, 실제 운영 API 미연동
- 원칙: 계약 확정 전 실제 고객 정보·내부 문서 ID·검색 점수·프롬프트를 화면에 노출하지 않는다.

## 현재 구현 범위

| WBS | 구현 내용 | 화면 상태 |
| --- | --- | --- |
| T-101 | 기간, 제품 모델, 관리 유형, 담당자, 증상, 위험도, 문의 상태, 처리 결과 필터 | URL Query로 유지, 초기화 지원 |
| T-102 | 조회 문의, 위험 문의, 상담 전환, 방문 전환, 처리 완료 지표 및 증상·상태 분포 | 공식 합성 문의 ViewModel 집계 |
| T-103 | 케어 일정 미산정, 문진 미응답, 처리 지연, 근거 검색 실패, AI 실패 목록 | 문의별 복수 사유와 마지막 처리 단계 표시 |
| T-104 | 운영 화면 및 상담사 화면 반응형 | 1180/900/820/700/560/460px 구간 대응 |

개발 상태는 `?mockState=loading|empty|error`로 확인할 수 있다. 운영 화면은 `OPERATOR` 역할만 접근할 수 있다.

## API 교체 지점

실제 Backend 계약이 확정되면 `operationsDashboardModel.ts` 앞에 API Adapter를 추가하고, 현재 공식 합성 문의 입력만 API 응답 ViewModel로 교체한다. 화면 컴포넌트와 URL 필터 계약은 유지한다.

예상 조회 계약은 다음 필드를 포함해야 한다.

- 요청: `from`, `to`, `product_model`, `management_type`, `assignee`, `symptom_type`, `risk_level`, `status`, `result`
- 지표: 전체, 위험, 상담 전환, 방문 전환, 완료 건수
- 분포: 증상 유형별·문의 상태별 건수
- 예외: 문의 공개 식별자, 예외 코드 목록, 마지막 처리 단계, 담당자, 변경 시각
- 메타: `generated_at`, `correlation_id`

예외 상세 응답에는 내부 문서 ID, Chunk ID, 검색 원점수, 원문 전체, Prompt, Trace를 포함하지 않는다.

## 실제 연동 완료 조건

1. Backend/OpenAPI 운영 집계 계약 확정
2. 로딩·빈 상태·403·전체 오류·부분 실패 Fixture 확정
3. API Adapter 및 Mapper 연결
4. 실제 Backend 권한·필터·집계 E2E 통과

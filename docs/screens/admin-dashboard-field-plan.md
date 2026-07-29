# ADMIN-01 운영 대시보드 필드 계획

- 담당: 한예나(Web)
- 상태: P1 Placeholder 완료, 집계 API 계약 대기
- 원칙: 계약 전 임의 수치·내부 식별자·개인정보를 화면에 표시하지 않는다.

## 지표 계획

| 지표 | 정의 | 화면 필드 | 예상 API 필드 |
| --- | --- | --- | --- |
| 처리 지연 문의 | SLA 기준을 초과한 진행 중 문의 | 건수, 최장 대기 시간 | `delayed_count`, `max_wait_minutes` |
| 처리 오류 | 조회·AI·워크플로 처리 오류 | 오류 유형별 건수 | `error_counts[]` |
| 근거 부족 | 공개 가능한 공식 근거가 없는 문의 | 건수, 제품 모델 | `no_evidence_count`, `product_model` |
| 위험 문의 | 위험도 `danger`인 미완료 문의 | 건수, 상태별 분포 | `danger_count`, `status_counts[]` |

## 필터 계획

- 조회 기간: `from`, `to`
- 문의 상태: `status`
- 위험도: `risk_level`
- 담당 역할: `assigned_role`
- 제품 모델: `product_model`
- 집계 기준 시각: 응답의 `generated_at`으로 표시

## API 계약 요청안

`GET /api/v1/admin/operations/summary`를 후보로 두되 Backend/OpenAPI 확정 전에는 호출하지 않는다. 성공 응답은 `generated_at`, 지표 객체, 필터 선택지, `correlation_id`를 포함하고, 화면 Drill-down용 내부 ID·검색 점수·원문은 포함하지 않는다.

## 완료 조건

1. 운영 집계 기준과 역할별 공개 필드 확정
2. OpenAPI와 Backend Runtime 구현
3. 로딩·빈 상태·403·오류·부분 실패 Fixture 확보
4. Placeholder를 실제 API 화면으로 교체하고 OPERATOR Guard 통합 테스트 통과

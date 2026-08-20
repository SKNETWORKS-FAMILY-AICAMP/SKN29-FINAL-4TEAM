# WaterCare 데이터 상태 QA

## 현재 기준

- 데이터 버전: `1.1.0`
- 검증 기준 시각: `2026-07-29T00:00:00+09:00`
- 목표 상태: 데이터 QA `PASS`
- 금지 표시: `DB_VERIFIED`, Runtime 검증 완료

## 고정 검증 항목

| 항목 | 기대값 |
|---|---:|
| 원본 시나리오 | 24 |
| 활성 projection | 22 |
| 차단 시나리오 | 2 |
| Inquiry | 22 |
| Consultation | 12 |
| Visit | 4 |
| CustomerProfile | 12 |
| 통합 상태이력 | 125 |
| Audit | 125 |
| subset | 7파일·33건 |
| API 멱등성 사례 | 3 |

QA는 대상 FK exactly-one, 대상별 상태 집합, 연속 `state_version`, 상태이력·Audit 대응, 멱등키 공유, 3계층 식별자, CustomerProfile 관계, Backend PK 직접 주입 금지, Care 미확정 mapping 제외를 검사합니다.

`SYN-JAC104-012`, `SYN-JAC104-016`은 계속 `BLOCKED_DECISION`입니다. `PRODUCT_VALIDATION_FAILED`는 Inquiry 상태 fixture로 생성하지 않습니다.

실제 PASS·오류·경고 수치는 `latest_qa_summary.json`과 5개 상세 리포트에서 확인합니다. 이 문서는 테스트 실행 전부터 PASS를 선기록하지 않습니다.

# WaterCare 데이터 처리 명세

## 기준

- 데이터 버전: `0.9.0`
- 생성 기준 시각: `2026-07-29T00:00:00+09:00`
- 공식 문서: WPU-JAC104D·WPU-JCC104D REV.00 44페이지
- 시간 표현: ISO 8601, `+09:00`
- 데이터 분류: `official`, `team_designed`, `synthetic`

## 생성 규모

| 데이터 | 건수 |
|---|---:|
| 매뉴얼 페이지 | 44 |
| FAQ 정규화 | 119 |
| OCR 검증 FAQ | 5 |
| 공식 FAQ 이미지 자산 | 10 |
| MVP RAG chunk | 7 |
| 근거 registry | 9 |
| 합성 사용자 | 16 |
| CustomerProfile | 12 |
| 원본 시나리오 | 24 |
| 활성 Inquiry | 22 |
| Consultation | 12 |
| Visit | 4 |
| 통합 상태이력 | 125 |
| Audit | 125 |
| subset | 7파일·33건 |
| API 멱등성 사례 | 3 |

## 생성·검증 규칙

1. `config/**`를 선언적 입력으로 사용해 `processed/**`, `synthetic/**`를 생성합니다.
2. `SYN-JAC104-012`, `SYN-JAC104-016`은 원본과 `BLOCKED_DECISION` 기록을 보존하되 활성 projection에서 제외합니다.
3. 복합 방문 이벤트는 Inquiry와 Visit 상태이력을 분리하며 같은 `idempotency_key`, `correlation_id`를 공유합니다.
4. 상태이력과 Audit은 대상·이벤트·버전·요청 키·상관 ID·시각이 1:1로 대응해야 합니다.
5. CustomerProfile은 User와 1:1이며 Subscription은 CustomerProfile과 CustomerProduct를 함께 참조합니다.
6. Backend import는 `public_id` 또는 업무키 lookup 후 실제 DB FK를 사용합니다. Fixture PK 직접 주입은 금지합니다.
7. 미확정 Care mapping은 `BLOCKED_OWNER_CONFIRMATION`으로 load 후보에서 제외합니다.
8. `PRODUCT_VALIDATION_FAILED`는 이벤트와 `CONSULTATION_REQUIRED` 기대 전환만 유지하고 Inquiry 상태로 생성하지 않습니다.
9. 상세 QA 리포트 5종과 summary는 같은 version·generated_at을 사용하며 summary는 실제 리포트 SHA-256을 기록합니다.

이 산출물은 데이터 QA `PASS`까지만 주장합니다. Backend import와 Runtime 검증은 완료되지 않았습니다.

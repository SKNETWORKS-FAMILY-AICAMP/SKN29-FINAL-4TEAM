# WaterCare 데이터 처리 명세

## 기준

- 데이터 버전: `1.1.0`
- 생성 기준 시각: `2026-07-29T00:00:00+09:00`
- 공식 문서: JAC104D 공동 매뉴얼 44쪽, IAC425 52쪽, IAC606 48쪽
- 시간 표현: ISO 8601, `+09:00`
- 데이터 분류: `official`, `team_designed`, `synthetic`

## 생성 규모

| 데이터 | 건수 |
|---|---:|
| 매뉴얼 페이지 | 144(`REFERENCE_ONLY`) |
| 지원 판매코드 | 3 |
| RAG Parent | 15(`CONTEXT_ONLY`) |
| RAG Child | 53(`INGEST_CANDIDATE`) |
| Evidence Group | 43 |
| RAG 평가 초안 | 50(양성 43·부정 7) |
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
| 합성 fixture 총계 | 369 |

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
10. RAG 확장 검색은 `exact_sales_code`를 점수 계산 전에 필수 적용하며 다른 모델 fallback을 허용하지 않습니다.
11. Parent는 답변 문맥 확장에만 사용하고 검색 후보는 행 단위 Child로 제한합니다.
12. 모델 미검증 FAQ와 WPU-IAC506, 정확 판매코드 미검증 JCC104(D)는 확장 코퍼스에 포함하지 않습니다.
13. 신규 제품 2건은 `RAG_READY_CONTRACT_BLOCKED`이며 기존 Backend handoff에서는 `LOAD_FILTERED`로 제외합니다.

확장 산출물은 데이터 QA `PASS`까지만 주장합니다. pgvector 적재·검색 성능과 신규 모델 Runtime 활성화는 검증되지 않았습니다.

# T-005 DB / T-006 AI 계약 정합성 검토

> 기준일: 2026-07-27
> T-005·DB 기준 담당: 최지용
> 판정: DB 기준 확정, AI Schema 부분 반영·Adapter 매핑 정합화 필요

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | T-005 DB·API 기준 확정, T-006 AI Schema 부분 반영·남은 매핑 추적 |
| 관련 WBS | `T-005`, `T-006` |
| 작성·유지 책임 | 최지용 |
| 산출물/내용 의사결정자 | 최지용: T-005 DB·API 필드·Enum·Django·PostgreSQL 기준. 이동윤: T-006 AI Schema 내용(경로 관할 기준). 윤승혁(PM): 교차 영역 충돌 시 통합 결정 |
| 협업 책임 | 이동윤: AI Schema 구현, 최지용: DB↔API↔AI 매핑 재검증, 김은진: Contract QA, 윤승혁(PM): 교차 영역 통합 |
| 검토 요청 대상 | 이동윤, 김은진, 윤승혁(PM) |
| 검토 상태 | 미요청 또는 증거 미확인 |
| PR 병합 담당 | 윤승혁(PM), 비작성자 1명 이상 리뷰 후 |
| 인계 대상 | 이동윤, 최지용, 김은진, 윤승혁(PM) |

T-006의 WBS 담당 이름은 기준 지침서에 직접 적혀 있지 않으므로,
`contracts/ai/**` 주관할에 따라 이동윤을 AI Schema 내용 책임자로
표기한다. 위 검토는 최지용의 T-005 DB·API·Django·PostgreSQL
작성이나 구현을 시작하기 위한 선행 승인이 아니다. 확정 DB 기준의
AI 소비 호환성과 Contract 검증, 교차 영역 충돌만 확인한다.

## 1. 검토 원본

- [T-005 데이터 설계 기준선](../../../../database/t-005/README.md)
- [T-005 결정 등록부](../../../../database/t-005/t005_decision_register_v0.1.json)
- [T-005 물리 계약](../../../../database/t-005/t005_physical_contract_v1.0.json)
- [사용 안내 상태 코드](../../../../../contracts/codes/usage-guidance-statuses.yaml)
- [위험도 코드](../../../../../contracts/codes/risk-levels.yaml)
- [UsageGuidance AI Schema](../../../../../contracts/ai/common/UsageGuidance.schema.json)
- [SafetyAssessment AI Schema](../../../../../contracts/ai/common/SafetyAssessment.schema.json)
- [SymptomAnalysisResponse AI Schema](../../../../../contracts/ai/responses/SymptomAnalysisResponse.schema.json)

현행 Runtime·계약 원본은 `backend/**`와 `contracts/**`다. 루트
`WaterCareBackend/**`는 구형 starter 참고본이며 DB↔AI 필드·Enum
정합성 판정에 사용하지 않는다.

## 2. 확정된 DB·API 기준

| 항목 | 확정 기준 |
| --- | --- |
| Canonical 필드 | `usage_guidance_status` |
| 사용 안내 코드 | `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION` |
| Legacy 변환 | `USE_ALLOWED` → `NORMAL` |
| Legacy 저장 | `usage_guidance_code` Dual-write 금지 |
| 위험도 | `general`, `caution`, `danger` |
| 운영 방식 | 계약 YAML과 Django `TextChoices` 일치 |

위 기준은 최지용 T-005 확정 산출물이며 T-006 AI Schema의 입력으로
사용한다.

## 3. 최신 정합성 결과

| 검수 항목 | 현재 결과 | 판정 |
| --- | --- | --- |
| 사용 안내 공통 코드 | 4개 값 존재 | 통과 |
| Legacy 변환 | `USE_ALLOWED: NORMAL` 존재 | 통과 |
| DB Canonical 명칭 | `usage_guidance_status`로 확정 | 통과 |
| 위험도 공통 코드 | 3개 값 존재 | 통과 |
| `UsageGuidance` 사용 안내 Enum | 4개 값이 공통 코드와 일치 | 통과 |
| `UsageGuidance` 필드명 | `guidance_status`, `message`, `next_actions` 사용 | DB/API canonical 이름과 매핑 필요 |
| `UsageGuidance` 필수 의미 | `evidence`, `requires_consultation`이 해당 객체에 없음 | 위치·Adapter 규칙 정합화 필요 |
| `SafetyAssessment` | 5개 필수 필드, 위험도 3개 값 존재 | 위험도 Enum 통과 |
| `SymptomAnalysisResponse` | 핵심 6개 필수 필드와 공통 Schema `$ref` 존재 | 부분 반영 |
| 남은 공통·업무 Schema | 9개 object Schema의 `properties`가 아직 비어 있음 | T-006 후속 반영 필요 |

과거 문서의 “사용 안내 코드가 비어 있음”, “DB·AI 명칭이 미결정”은
현재 사실과 다르므로 폐기한다. AI Schema는 더 이상 전체가 빈
Placeholder가 아니다. 남은 문제는 확정 DB·API canonical 이름과 AI
필드의 명시적 매핑, 비어 있는 후속 Schema와 실패·Fallback Fixture다.

## 4. T-006 반영 기준

T-006 담당자와 Backend 담당자는 다음 경계를 순서대로 맞춘다.

1. 이동윤이 `guidance_status`와 `usage_guidance_status`,
   `message`와 `usage_guidance_message`, `next_actions`와
   `next_action` 중 AI Schema의 canonical 이름·Shape를 명시한다.
2. `evidence_references`와 DB/API `evidence`, Safety의
   `requires_consultation`과 사용 안내 저장 필드 사이의 Adapter 규칙을
   정한다.
3. 아직 비어 있는 공통·Request·Response Schema는 실제 소비되는
   것부터 필수 필드, nullability와 `additionalProperties` 정책을
   채운다.
4. 정상·누락·위험·근거 없음·Timeout·Fallback Fixture를 만들고 잘못된
   AI 출력은 Schema 검증 실패로 처리한다.
5. 최지용은 확정된 AI 입력을 DB·API Adapter에 반영하고 이름·Enum·
   실패 응답 diff를 재검증한다.

AI Schema가 반영되면 최지용은 DB·API 필드명과 Enum 매핑을 다시
대조해 서비스 간 계약 정합성을 검증한다.

## 5. 검증 경계

현재 변경의 Backend 전체 회귀는 `239 passed`다.
이 수치는 현재 Branch 결과나 AI Schema 완료 증거가 아니다. T-006
완료는 AI Schema 자체 검증과 정상·누락·위험·근거 없음·Timeout·
Fallback Fixture를 별도로 통과해야 한다.

## 6. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 이동윤 | 확정 `usage_guidance_status`, 4개 안내 코드, 3개 위험도, 현재 AI Schema 차이 | AI canonical 필드·객체 위치를 명시하고 남은 빈 Schema와 실패·Fallback Fixture를 구현 | AI Schema 자체 검증과 정상·누락·위험·근거 없음·Timeout·Fallback Fixture 통과 | 핵심 Schema 부분 반영, 이름·Fallback 정합화 필요 |
| 최지용 | 이동윤이 확정한 AI Schema와 Fixture | DB·API 필드명·Enum·Adapter 매핑을 다시 대조 | DB↔API↔AI 이름·Enum diff 0건 또는 명시적 Adapter 규칙 | T-005 독립 진행, AI 입력 정합화 후 교차검증 |
| 김은진 | T-005 기준, T-006 Schema, 정상·오류 Fixture와 검증 명령 | Contract·Backend↔AI 통합 QA 실행 | 재현 가능한 테스트 결과와 불일치 0건 또는 결함 기록 | 검토 미요청 또는 증거 미확인 |
| 윤승혁(PM) | DB·API와 AI 간 해결되지 않은 교차 영역 충돌 및 영향 | 충돌이 있을 때만 기준 원본과 담당 영역을 지정해 통합 결정 | 결정 기록이 계약과 구현에 반영 | 현재 충돌 검토 요청 없음 |

DB·API에서 사용할 필드명과 코드값은 확정됐다. T-006은 새 후보
코드로 바꾸지 않고 이를 소비한다. DB Snapshot의 과거
`usage_guidance_code`는 이력이며 신규 구현 기준으로 사용하지 않는다.

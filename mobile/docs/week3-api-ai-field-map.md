# 3주차 API 및 AI 필드 대응표

## CUST-01 고객 홈

| 화면 표시 항목 | 모바일/API 데이터 출처 |
| --- | --- |
| 고객 정보 | 데모 로그인으로 인증된 사용자 정보 |
| 제품 및 모델 요약 | 고객 홈 Repository 응답 |
| 구독 및 관리 유형 | 구독 정보 또는 제품 요약 정보 |
| 진행 중 문의 코드 | 고객에게 표시하는 문의 코드 |
| 진행 중 문의 식별자 | 외부 공개용 문의 UUID |
| 사용 가능한 기능 | 백엔드 상태와 허용된 화면 이동 경로 |

## CUST-02 증상 입력

| 화면 입력 항목 | 요청 및 모델 필드 |
| --- | --- |
| 진입 유형 | `entryMode` |
| 복수 증상 선택 | 증상 선택값 또는 증상 코드 |
| 고객 원문 | `rawText` |
| 발생 조건 | `occurrenceCondition` |
| 화면 표시 및 오류 문구 | `displayText` |
| 중복 제출 방지 | 제출 중 상태와 요청 차단 로직 |
| 충돌 복구 | 현재 상태, 상태 버전, 허용 동작 |

## CUST-04 AI 안내

| 화면 구역 | 응답 및 표시 필드 |
| --- | --- |
| 위험도 | `riskLevel` |
| 사용 상태 | `usageStatus` |
| 사용 상태 설명 | `usageMessage` |
| 제한 기능 | `restrictedFunctions` |
| 안전 행동 | `safeActions` |
| 상담 전환 조건 | `escalationConditions` |
| 금지 행동 | `prohibitedActions` |
| 다음 행동 | `nextAction` |
| 상담 필요 여부 | `requiresConsultation` |
| 공식 근거 | 외부 공개가 허용된 근거 메타데이터 |
| 화면 동작 버튼 | `allowedActions`와 위험·근거 없음 안전 필터링 결과 |

## 외부에 노출하지 않는 항목

- 내부 정수형 기본키
- JWT Access Token 및 Refresh Token
- `chunk_id`
- 원본 저장 경로
- 검색 점수와 검색 원문
- 내부 문서 URL

# 상담 Handoff v2 로컬 보호 HTTP E2E 결과보고서

## 1. 판정

- 실행일: 2026-08-28
- 실행자: 최지용
- 기준 Commit: `95f90f843124373fc97c6cd9e258b1427e0cbde8`
- 코드 기준: `origin/main`
- 보호형 AI→Backend Handoff v2: `PASS`
- 전체 서비스 E2E: `PARTIAL`
- Web UI: `NOT_RUN`
- 실제 Provider: `NOT_RUN`
- AWS: `NOT_RUN`
- 운영 활성화: `HOLD`
- 독립 QA·PM 승인: `PENDING`

보호토큰을 적용한 실제 AI Process와 Backend가 같은 신규 합성 문의를 처리했고,
상담 이관 저장, 상태 전이, 상담사 조회, 멱등 Replay까지 통과했다. 다만 Web 화면,
실제 Provider, AWS를 실행하지 않았으므로 전체 서비스 또는 운영 완료로 판정하지 않는다.

## 2. 변경 범위

- Handoff 실행 코드는 현재 `main`에 이미 포함되어 있어 소스 코드는 수정하지 않았다.
- 기존 개발 가이드에 보호형 HTTP E2E 결과와 남은 Gate를 반영했다.
- 이 문서를 실행 증거 요약으로 추가했다.
- 기존 `jiyong` 작업 중인 관리자 기능 파일은 수정하거나 검증 Commit에 포함하지 않는다.

## 3. 실행 환경과 안전 경계

| 항목 | 적용 내용 |
| --- | --- |
| Backend | `http://127.0.0.1:18000`, Health 200 |
| AI | `http://127.0.0.1:8001`, 실제 FastAPI·MCP Runtime |
| DB | 로컬 Docker PostgreSQL 16·pgvector |
| 시험 데이터 | 신규 합성 고객·구독·문의 1건 |
| 보호 | AI와 Backend에 동일 보호토큰을 Process 환경으로 주입 |
| 기능 활성화 | 시험 AI Process에만 활성화 |
| 외부 Provider | API Key 제거, 호출하지 않음 |
| Telemetry | 시험 Process에서 비활성화 |
| 종료 | 검증 후 AI Process 종료, 운영 기본값 미변경 |

토큰, 고객 입력 본문, Prompt, Evidence 본문은 출력하거나 보고서에 기록하지 않았다.

## 4. 동일 문의 식별자

- Inquiry ID: `f73006db-5fa7-402c-ab60-61d2ece7dcb4`
- Correlation ID: `4d4aa464-2233-463f-9a6a-544a053c70c4`
- Model: `WPUJAC104DWH`
- Data Classification: `synthetic`

실행 전 문의는 `DRAFT`, 상태 버전 1이었고 AI Run, Handoff, Consultation은 모두
0건이었다. 완료된 기존 Fixture를 되돌리지 않고 신규 문의만 사용했다.

## 5. 보호형 HTTP 실행 결과

| 검증 항목 | 기대값 | 실제 결과 | 판정 |
| --- | --- | --- | --- |
| Backend→AI 분석 | HTTP 200 | HTTP 200 | PASS |
| 요청·응답 Correlation | 동일 | 동일 | PASS |
| 공개 응답 내부 Handoff 노출 | 없음 | 없음 | PASS |
| AI 분석 결과 | Fallback | `FALLBACK` | PASS |
| AI Run 상태 | 근거 없음 | `NO_EVIDENCE` | PASS |
| 문의 상태 | 상담 필요 | `CONSULTATION_REQUIRED` | PASS |
| 분석 후 상태 버전 | 3 | 3 | PASS |
| Handoff 전송 | 성공 | `DELIVERED`, Retry 0 | PASS |
| Handoff Schema | v2 | `2.0.0` | PASS |
| Routing | 안전 종료 상담 | `FAIL_CLOSED_CONSULTATION` | PASS |
| Escalation | 근거 없음 | `NO_EVIDENCE` | PASS |
| Evidence | 0건 | 0건 | PASS |
| Handoff 저장 | 정확히 1건 | 1건 | PASS |
| 식별자 결속 | AI Run과 동일 | Request·Correlation 동일 | PASS |
| 금지 정보 | 미포함 | 미포함 | PASS |

상담 맥락정리는 외부 Provider 설정을 제거한 시험 Process에서 결정론적 Fallback으로
생성되었다. 결과 상태는 `FALLBACK`, 사유는 `CONFIGURATION`이며 Handoff 전송과 저장을
막지 않았다.

## 6. 고객 상담·상담사 Projection 결과

| 검증 항목 | 실제 결과 | 판정 |
| --- | --- | --- |
| 고객 상담 요청 | HTTP 200, 상태 버전 4 | PASS |
| 기존 Handoff와 Consultation 연결 | 동일 상담 건으로 연결 | PASS |
| 상담사 Claim | HTTP 200, 상태 버전 5 | PASS |
| 배정 결과 | 합성 상담사, `ASSIGNED` | PASS |
| 상담사 상세 API | HTTP 200 | PASS |
| AI 초안 요약 | Handoff 원장과 동일, 비어 있지 않음 | PASS |
| 내부 Trace·Prompt·오류 정보 | 공개 응답에 없음 | PASS |

최종 DB는 AI Run 1건, Handoff 1건, Consultation 1건이며 Handoff와 Consultation이
같은 문의로 결속되었다. 문의 상태는 상담 필요, 배정 역할은 상담사다.

## 7. Replay 결과

- 저장된 동일 Handoff v2 Payload와 동일 식별자를 다시 전송했다.
- HTTP 200과 `idempotent_replay=true`를 확인했다.
- 최초 Handoff ID와 Replay 응답 ID가 동일했다.
- Replay 전후 Handoff 행은 1건으로 유지되었다.

판정: `PASS`

## 8. 회귀 테스트

| 테스트 묶음 | 결과 |
| --- | --- |
| AI Handoff Client·Background Delivery·HTTP Delivery | 20 passed |
| Backend Handoff API·Backend/Web Bridge·Live Socket E2E | 19 passed, 2 skipped |

Backend의 2건 Skip은 SQLite 실행에서 제외되는 PostgreSQL 행 잠금 전용 테스트다.
이번 보호형 E2E는 실제 로컬 PostgreSQL에 저장했지만 동시성 행 잠금 Gate를 다시
수행한 것은 아니므로 Skip을 PASS로 바꾸어 표현하지 않는다.

## 9. 확인된 제한

- 기존 5건 Fixture는 이미 사용되어 상태 버전이 2~3이므로, 상태 버전 1을 요구하는
  기존 로컬 환경 로더의 5건 사전검사를 그대로 재사용할 수 없다.
- 이번 실행은 신규 문의의 식별자, 상태 버전 1, 초기 원장 0건을 별도로 확인한 뒤
  보호 환경을 Process 단위로 불러와 수행했다.
- 이 제한은 Handoff 실행 코드 누락이 아니라 시험 Fixture 수명주기 문제다.
- 다음 실행도 완료 Fixture를 되돌리지 말고 신규 합성 문의를 생성해야 한다.

## 10. 후속 Gate

1. 윤승혁(PM)이 보호형 HTTP Handoff v2 Gate 결과를 확인한다.
2. 필요하면 독립 QA가 신규 합성 문의로 같은 경로를 재검증한다.
3. 실제 Provider Canary는 별도 승인 데이터와 별도 실행 증거로 검증한다.
4. Web UI 상담사 화면을 실행해 전체 서비스 E2E 상태를 갱신한다.
5. AWS 검증은 배포 Commit·보호토큰·시험 Process 설정을 확인한 뒤 별도로 수행한다.
6. 모든 Gate 전까지 운영 기본 활성화는 보류한다.

## 11. 최종 요약

```text
protected_http_handoff_v2=PASS
same_inquiry_binding=PASS
airun_no_evidence=PASS
handoff_exactly_once=PASS
consultation_link=PASS
consultant_api_projection=PASS
idempotent_replay=PASS
secret_and_internal_data_exposure=PASS
provider_canary=NOT_RUN
web_ui_status=NOT_RUN
aws_status=NOT_RUN
independent_qa=PENDING
pm_approval=PENDING
operation_activation=HOLD
overall_service_e2e=PARTIAL
```

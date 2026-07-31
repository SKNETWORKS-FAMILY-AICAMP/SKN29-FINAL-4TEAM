# Backend 구조화 로그 민감정보 비노출 감사

> 기준일: 2026-07-31
> 작성·검증 책임: 최지용
> 협업 검토: 김은진(Data·QA·DevOps)
> 판정: **현재 Request·Exception 로그 경로 PASS / T-024 전체 추적성 구현은 별도**

## 1. 감사 범위

이번 감사는 현재 Backend가 실제 호출하는 Request·Exception 로그만
대상으로 한다.

- [요청 로그 Middleware](../../../../../backend/common/middleware/request_logging.py)
- [JSON Formatter](../../../../../backend/common/logging/formatter.py)
- [Request Context Filter](../../../../../backend/common/logging/filters.py)
- [전역 예외 Handler](../../../../../backend/common/exceptions/handler.py)
- [Logging 설정](../../../../../backend/config/settings/base.py)

AI 호출·RAG 검색·계정 변경·업무 행위 전체를 저장하는 T-024 구현 완료를
이 문서로 주장하지 않는다.

## 2. 현재 안전 설계

현재 Request 로그는 민감값을 마스킹한 뒤 기록하는 방식이 아니라,
처음부터 안전한 필드만 허용하는 Allowlist 방식이다.

| 로그 필드 | 기록 여부 | 안전 기준 |
| --- | --- | --- |
| HTTP Method | 기록 | `GET`, `POST` 등 |
| Route Template | 기록 | 실제 Query String이 아닌 Resolver Route |
| Status Code | 기록 | 숫자 상태 코드 |
| Duration | 기록 | 처리 시간 |
| Correlation ID | 기록 | 요청 추적 UUID |
| Query String | 미기록 | Token·검색 원문 유출 방지 |
| Authorization Header | 미기록 | Access Token 유출 방지 |
| Cookie | 미기록 | Session·CSRF 정보 유출 방지 |
| Request Body | 미기록 | Password·전화번호·고객 원문 유출 방지 |
| Response Body | 미기록 | 개인정보·Token Projection 유출 방지 |
| Exception Message·Stack | JSON에서 미기록 | 고객 입력·내부 경로 유출 방지 |
| Exception Type | 기록 | 오류 분류만 기록 |

Formatter는 정해진 필드만 JSON에 넣는다. `extra`에 임의 객체가 들어와도
Formatter Allowlist 밖의 값은 출력하지 않는다. 현재 저장소에서 실제
`logger.*` 호출은 Request Logging Middleware와 전역 예외 Handler 두
경로뿐이며, 두 경로 모두 Request·Response Payload를 전달하지 않는다.

## 3. 검증

저장소 루트에서 다음을 실행했다.

```powershell
& .\backend\.venv\Scripts\python.exe -B -m pytest `
  .\backend\tests\unit\common\test_request_logging.py `
  .\backend\tests\unit\common\test_logging.py `
  .\backend\tests\unit\common\test_correlation_id.py `
  -q `
  -p no:cacheprovider
```

결과:

| 항목 | 결과 |
| --- | --- |
| 테스트 | `14 passed` |
| Query Secret 비노출 | PASS |
| Bearer Token 비노출 | PASS |
| Cookie Secret 비노출 | PASS |
| Password Body 비노출 | PASS |
| Exception Message 비노출 | PASS |
| Stack Trace 비노출 | PASS |
| Route Template·Correlation ID | PASS |

## 4. 남은 경계

[마스킹 유틸리티](../../../../../backend/common/utils/masking.py)는 현재
모듈 설명만 있고 실제 변환 함수가 없다. 하지만 현재 로그 경로는 원문을
기록하지 않는 Allowlist 구조이므로 이 사실만으로 민감정보가 노출되지는
않는다.

향후 T-024에서 AI·RAG·업무 감사 로그를 추가할 때는 다음 규칙을 지킨다.

1. 고객 원문, AI Prompt, 전화번호, 주소, Password, Token, Cookie를
   로그 인자로 넘기지 않는다.
2. 모델 입력 전체 대신 업무 식별자, 모델 버전, 안전한 상태 코드,
   처리 시간과 Correlation ID만 기록한다.
3. 꼭 필요한 부분 값은 명시적 마스킹 함수와 전용 테스트를 먼저 만든다.
4. 파일 경로·DSN·환경변수 전체를 오류 로그에 넣지 않는다.
5. 계정 변경 감사 이력은 일반 Request 로그와 분리하고 비밀번호·Token을
   전후값에 포함하지 않는다.
6. 새 `logger.*` 호출을 추가하면 비노출 회귀 테스트를 같은 Commit에
   추가한다.

## 5. 인계

| 담당 | 다음 행동 | 완료 증거 |
| --- | --- | --- |
| 최지용 | 새 Backend 로그마다 Allowlist·비노출 테스트 유지 | 관련 단위 테스트와 전체 회귀 |
| 김은진 | 다른 OS·통합 환경에서 JSON 로그 샘플 검토 | Token·PII·고객 원문 0건 |
| 이동윤 | AI Runtime 로그의 허용 Metadata와 금지 Payload 반환 | Model·Prompt·Evidence 로그 경계 |
| 윤승혁 PM | T-024 착수 시 업무 감사 범위와 보존 정책 확정 | 결정 문서·WBS 상태 |

현재 Request·Exception 로그의 민감정보 비노출은 로컬 기술 검증을
통과했다. T-024 추적성·AI·RAG·계정 변경 감사 전체는 아직 구현되지
않았으며 별도 작업·리뷰 없이 완료로 표기하지 않는다.

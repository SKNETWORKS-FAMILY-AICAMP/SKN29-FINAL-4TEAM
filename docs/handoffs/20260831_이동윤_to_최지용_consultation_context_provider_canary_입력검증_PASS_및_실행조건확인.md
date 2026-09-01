# Consultation Context Provider Canary 사전 확인 및 실행 보류

- 확인일: 2026-08-31 21:20 KST
- 발신: 이동윤(AI·RAG)
- 수신: 최지용(Backend), 참조 윤승혁(Handoff)
- 판정: **AWS 원본 입력 결속 PASS / Execute는 HOLD·NOT_RUN**
- 이 문서는 Execute 보고서가 아닙니다. 실제 맥락정리 Provider·Handoff·Replay 호출은 모두 0회입니다.

## 확인한 결과

브라우저 SSM에서 AWS 보호 입력의 본문을 출력하지 않고 메타데이터와 Hash만 확인했습니다.
기존 운영 AI 컨테이너의 Python 3.13.13으로 입력을 읽기 전용 검사했습니다.

- 파일 크기 11,379바이트, 소유자 ubuntu, 권한 600.
- 원본 파일 SHA-256 및 Runner 정규화 입력 Hash:
  `e2847f81e6690f8a978dec8fa385290b5e2afcd20e78fb5406e6131b7bf9d4c5`
- Runner Evidence 결속 Hash:
  `f33102c7be550173c0a0109d7d5e652c34a6dd96d497c3bc9a9a6c5119d91f60`
- 두 Hash 및 Inquiry·Correlation·AI Request·Review·Version·Checkpoint 모두 인계와 일치.
- Evidence 5건은 모두 Canonical JAC104 D세대 Child. 공식 검증·사용 허용·Runtime 적격 조건 충족.
  각 근거의 본문 SHA-256·원문 파일 SHA-256·페이지도 Canonical과 일치.
- 운영 Release ce22601bf4f21b0c11d7626fb3bd1b905464d1da,
  Container 43fd908192b3525948b2faa717774ae64f35875dc551790e0d3601908e5b59e3, healthy.
- 로컬 Runner 표적 단위 테스트: 13 PASS / exit 0. Fake Provider 테스트이며 실제 호출 증거가 아님.

이 검사는 **AWS 원본 Host**에서 수행했습니다. 보호 Host로 전송한 뒤의 검증으로
대체하지 않으며, 최신 Backend 원장·Review 상태를 다시 조회한 것도 아닙니다.

## Execute 전에 필요한 두 가지

1. **보호 Host와 SCP/SFTP 경로**
   이번 문서에는 AWS 원본 경로만 있고 수신 Host·접속 별칭·저장 경로가 없습니다.
   현재 PC인지 별도 서버인지 확인이 필요합니다. 입력 원문이나 인증키를 채팅으로
   전달하지 않고 승인된 경로를 확정한 뒤 전송해야 합니다.

2. **Handoff 내부 재전송 정책**
   현재 `ai/app/integrations/backend/handoff_client.py:36`은
   `MAX_ATTEMPTS=2`이며 Timeout·네트워크 오류와 일부 HTTP 오류에 자동 재전송 1회가 있습니다.
   이는 Runner 전체 재실행이나 성공 Payload의 명시적 Replay와는 다른 동작입니다.
   요청의 “불명확하면 즉시 중단”이 이 내부 재전송도 금지하는지 확정해야 합니다.
   엄격한 최초 오류 중단이 필요하면 윤승혁 주관할의 승인된 1회 전송 실행 방식을
   준비한 뒤 실행합니다. 공유 Handoff 코드를 임의 수정하거나 동작을 우회하지 않았습니다.

## Clean Runner 및 재개 조건

현재 로컬 HEAD는 `521c1d1d0a372ad29dc7ff627b195dfd1a8666c8`이며 다른 작업의 변경이
있습니다. 이를 지우거나 Clean으로 허위 기록하지 않았습니다. 보호 Host 확정 후
별도 Clean Checkout에서 실행 Commit을 고정해야 합니다.

전송 후 파일 크기·원본 Hash·두 Runner Hash를 재확인하고 Inspect를 수행합니다.
Execute 보고서는 보호 경로의 **새 파일**로 지정하고, Provider 호출 전에 해당 경로의
중복·쓰기 가능 여부를 확인합니다. 현재 Runner는 보고서 쓰기를 외부 호출 뒤 수행하므로
기존 파일을 지정한 채 실행해서는 안 됩니다.

조건이 확정되면 동일 입력으로 맥락정리 Provider 1회, 성공한 동일 실행에서 최초
Handoff와 같은 Payload Replay만 진행합니다. 실패·불명확 결과에는 자동 재실행하지 않습니다.

이번에는 파일 전송·신규 문의·Provider·Backend Write·배포·운영 환경 수정·Commit·Push를
수행하지 않았습니다. 전체 서비스 E2E나 운영 활성화 판정도 하지 않았습니다.

상세 비식별 사전 확인 기록:
`20260831_consultation_context_provider_canary_사전확인_및_실행보류.json`

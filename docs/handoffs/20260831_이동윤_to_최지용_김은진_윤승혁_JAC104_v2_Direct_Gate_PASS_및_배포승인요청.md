# JAC104 v2 EC2 Direct Gate 재실행 결과 및 운영 Profile 승인 요청

- 발신: 이동윤(AI·RAG)
- 수신: 최지용(Backend·DB), 김은진(Data·QA·배포), 윤승혁(PM)
- 참조: 양정현(MCP)
- 확인일: 2026-08-31, 최종 운영 Health 확인 16:47:21 KST
- 판정: **1~3번 PASS / 4번 HOLD / 5번 NOT_RUN / 6번 NOT_COMPLETE**
- 전체 복구: **FULL_RECOVERY=HOLD**. 신규 합성 문의·Provider Canary는 아직 재개하지 않습니다.

## 1. 최지용님께 회신

디스크 공간 확보 후 EC2에서 Provider 호출 없는 JAC104 검색 Gate를 재실행했습니다.
원래 후보 `c6036fe4`와, 작업 중 새로 운영에 올라온 것을 확인한 `ce22601b` 이미지에서
**각각 독립적으로 전·후 Readonly Preflight 및 Direct Gate가 종료 코드 0으로 PASS**했습니다.
추가 DB·View·Migration 수정은 요청하지 않습니다.

각 실행에서 실제 RDS 53건·15/19/19·Canonical 정합성을 확인했고, JAC104 3개 증상의
기대 근거 검색과 IAC425/IAC606 정책 차단을 통과했습니다. 이 결과는 **JAC104-only
Direct 검색 검증**이며, 운영 MCP 검증이나 3모델 Public 활성화 완료는 아닙니다.

| 번호 | 요청 항목 | 현재 판정과 근거 |
| --- | --- | --- |
| 1 | 실제 RDS 구조가 복구 계약과 일치 | PASS — 이전 실제 Canonical 검사에 더해 이번 두 이미지에서 Readonly·53건·15/19/19·Identity 재검증 |
| 2 | 후보 AI 이미지 Provider-free 검색 Gate | PASS — 원래 후보와 새 운영 이미지 각각 Gate exit 0 |
| 3 | 3개 증상 검색·나머지 두 제품 차단 | PASS — 각 실행에서 3/3 기대 근거 Hit, 2/2 검색 전 정책 차단 |
| 4 | Data·PM 승인 후 배포 문제 해결 | HOLD — 공간 확보와 새 이미지 운영은 확인. JAC104 15건 Data 검수, 최종 SHA·Profile에 대한 PM 승인 및 배포 담당 종결 회신 필요 |
| 5 | 새 이미지 배포 후 운영 MCP 경로 검증 | NOT_RUN — 현재 운영 Profile이 여전히 `mvp`. 승인된 `jac104_v2_recovery` 운영 MCP 실행 증거 없음 |
| 6 | 최종 Release·Image·Profile·Health 증거 | NOT_COMPLETE — 현재 식별자·Health는 확보했지만 복구 Profile과 운영 MCP PASS 증거가 아직 없음 |

## 2. 실제 실행 식별자

### 원래 지정 후보

- SHA: `c6036fe413ed94aa8ef2dd621941eea5e5d4f68d` (`v0.3.6`, 기존 CI 후보)
- Docker Image ID: `sha256:ba889b787808cb72efc564d6688cb05ef7278778d5743e7df4fce8ec5d243976`
- 검증 Container ID: `1792deb03af5b02118c07eded3049786591c1dc93a71758e8aaadfe59c39b478`
- 실행: 16:28:38.469 ~ 16:29:01.925 KST, exit 0, OOM false.
- 원본: `20260831_JAC104_v2_c6036fe4_EC2_Direct_Gate_stdout.txt`

### 별도로 재검증한 새 운영 이미지

- SHA: `ce22601bf4f21b0c11d7626fb3bd1b905464d1da`
- Git 태그: `v0.3.8` — 로컬 `git tag --points-at` 확인값. EC2에서는 SHA·Digest를 직접 확인.
- Docker Image ID: `sha256:6df3057e8f698dd613a3ed920bf9edb8ddf0d06593eacc356147dcf9053303c2`
- 검증 Container ID: `eec93b94f2d20734fa099f9f47f006bc43d026d430561b91f664ff907802ce6c`
- 실행: 16:39:47.704 ~ 16:40:10.340 KST, exit 0, OOM false.
- 원본: `20260831_JAC104_v2_ce22601b_EC2_Direct_Gate_stdout.txt`

두 SHA의 `ai/**`와 Readonly Preflight 소스는 `git diff --quiet` exit 0으로 동일했습니다.
그럼에도 이미지가 다르므로 첫 결과를 재사용하지 않고 두 번째 컨테이너에서 다시 실행했습니다.
각 이미지 안에서 Gate·Runtime Profile·Index Readiness·Preflight의 실제 파일 SHA-256도
확인했습니다. 이는 네 파일의 정합성 검사이며 전체 이미지의 재현 빌드 증명은 아닙니다.

## 3. 두 실행 모두 통과한 조건

- Python `3.13.13`, PostgreSQL `16.14`, pgvector `0.8.2`.
- 검증 Profile `jac104_v2_recovery`, Transport `direct`, Index `2.0.0`.
- 승인 View 53건, 고유 Child 53개, 완전한 Lineage 53건, Vector 1024차원.
- 모델별 JAC104 15 / IAC425 19 / IAC606 19. 실제 허용 제품은 JAC104 1종.
- Chunk Set SHA-256: `5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304`.
- 각 실행 전·후 Preflight: 모두 `AI_READONLY_RUNTIME_PREFLIGHT_PASS`, exit 0.
- 승인 View SELECT만 허용, View Write·Base Table 접근·Schema CREATE 차단,
  `default_transaction_read_only=on`.
- 각 실행의 Provider 호출 0, Backend Write 0, DDL 실행 없음.
- IAC425/IAC606: 모두 `POLICY_BLOCK_UNSUPPORTED_MODEL`, 반환 근거 없음.

| Probe | 실제 Hit 수 | 기대 근거 포함 |
| --- | --- | --- |
| 냉수가 미지근함 (`COLD_TEMPERATURE`) | 5 | PASS — JAC104 P037 COLD-NORMAL 및 COLD-FAULT 포함 |
| 출수량이 적음 (`LOW_FLOW`) | 5 | PASS — JAC104 P038 LOW-FLOW 포함 |
| 맛·냄새 (`TASTE_ODOR`) | 5 | PASS — JAC104 P038 TASTE-ODOR 포함 |

세 Probe에서 다른 모델 근거·Direct Parent·미검증 근거는 각각 0건입니다.
이는 반환 ID의 Canonical Child 소속, Exact 모델 코드, Runtime 적격성 검사가 모두
통과했다는 데서 도출한 값입니다. 원본 CLI에 별도 오염 카운터 필드가 있는 것은 아닙니다.

합격 기준은 **Top-5에 기대 근거 포함**입니다. 같은 JAC104의 다른 증상 근거도 포함되어
있으므로 5건 모두 완벽히 관련 있다고 주장하지 않습니다. 원본 `chunk_ids`는 ID 정렬이며
검색 순위가 아닙니다. 이번 실행은 새로운 50문항 QA·전체 Multi-Agent·Provider·동일 Inquiry
저장/Replay·MCP E2E가 아닙니다. Write/Provider 0도 해당 검사 프로그램의 실행 범위이며
운영 전체 호출 통계나 전체 DB 전후 해시 검사를 뜻하지 않습니다.

## 4. 현재 운영 상태와 검증 환경의 차이

작업 시작 시 운영은 `2fffbaeb...` / Image `811ca1c4...`였습니다. 작업 중 다른 실행 주체의
새 배포가 발생한 것을 확인했습니다. **이번 AI·RAG 검증 작업에서 운영 배포·재시작·env
변경을 수행한 것은 아닙니다.** 새 배포의 CI 전체 성공 여부는 이번 재개 실행에서 별도로
감사하지 않았습니다.

- 현재 Release SHA: `ce22601bf4f21b0c11d7626fb3bd1b905464d1da`.
- 현재 AI Image: `sha256:6df3057e8f698dd613a3ed920bf9edb8ddf0d06593eacc356147dcf9053303c2`.
- 현재 운영 Container: `44b24890320258070da176bd79303a9a4c99a8d15fb831352bc656fe0c037038`.
- 운영 Container 시작: 16:22:26.659 KST.
- 실제 운영 설정: **`mvp + multi_agent + mcp`**, Handoff Backend disabled.
- 최종 상태: running / healthy / restart 0 / AI Health HTTP 200.
- 디스크: 재개 시 여유 57G·27% 사용, 최종 여유 56G·28% 사용.

같은 새 이미지의 **별도 검증 컨테이너에서만** `jac104_v2_recovery + direct`를 사용했습니다.
따라서 Image Gate PASS와 현재 `mvp + mcp` 운영의 복구 완료를 동일시할 수 없습니다.
Health 200도 실제 MCP 검색 성공을 대신하지 않습니다.

## 5. 다음 담당자 순서 및 승인 요청

1. **김은진 / Data·QA**: 첨부 결과의 JAC104 공식 Child 15건과 3개 증상 근거를 검수한 뒤
   `JAC104_DATA_PASS` 또는 실패 항목을 회신해 주세요. 새 DB 수정·재적재를 요청하는 것은 아닙니다.
2. **윤승혁 / PM, 배포 담당**: Data 회신 후 최종 대상 SHA·Image를 확정하고,
   `AI_RAG_RUNTIME_PROFILE=jac104_v2_recovery`의 **JAC104-only 운영 전환** 승인 여부를 회신해 주세요.
   현재 확인된 대상은 위 `ce22601b` / Image `6df3057e...`이며, 아직 승인된 대상으로 간주하지 않습니다.
   Pipeline·Transport 변경이나 IAC425/IAC606 Public 활성화까지 승인하는 요청이 아닙니다.
3. **배포 담당**: 승인 후 배포 장애 종결 근거와 롤백 식별자를 보존하고 승인된 운영 Profile을
   반영해 주세요. 이미 배포된 이미지를 이유 없이 다시 빌드해야 한다는 의미는 아닙니다.
4. **이동윤·양정현 / AI·RAG·MCP**: 승인된 운영 Profile 반영 후 실제 MCP 경로로
   동일 3개 증상·두 제품 차단을 Provider/Backend Write 없이 검증하고 최종 식별자·Health를 인계합니다.
5. **최지용 / Backend**: 1~6번 전체 PASS와 최종 증거를 받은 뒤 신규 합성 문의·Provider Canary를 재개합니다.

## 6. 안전 조치 및 첨부

브라우저의 기존 SSM 세션에서 EC2 일회성 검증 컨테이너를 사용했습니다.
각 컨테이너는 4GiB·1 CPU, Readonly RootFS, 캐시·CA·Preflight Readonly Mount,
Provider Key·Handoff Token 비움, Handoff·Telemetry 비활성, 모델 Offline Cache 사용으로 제한했습니다.
운영 env 파일의 Secret 값을 출력하거나 복사한 문서를 만들지 않았습니다.

검증 종료 및 로그 확보 후 **이번에 만든 임시 검증 컨테이너 두 개만** 정확한 ID로 삭제했습니다.
이미지·캐시 Volume·운영 컨테이너는 삭제하지 않았습니다. 결과는 첨부 파일로 보존되어 있고,
이미지와 캐시가 남아 있어 승인된 조건으로 새 검증 컨테이너를 만들 수 있습니다.
후보 Pull에만 사용한 임시 ECR 인증 디렉터리가 제거된 것도 확인했습니다.

- 상세 실행·6단계 상태: `20260831_JAC104_v2_EC2_Direct_Gate_실행결과.json`
- 원래 후보 stdout: `20260831_JAC104_v2_c6036fe4_EC2_Direct_Gate_stdout.txt`
- 새 운영 이미지의 별도 Gate stdout: `20260831_JAC104_v2_ce22601b_EC2_Direct_Gate_stdout.txt`
- 첨부 무결성: `20260831_JAC104_v2_EC2_Direct_Gate_SHA256SUMS.txt`

두 stdout은 별개 Container에서 수집했지만 결과가 결정적이고 시간·Container ID를 출력하지
않으므로 내용과 SHA-256이 같습니다. 각각의 실제 Container ID·시작/종료 시각은 상세 JSON에
구분해 기록했습니다. 회신 문서는 작성만 했으며 담당자에게 외부 발송하지 않았습니다.

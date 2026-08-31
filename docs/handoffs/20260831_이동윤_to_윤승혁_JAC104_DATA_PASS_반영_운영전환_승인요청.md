# JAC104 Data 승인 수신 및 JAC104-only 운영 전환 승인 요청

- 발신: 이동윤(AI·RAG)
- 수신: 윤승혁(PM·기술 통합)
- 참조: 김은진(Data·QA·배포), 최지용(Backend·DB), 양정현(MCP)
- 작성일: 2026-08-31
- 상태: **JAC104_DATA_PASS 수신 / PM_APPROVAL_PENDING / FULL_RECOVERY=HOLD**
- 이 문서는 승인 요청 초안입니다. PM 승인·운영 변경·외부 발송을 완료했다는 기록이 아닙니다.

## 1. 윤승혁님께 전달할 요청문

윤승혁님, JAC104 복구를 위한 실제 RDS 계약 검사와 후보 이미지 Direct 검색 Gate를
통과했고, 김은진님으로부터 아래 대상의 **JAC104_DATA_PASS** 회신을 받았습니다.
이를 근거로 해당 이미지의 **JAC104-only 운영 Profile 전환 승인**을 요청드립니다.

- 대상 SHA: `ce22601bf4f21b0c11d7626fb3bd1b905464d1da`
- 대상 AI Image Digest / 기록된 Docker Image ID:
  `sha256:6df3057e8f698dd613a3ed920bf9edb8ddf0d06593eacc356147dcf9053303c2`
- 요청 Profile: `AI_RAG_RUNTIME_PROFILE=jac104_v2_recovery`
- 검색 허용 제품: `WPUJAC104DWH` 1종, 공식 Child 근거 15건.
- 유지 요청: `AI_PIPELINE_RUNTIME=multi_agent`, `AI_RETRIEVAL_TRANSPORT=mcp`,
  기존 Readonly 권한 및 Handoff 비활성 설정. Pipeline 기본값 승격이나 Transport 변경 요청이 아닙니다.
- 제외: IAC425/IAC606 Public 활성화, DB 수정·재적재, 신규 합성 문의·Provider Canary,
  전체 서비스 최종 Release 승인.

확보한 근거는 다음과 같습니다.

- 실제 RDS 계약·Canonical 정합성: PASS. 공식 View 53건, 모델별 15/19/19.
- 위 이미지의 별도 컨테이너에서 전·후 Readonly Preflight: 각각 PASS / exit 0.
- JAC104 냉수 미지근함·출수량 감소·맛/냄새: 3/3 기대 근거 Top-5 포함.
- IAC425/IAC606: 2/2 정책 차단. 검증 경로의 Provider 호출·Backend Write·DDL 없음.
- 김은진 Data 회신: JAC104 15건 원문·페이지·본문 동일, 3개 증상 기대 근거 적합,
  전체 53건 Chunk Set Hash 일치, 불일치 및 데이터 측 차단 사유 없음.

승인 후에는 김은진님(배포 담당)이 실제 운영 식별자·설정 및 롤백 조건을 재확인하고
승인된 AI 이미지·Profile을 반영하는 순서로 진행하고자 합니다. 동일 이미지가 이미
운영 중이라면 이를 이유 없이 다시 빌드하는 요청은 아닙니다.

이후 이동윤·양정현이 **실제 운영 MCP 경로**에서 같은 3개 증상과 두 제품 차단을
Provider/Backend Write 없이 검증하고, 최종 Release·Image·Profile·Health 증거를
최지용님께 전달하겠습니다. 운영 MCP 검증을 포함한 1~6번 전체 PASS 전까지
신규 합성 문의·Provider Canary는 HOLD를 유지합니다.

**위 정확한 SHA·Image·Profile에 대한 승인 또는 보류, 배포 담당자와 실행 조건을
회신해 주세요.** 다른 이미지·Profile로 변경한다면 기존 검증·Data 승인과의 정합성을
다시 확인한 뒤 진행해야 합니다.

## 2. Data 회신 수신 기록과 대상 연결

사용자가 이번 대화에 전달한 김은진 → 이동윤 회신을 Data Owner 승인 근거로 접수했습니다.
회신 내용은 다음과 같습니다.

> 판정: JAC104_DATA_PASS
>
> 공식 Child 15건은 기존 검수된 원문·페이지·본문과 동일합니다.
> 냉수 미지근함·출수량 감소·맛/냄새의 기대 근거가 적합합니다.
> 재계산한 전체 53건 Chunk Set Hash가 첨부와 일치합니다.
> 불일치 chunk_id 및 JAC104-only 검색 근거 사용의 데이터 측 차단 사유는 없습니다.
>
> 대상 SHA: ce22601bf4f21b0c11d7626fb3bd1b905464d1da
> 대상 이미지: 첨부의 해당 SHA 검증 이미지
> Profile: jac104_v2_recovery

기존 실행 JSON에는 이 SHA의 검증 Run이 하나만 존재합니다. 따라서 회신의
“첨부의 해당 SHA 검증 이미지”를 위의 정확한 Digest `6df3057e...`에 연결했습니다.
회신에서 참조한 전체 Chunk Set Hash는 다음 값입니다.

`5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304`

이는 전체 53건의 Hash이며, 이번 운영 허용 범위는 그중 **JAC104 15건**입니다.
53건의 Hash 일치를 나머지 두 제품의 운영 활성화 승인으로 확대하지 않습니다.

이번 작업에서 원문 검수나 RDS 검증을 새로 실행한 것은 아닙니다. 원문·Hash 재계산
확인은 김은진의 회신 근거이며, AI 측에서는 기존 증거의 정확한 SHA·Image·Profile 연결과
첨부 4개 파일의 SHA-256 무결성을 다시 확인했습니다.

## 3. Data 승인 수신 후 6개 항목 상태

| 번호 | 항목 | 상태 |
| --- | --- | --- |
| 1 | 실제 RDS 구조·복구 계약 일치 | PASS — 기존 실제 EC2 검증 증거 유지 |
| 2 | 후보 이미지 Provider-free Direct Gate | PASS — 위 ce22601b 이미지의 독립 실행 증거 유지 |
| 3 | JAC104 3개 증상 검색·다른 두 제품 차단 | PASS — 3/3 기대 근거 Hit 및 2/2 정책 차단 |
| 4 | Data·PM 승인 및 배포 문제 종결 | Data PASS 수신. PM 승인·배포 담당 종결 증거는 대기하므로 전체 항목은 HOLD |
| 5 | 승인된 복구 Profile의 실제 운영 MCP 검증 | NOT_RUN |
| 6 | 복구 완료 Release·Image·Profile·Health 최종 증거 | NOT_COMPLETE |

마지막 직접 운영 관찰은 2026-08-31 16:47:21 KST의 위 이미지,
`mvp + multi_agent + mcp`, healthy / HTTP 200 / restart 0입니다.
이번 승인 요청 작성 중 AWS에 재접속하거나 최신 운영 상태를 다시 조회하지 않았습니다.
배포 직전 재확인이 필요하며, 과거 Health 200을 복구 Profile의 MCP PASS로 대체하지 않습니다.

## 4. 첨부 및 보존

- 실행 JSON: `20260831_JAC104_v2_EC2_Direct_Gate_실행결과.json`
- 대상 이미지 stdout: `20260831_JAC104_v2_ce22601b_EC2_Direct_Gate_stdout.txt`
- 기존 전체 실행 회신: `20260831_이동윤_to_최지용_김은진_윤승혁_JAC104_v2_Direct_Gate_PASS_및_배포승인요청.md`
- 기존 첨부 4개 파일 무결성: `20260831_JAC104_v2_EC2_Direct_Gate_SHA256SUMS.txt`

기존 첨부는 Data 회신 수신 전의 실행 시점 기록이므로 수정하지 않았습니다.
이 문서가 **Data 승인 수신에 대한 후속 기록**이며, 기존 SHA256SUMS의 적용 대상은 아닙니다.
새 코드·DB·env 변경, Docker/EC2 재시작, 배포, Provider 호출, 외부 발송, Commit/Push는 없습니다.

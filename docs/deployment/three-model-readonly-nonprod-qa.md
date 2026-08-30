# 3모델 Readonly NONPROD QA 실행

이 절차는 `f595dd8777eaf3f3f7f59ff63aa8bb2a250225ab`의 AI·데이터 소스를
대상으로 공식 Readonly 50 Case Gate를 실행한다. Workflow 정의는 승인된 현재
`main`에서 실행하며 Public Runtime은 계속 `HOLD`다.

## GitHub NONPROD 설정

GitHub Environment `nonprod`와 다음 Repository Variable이 필요하다.

- `NONPROD_AWS_REGION`
- `NONPROD_AWS_ACCOUNT_ID`
- `NONPROD_AWS_ROLE_ARN`
- `NONPROD_EC2_INSTANCE_ID`
- `NONPROD_ECR_AI_QA_REPOSITORY`
- `NONPROD_AI_VECTOR_SECRET_ID`

OIDC Role은 `nonprod` Environment에서 발급된 GitHub OIDC Subject만 신뢰하고,
지정 QA ECR Repository Push와 지정 NONPROD Instance의 SSM Command 실행·조회만
허용한다. Production 배포 Role, Production EC2와 Production ECR Repository를
재사용하지 않는다.

EC2 Instance Role에는 지정 QA ECR Image Pull, 지정 Secret 조회와 SSM Agent
실행 권한이 필요하다. `/etc/waterbridge/certs/rds-ca.pem`에는 AWS RDS CA 파일이
일반 파일로 있어야 한다.

## 보호 Secret 계약

`NONPROD_AI_VECTOR_SECRET_ID`는 `waterbridge/nonprod/` Prefix의 Secrets Manager
Secret ID다. SecretString은 다음 Key 하나만 가진 JSON Object여야 한다.

```json
{
  "AI_VECTOR_DSN": "<protected-readonly-dsn>"
}
```

실제 값은 GitHub Variable·Workflow 입력·SSM Command·Artifact에 넣지 않는다.
EC2가 Secret을 직접 조회하며 값은 `/dev/shm`의 임시 Env File에만 기록한 후
Container 종료 시 삭제한다.

## 실행과 증거

GitHub Actions에서 `Three-model Readonly NONPROD QA`를 `main` 기준으로 수동
실행한다. Workflow는 다음을 수행한다.

1. 검증 Source를 고정 SHA로 Checkout한다.
2. Unit Test와 고정 BGE-M3 Revision을 포함한 `readonly-qa` Image를 빌드한다.
3. NONPROD QA ECR에 Push하고 Digest를 다시 조회해 일치시킨다.
4. 지정 NONPROD EC2에 SSM Run Command를 보내 일회성 Readonly Container를
   실행한다.
5. Readonly Role Preflight를 Gate 전후로 실행하고 공식 50 Case 결과를
   확인한다.
6. 기존 실행 Container 목록의 전후 Hash가 같은지 확인한다.
7. 원문 SSM 출력은 Artifact에서 제외하고, 정제된 `evidence.json`과
   `evidence.sha256`만 보존한다.

실패 시 운영 AI나 DB를 변경해 우회하지 않는다. ECR Digest나 SSM Command ID가
없거나, Secret 노출 위험이 탐지되거나, 기대 Count가 다르면 결과는 `HOLD`다.

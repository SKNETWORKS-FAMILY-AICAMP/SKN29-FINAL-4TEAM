# E13 — GitHub Actions + ECR + SSM Deployment Reproducibility

- Status: **E13_COMPLETE**
- Current Git SHA: `55bbc96057e46ebbf11d165da25c63fd6cde61a0`
- Repository: `SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM`

## E13-01 Release Source / CI Contract

- Source contract: `PASS`
- Application source pinned to release SHA: `True`
- Reusable workflow implementation pinned to release SHA: `False` (`production-deploy.yml@main`)

## E13-02 GitHub OIDC → AWS → ECR / SSM

- Status: `PASS`
- Workflow run ID: `33294950486`
- ECR repositories 3/3 verified: `True`
- SSM command path verified: `True`

## E13-03/E13-04 Existing Production Release Evidence

- Existing successful Production Deploy: `VERIFIED`
- Production workflow run ID: `33238345342`
- Release SHA: `55bbc96057e46ebbf11d165da25c63fd6cde61a0`
- Build and publish job: `True`
- SSM deploy job: `True`
- External HTTPS smoke: `True`
- Exact Web/Backend/AI digest values recovered from log: `False`
- DEPLOYMENT_RUNTIME_PASS marker recovered from log: `True`

## E13-05 Rollback Contract

- Rollback contract: `PASS`
- Production fault injection: `False`

## Security / Evidence Boundary

- AWS credentials captured: `False`
- OIDC token captured: `False`
- ECR password captured: `False`
- Raw SSM stdout persisted: `False`
- Raw GitHub job logs persisted: `False`

## Interpretation

E13_COMPLETE는 기존 성공 Production Release의 GitHub Actions 실행 증거까지 확인한 경우에만 사용한다. E13_PARTIAL은 GitHub OIDC → AWS Role → ECR repository 검증 → 실제 SSM command path까지는 확인했지만, 적절한 성공 Production Release 실행 증거를 확인하지 못한 경우다.

현재 배포 경계는 `DEPLOYMENT_RUNTIME_PASS`와 `OBSERVABILITY_PARTIAL`을 구분한다. E13은 완전한 distributed tracing 완료를 주장하지 않는다.

## Presentation-ready Claim

GitHub Actions에서 장기 Access Key 대신 OIDC로 AWS Role을 획득하고 ECR 및 SSM 연결 경로를 검증했다. 성공 Production Release가 확인된 경우에는 검증을 통과한 Web·Backend·AI 이미지를 ECR에 게시하고 Image Digest를 Release Bundle에 고정한 뒤, SSM을 통해 EC2에서 배포하고 외부 HTTPS Smoke까지 통과한 실행 증거를 연결했다.

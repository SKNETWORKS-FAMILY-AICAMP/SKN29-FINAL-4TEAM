# REST API 계약·오류·로그 보안 가이드

> 관련 업무: 공통 REST·OpenAPI 계약
> 원칙: 설명 문서보다 기계 계약과 Runtime 증거를 우선한다.

## 1. Source of Truth

- `contracts/api/openapi.yaml`
- `contracts/api/paths/**`
- `contracts/api/components/**`
- `contracts/api/examples/**`
- `contracts/error-codes/error-codes.yaml`
- `backend/config/api_urls.py`

## 2. 구현 순서

1. 요구사항과 역할·객체 범위 확인
2. Method·Path·operationId 확정
3. Request·Response·Error Schema 작성
4. Serializer·Permission·Service·Repository 구현
5. Route와 OpenAPI Runtime 상태 연결
6. 정상·403·404·409·422·Rollback Test
7. 계약 Validator와 전체 회귀

## 3. 공통 응답 경계

- 오류는 JSON Envelope와 Canonical Error Code를 사용한다.
- `state_version` 충돌은 409와 최신 Snapshot을 제공한다.
- 멱등 키 충돌과 상태 충돌을 같은 오류로 숨기지 않는다.
- 존재 은닉이 필요한 객체 권한은 계약에 따라 404를 사용한다.
- Correlation ID는 요청·응답·로그·DB 원장에서 동일한 UUID를 사용한다.

## 4. 로그 보안

다음 값은 Request·Exception·AI Lifecycle 로그에 기록하지 않는다.

- Password·JWT·Cookie·Authorization
- DB Password·DSN·Secret
- 고객 연락처·주소·원문 증상
- AI Prompt·원문 근거·내부 파일 경로

로그에는 Method·Route Template·Status·Duration·Correlation·안전한 오류 코드만
남긴다.

## 5. 검증

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  .\tests\contract `
  .\backend\tests\api\test_openapi_runtime_coverage.py `
  .\backend\tests\api\test_runtime_examples_contract.py

.\backend\.venv\Scripts\python.exe -B .\scripts\contracts\validate_openapi.py
```

## 6. 완료 판정

계약 Validator, Route Coverage, Example, 권한·오류·멱등·Rollback과 로그 Redaction이
통과하면 해당 API 계약·Runtime 작성자 검증 완료다. `OpenAPI-only`는 구현 완료가
아니다.

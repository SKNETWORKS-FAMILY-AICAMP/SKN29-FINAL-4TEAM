# Contracts

웹·모바일·백엔드·AI가 함께 지켜야 하는 언어 중립적 계약을 관리한다.

## 디렉토리

- `api/`: 웹·모바일과 백엔드 사이의 REST API 계약
- `ai/`: 백엔드와 AI 서비스 사이의 JSON Schema 계약
- `state-machine/`: 문의·상담·방문 상태, 이벤트, 가드와 허용 행동
- `codes/`: 역할·상태·위험도 등 공통 코드
- `error-codes/`: 업무 오류 코드 레지스트리
- `examples/`: 여러 계약을 연결한 대표 흐름 예시

## 공통 기준선

- `api/action-operation-crosswalk.yaml`: 외부 Action 23개의 State Machine Event·OpenAPI·Runtime 분류
- `api/g2-operation-crosswalk.yaml`: 상담·방문 G2 결정과 Operation 11개의 상세 연결

검증 명령:

```text
python scripts/contracts/validate_contract_crosswalk.py
python scripts/contracts/validate_codes.py
python scripts/contracts/validate_openapi.py
python scripts/contracts/validate_examples.py
python -m unittest discover -s tests/contract/api -p "test_*.py" -v
python -m unittest discover -s tests/contract -p "test_*.py" -v
```

위 명령은 `contracts/**`, `scripts/contracts/**`, `tests/contract/**` 변경 시
`.github/workflows/data-ci.yml`에서도 동일한 계약 Gate로 실행된다.

## 변경 원칙

1. 계약 파일을 먼저 수정한다.
2. 정상·오류 예시와 `CHANGELOG.md`를 함께 수정한다.
3. 백엔드 Serializer, AI Schema, Web 타입, Mobile DTO를 동기화한다.
4. 계약 테스트 통과 후 PR을 병합한다.

> 이 압축 파일은 초기 골격이다. 세부 속성은 API·ERD 확정 후 채운다.

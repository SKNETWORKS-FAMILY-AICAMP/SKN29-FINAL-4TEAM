# Changelog

## 0.3.0

- Inquiry 상태를 API 명세의 canonical 12개 코드로 통일
- 추가 답변 이벤트를 `SUBMIT_ANSWERS`로 확정하고 데이터 전용 구 코드 폐기
- `COMPLETION_PENDING`에서 고객의 `SUBMIT_RESOLUTION_FEEDBACK`은 상태를
  유지하고 snapshot 담당자만 `FINALIZE_INQUIRY`할 수 있도록 완료 정책 명시
- 대표 E2E에 필요한 상태 전이, 역할 권한, 담당자·동시성 guard를 실행 가능한
  기준표로 구체화

## 0.2.1

- 위험도 canonical 코드를 `general`, `caution`, `danger`로 재확인
- 위험도 `general`과 사용 안내 `NORMAL`을 서로 다른 필드의 독립 코드로 명시
- 데이터 Schema·Fixture가 `contracts/codes/risk-levels.yaml`과 같은 enum을
  사용하도록 계약 검증 범위를 확대

## 0.2.0

- 사용 안내 상태 코드 기준본을 `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`,
  `PENDING_CONSULTATION`으로 확정
- 기존 `USE_ALLOWED`는 별칭이나 입력 호환 없이 폐기
- `risk_level=general`과 `usage_guidance_status=NORMAL`은 서로 다른 필드의
  독립된 코드임을 명시

## 0.1.0

- `contracts/` 초기 골격 생성
- REST API, AI JSON Schema, State Machine, 공통 코드, 오류 코드 영역 분리

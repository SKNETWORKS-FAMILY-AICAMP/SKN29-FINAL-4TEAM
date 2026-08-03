# WaterBridge Architecture Decision Records

> 프로젝트: SKN29 Final Project — WaterBridge
>
> 범위: Backend·Database·인증·상태 이력의 팀 공용 기술 결정
>
> 기준일: 2026-08-02

이 디렉터리는 개인 작업 메모가 아니라 여러 구현과 소비자가 함께
따라야 하는 Architecture Decision Record(ADR)를 보관한다. 코드·계약과
상태가 달라졌다면 ADR의 결정 이력은 보존하고 현재 구현 결과와 대체
관계를 명확히 갱신한다.

## 1. 현재 ADR

| ADR | 사람이 읽는 현재 상태 | 적용 범위 |
| --- | --- | --- |
| [ADR 0008](0008-t005-data-contract-decisions.md) | 부분 대체 | T-005 최초 6개 결정 중 기본키 정책은 ADR 0010이 대체, 나머지 5개 결정은 활성 |
| [ADR 0009](0009-t017-jwt-rbac-owner-baseline.md) | 활성·구현됨·검토 대기 | JWT 발급·회전·폐기, UUID subject, 4역할 RBAC와 객체 범위 |
| [ADR 0010](0010-t005-three-layer-identifier-bridge.md) | 활성·구현됨 | 내부 BigInt PK·외부 UUID·업무 코드 분리와 완료된 Auth 전환 |
| [ADR 0011](0011-t005-status-history-idempotency-scope.md) | 활성·구현됨 | 요청 멱등성 원장과 Aggregate 상태 이력 책임 분리 |

ADR 0008 이전의 검토 제안은 최종 결정과 섞이지 않도록
[개인 Archive의 역사 제안서](../individual/jiyong/archive/20260725_데이터베이스_물리계약_검토제안_보관.md)로
분리했다.

## 2. 상태 해석

| 상태 축 | 의미 |
| --- | --- |
| 기계 상태 | 기존 Validator·Readiness가 읽는 호환 상태값 |
| 사람이 읽는 상태 | 현재 활성·부분 대체·구현·보관 여부 |
| 구현 상태 | Model·Migration·Service·계약·테스트 반영 여부 |
| 공식 완료 | 비작성자 재현·소비자 검토·PM 승인까지 포함한 WBS Gate |

`OWNER_BASELINE_ACCEPTED`는 채택된 담당 기준선을 뜻한다. 이 문자열만으로
공식 완료를 판정하지 않으며, 기존 도구가 소비하므로 의미를 바꾸거나
삭제할 때는 Validator와 테스트를 함께 수정한다.

## 3. 현재 Source of Truth

| 판정 대상 | 우선 원천 |
| --- | --- |
| T-005 활성 기계 계약 | [T-005 README](../database/t-005/README.md), `manifest.json`, Physical Contract v1.3 |
| 실제 데이터베이스 구조 | Django Model·적용 순서가 보존된 Migration·PostgreSQL 검증 결과 |
| 인증 Runtime | Django 설정·Accounts Service·JWT Authentication·Auth 계약·회귀 테스트 |
| 상태 전이 규칙 | `contracts/state-machine/**` |
| 결정 이유·대체 관계 | 이 디렉터리의 ADR |
| 제안·작성 과정 | `docs/individual/**/archive` |

문서 파일의 존재나 과거 테스트 수치만으로 현재 구현 완료를 판정하지
않는다.

## 4. ADR 변경 원칙

1. 기존 ADR 번호와 파일 경로를 재사용하거나 바꾸지 않는다.
2. 결정을 대체할 때 기존 내용을 삭제하지 않고 후속 ADR과 대체 범위를
   연결한다.
3. 현재형으로 남은 과거 전환 계획은 “결정 당시 계획”과 “현재 구현
   결과”로 분리한다.
4. 기계 계약·Model·Migration·Service·OpenAPI·테스트의 영향 범위를
   함께 기록한다.
5. 비밀값, 실제 고객 데이터, 개인 PC 절대경로와 일회성 대화 맥락을
   기록하지 않는다.

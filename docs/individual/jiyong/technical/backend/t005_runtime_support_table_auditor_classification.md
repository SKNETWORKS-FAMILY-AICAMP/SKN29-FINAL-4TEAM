# T-005 Runtime 지원 테이블 Auditor 분류 가이드

> 기준일: 2026-07-30  
> 상태: `LOCAL_VERIFIED`  
> 범위: T-005 32-table 구현 준비도 Auditor의 계약 외 Runtime 분류  
> 담당: 최지용

## 1. 결론

T-005 immutable 계약은 32개 도메인 테이블의 구현 완료율을 판정한다.
그러나 Audit, 합성 Import, HTTP 요청 멱등성에는 계약 개수에 더하지 않는
운영 지원 테이블이 필요하다.

[`T-005 Runtime Auditor`](../../../../../scripts/database/audit_t005_implementation_readiness.py)에
아래 네 테이블만 정확한 이름과 사유를 가진 allowlist로 등록했다.
네 테이블은 `approved_runtime_support_tables` 증거로 별도 보고되며
`MODEL_TABLES_OUTSIDE_CONTRACT` 또는
`MIGRATION_TABLES_OUTSIDE_CONTRACT` 차단 사유를 만들지 않는다.

임의의 다섯 번째 이름은 계속 unknown으로 분류되어 두 차단 사유를 모두
발생시킨다. 접두사, wildcard, App 전체 허용은 사용하지 않았다.

## 2. 승인한 운영 지원 테이블

| 테이블 | 운영 책임 | 32-table 완료 개수 포함 | 분류 사유 |
| --- | --- | --- | --- |
| `audit_event` | Workflow 전이와 1:1로 연결되는 append-only 감사 원장 | 미포함 | 도메인 원본이 아니라 Runtime 감사 추적 지원 |
| `operations_synthetic_import_batch` | 합성 Import 실행·출처·집계 원장 | 미포함 | Importer 운영·재현 증거 |
| `operations_synthetic_import_item` | 합성 Import 개별 항목 결과·출처 원장 | 미포함 | 배치 내부의 항목별 성공·변경 추적 |
| `workflow_idempotency_record` | HTTP replay·payload 충돌 요청 원장 | 미포함 | ADR 0011이 상태 이력과 분리한 요청 멱등성 책임 |

근거 구현은
[`AuditEvent`](../../../../../backend/apps/audit/models/audit_event.py),
[`Synthetic Import Ledger`](../../../../../backend/apps/operations/models/synthetic_import_ledger.py),
[`WorkflowIdempotencyRecord`](../../../../../backend/apps/workflow/models/idempotency_record.py)에서
확인할 수 있다.

`workflow_transition_history`는 allowlist에 넣지 않았다. Wave 2E에서 해당
Runtime 모델이 32-table 계약의 실제 테이블
`support_inquiry_status_history`로 정렬되었기 때문이다. 과거 물리 이름을
운영 지원 테이블로 승인하면 계약 테이블 구현을 이중 계산하거나 잘못
면제할 수 있다.

## 3. Auditor 판정 규칙

Auditor는 Model 선언·Runtime 등록·Migration에서 발견한 테이블을 다음
순서로 분류한다.

```text
발견 테이블
  ├─ immutable 32-table 계약 이름 → 계약 구현 매핑
  ├─ 정확히 일치하는 승인 이름 4개 → approved runtime support evidence
  └─ 그 밖의 이름 → unknown + outside-contract blocker
```

승인 이름은 상수 `APPROVED_RUNTIME_SUPPORT_TABLES`의 key이며, value에는
승인 사유가 들어 있다. Model과 Migration은 각각 별도로 분류하므로 한쪽만
존재하는 지원 테이블도 evidence의 `model_present`,
`migration_present`로 드러난다.

출력 예시는 다음과 같다.

```json
{
  "approved_runtime_support_tables": [
    {
      "table": "audit_event",
      "reason": "Append-only workflow audit ledger; ...",
      "model_present": true,
      "migration_present": true
    }
  ],
  "implementation_mapping": {
    "approved_runtime_support_model_tables": [
      "audit_event"
    ],
    "approved_runtime_support_migration_tables": [
      "audit_event"
    ],
    "unknown_model_tables": [],
    "unknown_migration_tables": []
  }
}
```

## 4. 안전 경계

| 입력 상태 | 결과 |
| --- | --- |
| 계약 테이블 32개 중 일부 미구현 | `NOT_READY`, Model·Migration 미완료 blocker 유지 |
| 승인 지원 테이블 4개가 Model·Migration에 존재 | 별도 evidence로 보고, outside-contract blocker 없음 |
| 승인 지원 테이블 Model만 존재 | `model_present=true`, `migration_present=false` |
| 승인 지원 테이블 Migration만 존재 | `model_present=false`, `migration_present=true` |
| 임의의 다섯 번째 테이블 존재 | unknown 목록에 포함, outside-contract blocker 발생 |
| 이름이 비슷한 접두사·suffix 테이블 존재 | exact match가 아니므로 unknown |

이 분류는
[`watercare_schema_v3.json`](../../../../database/t-005/watercare_schema_v3.json)과
[`t005_physical_contract_v1.2.json`](../../../../database/t-005/t005_physical_contract_v1.2.json)을
변경하지 않는다. App Model과 Migration도 이번 Auditor 작업에서 수정하지
않았다.

## 5. 자동 검증

[`Auditor 단위 테스트`](../../../../../backend/tests/unit/database/test_t005_implementation_readiness.py)에
다음 경계를 추가했다.

1. 승인한 네 이름은 Model·Migration approved 목록에만 들어간다.
2. 임의의 `unapproved_runtime_table`을 다섯 번째로 추가하면 Model과
   Migration unknown 목록에 각각 남는다.
3. unknown 다섯 번째 테이블은 readiness를 `NOT_READY`로 만들고
   outside-contract blocker 두 개를 발생시킨다.
4. 실제 저장소에서는 승인 네 테이블이 모두 별도 evidence에 나타나고
   outside-contract blocker는 사라진다.
5. 실제 저장소의 32개 계약 Model·등록·Migration이 모두 준비되면
   `READY`가 되고, 임의의 다섯 번째 테이블 테스트는 계속
   `NOT_READY` 경계를 보장한다.

검증 결과:

| 검증 | 결과 |
| --- | --- |
| Auditor 집중 테스트 | `6 passed` |
| T-005 Schema Validator 회귀 | `37 passed` |
| 실제 저장소 Auditor | 계약 32/32, 승인 지원 4개, unknown 0개, blocker 0 |
| 실제 저장소 구현 준비도 | `READY` |

`READY`는 Model·Runtime 등록·Migration 매핑 준비도를 뜻한다.
비작성자 리뷰, 외부 재현과 물리 계약의 완료 승인까지 자동으로 뜻하지
않는다. 최종 통합 결과는
[T-005 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)를
참조하고, 새 변경 뒤에는 아래 명령으로 최신 상태를 다시 판정한다.

```powershell
& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\audit_t005_implementation_readiness.py
```

## 6. 협업 인계

| 역할 | 인계 내용 |
| --- | --- |
| Backend | 새 운영 테이블이 필요하면 임의로 allowlist에 추가하지 말고 이름·책임·보존 정책을 먼저 확정 |
| 데이터·Importer | 배치·항목 원장은 32-table 완료율이 아니라 Import 재현 evidence로 사용 |
| Audit | `audit_event`는 계약 상태 이력의 대체 테이블이 아니라 연결된 감사 원장으로 유지 |
| API·Workflow | 요청 replay 판정은 [`ADR 0011`](../../../../adr/0011-t005-status-history-idempotency-scope.md)의 `workflow_idempotency_record` 범위를 유지 |
| QA | 승인 4개뿐 아니라 임의의 다섯 번째 테이블 차단 테스트도 함께 유지 |
| PM | 새 지원 테이블 승인 시 정확한 이름과 사유를 리뷰하고 32-table 계약 포함 여부를 별도로 결정 |

기존 Runtime 현황과 계약·지원 테이블 분리 배경은
[`T-005 기준선 README`](../../../../database/t-005/README.md)를 함께
참고한다.

# 신규 2모델 E2E Fixture Runtime 구현·검증 및 인계

## 1. 목적과 범위

- 작성일: 2026-08-20
- 담당: 최지용(Backend·DB)
- 대상: `WPUIAC425SNW`, `WPUIAC606SNW`
- 기준 후보:
  `data/synthetic/candidates/product_expansion_e2e_cases.json`
- 목표: 기존 완료 문의를 초기화하거나 재사용하지 않고, 고유 `run_id`마다
  격리 E2E용 구독과 신규 문의를 준비한다.

이 작업은 Product·Inquiry·Evidence 공개 계약, State Machine, AI Runtime,
공식 데이터 원본을 변경하지 않는다. 신규 모델의 Care Cycle Rule도 만들지 않는다.

## 2. 현재 main에서 확인한 선행 구현

- Public API와 구독 Repository의 정확 판매코드는 3모델로 확장돼 있다.
- Backend→AI 요청의 `model_code`는 고객 소유 구독의
  `ProductModel.model_code`를 사용한다.
- 공식 Evidence Import·Crosswalk·Readonly View는 53청크
  (`15/19/19`) 프로필을 지원한다.
- 김은진의 신규 Case 2건과 검증 자료가 main에 포함돼 있다.
- 신규 두 Product는 기본 Import에서 `is_supported_mvp=false`를 유지한다.
- AI 활성 Runtime은 별도 Gate가 끝날 때까지 JAC 단일 모델만 허용한다.

따라서 Backend에서 필요한 최소 추가분은 “격리 환경의 신규 문의 생성 경계”이며,
제품과 AI의 실제 활성 완료 판정은 이 명령의 책임이 아니다.

## 3. 구현 결과

관리 명령:

```text
python manage.py create_product_expansion_e2e_fixture
```

주요 동작:

1. 기본 실행은 읽기 전용 준비 상태만 JSON으로 반환한다.
2. `--apply`일 때만 구독과 문의를 생성한다.
3. PostgreSQL Apply에는 연결 DB와 같은 `--confirm-database`가 필요하다.
4. 같은 `model_code + run_id`는 멱등 Replay하며 중복을 만들지 않는다.
5. 다른 `run_id`는 별도 구독·문의·Correlation·Idempotency 원장을 만든다.
6. 문의가 한 번이라도 소비되면 다시 초기화하지 않고 새 `run_id`를 요구한다.
7. `--dry-run`은 실제 Runtime 경로를 실행한 뒤 전체 Transaction을 Rollback한다.
8. 신규 모델 Care 일정은 `next_care_on=null`로 유지한다.
9. 기존 `InquiryService.create()`를 재사용해 `START_INQUIRY` History와
   Idempotency 원장을 동일 계약으로 생성한다.
10. 다른 모델 Evidence Code, 잘못된 Product UUID, 미지원 모델은 차단한다.

## 4. 안전한 실행 순서

### 4.1 읽기 전용 점검

```powershell
cd C:\python-src\Final_PROJECT\SKN29-FINAL-4TEAM\backend
.\.venv\Scripts\python.exe manage.py create_product_expansion_e2e_fixture `
  --model-code WPUIAC425SNW `
  --run-id iac425-20260820-001 `
  --json
```

신규 Product가 아직 비활성이라면 정상적으로 다음 Blocker를 반환한다.

```text
fixture_readiness=BLOCKED
known_blockers=PRODUCT_MODEL_RUNTIME_NOT_ENABLED
```

### 4.2 Transaction Dry-run

Product가 활성 지원 상태인 격리 DB에서 실행한다.

```powershell
.\.venv\Scripts\python.exe manage.py create_product_expansion_e2e_fixture `
  --model-code WPUIAC425SNW `
  --run-id iac425-20260820-001 `
  --dry-run `
  --json
```

완료값은 `DRY_RUN_ROLLED_BACK`, `persisted=false`여야 한다.

### 4.3 격리 PostgreSQL Apply

```powershell
.\.venv\Scripts\python.exe manage.py create_product_expansion_e2e_fixture `
  --model-code WPUIAC425SNW `
  --run-id iac425-20260820-001 `
  --apply `
  --confirm-database waterbridge_team_integration `
  --json
```

김은진이 신규 Product 활성화를 E2E 범위로 확인한 경우에만 아래 옵션을 쓴다.
이 옵션은 PostgreSQL에서 `waterbridge_team_integration` 외 DB를 거부한다.

```text
--enable-candidate-product
```

운영·공용 제품 활성화를 의미하지 않으며 격리 E2E 종료 후 별도 판정이 필요하다.

## 5. 반환 Crosswalk

- `run_id`
- `model_code`
- `candidate_case_id`
- `subscription_id`
- `inquiry_id`, `inquiry_code`
- `status`, `state_version`, `allowed_actions`
- `topic_code`, `evidence_group_id`
- `request_correlation_id`
- `created`, `persisted`, `dry_run`
- `fixture_readiness`, `known_blockers`

초기 Inquiry 기대값:

```text
status=DRAFT
state_version=1
allowed_actions=SUBMIT_SYMPTOM,CANCEL_INQUIRY
```

이후 상태는 실제 Backend→AI 결과와 State Machine이 결정한다.
Fixture 명령이 `AI_GUIDANCE`나 `CONSULTATION_REQUIRED`를 미리 만들지 않는다.

## 6. 작성자 검증

| 검증 | 결과 |
| --- | --- |
| 신규 Fixture 표적 테스트 | `14 passed` |
| 문의 Fixture·3모델 구독·AI 판매코드 회귀 | `55 passed, 6 skipped` |
| 3모델 Import·Evidence·G1-B Readiness 회귀 | `40 passed` |
| 두 회귀 묶음 합계 | `95 passed, 6 skipped` |
| Django System Check | `0 issues` |
| Migration Drift | `No changes detected` |
| Python Compile | `PASS` |
| 현재 PC의 실제 PostgreSQL 점검 | `BLOCKED_CONNECTION_TIMEOUT` |

6개 Skip은 PostgreSQL Row Lock 전용 Gate이며 SQLite 작성자 검증의 실패가 아니다.
실제 팀 DB Apply·Replay는 김은진의 독립 검증으로 남긴다.

## 7. 김은진에게 인계할 독립 QA

1. 최신 main SHA와 `waterbridge_team_integration`을 일치시킨다.
2. 53청크 Import·Crosswalk·View 분포 `15/19/19`와 Role을 먼저 확인한다.
3. 두 모델의 기본 Readiness가 비활성 Blocker를 정확히 반환하는지 확인한다.
4. 격리 E2E 활성 범위를 확인한 뒤 Dry-run→Apply→Replay 순서로 실행한다.
5. 같은 run_id 중복 0건, 다른 run_id 문의 분리, History·Idempotency·Correlation을 확인한다.
6. 소비된 문의를 다시 실행했을 때 원장 Reset 없이 차단되는지 확인한다.
7. IAC425·IAC606 모두 `next_care_on=null`인지 확인한다.
8. 실제 DB에서 Product 활성화 여부와 E2E 후 유지·원복 정책을 별도 회신한다.

## 8. 이동윤에게 인계할 공동 실행

1. 김은진의 53청크·Readonly View READY 뒤에만 실제 검색을 실행한다.
2. Fixture가 반환한 Inquiry의 구독 판매코드가 AI Query에 그대로 전달되는지 확인한다.
3. IAC425는 IAC425 Evidence만, IAC606은 IAC606 Evidence만 반환해야 한다.
4. 교차 모델 검색 결과는 0건이어야 한다.
5. IAC425 위험 Case는 안전 판단 후 상담 경로를 확인한다.
6. IAC606 주의 Case는 실제 AI 안내와 자가 확인 경로를 검증한다.
7. Replay 시 Provider 추가 호출 0회와 같은 Correlation 연결을 확인한다.
8. 실제 G1-A·G1-B 증거 전에는 신규 모델 Runtime 활성 완료로 표시하지 않는다.

## 9. 남은 차단·주의사항

- 현재 PC의 PostgreSQL은 연결 Timeout이라 실제 DB 실행은 하지 못했다.
- 신규 Product 활성화는 격리 통합 DB에서만 명시적으로 수행한다.
- IAC606 후보의 안내 문장 분절은 Data 담당 검토 항목이며 Backend가 임의 결합하지 않는다.
- Candidate 2건은 기존 정식 369건과 합치거나 운영 데이터로 승격하지 않는다.
- 실제 AI 3모델 Runtime·50 Case·교차 모델 0건·독립 QA 전에는 전체 E2E PASS가 아니다.
- 기존 완료 Inquiry Delete·Reset·상태 직접 수정은 금지한다.

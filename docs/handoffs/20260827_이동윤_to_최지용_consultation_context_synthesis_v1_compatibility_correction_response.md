# Consultation Context Synthesis Handoff v1 호환성 정정 회신

- 작성일: 2026-08-27
- 발신: 이동윤
- 수신: 최지용
- 공동 검수 요청: 윤승혁(PM, Harness·Handoff)
- 회신 대상: Consultation Handoff `2.0.0` v1 호환성 보완 요청
- Branch: `dongyoon`
- 변경 전 기준 Commit:
  `18b26b6133bcbe4b145e88a711397d9d9a4f530e`
- 호환성 정정 Commit:
  `be456afa56f12c602f44f37336e89466263032c1`

---

## 1. 결론

요청한 v1 호환성 보완과 v2 강화 규칙 분리를 위 Commit에 반영했습니다.

기존 문제는 v1과 v2가 최상위 공통 `required`, `maxItems`, Safety Enum과
Evidence `page` 제약을 함께 사용해, v2용 강화 규칙이 기존 v1 요청에도
적용되는 구조였습니다. 이를 다음 두 독립 객체 Schema로 분리했습니다.

```text
#/$defs/v1Request
#/$defs/v2Request
```

현재 상태는 다음과 같습니다.

```text
correction_commit=be456afa56f12c602f44f37336e89466263032c1
v1_contract_compatibility=PASS_LOCAL_CONTRACT
v2_strict_constraints=PASS_LOCAL_CONTRACT
backend_v1_regression=PASS_SQLITE_TARGETED
contract_review=READY_FOR_REVIEW
contract_freeze_approved=NO
backend_v2_implementation=NOT_STARTED
ai_v2_external_mapper=NOT_STARTED
runtime_v2_e2e=NOT_RUN
status=HOLD_REVIEW_REQUIRED
```

이 회신은 수정된 Contract 후보와 Local 검증 결과입니다. 최지용 검수 전에는
Contract Freeze 승인 또는 Backend v2 구현 시작 승인으로 표시하지 않겠습니다.

---

## 2. 요청 사항별 반영 결과

| 요청 사항 | 반영 결과 |
| --- | --- |
| 기존 상담 인계 방식의 허용 범위 유지 | v1을 현재 AI·Backend 경계에 맞춘 독립 Schema로 분리 |
| 새 제한은 새 상담 인계 방식에만 적용 | 배열 필수화·개수 상한·Safety Enum·Evidence `page` 필수화를 v2에만 적용 |
| 기존 정상 요청 회귀 테스트 | v1 선택 필드 생략, 기존 경계 초과 개수, 자유 Safety 값, Evidence `page` 생략 허용 테스트 추가 |
| 새 방식 강화 제한 테스트 | 같은 입력을 v2에서 거절하고 v2 필수 배열 생략도 거절하는 테스트 추가 |
| 수정 계약과 검증 결과 전달 | 본 문서의 Commit과 5·6절에 고정 |

기존 `HARNESS_ESCALATE` AIRun Crosswalk, Human Review 거절 결속,
Handoff 재시도 정책과 `PRE_SEND_HUMAN_REVIEW` 금지는 이번 수정에서 변경하지
않았습니다.

---

## 3. v1에서 유지한 기존 허용 범위

v1은 현재 AI `ConsultationHandoffResult`와 Backend v1 Serializer가 처리하는
범위에 맞췄습니다.

### 선택 필드

다음 여섯 배열은 생략할 수 있으며 Backend가 빈 배열로 정규화합니다.

```text
questionnaire_answers
self_help_actions
evidence
safety_notes
consultant_priority_checks
source_chunk_ids
```

### 목록 개수

v1에는 다음 목록의 `maxItems`를 추가하지 않았습니다.

```text
questionnaire_answers
self_help_actions
evidence
safety_notes
consultant_priority_checks
source_chunk_ids
```

배열 항목 문자열 길이, UUID 형식, 알 수 없는 필드 금지와 Evidence Chunk
결속은 기존대로 유지합니다.

### Safety와 Evidence Page

- `safety_level`: 비어 있지 않은 50자 이하 문자열
- `evidence[].page`: 키 생략 또는 `null` 허용

현재 AI v1 Client는 `schema_version`을 보내지 않고 Backend가 `1.0.0`으로
정규화합니다. 명시적으로 보내는 경우에도 `1.0.0`만 v1로 인정하며, 다른 버전
표기를 v1로 추정하지 않습니다.

v1에는 v2 전용 필드인 `state_version`, `routing_reason`,
`context_synthesis`를 허용하지 않습니다.

---

## 4. v2에만 적용한 강화 규칙

| 항목 | v1 | v2 |
| --- | --- | --- |
| 배열 필드 6종 | 선택 | 모두 필수 |
| 문진 최대 개수 | 제한 없음 | 30 |
| 도움 행동 최대 개수 | 제한 없음 | 20 |
| Evidence 최대 개수 | 제한 없음 | 10 |
| 안전 메모 최대 개수 | 제한 없음 | 20 |
| 상담사 우선 확인 최대 개수 | 제한 없음 | 30 |
| Source Chunk ID 최대 개수 | 제한 없음 | 10 |
| `safety_level` | 50자 이하 문자열 | `general`, `caution`, `danger`, `unknown` |
| `evidence[].page` | 키 생략 가능 | 키 필수, 값은 `null` 허용 |

v2는 기존대로 다음 필드도 모두 필수입니다.

```text
schema_version=2.0.0
state_version>=1
routing_reason
context_synthesis=object|null
```

버전별 객체가 독립되어 있으므로 v1 payload에 `schema_version=2.0.0`만 붙여
v2로 재분류하거나, v2 payload를 `1.0.0`으로 낮춰 통과시키는 것도 거절합니다.

---

## 5. 추가한 회귀 테스트

수정 파일은 다음과 같습니다.

```text
contracts/ai/handoff/ConsultationHandoffRequest.schema.json
ai/tests/contract/test_consultation_handoff_contract_v2.py
contracts/ai/handoff/README.md
contracts/ai/README.md
contracts/ai/CHANGELOG.md
```

추가한 핵심 Case는 다음과 같습니다.

### v1 허용

- 배열 여섯 개를 모두 생략
- `safety_level=legacy_review_required`
- Evidence의 `page` 키 생략
- 문진 31개
- 도움 행동 21개
- Evidence와 Source Chunk ID 11개
- 안전 메모 21개
- 상담사 우선 확인 31개
- 명시적 `schema_version=1.0.0`

### v2 거절

- 위 목록 개수를 각각 v2 상한보다 한 개 초과
- v2 Enum에 없는 Safety 값
- Evidence의 `page` 키 생략
- v2 필수 배열 각각 생략
- v1 payload에 `schema_version=2.0.0`만 지정
- v2 payload를 `schema_version=1.0.0`으로 변경

---

## 6. 실행 검증 결과

실행 환경은 Python `3.13.13`입니다.

### Handoff·분석 Contract

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\contract\test_consultation_handoff_contract_v2.py ai\tests\contract\test_symptom_analysis_contract_v4.py -q
```

```text
56 passed in 0.76s
```

Handoff Contract 단독 결과는 `40 passed in 0.68s`입니다.

### AI Schema·Config Unit

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit\test_schemas_and_configs.py -q
```

```text
42 passed, 2 warnings in 0.95s
```

### AI 전체 Unit

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider ai\tests\unit -q
```

```text
668 passed, 4 warnings, 41 subtests passed in 25.98s
```

### 기존 Backend v1 Handoff API 회귀

```powershell
cd backend
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\api\test_ai_consultation_handoff_runtime.py -q
```

```text
6 passed, 1 skipped in 11.59s
```

SQLite 범위의 기존 저장·Replay·변경 payload 거절·PII/unknown-field 거절·식별자
검증·Rollback은 통과했습니다. PostgreSQL 동시 Row Lock Case 1건은 SQLite
환경이므로 기존 조건에 따라 `SKIPPED`입니다.

Backend Serializer를 저장 없이 직접 검증한 Read-only Probe에서도 다음 두
Case가 모두 `is_valid=True`였습니다.

```text
legacy-defaults=True
legacy-boundaries=True
```

- 선택 배열 전체 생략
- 자유 Safety 값
- `31/21/11/21/31/11` 목록 개수
- Evidence `page` 생략

이 Probe는 실제 DB 저장 또는 E2E 결과가 아니라 Backend v1 Serializer 허용
범위 확인입니다.

### 공통 Contract 검증

```text
Contract Example validation: PASS, API JSON examples 72
Root AI Contract Pytest: 23 passed
Root Contract Unit: 4 tests OK
Contract Crosswalk validation: PASS
git diff --check: PASS
```

---

## 7. 변경하지 않은 범위

이번 호환성 정정 Commit에서는 다음을 수정하지 않았습니다.

- Backend Serializer·Service·Model·Repository·Projection
- 윤승혁 소유 Harness·Handoff Runtime·Backend Client
- Handoff 예시 payload의 업무 의미
- AIRun Crosswalk와 Human Review 결속
- Backend 오류별 AI 재시도 정책
- `AI_HANDOFF_BACKEND_ENABLED`

따라서 현재 기존 v1 Runtime 동작에는 변경이 없으며, v2 외부 전송도 아직
활성화되지 않았습니다.

실제 AI v2 요청의 Backend HTTP 수신, PostgreSQL 저장, Replay, Consultation
연결과 상담사 Projection은 `NOT_RUN`입니다.

---

## 8. 검수 요청

Commit `be456afa56f12c602f44f37336e89466263032c1`에서 다음 항목을 확인해
주세요.

1. v1 선택 필드와 기존 목록 개수 범위가 유지됐는지
2. v1 Safety 값과 Evidence `page` 허용 범위가 유지됐는지
3. v2 강화 규칙이 `v2Request`에만 적용되는지
4. 동일 경계 입력의 v1 허용·v2 거절 테스트가 충분한지
5. 기존 Crosswalk·Human Review·재시도 정책이 그대로 유지됐는지

수정본이 승인되면 아래 순서로 진행하는 것이 맞습니다.

```text
Contract Freeze 승인
→ 최지용 Backend v2 Serializer·저장·Replay·Projection 구현
→ 윤승혁 AI v2 Mapper·Client allowlist·재시도 구현 및 검수
→ 양쪽 표적 회귀
→ 보호된 통합환경 동일 Inquiry E2E
→ 확인 후 AI_HANDOFF_BACKEND_ENABLED 활성 판단
```

---

## 9. 요청 회신 형식

```text
reviewed_contract_commit=be456afa56f12c602f44f37336e89466263032c1
contract_review=APPROVED | CHANGES_REQUIRED
v1_compatibility=APPROVED | CHANGES_REQUIRED
v2_strict_constraints=APPROVED | CHANGES_REQUIRED
compatibility_tests=APPROVED | CHANGES_REQUIRED
contract_freeze=APPROVED | HOLD
backend_implementation_start=YES | NO
requested_changes=<없음 또는 정확한 필드·규칙>
```

Contract 승인만으로 Runtime 연동 완료가 되는 것은 아닙니다. Backend 구현과
윤승혁 AI Client 구현 후 실제 동일 Inquiry E2E는 별도 Gate로 검증하겠습니다.

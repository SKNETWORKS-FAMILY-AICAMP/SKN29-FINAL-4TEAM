# D-03 Answerability/Capability Gate

> 상태: `IMPLEMENTED_TARGETED_TEST_COMPLETE`  
> 범위: 정적 JAC104 사용설명서로 답할 수 없는 질의를 Vector Search 전에 차단

## 결정

D-03은 검색 점수 Threshold 조정이 아니라 Query 범위와 제품 Capability를 함께
판정하는 명시적 Gate로 구현한다. Gate는 Gold Label이나 검색 결과를 입력으로 읽지
않으며 Query 문자열, 제품 모델 코드, 제품 세대만 사용한다.

| 범주 | Rule | 대상 Case | 처리 |
|---|---|---|---|
| 동적 계약·할인 | `GATE-COMMERCIAL-001` | `0051` | 검색 전 차단 |
| 동적 부품 가격·구매 | `GATE-PART-PRICE-001` | `0052` | 검색 전 차단 |
| 전체 판매 옵션·카탈로그 | `GATE-PRODUCT-CATALOG-001` | `0054` | 검색 전 차단 |
| JAC104 미지원 제빙 기능 | `GATE-JAC104-ICE-001` | `0056`~`0058` | 검색 전 차단 |
| 미지원 모델 | `GATE-MODEL-001` | `0059` | 기존 동작을 Gate 결정으로 유지 |

`0053`은 Gate 규칙을 억지로 추가하지 않고 기존처럼 검색 결과 0건과 상담 전환을
유지하는 통제 Case다. `0001`, `0013`, `0023`, `0031`은 Gate를 통과해야 한다.

## 실행 경로

Gate 차단 시 Embedding과 Vector Store Query를 모두 실행하지 않고 빈 검색 결과를
반환한다. 기존 Pipeline의 No-Evidence 분기가 이를 `PENDING_CONSULTATION`으로
전환한다. 차단 사유는 Rule ID, 범주, 실행 경로 코드로 재현할 수 있다.

## 변경 파일

- `ai/configs/retrieval_policy.yaml`: 운영 Gate와 모델별 Capability 설정
- `ai/app/retrieval/verification/answerability_capability_gate.py`: 판정 구현
- `ai/app/retrieval/search/vector_search.py`: 실제 검색 진입점 연결
- `ai/tests/unit/test_retrieval.py`: 표적 12건과 검색 미실행 회귀 검증

## 제한

- Threshold `0.4`는 변경하지 않는다.
- `0053`의 실시간 방문 상태를 일반화하는 규칙은 이번 표본만으로 추가하지 않는다.
- 현재 Capability Registry는 MVP 운영 대상인 `WPUJAC104DWH`만 포함한다.
- Gold 2인 검수 전 결과를 공식 성능으로 발표하지 않는다.

## 검증 결과

- 지정 회귀 Case `12/12 PASS`
- Gate 차단 시 Embedding·Vector Store 미호출 `PASS`
- Pipeline 상담 전환 `PASS`
- 기존 Full Corpus Baseline 단위 테스트 `8/8 PASS`
- `test_env`에서 신규 D-03 테스트 함수 3개를 직접 호출해 모두 통과했다.

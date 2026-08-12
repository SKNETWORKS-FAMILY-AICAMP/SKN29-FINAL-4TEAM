# D-01 Evidence Match Policy 평가 계약

> 반영일: 2026-08-11 KST  
> 상태: `IMPLEMENTATION_COMPLETE_BASELINE_RERUN_PENDING`

## 목적

Gold Dataset의 `evidence_match_policy`를 Runner가 실제 평가에 반영하도록 평가 계약을 고정한다. 이 변경은 평가 로직만 수정하며 Gold Dataset과 Corpus·Chunking 데이터는 변경하지 않는다.

## 정책별 판정

| 정책 | Hit·MRR 판정 | nDCG@5 | 비고 |
|---|---|---|---|
| `ANY` | 명시된 Evidence Unit 중 하나를 처음 찾은 순위 | 최초 충족 순위 기준 | 대체 가능한 근거 중 하나가 필요한 문항 |
| `ALL` | 서로 다른 모든 Evidence Unit을 누적해서 찾은 완료 순위 | `null` | 한 Chunk의 `evidence_unit_ids`에 필요한 ID가 모두 있으면 한 번에 충족 가능 |
| `NONE` | 검색 결과가 비었는지만 별도 진단 | 해당 없음 | D-03 Answerability Gate 전까지 정답률로 해석하지 않음 |

Evidence 관련성은 문서·페이지 문자열만으로 판정하지 않고, Chunk의 `evidence_unit_ids`와 Gold의 `evidence_unit_id`가 일치하는지를 함께 확인한다.

`ALL`의 MRR은 모든 필수 Evidence Unit이 처음 완성되는 순위의 역수로 정의한다. `ALL` nDCG는 다중 근거의 이상적 순위 정의를 별도로 합의하기 전까지 계산 대상에서 제외한다.

`NONE`의 기존 `no_evidence_accuracy` 값은 호환성을 위해 결과 Schema에 남기되, 의미는 검색 결과가 비었는지를 나타내는 진단값이다. 실제 답변 가능 여부 판정은 D-03에서 구현하며 현재 `answerability_gate_passed`는 `null`이다.

## 회귀 검증

다음 Gold Case를 고정 회귀 대상으로 사용한다.

* `0036`, `0037`: 필수 Evidence Unit 두 개를 모두 찾기 전에는 `ALL` 성공으로 판정하지 않는다.
* `0038`: 페이지 38 Chunk 하나가 필수 Evidence Unit 두 개를 모두 포함하면 Rank 1에서 `ALL` 성공으로 판정한다.
* `0004`: 현재 Gold에 명시되지 않은 페이지 5 Chunk를 관련 근거로 오인하지 않는다.
* `0051`: `NONE`은 빈 검색 결과 진단만 수행하고 Answerability Gate 결과는 생성하지 않는다.

관련 단위 테스트 21건을 기존 `test_env`에서 통과했다.

## 결과물 사용 제한과 재실행 조건

2026-08-10에 생성된 `full_corpus_baseline_v1` 결과는 D-01 적용 전 평가 계약으로 계산되었으므로 성능 비교에 사용하지 않는다. 다음 순서로 진행한다.

1. D-02에서 누수 관련 Gold 근거를 원문 이미지로 검수하고 Dataset Version·Hash를 갱신한다.
2. 확정된 Gold와 D-01 Runner로 동일 Profile을 다시 실행한다.
3. 재실행 결과부터 Draft 비교 기준으로 사용한다.

Gold 2인 검수와 IAC425 Positive 평가 문항 보강 전에는 재실행 결과도 공식 Phase B 수치로 승격하지 않는다.

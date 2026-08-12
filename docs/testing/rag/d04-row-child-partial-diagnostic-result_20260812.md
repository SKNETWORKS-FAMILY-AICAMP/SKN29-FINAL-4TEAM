# D04 행 단위 Parent·Child 부분 진단 결과

> 실행일: 2026-08-12 KST  
> 실행자: 이동윤 / AI·RAG  
> 기준 HEAD: `8b5bb6292e087fd15558f53c530b06653edc4d29`  
> 상태: `PARTIAL_SCOPE_DIAGNOSTIC_COMPLETE`  
> 운영 적용: `NOT_APPROVED`

## 1. 결론

행 단위 Child 검색은 이번 부분 DEV 진단에서 유효했다. 기존 페이지 기준선에서
Top-5 밖이었던 무출수 `0025`와 누수 `0027`을 각각 2위와 4위로 복구했고, 정상
통제 5건의 Hit@5·순위 회귀는 없었다.

반면 페이지 전체 Parent를 기본 Context로 확장하는 방식은 현재 형태로 채택하기
어렵다. Child-only보다 Context가 평균 484 whitespace token 늘었고, 16건 중 15건에
검색되지 않은 다른 Evidence Group이 함께 들어왔다. 38쪽 Parent가 선택된 12건에는
Child에서 제외한 미세입자 행도 다시 포함됐다.

```text
row_child_retrieval=PARTIALLY_SUPPORTED_ON_DRAFT_DEV
full_page_parent_context=NOT_SUPPORTED_AS_DEFAULT_PENDING_REDESIGN
full_corpus_v2=NOT_RUN
production_adoption=NOT_APPROVED
next_gate=HUMAN_CONTEXT_REVIEW_AND_BOUNDED_CONTEXT_DESIGN
```

즉, **행 단위 검색 구조는 다음 검증으로 진행할 근거가 생겼지만, 페이지 전체를
그대로 Parent Context로 붙이는 C안은 범위를 줄여 다시 설계해야 한다.**

## 2. 고정한 부분 실험 범위

- 영향 11건: `0004`, `0005`, `0007`, `0008`, `0021`, `0024`, `0025`,
  `0027`, `0036`, `0037`, `0038`
- 정상 통제 5건: `0001`, `0002`, `0003`, `0006`, `0009`
- 기준 Corpus: 기존 페이지 96건
- 부분 v2 Corpus: 대상 페이지 5건 제외 + Child 15건 = 106건
- 검색: BGE-M3 고정 Revision, 1024차원, Cosine Exact, Exact Product Filter,
  Top-K 5, Threshold 0.4
- 비교: `CURRENT_PAGE_V1`, `CHILD_ONLY_V2`,
  `CHILD_PARENT_CONTEXT_V2`

Case 목록과 판정 규칙은 결과를 보기 전에
`ai/configs/experiments/row_child_partial_v2.yaml`과 평가 계약에 고정했다.

### Full Corpus와 이번 부분 Corpus의 차이

여기서 **Full Corpus**는 평가 대상 제품의 공식 매뉴얼 원문 전체를 검색 후보로
보존한 데이터셋을 뜻한다. 현재 기준선인 Full Corpus v1은 다음과 같이 구성된다.

```text
JAC104 공식 매뉴얼 44쪽
+ IAC425 공식 매뉴얼 52쪽
= 페이지 Chunk 96건
```

이번 실험은 이 96건 전체를 행 단위로 다시 만든 것이 아니다. JAC104의
5·7·37·38·39쪽 페이지 Chunk 5건만 제외하고, 해당 페이지에서 선택한 Child 15건을
넣었다.

```text
기존 페이지 Chunk 96건
- 대상 페이지 Chunk 5건
+ 선택된 행 Child 15건
= 부분 진단 검색 후보 106건
```

검색 후보가 96건에서 106건으로 증가했어도 Full Corpus v2는 아니다. 5·7쪽의 다른
안전 문단과 38쪽 미세입자 행처럼, 제외한 페이지에 있었지만 Child로 만들지 않은
내용이 검색 후보에서 빠졌기 때문이다. 이번 106건은 `0025`·`0027` 등 지정 Case의
행 단위 분리 효과를 확인하기 위한 **부분 페이지 교체 Corpus**다.

| 구분 | 구성 | 사용 목적 | 현재 상태 |
|---|---|---|---|
| Full Corpus v1 | 공식 매뉴얼 96쪽을 페이지 단위로 보존 | 기존 B1 기준선 | 사용 중인 Draft 기준선 |
| 부분 진단 Corpus | v1의 지정 5쪽을 선택 Child 15건으로 부분 교체 | 행 단위 분리 가설 확인 | 이번 실험 완료 |
| Full Corpus v2 | 전체 검색 가능 원문을 Child 또는 보존 Chunk로 누락 없이 구성 | 전체 B1 재실행·운영 후보 비교 | 미생성·미실행 |

Full Corpus v2로 인정하려면 최소한 다음 조건이 필요하다.

1. 교체되는 모든 페이지의 검색 가능 원문이 Child 또는 보존 Chunk로 남아야 한다.
2. 각 Child는 Evidence Group 하나와 원본 Source Span으로 역추적돼야 한다.
3. 특정 Gold 질문에 필요한 행만 선택하지 않고 정상·무근거 질문에 필요한 후보도
   동일한 규칙으로 보존해야 한다.
4. JAC104뿐 아니라 기존 IAC425 범위와 제품 Filter 조건도 유지해야 한다.
5. 전체 Gold DEV, NO_EVIDENCE와 다른 제품 통제를 같은 검색 조건에서 재실행해야 한다.
6. 기존 Full Corpus v1과 Dataset·Corpus·Profile Hash가 기록된 새 Run ID로
   비교해야 한다.

따라서 이번 결과는 행 단위 Child 구조의 다음 검증을 진행할 근거지만, 전체 매뉴얼
검색 성능이나 운영 Corpus 개선을 증명하는 결과로 확대해서는 안 된다.

## 3. 검색 결과

| Variant | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 |
|---|---:|---:|---:|---:|---:|
| 기존 페이지 v1 | 0.500 | 0.875 | 0.875 | 0.6771 | 0.7326 |
| Child-only v2 | 0.625 | 0.875 | 1.000 | 0.7677 | 0.8807 |
| Child+Parent Context v2 | 0.625 | 0.875 | 1.000 | 0.7677 | 0.8807 |

두 v2 Variant는 동일 Child 검색 순위를 공유하므로 검색 지표가 동일하다. Parent는
정답 판정에 참여하지 않았다.

### 필수 Case

| Case | 기존 순위 | v2 순위 | 판정 |
|---|---:|---:|---|
| `0004` 누수 직접 질문 | 1 | 1 | 유지 |
| `0025` 무출수 구어체 | Top-5 밖 | 2 | 복구 |
| `0027` 바닥 누수 구어체 | Top-5 밖 | 4 | 복구 |
| `0036` 냉수+저출수 `ALL` | Completion 3 | Completion 3 | 유지 |
| `0037` 누수+소음 `ALL` | Completion 2 | Completion 2 | 유지 |
| `0038` 냄새+저출수 `ALL` | Completion 1 | Completion 2 | Hit@5 유지, 순위 1단계 회귀 |

### 전체 선택 Case의 순위 변화

- 개선: `0005`, `0007`, `0008`, `0025`, `0027`
- Hit@5 복구: `0025`, `0027`
- Hit@5 회귀: 0건
- 정상 통제 Hit@5·순위 회귀: 0건
- 영향 Case 순위 회귀: `0021` 2→5, `0038` 1→2

따라서 평균 지표만 보고 전체 성공으로 판정하지 않는다. `0021`은 Top-5 경계까지
밀렸으므로 Full Corpus v2에서 반드시 다시 확인해야 한다.

## 4. Parent Context 결과

| 항목 | 결과 |
|---|---:|
| Child-only 평균 Context | 342.2 whitespace token |
| Parent 확장 평균 Context | 825.9 whitespace token |
| 평균 증가량 | +483.7 whitespace token |
| 평균 배율 | 2.833배 |
| 최대 증가량 | +800 token |
| 다른 Evidence Group 유입 | 15/16 Case |
| 제외한 미세입자 행 유입 | 12/16 Case |
| Parent 확장 처리 p95 | 0.0152ms |

처리 시간은 작지만 실제 문제는 Token 양과 문맥 혼합이다. Parent가 페이지 전체라서
행 단위 검색으로 제거한 다른 증상과 제외 행이 생성 Context에서 다시 합쳐진다.
이는 `ALL` 검색 평가는 오염시키지 않지만 이후 답변 관련성과 안전 안내 집중도를
낮출 수 있다.

현재 Runtime은 Template 기반이고 이번 Runner는 답변 생성을 수행하지 않으므로,
Parent Context의 답변 품질은 자동 PASS로 확정하지 않았다. 최종 Gate는
`PENDING_HUMAN_CONTEXT_REVIEW`다.

## 5. 해석과 다음 결정

이번 결과가 지지하는 것은 **행 단위 Child를 검색 단위로 사용하는 방향**이다.
다음은 아직 지지하지 않는다.

- 페이지 전체 Parent를 항상 생성 Context로 전달
- 지정 15개 Child만으로 Full Corpus v2 구성
- `parent_child_v2` 운영 Profile 채택
- 전체 제품·전체 Gold 성능 개선 주장

다음 실험에서는 전체 페이지 Parent 대신 아래 후보를 비교해야 한다.

1. 검색된 Child만 전달
2. 같은 Evidence Group의 인접 행 또는 안전 문단만 확장
3. `source_span` 주변의 제한된 범위만 확장

안전 경고가 있는 5·7쪽은 경고 문단 전체를 유지하되, 37~39쪽 표는 검색된 행과
필요한 헤더·연속 조치만 제한적으로 확장하는 방안이 우선 후보다.

그 후 Data 측에서 5개 페이지의 검색 가능 내용을 누락 없이 Child로 보존한 Full
Corpus v2를 만들고, Gold DEV 전체와 NO_EVIDENCE 통제를 포함해 B1을 재실행해야 한다.

## 6. 실행·검증 증거

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_row_child_partial_experiment_v2.py -q -p no:cacheprovider

.\ai\.venv\Scripts\python.exe `
  -m ai.scripts.run_row_child_partial_experiment_v2 `
  --allow-draft-gold
```

- Adapter 단위 테스트: `2 passed`
- AI 전체 단위 테스트: `174 passed, 3 warnings, 7 subtests passed`
- `pip check`: PASS
- `git diff --check`: PASS
- 실제 모델 첫 실행: Exit `0`, 약 154초, v2 임베딩 Cache 생성
- Cache 재실행: Exit `0`, 약 8초
- Python: `3.13.13`
- 결과: 3 Variant × 16 Case = 48개
- Child-only와 Parent Context 검색 순위 Parity: PASS

결과 파일 SHA-256:

| 파일 | SHA-256 |
|---|---|
| `preflight.json` | `58C9BFF62D90E2983B2F3C296B5CBBDBFE1B5BFE743E50420DD7B3EDE3910F65` |
| `manifest.json` | `B446052DFCA45E86EAF3D02B6BE0233BA8F1B5A7309F8B59D3ADAA4ACCF28806` |
| `summary.json` | `2503577DE8695511562DEAE98B9F75709AE502C72B0575BFB48BD9D6F63F900A` |
| `case_results.jsonl` | `7F12E6A507D65BBFB0A2B6C5195FA6A26A7888CDE477BFFEF3759EC3B4570FBD` |

위 Hash는 최종 Adapter 보강 후 Cache 재실행한 현재 산출물 기준이다.

## 7. 제한

- Gold는 `UNREVIEWED_DRAFT`이며 공식 성능 수치가 아니다.
- 선택된 16건은 JAC104의 7개 Evidence Group에 한정된다.
- 부분 v2는 대상 페이지의 모든 검색 가능 행을 보존하지 않는다.
- NO_EVIDENCE, 다른 제품과 전체 DEV는 이번 실행 범위가 아니다.
- 실행 당시 작업 트리는 실험 코드·문서 변경으로 Dirty였고 Manifest에 그대로
  기록했다.

# D04 행 단위 Parent·Child 부분 진단 평가 계약

> 버전: `2.0.0-draft.1`  
> 상태: `PARTIAL_SCOPE_DIAGNOSTIC`  
> 적용 범위: experimental v2 Adapter와 선택된 DEV 16건

## 목적

행 단위 Child가 기존 페이지 Chunk의 검색 희석을 줄이는지 확인하고, 선택된 Child의
페이지 Parent를 답변 Context로 확장할 때 발생하는 문맥 범위와 비용을 측정한다.
전체 매뉴얼 청킹 성능이나 운영 Profile을 결정하는 실험은 아니다.

## 고정 Case

- 영향 11건: `0004`, `0005`, `0007`, `0008`, `0021`, `0024`, `0025`,
  `0027`, `0036`, `0037`, `0038`
- 정상 통제 5건: `0001`, `0002`, `0003`, `0006`, `0009`
- 필수 집중 검수: `0004`, `0025`, `0027`, `0036`, `0037`, `0038`

영향 Case는 실행 결과를 보기 전에 고정한다. 필수 6건에 과거 B1에서 Profile에 따라
순위·판정이 달라진 대표 Case 5건을 추가했다. 정상 통제는 과거 Exact Filter의 모든
Profile에서 Hit@1이었던 직접 질문으로 고정한다.

## Corpus와 검색 규칙

- 기준선: Full Corpus v1 페이지 96건
- 부분 v2: 기준선에서 JAC104의 5·7·37·38·39쪽 5건을 제외하고 Child 15건을
  추가한 106건
- 검색: BGE-M3 고정 Revision, Cosine Exact, Exact Product Filter, Top-K 5,
  Threshold 0.4
- 검색·Top-K·Hit·MRR·`ANY`·`ALL`: Child 또는 기존 검색 Chunk만 사용
- Parent: 검색 후보와 정답 판정에서 제외

부분 v2는 지정 페이지에서 Child로 만들지 않은 행을 검색 후보로 보존하지 않는다.
따라서 결과 상태는 항상 `PARTIAL_SCOPE_DIAGNOSTIC`이며 Full Corpus v2로 부르지
않는다.

## 비교 Variant

1. `CURRENT_PAGE_V1`: 기존 Full Corpus 페이지 기준선
2. `CHILD_ONLY_V2`: 부분 교체 Corpus의 Child 검색 결과만 사용
3. `CHILD_PARENT_CONTEXT_V2`: `CHILD_ONLY_V2`와 동일한 검색 순위를 사용하고
   선택된 Child의 Parent만 중복 제거해 Context로 확장

두 v2 Variant의 검색 Chunk ID, 순위, Score와 검색 지표는 같아야 한다. Parent 확장은
Context Token, 문자 수, 지연시간, 추가 Evidence Group과 제외된 미세입자 문맥 포함
여부만 별도로 기록한다.

## 판정 제한

- 정상 통제 Hit@5 회귀가 있으면 v2 승격 후보로 보지 않는다.
- `0025`·`0027` 복구와 `0036`~`0038` Completion Rank를 별도 보고한다.
- Parent Context 관련성과 안전 문구 보존은 자동 확정하지 않고 사람 검수로 남긴다.
- Gold 2인 검수, 전체 검색 가능 행 보존과 Full Corpus v2 재실행 전에는 운영 적용을
  승인하지 않는다.

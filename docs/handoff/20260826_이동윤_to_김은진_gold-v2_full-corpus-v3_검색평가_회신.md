# Gold v2·Full Corpus v3 검색평가 회신

> 보내는 사람: 이동윤 — AI·RAG·Evaluation
>
> 받는 사람: 김은진 — Data·QA
>
> Branch: `dongyoon`
>
> 상태: `LOCAL_DIAGNOSTIC_COMPLETE_HUMAN_SIGNOFF_PENDING`

## 한 줄 요약

Gold와 Corpus 연결 및 검색 수정은 모두 확인됐으며, 답변용 Child만 검색하는 기준에서 필수 근거 Hit@5 100%를 확인했습니다.

## 검수 및 수정 결과

김은진님이 전달한 Full Corpus v3와 새 Gold의 연결을 다시 확인했습니다. Gold 60건 중 55건은 평가 대상으로 유지했고, 근거 범위를 확정하기 어려운 `0017`, `0033`, `0040`, `0043`, `0047`은 삭제하지 않고 제외 상태로 보존했습니다. 현재 Gold 버전은 `2.0.0-draft.2`이며 모든 항목은 아직 `UNREVIEWED_DRAFT`입니다.

Gold에서 요구하는 필수·보조 Evidence Group과 Corpus의 Child 연결은 오류 없이 통과했습니다. IAC425 후보 18건도 필요한 근거와 모두 연결됐지만, Main Gold에는 아직 넣지 않았습니다.

검색에서는 Source Page와 Preservation이 답변용 Child의 순위를 밀어내는 문제가 확인돼 역할을 다음과 같이 분리했습니다.

- `CHILD`는 1차 검색과 Gold 채점에 사용합니다.
- `SOURCE_PAGE`는 Child가 검색된 뒤 인용과 문맥 보강에 사용합니다.
- `PRESERVATION`은 계보와 재생성 QA에만 사용합니다.

LOW-FLOW 질문인 `0013`, `0020`, `0023`은 고객 문장을 바꾸지 않고 임베딩 질의에만 “출수량이 적음” 의미를 보조하도록 수정했습니다. 세 질문 모두 Top-1에서 필수 근거를 찾았습니다. 완전히 물이 나오지 않는 표현은 LOW-FLOW로 잘못 분류하지 않도록 별도로 차단했습니다.

월 렌탈료·필터 가격·기사 도착시간·판매 색상을 묻는 `0051~0054`는 정적 매뉴얼 검색 대상이 아니므로 Vector 검색 전에 범위 밖 질문으로 차단하도록 정리했습니다. 미검증 FAQ와 미지원 기능·제품을 묻는 `0055~0060`도 Gold의 기대 경로와 실제 검색 정책이 일치하는 것을 확인했습니다.

## 검색 결과

BGE-M3 Local Dense, Exact 제품 필터, `top_k=5`, threshold `0.4` 조건에서 평가했습니다.

- 필수 근거가 있는 45건 모두 Top-5 안에서 정답 Evidence Group을 찾았습니다.
- LOW-FLOW 3건은 모두 Top-1로 회복됐습니다.
- 정책 차단 10건은 모두 Vector 호출 없이 차단됐습니다.
- 다른 제품, 비 Child, 미검증 근거가 섞인 결과는 0건이었습니다.
- MRR은 `0.788519`입니다.

보조 근거는 8건 중 7건이 함께 검색됐습니다. `0030`의 필수 근거는 정상 적중했지만 선택 사항인 보조 근거 한 건은 Top-5에 포함되지 않았습니다.

AI 전체 단위 테스트는 `603 passed, 4 warnings, 41 subtests passed`로 통과했고, Gold–Corpus 연결 검사도 오류 0건으로 통과했습니다.

## 최종 확인 요청

아래 내용을 승인하거나 반려해 주세요.

1. Main Gold의 `ACTIVE 55 / EXCLUDED 5` 구성
2. `0045`의 실제 누수 대응 근거와 `0049`의 필수·보조 근거 구분
3. 상담 조건 10개와 Source Child 연결
4. IAC425 후보 18건의 라벨 및 Main Gold 편입 여부
5. `CHILD=검색`, `SOURCE_PAGE=문맥 보강`, `PRESERVATION=QA` 역할 구분

이번 결과는 로컬 검색 진단입니다. 실제 pgvector·Provider·Backend 연동은 아직 실행하지 않았으며, 사람 최종 승인 전에는 `TWO_PERSON_APPROVED`, 공식 Gold 또는 Full B1 완료로 표시하지 않겠습니다.

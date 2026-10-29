# 실습 03 — 임베딩 검색 vs BM25 vs 단어 겹침

## 목적

- **가설:** BM25는 `조리수를`과 `조리수`, `물줄기`와 `출수량`처럼 표현이 다르면 근거를 놓칠 수 있다. 의미를 벡터로 나타내는 임베딩 검색은 이런 질문에서 유리할 수 있다.
- **공정한 비교:** 실습 02의 **같은 8개 문단, 같은 10개 질문, 같은 정답, 같은 Top-K=3**을 유지한다. 실제 정답은 결과 평가에만 사용한다.
- **실험 규모:** 원본 PDF를 직접 검증하지 않은 사용자 발췌 3개 절을 나눈 8개 문단·연관 질문 10개. **실서비스 품질의 정량 평가로 쓰지 않는다.**

## 파일 설치

`WaterBridge_임베딩검색_실습03.zip`의 `portfolio_upgrade/`를 기존 레포지토리 루트에 병합한다. **실습 01·02를 이미 설치한 상태여야 한다.** 기존 파일은 덮어쓰지 않는다.

`C:\SKN projects\final` 기준 **Windows CMD**:

```cmd
cd /d "C:\SKN projects\final"
python -m pip show sentence-transformers
```

모듈이 없으면 사용 중인 가상환경에서 아래 명령으로 설치한다:

```cmd
python -m pip install sentence-transformers
```

실제 모델은 첫 실행 시 Hugging Face에서 다운로드된다. 다운로드가 불가능한 환경에서는 실행되지 않으므로 결과 숫자를 만들어내지 않는다.

## 실행

```cmd
python portfolio_upgrade\src\compare_search_step03.py --demo
```

기본 모델은 `intfloat/multilingual-e5-small`이다. 모델 설명서에 따라 문서에 `passage: `, 질문에 `query: ` 접두어를 붙인다. 벡터를 정규화한 후 내적을 계산하면 코사인 유사도와 같다.

개별 질문의 상위 검색 결과:

```cmd
python portfolio_upgrade\src\compare_search_step03.py --query "조리수를 같이 쓰고 있는데 정수기 물줄기가 약해졌어요"
```

기존 WaterBridge의 임베딩 모델인 **BGE-M3**로도 비교할 수 있다(모델 다운로드 크기 및 CPU 실행 시간이 증가할 수 있음):

```cmd
python portfolio_upgrade\src\compare_search_step03.py --demo --model bge-m3 --out portfolio_upgrade\experiments\step03\bge_m3_comparison.json
```

테스트는 사전학습 모델을 다운로드하지 않는 **FakeModel**로 벡터 순위 계산 부분만 확인한다:

```cmd
python -m unittest discover -s portfolio_upgrade\tests -p "test_search_step03.py" -v
```

## 실행 이후 확인할 것

1. **Q007:** BM25는 검색 결과가 없었는데, 임베딩은 `WB-S02-005`를 찾았는가? **아직 모름. 실행 결과로 확인할 가설.**
2. **Q008과 Q009:** BM25가 맞힌 질문을 임베딩 검색도 맞혔는가? 임베딩이 더 좋다고 단정하지 않는다.
3. **Q001/Q002:** 비슷하지만 다른 증상(`전혀 안 나옴` vs `조금씩 나옴`)을 구별했는가?
4. **Q003/Q010:** 누수 관련 질문을 `WB-S02-008`로 연결했는가? Q003/Q010은 서로 연관된 표현 변형임을 표시한다.
5. 비교 결과는 `portfolio_upgrade/experiments/step03/embedding_comparison.json`에 기록된다. **실제 실행에서만 생성된다.**

## 모델 주의사항

- 모델은 **학습되지 않은 사전학습 모델**이다. 이 실습에서 직접 파인튜닝하지 않는다.
- BM25/Overlap과 임베딩의 **점수 크기**를 직접 비교하면 안 된다. 점수 단위가 달라 순위와 품질 지표를 비교해야 한다.
- 8개 문단으로는 `Hit@5`가 정보를 거의 주지 않는다. 우선 `Hit@1`, `Hit@3`, `MRR@3`를 사용한다.
- 이번 10문항은 독립·블라인드 평가가 아니라, 검색 방식을 이해하기 위한 **작은 학습용 실험**이다.
- 모델마다 전처리 규약이 다르다. 이번 E5에는 query/passsage 접두어가 필요하다. BGE-M3에는 접두어를 넣지 않는다.
- BGE-M3와 E5-small의 비교는 학습·모델 크기·학습 목적 등이 달라 **임베딩 검색이라는 기법 자체의 효과**와 모델 간 차이를 분리하지 못한다.

## 이번 실습 뒤 정리할 내용

| 문제 | 해결 가설 | 검증 항목 | 선택 이유 |
|---|---|---|---|
| 키워드 불일치로 정답 미검색(Q007) | 임베딩이 문장 의미를 반영한다 | Q007의 `Hit@1`, `MRR@3` | 동일 질문에서 직접 비교 |
| 비슷하지만 다른 증상(Q001/Q002) | 의미 검색이 지나치게 묶을 수 있다 | 완전 미출수/저출수 혼동 여부 | 단순 점수 개선보다 원인 설명 |
| 기존 BM25 정답(Q008/Q009) | 임베딩이 정답을 놓칠 수도 있다 | BM25 대비 개선·퇴행 건수 | 기술의 장단점 확인 |

### 면접 대비 한 문장

> "BM25가 조사가 붙거나 증상 표현이 다른 문장을 놓치는 현상을 확인해, 동일 문서·질문에서 사전학습 임베딩 검색을 대조했습니다. 일부 문제의 개선 여부뿐 아니라 BM25가 맞혔던 사례의 퇴행까지 검증했습니다."

실제 수치는 `embedding_comparison.json`을 생성한 뒤 작성한다.

# WaterBridge — 개인 AI 고도화

팀 프로젝트 WaterBridge를 기반으로, **설명할 수 있는 기술적 선택과 정량 검증**을 축적하는 개인 개발 영역입니다. `main`의 기존 코드와 결과는 보존하고 `seunghyuk` 브랜치에서 진행합니다.

**현재 진행:** **S01~S04 완료(단, S04는 30건 파일럿 평가자료 구축)**, S05 예비 RAG/Oracle 응답 실험 준비. S04의 16건 Gold 수정은 개인 평가자료에 제안되었고 팀 원본에는 미반영입니다.

## 주요 문서 — 세 개만 유지

| 문서 | 역할 |
|---|---|
| **README.md** | 현재 위치, 실행 방법, 파일 안내(이 문서) |
| **docs/plan_v4.md** | S01~S25 단계별 계획, 기술 목표 및 통과 조건 |
| **notes/week01.md** | 1주차의 원문 검증·실험·오류·판단·회고를 합친 단일 기록 |

이후 실습은 **notes/week02.md, week03.md**처럼 해당 주차 파일에 절을 추가합니다. 별도의 `실습안내.md`, `진행기록.md`, `addendum.md`, `회고초안.md`를 반복 생산하지 않습니다. 다른 개발자에게 별도 명세가 꼭 필요한 API 계약이나 시스템 설계만 새 문서로 만듭니다.

## 실제 작업 파일

- **src/** — 단어 겹침, BM25, E5 임베딩, RRF 순위 결합을 검증하는 코드.
- **scripts/** — 검색 성능 평가기. 새 기능은 동일한 역할의 코드부터 확장합니다.
- **tests/** — 직접 이해한 요구사항으로 작성한 소규모 테스트.
- **data/** — 실습 말뭉치, Gold JSON, 공식 출처 및 검증 메타데이터.
- **experiments/** — 문항별 원시 결과 JSON과 실행 근거. 재생성되는 요약 Markdown은 Git 기록에서 제외합니다.

현재 검색 실습 02/03 코드는 `data/mini_corpus_step02.json` 및 `data/gold/mini10_gold_step02.json`을 사용합니다. `*_verified_v03.json`은 **원문 대조 결과와 필드 수정이 반영된 별도 검증판**으로, 기존 실험 재현성을 위해 원본을 아직 유지합니다. 이 관계를 이해하기 전에는 데이터를 일괄 삭제하거나 이름을 바꾸지 않습니다.

## 재현 (Windows CMD, 저장소 루트)

    python portfolio_upgrade\src\keyword_search.py --demo
    python portfolio_upgrade\src\compare_search_step02.py --demo
    python portfolio_upgrade\src\compare_search_step03.py --demo
    python portfolio_upgrade\scripts\evaluate_mini.py
    python portfolio_upgrade\scripts\compare_rrf_step05.py
    python -m unittest discover -s portfolio_upgrade\tests -v

임베딩 실습은 모델을 처음 불러올 때 인터넷 연결과 설치된 라이브러리가 필요할 수 있습니다. 문항별 결과를 확인하려면 `experiments/step03/embedding_comparison.json` 및 `experiments/step04/metrics_recomputed.json`을 참고하세요.

## 문서 작성 규칙

1. 새 문서를 만들기 전에 **README / 계획 / 해당 주차 기록**에 합칠 수 있는지 먼저 확인합니다.
2. 각 세션의 문제·선택 이유·실행·실패 사례·측정값·배운 점은 **주차별 기록의 한 절**로 합칩니다.
3. 코드·테스트·학습 데이터·Gold·원시 실험 결과는 **별도 파일로 보존**합니다. 재현성에 필요한 증거까지 한 파일로 압축하지 않습니다.
4. 실제 비교가 끝나지 않은 기술은 ‘계획/가설’로, 사용자 PC에서 나온 값은 ‘사용자가 실행해 제출한 결과’로, 검토한 원문은 ‘검증 근거’로 구분합니다.
5. 오래된 문서의 내용을 꼭 복구해야 한다면 Git 이력에서 확인합니다. **문서 개수는 산출물 성과가 아닙니다.**

**최종 목표:** 공식 근거를 활용하는 고객지원 모델 학습 실험, 실제 도구 호출 Agent, 자체 모델 서빙을 통해 **문제 → 대안 비교 → 구현 → 수치 → 채택 이유**를 설명할 수 있는 포트폴리오.

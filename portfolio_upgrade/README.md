# WaterBridge — 개인 AI 고도화

팀 프로젝트 WaterBridge를 기반으로, **설명할 수 있는 기술적 선택과 정량 검증**을 축적하는 개인 개발 영역입니다. `main`의 기존 코드와 결과는 보존하고 `seunghyuk` 브랜치에서 진행합니다.

**현재 진행:** **M0(S01~S02) 완료, M1(S03~S05) 오프라인 파일럿 실험 종료·복습 진행 중**. S04는 합성 데이터 30건의 파일럿 검수(16개 그룹·18/6/6 분할), S05는 Dev 6건 비교입니다. 독립 최종 성능·실제 WaterBridge E2E 검증·SFT는 아직 아닙니다.

## 학습 자료 — 개요 + M0 + M1

| 문서 | 언제 읽는가? |
|---|---|
| **[notes/overview.md](notes/overview.md)** | RAG 전체 흐름, 용어, 공부 순서 |
| **[notes/M0.md](notes/M0.md)** | S01·S02: Overlap, BM25, E5, Hit/MRR, RRF, 실패 문항 |
| **[notes/M1.md](notes/M1.md)** | S03·S04·S05: 기존 코드 흐름, 데이터 누출과 분할, Oracle vs 검색/안전 라우팅 RAG |
| **[docs/plan_v4.md](docs/plan_v4.md)** | S01~S25 전체 목표와 이후 M2~ 학습/Agent/서빙 계획 |

**학습 원칙:** 먼저 한 단계의 개념·실험을 본인 말로 설명하고, 다음 단계로 이동합니다. S05의 **오프라인 파일럿은 종료**했지만 M1 복습 후 M2에 진입하며, 파일럿 수치를 실서비스 성능으로 표현하지 않습니다. 이전 `week01.md`는 Git 이력에서 볼 수 있는 통합본입니다.

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

1. **개요·M0·M1 문서를 기준**으로 같은 마일스톤의 개념·실험·오류·결정을 모읍니다. 새 학습 내용은 해당 마일스톤 문서의 절을 갱신합니다.
2. **코드, 원시 실험 로그, Gold/분할 데이터, 자동 테스트는 별도 파일로 유지**합니다. 문서 파일 수가 성과는 아닙니다.
3. **팀 원본 코드·데이터와 개인 오프라인 실험을 분리**합니다. 재현 가능한 실행 근거가 없는 성능·서비스 적용을 주장하지 않습니다.
4. 정답 근거가 있어도 **안내 조건을 잘못 해석하거나 무관한 출처를 인용**할 수 있으므로 행동 분류뿐 아니라 안내 내용도 평가합니다.
5. 앞으로 M2에 들어가기 전에 **M0~M1을 직접 설명할 수 있게 복습**합니다.

**최종 목표:** 공식 근거를 활용하는 고객지원 모델 학습 실험, 실제 도구 호출 Agent, 자체 모델 서빙을 통해 **문제 → 대안 비교 → 구현 → 수치 → 채택 이유**를 설명할 수 있는 포트폴리오.

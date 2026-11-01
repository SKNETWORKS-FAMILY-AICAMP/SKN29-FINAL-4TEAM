# WaterBridge — 개인 AI 고도화 (학습·실험 저장소)

> **기준 커밋:** `seunghyuk` / `392dfaca` (2026-10-31). 팀 프로젝트의 기존 코드와 결과는 보존하고 `portfolio_upgrade/`에서 개인 실험을 진행한다. 여기 적힌 수치는 **교육·포트폴리오용 오프라인 파일럿**이며 실제 고객 응대 운영 성능이 아니다.

## 지금 어디까지 진행했나?

| 묶음 | 실험 | 현재 상태 |
|---|---|---|
| **M0** | S01 Overlap/BM25/E5, S02 RRF | 소규모 검색 실습 종료, 실사용 검색기 채택 보류 |
| **M1** | S03 코드 추적, S04 공식 PDF·분할, S05 Oracle/일반/안전 라우팅 | 코드·오프라인 Dev 파일럿 종료, 독립 성능·E2E는 미검증 |
| **M2** | S06 정답 검수, S07 재표현, S08 Qwen3 B0/B1, S09 모델·검색 입력 점검 | **설계·진단 파일럿 종료, 복습 단계** |
| **M3 이후** | LoRA/QLoRA SFT, Tool-use Agent, vLLM 서빙, 독립 평가 | **아직 미실행** |

**중요:** S07 학습 초안은 26문장이지만 **13개 원본·6개 의미 그룹**에서 파생됐다. S09에서 검색 근거를 26/26 연결했어도 일부 필수 근거가 부족하고 **학습 데이터 사용 범위가 미확정**이므로 `training_ready=0`이다. **SFT 학습이나 성능 개선을 달성했다고 주장하지 않는다.**

## 공부용 문서 — 이 순서대로 읽기

| 문서 | 읽고 답할 질문 |
|---|---|
| **[notes/overview.md](notes/overview.md)** | 전체 작업이 어떻게 연결되고, 왜 M2가 SFT를 위한 준비 단계인가? |
| **[notes/M0.md](notes/M0.md)** | Overlap/BM25/E5와 RRF는 무엇을 개선했고 무엇을 놓쳤나? |
| **[notes/M1.md](notes/M1.md)** | 질문 분류·검색·근거 적용·정책 오류는 어떻게 구분하나? |
| **[S04 분할표 읽기 가이드](data/splits/S04_분할표_읽기_가이드.md)** | 30건의 고객 발화와 `semantic_group_id`가 실제로 무엇인가? |
| **[notes/M2.md](notes/M2.md)** | 정답 라벨·재표현·검색 근거·학습 전 Qwen3 결과가 어떻게 연결되나? |
| **[docs/plan_v4.md](docs/plan_v4.md)** | M3 이후 해야 할 실제 학습/Agent/서빙 과제와 GO 조건은? |

각 실험은 **0. 한눈에 보기 → 1. 정의 → 2. 목적 → 3. 과정·기술적 판단 → 4. 결과·증거 → 5. 해석·결론** 순서다. 처음에는 **0·1·2·5번을 먼저 읽고**, 다음에 원리·코드(3), 실제 JSON·CSV(4)를 확인한다.

## 바로 확인할 대표 증거

| 단계 | 중요한 원시 증거 | 핵심 결과 |
|---|---|---|
| S01·S02 | `experiments/step04/metrics_recomputed.json`, `experiments/step05_rrf/rrf_comparison.json` | E5 Hit@3 8/10, RRF 9/10, Q008 정답 퇴행 |
| S04 | `data/splits/s04_reviewed_pilot_split_v2.csv` | Train/Dev/Holdout 18/6/6, 16개 의미 그룹 |
| S05 | `experiments/s05_retrieval/`의 BGE·safe_routing JSONL | Gold Hit@5 3/5→5/5, 답변 조건 오류는 남음 |
| S06·S07 | `data/training/s06_review_cards.md`, `train_draft_s07_reviewed_v1.jsonl` | PDF 검수 15건, 보류 2건, 재표현 포함 26건 |
| S08 | `experiments/s08_baseline/s08_b0_b1_human_review.json` | Qwen3 JSON 3/6→6/6, 행동 정답 1/6→1/6 |
| S09 | `experiments/m2_training_readiness/m2_retrieval_review_26.json` | Gold 하나 이상 26/26, 모두 포함 25/26; 학습 미승인 |

표의 `experiments/`·`data/`는 **이 `portfolio_upgrade/` 폴더 아래 상대경로**다. `notes/` 문서에는 저장소 최상위 기준의 전체 경로가 따로 적혀 있다. `.jsonl`은 한 줄에 한 JSON 객체를 둔 형식이다.

## 현재 바로 할 작업

**새 명령어 실행보다 M0→M1→M2의 내용 복습이 우선**이다. 이후 M3 첫 파일럿의 진입 조건(GO)을 점검해야 한다: 공식 매뉴얼 유래 데이터 이용 가능 범위, 부족한 검색/인용 근거 보강, **검색 근거가 포함된 전체 토큰 길이** 측정, 충분한 독립 Train 시나리오 확대, Dev/Holdout 분리 및 동일 기반 모델 비교.

## 파일 관리 원칙

- `src/` 검색 구현, `scripts/` 실행·검증, `tests/` 단위 테스트, `data/` 공식 출처 및 정답/분할, `experiments/` 원시 실행 결과, `notes/` 학습 교재로 구분한다.
- **팀 원본/개인 오프라인 실험/실제 서비스 적용**을 구분한다. 기존 원시 JSONL·CSV·코드는 문서 개편 과정에서 수정하지 않는다.
- S05는 **GPT-4.1-mini**의 Dev 비교, S08은 **학습하지 않은 Qwen3-1.7B**의 B0/B1 비교다. 두 수치를 'SFT 학습 전후'라고 비교하지 않는다.
- 검색 성공(Hit@K), 행동 일치, 필수 조치 충족, 인용의 적합성, JSON 형식은 별도 지표다.
- 데이터 생성/검증의 실행 경로와 직접 측정하지 않은 미래 성과는 분리해 기록한다.

**최종 목표:** 근거에 충실한 고객 응대 모델의 직접 학습 실험, 실제 도구 호출 Agent, 자체 모델 서빙을 검증하고 **문제 → 대안 → 구현 → 측정 → 선택의 이유**를 면접에서 설명하는 것.

# 데이터 디렉터리 안내

## 적용 모델

| 역할 | 모델 | 적용 원칙 |
|---|---|---|
| 기본 MVP | `WPUJAC104DWH` / `WPU-JAC104D` 계열 | 공식 REV.00 매뉴얼과 모델 계열 직접 FAQ를 우선 사용 |
| 후속 확장 | `WPUIAC425SNW` / `WPU-IAC425` 계열 | 기본 MVP 완료 후 얼음 특화 시나리오에만 추가 |
| 사용 중단 | `WPU-IAC506` | `archive/` 이력 확인용이며 신규 RAG·합성·UI 구현에 사용 금지 |

## 표준 구조

```text
data/
├── raw/                         # 공식 원문, Git 제외
├── processed/
│   ├── documents/              # 매뉴얼 페이지 추출본
│   ├── metadata/               # 출처·로그·품질·오류·정책
│   └── structured/             # 검증된 RAG·FAQ 후보
├── synthetic/                  # 개인정보 없는 JAC104 시연 데이터
├── reports/                    # PM 결정과 최종 수집 보고서
├── handoff_guides/             # 팀원별 GitHub 데이터 확인 가이드
└── archive/WPU-IAC506_20260720 # 폐기 모델의 이전 산출물 이력
```

## 사용 우선순위

1. `processed/structured/rag_verified_sample.jsonl`의 `model_exact` 청크
2. `selected_faq_candidates.jsonl` 중 `model_family_direct`
3. 매뉴얼과 일치하는 `category_common_safety`
4. 그 외 공통 FAQ는 검증 전 답변 근거로 사용하지 않음

`other_model_only`, `other_product_family`, `image_only_unverified` 항목은 RAG에서 제외합니다.

## 공식·설계·합성 구분

- `official`: 공식 매뉴얼·FAQ에서 확인한 사실과 조치
- `team_designed`: 문의 상태·우선순위·상담/방문 흐름
- `synthetic`: 실제 개인정보를 포함하지 않는 시연용 고객 문의

공식 사실과 팀 설계 규칙을 같은 근거처럼 표현하지 않습니다.


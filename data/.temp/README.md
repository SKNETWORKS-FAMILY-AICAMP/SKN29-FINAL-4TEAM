# 데이터 디렉터리 안내

## 적용 모델

| 역할 | 모델 | 적용 원칙 |
|---|---|---|
| 기본 MVP | `WPUJAC104DWH` / `WPU-JAC104D` 계열 | 공식 REV.00 매뉴얼을 1차 근거로 사용하고 계열 FAQ는 조건부 보조로만 사용 |
| 후속 확장 | `WPUIAC425SNW` / `WPU-IAC425` 계열 | 기본 MVP 완료 후 얼음 특화 시나리오에만 추가 |
| 삭제·사용 중단 | `WPU-IAC506` | 저장소에서 삭제됐으며 신규 RAG·합성·UI 구현에 사용 금지 |

## 표준 구조

```text
data/
├── raw/                         # 공식 원문, Git 제외
├── processed/
│   ├── documents/              # 매뉴얼 페이지 추출본
│   ├── metadata/               # 출처·로그·품질·오류·정책
│   └── structured/             # 검증된 RAG·FAQ 후보
├── synthetic/                  # 개인정보 없는 JAC104 시연 데이터
├── reports/                    # PM 결정과 공식 근거 검증 보고서
└── handoff_guides/             # 팀원별 GitHub 데이터 확인 가이드
```

## 사용 우선순위

1. `processed/structured/rag_verified_sample.jsonl`의 JAC104D `model_exact` 청크 7건
2. `selected_faq_candidates.jsonl` 중 `model_family_direct`이면서 D 매뉴얼과 일치하는 항목
3. 매뉴얼과 일치하는 `category_common_safety`
4. 그 외 공통 FAQ는 검증 전 답변 근거로 사용하지 않음

`other_model_only`, `other_product_family`, `image_only_unverified` 항목은 RAG에서 제외합니다.

IAC425 검증 청크는 `processed/structured/rag_expansion_iac425.jsonl`에 별도 보관하며 기본 MVP 인덱스에 포함하지 않습니다. JAC104D의 문서 계보와 페이지 근거는 각각 `processed/metadata/model_document_lineage.csv`, `processed/structured/jac104_evidence_registry.jsonl`에서 확인합니다.

## 공식·설계·합성 구분

- `official`: 공식 매뉴얼·FAQ에서 확인한 사실과 조치
- `team_designed`: 문의 상태·우선순위·상담/방문 흐름
- `synthetic`: 실제 개인정보를 포함하지 않는 시연용 고객 문의

공식 사실과 팀 설계 규칙을 같은 근거처럼 표현하지 않습니다.

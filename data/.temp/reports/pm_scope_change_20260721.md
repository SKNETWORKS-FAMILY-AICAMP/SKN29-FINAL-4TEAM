# 정수기 MVP 대상 모델 변경 결정

> 결정일: 2026-07-21  
> 상태: PM 승인 완료 - 기존 2026-07-20 WPU-IAC506 단일 모델 결정을 대체  
> 승인 확인: 2026-07-21 사용자 전달 기준

## 결정

- 기본 MVP 제품 코드를 `WPUJAC104DWH`, 매뉴얼 적용 계열을 `WPU-JAC104D`로 확정한다.
- `WPUIAC425SNW`는 기본 MVP가 안정화된 이후 적용하는 후속 확장 모델로 확정한다.
- 기존 `WPU-IAC506` 데이터와 보고서는 원격 커밋 `e909835`에서 저장소 삭제했으며 신규 RAG·합성 데이터·UI 구현에서 사용하지 않는다.

## 결정 근거

- WPU-JAC104 계열은 공식몰 표시 리뷰가 비교 후보 중 가장 많아 수요와 사용 기반을 추정할 수 있는 공개 신호가 강하다.
- 모델 계열 직접 FAQ와 최신 D 세대 공식 매뉴얼을 확보할 수 있어 대표 고객 문의 시나리오의 공식 근거를 구성하기 쉽다.
- WPU-IAC425는 제빙, 출빙, 아이스룸 위생, 얼음 상태, 제빙·탈빙 소음 등 기능 특화 문의를 추가할 수 있다.
- 구현 범위를 처음부터 두 모델로 넓히지 않고, JAC104 기본 상담 흐름을 먼저 완성한 뒤 IAC425로 확장한다.

## 근거 해석 제한

리뷰 수와 판매량 사이에 상관 가능성은 있으나 모델별 실판매량과 노출 알고리즘이 공개되지 않았다. 따라서 리뷰 수, 상단 노출, 향후 판매량의 관계는 선정 가설로만 사용하며 확정적인 판매 성과로 표현하지 않는다.

## 신규 데이터 위치

- JAC104D 공식 근거 검증 보고서: `data/reports/team_A_feedback_response_20260721.md`
- 공식 매뉴얼 페이지 추출: `data/processed/documents/manual_pages.jsonl`
- 검증된 RAG 샘플: `data/processed/structured/rag_verified_sample.jsonl`
- IAC425 후속 확장 RAG: `data/processed/structured/rag_expansion_iac425.jsonl`
- JAC104D 근거 레지스트리: `data/processed/structured/jac104_evidence_registry.jsonl`
- D/S 문서 계보: `data/processed/metadata/model_document_lineage.csv`
- FAQ 재선별 후보: `data/processed/structured/selected_faq_candidates.jsonl`
- 모델 범위 정책: `data/processed/metadata/model_scope.csv`

## 인계 방식

- ZIP 패키지를 생성하지 않는다.
- GitHub 저장소의 표준 데이터 경로를 팀 공용 인계 경로로 사용한다.
- 팀원 B·D·E와 PM은 `data/handoff_guides/`의 역할별 확인 가이드를 따른다.

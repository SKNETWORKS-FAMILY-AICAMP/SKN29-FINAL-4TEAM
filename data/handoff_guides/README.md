# 팀원별 데이터 확인 가이드

인계용 ZIP을 만들지 않는다. 모든 팀원은 이 저장소의 `data/` 표준 경로를 단일 공유 원본으로 사용한다.

## 적용 범위

- 기본 MVP: `WPUJAC104DWH` / `WPU-JAC104D`
- 후속 확장: `WPUIAC425SNW` / `WPU-IAC425`
- 사용 금지: `data/archive/WPU-IAC506_20260720/`의 이전 데이터

## 역할별 가이드

- [팀원 B - RAG 데이터 확인](team_B_rag_data_guide.md)
- [팀원 D - 데이터 구조 확인](team_D_data_structure_guide.md)
- [팀원 E - UI·시연 데이터 확인](team_E_ui_demo_guide.md)
- [PM - 최종 데이터 검토](PM_data_review_guide.md)

## 공통 확인 순서

1. `data/processed/metadata/model_scope.csv`
2. 자신의 역할별 가이드
3. 역할별 필수 데이터 파일
4. `data/processed/metadata/error_missing_list.csv`
5. 검토 결과를 PR 코멘트 또는 팀 협업 채널에 기록

공식 원본 PDF는 GitHub에 포함되지 않는다. 문서 원문 확인이 필요한 경우 `source_inventory.csv`의 공식 URL과 팀 내부 `data/raw/` 경로를 사용한다.


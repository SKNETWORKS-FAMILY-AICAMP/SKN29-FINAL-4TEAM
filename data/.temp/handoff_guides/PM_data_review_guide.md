# PM - 최종 데이터 검토 가이드

## 확정 범위

- 기본 MVP: `WPUJAC104DWH`
- 후속 확장: `WPUIAC425SNW`
- 폐기 모델: `WPU-IAC506`

## 필수 확인 파일

1. `data/reports/team_A_feedback_response_20260721.md`
2. `data/reports/pm_scope_change_20260721.md`
3. `data/processed/metadata/final_submission_checklist.csv`
4. `data/processed/metadata/quality_review.csv`
5. `data/processed/metadata/error_missing_list.csv`

## 수량 확인

- 공식 매뉴얼: 2개 모델·2파일·96쪽
- FAQ 원문: 119건
- FAQ 재선별: 20건
- 실제 우선 사용 FAQ: 직접 1건·공통 안전 3건
- 검증 RAG: JAC104 7건·IAC425 후속 4건
- 합성 시나리오: JAC104 6건
- 역할별 확인 가이드: 4개

## 승인 시 확인할 제한

- 리뷰 수는 수요 대체 지표이며 판매량으로 표현하지 않음
- IAC425는 기본 MVP에 포함하지 않음
- 저장소에서 삭제된 IAC506 이전 데이터는 신규 구현에서 사용하지 않음
- 공식 PDF와 원본 포함 ZIP은 GitHub에 없음
- 방문 일정·처리 상태는 공식 정책이 아닌 `team_designed`

## 최종 승인 체크

- [ ] 기본 모델 코드가 화면·RAG·DB에서 일치함
- [ ] JAC104S 구형 IoT 자료가 혼합되지 않음
- [ ] FAQ 허용 상태 필터가 적용됨
- [ ] 누수·온수 경고의 안전 분기가 유지됨
- [ ] 합성 데이터에 실제 개인정보가 없음
- [ ] 팀원 B·D·E가 각 가이드 확인 결과를 남김

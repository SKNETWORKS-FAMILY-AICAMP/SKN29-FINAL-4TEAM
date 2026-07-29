# WaterCare 데이터 전처리 결과서

## 현재 기준

- 데이터 버전: `0.9.0`
- 공식 매뉴얼 페이지: 44건
- 정규화 FAQ: 119건
- FAQ 후보: 20건
- 승인 RAG 청크: 7건
- Evidence: 9건
- 합성 원본 시나리오: 24건
- 활성 projection: 22건
- 상태이력·Audit: 각각 125건

`SYN-JAC104-012`, `016`은 원본에 보존하지만 State Machine v1.0.0의
terminal 동일 ID 재개 금지와 충돌하므로 재설계 승인 전까지 제외한다.

## 품질·재현성

Schema, ID/FK, 상태이력, 멱등성, 대표 E2E, manifest hash와 byte
결정성을 데이터 파이프라인에서 검증한다. 최신 실행 결과는
`data/processed/validation/latest_qa_summary.json`을 기준으로 한다.

- 데이터 단위 테스트: 55/55 통과
- State Machine 계약 검증: 통과
- 전체 QA: 48개 파일·740개 레코드, 오류·경고 0건
- 대표 E2E: 17/17 통과
- 결정적 재생성 drift: 0건
- 최종 Manifest: 154개 항목 검증

## 미확정 항목

- DB 적재: 사용자 성공 확인, 실행 증빙 대기
- RAG 검색: 평가 기준 준비, 실제 Index·Case별 결과 진행 중
- 외부 원본: 저장소 밖 보존본을 Inventory 검증 명령으로 재확인 필요

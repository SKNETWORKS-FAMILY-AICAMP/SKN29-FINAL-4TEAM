# Week 3 P0 데이터 인수 기준

기준 데이터 버전은 `0.9.0`, 승인 상태 계약은 State Machine
`1.0.0/TEAM_APPROVED`다.

## 자동 통과 기준

- 데이터 단위 테스트 전체 통과
- `qa --verify-rebuild` 오류·경고·결정성 drift 0건
- manifest의 record·SHA-256과 실제 파일 일치
- 원본 시나리오 24개, 활성 projection 22개
- `SYN-JAC104-012`, `016`은 `BLOCKED_DECISION`이며 load 후보에서 제외
- 상태이력·Audit 각각 125건, 대상별 `state_version` 중복 0건
- 상태이력은 대상 FK 하나만 설정하고 `target_type_code`와 일치
- Public UUID·fixture 정수 PK·업무 코드 혼용 0건
- API replay·payload conflict·복합 이벤트 멱등성 Case 통과
- RAG 승인 청크 7건만 기본 인덱싱 대상으로 전달

## 외부 증빙 Gate

- DB 적재: commit, Migration, 명령, 테이블별 건수, FK 오류, 2회 적재
  중복 결과가 있어야 `DB_LOAD_VERIFIED`로 표시한다.
- RAG 검색: embedding/index metadata와 Case별 순위가 있어야 실제
  Recall@K·MRR을 확정한다.
- Backend Runtime 전체나 AI Runtime은 담당자 실행 증거 없이
  `VERIFIED`로 표시하지 않는다.

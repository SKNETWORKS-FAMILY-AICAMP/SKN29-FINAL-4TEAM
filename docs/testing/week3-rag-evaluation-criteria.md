# Week 3 RAG 검색 평가 기준

데이터 기준본은 `data/config/rag/jac104_retrieval_cases.json`이다.

- 양성 Case 7개는 승인 청크 각각을 최소 1회 정답으로 포함한다.
- `top_k=5`에서 expected chunk가 1건 이상 반환되어야 한다.
- 부정 Case 5개는 금지 모델·문서 hit가 0건이어야 하며 근거 없음
  fallback을 반환해야 한다.
- 결과에는 embedding model/version, chunk-set SHA, index version,
  filter, 순위, Recall@K, MRR을 기록한다.
- JAC104 S세대, IAC425, IAC506, 미검증 FAQ, 존재하지 않는 모델을
  전용 부정 Case로 유지한다.

AI 평가 데이터의 canonical 경로와 실제 결과 Manifest는 이동윤 담당자가
확정한다. 그 전까지 데이터 문서는 평가 기준만 `READY`, 실행 결과는
`PENDING_AI_OWNER`로 표시한다.

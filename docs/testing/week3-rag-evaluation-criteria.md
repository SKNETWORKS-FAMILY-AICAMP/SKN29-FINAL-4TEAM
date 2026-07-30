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
확정했다.

- Canonical dataset:
  `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`
- Result manifest:
  `ai/evaluation/reports/pgvector_verification.json`
- Index manifest: `ai/configs/index_manifest.json`
- 실행 환경: PostgreSQL 16.14, pgvector 0.8.6, cosine exact search
- Embedding: `BAAI/bge-m3`,
  revision `5617a9f61b028005a4858fdac845db406aefb181`
- 실행 결과: 12/12 PASS, 양성 Recall@5 `1.0`, 평균 MRR
  `0.8857142857142858`, 금지 hit 0

Data 실행 상태는 `PASS`, 승인 범위는 `APPROVED_FOR_MVP_INGEST`다.
이 승인은 JAC104D D세대 REV.00 37~39쪽의 7개 증상에 한정한다.
누수 Case는 기대 청크가 5위로 Recall@5는 통과했지만 MRR `0.2`이므로
검색 품질 후속으로 유지한다.

지침서 3.3의 동일 모델 정책 차단 Case, Case별 Page·Filter·
`PASS/FAIL/MANUAL_REVIEW` 결과 구조는 v2 평가 계약에서 추가한다.
v2는 이동윤의 13개 재실행 결과를 받기 전까지
`DATA_EXPECTATION_READY_AI_REVERIFY_REQUIRED`로 관리한다.

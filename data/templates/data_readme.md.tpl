# WaterCare Data

공식 출처에서 검증한 전처리·RAG 데이터와 개인정보가 없는 합성 시연 데이터의 기준본입니다.

## 현재 범위

- 데이터 버전: `${dataset_version}`
- 생성 기준 시각: `${generated_at}`
- MVP 제품: `WPUJAC104DWH` / WPU-JAC104D·WPU-JCC104D REV.00
- 제한 RAG 인계 후보: `WPUIAC425SNW`, `WPUIAC606SNW`
- 공식 매뉴얼 페이지: 144쪽(`REFERENCE_ONLY`)
- RAG 확장: Parent 15건·Child 53건·Evidence Group 43건
- 평가 초안: 양성 43건·부정 7건, 총 50건(`DATA_READY_AI_NOT_RUN`)
- 합성 fixture: 369건(제품 3건), 기존 DB handoff closure: 367건
- 합성 원본 시나리오: 24개
- 계약 정합 활성 projection: 22개
- 차단 유지: `SYN-JAC104-012`, `SYN-JAC104-016`
- 상태이력·감사이력: 각 125건
- 시나리오 subset: 7파일, 33건
- 상태 계약: State Machine v1.0.0 / `TEAM_APPROVED`
- RAG 평가 계약: 양성 7건·부정 5건, JAC104D MVP pgvector 12/12 PASS

RAG 실행 승인은 `WPUJAC104DWH`, D세대, 공식 매뉴얼 REV.00
37~39쪽의 7개 증상에 한정합니다. `BAAI/bge-m3`와 PostgreSQL
16.14·pgvector 0.8.6으로 7개 청크를 적재했고, 양성 Recall@5
`1.0`, 평균 MRR `0.8857142857`, 금지 문서·모델 유입 0건을
확인했습니다. 누수 기대 청크는 Top-5의 5위이므로 적재 승인을
막지는 않지만 검색 품질 P1 후속으로 유지합니다.

`rag-expansion`은 실제 적재 결과가 아니라 `INGEST_CANDIDATE`입니다.
Parent는 문맥 확장용 `CONTEXT_ONLY`이고 검색 후보는 Child 53건뿐입니다.
검색 점수 계산 전에 `exact_sales_code` 필터를 적용해야 하며 다른 모델로
fallback하지 않습니다. IAC425·IAC606은 Backend/API 계약이 확장되기 전까지
`CONTRACT_BLOCKED_NOT_INDEXED` 상태입니다.

원본 24개 카탈로그와 alignment registry는 보존합니다. Fixture·expected·DB handoff 후보에는 차단된 두 시나리오를 제외한 22개만 투영합니다.

## 식별자와 T-005 정책

- `id`: fixture 내부 관계용 정수 PK
- `public_id`: Public API용 UUID
- `DEMO-*`, `SYN-*`: 사람이 확인하는 업무 코드
- 상태이력은 네 대상 FK 중 정확히 하나만 설정하고 `target_type_code`와 일치해야 합니다.
- `idempotency_key`는 요청과 이력을 연결하는 추적값이며 UNIQUE가 아닙니다.
- 이력 중복은 대상 Aggregate별 `state_version`으로 차단합니다.

CustomerProfile fixture와 Backend import crosswalk는 lookup 변환 규칙만
제공합니다. Fixture 정수 PK를 Backend PK로 직접 주입하지 않습니다.
Crosswalk v2의 `DB_FULL_VERIFIED`는 빈 격리 PostgreSQL에서 합성 Handoff
`db-full` 프로필 367 Source의 최초 Import와 Replay를 검증했다는
뜻입니다. T-005 전체 32개 테이블, 운영 DB 적재 또는 서비스 배포 완료를
뜻하지 않습니다.

`service_contracts_used=true`는 Data projection과 Backend Importer가 승인된
State Machine v1.0.0과 Crosswalk v2를 사용한다는 뜻입니다. T-005 전체
구현 상태와 Backend Runtime Import 검증 상태는 handoff metadata에서
분리합니다.

## 실행

```powershell
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py build synthetic
python -B -m data.tools.rag_experiments.build_three_model_handoff
python -B -m data.tools.rag_experiments.qa_three_model_handoff
python -B data/tools/pipeline.py handoff rag-expansion
python -B data/tools/pipeline.py handoff db-smoke
python -B data/tools/pipeline.py handoff db-full
python -B data/tools/pipeline.py handoff qa
python -B data/tools/pipeline.py qa --verify-rebuild
python -B data/tools/pipeline.py inventory
python -B data/tools/pipeline.py finalize
```

생성 결과 JSON을 수동 수정하지 않습니다. 같은 설정으로 두 번 생성한 byte 결과, manifest 건수·SHA-256, 상세 QA 리포트 해시를 파이프라인이 검증합니다.

외부 보존 원본을 다시 확인할 때는 Inventory의 `local_path`가 상대적인
루트를 지정합니다.

```powershell
python -B scripts/data/verify_source_inventory.py `
  --external-root 'C:\approved-source-root'
```

PDF 페이지 수 검증에는 팀이 승인한 `pypdf` Runtime이 필요합니다.

# AI 사전학습 모델·Vector DB 적용 결과서

> 작성자: 이동윤(AI·RAG)
>
> 기준일: 2026-08-03
>
> 상태: `ISOLATED_VERIFIED_TEAM_DB_PENDING`

## 1. 산출물 성격

본 프로젝트는 ML/DL 모델을 직접 학습하거나 파인튜닝하지 않았다. 공식
산출물의 “학습 결과”는 사전학습 임베딩 모델 `BAAI/bge-m3`의 고정 Revision
적용, pgvector 적재·검색, 정책 필터와 재현 절차로 대체한다.

다음 표현은 사용하지 않는다.

- 직접 학습한 `bge-m3`
- 파인튜닝 완료
- 전체 정수기 정확도 100%
- 환각 0%

## 2. 적용 모델

| 항목 | 값 |
| --- | --- |
| 모델 | `BAAI/bge-m3` |
| 유형 | 사전학습 Text Embedding Model |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Framework | SentenceTransformers `5.5.1`, Torch `2.13.0+cpu` |
| 출력 Dimension | `1024` |
| 정규화 | L2 Normalize |
| 실행 환경 | Python `3.13.13`, Windows 11 AMD64 |
| 모델 저장 | Git 미포함, Hugging Face Cache 사용 |

모델 Revision이 없으면 `AI_VECTOR_DSN` 기반 검색 Runtime을 시작하지 않는다.
모델 Cache 유무와 관계없이 같은 Revision을 사용해야 한다.

## 3. 입력 전처리·출력

검색 질의는 고객 원문을 그대로 로그에 남기지 않고 Runtime 내부에서만
Embedding한다. 검색 전에 다음 정책을 적용한다.

1. 공개 `model_code` 존재 확인
2. MVP 허용 모델 `WPUJAC104DWH` 확인
3. D세대 확인
4. 공식 검증 또는 팀 검증 문서 확인
5. 고객 안내 사용 허용 확인
6. 미검증 FAQ 단독 근거 차단

Embedding 결과는 길이 `1024`의 정규화 Vector이며 PostgreSQL에는
`vector(1024)`로 저장한다.

## 4. Vector DB 구성

| 항목 | 값 |
| --- | --- |
| DBMS | PostgreSQL `16.14` |
| Extension | pgvector `0.8.6` |
| 거리 함수 | Cosine distance `<=>` |
| 검색 방식 | Exact Search |
| ANN Index | 미사용 |
| Top-K | `5` |
| Score Threshold | `0.4` |
| 승인 청크 | `7` |
| Index Version | `1.0.0` |
| Chunk Set SHA-256 | `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` |

격리 검증 DB는 `watercare_ai_verify`였으며 팀 DB와 Volume을 공유하지 않았다.
Schema 초기화는 DB 이름에 `verify`, `test`, `tmp`, `disposable` 중 하나가
포함되고 `AI_VECTOR_DISPOSABLE_CONFIRM=DISPOSABLE_ONLY`일 때만 허용한다.

팀 DB에서는 AI 스크립트가 `CREATE EXTENSION`이나 `CREATE TABLE`을 수행하지
않는다. 최지용이 Django Model·Migration으로 Schema를 확정한 뒤 승인 청크만
UPSERT한다.

## 5. 평가 Dataset과 결과

공식 후보 기준은
[`official_mvp_baseline_20260803.json`](../../ai/evaluation/reports/official_mvp_baseline_20260803.json)이다.

### 5.1 격리 pgvector 이력

| 지표 | 결과 |
| --- | ---: |
| 전체 Case | `12` |
| PASS | `12` |
| 실제 pgvector Query | `7` |
| 정책 차단 | `5` |
| 양성 Recall@5 | `1.0` |
| 양성 MRR | `0.8857` |
| 금지 Hit | `0` |
| Fixture Rollback 후 잔존 | `0` |

평가 범위는 제품 1종, D세대 1종, 공식 매뉴얼 1개, 승인 청크 7개다. 이
결과를 전체 제품·전체 증상 성능으로 확대 해석하지 않는다.

### 5.2 현재 오프라인 실행

Vector Store가 설정되지 않은 실행은 다음처럼 표시한다.

```text
status=vector_store_not_configured
rag_metrics_publishable=false
```

이때 생성되는 Recall·MRR `0.0`은 검색 품질이 아니라 DB 미연결 상태를 뜻한다.
안전 규칙 평가는 검색과 분리해 4/4, `100%`를 확인했다.

### 5.3 13번째 정책 차단 Case

“제품은 일치하지만 문서 정책상 사용 불가한 자료” Case는 아직 Data Owner와
기대값을 확정하지 않았다. `data/config/rag/**` 소유자 김은진과 문서 ID,
차단 사유, 예상 실행 경로를 합의한 뒤 추가한다. 합의 전에는 현재 12개
Dataset을 임의 변경하거나 13개 완료로 보고하지 않는다.

## 6. Revision·Hash Assertion

| 대상 | 경로·값 |
| --- | --- |
| 검색 Dataset | `data/config/rag/jac104_retrieval_cases.json` |
| Dataset File SHA-256 | `6E9F202F902F965B0C6875D8FCDF26333651E680019CC8B34416E8A444A12E4F` |
| 승인 청크 원본 | `data/config/rag/jac104_chunks.json` |
| 청크 File SHA-256 | `73C8E9C66B87D0B5A115D75DD1A2A81F4142A5CB581F7F8CC85DF9072E98F0DB` |
| Canonical Chunk Set SHA-256 | `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` |
| Index Manifest | `ai/configs/index_manifest.json` |
| Document Source SHA-256 | `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C` |

File SHA-256는 파일 Byte를 그대로 SHA-256으로 계산한다. Canonical Chunk Set
Hash는 인덱싱 코드의 정렬·직렬화 규칙으로 계산한 값이므로 File Hash와
동일할 필요가 없다.

## 7. 재현 절차

### 7.1 AI 환경과 단위 검증

```powershell
.\ai\.venv\Scripts\python.exe --version
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
```

### 7.2 격리 DB 검증

```powershell
$env:AI_VECTOR_DSN='<격리 PostgreSQL DSN>'
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'
$env:AI_VECTOR_DISPOSABLE_CONFIRM='DISPOSABLE_ONLY'

.\ai\.venv\Scripts\python.exe -m ai.scripts.initialize_disposable_vector_schema
.\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_pgvector_runtime
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -v
```

### 7.3 팀 DB 검증

최지용의 Migration이 적용된 뒤 `AI_VECTOR_DISPOSABLE_CONFIRM` 없이 승인
청크 UPSERT와 검색 검증만 실행한다. 팀 DB 연결 문자열은 문서·로그·Git에
기록하지 않는다.

## 8. Graph DB 미사용 사유

현재 MVP는 제품·구독·문의·상태 이력·문서 Metadata가 PostgreSQL FK와
정형 필터로 표현된다. 검색 대상도 제품 1종과 승인 청크 7개이므로 별도 Graph
DB가 제공하는 다단계 관계 탐색 이점이 작다.

Graph DB를 추가하면 다음 운영 부담이 생긴다.

- PostgreSQL과 Graph DB 간 이중 쓰기·동기화
- 별도 Backup·복구·권한·배포
- 문서·제품 관계의 중복 SSOT
- Backend 상태 머신과 AI Evidence 간 일관성 검증 증가

따라서 4주차 MVP는 PostgreSQL FK·상태 이력·pgvector Metadata Filter를
사용한다. 제품·부품·증상·조치 관계가 크게 확장되고 다단계 설명 가능성
요구가 생길 때 Graph DB 도입을 재검토한다.

## 9. 미완료·수락 조건

- 팀 DB `waterbridge:5432`의 vector Migration
- 팀 DB 승인 청크 UPSERT와 12개 평가 재실행
- 13번째 정책 차단 Case의 Data Owner 승인
- Backend AI Adapter·Evidence 저장 E2E
- 최신 `main`의 공식 Commit/Tag와 결과 Hash 갱신

위 항목 전에는 상태를 `TEAM_DB_COMPLETE`로 변경하지 않는다.

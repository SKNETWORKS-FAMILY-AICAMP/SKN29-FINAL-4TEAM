# WaterCare AI/RAG

## 실행 환경

- Python 3.10 이상
- PostgreSQL과 `vector` 확장
- `AI_VECTOR_DSN`: pgvector 연결 문자열. 설정하지 않으면 Local 모드는 안전 분류와 근거 없음 정책까지만 실행한다.

```powershell
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pip install -e ai
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m uvicorn ai.app.main:app --reload
```

Health Check는 `GET /health`, 분석 API는 `POST /api/v1/ai/analyze?mode=mock|local`이다. `inquiry_id`는 Backend 내부 정수 PK가 아닌 공개 업무 식별자를 사용한다.

## 검증

```powershell
C:\Users\Playdata\miniconda3\envs\myenv\python.exe -m pytest ai/tests/unit/
```

Local 검색은 `BAAI/bge-m3`의 1024차원 정규화 임베딩과 pgvector Cosine Exact Search(`<=>`)를 사용한다. 제품 코드·D세대·공식 검증·고객 안내 허용 조건은 유사도 계산 전 SQL에서 제한한다. 모델 파일과 DB가 준비되지 않은 환경에서는 자동으로 하드코딩 검색으로 대체하지 않고 근거 없음 상담 경로를 반환한다.

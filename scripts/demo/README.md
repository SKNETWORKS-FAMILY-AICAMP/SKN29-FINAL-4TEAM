# AI Local·Mock 검증 Runbook

이 Runbook은 Backend E2E 전에 FastAPI 계약과 결정적 위험 분기를 확인한다.
Mock 결과는 RAG 근거가 아니며, Local 위험 분기는 명백한 위험 입력이 Vector DB
구성과 무관하게 안전 안내를 반환하는지 확인한다.

## 1. 사전 조건

- 저장소 Root에서 실행한다.
- Python은 `ai/.venv`의 `3.13.13`을 사용한다.
- `AI_VECTOR_DSN` 같은 Secret을 화면, 로그 또는 문서에 출력하지 않는다.

## 2. AI 서비스 시작

첫 번째 PowerShell에서 실행한다.

```powershell
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
```

## 3. DB 없이 실행 가능한 Smoke

두 번째 PowerShell에서 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo\verify_ai_runtime.ps1
```

다음 세 항목이 `PASS`여야 한다.

- Health와 안전 규칙 로딩
- `mode=mock` 계약 응답과 Correlation ID 보존
- `mode=local` 위험 입력의 `danger`·`TOTAL_STOP` 반환

## 4. Local RAG 선택 검증

Backend/DB 담당자가 준비한 최소 권한 Secret으로 AI 서버 프로세스에
`AI_VECTOR_DSN`과 고정 `AI_EMBEDDING_REVISION`을 주입한 경우에만 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo\verify_ai_runtime.ps1 -IncludeLocalRetrieval
```

정상 검색 0건은 HTTP 200 `FALLBACK`이고, Vector Store 설정 누락은 HTTP 503이다.
둘을 같은 결과로 기록하지 않는다. 이 Smoke는 Backend 저장, stale
`state_version`, 멱등성 또는 최종 `EvidenceCardDTO`를 검증하지 않는다.

## 5. 실패 시 기록

다음 항목만 남긴다.

- Branch와 40자리 Commit SHA, Dirty 여부
- Python Version과 실행 명령
- HTTP Status, 공개 오류 코드, `failure_stage`, `retry_count`
- `correlation_id`와 재현 시각

고객 원문, DSN, Token, Stack Trace와 내부 문서 경로는 공유 로그에 남기지 않는다.

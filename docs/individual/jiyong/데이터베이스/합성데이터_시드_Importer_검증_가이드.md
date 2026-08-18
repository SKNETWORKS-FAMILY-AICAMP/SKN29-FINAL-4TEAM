# 합성데이터 Seed·Importer 검증 가이드

> 관련 업무: 합성 데이터 적재·재현
> 범위: 실제 고객·운영 Dump 제외

## 1. 목적

승인된 합성 Fixture를 PostgreSQL에 결정적으로 적재하고, Dry-run·Apply·Replay와
원장·상태·감사 정합성을 재현한다.

## 2. 주요 경로

- `data/synthetic/fixtures/**`
- `data/config/handoff/backend_import_crosswalk.json`
- `data/processed/metadata/**`
- `backend/apps/operations/**`
- `backend/apps/operations/management/commands/import_synthetic_handoff.py`
- `backend/tests/integration/operations/**`

## 3. 데이터 경계

- 공개 식별자는 Fixture의 Canonical ID와 Crosswalk로 연결한다.
- Fixture 정수 ID를 Django PK에 직접 주입하지 않는다.
- 직접 저장되지 않는 항목은 `PROJECTED`로 명시한다.
- Hash·Dataset Version·Mapping Version을 Import 원장에 남긴다.
- 충돌을 자동 병합하거나 오류 행만 건너뛰지 않는다.

## 4. 재현 절차

새 빈 PostgreSQL QA DB에서만 수행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate --noinput

.\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
  --profile full --dry-run
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
  --profile full
.\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
  --profile full
```

## 5. 성공 조건

| 단계 | 성공 조건 |
| --- | --- |
| Dry-run | 도메인·Batch·Item 저장 0 |
| 최초 Apply | 입력이 CREATED 또는 명시적 PROJECTED |
| Replay | 비의도 CREATED·UPDATED 0 |
| 원장 | Batch와 모든 Source Item의 provenance 존재 |
| 상태 | Aggregate의 최종 상태·버전이 최신 History와 일치 |
| 감사 | 상태 이력과 Audit Event 연결 불일치 0 |
| 무결성 | Unique·FK·Check 오류 0 |

## 6. Seed와 Importer 구분

기본 Demo Seed는 개발 계정·제품·최소 시나리오를 준비한다. Synthetic Importer는
전체 합성 Handoff와 provenance를 검증한다. 두 절차를 같은 명령이나 같은
기본 DB에 혼합하지 않는다.

## 7. 안전 경계

- 기본 개발 DB에서 Importer와 Dry-run을 실행하지 않는다.
- Dry-run도 Sequence를 소비할 수 있으므로 새 QA DB를 사용한다.
- `dropdb`, Volume 삭제, 운영 Dump 적재는 이 가이드 범위가 아니다.
- 결과 문서에 DB Password·DSN·JWT·개인정보를 기록하지 않는다.

## 8. 판정

Fresh Migration, Dry-run, Apply, Replay, 원장·상태·감사 검증이 모두 통과하면
합성데이터 적재 기능은 작성자 검증 완료다. 소비자 E2E와 독립 QA는 별도다.

# 신규 모델 업무 체인·Coverage Gate 데이터 변경 기록

- 작업일: 2026-08-19 (Asia/Seoul)
- 작업 브랜치: `eunjin`
- 최초 HEAD: `457bc73dc60b465447fc74830f367293b4a0921e`
- 작업 전 동기화 HEAD: `8df4d498`
- 데이터 버전: `1.0.0` → `1.1.0`
- 파이프라인 설정 버전: `1.6.0` → `1.7.0`

## 1. 김은진 역할에서 수행한 변경

- `WPUIAC425SNW`의 온수 출수 중단과 `WPUIAC606SNW`의 얼음 미출수 업무 체인을 모델별 `E2E_CANDIDATE` 데이터로 추가했다.
- 제품 → 고객제품 후보 → 구독 후보 → 문의 후보 → 공식 근거 → 안전성 → 예상 처리 결과를 한 레코드에서 추적하도록 구성했다.
- 모델별 관계 누락, 다른 모델 근거 혼입, 후보의 정식 Fixture·DB Handoff 유입과 허위 Runtime 검증 상태를 차단하는 Coverage Gate를 파이프라인 QA에 연결했다.
- `WPU-JCC104 (D)`는 공동 매뉴얼 Alias로만 보존하고 활성 제품·Coverage 대상에서 제외했다.

## 2. 변경 파일과 관할 근거

- `data/config`, `data/schemas`, `data/synthetic`: 후보 정의·Schema·결정적 산출물
- `data/tools`, `data/tools/tests`: Builder·Coverage Gate·회귀 테스트
- `data/catalog`, `data/processed`, `data/templates`: 버전·Manifest·QA 보고서 재생성
- `docs/individual/eunjin`: 데이터 변경 및 담당자 인계 기록

모든 변경은 김은진 직접 관할인 `data/**` 또는 공동 편집 영역인 `docs/**`에 한정했다. Backend Runtime·Model·Migration·Importer는 수정하지 않았다.

## 3. 실행한 데이터·QA·CI 검증과 결과

### 데이터 단위 테스트

```powershell
python -B -m unittest discover -s data\tools\tests -v
```

- 결과: `94 tests`, `OK`
- 신규 Coverage Gate, 허위 Runtime 검증 상태 차단, 결정적 Builder와 12개 Backend Fixture 해시 고정을 포함한다.

### 결정적 재생성 QA

```powershell
python -B data\tools\pipeline.py qa --verify-rebuild
```

- 결과: `PASS`
- 오류 0건, 경고 0건, 파일 57개·레코드 958건 검사
- `changed_files=[]`, `canonical_drift_files=[]`
- 정식 합성 Fixture 369건 유지
- 후보 업무 체인 2건 확인

### Backend Handoff 표적 회귀

```powershell
$env:DJANGO_SETTINGS_MODULE='config.settings.test'
backend\.venv\Scripts\python.exe -m pytest backend\tests\integration\operations\test_synthetic_handoff_import.py -q -p no:cacheprovider
```

- 결과: `8 passed`
- 후보 파일이 기존 `db-smoke`·`db-full` Import 경로에 포함되지 않음을 확인했다.

### 기존 Fixture 보존

- `data/synthetic/fixtures/*.json` 12개 파일의 SHA-256이 작업 시작 시점과 모두 동일하다.
- 정식 Fixture 총합 369건과 기존 DB Handoff closure 367건을 변경하지 않았다.
- `git diff --check`: 오류 없음

## 4. 실행하지 못한 검증과 이유

- PostgreSQL 적재 검증: `NOT_APPLICABLE`. 후보 업무 체인은 `NOT_IMPORTED`이며 기존 Backend Import 대상이 아니다.
- 실제 AI 검색·LLM 실행: 변경 범위가 기존 검증 Evidence Group을 참조하는 합성 후보와 데이터 Gate이므로 수행하지 않았다.

## 5. 발견했지만 수정하지 않은 관할 밖 문제

- IAC425·IAC606의 고객제품·구독·문의는 아직 Backend 정식 Fixture와 Runtime에 연결되지 않았다.
- 두 모델의 `usage_guidance_status`, 상태 전이와 최종 처리 상태는 Backend·상태 계약에서 정식 확정되지 않아 후보 데이터에서 임의로 canonical 값으로 만들지 않았다.
- IAC606 Evidence의 안전 행동 일부는 기존 전처리 결과에서 문장 단위가 분리되어 있다. 이번 작업은 검증된 Evidence를 그대로 참조했으며 원문·RAG 전처리를 임의 수정하지 않았다.

## 6. 필요한 담당자 인계

- Backend 담당자: 후보 체인을 정식 DB Fixture로 승격할 때 고객제품·구독·문의 Model/Serializer/Importer와 상태 전이를 확정하고 PostgreSQL 독립 Gate를 수행한다.
- AI 담당자: 정식 승격 전에 `WPUIAC425SNW`, `WPUIAC606SNW`의 정확 판매코드 필터와 후보 Case 검색 결과를 실제 pgvector에서 재검증한다.

## 7. 남은 위험과 확인 필요 항목

- 두 후보는 `scope_status=E2E_CANDIDATE`, `backend_import_status=NOT_IMPORTED`, `runtime_status=NOT_VERIFIED` 상태다.
- IAC425는 `danger`·상담사 인계, IAC606은 `caution`·자가 해결 예상까지 데이터 수준에서만 검증했다.
- Backend 계약과 PostgreSQL 검증 없이 후보 상태를 제거하거나 정식 Fixture에 병합하면 안 된다.

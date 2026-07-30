# Crosswalk v2 Data Owner Review

> 검토일: 2026-07-30
>
> 검토자: 김은진(Data·QA·DevOps)
>
> 판정: `APPROVED`
>
> 검토 기준 `main` SHA: `0bcb8b514f2b0d1476882d926b667dbdb5d8c06a`
>
> 검토 후보 `jiyong` SHA: `665bef9b4f43db3c1d8bd847b58b620b5d462736`
>
> 사후 검토 HEAD: `e5cc511189b54060dfafde9215b2cb0799b1bf7a`

## 1. 판정 요약

`0bcb8b5..665bef9`의 Data 소유 변경 19개를 의미·Schema·검증
안전성·결정성 기준으로 검토했다. 2026-07-30 `git fetch --prune
origin` 후 `HEAD`, `origin/main`, `origin/eunjin`은 모두
`e5cc511189b54060dfafde9215b2cb0799b1bf7a`였고, `665bef9..HEAD`의
`data/**`, `scripts/data/**` 추가 변경은 없었다.

후보는 Owner Review 전에 이미 `main`에 병합되었다. 이번 판정은 그
절차 편차를 숨기지 않은 사후 Owner Review다. 검토 결과 Data 의미나
Mapping을 수정할 결함은 발견하지 않았다. 문서 정합화를 위해 Data
README의 원본 템플릿을 수정하고 공식 `finalize` 명령으로 README와 최종
Manifest를 재생성했다.

`DB_FULL_VERIFIED`는 빈 격리 PostgreSQL에서 합성 Handoff `db-full`
프로필 367 Source의 Import·Replay를 검증했다는 뜻이다. T-005 전체
32개 테이블, 운영 DB 적재 또는 서비스 배포 완료를 뜻하지 않는다.

## 2. 검토한 19개 경로

### 설정·Schema·검증 코드

1. `data/config/handoff/backend_import_crosswalk.json`
2. `data/config/handoff/consumer_profiles.json`
3. `data/config/workflow/service_contract_mapping.json`
4. `data/schemas/config/backendImportCrosswalk.schema.json`
5. `data/schemas/config/consumerProfiles.schema.json`
6. `data/schemas/config/serviceContractMapping.schema.json`
7. `data/tools/tests/test_handoff_profiles.py`
8. `data/tools/tests/test_service_contract_mapping.py`
9. `data/tools/watercare/io.py`
10. `data/tools/watercare/validation.py`
11. `scripts/data/refresh_source_hashes.py`

### 파이프라인 생성물

12. `data/processed/metadata/consumer_handoff_manifest.json`
13. `data/processed/metadata/final_dataset_manifest.json`
14. `data/processed/validation/business/latest_business_rules_report.json`
15. `data/processed/validation/integrity/latest_integrity_report.json`
16. `data/processed/validation/latest_qa_summary.json`
17. `data/processed/validation/quality/latest_quality_report.json`
18. `data/processed/validation/reproducibility/latest_reproducibility_report.json`
19. `data/processed/validation/schema/latest_schema_report.json`

## 3. 의미·안전성 검토

| 검토 항목 | 결과 | 근거 |
|---|---|---|
| Backend Source | PASS | 17개 경로 등록, LF 정규화 SHA-256 일치 |
| Fixture Mapping | PASS | 12개 고유 Fixture, Direct 11개·Projected 1개 |
| 식별자 정책 | PASS | Fixture 정수 PK 직접 주입 금지, Public ID·업무키 lookup |
| Care Type | PASS | `REGULAR_INSPECTION→PERIODIC_CHECK`, `FILTER_REPLACEMENT`, `VISIT_SERVICE`가 Importer와 일치 |
| Smoke 범위 | PASS | 37 Source = 31 Direct + 6 Projected, Replay 31 Unchanged + 6 Projected |
| Full 범위 | PASS | 367 Source = 355 Direct + 12 Projected, Replay 355 Unchanged + 12 Projected |
| Schema | PASS | Crosswalk·Consumer Profile·Service Mapping 설정과 필수 구조 일치 |
| 경로 안전성 | PASS | 저장소 밖 경로 탈출 차단, 절대경로 비허용 |
| Text Hash | PASS | UTF-8 BOM 제거, CRLF·LF 정규화, 잘못된 UTF-8 거부 |
| `--check` 안전성 | PASS | 불일치 보고만 수행하며 Data 파일을 쓰지 않음 |
| 검증 강도 | PASS | Runtime 문서 Hash, DB명, Batch Code, 실행 순서와 수치를 검증 |
| 생성물 결정성 | PASS | QA 2회 후 Data tracked diff 0 |

Crosswalk의 Runtime 증거에는 검증 당시
`worktree_state=UNCOMMITTED_VERIFIED_CHANGES`가 기록돼 있다. 이 값은
당시 실행 조건을 보존하는 역사 증거로 승인하되, 현재 검토 기준은 해당
내용을 포함해 병합된 `e5cc511`로 별도 기록한다.

## 4. 실행 검증

검증 환경은 `backend/.venv` Python `3.13.13`, pip `26.0.1`,
constraints 고정 패키지 31개, 추가 패키지 0개다.

| 검사 | 결과 |
|---|---|
| Backend 환경 검사 | PASS, failures 0, warnings 0 |
| Source Hash `--check` | PASS, changed 0 |
| Data 단위 테스트 | 61/61 PASS, Exit code 0 |
| QA 실행 1 | PASS, 오류 0, 경고 0, E2E 17/17 |
| QA 실행 1 Data diff | 0 |
| QA 실행 2 | PASS, 오류 0, 경고 0, E2E 17/17 |
| QA 실행 2 Data diff | 0 |
| 재현성 changed files | 0 |
| canonical drift | 0 |
| Finalize | PASS, Manifest 154개 항목, QA 오류·경고 0 |

실행 명령:

```powershell
.\backend\.venv\Scripts\python.exe `
  .\scripts\data\refresh_source_hashes.py --check

.\backend\.venv\Scripts\python.exe -B `
  -m unittest discover -s .\data\tools\tests -v

.\backend\.venv\Scripts\python.exe -B `
  .\data\tools\pipeline.py qa --verify-rebuild

.\backend\.venv\Scripts\python.exe -B `
  .\data\tools\pipeline.py qa --verify-rebuild
```

## 5. Owner Review 반환

```text
[김은진 Data Owner Review]
review_status=APPROVED
review_base_jiyong_sha=665bef9b4f43db3c1d8bd847b58b620b5d462736
review_head_sha=e5cc511189b54060dfafde9215b2cb0799b1bf7a
reviewed_paths=19
source_hash_check=PASS/changed=0
data_test_result=61 passed
qa_run_1=PASS/errors=0/warnings=0/e2e=17/17
qa_run_2=PASS/errors=0/warnings=0/e2e=17/17
manifest_hash_diff=0
changed_source_templates=data/templates/data_readme.md.tpl
changed_generated_outputs=data/README.md,data/processed/metadata/final_dataset_manifest.json
mapping_change_requires_new_database=false
remaining_blocker=BACKEND_REVERIFY_REQUIRED
note=후보가 현재 HEAD에 이미 병합된 상태에서 사후 Owner Review 수행
```

문서 정합화 변경은 이 검토 문서, `data/README.md`, README 템플릿,
`final_dataset_manifest.json`, 기존 김은진 작업 보고서와 공용 인계
허브다. Crosswalk·Schema·Validator·Fixture Mapping은 변경하지 않았다.

## 6. 후속 인계

### 최지용

Data Mapping 변경은 없으므로 새 격리 DB 생성 조건은 발생하지 않았다.
다만 인계 Gate에 따라 현재 `main` 기준 Source Hash, Data 61건, QA,
Backend 397건과 기존 PostgreSQL Import 증거를 재확인해야 한다.

### 윤승혁 PM

WBS는 이번 검토에서 수정하지 않는다. 다음 근거로 상태를 재판정한다.

- `T-007`: P0 인수 기준·Case Matrix·Fixture·증빙 형식이 존재하므로 완료 후보
- `T-013`: 합성 Fixture와 격리 PostgreSQL db-full Import 증거가 있으므로 완료 후보
- `T-012`: 평가 계약은 준비됐지만 실제 AI 검색·Recall@K·MRR 증거가 없어 진행 중 유지

### 남은 범위

- T-005는 32개 중 10개 구현, 22개 미구현으로 전체 `NOT_READY`
- 실제 RAG 검색 지표는 이동윤 담당 실행 증거 대기
- 운영 DB 적재와 배포 검증은 이번 Owner Review 범위 밖

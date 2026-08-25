# main Production Backend·Data Gate 읽기 전용 증거

> 확인일: 2026-08-24
>
> 대상: `main@e99cf78faa58a40f2cec49281119c437b594e470`
>
> GitHub Run: `32720657302`

## 1. 현재 판정

```text
release_source_boundary=PASS
machine_contract=PASS
web_production_gate=PASS
data_deterministic_gate=FAIL
backend_environment_prepare=FAIL
image_publish=SKIPPED
production_deploy=SKIPPED
overall=HOLD
```

이번 실패는 G3 후보가 원인이 아니다. G3 후보는 아직 원격에 공개되지 않았고,
Run 대상은 Mobile G2가 병합된 최신 `main`이다.

## 2. Data 실패

Data QA 자체는 오류·경고 0건으로 끝났지만, 재생성 뒤
`data/processed/metadata/final_dataset_manifest.json`에 Diff가 생겨
결정성 Gate가 실패했다. 로그상 Raw Manual 항목이 Clean Runner에서 빠지는
형태다.

이 문제의 소유 범위는 `data/**`와 배포 Gate이므로 최지용이 Manifest를
수동 편집하거나 원본 PDF를 추가하지 않는다. 김은진이 Clean Runner의 Raw
비보존 정책과 생성 Manifest 기대값을 정합화해야 한다.

## 3. Backend 실패

Backend Test 실행 전 Production 설정 Import 단계에서 중단됐다.

```text
reason=verify_full_required
missing=POSTGRES_SSLMODE
```

Production은 PostgreSQL TLS `verify-full`을 강제한다. GitHub Environment 또는
Workflow 주입값에 `POSTGRES_SSLMODE`가 없어 Test가 시작되지 않았다. 비밀값이나
CA 내용을 문서·Git에 넣지 않고, QA·DevOps가 보호 환경에서 설정 존재 여부를
확인해야 한다.

## 4. Backend 작성자 증거

G3 후보를 최신 `main`에 적용한 로컬 검증은 다음과 같다.

```text
targeted=33 passed
contract=46 passed
p1_candidate_data=7 passed
backend_full=1475 passed, 41 skipped
django_check=PASS
migration_drift=NO_CHANGES
```

이는 코드 회귀 증거이며 Production 배포 성공 증거는 아니다.

## 5. 책임 경계

- 최지용: Backend 코드·Migration·격리 PostgreSQL 증거 제공
- 김은진: Data 결정성, GitHub 보호 환경, 독립 QA·DevOps 검증
- 윤승혁(PM): Gate 해소 뒤 Release 판정

Workflow, Secret, `data/**`는 이번 작업에서 수정하지 않았다.

# 정수기 딜러 팀 통합 인계 허브

> 기준일: 2026-07-29
>
> 문서 책임: 공동 편집(`docs/**`)
>
> 현재 상태: `SHARED_CANDIDATE_DATA_OWNER_REVIEW_REQUIRED`
>
> 기능 통합 Commit: `cbf1b6cfa3c56e95e30284ab1e8424f77e1594ec`
>
> 현재 원격 후보 SHA: `git fetch origin --prune` 후 `git rev-parse origin/jiyong`으로 확인
>
> 실행 원칙: `작업 → 즉시 검증 → 다음 작업`

이 문서는 팀원이 “어느 Commit을 받아야 하는지”, “현재 완료된 것은
무엇인지”, “자기 담당에서 다음에 무엇을 해야 하는지”를 한 곳에서
확인하는 공용 인계 진입점이다.

상세 구현 이력과 긴 실행 설명은 각 원본 문서로 연결하고, 이 문서에는
현재 기준선·차단 요소·담당자·실행 순서만 유지한다.

---

## 1. 이 문서의 판단 기준

### 1.1 적용한 팀 지침

| 구분 | 팀 저장소 안의 확인 문서 |
| --- | --- |
| 디렉토리·산출물 위치 | [프로젝트 디렉토리 구조 v2](../architecture/%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%EB%94%94%EB%A0%89%ED%86%A0%EB%A6%AC%20%EA%B5%AC%EC%A1%B0%20v2.md) |
| 공통 개발·Git·계약 규칙 | [공통 개발 규칙](../planning/md/%EA%B3%B5%ED%86%B5%20%EA%B0%9C%EB%B0%9C%20%EA%B7%9C%EC%B9%99.md) |
| 최지용 3주차 Backend 범위 | [최지용 3주차 업무 지침서](../weekly-task/%EC%B5%9C%EC%A7%80%EC%9A%A9_3%EC%A3%BC%EC%B0%A8_%EC%97%85%EB%AC%B4_%EC%A7%80%EC%B9%A8%EC%84%9C.md) |
| 경로별 주담당·협업담당 | [팀원별 관할 영역 v2](../planning/md/%ED%8C%80%EC%9B%90%EB%B3%84%20%EA%B4%80%ED%95%A0%20%EC%98%81%EC%97%AD%20v2.md) |

### 1.2 충돌 시 우선순위

1. `contracts/**`의 기계 판독 계약
2. 실제 Model·Migration·Route·Runtime 검증 결과
3. 담당자 Commit과 PM이 병합한 `main` 40자리 SHA
4. 이 문서를 포함한 설명 문서
5. 과거 계획표·회의 메모

설명 문서가 계약 또는 실행 결과와 다르면 설명 문서를 수정한다. 실패한
테스트를 피하려고 다른 담당자의 계약이나 데이터를 임의 변경하지 않는다.

### 1.3 상태 표기

| 표기 | 의미 |
| --- | --- |
| `SHARED_CANDIDATE` | 담당자 Branch에 Push됐지만 PM `main` 병합 전 |
| `TEAM_BASELINE` | PM이 `main`에 병합하고 40자리 SHA를 공유함 |
| `LOCAL_VERIFIED` | 현재 PC에서 검증했지만 Commit·Push 전 |
| `BLOCKED` | 선행 입력 또는 검증 실패 때문에 후속 작업 금지 |
| `FOLLOW_UP` | 기준선 반영 뒤 담당자가 이어서 작업할 항목 |

`LOCAL_VERIFIED`는 팀원이 Pull할 수 있는 기준선이 아니다. 해당 구현·계약·
테스트·문서가 같은 작업 단위로 Push되고 PM이 병합한 뒤에만
`TEAM_BASELINE`으로 승격한다.

---

## 2. 2026-07-29 기준선

### 2.1 원격에 존재하는 공유 후보

| 항목 | 값 | 판정 |
| --- | --- | --- |
| 현재 Branch | `jiyong` | 확인 |
| `origin/jiyong` | `git rev-parse origin/jiyong`의 40자리 결과 | `SHARED_CANDIDATE` |
| 게시 기준 `origin/main` | `0bcb8b514f2b0d1476882d926b667dbdb5d8c06a` | 게시 직전 최신 Snapshot |
| 게시 후보의 위 `main` 포함 여부 | 포함됨 | 최신 `main` 기반, PM 병합은 아직 대기 |
| Backend 회귀 | `397 passed` | 같은 후보 내용 기준 |
| Data 회귀 | `61 passed`, QA 2회·E2E `17/17` | 김은진 Owner Review 대기 |
| Crosswalk v2 | Backend Source `17/17`, Fixture Mapping `12/12` | Source Hash PASS |
| T-005 | `10/32`, 잔여 22 | 전체 `NOT_READY` |

팀원이 작업을 시작할 최종 기준은 위 `origin/main` Snapshot을 임의로
사용하는 것이 아니라, PM이 병합 후 새로 전달한 `main` 40자리 SHA다.

### 2.2 원격에 게시한 통합 후보

| 항목 | 현재 확인 결과 | 공유 판정 |
| --- | --- | --- |
| Backend 전체 테스트 | `397 passed` | `SHARED_CANDIDATE` |
| Data 도구 테스트 | `61 passed`, QA 2회 결정성 확인 | `SHARED_CANDIDATE`, Owner Review 대기 |
| Django System Check | 오류 0 | `SHARED_CANDIDATE` |
| Migration drift | 새 Migration 생성 필요 없음 | `SHARED_CANDIDATE` |
| T-005 구현 | `10/32`, 잔여 22 | `SHARED_CANDIDATE`, 전체 `NOT_READY` |
| 합성 Handoff | Source 367행, 12종 Fixture, 격리 PostgreSQL Smoke·Full·재실행 검증 | `SHARED_CANDIDATE` |
| 기본 개발 DB | 기존 9개 + `workflow.0003` 적용, 기존 데이터 보존 | 실행 증거 완료 |
| Workflow 시간 이력 | 기존 11건의 `changed_at`을 원래 `created_at`으로 보정 | `SHARED_CANDIDATE` |
| Health·Auth HTTP Smoke | 기본 DB 선행 증거 완료, PM `main` SHA에서 독립 재현 필요 | `FOLLOW_UP` |
| Git 게시 | 원격 `jiyong`과 40자리 SHA 일치, 게시 Worktree clean | `SHARED_CANDIDATE` |

두 PostgreSQL 실행 경로는 목적이 다르므로 섞지 않는다.

- 격리 검증 DB에서는 합성 Importer와 재실행 멱등성까지 통과했다.
- 현재 `.env`가 가리키는 기본 개발 DB에는 Migration과 Demo Seed 4종을
  적용하고 2회 실행 시 중복 행이 생기지 않음을 확인했다.
- 기본 개발 DB의 `SYN-CUSTOMER-001` UUID와 활성 Serial은 canonical
  Fixture와 충돌하므로 이 DB에서는 합성 Importer를 실행하지 않는다.
  합성 Importer는 빈 격리 DB 전용이다.

따라서 현재 `jiyong` 후보를 전 팀의 Pull 기준으로 전달하면 안 된다.
김은진 Data Owner Review와 최지용 재검증 뒤 PM이 병합해 전달한
40자리 `main` SHA만 `TEAM_BASELINE`이다.

### 2.3 기본 개발 DB에 적용한 Migration과 보정

2026-07-29 적용 전에 다음 9개가 미적용으로 확인됐고, 백업 후 순서대로
적용했다.

1. `inquiries.0003_add_synthetic_handoff_fields`
2. `visits.0001_initial`
3. `consultations.0001_initial`
4. `workflow.0002_expand_transition_targets`
5. `audit.0001_initial`
6. `care.0002_add_imported_care_fields`
7. `inquiries.0004_followup_confirmation`
8. `subscriptions.0002_add_synthetic_projection_fields`
9. `operations.0001_initial`

검증 과정에서 `workflow.0002`가 기존 전이 이력 11건의 `changed_at`을
Migration 실행 시각으로 채운 사실을 발견했다. 이를 숨기거나 이미 적용된
`0002`만 고치지 않고 다음 보정 Migration과 회귀 테스트를 추가했다.

10. `workflow.0003_backfill_legacy_changed_at`

`0003`은 `0002`가 만든 `HST-{기존 public_id}` 서명과
`changed_at > created_at` 조건을 모두 만족하는 기존 행만 보정한다. 적용
전 11건이 조건에 해당했고, 적용 후 `changed_at > created_at`은 0건,
`changed_at = created_at`은 11건이다. 역방향은 잘못된 Migration 시각을
복원하지 않는 의도적 `noop`이다.

적용 전 백업은 Git 제외 경로
`backend/.runtime/db-backups/watercare_pre_9_migrations_20260729-162334.dump`에
생성했다. Custom Archive 형식·`pg_restore --list`는 통과했지만 실제 새
DB 복원 리허설까지 완료했다는 의미는 아니다.

팀원은 PM이 병합한 동일 Commit에서 `0002`와 `0003`를 함께 받고, 자기
로컬 DB의 Backend 쓰기를 중단한 뒤 적용한다. 새 Migration 파일을 다시
만들지 않는다. 상세 절차는
[Django·PostgreSQL 공유패키지 인계서 v1.3](<../individual/jiyong/manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)을
따른다.

---

## 3. 완료·해결된 항목

### 3.1 원격 공유 후보에서 완료

| 항목 | 현재 결과 | 회귀 금지 기준 |
| --- | --- | --- |
| OpenAPI·Runtime 정합화 | OpenAPI 9개 = Runtime 지원 7개 + 미구현 2개 | 미구현 Operation을 구현된 API처럼 소비하지 않음 |
| Runtime 오류 Registry | 누락 오류 코드 정합화 | [오류 코드 계약](../../contracts/error-codes/error-codes.yaml) 우선 |
| Auth·문의 JSON 예시 | Auth 4개, 문의 생성·취소 정상/오류/Replay 예시 | 예시와 Runtime 응답을 함께 변경 |
| Backend 환경 재현 문서 | v1.3 작성·`jiyong` Push | `.venv`·`.env` 자체는 공유 금지 |
| PM State 계약 | v1.0.0·`TEAM_APPROVED` | 상태·권한·409·멱등성 임의 변경 금지 |
| Mobile 구조 충돌 | `customer-app`·`technician-app`·`core` 3모듈 확정 | 구형 단일 App 구조 재도입 금지 |

상세 근거:

- [API Runtime 구현 상태](../api/runtime_implementation_status.md)
- [Backend API 계약 정합화 검증보고서](../individual/jiyong/manuals/20260729_%EC%B5%9C%EC%A7%80%EC%9A%A9_Backend_API_%EA%B3%84%EC%95%BD_%EC%A0%95%ED%95%A9%ED%99%94_%EA%B2%80%EC%A6%9D%EB%B3%B4%EA%B3%A0%EC%84%9C_v1.0.md)
- [Django·PostgreSQL 공유패키지 인계서 v1.3](<../individual/jiyong/manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)
- [State Machine 계약](../../contracts/state-machine/README.md)
- [Mobile 모듈 설정](../../mobile/settings.gradle.kts)

### 3.2 이번 공유 후보에서 해결했으며 검토가 남은 항목

| 항목 | 해결 내용 | 공유 전 남은 Gate |
| --- | --- | --- |
| Data→Backend Mapping | `service_contracts_used=true`, Source 17·Mapping 12 검증 | 김은진 Data 19경로 Owner Review |
| 기본 개발 DB Migration | 기존 9개와 `workflow.0003` 적용·검증 | PM 병합 뒤 팀원 로컬 DB 재현 |
| Workflow 시간 이력 | 기존 11건 보정, MigrationExecutor 회귀 추가 | PM 병합 뒤 팀원 로컬 DB 재현 |
| 합성 Handoff Importer | 격리 DB에서 `DB_SMOKE_VERIFIED`·`DB_FULL_VERIFIED` | 기본 DB 실행 금지, 빈 격리 DB만 사용 |
| 합성 데이터 적재 | 12종, Source 367행, 재실행 생성·수정 0 | 김은진 Owner Review 뒤 최지용 재검증 |
| Health·Auth Smoke | 현재 Backend를 8001에 실행해 전체 흐름 통과 | 팀 기준선에서 기본 포트 재검증 |
| Backend 실행 매뉴얼 | v1.3에 설치·실행·Migration·복구 절차 통합 | 게시 완료 |
| T-005 | 7개에서 10개로 증가 | 잔여 22개 및 계약 밖 Table 판정 |
| Role 정규화 | 활성 데이터의 `CONSULTANT` 기준 정합화 | Legacy Alias 회귀 금지 |

로컬 근거:

- [PostgreSQL 합성 Handoff Runtime 검증·인계서](../individual/jiyong/manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md)
- [합성 고객 Auth Alias](../individual/jiyong/manuals/20260729_synthetic_customer_auth_alias.md)
- [합성 도메인 Schema·Migration](../individual/jiyong/technical/backend/20260729_synthetic_domain_schema_migration.md)
- [합성 Handoff Importer](../individual/jiyong/technical/backend/20260729_synthetic_handoff_importer.md)
- [Data QA Fixture Hash 강화](../individual/jiyong/technical/contracts/20260729_data_qa_fixture_hash_hardening.md)
- [Backend Import Crosswalk](../../data/config/handoff/backend_import_crosswalk.json)

위 링크와 근거 파일은 기능 통합 Commit
`cbf1b6cfa3c56e95e30284ab1e8424f77e1594ec`부터 함께 게시됐다.
김은진 검토 전 PM이 `main`에 병합하지 않는다.

---

## 4. 현재 Blocker와 후속 담당

| 우선순위 | Blocker | 주담당 | 필요한 입력 | 다음 소비자 |
| --- | --- | --- | --- | --- |
| P0 | Data 변경 19개가 `jiyong` 후보에 함께 게시됨 | 김은진(원본·QA) + 최지용(Backend 소비) | 김은진 `APPROVED` 또는 수정 Diff·Branch SHA | PM |
| P0 | PM `main` 병합 SHA 미전달 | 윤승혁 | 담당자 Branch 검토·병합 | 전 팀원 |
| P1 | T-005 `10/32`, 잔여 22개 | 최지용 | PM State·Data·AI 입력별 Wave | Backend·QA |
| P1 | T-005 계약 밖 Table이 Auditor에 검출 | 최지용 + 윤승혁 | `audit`·`operations`·`workflow` Table의 계약 편입/별도 분류 결정 | QA |
| P1 | `SYN-JAC104-012`, `SYN-JAC104-016` 업무 결정 미확정 | 윤승혁 | Reopen·제품 검증 정책 | 김은진·최지용 |
| P1 | Web `public_id` 소비 불일치 | 한예나 | PM `main` SHA·Data Crosswalk | Backend E2E |
| P1 | Web Node 호환·Test Startup 미검증 | 한예나 | 지원 Node로 재설치 후 Test 재실행 | PM 통합 QA |
| P1 | Mobile API·DTO·Network 미완료 | 양정현 | PM `main` SHA·OpenAPI 7개 Runtime 범위 | Backend E2E |
| P1 | AI 재현 환경·Runtime 명령 미확정 | 이동윤 | 의존성 Manifest·Schema·실행·테스트 결과 | 최지용 AI Client |
| P1 | Backend AI Client가 Placeholder | 최지용 | 이동윤의 AI Commit SHA와 Runtime 계약 | 통합 E2E |
| P2 | 동일 Commit Web·Mobile·AI 포함 E2E 미수행 | 각 담당 + PM | 위 P0·P1 완료 | 최종 QA |

T-005는 현재 `NOT_READY`다. 10개 구현을 32개 완료로 표현하지 않는다.
잔여 22개를 한 번에 구현하지 말고, 계약 입력이 확정된 작은 Wave별로
`작업 → Migration/계약 검증 → 테스트`를 반복한다.

---

## 5. 변경 금지 계약

| 계약 | 원본 | 담당 원칙 |
| --- | --- | --- |
| REST Method·Path·Schema | [OpenAPI](../../contracts/api/openapi.yaml) | 최지용 주담당, 변경 후 소비자 전달 |
| 오류 코드 | [Error Registry](../../contracts/error-codes/error-codes.yaml) | Runtime과 예시를 같은 작업에서 갱신 |
| 공통 코드 | [Code Registry](../../contracts/codes/) | 문자열 임의 생성 금지 |
| 상태·Action·권한 | [State Machine](../../contracts/state-machine/README.md) | 윤승혁 주담당, 최지용 Backend 소비 |
| AI Request·Response | [AI 계약](../../contracts/ai/README.md) | 이동윤 주담당, 최지용 Client 소비 |
| T-005 물리 계약 | [T-005 Manifest](../database/t-005/manifest.json) | 구현 수와 완료 상태 분리 |
| Data Handoff | [Data 정합화 진행](data-contract-alignment-progress.md) | 김은진 원본·QA, 최지용 Import 소비 |

공통 불변식:

- 내부 PK는 정수, 외부 노출 ID는 UUID, 업무 식별자는 별도 Code로 분리한다.
- 상태 변경은 Backend만 수행한다.
- 쓰기 Action은 `state_version`, `Idempotency-Key`, Transition History를
  함께 검증한다.
- `.env`, `.venv`, Token, Password, 로컬 PostgreSQL Volume은 Git에
  올리지 않는다.
- Schema 변경은 Model만 고치지 않고 Migration으로 남긴다.
- 기본 DB의 Demo Seed와 빈 격리 DB의 Importer는 서로 다른 경로에서
  각각 두 번 실행해 두 번째 실행의 중복 생성을 허용하지 않는다.

---

## 6. 도미노 오류를 막는 인계 순서

### G0. 현재 로컬 통합 후보 고정

1. 최지용이 최신 `main` 기반 기능 통합 후보를
   `cbf1b6cfa3c56e95e30284ab1e8424f77e1594ec`부터 `jiyong`에 게시했다.
2. Hash graph와 생성 Manifest가 하나의 검증 단위이므로 Backend·Data·
   문서를 원자적 후보로 묶었지만, Data 소유권 승인을 생략하지 않는다.
3. 김은진이 Data 원본·Crosswalk·QA 19경로를 검토해 `APPROVED` 또는
   수정 Diff·`eunjin` 40자리 SHA를 반환한다.
4. 수정이 있으면 최지용이 승인된 변경만 반영한 뒤 Backend 397,
   Data 61, QA 2회, T-005 Auditor, PostgreSQL, Import Replay를 다시
   검증하고 `jiyong` 후속 SHA를 게시한다.
5. 김은진 승인 전에는 PM이 `main`에 병합하지 않는다.
6. 승인 뒤 윤승혁이 후보의 충돌·보존 범위를 검토해 `main`에 병합하고
   40자리 SHA를 공유한다.

G0 전에는 Web·Mobile·AI 담당자가 로컬 미공유 파일 경로를 복사해
구현하지 않는다.

김은진은 게시된 `jiyong` SHA를 별도 Worktree에서 검토한다. 자기
작업트리에 미커밋 변경이 있으면 삭제·초기화하지 않는다.

```powershell
Set-Location (git rev-parse --show-toplevel)
$reviewDir = Join-Path ([IO.Path]::GetTempPath()) "watercare-data-review-20260729"
New-Item -ItemType Directory -Path $reviewDir -Force | Out-Null

git diff --name-status -- data
git diff --binary --output="$reviewDir\tracked-data.patch" -- data
git ls-files --others --exclude-standard -- data |
    Set-Content -LiteralPath "$reviewDir\untracked-data-paths.txt" -Encoding UTF8
Get-FileHash -Algorithm SHA256 "$reviewDir\tracked-data.patch"
```

- Patch는 추적 중인 `data/**` 변경만 담는다.
- `untracked-data-paths.txt`의 파일은 동일 상대경로와 SHA-256을 보존해
  별도 전달한다.
- Raw 개인정보·`.env`·Token은 Patch나 압축 파일에 포함하지 않는다.
- 김은진은 `eunjin`에서 `git apply --check` 후 적용하고 Data 61개
  테스트를 실행한 뒤 Commit·PR URL·SHA를 반환한다.
- Patch 전달이 어렵다면 Data 변경만 별도 PR로 만들고 김은진의 Owner
  Review 전에는 병합하지 않는다.

### G1. 팀원별 Branch 반영

각 팀원은 PM이 전달한 `main` SHA만 자기 Branch에 반영한다. 서로의
Branch를 임의로 연쇄 Merge하지 않는다.

| 담당자 | 작업 Branch |
| --- | --- |
| 윤승혁 | `seunghyuk` |
| 최지용 | `jiyong` |
| 김은진 | `eunjin` |
| 한예나 | `yena` |
| 양정현 | `jeonghyun` |
| 이동윤 | `dongyoon` |

```powershell
Set-Location (git rev-parse --show-toplevel)

$dirty = @(git status --porcelain)
if ($dirty.Count -gt 0) {
    throw "작업트리가 깨끗하지 않습니다. Commit 또는 담당자 협의 후 다시 실행하세요."
}

git status --short
git fetch origin
if ($LASTEXITCODE -ne 0) {
    throw "origin fetch에 실패했습니다."
}

$expectedBranch = "<위 표의 자기 Branch>"
git switch $expectedBranch
if ($LASTEXITCODE -ne 0) {
    throw "자기 Branch 전환에 실패했습니다."
}
$currentBranch = git branch --show-current
if ($currentBranch -ne $expectedBranch -or $currentBranch -eq "main") {
    throw "자기 Branch 전환에 실패했습니다."
}
git pull --ff-only origin $expectedBranch
if ($LASTEXITCODE -ne 0) {
    throw "자기 원격 Branch의 Fast-forward Pull에 실패했습니다."
}

$pmMainSha = "<PM이 전달한 40자리 main SHA>"
git cat-file -e "$pmMainSha^{commit}"
if ($LASTEXITCODE -ne 0) {
    throw "전달받은 SHA가 로컬에서 유효한 Commit이 아닙니다."
}
git merge-base --is-ancestor $pmMainSha origin/main
if ($LASTEXITCODE -ne 0) {
    throw "전달받은 SHA가 origin/main의 조상이 아닙니다."
}

# 모든 Guard가 통과한 자기 Branch에서만 실행
git merge --no-ff $pmMainSha
if ($LASTEXITCODE -ne 0) {
    git merge --abort
    throw "병합 충돌을 원복했습니다. 충돌 파일과 두 SHA를 PM에게 전달하세요."
}
```

작업트리가 깨끗하지 않거나 SHA 검증 Exit code가 0이 아니면 Merge를
중단하고 담당자에게 현재 Branch·SHA·변경 파일을 전달한다.

### G2. 소비자 병렬 작업

PM `main` SHA 반영 후 다음 작업은 서로 병렬로 진행할 수 있다.

- 김은진: Data QA·Crosswalk·Blocked Scenario 결정 반영
- 한예나: Web `public_id` Mapping과 Runtime 7개 API 소비
- 양정현: Mobile 3모듈의 DTO·Network·Auth 연동
- 이동윤: AI 재현 환경·Schema·Runtime 증거 제공
- 최지용: T-005 다음 Wave와 Backend AI Client 준비

각 담당자는 자기 작업 직후 자기 영역 검증을 실행하고 결과를 Commit과
함께 반환한다.

### G3. 동일 Commit 최종 통합

각 Branch 결과를 모두 합친 PM 통합 Commit 하나에서만 최종 완료를
판정한다.

1. PostgreSQL 연결·Migration 적용
2. 기본 DB는 Demo Seed 4종 2회, 빈 격리 DB는 Importer 2회
3. Backend 전체 회귀
4. Data 전체 QA
5. Web 지원 Node·Test·Lint·Build·Auth Browser/API Smoke
6. Mobile JDK 17·Unit Test·Lint·두 App Build·Emulator API Smoke
7. AI Unit Test·Smoke
8. 대표 Auth·문의·상태전이·409·Replay E2E

한 단계라도 실패하면 후속 단계를 완료 처리하지 않고 첫 실패 원인을
해결한 뒤 G3를 처음부터 다시 실행한다.

---

## 7. 팀원별 상세 인계

### 7.1 최지용 — Backend·DB·API 계약

**현재 책임**

- `backend/**`
- `contracts/api/**`
- `contracts/error-codes/**`
- Backend가 소비하는 Migration·Importer
- T-005 구현 증거와 API Runtime 정합성

**지금 할 일**

1. 작업트리를 경로별 소유자와 작업 단위로 분리한다.
2. 완료한 9개 Migration과 `workflow.0003` 보정·회귀를 같은 작업 단위로
   유지한다.
3. 기본 DB에서는 Demo Seed만 사용하고 합성 Importer를 실행하지 않는다.
4. T-005 10/32 상태와 잔여 22개를 그대로 보고한다.
5. 사용자 승인 전에는 Commit·Push하지 않는다.
6. 승인 후 문서·구현·검증 근거를 같은 작업 단위로 `jiyong`에 Push한다.

**재현·검증**

상세 최초 설치와 재실행 절차는
[Django·PostgreSQL 공유패키지 인계서 v1.3](<../individual/jiyong/manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)을
따른다.

```powershell
Set-Location (git rev-parse --show-toplevel)
python --version
python .\scripts\development\bootstrap.py --service backend
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres
python .\scripts\development\check_environment.py --service backend
.\backend\.venv\Scripts\python.exe .\backend\manage.py migrate --check --noinput --settings=config.settings.local
python .\scripts\development\check_environment.py --service backend --full --postgresql
python .\scripts\database\audit_t005_implementation_readiness.py --settings config.settings.test
```

현재 기본 DB는 Applied Migration Gate까지 통과했다. 다른 PC에서
`migrate --check`가 실패하면 곧바로 `migrate`하지 말고, v1.3의
대상 DB 확인·Writer 중단·Plan·백업 판단·적용 절차를 따른다.

현재 마지막 명령의 정상 상태는 Process 성공이 아니라 JSON
`status=NOT_READY`, `fully_implemented_contract_table_count=10`을 정확히
보고하는 것이다. 전체 완료 Gate에서는 `--require-ready`가 필요하다.

Migration과 자기 DB 경로에 맞는 Seed 또는 Importer Gate가 통과한 뒤
실제 HTTP를 검증할 때는 터미널을 두 개 사용한다. 기본 개발 DB에는
Importer를 실행하지 않는다.

```powershell
# 터미널 A — 저장소 루트에서 시작
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --settings=config.settings.local
```

```powershell
# 터미널 B — 저장소 루트
Set-Location (git rev-parse --show-toplevel)
.\backend\.venv\Scripts\python.exe .\scripts\smoke\check_backend_auth.py --base-url http://127.0.0.1:8000
```

Smoke는 실행 중인 Server의 Health·CORS·Auth 응답을 확인한다. Token
원문은 인계 문서나 Git에 남기지 않는다. Auth Smoke는 JWT
Outstanding·Blacklist Table을 변경하므로 읽기 전용 검사가 아니다.

2026-07-29 실측에서는 8000 포트에 15:08부터 실행된 별도 Miniconda
Python 서버가 있어 현재 코드를 8001에 실행하고 같은 Smoke를 통과했다.
기존 프로세스를 임의 종료하지 말고 다음으로 포트를 확인한다.

```powershell
netstat -ano -p tcp | Select-String ':8000'
```

포트가 이미 사용 중이면 원래 프로세스의 소유자를 확인하거나, 두 터미널의
서버 주소와 `--base-url`을 모두 8001로 맞춘다. Web·Mobile도 같은 포트로
맞춰야 하며, 8001 통과를 8000의 기존 서버 통과로 기록하지 않는다.

### 7.2 김은진 — Data 원본·Crosswalk·통합 QA

> 최지용 작성 실행 상세:
> [김은진 인계 및 요청사항](../individual/jiyong/team_handover/20260729_최지용_김은진_인계및요청사항.md)

**현재 책임**

- `data/**`의 원본·가공·Fixture·QA
- Hash·Manifest·Crosswalk의 재현성
- Data 변경이 Backend Import 계약과 일치하는지 검토

**지금 할 일**

1. 현재 로컬 Data 변경을 검토해 승인 범위와 자신의 Branch SHA를 남긴다.
2. `service_contracts_used=true`와 367행 Manifest가 현재 파일 Hash와
   일치하는지 재검증한다.
3. `SYN-JAC104-012`, `SYN-JAC104-016`은 PM 결정 전 Projection에서
   차단 상태를 유지한다.
4. 실제 운영 데이터 적재와 합성 Fixture 적재를 같은 완료 항목으로
   표현하지 않는다.

```powershell
Set-Location (git rev-parse --show-toplevel)
python -B -m unittest discover -s data\tools\tests -v
```

기대 증거는 Data Test `61 passed`, Manifest·Hash 일치, 차단 Scenario
미투영이다. 수치가 달라지면 변경된 Fixture와 Manifest를 함께 제출한다.

### 7.3 윤승혁 — PM·State 계약·통합

> 최지용 작성 실행 상세:
> [윤승혁(PM) 인계 및 요청사항](../individual/jiyong/team_handover/20260729_최지용_윤승혁PM_인계및요청사항.md)

**현재 책임**

- State Machine v1.0.0 유지
- 담당자 Branch 검토와 `main` 병합
- 팀원이 사용할 40자리 `main` SHA 제공
- Reopen·제품 검증 정책 결정

**지금 할 일**

1. `jiyong` 통합 후보가 구현·계약·테스트·문서를 함께 포함하는지 확인한다.
2. Data 소유 범위 검토 근거가 있는지 확인한다.
3. T-005 계약 밖 Table을 계약에 편입할지 별도 운영 Table로 둘지
   결정한다.
4. 병합 후 다음 형식으로 팀에 전달한다.

```text
main_sha=<40자리 SHA>
merged_branches=<담당자 Branch 목록>
state_contract_version=1.0.0
known_blockers=<남은 Blocker>
```

### 7.4 한예나 — Web

> 최지용 작성 실행 상세:
> [한예나 인계 및 요청사항](../individual/jiyong/team_handover/20260729_최지용_한예나_인계및요청사항.md)

**현재 책임**

- Backend Runtime 7개 범위의 실제 API 소비
- Auth·CORS·오류 응답·Replay 처리
- 외부 식별자 `public_id` Mapping

**현재 Blocker**

Web Mock은 일부 문의를 `inquiry_id`로 소비하지만 Data Fixture의 외부
식별자는 `public_id`다. Backend 또는 Data 계약을 바꾸지 말고 Web
Mapper에서 외부 UUID를 일관되게 소비한다.

현재 PC의 Node `24.14.0`은 잠금 파일의 `jsdom@30.0.0` 요구 범위
`^22.22.2 || ^24.15.0 || >=26.0.0`에 들지 않는다. 2026-07-29 자동
검증 세션의 `npm test`도 Vitest Config 로딩 중 `spawn EPERM`으로
Exit code 1을 반환했다. 이 결과만으로 코드 결함이라고 단정하지 말고,
지원 Node로 `node_modules`를 재현한 Web 담당자의 일반 터미널에서 먼저
재실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\web
node --version
npm ci
npm test
npm run lint
npm run build
```

`web/package.json`에는 이미 `test: vitest run`이 있으므로 Test Script를
추가하는 작업은 필요 없다. `npm test`가 실패하면 원인을 해결하기 전에
Lint·Build 완료를 선언하지 않는다. PM SHA 반영 전에는 로컬 Importer
결과를 하드코딩하지 않는다.

Test·Lint·Build 통과는 실제 API 연동 완료 증거가 아니다. Backend가
실행 중인 별도 검증 터미널에서 다음 환경으로 Web을 기동한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\web
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
$env:VITE_USE_MOCK_API = "false"
npm run dev -- --host 127.0.0.1
```

실제 API Smoke 범위는 구현된 Runtime 7개만 사용한다.

- `DEMO-CONSULTANT-001`: Auth Login·`/me`와 상담사 화면 Guard를 확인한다.
- CUSTOMER 계정의 문의 생성·취소는 Backend 계약 Harness에서 검증한다.
- CONSULTANT가 CUSTOMER 전용 문의 생성·취소를 호출하면 403이 정상이다.
- 문의 목록·상세와 상담사 Action은 아직 Runtime이 없으므로
  `BLOCKED`를 유지한다.

로컬 `.env.local`을 사용했다면 Git에 올리지 않는다. 지원 범위의
Browser/API Smoke가 없으면 Web 실제 연동은 계속 `BLOCKED`다.

### 7.5 양정현 — Mobile

> 최지용 작성 실행 상세:
> [양정현 인계 및 요청사항](../individual/jiyong/team_handover/20260729_최지용_양정현_인계및요청사항.md)

**현재 책임**

- `customer-app`·`technician-app`·`core` 3모듈 유지
- Backend DTO·Network·JWT·오류 응답 연동
- 고객·기사 App Build와 대표 흐름 검증

**해결된 항목**

구형 단일 App 대 3모듈 구조 충돌은 해결됐다. 구조를 다시 설계하지 말고
현재 모듈 위에서 API 연동을 진행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\mobile
java -version
.\gradlew.bat projects
.\gradlew.bat test
.\gradlew.bat lintDebug
.\gradlew.bat :customer-app:assembleDebug
.\gradlew.bat :technician-app:assembleDebug
```

JDK 17과 `local.properties`의
`BACKEND_BASE_URL=http://10.0.2.2:8000/`을 확인한 Emulator에서 두
App이 Backend에 실제 요청을 보내는지 검증한다. JWT·DTO·Network·오류
응답의 대표 Smoke 증거가 반환되기 전까지 Mobile 실제 API 연동은
`FOLLOW_UP`이다. `local.properties`와 Key는 Git에 올리지 않는다.

### 7.6 이동윤 — AI

> 최지용 작성 실행 상세:
> [이동윤 인계 및 요청사항](../individual/jiyong/team_handover/20260729_최지용_이동윤_인계및요청사항.md)

**현재 책임**

- `ai/**` 실행 환경·의존성 Manifest
- AI Request·Response Schema와 Runtime
- Unit Test·Smoke 명령과 Commit SHA

**현재 Blocker**

AI App 코드는 존재하지만 `ai/pyproject.toml`과 `ai/README.md`만으로는
동일 환경을 재현할 수 없다. 검증되지 않은 설치·실행 명령을 이 문서에서
추측하지 않는다.

다음 내용을 먼저 인계한다.

```text
ai_commit_sha=<40자리 SHA>
python_version=<정확한 버전>
dependency_manifest=<lock 또는 requirements 경로>
start_command=<실제 검증한 명령>
test_command=<실제 검증한 명령>
health_url=<실제 응답한 URL>
request_schema_version=<계약 버전>
response_schema_version=<계약 버전>
```

최지용은 이 인계를 받은 뒤에만
`backend/integrations/ai/**`의 Client·Mapper·Schema Validator를
구현한다.

---

## 8. 검증 명령과 완료 기준

### 8.1 Backend·PostgreSQL

```powershell
Set-Location (git rev-parse --show-toplevel)
python .\scripts\development\check_environment.py --service backend --full --postgresql
```

완료 기준:

- Exit code `0`
- Environment failures `0`
- Django System Check 오류 `0`
- Migration drift 없음
- 미적용 Migration 없음
- Backend 전체 테스트 실패 `0`
- PostgreSQL 16.14·UTC 연결 성공

2026-07-29 현재 실측은 `397 passed`, Exit code 0,
failures 0, warnings 0이다. 이 397개 Pytest는 `config.settings.test`의
SQLite 테스트이며, `--postgresql` 단계는 실제 PostgreSQL 연결과 적용
Migration을 읽기 전용으로 확인한다. “PostgreSQL에서 397개 테스트 통과”로
표현하지 않는다.

### 8.2 T-005

```powershell
Set-Location (git rev-parse --show-toplevel)
python .\scripts\database\validate_t005_schema.py
python .\scripts\database\audit_t005_implementation_readiness.py --settings config.settings.test
```

중간 인계는 구현 수·누락 수·계약 밖 Table을 모두 기록한다. T-005 전체
완료를 선언할 때만 다음을 추가한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
python .\scripts\database\audit_t005_implementation_readiness.py --settings config.settings.test --require-ready
```

### 8.3 State 계약

```powershell
Set-Location (git rev-parse --show-toplevel)
python .\scripts\contracts\validate_state_machine.py
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\workflow -q
```

완료 기준은 v1.0.0 계약 검증 성공과 Backend 상태 전이 테스트 성공이다.
PostgreSQL을 포함한 T-023 최종 완료 판정은 다음 준비도 Gate까지
통과해야 한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
.\.venv\Scripts\python.exe .\apps\workflow\readiness.py --run-runtime-tests --verify-postgresql --require-ready
```

### 8.4 Data

```powershell
Set-Location (git rev-parse --show-toplevel)
python -B -m unittest discover -s data\tools\tests -v
```

현재 로컬 기대값은 `61 passed`다. PM 통합 Commit에서 다시 실행한다.

### 8.5 Web

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\web
node --version
npm test
npm run lint
npm run build
```

중앙 Web Gate는 위 명령뿐 아니라 지원 Runtime 7개 범위의 Auth
Browser/API Smoke 증거를 요구한다. 문의 목록·상세·상담사 Action은
미구현으로 남긴다.

### 8.6 Mobile

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\mobile
java -version
.\gradlew.bat test
.\gradlew.bat lintDebug
.\gradlew.bat :customer-app:assembleDebug
.\gradlew.bat :technician-app:assembleDebug
```

중앙 Mobile Gate는 JDK 17, Lint, 두 App Build와 함께 Emulator에서
Backend 대표 API Smoke 증거를 요구한다.

### 8.7 AI

AI 담당자가 검증한 Manifest와 명령을 인계하기 전에는 공식 공통 명령을
정하지 않는다.

---

## 9. Git 공유와 인계 결과 양식

### 9.1 Commit 규칙

공통 규칙의 순서는 `작업 일자 | 작업 내용`이다.

```text
2026-07-29 | 합성 Handoff Backend·Crosswalk v2 검증 및 인계 최신화
2026-07-29 | 팀 통합 인계 허브를 게시 기준으로 정합화
```

`작업 내용 | 작업 일자` 순서로 뒤집지 않는다. 서로 다른 소유자 또는
서로 독립적으로 되돌려야 하는 작업을 한 Commit에 섞지 않는다. 다만
이번 Crosswalk 후보처럼 Source Hash·생성 Manifest·Runtime 문서가
서로를 검증하는 단일 Hash graph이면 원자적 검토 후보로 게시하고,
각 경로의 주담당자 승인을 별도 병합 Gate로 둔다.

### 9.2 담당자 반환 양식

```text
담당자:
branch:
commit_sha: <40자리>
base_main_sha: <PM이 전달한 40자리>
pr_url: <담당자 Branch PR URL>

변경 파일:
- <상대경로>

적용한 계약:
- <계약 상대경로와 버전>

실행 명령:
1. <명령>
2. <명령>

검증 결과:
- command:
- exit_code:
- passed:
- failed:

완료 범위:
- <완료>

미완료·Blocker:
- <미완료와 필요한 입력>

다음 담당자:
- <이름과 해야 할 작업>
```

### 9.3 최종 완료 조건

다음 조건을 모두 만족해야 이 문서 상태를 `TEAM_BASELINE_READY`로 바꿀
수 있다.

- [x] 변경 경로와 소유자를 분류하고 Data 19경로를 Owner Review 대상으로 표시했다.
- [x] 기본 개발 DB와 격리 검증 DB의 Migration 적용 상태를 확인했다.
- [x] Backend·Data·T-005·PostgreSQL 검증 결과를 같은 후보 내용 기준으로 남겼다.
- [x] `jiyong` 후보가 Push되고 원격 SHA 일치를 확인했다.
- [ ] 김은진이 Data 19경로를 `APPROVED`했거나 수정 SHA를 반환했다.
- [ ] PM이 `main`에 병합하고 40자리 SHA를 공유했다.
- [ ] Web `public_id` Mapping, 지원 Node, Test·Lint·Build,
      지원 Runtime 범위의 Auth Browser/API Smoke가 통과했다.
- [ ] Mobile DTO·Network 연동, JDK 17, Test·Lint·두 App Build,
      Emulator API Smoke가 통과했다.
- [ ] AI 재현 환경·Schema·Runtime 증거가 인계됐다.
- [ ] Backend AI Client와 대표 E2E가 통과했다.
- [ ] 남은 Blocker와 미구현 범위를 완료로 숨기지 않았다.

---

## 10. 빠른 문서 찾기

| 목적 | 문서 |
| --- | --- |
| Backend 최초 설치·재실행 | [Django·PostgreSQL 공유패키지 인계서 v1.3](<../individual/jiyong/manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>) |
| Backend `.venv` 재현 원리 | [Backend 가상환경 재현 가이드](../individual/jiyong/technical/backend/backend_venv_reproducibility_guide.md) |
| API 지원·미구현 범위 | [API Runtime 구현 상태](../api/runtime_implementation_status.md) |
| API 계약 설명 | [API 문서 허브](../api/README.md) |
| State·권한·멱등성 | [State Machine 계약](../../contracts/state-machine/README.md) |
| T-005 구현 기준 | [T-005 README](../database/t-005/README.md) |
| Data→Backend 정합화 | [Data 계약 정합화 진행](data-contract-alignment-progress.md) |
| Data QA | [팀 공유용 Data QA 보고서](../individual/eunjin/%ED%8C%80_%EA%B3%B5%EC%9C%A0%EC%9A%A9_%EB%8D%B0%EC%9D%B4%ED%84%B0_QA_%EC%9E%91%EC%97%85_%EB%B3%B4%EA%B3%A0%EC%84%9C.md) |
| 합성 Import PostgreSQL 실증 | [Runtime 검증·인계서](../individual/jiyong/manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md) |
| Web 현재 이슈 | [Web 3주차 Open Issues](../../web/docs/week3-open-issues.md) |
| Mobile 실행 | [Mobile README](../../mobile/README.md) |
| AI 계약 | [AI 계약 README](../../contracts/ai/README.md) |

이 문서는 상태 요약과 인계 순서를 담당한다. 세부 명령이나 계약을
복사해 중복 유지하지 말고, 위 원본을 수정한 뒤 이 문서의 상태와 링크만
함께 갱신한다.

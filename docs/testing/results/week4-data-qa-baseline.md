# 4주차 Data QA 기준선

> 실행일: 2026-08-07 KST
> 실행 기준: `eunjin@71754053868233d6913538f70e6e78ecaa8584c9`
> 비교 기준: `origin/main@71754053868233d6913538f70e6e78ecaa8584c9`
> 판정: `LOCAL_PASS_REMOTE_CI_BLOCKED_BY_PREEXISTING_CONTRACT_DRIFT`

## 1. 검증 범위

현재 Main의 Data 단위 테스트, 결정적 재생성, QA, Finalize와 Data Diff를
Backend 가상환경 Python 3.13.13에서 검증했다. 공식 DB Migration·Seed·RAG
UPSERT는 실행하지 않았고 Backend·AI Runtime을 수정하지 않았다.

## 2. `backend_runtime_document_missing` 회귀 이력

Data Crosswalk는 다음 Runtime 증빙을 SHA-256과 함께 검증한다.

```text
docs/individual/jiyong/manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md
```

Git 이력으로 확인한 원인은 다음과 같다.

| Commit | 날짜 | 변경 | 영향 |
| --- | --- | --- | --- |
| `cbf1b6c` | 2026-07-29 | Runtime 증빙 추가 | Crosswalk 검증 가능 |
| `f4f4528` | 2026-08-01 | 문서 통합 과정에서 증빙 삭제 | `backend_runtime_document_missing` 발생 가능 |
| `0c1e3d6` | 2026-08-03 | 충돌 해결 과정에서 증빙 복구 | Crosswalk 경로 복구 |

현재 파일은 존재하며 Crosswalk의 UTF-8·LF·BOM 무시 Text Hash 정책 검사를
통과한다. Crosswalk 고정 Text SHA-256은
`07F08FB08C74ADB5F007202C6F1F423DA21CE11267E98F8004972A432E49AD8F`다.
Windows 파일의 원시 Byte Hash와 Text Hash는 줄바꿈 정규화 때문에 다를 수
있으므로 서로 대체하지 않는다.

## 3. 현재 실행 결과

| 검증 | 결과 | Exit Code |
| --- | --- | ---: |
| Data 단위 테스트 | `69/69 PASS` — 기존 67건 + CI 의존 경로 2건 | 0 |
| `qa --verify-rebuild` | PASS, 오류 0, 경고 0 | 0 |
| 검사 범위 | 48파일, 740레코드 | — |
| 대표 E2E | `17/17 PASS` | — |
| 승인 RAG Chunk | 7 | — |
| 합성 Fixture | 367 | — |
| 결정적 재생성 | 변경 0, Canonical Drift 0 | — |
| `finalize` | Dataset 0.9.0, Manifest 155개 | 0 |
| 결정성 재실행 | Manifest SHA-256 전후 동일 | 0 |

`latest_qa_summary.json`의 논리 `generated_at=2026-07-29`와
`source_commit=6512178...`은 결정적 Dataset·계약 계보 값이다. 이번 실제 실행
시각과 Git 기준선은 이 문서와 실행 로그에 별도로 기록하며, 두 필드를 현재
실행 시각이나 HEAD로 임의 변경하지 않는다.

새 테스트 추가 후 Finalize가 `final_dataset_manifest.json`에 해당 파일과
Toolchain 집계를 추가했다. 이후 전체 Gate를 다시 실행한 결과 Manifest
SHA-256은 재실행 전후
`7415F1A666B9CCB20AE54B2FF7EB8FD46A8195126D976451CC7B267C30224D94`로
동일했다. 이 Manifest Diff는 의도된 생성 결과이며 다른 Data 설정·Fixture·QA
결과 Hash는 변경되지 않았다.

## 4. CI 재발 방지

Data 검증이 실제로 읽는 다음 외부 의존성을 `.github/workflows/data-ci.yml`의
Pull Request와 Push Trigger에 동일하게 추가했다.

- `backend_import_crosswalk.json`에 등록된 Backend Source 17개
- Crosswalk가 고정한 Runtime 증빙 문서 1개
- RAG 평가 계약이 고정한 pgvector 결과와 Index Manifest 2개

`data/tools/tests/test_data_ci_dependency_paths.py`는 Crosswalk와 RAG 평가
Dataset에서 의존 경로를 직접 읽어 두 Trigger의 누락을 검사한다. 전체
`backend/**`, `ai/**`, `docs/**`를 감시하지 않아 무관한 변경으로 Data CI가
과도하게 실행되지 않도록 한다.

## 5. 원격 Data CI 교차 검증

`5553dd6`을 `origin/eunjin`에 Push해 생성된
[Data CI Run 31189311449](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM/actions/runs/31189311449)은
`Reject state machine diagram drift` 단계에서 Exit 1로 실패했다. 이 단계가
Data 단위 테스트보다 앞에 있어 원격 Data 테스트·결정적 재빌드·생성물 Drift
검사는 모두 `SKIPPED`됐다.

직전 기준 SHA `7175405`의
[Run 31146633538](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM/actions/runs/31146633538)도
같은 단계와 메시지로 실패했다. 로컬에서도
`python -B scripts/contracts/render_state_machine.py --check`가 동일한 Exit 1을
재현했다. 따라서 이번 Data CI 의존 경로 변경이 만든 회귀가 아니라,
`contracts/state-machine/diagrams/inquiry-state-machine.mmd`와 YAML 계약 간
선행 Drift다.

## 6. 제한 사항

- GitHub Actions 원격 Run은 실행했지만 선행 상태 머신 Drift로 `FAIL`이며,
  Data 관련 단계는 원격에서 실행되지 않았다.
- 현재 PASS는 Data Pipeline의 로컬 재현 결과이며 팀 DB RAG 완료 증거가 아니다.
- 13번째 RAG Case, 팀 DB 적재·검색, T-017B Migration QA는 별도 선행 구현
  부재로 각각 `BLOCKED` 또는 `NOT_RUN`이다.

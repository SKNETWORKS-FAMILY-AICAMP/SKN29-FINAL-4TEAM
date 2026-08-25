# Backend CI 속도 최적화 검증 기록

> 로컬 검증일: 2026-08-25 KST
> 기준: `8f87e7973f3552f93cd6a50301a6f71af8160c89` + 현재 CI 변경 Worktree

## 실행 정책

- PR과 `main` Push에서는 변경 경로 판정과 `Verify Backend baseline` 집계를
  항상 실행한다.
- `backend/**`, `contracts/**`, `scripts/development/**`, Backend CI 판정 자산이
  바뀐 경우에만 세 Backend shard를 실행한다.
- 수동 실행과 Release Workflow 호출은 경로와 관계없이 세 shard를 실행한다.
- Production 배포는 stable SemVer Tag에서 호출된 동일 shard 결과를 사용하며
  별도의 Backend 전체 pytest를 반복하지 않는다.

## 동일 HEAD 로컬 비교

| 실행 | Passed | Skipped | pytest 시간 |
|---|---:|---:|---:|
| `domain` | 551 | 6 | 312.05초 |
| `platform` | 555 | 10 | 65.39초 |
| `api-integration` | 397 | 25 | 290.38초 |
| 세 shard 합계 | 1,503 | 41 | 병렬 임계 경로 312.05초 |
| 기존 단일 전체 회귀 | 1,503 | 41 | 546.45초 |

테스트 실행 시간만 비교하면 병렬 임계 경로는 234.40초, 약 42.9% 줄었다.
GitHub Runner 준비·의존성 Cache·Queue 시간은 이 로컬 수치에 포함되지 않는다.

## 원격 확인 필요

- Docs 전용 PR에서 세 shard 미실행과 경량 집계 성공
- Backend PR에서 세 shard 병렬 실행과 집계 성공
- Data 전용 PR에서 Backend shard 미실행과 Data CI 실행
- stable SemVer Tag에서 모든 Release Gate 뒤 Build·Deploy 진입
- 비정식 Tag와 `main` 밖 Commit Tag가 AWS 변경 전에 실패

Commit·Push·Tag·실제 배포를 수행하지 않았으므로 위 항목과 GitHub Actions의
변경 전후 벽시계 비교는 원격 Run에서 확인해야 한다.

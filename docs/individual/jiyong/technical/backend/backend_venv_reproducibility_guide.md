# Backend `.venv` 재현성과 VS Code 환경 설계 가이드

> 기준일: 2026-07-29
> 문서 상태: `CURRENT`
> 작성·유지 책임: 최지용
> 적용 범위: `backend/.venv`, Backend Python 의존성, 로컬 VS Code 연결
> 검토 상태: 미요청 또는 검토 증거 미확인

## 1. 결정

이 저장소는 루트에 하나의 공용 `.venv`를 두지 않고
`backend/.venv`를 Django Runtime 전용 환경으로 사용한다.
가상환경 디렉터리는 PC마다 새로 만들며 Git이나 파일 압축으로
공유하지 않는다. 팀에 공유하는 것은 다음 재현 입력과 자동화다.

| 단일 원본 | 책임 |
| --- | --- |
| [Python 버전](<../../../../../backend/.python-version>) | Python `3.13.13` 고정 |
| [직접 공통 의존성](<../../../../../backend/requirements/base.txt>) | Django Runtime 직접 의존성 |
| [직접 로컬 의존성](<../../../../../backend/requirements/local.txt>) | 개발·테스트 직접 의존성 |
| [간접 의존성 constraints](<../../../../../backend/requirements/constraints-py313.txt>) | Python 3.13 검증 해상도 32개 고정 |
| [환경 생성 스크립트](<../../../../../scripts/development/bootstrap.py>) | 생성·동기화·안전 재생성 |
| [환경 검증 스크립트](<../../../../../scripts/development/check_environment.py>) | 읽기 전용 재현성 게이트 |
| [VS Code 설정](<../../../../../.vscode/settings.json>) | 상대경로 Interpreter·터미널 활성화 |
| [VS Code Task](<../../../../../.vscode/tasks.json>) | 빠른 검사·최초 생성·전체 검증 진입점 |

`ai/**`는 별도 서비스 경계다. 현재 AI 의존성 Manifest와 실행 기준이
확정되지 않았으므로 이 작업에서 `ai/.venv`나 AI 패키지 잠금 파일을
추측해 만들지 않는다. 이동윤이 AI Runtime 기준을 확정하면 같은
원칙으로 별도 환경을 추가한다.

## 2. 네 지침서 반영

| 지침 | 이번 반영 |
| --- | --- |
| 프로젝트 디렉터리 구조 | Backend 환경은 `backend/**`, 공통 로컬 자동화는 `scripts/development/**`, 개인 개발문서는 `docs/individual/jiyong/**`에 배치 |
| 공통 개발 규칙 | Secret 비공유, 상대경로, 재현 명령과 검증 결과 기록, 작성자 외 재현·통합 확인을 품질 게이트로 유지 |
| 최지용 3주차 업무 지침서 | Django·PostgreSQL 주관 범위와 T-005·T-016·T-017 우선순위를 유지 |
| 팀원별 관할 영역 | Backend 환경은 최지용, 개발 자동화는 김은진 주관·최지용 부관, 루트 Workspace 설정은 윤승혁 주관·김은진 부관으로 인계 |

위 역할 구분은 최지용이 Backend 환경을 작성하기 위한 선행 승인을
뜻하지 않는다. 김은진은 다른 PC 재현, 윤승혁은 공통 Workspace와
통합 충돌 여부를 확인하는 후속 품질 역할이다.

## 3. `.venv`가 하는 일과 하지 않는 일

`backend/.venv`는 Python Interpreter와 설치된 Python 패키지를
저장소의 다른 프로젝트·시스템 Python에서 격리한다. VS Code는
[설정](<../../../../../.vscode/settings.json>)의 상대경로를 사용해
이 Interpreter를 선택하고 새 통합 터미널에서 활성화한다.

다음 항목은 `.venv`의 역할이 아니다.

- 저장소 폴더로 이동하는 것: VS Code의 `terminal.integrated.cwd`가 담당
- Python 3.13.13 자체를 다운로드하는 것: 각 PC에 먼저 설치해야 함
- PostgreSQL을 실행하는 것: [Compose](<../../../../../docker-compose.yml>)가 담당
- `.env` 비밀값을 만드는 것: 각 PC 소유자가 로컬에서 관리
- Migration·Seed를 자동 적용하는 것: 명시적 검증 순서에서만 실행
- AI 패키지를 함께 설치하는 것: AI는 별도 서비스 환경

즉, 저장소를 열면 현재 PC에 이미 만들어진 `backend/.venv`가 자연스럽게
선택된다. 최초 Pull처럼 환경이 없을 때는 Workspace Trust를 확인하고
bootstrap을 한 번 실행해야 한다.

## 4. 버전과 의존성 정책

### 4.1 Python

- 기준: `3.13.13` 정확한 패치 버전
- 표시 파일: [`.python-version`](<../../../../../backend/.python-version>)
- 생성 기반이 Conda의 Python이어도 결과물은 표준 `venv`다.
- `backend/.venv` 내부의 Python이 다르면 자동 덮어쓰기하지 않고
  `--recreate`를 요구한다.

### 4.2 pip와 패키지

- pip: `26.0.1`
- 직접 의존성: `base.txt`, `local.txt`
- 직접·간접 해상도: `constraints-py313.txt`
- 설치 명령은 `local.txt`와 constraints를 함께 사용한다.
- 현재 검증 기준은 constraints 32개, constraints 밖 추가 패키지 0개다.

의존성을 바꿀 때는 직접 요구 파일만 수정하고 끝내지 않는다. 깨끗한
임시 환경에서 새 해상도를 설치하고 `pip check`, Django check,
Migration drift, 전체 pytest를 통과한 뒤 constraints와 이 문서의
검증 결과를 같은 변경 단위로 갱신한다.

## 5. 최초 생성과 일상 사용

### 5.1 최초 생성

Python 3.13.13이 현재 `python` 명령으로 실행되는지 확인한다.

```powershell
python --version
python .\scripts\development\bootstrap.py --service backend
```

bootstrap은 다음 순서만 수행한다.

1. 실행 Python과 `.python-version` 비교
2. `backend/.venv`가 없으면 최종 경로에 직접 생성
3. pip 26.0.1 고정
4. `local.txt + constraints-py313.txt` 설치
5. `pip check`와 테스트 설정의 Django check
6. requirements fingerprint를 `.venv` 안의 로컬 상태파일에 기록

`.env`, Docker, Migration, Seed와 실제 DB 데이터는 변경하지 않는다.

### 5.2 일상 사용

VS Code에서 저장소 루트를 열고 새 터미널을 만들면
`backend/.venv`가 선택·활성화된다. 폴더 열기 Task는 패키지를
설치하지 않고 다음 빠른 검사만 실행한다.

```powershell
python .\scripts\development\check_environment.py --service backend
```

requirements fingerprint가 같으면 bootstrap을 다시 실행해도 설치를
생략하고 경량 검증만 수행한다.

### 5.3 공유 전 전체 검사

```powershell
python .\scripts\development\check_environment.py --service backend --full
```

전체 모드는 다음을 확인한다.

- `pyvenv.cfg`와 system site-packages 격리
- Python·pip 정확한 버전
- constraints 32개 버전과 추가 패키지
- requirements fingerprint
- `pip check`, Django system check
- Migration drift
- Backend 전체 pytest
- `backend/.venv` Git 추적 파일 0개

PostgreSQL이 실행 중이고 현재 Commit의 Migration 적용까지 끝난 경우에만
읽기 전용 연결과 적용 Migration 검사를 추가한다. 새 DB에서는 먼저
[공유 패키지 인계서 v1.3](<../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)의
사전 검사 → Migration·Seed → 최종 Gate 순서를 따른다.

```powershell
python .\scripts\development\check_environment.py `
  --service backend `
  --full `
  --postgresql
```

Seed와 Health·Auth Smoke는 DB와 HTTP 상태를 바꾸므로 이 읽기 전용 검사에
포함하지 않고 [공유 패키지 인계서 v1.3](<../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)의
명시적 순서로 실행한다.

### 5.4 환경 준비 후 서버 다시 켜기

이 문서는 `.venv` 생성·검증·복구까지만 책임진다. 최초 설치가 끝난
PC에서 PostgreSQL과 Django를 다시 켜거나 종료·재시작할 때는
[공유 패키지 인계서 v1.3](<../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)을
사용한다. requirements fingerprint가 같고 빠른 검사가 통과하면
bootstrap과 패키지 설치를 다시 실행하지 않는다.

### 5.5 fingerprint 불일치 해석과 동기화

빠른 검사에서 다음 결과가 나오면 requirements 파일 자체가 잘못됐다고
바로 판정하지 않는다.

```text
[FAIL] requirements fingerprint 불일치. bootstrap.py를 실행하세요.
```

이 메시지는 `base.txt`, `local.txt`, constraints와 Python·pip 기준을
합친 현재 SHA-256과 `.venv` 내부 상태파일에 기록된 SHA-256이 다르다는
뜻이다. 저장소 루트에서 같은 작업을 반복하지 말고 다음 두 단계만
순서대로 실행한다.

```powershell
python .\scripts\development\bootstrap.py --service backend
python .\scripts\development\check_environment.py --service backend
```

첫 명령은 현재 패키지 집합을 검사하고 필요한 경우에만 동기화한 뒤
fingerprint 상태를 갱신한다. 두 번째 명령에서 같은 64자리 SHA-256,
`failures=0`, Exit code `0`이 확인되면 동기화 완료다. Python 버전이
다르거나 환경이 손상된 경우에만 다음 장의 `--recreate`를 사용한다.

## 6. 안전 재생성·복구

가상환경은 다른 경로로 옮긴 상태에서 사용할 수 없다. 손상되었거나
Python 버전이 바뀐 경우, 교체 대상 `.venv` 밖의 Python 3.13.13으로
다음 명령을 실행한다.

```powershell
python .\scripts\development\bootstrap.py --service backend --recreate
```

스크립트는 기존 환경을
`backend/.runtime/venv-backups/<timestamp>/.venv`로 이동하고 원래
`backend/.venv` 위치에 새 환경을 만든다. 생성·설치·경량 검증이
실패하면 새 환경만 제거하고 백업을 원래 위치로 복원한다.

성공해도 백업은 즉시 자동 삭제하지 않는다. `--full` 검증까지
통과한 뒤 출력된 정확한 백업 경로만 삭제한다. `.runtime` 전체나
상위 폴더를 재귀 삭제하지 않는다.

## 7. Git·보안 경계

- `.venv/`, `.runtime/`, `.env`는 Git에서 제외한다.
- `.env.example`에는 변수명, 공개 가능한 로컬 기본값,
  `replace-with-*` 표식만 둔다.
- 실제 Django Secret, PostgreSQL Password, Token, 고객정보는
  문서·로그·커밋에 기록하지 않는다.
- VS Code, 스크립트와 Markdown에는 개인 PC 절대경로를 넣지 않는다.
- Python 설치 프로그램이나 Conda 환경 전체를 팀에 전달하지 않는다.
- 팀 공유는 버전 파일, requirements, constraints, 자동화, 검증 기록으로
  한정한다.

## 8. 2026-07-29 작성자 환경·Runtime 검증

다음 표는 합성 Schema·Migration 통합 전 v1.2 기준선의 역사 기록이다.
후속 테스트 수와 기본 DB Migration 결과로 이 수치를 덮어쓰지 않는다.

| v1.2 기준선 검증 | 당시 결과 |
| --- | --- |
| bootstrap 동기화 | Exit code `0` |
| Python | `3.13.13` |
| pip | `26.0.1` |
| constraints 패키지 | 32개 일치 |
| constraints 밖 추가 패키지 | 0개 |
| requirements fingerprint | `350a1d4c0a03d91be0a5b95361ae7a32634d1cc99475d9e58bce2e7a87c8fdb5` |
| `pip check` | 통과 |
| Django system check | 통과 |
| Migration drift | 없음 |
| Backend 전체 테스트 | `353 passed` |
| `.venv` Git 추적 파일 | 0개 |
| Docker daemon | Docker Desktop 4.75.0·Engine 29.5.2 연결 통과 |
| PostgreSQL | 16.14, `running`·`healthy`, UTC 읽기 전용 연결 통과 |
| 적용 Migration | 누락 없음 |
| Health·Auth Smoke | `status=PASSED`, Exit code `0` |

이 표는 최지용 작성자 PC에서 2026-07-29에 실행한 당시 증거다. 테스트가
추가되면 개수는 달라질 수 있으므로 장기 정상 기준은 Exit code `0`,
`failures=0`, Migration drift 없음이다. 김은진의 독립 재현이나 PR
비작성자 리뷰가 완료됐다는 증거로 해석하지 않는다.

`353 passed`는 `backend/`의 Python 테스트만 집계한 값이다. Web의
Node·npm 버전, 자동 테스트와 실제 Browser API 소비 검증은 별도
게이트이며 이 숫자에 포함되지 않는다.

### 8.1 합성 Schema·Migration 통합 후 현재 실측

| 현재 검증 | 결과 |
| --- | --- |
| Backend 전체 테스트 | `397 passed` |
| 테스트 DB | `config.settings.test`의 SQLite |
| PostgreSQL | 16.14, 기본 `watercare` 읽기 전용 연결 통과 |
| 적용 Migration | 기존 미적용 9개 + `workflow.0003`, 누락 0 |
| 기존 데이터 | 적용 전후 테이블별 row count 보존 |
| Workflow 보정 | 기존 11건의 `changed_at`을 원래 `created_at`으로 보정 |
| Demo Seed | 4종 명령 2회 실행, 비의도 중복 0 |
| Migration drift | 없음 |

`397 passed`는 PostgreSQL에서 실행한 테스트 수가 아니다. Pytest는
SQLite 테스트 설정을 사용하고, 같은 `--full --postgresql` Gate가 실제
PostgreSQL 연결과 적용 Migration을 별도의 읽기 전용 단계로 확인한다.
상세 적용·보정 증거는
[PostgreSQL 합성 Handoff Runtime 검증·인계서](<../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md>)에
누적했다.

기본 `watercare`에서는 합성 Importer와 `--dry-run`을 실행하지 않는다.
canonical fixture와 기존 공개 UUID가 달라 예상되는 UUID mismatch를
우회하지 않으며, Importer는 새 빈 격리 DB에서만 검증한다. dry-run도
PostgreSQL Sequence를 바꿀 수 있으므로 기본 DB의 읽기 전용 환경 Gate와
동일시하지 않는다.

## 9. 담당자별 인계

| 대상 | 전달 범위 | 다음 행동 | 완료 증거 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 김은진 | `scripts/development/**`, requirements·constraints, 전체 검사 | 새 Pull 환경에서 bootstrap과 Migration 적용 후 `--full --postgresql`, Health·Auth Smoke를 재현하고 Windows/Linux 차이를 기록 | 사용한 Python, 명령, exit code, 테스트 수를 PR 또는 Issue에 기록 | 작성자 현재 397 테스트·PostgreSQL 읽기 전용 Gate 검증 완료, 독립 재현 미확인 |
| 윤승혁(PM) | `.vscode/**`, 루트 `.gitignore`, 서비스별 환경 경계 | Web·AI Workspace 설정과 충돌이 없는지 확인하고 비작성자 리뷰 후 통합 | 검토 의견 또는 PR 리뷰와 병합 Commit | 통합 검토 미확인 |
| 이동윤 | Backend와 분리된 AI 환경 원칙 | AI Manifest·Python·실행 명령 확정 후 `ai/.venv` 재현 입력 작성 | AI 단독 설치·테스트 기록 | AI 환경 기준 미확정 |
| 한예나·양정현 | Backend Interpreter가 아닌 HTTP API 소비 경계 | `.venv`를 복사받지 않고 Backend URL·계약으로 연동 | Web·Mobile 소비 호환성 결과 | 소비 확인 미확인 |

## 10. 작업 순서

환경 작업도 기능 작업과 같은 `작업 → 검증` 원칙을 따른다.

1. Python·requirements 입력 변경
2. 깨끗한 임시환경 설치·전체 검증
3. 실제 `backend/.venv` 재생성
4. 실제 환경 전체 검증
5. 공유 패키지 인계서 v1.3과 환경 검증 기록 갱신
6. 환경 기준선이 통과한 뒤 T-005의 다음 한 Wave 작업
7. 해당 Wave 검증 후 다음 작업

환경 자동화와 T-005·T-022·T-023 Runtime을 한 번에 섞지 않는다.

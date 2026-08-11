# 이동윤 → 김은진 AI venv·설치 방식 SSOT 확인 회신 v0.1

> 작성일: 2026-08-10 KST
> 발신자: 이동윤 / AI·RAG
> 수신자: 김은진 / Data·QA·DevOps

## 1. 결론

```text
install_ssot=ai/requirements.lock
runtime_mode=MONOREPO_SOURCE_RUNTIME
runtime_working_directory=repository_root
package_install_supported=NO
editable_install_supported=NO
wheel_distribution_supported=NO
```

현재 AI는 저장소 Root에서 `ai.app`을 소스로 직접 Import하는 Runtime이다.
`pip install ai`, `pip install .\ai`, `pip install -e .\ai`는 공식 설치 방식이
아니며 지원하지 않는다. `ai/pyproject.toml`은 Metadata·직접 의존성·Pytest
설정용이고 배포 가능한 Python Package 계약이 아니다.

## 2. 재현 결과

| 검증 항목 | 결과 |
|---|---|
| Python | `3.13.13` |
| `pip check` | PASS |
| 저장소 Root `import ai.app.main` | PASS |
| 저장소 밖 `import ai.app.main` | FAIL — Source Runtime 범위 밖 |
| `pip install .\ai` dry-run | FAIL 재현 — 복수 최상위 Package 자동 탐색 |
| `pip install -e .\ai` dry-run | FAIL 재현 — 동일 원인 |
| pyproject↔requirements.txt 직접 의존성 | 10/10 일치 |
| requirements.lock 직접·Extra 전이 Package | PASS |
| AI Unit | `127 passed, 3 warnings` |

단위 Test는 저장소 Root가 Python Import 경로에 포함되므로 `ai.app` 소스를 직접
불러온다. setuptools 배포 Package Metadata 생성은 별도 경로이므로 단위 Test
PASS와 `pip install .\ai` 실패는 모순이 아니다.

## 3. 공식 설치·실행·검증 명령

저장소 Root에서 다음 하나의 기준을 사용한다.

```powershell
py -3.13 -m venv ai\.venv
.\ai\.venv\Scripts\python.exe -m pip install -r ai\requirements.lock
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -c "import ai.app.main"
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
```

## 4. 반영 내용

- Root README와 AI README에 `requirements.lock` 설치 SSOT를 명시했다.
- Package·Editable·Wheel 설치 비지원과 저장소 Root 실행 조건을 명시했다.
- `ai/pyproject.toml`에 현재 용도를 주석으로 명시했다.
- pyproject·requirements.txt·requirements.lock의 직접 의존성 이름·Version과
  Extra 전이 Package를 검증하는 단위 Test를 추가했다.

Package 배포가 필요해지는 경우에는 현재 `ai` 내부를 Build Root로 둔 채 탐색
설정만 추가하지 않고, `ai.app` Import 경로를 보존하는 Package Layout과 Wheel·
Editable 설치를 별도 변경으로 설계·검증한다.

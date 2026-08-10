# Mobile Extension Workspace

이 디렉터리는 양정현 Mobile 확장 기능 전용 작업공간이다.

## Scope

```text
personal/mobile-extension/**
```

확장 작업은 이 경로 아래에서만 작성한다.

기존 제품 본체:

```text
mobile/**
```

는 Week5 실제 Backend 연동 및 회귀 기준선으로 유지하며,
확장 기능을 이유로 임의 수정하지 않는다.

## Directory

```text
personal/mobile-extension/
├─ README.md
├─ app/
├─ docs/
├─ scripts/
└─ tests/
```

- `app/`: 확장 기능 소스 또는 독립 실행 예제
- `docs/`: 설계·기능 정의·검증 결과
- `scripts/`: 확장 전용 실행/검증 스크립트
- `tests/`: 확장 전용 테스트

## Git rule

- 작업 브랜치 기준: `jeonghyun`
- `main` 직접 push 금지
- force push 금지
- 확장 커밋은 원칙적으로 `personal/mobile-extension/**`만 포함
- `mobile/**`, `backend/**`, `web/**`, `ai/**` 수정이 필요하면 별도 통합 작업으로 분리

## Runtime rule

Backend/AI Runtime이 아직 없는 기능은 실제 성공처럼 구현하지 않는다.

확장 기능이 본체 API를 소비해야 할 경우:

1. 실제 Route 존재 확인
2. 계약/권한 확인
3. 확장 경로에서 adapter 또는 prototype 구현
4. 실제 본체 반영은 별도 검토 후 진행

## Baseline

- scaffold base `jeonghyun`: `59436a9076c087af3d893b50c39b7067d61fb3f1`
- included `main`: `2198e9e90fe894fb848d551ef638fb3ae0a2b433`

## Week5 Autonomous Completion Gate

5주차 업무지침서에서 Mobile 담당자가 독자적으로 수행 가능한 회귀·실단말·보안·Runtime 판정을 자동화한다.

반복 실행:

```powershell
python personal/mobile-extension/scripts/run_week5_autonomous_gate.py --repo-source <repo> --config-source <config-worktree> --bundle-dir <bundle>
```

판정 원칙:

- 고객 Subscription / Inquiry create / symptom submit: 실제 Runtime 사용
- 상담사 Consultation / Visit scheduling: Backend Runtime 존재 여부와 회귀 검증
- 고객 Follow-up / request-consultation: Runtime 미구현이면 Blocked
- 기사 assigned Visit list/detail / start / complete: Runtime 미구현이면 Blocked
- Guidance/Evidence: 고객 Runtime 미구현이면 Remote fail-closed
- 미구현 Runtime을 Mobile Fake 성공으로 대체하지 않음

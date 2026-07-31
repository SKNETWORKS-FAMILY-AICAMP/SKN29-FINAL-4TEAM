# 정수기 딜러 팀 통합 인계 허브

> 기준일: 2026-07-31
>
> 문서 책임: 공동 편집(`docs/**`)
>
> 현재 상태: `WATERBRIDGE_LOCAL_GATE_PASS_T005_TECHNICALLY_READY_APPROVAL_PENDING`
>
> 현재 기본 DB: `waterbridge` / Schema: `public`
>
> 실행 원칙: `작업 → 즉시 검증 → 다음 작업`

## 1. 이 문서의 역할

이 문서는 팀원이 현재 기준선, 남은 Gate, 담당자와 인계 순서를 빠르게
확인하는 공용 진입점이다. 긴 실행 절차, 특정 시점 검증 수치와 담당자별
상세 요청은 아래 단일 원본으로 연결한다.

| 목적 | 단일 원본 |
| --- | --- |
| 담당자별 요청·반환 증거 | [백엔드 팀 검토 및 인계 체크리스트](../individual/jiyong/team_handover/백엔드_팀_검토_및_인계_체크리스트.md) |
| WaterBridge 설치·Migration·Seed·복구 | [WaterBridge 백엔드 실행 가이드](../individual/jiyong/manuals/워터브리지_백엔드_설치_마이그레이션_시드_복구_가이드.md) |
| T-005 PostgreSQL 실행 증거 | [T-005 WaterBridge PostgreSQL 통합 검증 보고서](../individual/jiyong/technical/backend/20260731_t005_워터브리지_postgresql_통합_검증_보고서.md) |
| T-005 계약·변경 절차 | [T-005 데이터베이스 스키마 변경 실행 가이드](../individual/jiyong/technical/backend/t005_데이터베이스_스키마_변경_실행_가이드.md) |
| T-005 구현 역사 | [T-005 테이블 구현·변경 이력](../individual/jiyong/technical/backend/20260730_t005_테이블_구현_및_변경_이력.md) |
| 합성 데이터 적재 | [합성 데이터 Schema·Importer·PostgreSQL 검증 가이드](../individual/jiyong/technical/backend/합성_데이터_스키마_적재기_postgresql_검증_가이드.md) |
| Backend·AI 미해결 계약 | [백엔드·AI 계약·Runtime 통합 미해결 사항](../individual/jiyong/technical/contracts/백엔드_ai_계약_런타임_통합_미해결_사항.md) |

## 2. 판단 기준

충돌할 때는 다음 순서로 확인한다.

1. `contracts/**`의 기계 판독 계약
2. Django Model·Migration·Route와 실제 Runtime 검증 결과
3. 담당자 Commit과 PM이 병합한 `main` 40자리 SHA
4. 이 문서를 포함한 설명 문서
5. 과거 계획표·회의 메모

설명 문서가 계약 또는 실행 결과와 다르면 설명 문서를 수정한다. 실패한
테스트를 피하기 위해 다른 담당자의 계약·데이터·Runtime을 임의로
변경하지 않는다.

| 상태 | 의미 |
| --- | --- |
| `LOCAL_VERIFIED` | 작성자 환경에서 검증했지만 팀 기준선으로 승인되지 않음 |
| `SHARED_CANDIDATE` | 담당자 Branch에 Push됐지만 PM `main` 병합 전 |
| `TEAM_BASELINE` | PM이 검토·병합하고 40자리 `main` SHA를 공유함 |
| `BLOCKED_EXTERNAL` | 다른 담당자 입력이나 소비 검증을 기다림 |
| `FOLLOW_UP` | 기준선 반영 뒤 이어서 수행할 항목 |

## 3. 현재 WaterBridge·T-005 Gate

| 항목 | 현재 결과 | 판정 |
| --- | --- | --- |
| PostgreSQL | `waterbridge.public`, PostgreSQL 16.14 | `PASS` |
| T-005 물리 계약 | 32개 테이블, Model·Registry·Migration 32/32 | `TECHNICALLY_READY` |
| Active 범위 | 13개 테이블·총 369행 | `PASS` |
| Target-only 범위 | 19개 테이블·각 0행으로 보존 | `PASS` |
| Migration·Seed | Drift·미적용 0, 기본 Seed 2회 멱등 | `PASS` |
| 합성 Importer | 빈 격리 DB에서만 367건 Import·Replay 검증 | `PASS_WITH_SAFETY_RULE` |
| Backend 회귀 | SQLite `740 passed, 11 skipped`, PostgreSQL `751 passed` | `PASS` |
| Data QA | 67 tests, 대표 E2E 17/17, 오류·경고 0 | `PASS` |
| 공식 완료 | 기술 Gate 통과, 외부 승인은 미반영 | `REVIEW_PENDING` |

Active 13과 Target-only 19는 서로 다른 Schema가 아니다. 32개 물리
계약은 모두 유지하고, Target-only 테이블은 데이터와 소비 기능이
준비되는 순서대로 활성화한다.

합성 Importer는 기본 `waterbridge`에서 `--dry-run`을 포함해 실행하지
않는다. 새 빈 격리 DB에서 Migration 후 실행·Replay하고 검증 뒤 해당
격리 DB를 제거한다.

작성자 격리 재현 수치는
[`t005_author_isolated_reproduction_evidence_20260731.json`](../database/t-005/t005_author_isolated_reproduction_evidence_20260731.json)에
기록한다. 이 파일은 비작성자 승인 증거가 아니다.

## 4. 지금 인계할 순서

| 순서 | 담당 | 해야 할 일 | 완료 증거 |
| ---: | --- | --- | --- |
| 1 | 최지용 | 동일 작업 단위의 코드·Migration·계약·문서·검증 결과와 후보 SHA 전달 | 40자리 SHA, 변경 범위, 실행 명령·Exit code |
| 2 | 김은진 또는 지정 비작성자 | 새 worktree·새 PostgreSQL Volume에서 독립 재현 | 32/32, Seed 2회차 신규 0, Importer Replay, 전체 회귀 |
| 3 | 윤승혁(PM) | 계약·비작성자 증거 검토 후 완료·병합 여부 결정 | 승인 기록과 병합된 `main` SHA |
| 4 | 한예나 | PM `main` 기준 Web UUID·Auth·오류 응답 소비 검증 | Test·Lint·Build·실제 API Smoke |
| 5 | 양정현 | PM `main` 기준 Mobile DTO·Network·상태·멱등 소비 검증 | Unit·Lint·두 App Build·Emulator Smoke |
| 6 | 이동윤 | PM `main` 기준 AI Schema·Vector·Evidence 소비 검증 | 계약 Parity·검색 후검증·통합 E2E |

Gate 4~6이 남았다는 이유로 Gate 1~3을 임의 완료 처리하지 않는다.
반대로 Backend 담당자가 Web·Mobile·AI 담당 파일을 대신 수정하지 않는다.

## 5. 담당자별 현재 요청

| 담당 | 주관 영역 | 현재 요청 |
| --- | --- | --- |
| 최지용 | Backend·DB·Public API 계약 | 후보 SHA·실행 증거 제공, 회신된 계약 차이 반영 |
| 김은진 | `data/**`, Data QA·재현 검토 | Fixture·Crosswalk·Hash와 빈 PostgreSQL 독립 재현 |
| 윤승혁(PM) | State 계약·완료·병합 Gate | 완료 Evidence와 외부 소비 결과 검토 |
| 한예나 | `web/**` | Runtime 7개와 Mock/Blocked 경계, UUID·401/403 소비 |
| 양정현 | `mobile/**` | Auth·문의·상태·멱등 DTO와 실제 Network 연동 |
| 이동윤 | `ai/**`, `contracts/ai/**` | Schema/Pydantic Parity, 로그·취소·검색 후검증·Revision |

세부 체크박스와 반환 형식은
[백엔드 팀 검토 및 인계 체크리스트](../individual/jiyong/team_handover/백엔드_팀_검토_및_인계_체크리스트.md)를
사용한다.

## 6. 현재 차단 요소

| 우선순위 | 항목 | 주담당 | 해제 조건 |
| ---: | --- | --- | --- |
| P0 | T-005 비작성자 독립 재현 | 김은진 또는 지정 리뷰어 | 같은 SHA의 새 DB Migration·Seed·Importer·회귀 Evidence |
| P0 | T-005 공식 완료·`main` 병합 | 윤승혁(PM) | v1.3 계약·비작성자 Evidence·완료 경계 승인 |
| P1 | T-017A 합성 계정 관리 설계 검토 | 윤승혁·김은진 | 정책·Migration·감사 원장 검토 |
| P1 | T-022 `SUBMIT_SYMPTOM` Runtime | 최지용 | 계약 게이트 통과 후 첫 수직 Slice 구현·검증 |
| P1 | Web·Mobile 소비 검증 | 한예나·양정현 | PM `main` SHA와 실제 API 연동 결과 |
| P1 | Backend·AI 계약·Runtime 통합 | 이동윤·최지용 | AI 계약 Parity·Adapter·Evidence·통합 E2E |
| P2 | 전 영역 동일 SHA E2E | 각 담당·PM | 위 P0·P1 완료 |

T-005 Runtime은 현재 `READY 32/32`, 구현 blocker 0이다. 공식 WBS
상태는 비작성자 재현·외부 소비 검토·PM 승인 전까지 진행 중으로 유지한다.

## 7. 변경 금지 기준

| 계약 | 원본 | 원칙 |
| --- | --- | --- |
| REST Method·Path·Schema | [OpenAPI](../../contracts/api/openapi.yaml) | 변경 후 사람용 명세·예시·테스트를 함께 갱신 |
| 오류 코드 | [Error Registry](../../contracts/error-codes/error-codes.yaml) | Runtime과 예시를 같은 작업에서 갱신 |
| 공통 코드 | [Code Registry](../../contracts/codes/) | 문자열 임의 생성 금지 |
| 상태·Action·권한 | [State Machine](../../contracts/state-machine/README.md) | PM 관할 입력을 Backend가 소비 |
| AI Request·Response | [AI 계약](../../contracts/ai/README.md) | AI 관할 입력을 Backend Client가 소비 |
| T-005 물리 계약 | [T-005 기준](../database/t-005/README.md) | 계약과 Runtime 완료 상태를 분리 |
| 합성 데이터 | [Data 정합화 진행](data-contract-alignment-progress.md) | Data 원본·QA와 Backend Import 책임을 분리 |

공통 불변식:

- 내부 PK·외부 공개 UUID·업무 코드를 분리한다.
- 상태 변경과 최종 권한 검사는 Backend가 수행한다.
- 쓰기 Action은 `state_version`, `Idempotency-Key`, 전이 이력을 검증한다.
- Schema 변경은 Django Migration으로 남기며 적용된 Migration을 수정하지 않는다.
- `.env`, `.venv`, Token, Password, Dump와 로컬 Volume을 Git에 올리지 않는다.
- 실제 개인정보를 사용하지 않고 가명·합성 데이터만 사용한다.

## 8. Git 공유와 반환 형식

팀원은 전달받은 후보 SHA와 원격 HEAD를 확인한다.

```powershell
git fetch origin
git rev-parse origin/main
git rev-parse origin/<담당자-브랜치>
git status --short
```

반환할 최소 증거:

```text
branch=<브랜치>
commit=<40자리 SHA>
environment=<OS·Runtime·DB 버전>
commands=<실행 명령>
exit_codes=<명령별 Exit code>
tests=<테스트 결과>
contract_diff=<계약 차이 또는 없음>
remaining_blockers=<남은 차단 요소>
```

기존 작업트리에 미커밋 변경이 있으면 삭제·초기화하지 않는다. 다른
담당자의 경로를 수정해야 할 경우 직접 고치지 않고 차이와 재현 절차를
반환한다.

## 9. 빠른 문서 찾기

| 목적 | 문서 |
| --- | --- |
| Backend 최초 설치·재실행 | [WaterBridge 백엔드 실행 가이드](../individual/jiyong/manuals/워터브리지_백엔드_설치_마이그레이션_시드_복구_가이드.md) |
| Backend 가상환경 | [백엔드 Python 가상환경 재현 가이드](../individual/jiyong/technical/backend/백엔드_파이썬_가상환경_재현_가이드.md) |
| API 계약·Runtime 증거 | [백엔드 API 통합 검증 보고서](../individual/jiyong/manuals/20260729_백엔드_api_계약_및_런타임_통합_검증_보고서.md) |
| API 변경 절차 | [백엔드 API 계약 개발·인계 가이드](../individual/jiyong/technical/backend/백엔드_api_계약_개발_및_인계_가이드.md) |
| 합성 고객 로그인 | [합성 고객 데모 로그인 가이드](../individual/jiyong/manuals/합성_고객_데모_로그인_가이드.md) |
| Data QA Hash·Crosswalk | [합성 데이터 Fixture Hash·Crosswalk 검증 보고서](../individual/jiyong/technical/contracts/합성_데이터_픽스처_해시_교차표_검증_보고서.md) |
| Web 현재 이슈 | [Web 3주차 Open Issues](../../web/docs/week3-open-issues.md) |
| Mobile 실행 | [Mobile README](../../mobile/README.md) |
| AI 계약 | [AI 계약 README](../../contracts/ai/README.md) |

과거 10/32·12/32·13/32와 개별 담당자 인계 전문은 Git 이력과
[T-005 테이블 구현·변경 이력](../individual/jiyong/technical/backend/20260730_t005_테이블_구현_및_변경_이력.md)에서
확인한다. 이 허브에는 현재 기준선과 다음 행동만 유지한다.

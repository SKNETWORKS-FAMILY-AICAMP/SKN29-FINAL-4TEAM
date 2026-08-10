# 4주차 범위 및 완료 조건

> 기준일: **2026-08-07 KST**
> 기준 브랜치/Commit: `main@dad0e7a2c0e6c184ac8811bce6c6974bd7cb3fe0`
> 판정: **3.1 저장소 산출물 완료 / 3.3 로컬 기준선 완료·외부 Issue 확인 대기**

## 1. 작업 목적

4주차 업무 지침서 3.1의 목적은 최신 `main`에서 영역별 통과·실패·미검증 상태를 같은 기준으로 분류하고, WBS와 차단 요소 및 후속 인계를 실제 상태에 맞추는 것이다.

상태 판정은 다음 여섯 종류만 사용한다.

| 상태 | 의미 |
|---|---|
| `VERIFIED_DONE` | 현재 기준선에서 직접 실행해 통과함 |
| `DONE_WITH_LIMITATION` | 구현 또는 과거 증거는 있으나 현재 전체 Gate나 실연동 증거가 부족함 |
| `INTEGRATION_BLOCKED` | 환경·타 영역·미구현 의존성 때문에 실연동 검증이 막힘 |
| `MOCK_ONLY` | Mock·Fixture 경계까지만 동작함 |
| `CONTRACT_ONLY` | 계약·예시·테스트 골격만 있고 Runtime이 없음 |
| `NOT_STARTED` | 검증 가능한 구현 또는 산출물이 없음 |

## 2. 포함 범위

- Data 단위 테스트, QA Verify Rebuild, Finalize 결과
- State Machine Validator, Mermaid 재생성 및 Drift Check 결과
- Backend 테스트·Migration Gate의 실행 가능 여부와 차단 원인
- AI 단위 테스트·pgvector 결과의 현재성 및 Backend 연동 한계
- Web 테스트·Lint·TypeScript·Production Build 결과와 Mock 경계
- Mobile 단위 테스트·APK Build 결과와 SDK Platform 차단 원인
- WBS 상태, 담당자, 차단 요소, 해제 조건 및 인계 목록의 정합성
- 기준 Commit과 발표 가능 범위의 고정

## 3. 이번 단계에서 완료로 보지 않는 범위

- Backend-AI 실제 HTTP·DB 수직 연동
- 상담·방문 Runtime 11개 Operation 구현
- 모든 Action 23개의 OpenAPI·Runtime·클라이언트 전체 분류 완료
- 실제 Backend를 사용하는 Web·Mobile 상담·방문 E2E
- 최종 발표용 중앙 실행 패키지와 전체 리허설 3회

위 항목은 3.1에서 숨기지 않고 Blocker 또는 후속 작업으로 등록하는 것이 완료 조건이다.

## 4. 완료 조건 점검표

| 완료 조건 | 결과 | 근거 |
|---|---|---|
| 기준 Commit과 작업 트리 상태가 기록됨 | 완료 | [현재 기준선](week4-current-baseline.md) |
| 영역별 PASS·FAIL·미검증 결과가 한 문서에 정리됨 | 완료 | [Main 회귀 결과](../testing/week4-main-regression-result.md) |
| 환경 부족과 코드 실패가 분리됨 | 완료 | [진입 Gate](../testing/week4-entry-gate.md) |
| WBS가 구현·Mock·계약 경계를 반영함 | 완료 | [WBS](md/WBS.md) |
| 회귀·차단 항목에 담당자와 해제 조건이 연결됨 | 완료 | [차단 요소 Register](week4-blocker-register.md) |
| Known Failure와 통합 인계가 작성됨 | 완료 | [Known Failures](../testing/week4-known-failures.md), [통합 인계](../handoffs/week4-integration-handoff.md) |
| 외부 GitHub Issue와 WBS 상태가 일치함 | 확인 대기 | 로컬 저장소만으로 외부 Issue 상태를 검증할 수 없음 |
| 발표 중앙 패키지·Fallback·리허설 3회가 확보됨 | 미완료 | `W4-BLK-009`, T-052 후속 작업 |

## 5. 3.1 판정

로컬 저장소에서 요구되는 기준선·WBS·Gate·Blocker·Known Failure·인계 문서는 모두 작성되었다. 따라서 **3.1의 저장소 산출물은 완료**로 판정한다.

다만 외부 GitHub Issue 정합성은 별도 확인이 필요하며, Backend·AI·Mobile 최신 Gate와 중앙 발표 패키지가 준비되지 않았으므로 프로젝트 통합 상태는 계속 **`INTEGRATION_BLOCKED / PRESENTATION_FREEZE_NOT_APPROVED`**이다.

## 6. 3.3 P0 범위 분류

| 분류 | 작업 | 범위 결정 |
|---|---|---|
| 발표 전 필수 | `T-022`, `T-023`, `T-040`, `T-045`, `T-052` | 구현된 Runtime·Web Mock·계약 증거만 사용하며 서로의 완료 상태로 혼동하지 않는다. |
| 발표 전 가능하면 포함 | `T-011`, `T-026`, `T-032`, `T-041` | 저장된 검색·AI 결과와 Mock UI만 허용하고 현재 팀 DB·전체 E2E 성공으로 표현하지 않는다. |
| 발표 후 8월 7일 착수 | `T-019` | `T-018` 구독·제품 Runtime과 Care Migration이 확인될 때 착수한다. |
| 5주차 이관 | 위 작업의 미완료 Runtime·소비자 연동·실 DB 검증 | 담당자·진입 조건·증거를 통합 인계 목록으로 관리한다. |

발표 흐름은 Demo 로그인, 대표 고객·구독·문의, 증상 또는 준비된 문의, 공식 검색·안전 결과, 상담사 상세, 상담 결과 또는 방문 필요 분기로 제한한다. 2026-08-05 이후 중간 발표 범위에는 신규 기능을 추가하지 않는다.

상세 선행 관계와 작업별 판정은 [P0 의존성 Map](week4-dependency-map.md), 담당자와 증거 책임은 [P0 담당자·완료 증거 Matrix](week4-owner-matrix.md)를 따른다.

## 7. 3.3 완료 조건 점검표

| 완료 조건 | 결과 | 근거 |
|---|---|---|
| 4주차 필수·선택·8월 7일 착수·5주차 이관 범위가 구분됨 | 완료 | 이 문서 6장, [의존성 Map](week4-dependency-map.md) |
| 10개 업무에 담당자·선행 산출물·실행 증거·목표일이 있음 | 완료 | [담당자·완료 증거 Matrix](week4-owner-matrix.md) |
| Mock·계약 전용·Runtime이 분리됨 | 완료 | [의존성 Map](week4-dependency-map.md), [WBS](md/WBS.md) |
| WBS에 2026-08-07 Exit 결정이 반영됨 | 완료 | [WBS](md/WBS.md) 5-1장 |
| 5주차 이관 항목에 담당자와 진입 조건이 기록됨 | 완료 | [통합 인계](../handoffs/week4-integration-handoff.md) 4장 |
| 외부 GitHub Issue에 관할 승인·의존성·목표일이 일치함 | 확인 대기 | 외부 Issue 링크 및 담당자 회신 필요 |

## 8. 3.3 판정

Scope·DoD, 의존성 Map, 담당자·증거 Matrix, WBS Exit 기준선과 5주차 이관 목록은 로컬 저장소에 작성됐다. 따라서 **3.3의 로컬 문서 산출물은 완료**다.

외부 GitHub Issue 대조와 담당자 회신은 아직 확인되지 않았으므로 최종 운영 판정은 **`LOCAL_READY / OWNER_AND_ISSUE_CONFIRMATION_PENDING`**으로 유지한다.

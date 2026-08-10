# 4주차 → 5주차 통합 인계

> 인계일: **2026-08-07 KST**
> 기준 Commit: `dad0e7a2c0e6c184ac8811bce6c6974bd7cb3fe0`
> 4주차 Exit: **CONDITIONAL_EXIT / WEEK5_BLOCKERS_OPEN**
> 5주차 진입: **CONDITIONAL_ENTRY / UNBLOCK_FIRST**

## 1. 인계 기준선

| 구분 | 인계 가능한 입력 | 제한 |
|---|---|---|
| 계약 | State Machine 1.0.0, Action Crosswalk, Code Registry, OpenAPI·Example | Contract Test 7/7은 기존 증거 승계, 현재 로컬 pytest 미재실행 |
| Data | 대표 제품·구독·문의·근거, 67/67·QA·Finalize 증거 | 8월 5일 이후 Data Source 변경 없음 |
| Backend | 문의 생성·취소·증상 제출 Slice, 권한·409·멱등 기반 Source | 현재 Test·Migration Gate와 상담·방문 Runtime 없음 |
| AI·RAG | 구조화·추가 질문·안전 규칙·내부 Timeout Source | 현재 AI Test·팀 DB Vector·Backend Event 저장 미재현 |
| Web | Test 113, Lint·TypeScript·Build 증거, Mock Repository 경계 | 상담·방문 실제 Remote Adapter 없음 |
| Mobile | 인증·문의의 과거 실단말 증거, DTO·UiState Source | 최신 Build·Test는 SDK Platform 차단 |
| 발표 | 실제 중간 발표 피드백 원문과 분류 결과 | 사전 리허설·승인 기록은 소급 작성하지 않음 |

## 2. 담당자별 5주차 첫 인계

| 담당자 | 첫 작업 | 받는 입력 | 다음 담당자에게 줄 출력 | 완료 증거 |
|---|---|---|---|---|
| 최지용 | Backend 환경 복구와 AI 최소 호출·저장 경로 | 계약 1.0.0, AI Mapping, 대표 Inquiry | Runtime Operation·DB·Event·추적 ID | pytest·Migration·수직 E2E |
| 이동윤 | AI Test·팀 DB Vector 재현과 Schema Mapping | 대표 Data, Code·State 계약 | 구조화·위험·근거·Fallback 출력 | AI Test, 검색 평가, Schema Test |
| 한예나 | 상담·방문 Mock·Remote 경계 유지 및 DTO 준비 | Action·OpenAPI, Backend Operation 상태 | Remote Adapter 연결 PR 또는 명시적 차단 | Web Test·Build, 409·오류 처리 Test |
| 양정현 | Mobile SDK Gate 복구와 확정 DTO 소비 준비 | Action·상태·오류 계약 | Core·Customer·Technician 소비 가능 상태 | Gradle Test·APK·UiState Test |
| 김은진 | Gate 증거·대표 Seed·평가 기준 통합 | 전 영역 Commit·명령·결과 | 같은 Commit QA·Issue·보고서 | Test 집계, Drift 0, 검수 기록 |
| 윤승혁 | 기준선 Commit·Issue 대조·범위 승인 | 3.3·3.6 문서, 담당자 회신 | WBS·Issue·Dependency 일치 판정 | Commit, Issue 링크, 의존성 예외 기록 |

## 3. 작업별 인계 순서

| 선행 출력 | 후속 소비자 | 전달 조건 |
|---|---|---|
| AI 요청·응답·Event Mapping | Backend 최소 Client·Mapper | Schema·오류·Fallback Test 통과 |
| Backend 최소 수직 E2E | `T-026`, `T-032`, Web·Mobile Adapter | HTTP·DB·State Event·`correlation_id` 확인 |
| 팀 DB Vector 평가 | `T-028A` | 제품·세대 Filter와 공식 문서·페이지 일치 |
| `T-027` 위험·사용 안내 | `T-028A`, `T-031` | 위험 조합·표현 변형·상담 우선 Test |
| `T-028A` 구조화 검색 | `T-028B` | 근거·페이지·관리 이력 Schema 고정 |
| `T-028B` `EvidenceCardDTO` | Web·Mobile | 내부 경로·원문·내부 ID 비노출 Test |
| `T-031` 근거 없음 Guard | `T-032` | 생성문 차단과 안전 Template·상담 상태 확인 |

## 4. 열린 차단 요소

| Blocker | 상태 | 5주차 처리 |
|---|---|---|
| `W4-BLK-005` Backend 환경 | `ENVIRONMENT_BLOCKED` | 8/10 첫 Gate |
| `W4-BLK-007` Mobile Build | `SDK_PLATFORM_BLOCKED` | 8/10 환경 복구 |
| `W4-BLK-010` Backend↔AI | `WEEK5_HANDOFF_READY` | Mapping 후 최소 수직 E2E |
| `W4-BLK-011` 상담·방문 Runtime | `WEEK5_HANDOFF_READY` | Operation 우선순위·목표일 확정 |
| `W4-BLK-012` AI·Vector 현재 Gate | `WEEK5_ENTRY_BLOCKED` | AI Test·팀 DB 평가 재실행 |
| `W4-BLK-014` Issue·담당자 확인 | `EXTERNAL_CONFIRMATION_PENDING` | 기준선 Commit 후 대조·회신 |

## 5. 인수 확인

각 담당자는 5주차 첫 작업 전에 다음을 회신한다.

1. 담당 Backlog와 목표일
2. 필요한 입력 파일·API·DB·Fixture
3. 실행 환경과 재현 명령
4. 완료 증거 경로
5. 관할 밖 변경의 Issue·PR 승인
6. 이번 주 제외 범위

회신이나 실행 증거가 없는 작업은 `진행 중` 이상으로 승격하지 않는다.

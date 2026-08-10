# 4주차 P0 담당자·완료 증거 Matrix

> 기준 Commit: `dad0e7a2c0e6c184ac8811bce6c6974bd7cb3fe0`  
> 기준일: **2026-08-07 KST**  
> 연계 문서: [4주차 P0 의존성 Map](week4-dependency-map.md)  
> 외부 Issue 상태: **LOCAL_MATRIX_READY / ISSUE_LINK_PENDING**

## 1. 운영 규칙

1. WBS의 주 담당자를 변경하지 않는다.
2. 선행 조건은 담당자 이름이 아니라 계약·API·DB·Test·로그 산출물로 기록한다.
3. 담당 영역 밖 파일 수정은 해당 주관자의 Issue·PR 승인을 받은 뒤 수행한다.
4. Mock·Fixture·과거 녹화는 실제 Runtime 완료 증거로 사용하지 않는다.
5. WBS 목표일이 지난 작업은 완료로 간주하지 않고 2026-08-07 Exit 결정 또는 5주차 재계획을 기록한다.

## 2. P0 담당자·증거 Matrix

| 작업 | 주 담당 | 협업·검수 | 4주차 분류 | 선행 산출물 | 완료 증거 | WBS 목표 | 2026-08-07 Exit 결정 |
|---|---|---|---|---|---|---|---|
| `T-011` Vector DB·검색 | 이동윤 | 김은진 | 발표 전 가능하면 포함 | 공식 Chunk·Metadata, 임베딩 설정, 접근 가능한 pgvector | Index 로그, 제품·증상 필터 검색 결과, 정답 문서·페이지 평가 | 2026-07-29 경과 | `DONE_WITH_LIMITATION`; 팀 DB 재검증을 5주차 진입 조건으로 이관 |
| `T-019` 케어 이력 | 최지용 | 김은진 | 발표 후 8월 7일 착수 | `T-018` 구독·제품 Runtime, Care Schema·Migration | Care API 요청·응답, DB 누적·조회, 권한 Test | 2026-08-06 경과 | 선행 Runtime 확인 후 착수; 미충족 시 5주차 이관 |
| `T-022` 문의 생성·누적 | 최지용 | 김은진 | 발표 전 필수 | Inquiry Schema·Migration, 구독·제품 Fixture, 문의 OpenAPI | 생성·누적 응답, 동일 Inquiry DB 저장, 오류·멱등 Test | 2026-07-29 경과 | 생성·증상 제출만 `RUNTIME_IMPLEMENTED`; 추가 답변·자가조치·AI 효과 이관 |
| `T-023` State Machine API | 최지용 | 김은진·윤승혁 | 발표 전 필수 | 계약 1.0.0, Action Crosswalk, `T-022` Runtime, Backend 실행 환경 | 권한·Guard·409·멱등·이력 Test, `correlation_id` 로그 | 2026-07-31 경과 | Action 2개 Runtime만 승인; 상담·방문·완료 Action은 계약 분류 유지 |
| `T-026` 추가 질문 | 이동윤 | 김은진·최지용 | 발표 전 가능하면 포함 | AI Schema, 구조화 기준, `T-025` 또는 의존성 예외 승인 | 누락 필드·추가 질문 JSON, 중복 방지 Test, 소비자 DTO Test | 2026-08-07 | AI 단독 결과 `DONE_WITH_LIMITATION`; Backend·Web·Mobile 소비 이관 |
| `T-032` Timeout·Retry·Fallback | 이동윤 | 김은진·최지용 | 발표 전 가능하면 포함 | Timeout 설정, 오류 Schema, Backend 호출 경계, `T-025` 또는 예외 승인 | Timeout·재시도 로그, 오류 응답, 상담 전환 Event·DB E2E | 2026-08-05 경과 | AI 내부 Timeout·1회 재시도만 인정; 전체 Fallback E2E 이관 |
| `T-040` 상담 결과 저장 | 한예나 | 최지용·윤승혁 | 발표 전 필수 | `T-023` 상담 Runtime, `T-039` 상세 조회, 상담 OpenAPI | HTTP 요청·응답, DB 저장, 전이·409·멱등 Test, Web 표시 | 2026-08-03 경과 | `MOCK_UI`; Runtime 미구현을 `W4-BLK-011`로 유지 |
| `T-041` 방문 일정 등록 | 한예나 | 최지용·윤승혁 | 발표 전 가능하면 포함 | `T-040` 방문 분기, 방문 Runtime, 합성 기사 Fixture | 일정 요청·응답, 희망일·확정일 DB 저장, 권한·409 Test | 2026-08-04 경과 | `MOCK_UI`; 방문 Runtime과 Remote Adapter를 5주차 이관 |
| `T-045` 공통 UI·상태 표시 | 한예나 | 양정현·윤승혁 | 발표 전 필수 | 역할·상태·Action·오류 계약, Router·공통 Component | 역할 Route, 상태 Badge, `allowed_actions`, 오류·Fallback Test | 2026-07-24 경과 | Web Gate 증거 유지; Mock·Runtime 상태 표시를 필수 조건으로 유지 |
| `T-052` 시연 준비 | 윤승혁 | 김은진·전 팀원 | 발표 전 필수 | 고정 ID·근거, 기능 상태표, 초기화·실행 명령, 영역별 증거 | 단계별 결과, Fallback, 추적 ID, 리허설 3회, QA 승인 | 2026-08-04 경과 | 중간 제한 시연과 최종 E2E 분리; 중앙 패키지는 `W4-BLK-009` 유지 |

## 3. 관할 승인 Matrix

| 변경 범위 | 주관 | 사전 승인·검토가 필요한 협업 | Issue·PR 기록 기준 |
|---|---|---|---|
| `backend/**`, `contracts/api/**`, `contracts/codes/**` | 최지용 | 윤승혁, 기능별 소비자 | API·Runtime·Migration·Test Commit과 실행 결과 |
| `ai/**`, `contracts/ai/**` | 이동윤 | 최지용·김은진 | Schema, 평가 결과, Backend Event 매핑·Fallback 증거 |
| `web/**` | 한예나 | 최지용·윤승혁 | Action·Operation ID, Mock/Remote 경계, Test·Build 결과 |
| `mobile/**` | 양정현 | 최지용·김은진·윤승혁 | DTO·상태·Action, Gradle Test·APK 결과 |
| `data/**`, `tests/**`, `.github/**` | 김은진 | 대상 영역 담당자·윤승혁 | Fixture·QA·CI 결과와 Raw 비보존 정책 확인 |
| `contracts/state-machine/**`, `scripts/contracts/**` | 윤승혁 | 최지용·김은진 | Breaking Change, 소비자 영향, Validator·Contract Test |
| `docs/**` | 공동 | 관련 주장·증거의 원 담당자 | Runtime·Mock·계약 분류와 기준 Commit |

다른 관할의 Source를 직접 수정하는 대신 담당자의 PR을 우선한다. 긴급 수정이 필요한 경우 `.github/ISSUE_TEMPLATE/task.yml`의 `dependencies`, `output_paths`, `excluded_scope`에 승인 범위를 남긴다.

## 4. 담당자별 3.3 회신 요청

| 담당자 | 확인·회신 항목 | 필요한 증거 | 상태 |
|---|---|---|---|
| 최지용 | `T-019`, `T-022`, `T-023` Runtime 범위와 5주차 우선순위 | Backend Gate, Migration, 구현 Action 목록, 상담·방문 이관 결정 | 회신 대기 |
| 이동윤 | `T-011`, `T-026`, `T-032`의 팀 DB·소비자 연동·Fallback 경계 | AI Test, pgvector 평가, Backend Event 매핑 계획 | 회신 대기 |
| 한예나 | `T-040`, `T-041`, `T-045`의 Mock·Remote 경계 | Web Test·Build, 기능 상태 표시, Remote Adapter 이관 조건 | 회신 대기 |
| 양정현 | `T-045` Mobile 공통 표현과 신규 Mobile 범위 | DTO·UiState Test, Gradle Build 또는 발표 제외 확인 | 회신 대기 |
| 김은진 | 모든 완료 주장과 실행 증거, Issue·WBS 정합성 | CI 결과, QA 확인표, 발표·이관 상태표 | 회신 대기 |
| 윤승혁 | 동결 범위·의존성 예외·5주차 이관 최종 기록 | Scope·Dependency·Owner Matrix, Blocker·WBS 갱신 | 작성 중 |

## 5. Issue 등록 기준

외부 GitHub Issue를 로컬에서 직접 확인할 수 없으므로 다음 값은 Issue에 대조 기록해야 한다.

| Issue 필드 | 기록할 내용 |
|---|---|
| 요구사항·WBS ID | Matrix의 `T-xxx`와 요구사항 ID |
| 담당자 | 본 문서의 주 담당 |
| 목표 완료일 | 기존 WBS 목표일과 2026-08-07 Exit 결정; 이관 시 5주차 날짜 |
| 선행 작업·의존성 | 담당자 이름이 아닌 API·계약·DB·Test 산출물 |
| 예상 결과물·완료 기준 | 본 문서의 완료 증거 |
| 결과물 경로 | 해당 주관 영역의 실제 경로 |
| 제외 범위 | Mock·미연동·후속 이관 범위 |
| 현재 상태 | 진행 중·검토 대기·연동 확인·다음 주 인계 중 실제 상태 |

## 6. 3.3 Matrix 판정

- 10개 P0 작업에 주 담당, 협업·검수, 선행 산출물, 완료 증거와 Exit 결정이 기록됐다.
- 기존 WBS 목표일이 지난 작업은 완료로 승격하지 않고 제한·차단·이관으로 분류했다.
- 로컬 Matrix 작성은 완료했으나 외부 GitHub Issue 링크와 담당자 회신은 아직 없다.
- 따라서 담당자·증거 Matrix는 **`LOCAL_READY / OWNER_AND_ISSUE_CONFIRMATION_PENDING`**이다.

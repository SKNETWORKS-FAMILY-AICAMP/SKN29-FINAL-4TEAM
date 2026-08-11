# Backend 팀 검토 및 인계 체크리스트

- 작성·유지 책임: Backend·Database·API 계약 담당
- 검토 역할: Data·QA, PM·State 계약, Web, Mobile, AI·RAG 담당
- 목적: 담당자별 우선순위·요청·반환 증거·금지사항을 한 곳에서 추적
- 현재 상태: T-017A/B 완료, T-017C 작성자 구현 착수 / T-022 Slice A 작성자 검증 완료

> 2026-08-11 현행화: 이 문서의 과거 `T-017A 검토 대기`, `T-017B 미착수`
> 문구는 당시 인계 이력이다. 현재 실행 기준은 `T-017A/B 완료`,
> `T-017C 착수 가능·독립 QA 전`이다.

이 문서는 역할별 요청·반환 증거와 완료 Gate를 추적하는 실행 체크리스트다.
T-005와 T-016은 후속 개발에서 재사용하는 구현·기술 검증 기준선이다.
회귀가 확인되지 않으면 새 구현을 추가하지 않지만, 현재 WBS 상태와
T-005 manifest에 남은 비작성자·PM 검토 및 공식 완료 판정은 계속
추적한다. 현재 구현 판정은
[T-005 데이터 설계 기준선](../../../database/t-005/README.md),
[API Runtime 지원표](../../../api/runtime_implementation_status.md),
[최지용 문서 인덱스](../README.md)를 우선한다.

팀 공용 기준은 PM 승인과 독립 검토를 거쳐 공용 기준선에 반영된 변경이다.
아직 반영되지 않은 기능 후보는 소비 가능한 Runtime으로 보지 않는다.
인계 단위에는 범위, 대상 파일, 환경, 명령·결과, 계약 차이와 검토 결정을
함께 포함한다.

## 1. 공통 인계 원칙

1. 각 담당자는 자기 주관 경로에서만 수정한다.
2. 계약 차이는 상대 영역 파일을 직접 고치지 않고
   `경로·필드·현재값·기대값·재현 절차`로 반환한다.
3. 테스트 개수만 전달하지 않고 기준선 식별자, 실행 환경, 명령,
   Exit code, 실행 시각을 함께 남긴다.
4. PM의 팀 기준선 반영 완료 통지를 공용 소비 시작 조건으로 사용한다.
5. 기술 구현 완료와 기능 책임자 검토·PM 공식 완료 판정을 구분한다.
6. 실제 개인정보, 운영 Dump, `.env`, Token, Secret, 개인 PC 절대경로를
   Git 추적 파일이나 인계 문서에 넣지 않는다.

## 2. Backend·Database 담당의 현재 협업·검토 요청 우선순위

### 2.1 기준선과 완료 경계

| 항목 | 현재 값 | 해석 |
|---|---|---|
| 팀 공용 기준 | PM 승인·독립 검토가 완료된 팀 기준선 | 미승인 기능 후보를 공용 Runtime으로 사용하지 않음 |
| Backend 전달 단위 | 계약·Runtime·테스트·문서를 묶은 검토 패킷 | 대상 파일·검증 결과·계약 차이·검토 결정을 함께 전달 |
| 후보 DB | `waterbridge.public`, 물리 32·Active 13·Target-only 19 | PM 승인 전 팀 공용 기준으로 확대하지 않음 |
| 실행 검증 기준 | 검증 명령·환경·Exit code가 함께 기록된 변경 묶음 | 과거 테스트 수치를 현재 코드의 자동 완료 증거로 사용하지 않음 |
| T-005·T-016 | 구현·기술 검증 기준선 확보, 공식 WBS·비작성자 검토 대기 (`IMPLEMENTATION_BASELINE_REVIEW_PENDING`) | 회귀가 없으면 새 구현은 추가하지 않되 공식 검토·WBS 상태 갱신은 남은 Gate로 관리 |
| T-017 | Auth·RBAC 완료, 계정관리 후속 구현 분리 | T-017A/B 완료, T-017C는 별도 변경 단위 |
| T-017A/B | 설계·Django Admin·독립 QA 완료 | T-017C 완료로 확대 금지 |
| T-017C | 착수 가능·작성자 구현 대상 | Token 세대·Lifecycle·감사·동시성·rollback 검증 필요 |
| T-022 Submit | 증상 제출 DB 전이 준비 (`SUBMIT_SYMPTOM_DB_TRANSITION_READY`) | Slice A 계약·Runtime·작성자 검증 완료. 독립 검토·팀 기준선 반영과 Slice B AI 효과는 별도 |
| T-018 | 계약·테스트 제안만 존재 (`SAFE_CONTRACT_TEST_PROPOSAL_ONLY`) | 최소 GET 제안만 완료, 계약·Runtime·최근 관리일 규칙 미확정 |

### 2.2 지금 요청해야 할 항목

| 우선 | 검토·협업 요청 | 요청 역할 | Backend·Database 담당이 제공할 입력 | 반환받을 증거 | 현재 상태 |
|---:|---|---|---|---|---|
| P0 | T-022 Slice A 구현 증거 리뷰·Slice B 경계 | PM·State 계약, Data·QA, AI·RAG | [T-022 설계서](../API/Django_REST_API_문의_증상제출_구현_검증_인계서.md), OpenAPI·Runtime Diff, 집중·전체 회귀 결과 | Slice A 계약·DB 불변식·동시성 재현, 팀 기준선 반영 결정, Slice B AI dispatch 경계 | 작성자 구현 완료, 독립 검토 대기 (`OWNER_IMPLEMENTATION_READY_REVIEW_PENDING`) |
| P1 | T-017C 작성자 구현 후 독립 QA | Data·QA, PM·State 계약 | [계정관리 구현·검증 가이드](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md), Migration·표적·PostgreSQL·rollback 결과 | Token 세대·Lifecycle·감사·마지막 관리자 보호 독립 재현 | 작성자 구현 대상 (`START_ALLOWED_NOT_IMPLEMENTED`) |
| P2 | T-018 최소 GET 계약·테스트 검토 | Data·QA, PM·State 계약 | [T-018 제안서](../API/Django_REST_API_구독_제품조회_계약_제안서.md) | 본인 범위·MVP 필터·최근 관리일 집계·공개 필드·부분 완료 결정 | 제안 게시 후 검토 대기 (`PROPOSAL_PUBLISHED_REVIEW_PENDING`) |
| P3 | Web·Mobile 소비 준비 | Web, Mobile | 확정 OpenAPI와 팀 기준선의 Runtime 상태 | T-045 공통 기반 증거, 이후 UUID·Auth·오류·DTO·실제 API Smoke | 공통 기반 우선 (`COMMON_FOUNDATION_FIRST`) |
| P4 | AI Runtime·Evidence 소비 | AI·RAG | Slice A 기준선 반영 상태와 별도로 확정할 T-022 Slice B 계약 | Schema Parity·Timeout·재처리·Evidence E2E | Slice B 계약 대기 (`SLICE_B_CONTRACT_PENDING`) |

T-022, T-017A, T-018 검토 요청은 각 주요 문서와 이 체크리스트의 반환
형식을 준비한 뒤 동시에 보낼 수 있다.
T-022 Slice A는 `계약 → 계약 검증 → Runtime → 집중 검증 → 전체 회귀`까지
수행됐다. 이제 같은 범위를 독립 검토자가 재현하고 PM이 팀 기준선 반영
여부를 판단한다. Backend·Database 담당은 Slice B나 T-023을 같은 변경
묶음에 추가하지 않는다.

### 2.3 Backend·Database 담당 발송·회수 체크리스트

- [x] T-017A·T-022 역할별 결정 항목과 반환 형식 작성
- [x] T-018 최소 GET 요청·응답·권한·오류·테스트 Matrix 작성
- [x] 이 체크리스트에 현재 담당 역할·선행 Gate·완료 경계 반영
- [x] T-022 Slice A OpenAPI·Runtime 구현과 작성자 집중·전체 회귀 완료
- [x] T-017A·T-022 주요 문서·T-018 제안서·체크리스트의 대상 파일과 범위 확인
- [ ] 검토 역할에 대상 문서·응답 기한·반환 형식 전달
- [ ] `APPROVE / HOLD / CHANGE_REQUEST` 검토 결과를 역할별로 기록
- [ ] 승인된 항목 하나만 다음 구현 Wave로 선택
- [ ] 구현 뒤 같은 변경 묶음에서 PostgreSQL·권한·계약·전체 회귀 검증

패킷 전달 완료는 검토 완료나 팀 기준선 반영 완료를 뜻하지 않는다.
독립 검토와 PM 승인 전에는 팀 공용 Runtime 기준으로 확대하지 않는다.

### 2.4 담당자별 현재 요청 요약

| 역할 | P0 | P1 | P2 이후 | 반환해야 할 핵심 증거 |
|---|---|---|---|---|
| Data·QA | T-022 DB 불변식·Replay·rollback 검토 | T-017A Migration·감사 QA | T-018 조회·최근 관리일, 합성 데이터 책임자 검토 | QA 결정·계약/Schema 차이·변경 요청 |
| PM·State 계약 | T-022 Path·State·ADHOC·다음 Action 결정 | T-017A 계정 정책·B/C 순서 | T-018 공개 계약, 팀 기준선 반영 Gate | 승인/보류/변경 요청·결정 근거·반영 안내 |
| Web | T-045 Web 공통 Auth·API Client 완료 증거 | T-038 문의 목록 소비 | T-039~T-041, 통합 Smoke | Test·Lint·Build·실제 API·DTO 차이 |
| Mobile | T-045 Mobile 공통 계약·역할 라우팅 | T-033~T-037 고객 화면 | T-042~T-043 기사 화면·통합 Smoke | Unit·Lint·Build·Emulator·DTO 차이 |
| AI·RAG | T-022 Slice B Schema·dispatch·Timeout 경계 | T-025·T-032 Orchestrator·실패 처리 | T-026~T-031 Evidence·안전성·역할별 결과 | 계약 Parity·재처리 결정·통합 E2E 결과 |

이 표와 3~7장의 P0~P3은 **각 담당자 내부 큐**의 우선순위다. 팀 전체
우선순위는 2.2의 `P0 T-022 → P1 T-017A → P2 T-018`을 따른다.

### 2.5 WBS 기준 Backend·Database 공식 작업일정

날짜·담당자·선행 작업은 [WBS v2.0](../../../planning/md/WBS.md)을
그대로 옮겼다. `공식 기간 경과`는 실패나 완료를 뜻하지 않고, 2026-08-01
기준으로 WBS 재계획이 필요하다는 의미다. 이 체크리스트에서 기술 증거가
확인됐더라도 WBS 상태는 PM이 갱신하기 전까지 원문 값을 유지한다.

- 프로젝트 공식 기간: 2026-07-17 ~ 2026-09-03
- P0 실작업 완료일: 2026-09-02
- 최종 발표: 2026-09-03

| WBS | 시작일 | 종료일 | WBS 주담당 | 협업·검수자 | 선행 Task | WBS 상태 | 현재 일정 해석 |
|---|---|---|---|---|---|---|---|
| `T-017` 사용자·권한 | 2026-07-24 | 2026-07-27 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-005, T-016 | 미착수 | 공식 기간 경과·현재 Auth 증거와 공식 상태 분리 |
| `T-022` 문의·증상 제출 | 2026-07-28 | 2026-07-29 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-005, T-016, T-017 | Slice A 작성자 구현 완료 | 독립 검토·팀 기준선 반영 대기. 입력 누적·AI Slice B가 남아 T-022 전체 완료는 아님 |
| `T-017A` 계정 관리 설계 | 2026-07-30 | 2026-07-30 | 최지용<br>백엔드·데이터베이스 | 윤승혁·김은진 | T-005, T-017 | 완료 | PM 설계 완료 결정 반영 |
| `T-023` State Machine API | 2026-07-30 | 2026-07-31 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-002, T-005, T-016, T-022 | 미착수 | T-022 Slice A 독립 리뷰·팀 기준선 반영 전 추가 Action 확대 금지 |
| `T-018` 제품·구독 관리 | 2026-07-31 | 2026-08-03 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-005, T-016, T-017 | 미착수 | 최소 GET 제안은 전체 T-018 완료가 아님 |
| `T-017B` Django Admin | 2026-08-03 | 2026-08-03 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-017A | 완료 | Runtime·Migration·독립 QA 42건과 보호 경계 PASS |
| `T-017C` Lifecycle·Audit | 2026-08-04 | 2026-08-05 | 최지용<br>백엔드·데이터베이스 | 김은진·윤승혁 | T-017A, T-017B | 착수 | T-017A/B 완료, 작성자 구현·검증 후 독립 QA 필요 |
| `T-019` 케어 관리 | 2026-08-05 | 2026-08-06 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-018 | 미착수 | T-018 저장·조회 계약 완료 뒤 착수 |
| `T-020` 다음 케어 예정일 | 2026-08-10 | 2026-08-10 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-009, T-019 | 미착수 | 공식 주기·최근 케어 이력과 근거 부재 정책 검증 |
| `T-021` 사전 문진 | 2026-08-11 | 2026-08-12 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-005, T-016, T-020 | 미착수 | Inquiry 없는 사전 문진과 후속 Inquiry 연결 검증 |
| `T-024` 추적성·로그 | 2026-08-13 | 2026-08-14 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-016, T-023 | 미착수 | AI·RAG·상태·오류 이력 재현 가능성 검증 |
| `T-028B` EvidenceCardDTO 조립 | 2026-08-13 | 2026-08-14 | 최지용<br>백엔드·데이터베이스 | 이동윤·김은진 | T-005, T-011, T-028A | 미착수 | 공식 근거만 노출하고 내부 경로·원문 전체 비노출 |
| `T-044` 방문 결과·케어 연계 | 2026-08-18 | 2026-08-18 | 최지용<br>백엔드·데이터베이스 | 양정현·김은진 | T-019, T-043 | 미착수 | 중복 없이 케어 이력·다음 일정 갱신 |
| `T-055` 사후 상태 확인 | 2026-08-19 | 2026-08-19 | 최지용<br>백엔드·데이터베이스 | 양정현·윤승혁 | T-023, T-037, T-044 | 미착수 | COMPLETION_PENDING·FINALIZE_INQUIRY·REOPENED 정책 검증 |
| `T-046` 전 영역 통합 | 2026-08-21 | 2026-08-24 | 최지용<br>백엔드·데이터베이스 | 양정현·한예나·윤승혁·이동윤·김은진 | T-025, T-033, T-038, T-042, T-044 | 미착수 | 각 영역 기능·소비 증거가 모두 준비된 뒤 수행 |
| `T-047` Backend 종합 테스트 | 2026-08-25 | 2026-08-26 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-016~T-024, T-044 | 미착수 | 정상·예외·권한·상태·멱등·추적 전체 검증 |
| `T-047A` 계정 보안 테스트 | 2026-08-26 | 2026-08-27 | 최지용<br>백엔드·데이터베이스 | 김은진 | T-017B, T-017C, T-047 | 미착수 | Admin·Token 폐기·감사·권한 상승 회귀 |

WBS상 T-022·T-023은 공식 기간이 지났고 T-018과 T-017B는 8월 3일에
겹친다. Backend·Database 담당은 두 Runtime을 동시에 진행하지 않는다. T-022 Slice A는
작성자 구현·검증까지 끝났으므로 현재는 독립 리뷰·병합 Gate만 진행한다.
T-023·T-017A·T-018의 Runtime은 별도 우선순위가 확정될 때까지 이 변경에
섞지 않는다.

연계 작업에는 공식 기간보다 선행 Task 완료일이 늦은 WBS 충돌도 있다.
아래 날짜를 임의로 바꾸지는 않되, PM이 순서를 다시 확정하기 전에는
해당 담당자가 구현 완료로 처리하지 않는다.

| 충돌 작업 | WBS 공식 기간 | 충돌하는 선행 조건 | 처리 원칙 |
|---|---|---|---|
| `T-025` AI Orchestrator | 2026-07-30 ~ 2026-07-31 | 선행 T-023도 2026-07-30 ~ 2026-07-31 | T-023 PASS 후 새 기간 확정 |
| `T-038` Web 상담사 화면 | 2026-07-27 ~ 2026-07-28 | T-023은 2026-07-30 ~ 2026-07-31 | T-023 Runtime·계약 승인 뒤 새 기간 확정 |
| `T-039` Web 상담 상세 | 2026-07-29 ~ 2026-07-30 | 선행 T-030A는 2026-08-18 | T-030A와 T-038 완료 뒤 새 기간 확정 |
| `T-042` 기사 Mobile 화면 | 2026-08-07 ~ 2026-08-10 | T-030B는 2026-08-19 | T-030B 또는 대체 승인 입력이 준비된 뒤 새 기간 확정 |
| `T-043 → T-044 → T-055 → T-046` 연쇄 | 2026-08-14 ~ 2026-08-24 | T-042 지연 시 후속 방문·케어·사후 상태·통합도 순차 지연 | T-042 재계획과 함께 후속 작업을 묶어서 재계획 |
| `T-028B` Evidence 조립 | 2026-08-13 ~ 2026-08-14 | 선행 T-028A 종료일과 시작일이 2026-08-13으로 중첩 | 당일 인계 허용 여부와 완료 시각을 PM이 확인 |
| `T-047A` 계정 보안 테스트 | 2026-08-26 ~ 2026-08-27 | 선행 T-047 종료일과 시작일이 2026-08-26으로 중첩 | T-047 PASS 확인 후 착수하도록 시각 또는 날짜 재확정 |
| `T-050` 화면·상태 검증 | 2026-08-25 ~ 2026-08-26 | 선행 T-033~T-043 중 T-042·T-043이 재계획 대상 | 소비 화면 완료 증거 회수 뒤 기간 재확인 |
| `T-048` 종합 결과 보고 | 2026-08-25 ~ 2026-08-26 | T-047A는 2026-08-27 종료, T-049·T-051은 2026-08-27 ~ 2026-08-28 | 모든 선행 증거 회수 뒤 보고서 완료일 재확정 |
| `T-052` 시연 준비 | 2026-08-04 | 선행 T-046은 2026-08-21 ~ 2026-08-24 | 중간 시연 최소 Slice와 최종 시연 준비를 분리해 PM 재계획 |

### 2.6 협업·검토 요청일과 반환 시점

WBS에는 설계 검토자의 별도 작업일이 없다. 아래 `요청·반환 시점`은
WBS 선행관계를 지키기 위한 착수 조건이다. 검토 작업 자체의 시작일과
종료일은 WBS에 없으므로 PM이 정하기 전까지 미정이며, 과거 WBS 날짜를
새 검토 마감일로 해석하지 않는다.

`T-005`와 `T-016`은 구현·기술 검증 기준선으로 재사용하되 공식 WBS 완료와
비작성자 검토는 아직 닫지 않는다. 회귀가 없으면 새 구현 대상으로 다시
열지 않지만, 완료 Evidence·PM 판정·WBS 상태 갱신은 별도 Gate로 남긴다.

| 요청 항목 | 연결 WBS | WBS 시작일 | WBS 종료일 | 일정 성격 | 실제 착수 조건 | 검토 일정 | 요청 대상 |
|---|---|---|---|---|---|---|---|
| T-022 Slice A 구현 증거 리뷰 | T-022 | 2026-07-28 | 2026-07-29 | 공식 기간 경과·작성자 구현 완료 | OpenAPI·Runtime Diff와 PostgreSQL·전체 회귀 결과 게시 | 미정 — 결정권자: PM; 확정 조건: Slice A 독립 검토 완료 | PM·State 계약, Data·QA |
| T-022 Slice B AI 경계 | T-025 연계 | 2026-07-30 | 2026-07-31 | 공식 기간 경과·T-023과 중첩 | 예비 검토는 T-022 주요 문서 게시 후, 최종 승인은 Slice A 확정 후 | 미정 — 결정권자: PM; 확정 조건: Slice A 팀 기준선 확정 | AI·RAG |
| T-017A 정책·Migration 리뷰 | T-017A | 2026-07-30 | 2026-07-30 | 공식 기간 경과 | T-017A 주요 문서·결정 기록표 준비 | 미정 — 결정권자: PM; 확정 조건: T-017B 착수 전 정책·Migration 승인 | PM·State 계약, Data·QA |
| T-018 최소 GET 리뷰 | T-018 | 2026-07-31 | 2026-08-03 | 공식 기간 내 | T-018 제안서 준비 | 미정 — 결정권자: PM; 확정 조건: T-018 Runtime 착수 전 계약 승인 | Data·QA, PM·State 계약 |
| Web 문의·상태 소비 | T-038 | 2026-07-27 | 2026-07-28 | 선행 T-023보다 빠른 충돌 일정 | T-023 Runtime 팀 기준선 반영 | 미정 — 결정권자: PM; 확정 조건: T-023 Runtime 팀 기준선 확정 | Web, PM·State 계약, Backend·Database |
| Mobile 고객 소비 | T-033 | 2026-08-11 | 2026-08-12 | 공식 예정 | T-018·T-020·T-045 완료 | WBS 공식 기간 사용 | Mobile, PM·State 계약, Backend·Database |
| Mobile 기사·AI 근거 소비 | T-042 | 2026-08-07 | 2026-08-10 | 선행 T-030B보다 빠른 충돌 일정 | T-030B·T-041·T-045 완료 | 미정 — 결정권자: PM; 확정 조건: 세 선행 Task 완료 | Mobile, AI·RAG, Backend·Database |
| AI Runtime·Evidence 소비 | T-025·T-028B | 2026-07-30 | 2026-08-14 | 일부 경과·T-028A와 중첩 | T-023·T-028A 완료와 계약 확정 | 미정 — 결정권자: PM; 확정 조건: 선행 Runtime·계약 완료 | AI·RAG, Data·QA, Backend·Database |

### 2.7 협업자의 상세 작업순서

순번은 WBS 번호가 아니라 선행 작업을 지키기 위한 실행 순서다. 공식
기간이 경과했거나 선행일과 충돌하는 작업은 날짜를 임의 변경하지 않고
결정권자와 확정 조건을 함께 기록한다.

#### 2.7.1 현재 검토·병합 순서 — WBS 별도 기간 없음

| 순서 | 시작일 | 종료일 | 담당자 | 작업 | 완료·반환 조건 |
|---:|---|---|---|---|---|
| P0-A | 미정 — 결정권자: PM; 확정 조건: Slice A 증거 준비 | 미정 — 결정권자: PM; 확정 조건: 독립 검토 완료 | PM·State 계약, Data·QA | T-022 Slice A State·OpenAPI·DB 불변식과 작성자 증거 독립 검토 | Slice A 팀 기준선 반영과 T-023 착수 결정 |
| P0-B | 미정 — 결정권자: PM; 확정 조건: T-022 주요 문서 준비 | 미정 — 결정권자: PM; 확정 조건: P0-A 승인 | AI·RAG | T-022 Slice B AI Schema·dispatch·Timeout·재처리 경계 예비 검토 | P0-A 승인 뒤 최종 AI 계약 결정 |
| P0-C | 2026-08-01 | 2026-08-01 | Backend·Database | 승인된 T-022 Slice A를 계약→검증→Runtime→검증 순서로 구현 | 작성자 구현·회귀 완료, 독립 검토·팀 기준선 반영 대기 |
| P1-A | 미정 — 결정권자: PM; 확정 조건: T-017A 주요 문서 준비 | 미정 — 결정권자: PM; 확정 조건: 정책·Migration 승인 | PM·State 계약, Data·QA | T-017A 정책·Migration·감사 QA 검토 | T-017B/C 착수 결정 |
| P1-B | 미정 — 결정권자: PM; 확정 조건: P1-A 승인 | 미정 — 결정권자: PM; 확정 조건: 단계별 회귀 PASS | Backend·Database | 승인된 T-017A를 구현하고 T-017B→T-017C 순차 수행 | 각 단계 회귀 PASS·팀 기준선 반영 |
| P2-A | 미정 — 결정권자: PM; 확정 조건: 제안서 준비 | 미정 — 결정권자: PM; 확정 조건: 공개 계약 승인 | Data·QA, PM·State 계약 | T-018 본인 범위·공개 필드·최근 관리일 검토 | T-018 Runtime 착수 결정 |
| P2-B | 미정 — 결정권자: PM; 확정 조건: P2-A 승인 | 미정 — 결정권자: PM; 확정 조건: T-018 회귀 PASS | Backend·Database | 승인된 T-018 최소 GET Runtime 구현 | T-018 팀 기준선 반영 뒤 T-019/T-020 착수 |

P0·P1·P2의 문서 검토는 병렬로 요청할 수 있다. 구현은 `P0 → P1 → P2`
순서로 한 트랙씩 수행하고, 각 트랙의 검증과 팀 기준선 반영이 끝난 뒤 다음
트랙으로 이동한다. PM이 순서를 바꾸는 경우에는 변경 이유와 새 착수일을
검토 결과에 남긴다. T-022 Slice B 예비 검토는 병렬로 가능하지만 최종 승인과
Runtime 착수는 Slice A 확정 뒤에 한다.

#### 2.7.2 Backend·소비 영역 WBS 의존성 목록

아래 순번은 WBS 의존성 추적용이며 현재 실행 우선순위가 아니다. 실제
검토·구현 순서는 2.2와 2.7.1을 따른다.

| 순서 | WBS | 시작일 | 종료일 | 주담당·협업 | 선행·착수 조건 | 협업 작업과 반환 | 일정 판정 |
|---:|---|---|---|---|---|---|---|
| 3 | T-017 | 2026-07-24 | 2026-07-27 | 최지용 / 김은진 | T-005·T-016 | 역할별 Auth·조회 범위 검증 | 경과·공식 상태 재판정 |
| 4A | T-017A | 2026-07-30 | 2026-07-30 | 최지용 / 윤승혁·김은진 | T-005·T-017, P1-A | 정책·Migration·감사 설계 확정 | P1로 재계획·미정 — 결정권자: PM; 확정 조건: P1-A 승인 |
| 4B | T-017B | 2026-08-03 | 2026-08-03 | 최지용 / 김은진 | T-017A 승인 | Admin 접근·CRUD·권한 검증 | 선행 승인 전 착수 금지 |
| 4C | T-017C | 2026-08-04 | 2026-08-05 | 최지용 / 김은진·윤승혁 | T-017A·T-017B | 비활성·Token 폐기·감사 회귀 | T-017B PASS 후 착수 |
| 5A | T-022 | 2026-07-28 | 2026-07-29 | 최지용 / 김은진 | T-005·T-016·T-017 | Active 13·원문 불변·409·Replay·동시성 독립 검토 | Slice A 작성자 완료·리뷰/병합 대기 |
| 5B | T-023 | 2026-07-30 | 2026-07-31 | 최지용 / 김은진 | T-002·T-005·T-016·T-022 | State·권한·버전·멱등·추적 검증 | T-022 PASS 뒤 재계획 |
| 5C | T-024 | 2026-08-13 | 2026-08-14 | 최지용 / 김은진 | T-016·T-023 | AI·검색·상태·오류 로그 재현 | 공식 예정·T-023 필요 |
| 6A | T-018 | 2026-07-31 | 2026-08-03 | 최지용 / 김은진 | T-005·T-016·T-017, P2-A | 제품·구독·최근 관리일·비노출 검증 | P2로 재계획·P0/P1 뒤 착수 |
| 6B | T-019 | 2026-08-05 | 2026-08-06 | 최지용 / 김은진 | T-018 | 케어 이력·구독·제품 연결 검증 | T-018 PASS 후 착수 |
| 6C | T-020 | 2026-08-10 | 2026-08-10 | 최지용 / 김은진 | T-009·T-019 | 관리 주기·최근 이력·근거 부재 검증 | 공식 예정 |
| 6D | T-021 | 2026-08-11 | 2026-08-12 | 최지용 / 김은진 | T-005·T-016·T-020 | Inquiry 없는 문진·후속 연결 검증 | 공식 예정 |
| 7A | T-025 | 2026-07-30 | 2026-07-31 | 이동윤 / 김은진·최지용 | T-006·T-015·T-023, P0-B | Orchestrator·Slice B Schema·Timeout 검증 | 미정 — 결정권자: PM; 확정 조건: T-023 팀 기준선 확정 |
| 7B | T-028A | 2026-08-12 | 2026-08-13 | 이동윤 / 김은진·최지용 | T-011·T-019·T-026 | 공식 근거 출력 Schema 검증 | 공식 예정 |
| 7C | T-028B | 2026-08-13 | 2026-08-14 | 최지용 / 이동윤·김은진 | T-005·T-011·T-028A | EvidenceCardDTO·Lineage·비노출 검증 | 8월 13일 당일 인계 여부 PM 확인 |
| 7D | T-032 | 2026-08-04 | 2026-08-05 | 이동윤 / 김은진·최지용 | T-016·T-025 | AI·검색 Timeout·재시도·Fallback 검증 | T-025 재계획 영향 |
| 8A | T-045 | 2026-07-23 | 2026-07-24 | 한예나 / 양정현·윤승혁 | T-003·T-004 | 공통 Auth·API Client·환경 계약 증거 반환 | 경과·소비 작업 전 완료 확인 |
| 8B | T-033 | 2026-08-11 | 2026-08-12 | 양정현 / 최지용·윤승혁 | T-018·T-020·T-045 | 고객 제품·구독·케어 소비 검증 | 공식 예정 |
| 8C | T-037 | 2026-08-12 | 2026-08-13 | 양정현 / 최지용·윤승혁 | T-023·T-045 | 후속 상태·재문의 소비 검증 | 공식 예정 |
| 9A | T-038 | 2026-07-27 | 2026-07-28 | 한예나 / 최지용·윤승혁 | T-023·T-045 | 문의 목록·상태 소비 검증 | 미정 — 결정권자: PM; 확정 조건: T-023·T-045 완료 |
| 9B | T-030A | 2026-08-18 | 2026-08-18 | 이동윤 / 김은진·윤승혁 | T-023·T-029 | 상담 AI 요약 초안 계약 반환 | T-039의 선행인데 후행 날짜 |
| 9C | T-039 | 2026-07-29 | 2026-07-30 | 한예나 / 최지용·윤승혁 | T-030A·T-038 | 상담 상세·AI 초안 소비 검증 | 미정 — 결정권자: PM; 확정 조건: T-030A·T-038 완료 |
| 9D | T-040 | 2026-07-31 | 2026-08-03 | 한예나 / 최지용·윤승혁 | T-023·T-039 | 상담 결과·상태 전이 검증 | T-039 재계획 영향 |
| 9E | T-041 | 2026-08-04 | 2026-08-04 | 한예나 / 최지용·윤승혁 | T-023·T-040 | 상담 보류·재요청 흐름 검증 | T-040 재계획 영향 |
| 10A | T-030B | 2026-08-19 | 2026-08-19 | 이동윤 / 김은진·윤승혁 | T-019·T-030A | 기사 사전 점검 AI 결과 계약 반환 | T-042의 선행인데 후행 날짜 |
| 10B | T-042 | 2026-08-07 | 2026-08-10 | 양정현 / 최지용·이동윤 | T-030B·T-041·T-045 | 기사 리포트·근거 소비 검증 | 미정 — 결정권자: PM; 확정 조건: T-030B·T-041·T-045 완료 |
| 10C | T-043 | 2026-08-14 | 2026-08-17 | 양정현 / 최지용·이동윤 | T-023·T-042 | 방문 결과·필수값·상태 전이 검증 | T-042 재계획 영향 |
| 10D | T-044 | 2026-08-18 | 2026-08-18 | 최지용 / 양정현·김은진 | T-019·T-043 | 방문 결과의 케어·일정 반영 검증 | T-043 재계획 영향 |
| 10E | T-055 | 2026-08-19 | 2026-08-19 | 최지용 / 양정현·윤승혁 | T-023·T-037·T-044 | 완료 대기·최종 완료·재문의 E2E | T-044 재계획 영향 |

#### 2.7.3 통합·검증·배포 WBS 실행 순서

| 순서 | WBS | 시작일 | 종료일 | 주담당·협업 | 공식 선행 Task | 수행·반환 | 일정 판정 |
|---:|---|---|---|---|---|---|---|
| 11 | T-046 | 2026-08-21 | 2026-08-24 | 최지용 / 전 영역 담당 | T-025·T-033·T-038·T-042·T-044 | 팀 기준선에서 고객→상담사→기사 E2E | 앞선 충돌의 도미노 영향 확인 |
| 12 | T-047 | 2026-08-25 | 2026-08-26 | 최지용 / 김은진 | T-016~T-024·T-044 | Backend 정상·예외·권한·상태·멱등 회귀 | T-046 이후 수행 |
| 13 | T-047A | 2026-08-26 | 2026-08-27 | 최지용 / 김은진 | T-017B·T-017C·T-047 | Admin·Token·감사·권한 보안 회귀 | T-047 종료일과 중첩·PM 확인 |
| 14A | T-049 | 2026-08-27 | 2026-08-28 | 이동윤 / 김은진 | T-015·T-027·T-031 | AI·RAG 안전성 결과 반환 | 공식 예정 |
| 14B | T-050 | 2026-08-25 | 2026-08-26 | 김은진 / 양정현·한예나·최지용·이동윤 | T-033~T-043 | 화면·권한·상태·버튼 일치 검증 | T-042/T-043 재계획 영향 |
| 14C | T-051 | 2026-08-27 | 2026-08-28 | 김은진 / 양정현·한예나·최지용·이동윤 | T-024·T-032·T-046 | 성능·Timeout·Replay·Fallback 검증 | 공식 예정 |
| 15 | T-048 | 2026-08-25 | 2026-08-26 | 김은진 / 전 팀원 | T-047·T-047A·T-049~T-051 | 모든 영역 결과를 취합해 종합 보고 | 미정 — 결정권자: PM; 확정 조건: 모든 선행 증거 회수 |
| 16 | T-052 | 2026-08-04 | 2026-08-04 | 윤승혁 / 김은진·전 팀원 | T-014·T-046 | 시연 Seed·초기화·대본 검증 | T-046보다 빠름·중간/최종 시연 분리 필요 |
| 17 | T-053 | 2026-08-31 | 2026-09-01 | 김은진 / 윤승혁·전 개발 담당 | T-046·T-047·T-047A·T-051 | 배포·환경·Smoke·README·시연 자료 | 공식 예정 |
| 18 | T-054 | 2026-09-02 | 2026-09-02 | 윤승혁 / 전 팀원 | T-047·T-047A·T-048~T-053 | P0 추적·대표 E2E·제출물·리허설 | 2026-09-03 발표 전 최종 Gate |

협업자는 앞 단계가 끝나지 않았으면 자기 화면·AI·Data 파일에서 Backend
계약을 추측해 우회하지 않는다. 차이는 상대 파일 수정이 아니라 이 문서의
반환 형식으로 Backend·Database 담당에게 전달한다.

## 3. Data·QA 독립 검토

> **3~7장 일정 표기 원칙**
> `WBS 시작일·종료일`은 WBS 원문의 연계 작업기간이며 협업 검토의 새
> 마감일이 아니다. `TBD`는 일정 누락이 아니라 PM 역할의 재계획이
> 필요하다는 뜻이다. 실제 착수는 각 표의 `착수 조건`을 모두 만족한
> 뒤에만 가능하다.

### 3.1 편집 경계

| 범위 | 책임 |
|---|---|
| `data/**` | Data·QA 담당 주관 |
| `scripts/data/**` | Data·QA 담당 주관 |
| `backend/**`, `backend/tests/**` | Backend·Database 담당 주관 |
| `contracts/codes/**` | Backend·Database 담당 주관, Data 소비자 검토 |
| `docs/**` | 공동 편집, 실제 증거와 미완료 경계 기록 |

Backend Source Hash를 맞추기 위해 Backend 구현을 임의 변경하지 않는다.
변경이 필요하면 경로·필드·기대값을 Backend·Database 담당에게 반환한다.

### 3.2 요청 작업

#### 3.2.1 P0 — T-022 Slice A DB·QA 검토

- **연결 WBS:** `T-022`
- **WBS 공식 작업일:** `2026-07-28 ~ 2026-07-29`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** 공식기간 경과·작성자 구현 완료·별도 DB·QA 검토일 WBS 미명시
- **착수 조건:** T-005·T-016 구현 기준선과 공식 검토 대기 경계 확인, T-017 작성자 증거, Slice A OpenAPI·Runtime·검증 결과 게시
- **완료·반환:** Active 13·원문 불변·동시성·Replay·rollback QA Matrix

- [ ] 작성자와 다른 PostgreSQL 테스트 DB에서 새 Migration 없이 Slice A 재현
- [ ] Active 13을 유지하고 Target-only `QuestionnaireSession`을 생성하지 않는지 확인
- [ ] 최초 `Inquiry.raw_text` 불변과 추가 입력 미수용 경계 확인
- [ ] 상태·버전·이력·멱등 기록의 단일 Transaction·rollback 확인
- [ ] 동일 Key·다른 Key 동시 요청, 409, Replay, 실패 후 반쪽 데이터 0 확인

#### 3.2.2 P1 — T-017A Migration·QA 검토

- **연결 WBS:** `T-017A`
- **WBS 공식 작업일:** `2026-07-30 ~ 2026-07-30`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** 공식기간 경과·별도 QA 검토일 WBS 미명시
- **착수 조건:** T-005 구현 기준선과 공식 검토 대기 경계 확인, T-017 작성자 증거, T-017A 주요 문서·결정 기록표 준비
- **완료·반환:** Migration·backfill·rollback·감사 QA Diff와 필수 Test Case

- [ ] `User.is_synthetic`, `auth_version` 필요성과 기존 행 backfill 검토
- [ ] 위반 행 발견 시 Migration 중단 기준 검토
- [ ] 빈 DB·기존 합성 DB Migration과 업무 FK 보존 계획 검토
- [ ] Refresh 폐기·동시성·rollback·마지막 관리자 보호 테스트 검토
- [ ] 계정 감사 JSON Allowlist와 append-only 불변식 검토

#### 3.2.3 P2 — T-018 최소 GET 검토

- **연결 WBS:** `T-018`
- **WBS 공식 작업일:** `2026-07-31 ~ 2026-08-03`
- **실제 협업 작업일:** `TBD — Runtime 착수 전 완료 필요`
- **일정 상태:** 공식 작업 창이나 T-017B와 2026-08-03 중첩·PM 우선순위 필요
- **착수 조건:** T-005·T-016 구현 기준선과 공식 검토 대기 경계 확인, T-017 작성자 증거, 최소 GET 제안서 준비
- **완료·반환:** 본인 범위·공개 필드·최근 관리일·정렬·오류 Test Matrix

- [ ] 본인 구독만 조회하고 타인 행·soft-deleted 고객을 제외하는 범위 검토
- [ ] `is_supported_mvp=true`, `is_active=true` 기본 필터 채택 여부 검토
- [ ] 내부 PK·고객 ID·계약번호·일련번호·주소·원본 JSON 비노출 검토
- [ ] 최근 관리일 집계 대상 상태·날짜·동률 규칙 검토
- [ ] 빈 목록 200, 401, 403, 422와 결정적 정렬 Test Matrix 검토

#### 3.2.4 P3 — 합성 데이터 책임자 검토

- **연결 WBS:** `T-013`, `T-014`
- **WBS 공식 작업일:** `T-013: 2026-07-22 ~ 2026-07-24`, `T-014: 2026-07-20 ~ 2026-07-22`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** T-014가 선행 T-013 종료보다 빠른 WBS 충돌·책임자 검토 기간 미명시
- **착수 조건:** T-013 완료 증거와 Fixture·Crosswalk·QA·Manifest 준비
- **완료·반환:** Source Hash·Data Test·QA 2회·Manifest 결정성·변경 요청

- [ ] 활성 Fixture 12종의 의미·건수·관계가 승인 데이터와 일치하는지 확인
- [ ] Backend Import Crosswalk의 Source·Mapping·차단 항목 검토
- [ ] 텍스트 Hash가 LF·CRLF·CR·BOM을 내용 변경과 구분하는지 확인
- [ ] Source Hash 검사에서 변경 0건 확인
- [ ] Data 전체 테스트 통과
- [ ] QA·Manifest를 두 번 재생성해 결과와 Hash가 결정적인지 확인
- [ ] 생성물이 매 실행마다 바뀌는 비결정적 필드를 포함하지 않는지 확인

권장 명령:

```powershell
Set-Location (git rev-parse --show-toplevel)

.\backend\.venv\Scripts\python.exe `
  .\scripts\data\refresh_source_hashes.py `
  --check

.\backend\.venv\Scripts\python.exe -B `
  -m unittest discover `
  -s .\data\tools\tests `
  -v

.\backend\.venv\Scripts\python.exe -B `
  .\data\tools\pipeline.py `
  qa `
  --verify-rebuild

.\backend\.venv\Scripts\python.exe -B `
  .\data\tools\pipeline.py `
  qa `
  --verify-rebuild
```

### 3.3 반환 증거

각 검토는 아래 공통 머리말로 범위를 분리한다.

```text
[Backend 협업 검토 결과]
reviewer=<이름>
scope=T022_DB_QA | T017A_MIGRATION_QA | T018_READ_QA | DATA_OWNER_REVIEW
decision=APPROVE | HOLD | CHANGE_REQUEST
branch=<검토 브랜치>
base_branch=main
main_pull_status=UP_TO_DATE | NEEDS_PULL
candidate_branch=<작성자 후보 브랜치 또는 NONE>
review_pr=<PR 번호 또는 URL, 없으면 NONE>
baseline_reference=<팀 기준선 또는 작성자 전달 스냅샷 식별자>
environment=<OS·Python·PostgreSQL·Docker>
commands=<실행 명령>
exit_codes=<명령별 Exit code>
observed=<실제 결과>
contract_or_schema_diff=<차이 또는 없음>
remaining_blocker=<없음 또는 상세>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```

합성 데이터 책임자 검토는 추가로 아래 세부 필드를 반환한다.

```text
[합성 데이터 책임자 검토 결과]
review_status=APPROVED | CHANGES_REQUESTED
baseline_reference=<팀 기준선 또는 작성자 전달 스냅샷 식별자>
verification_environment=<OS·도구·DB>
reviewed_paths=<경로 목록>
source_hash_check=PASS
data_test_result=<실행 결과>
qa_run_1=<PASS와 요약>
qa_run_2=<PASS와 요약>
manifest_hash_diff=0
changed_generated_outputs=<목록 또는 없음>
remaining_blocker=<없음 또는 상세>
```

### 3.4 금지사항

- Fixture 원본·상태 계약을 Hash에 맞추기 위해 임의 변경하지 않는다.
- 실패 테스트를 삭제하거나 검증 규칙을 완화하지 않는다.
- 기존 증적 DB나 Docker Volume을 책임자 검토 과정에서 삭제하지 않는다.
- 단순 문구 변경만으로 합성 Import DB를 불필요하게 재생성하지 않는다.

관련 문서:

- [T-017A 합성 사용자 계정 관리 설계서](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md)
- [T-022 증상 제출 API 설계·계약 Gate](../API/Django_REST_API_문의_증상제출_구현_검증_인계서.md)
- [T-018 구독·제품 조회 API 계약 제안서](../API/Django_REST_API_구독_제품조회_계약_제안서.md)
- [합성 데이터 스키마·적재기·PostgreSQL 검증 가이드](../데이터베이스/PostgreSQL_합성데이터_적재_통합검증_가이드.md)
- [합성 데이터 픽스처·해시·교차표 검증 보고서](../데이터베이스/PostgreSQL_합성데이터_적재_통합검증_가이드.md)

## 4. PM·State 계약 Gate

### 4.1 요청 작업

#### 4.1.1 P0 — T-022·T-023 문의·Workflow 계약 결정

- **연결 WBS:** `T-022`, `T-023`
- **WBS 공식 작업일:** `T-022: 2026-07-28 ~ 2026-07-29`, `T-023: 2026-07-30 ~ 2026-07-31`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** 공식기간 경과·T-022 Slice A 작성자 구현 완료·PM 병합 검토일은 WBS 미명시
- **착수 조건:** T-005·T-016 구현 기준선과 공식 검토 대기 경계 확인, T-017 작성자 증거와 Slice A 작성자·DB·QA 증거
- **완료·반환:** Slice A 계약 불일치 0·병합 결정과 T-023 다음 Action 정책 결정

PM 역할은 이 섹터의 WBS 공식 협업자가 아니라 운영상 계약 결정자다.

- [ ] 구현된 T-022 `submitSymptom` Path·Body·응답·State 전이·409가 PM State 계약과 일치하는지 확인
- [ ] ADHOC 제출이 상태·이력 Projection만 사용하고 Target-only 물리 행을 만들지 않는지 확인
- [ ] 다음 Workflow Action의 Source·Target·Role·Guard·Reopen 정책 확정

#### 4.1.2 P1 — T-017A·T-017B·T-017C 계정 정책·구현 순서 결정

- **연결 WBS:** `T-017A`, `T-017B`, `T-017C`
- **WBS 공식 작업일:** `T-017A: 2026-07-30`, `T-017B: 2026-08-03`, `T-017C: 2026-08-04 ~ 2026-08-05`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** T-017A 공식기간 경과·T-017B/C는 선행 승인 대기
- **착수 조건:** T-005 구현 기준선과 공식 검토 대기 경계 확인, T-017 작성자 증거와 Data·QA Migration 검토 결과
- **완료·반환:** 계정 원장·권한·감사 정책과 A 승인→B PASS→C 착수 순서

- [ ] T-017A의 단일 User 원장·합성 계정 범위·마지막 관리자 보호 정책 결정
- [ ] `is_synthetic`, `auth_version`, 계정 전용 감사 원장 채택·보류 결정
- [ ] T-017B Admin과 T-017C Lifecycle·Audit 분리 순서 승인

#### 4.1.3 P2 — T-018 공개 조회 계약 결정

- **연결 WBS:** `T-018`
- **WBS 공식 작업일:** `2026-07-31 ~ 2026-08-03`
- **실제 협업 작업일:** `TBD — Runtime 착수 전 결정`
- **일정 상태:** T-017B와 2026-08-03 중첩·PM 우선순위 필요
- **착수 조건:** 최소 GET 제안과 Data·QA 검토 결과
- **완료·반환:** CUSTOMER 범위·공개 필드·최근 관리일·부분 완료 경계

PM 역할은 T-018의 WBS 공식 협업자가 아니라 운영상 공개 계약 결정자다.

- [ ] T-018 공개 필드·CUSTOMER 전용·부분 완료 경계 결정
- [ ] T-018 최근 관리일 집계가 확정되기 전 완료 처리하지 않음

#### 4.1.4 P3 — 팀 기준선 반영 Gate

- **연결 WBS:** 독립 WBS Task 없음
- **WBS 공식 작업일:** `WBS 미명시`
- **실제 협업 작업일:** 각 담당 역할의 검토 완료 후
- **일정 상태:** 운영 Gate·개인 저장소 상태 제출 불필요
- **착수 조건:** 기능 책임자 검토·CI·계약·테스트·비밀값 비포함 확인
- **완료·반환:** 승인 변경 묶음·팀 기준선 반영 여부와 소비 시작 통지

- [ ] 각 주담당 역할의 변경 묶음·기능 책임자 검토·CI·검증 결과 확인
- [ ] Source Hash·Data QA·Backend·PostgreSQL 검증이 같은 기준선인지 확인
- [ ] 민감정보·환경파일·DB Dump가 변경 목록에 없는지 확인
- [ ] 반영 후 팀에 기준선 식별자와 소비 시작 조건 전달

Workflow Action 반환 형식:

```text
action_name=<Action>
allowed_source_states=<상태>
target_state=<상태>
actor_roles=<역할>
guard_rules=<조건>
terminal_reopen_policy=<정책>
state_version_rule=<규칙>
idempotency_rule=<규칙>
```

### 4.2 반환 증거

```text
[PM·State 계약 검토 결과]
review_scope=T022_CONTRACT | T017A_POLICY | T018_PUBLIC_CONTRACT | BASELINE_GATE
decision=APPROVE | HOLD | CHANGE_REQUEST
reviewed_change_sets=<변경 묶음 목록>
baseline_reference=<검토 기준 식별자>
data_owner_review=APPROVED
technical_gate_results=<실행 명령·Exit code·결과>
baseline_update_status=APPLIED | NOT_APPLIED | CHANGES_REQUESTED
consumer_start_allowed=true | false
next_workflow_action=<Action>
contract_diff=<차이 또는 없음>
remaining_blocker=<없음 또는 상세>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```

### 4.3 금지사항

- 기능 책임자 검토 없이 기술 수치만 보고 팀 기준선에 반영하지 않는다.
- 팀 공용 DB를 초기화하거나 다른 담당자의 Volume을 삭제하지 않는다.
- 미승인 기능 후보를 팀 공용 기준으로 배포하지 않는다.
- 확인된 회귀 결함 없이 T-005·T-016 구현 기준선을 신규 개발로 다시 열지 않는다. 단, 공식 WBS·비작성자 검토 Gate는 닫지 않는다.

## 5. Web API 소비 검토

Web 전체가 T-017A·T-022·T-018을 모두 기다리는 것은 아니다. 공통
Auth·UUID Smoke는 관련 변경의 팀 기준선 반영 후, 문의 화면은 T-022·T-023
Runtime 반영 후, 제품·구독 화면은 T-018 Runtime 반영 후 각각 수행한다. 그전에는
해당 기능의 Mock/Blocked 경계를 유지하고 미구현 Endpoint를 추측해
소비하지 않는다.

### 5.1 요청 작업

#### 5.1.1 P0 — T-045 Web 공통 UI·Auth·API Client

- **연결 WBS:** `T-045`
- **WBS 공식 작업일:** `2026-07-23 ~ 2026-07-24`
- **실제 협업 작업일:** `TBD — 완료 증거 확인 필요`
- **일정 상태:** 공식기간 경과·WBS 상태 진행 중
- **착수 조건:** T-003·T-004 완료와 팀 기준선 반영 확인
- **완료·반환:** 공통 UI·Auth·Mapper·오류 처리 Test·Lint·Build 결과

- [ ] [API Runtime 지원표](../../../api/runtime_implementation_status.md)의
  Runtime·OpenAPI-only·Mock/Blocked 구분을 Web에 반영
- [ ] 외부 문의 식별자를 Public UUID로 유지
- [ ] API `snake_case`와 Web `camelCase`를 Mapper 경계에서 변환
- [ ] ISO 8601 Offset과 `correlation_id`를 손실하지 않음
- [ ] 401 Refresh는 승인 흐름으로 한 번만 수행
- [ ] 401·403·404·409·Replay 오류를 구분

#### 5.1.2 P1 — T-038 상담 대기 문의·상태 소비

- **연결 WBS:** `T-038`
- **WBS 공식 작업일:** `2026-07-27 ~ 2026-07-28`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** 선행 T-023 공식일보다 빠른 WBS 충돌
- **착수 조건:** T-023·T-045 완료와 Runtime의 팀 기준선 반영
- **완료·반환:** 상담 대기 목록·위험도·우선순위·검색 API 소비 결과

- [ ] 상담 대기 문의 목록과 위험도·우선순위 정렬을 실제 API로 검증
- [ ] 문의 Public UUID와 서버 `allowed_actions`를 Web 화면에 그대로 반영

#### 5.1.3 P2 — T-039·T-040·T-041 상담 상세·결과·방문 일정

- **연결 WBS:** `T-039`, `T-040`, `T-041`
- **WBS 공식 작업일:** `T-039: 2026-07-29 ~ 2026-07-30`, `T-040: 2026-07-31 ~ 2026-08-03`, `T-041: 2026-08-04`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** T-039가 선행 T-030A(2026-08-18)보다 빠른 WBS 충돌
- **착수 조건:** T-030A·T-038 완료 후 T-039→T-040→T-041 순차 진행
- **완료·반환:** 상담 상세·상담 결과·State 전이·방문 희망/확정일 소비 결과

- [ ] 새 업무 요청의 `Idempotency-Key`, `state_version`,
  `allowed_actions` 처리 검증
- [ ] 상담 AI 초안·수정본·확정본과 상태 이력을 구분해 표시
- [ ] 방문 희망일·확정일·기사 배정 상태를 서버 계약대로 저장·조회

#### 5.1.4 P3 — Web 통합 QA·배포 Smoke

- **연결 WBS:** `T-046`, `T-050`, `T-051`, `T-053`
- **WBS 공식 작업일:** `T-046: 2026-08-21 ~ 2026-08-24`, `T-050: 2026-08-25 ~ 2026-08-26`, `T-051: 2026-08-27 ~ 2026-08-28`, `T-053: 2026-08-31 ~ 2026-09-01`
- **실제 협업 작업일:** 선행 화면·Runtime 완료 후 WBS 기간 사용, 충돌 시 `TBD`
- **일정 상태:** T-038~T-043 재계획 결과의 도미노 영향 가능
- **착수 조건:** T-046 통합과 T-050/T-051 선행 Gate 완료, 배포 Runtime 준비
- **완료·반환:** Test·Lint·Build·실제 Auth/API Smoke·DTO Diff·미해결 결함

- [ ] 실제 API 모드에서 Auth·현재 사용자·지원 Runtime Smoke 수행
- [ ] Runtime이 없는 상담·방문 기능은 Mock/Blocked로 표시

권장 검증:

```powershell
Set-Location .\web
node --version
npm ci
npm test
npm run lint
npm run build
```

### 5.2 반환 증거

```text
[Web API 소비 검토 결과]
consumer_role=WEB
baseline_reference=<팀 기준선 식별자>
verification_status=PASS | FAIL | BLOCKED
node_npm=<버전>
test_lint_build=<명령·Exit code·결과>
runtime_api_smoke=<Method·Path·역할·HTTP·correlation_id>
runtime_consumed=<목록>
mock_blocked=<목록>
dto_identifier_diff=<목록>
backend_change_request=<없음 또는 상세>
remaining_blocker=<없음 또는 상세>
```

### 5.3 금지사항

- Runtime이 없는 Endpoint를 실제 연동 완료로 표시하지 않는다.
- 내부 정수 PK나 `DEMO-*`·`SYN-*` 업무 코드를 문의 URL UUID로 쓰지 않는다.
- Web에서 상태머신·완료 상태·허용 행동을 자체 확정하지 않는다.
- Token·`.env.local`·실제 개인정보를 Git 추적 파일에 저장하지 않는다.

## 6. Mobile API 소비 검토

현재 즉시 전체 Mobile 검증 단계가 아니다. 고객 제품·케어는 T-018·
T-020, 문의·후속 상태는 T-023, 기사 화면은 T-030B·T-041 Runtime이
각각 팀 기준선에 반영된 뒤 수행한다. T-022·T-018 제안서를 Mobile
확정 DTO로 선반영하지 않는다.

### 6.1 요청 작업

#### 6.1.1 P0 — T-045 Mobile 공통 계약·역할 라우팅

- **연결 WBS:** `T-045`
- **WBS 공식 작업일:** `2026-07-23 ~ 2026-07-24`
- **실제 협업 작업일:** `TBD — 완료 증거 확인 필요`
- **일정 상태:** 공식기간 경과·WBS 상태 진행 중
- **착수 조건:** T-003·T-004 완료와 팀 기준선 반영 확인
- **완료·반환:** 3모듈·공통 DTO·Auth·오류·역할 라우팅 Unit·Lint 결과

- [ ] `customer-app`·`technician-app`·`core` 3모듈 구조 유지
- [ ] Runtime·OpenAPI-only·Mock/Blocked API 구분
- [ ] Public UUID, ISO 8601 Offset, 공통 Wrapper,
  `metadata.correlation_id` 보존
- [ ] Access·Refresh·역할 Guard와 401·403·404 처리
- [ ] `Idempotency-Key`, `state_version`, `allowed_actions`, 409 처리

#### 6.1.2 P1 — T-033~T-037 고객 Mobile 화면

- **연결 WBS:** `T-033`, `T-034`, `T-035`, `T-036`, `T-037`
- **WBS 공식 작업일:** `T-033: 2026-08-11 ~ 2026-08-12`, `T-034: 2026-08-13 ~ 2026-08-14`, `T-035: 2026-08-17 ~ 2026-08-18`, `T-036: 2026-08-19 ~ 2026-08-20`, `T-037: 2026-08-12 ~ 2026-08-13`
- **실제 협업 작업일:** 각 선행 Backend·AI Runtime 완료 후 WBS 기간 사용
- **일정 상태:** 공식 예정·T-018·T-020·T-021·T-022·T-023 지연 영향 가능
- **착수 조건:** T-045와 각 화면별 선행 Task의 팀 기준선 반영
- **완료·반환:** 제품·문진·AI 질문·사용 안내·후속 상태 화면 Build·DTO Diff

- [ ] T-033 제품·구독·케어 조회와 다음 케어 일정을 실제 API로 검증
- [ ] T-034~T-036 문진→AI 질문→위험도·사용 안내 흐름을 순차 검증
- [ ] T-037 문의 상태·담당 주체·고객 행동·재문의 정책을 검증
- [ ] 서버 상태를 `core` 로컬 상태머신보다 최종 기준으로 사용

#### 6.1.3 P2 — T-042·T-043 방문기사 Mobile 화면

- **연결 WBS:** `T-042`, `T-043`
- **WBS 공식 작업일:** `T-042: 2026-08-07 ~ 2026-08-10`, `T-043: 2026-08-14 ~ 2026-08-17`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** T-042가 선행 T-030B(2026-08-19)보다 빠른 WBS 충돌
- **착수 조건:** T-030B·T-041·T-045 완료 후 T-042→T-043 순차 진행
- **완료·반환:** 기사 리포트·공식 근거·방문 결과·필수값·상태 전이 결과

- [ ] 배정 방문 목록·사전 점검 리포트·공식 근거 조회를 실제 API로 검증
- [ ] 방문 결과·원인·조치·교체 항목과 COMPLETION_PENDING 전이를 검증

#### 6.1.4 P3 — Mobile 통합 QA·배포 Smoke

- **연결 WBS:** `T-046`, `T-050`, `T-051`, `T-053`
- **WBS 공식 작업일:** `T-046: 2026-08-21 ~ 2026-08-24`, `T-050: 2026-08-25 ~ 2026-08-26`, `T-051: 2026-08-27 ~ 2026-08-28`, `T-053: 2026-08-31 ~ 2026-09-01`
- **실제 협업 작업일:** 선행 화면·Runtime 완료 후 WBS 기간 사용, 충돌 시 `TBD`
- **일정 상태:** T-042/T-043 재계획의 도미노 영향 가능
- **착수 조건:** 고객·기사 화면과 T-046 통합·T-050/T-051 Gate 완료
- **완료·반환:** Unit·Lint·두 App Build·Emulator Smoke·DTO Diff·미해결 결함

- [ ] Unit Test·Lint·두 App Build 수행
- [ ] Emulator에서 현재 지원 Runtime의 실제 Smoke 수행

권장 검증:

```powershell
Set-Location .\mobile
java -version
.\gradlew.bat projects
.\gradlew.bat test
.\gradlew.bat lintDebug
.\gradlew.bat :customer-app:assembleDebug
.\gradlew.bat :technician-app:assembleDebug
```

### 6.2 반환 증거

```text
[Mobile API 소비 검토 결과]
consumer_role=MOBILE
baseline_reference=<팀 기준선 식별자>
verification_status=PASS | FAIL | BLOCKED
jdk_gradle_sdk=<버전>
unit_lint_build=<명령·Exit code·결과>
emulator=<기종·Android 버전>
runtime_api_smoke=<역할·HTTP·correlation_id>
runtime_screens=<목록>
mock_blocked_screens=<목록>
dto_contract_diff=<목록>
backend_change_request=<없음 또는 상세>
remaining_blocker=<없음 또는 상세>
```

### 6.3 금지사항

- 구형 단일 App 구조를 다시 도입하지 않는다.
- Mobile 로컬 상태를 서버 상태의 최종 권한으로 사용하지 않는다.
- Runtime이 없는 Questionnaire·Action Result·Visit·Tracking을 완료 처리하지 않는다.
- Key·Token·실제 위치·개인정보·`local.properties`를 공유하지 않는다.

## 7. AI·RAG 계약·Runtime 인계

상세 기술 반례와 수정 조건은
[백엔드·AI 계약·Runtime 통합 미해결 사항](Backend_AI_API_계약_구현_미해결_사항.md)을
단일 기준으로 사용한다.

### 7.1 요청 작업

#### 7.1.1 P0 — T-022 Slice B 예비 계약 검토

- **연결 WBS:** 독립 WBS Task 없음·`T-025` 연계
- **WBS 공식 작업일:** Slice B 검토일 미명시·연계 T-025는 `2026-07-30 ~ 2026-07-31`
- **실제 협업 작업일:** `TBD — 예비 검토만 다른 문서 검토와 병렬 가능`
- **일정 상태:** 검토 기간 WBS 미명시·최종 승인은 Slice A 확정 대기
- **착수 조건:** T-017A·T-022 주요 문서와 이 체크리스트의 회신 형식 게시, 최종 결정은 Slice A 승인 후
- **완료·반환:** AI 요청·응답·dispatch·Timeout·재처리 경계 Contract Diff

- [ ] 지금 단계에서는 T-022 Slice B의 AI 요청 Schema·응답 Echo 필드 검토
- [ ] durable dispatch 저장 위치와 DB Transaction Commit 이후 호출 경계에 대한 의견 반환
- [ ] Timeout·실패·재처리·stale `state_version` 결과 처리 정책 검토
- [ ] Slice A 승인 전 Backend가 AI Adapter를 추측 구현하지 않도록 계약 차이 반환

#### 7.1.2 P1 — T-025·T-032 Orchestrator·Timeout Runtime

- **연결 WBS:** `T-025`, `T-032`
- **WBS 공식 작업일:** `T-025: 2026-07-30 ~ 2026-07-31`, `T-032: 2026-08-04 ~ 2026-08-05`
- **실제 협업 작업일:** `TBD — PM 재계획 필요`
- **일정 상태:** T-025가 선행 T-023과 같은 기간·T-032는 T-025 지연 영향
- **착수 조건:** T-006·T-015·T-023 완료와 Slice B 최종 승인, 이후 T-016·T-025 완료
- **완료·반환:** Orchestrator 분기·Schema Parity·Timeout·재시도·Fallback 결과

- [ ] JSON Schema와 Pydantic의 전체 Parity Matrix 통과
- [ ] 성공·422·Header 불일치·Timeout·내부 실패의 구조화 로그 검증
- [ ] 실행 중 Embedding·LLM·DB Query의 취소 경계 또는 승인된 위험 기록

#### 7.1.3 P2 — T-026~T-031 Evidence·역할별 결과·안전성

- **연결 WBS:** `T-026`, `T-027`, `T-028A`, `T-028B`, `T-029`, `T-030A`, `T-030B`, `T-030C`, `T-031`
- **WBS 공식 작업일:** `T-026: 2026-08-06 ~ 2026-08-07`, `T-027: 2026-08-10 ~ 2026-08-11`, `T-028A: 2026-08-12 ~ 2026-08-13`, `T-028B: 2026-08-13 ~ 2026-08-14`, `T-029: 2026-08-14 ~ 2026-08-17`, `T-030A: 2026-08-18`, `T-030B: 2026-08-19`, `T-030C: 2026-08-20`, `T-031: 2026-08-20`
- **실제 협업 작업일:** 각 선행 Backend·AI Task 완료 후 WBS 기간 사용
- **일정 상태:** 공식 예정·T-025 재계획과 T-028A/B 당일 인계 영향 가능
- **착수 조건:** T-025→T-026→T-027, T-019·T-026→T-028A/B, 이후 T-029→T-030A/B/C
- **완료·반환:** 구조화·위험도·Evidence·상담/기사 결과·근거 부재 안전성 검증

- [ ] 검색 결과의 모델·세대·검증 상태·사용 허용 후검증
- [ ] 문서·Index·Embedding Revision과 Chunk Hash의 DB 결과 대조
- [ ] 상담용 요약과 기사 사전 점검 리포트의 AI 초안·담당자 확정본 분리
- [ ] 근거 부재·모델 불일치 시 임의 사용 가능 판정과 자가조치 차단

#### 7.1.4 P3 — AI 통합 QA·배포 Smoke

- **연결 WBS:** `T-046`, `T-049`, `T-050`, `T-051`, `T-053`
- **WBS 공식 작업일:** `T-046: 2026-08-21 ~ 2026-08-24`, `T-049: 2026-08-27 ~ 2026-08-28`, `T-050: 2026-08-25 ~ 2026-08-26`, `T-051: 2026-08-27 ~ 2026-08-28`, `T-053: 2026-08-31 ~ 2026-09-01`
- **실제 협업 작업일:** 전체 선행 Runtime 완료 후 WBS 기간 사용, 충돌 시 `TBD`
- **일정 상태:** 화면·Backend 재계획의 도미노 영향 가능
- **착수 조건:** T-046 통합, T-049~T-051 검증 대상과 배포 환경 준비
- **완료·반환:** 재현 환경·안전성·성능·Fallback·통합 E2E·배포 Smoke 결과

- [ ] Python·OS·Lock 생성 도구·의존성 범위와 재현 명령 제공
- [ ] 개인 절대경로·과거 Port·폐기된 환경값이 남은 문서 정리
- [ ] 팀 기준선에서 AI·Backend·Web·Mobile 통합 E2E와 결함 목록 반환

### 7.2 반환 증거

```text
[AI·RAG 계약·Runtime 검토 결과]
review_scope=T022_SLICE_B | AI_RUNTIME_EVIDENCE
decision=APPROVE | HOLD | CHANGE_REQUEST
baseline_reference=<팀 기준선 또는 작성자 전달 스냅샷 식별자>
verification_status=PASS | FAIL | BLOCKED
python_os_lock=<버전·범위·생성 도구>
install_pip_check_test=<명령·Exit code·결과>
health_analysis_endpoint=<Port 포함>
schema_version=<버전>
parity_matrix=<정상·경계·위반 결과>
structured_logs=<성공·오류·Timeout 결과>
timeout_cancellation=<Embedding·LLM·DB 지속 여부>
retrieval_post_validation=<모델·세대·검증·허용 결과>
revision_assertion=<Document·Index·Embedding·Chunk Hash>
contract_diff=<차이 또는 없음>
remaining_blocker=<없음 또는 PM 승인 필요 위험>
reviewed_at=<YYYY-MM-DD HH:mm KST>
```

### 7.3 금지사항

- AI 계약 입력 없이 Backend Mapper·Client를 추측 구현하지 않는다.
- AI가 업무 상태·권한·최종 EvidenceCard를 직접 확정하지 않는다.
- 샘플 검색이나 격리 pgvector 실증을 팀 전체 RAG 완료로 표시하지 않는다.
- 재시도 횟수를 늘려 전체 Timeout을 우회하지 않는다.
- Prompt·내부 경로·Secret·개인정보를 응답·로그·예시에 넣지 않는다.

## 8. 통합 완료·반환 순서

```text
T-005·T-016: 구현·기술 검증 기준선 (`IMPLEMENTATION_BASELINE_REVIEW_PENDING`) — 새 구현은 추가하지 않되 공식 WBS·비작성자 검토 Gate 유지
→ Backend·Database: T-022 Slice A 계약→검증→Runtime→검증 완료
→ P0: T-022 Slice A 독립 DB·QA 검토와 팀 기준선 반영, Slice B 예비 계약 검토
→ PM 기준선 반영 결정 뒤 T-023 착수 여부 결정
→ P1: T-017A 정책·Migration 검토 후 T-017B→T-017C 순차 수행
→ P2: T-018 최소 GET 계약·QA 검토 후 Runtime과 T-019→T-020 수행
→ 각 트랙의 PostgreSQL·권한·전체 회귀 증거 반환
→ PM 기준선 반영 완료 통지 후 전 역할이 동일 기준선 확인
→ Web·Mobile·AI 소비자 Smoke와 결함 반환
```

세부 순서:

1. T-005·T-016은 회귀 결함이 확인되지 않는 한 신규 구현으로 다시 열지 않는다. 공식 검토·WBS 상태 갱신은 별도 Gate로 계속 추적한다.
2. T-022 Slice A 독립 리뷰와 T-017A·T-018 문서 검토는 병렬 요청할 수 있다.
3. T-022 Slice A는 작성자 구현이 끝났으므로 새 기능을 덧붙이지 않고
   독립 검토·팀 기준선 반영 결과를 기다린다. 후속 Runtime은 PM이 확정한 한 트랙씩 진행한다.
4. T-018 Runtime은 최소 GET 계약 승인을 받아도 T-022 Slice A와 같은
   작업 단위에 섞지 않는다.
5. Web·Mobile 전체 소비 검증과 AI 통합 E2E는 PM이 확정한 팀 기준선에서만
   수행한다.

설계 검토에는 실행 명령이 없을 수 있다. 이때 반환 형식의 `commands`에는
검토한 문서 상대경로와 확인한 계약 경로를 적고, `decision`과
`contract_or_schema_diff`를 반드시 채운다.

결함은 다음 형식으로 원 담당자에게 반환한다.

```text
owner_role=<담당 역할>
baseline_reference=<팀 기준선 또는 작성자 전달 스냅샷 식별자>
path_or_endpoint=<경로 또는 Method·Path>
observed=<실제값>
expected=<계약값>
reproduction=<명령·환경·입력>
evidence=<Exit code·HTTP·correlation_id>
severity=P0 | P1 | P2
```

## 9. 기준 문서

- [WBS v2.0](../../../planning/md/WBS.md)
- [프로젝트 디렉토리 구조 v2](<../../../architecture/프로젝트 디렉토리 구조 v2.md>)
- [공통 개발 규칙](<../../../planning/md/공통 개발 규칙.md>)
- [팀원별 관할 영역 v2](<../../../planning/md/팀원별 관할 영역 v2.md>)
- [최지용 3주차 업무 지침서](../../../weekly-task/최지용_3주차_업무_지침서.md)
- [팀 공용 인계 허브](../../../handoffs/README.md)
- [T-017A 합성 사용자 계정 관리 설계서](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md)
- [T-022 증상 제출 API 설계·계약 Gate](../API/Django_REST_API_문의_증상제출_구현_검증_인계서.md)
- [T-018 구독·제품 조회 API 계약 제안서](../API/Django_REST_API_구독_제품조회_계약_제안서.md)
- [OpenAPI](../../../../contracts/api/openapi.yaml)
- [T-005 데이터 설계 기준선](../../../database/t-005/README.md)

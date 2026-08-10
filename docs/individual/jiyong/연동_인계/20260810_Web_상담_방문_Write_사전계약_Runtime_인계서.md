# Web 상담·방문 Write 사전 계약·Runtime 인계서

> - 작성일: 2026-08-10
> - 작성/전달: 최지용(Backend·DB) → 한예나(Web Frontend)
> - 기준: `origin/main@c6848a9ec170db37bdf10a0b46e860ef5677b072`
> - 문서 상태: `PRE_IMPLEMENTATION_HANDOFF`
> 검토 방식: 최신 `origin/main` 정적 감사. 이번 검토에서는 Runtime Smoke와 테스트를 실행하지 않았다.

## 0. 결론

- Backend에는 상담 Write 4개와 방문 Write 5개의 URL·View·계약이 존재하고, 경로 계약에는 모두 `CONFIRMED / IMPLEMENTED`가 표시되어 있다.
- 이는 **정적 구현 존재**를 뜻한다. Web에서 실제 호출에 성공했다는 의미는 아니므로 공유 Runtime Smoke 전에는 연결 완료로 표시하지 않는다.
- Web에는 상담 4개 Remote Repository와 방문 4개 Remote Repository가 준비되어 있다.
- 방문 5개 중 `markVisitNotNeeded` Remote 메서드는 없다.
- 준비된 Repository는 production 화면·Hook에서 사용되지 않는다. 현재 상담 Write Hook은 Remote 모드를 명시적으로 차단하고 Mock만 실행한다.
- 따라서 Web 작업은 상담사 GET 목록·상세 Remote Smoke 통과 후, 한 번에 한 Action씩 수직 연결한다.
- Mock은 삭제하지 않되, Remote 모드에서 오류가 발생했을 때 Mock으로 자동 대체하면 안 된다.

## 1. 기준 소스

- [상담 Write OpenAPI 경로](../../../../contracts/api/paths/consultations.yaml)
- [방문 Write OpenAPI 경로](../../../../contracts/api/paths/visits.yaml)
- [상담 Backend URL](../../../../backend/apps/consultations/api/urls.py)
- [방문 Backend URL](../../../../backend/apps/visits/api/urls.py)
- [공통 상태 전환 결과](../../../../contracts/api/components/schemas/workflow/StateTransitionResult.yaml)
- [공통 409 응답](../../../../contracts/api/components/responses/WorkflowConflict.yaml)
- [Web 상담 Write Repository](../../../../web/src/features/consultation/repositories/consultationWriteRepository.ts)
- [Web 방문 Write Repository](../../../../web/src/features/visit-transition/repositories/visitWriteRepository.ts)
- [현재 상담 Write Hook](../../../../web/src/features/consultation/hooks/useSaveConsultation.ts)
- [Web Request Context](../../../../web/src/common/api/requestContext.ts)
- [Web HTTP Client](../../../../web/src/common/api/httpClient.ts)
- [Repository 단위 테스트](../../../../web/tests/unit/writeRepositories.test.ts)

## 2. Backend 상담 Write 4개

| 순서 | Action | Method·Endpoint | 상태 전환 | 요청 핵심 | 정적 상태 |
|---:|---|---|---|---|---|
| C1 | `START_CONSULTATION` | `POST /api/v1/inquiries/{id}/start-consultation` | `CONSULTATION_REQUIRED → CONSULTATION_IN_PROGRESS` | `state_version` | 구현 존재 |
| C2 | `UPDATE_CONSULTATION_SUMMARY` | `PATCH /api/v1/inquiries/{id}/consultation-summary` | `CONSULTATION_IN_PROGRESS` 유지 | `state_version` + 변경 필드 1개 이상 | 구현 존재 |
| C3 | `CONFIRM_CONSULTATION_SUMMARY` | `POST /api/v1/inquiries/{id}/consultation-summary/confirm` | `CONSULTATION_IN_PROGRESS` 유지 | `state_version` | 구현 존재 |
| C4 | `CONSULTATION_COMPLETED` | `POST /api/v1/inquiries/{id}/complete-consultation` | `CONSULTATION_IN_PROGRESS → COMPLETION_PENDING` | `state_version`만 허용 | 구현 존재 |

주의:

- C2는 사용자 명시 저장이다. 타이머 자동 저장이나 서버 Draft 복구 범위가 아니다.
- C4 요청 스키마는 `state_version`만 받는다. Web의 현재 `CompleteConsultationRequestDto = SaveConsultationRequestDto`는 실제 계약보다 넓으므로 축소해야 한다.
- C4는 방문 검토를 타지 않는 완료 분기다. C4 이후 방문 검토를 연속 호출하지 않는다.

## 3. Backend 방문 Write 5개

| 순서 | Action | Method·Endpoint | 상태 전환 | 요청 핵심 | 정적 상태 |
|---:|---|---|---|---|---|
| V1 | `VISIT_REVIEW_REQUIRED` | `POST /api/v1/inquiries/{id}/visit-review` | `CONSULTATION_IN_PROGRESS → VISIT_REVIEW_PENDING` | `state_version`, `reason_code`, nullable `reason_detail` | 구현 존재 |
| V2-A | `VISIT_NOT_NEEDED` | `POST /api/v1/inquiries/{id}/visit-not-needed` | `VISIT_REVIEW_PENDING → COMPLETION_PENDING` | `state_version`, `reason_code`, nullable `reason_detail` | 구현 존재 |
| V2-B | `VISIT_NEEDED` | `POST /api/v1/inquiries/{id}/visits` | `VISIT_REVIEW_PENDING → VISIT_SCHEDULING` | 사유·사용 안내·기사 인계, 날짜 nullable | 구현 존재 |
| V3 | `UPDATE_VISIT_SCHEDULE` | `PATCH /api/v1/visits/{visit_id}/schedule` | Visit `ASSIGNING/SCHEDULING → SCHEDULING` | 합성 기사 UUID, 두 날짜 키 필수·값 nullable | 구현 존재 |
| V4 | `CONFIRM_VISIT` | `POST /api/v1/visits/{visit_id}/confirm` | Inquiry `VISIT_SCHEDULING → VISIT_SCHEDULED`, Visit `→ CONFIRMED` | `state_version` | 구현 존재 |

주의:

- V2-A와 V2-B는 서로 배타적인 분기다.
- V2-B 성공 시 서버가 기사 미배정 `ASSIGNING` Visit을 생성한다. Client가 다음 상태를 임의 지정하지 않는다.
- 날짜는 timestamp가 아니라 `YYYY-MM-DD`다.
- 기사 `start`와 `complete`는 계약상 `NOT_IMPLEMENTED`이며 이 Web 상담사 9개 Write 범위에서 제외한다.
- 경로 수준은 `CONFIRMED / IMPLEMENTED`지만 아래 구성 스키마 메타데이터는 아직 `G2_PROPOSED_PM_MERGE_APPROVAL`이다.
  - `VisitReviewRequest`
  - `VisitNotNeededRequest`
  - `VisitHandoff`
- Web production 연결 전 PM·Backend가 위 메타데이터를 경로 상태와 맞출지 확인해야 한다. Runtime 존재만으로 계약 메타데이터 불일치를 무시하지 않는다.

## 4. Web 현재 상태와 부족한 부분

| 항목 | origin/main에서 확인한 상태 | 판정 |
|---|---|---|
| 상담 Remote Repository | C1~C4 경로·Method 생성 코드 존재 | `PREPARED` |
| 방문 Remote Repository | V1, V2-B, V3, V4 생성 코드 존재 | `PREPARED` |
| 방문 불필요 V2-A | Repository 인터페이스·메서드 없음 | `MISSING` |
| production import/wiring | 두 Remote Repository factory를 `web/src`의 다른 파일이 사용하지 않음 | `NOT_CONNECTED` |
| 상담 화면 Write | `useSaveConsultation`이 Remote 모드에서 `RUNTIME_BLOCKED` 반환 | `MOCK_ONLY` |
| 방문 화면 Write | 기존 Mock UI와 준비 Repository가 연결되지 않음 | `MOCK_ONLY` |
| Repository 테스트 | URL·Method·Payload 생성 단위 테스트 존재 | `CONSTRUCTION_TEST_ONLY` |
| 완료 요청 DTO | 저장 DTO를 그대로 별칭 사용 | `CONTRACT_TOO_BROAD` |
| 성공 `resource` DTO | optional generic record로 선언 | `CONTRACT_TOO_LOOSE` |

`PREPARED`는 화면에서 사용할 수 있다는 뜻이 아니다. Query/Hook → Repository → HTTP Client → Backend → 재조회까지 연결되어야 `CONNECTED`로 바꿀 수 있다.

## 5. 권장 수직 연결 순서

### 5.1 선행 Gate

1. 상담사 문의 목록·상세 GET Remote Smoke를 통과한다.
2. 로그인·담당 문의 권한·공통 응답·오류 Mapper·Correlation ID를 확인한다.
3. 정확한 시작 상태와 최신 `state_version`을 가진 Seed 문의를 준비한다.
4. `VITE_USE_MOCK_API=false`에서 Mock fallback 없이 실패가 드러나는지 확인한다.

### 5.2 상담 공통 구간

1. C1 상담 시작을 단독 연결하고 검증한다.
2. C2 상담 저장을 연결하고 명시 저장·입력 유지·재조회를 검증한다.
3. C3 요약 확정을 연결하고 상태·버튼 갱신을 검증한다.

### 5.3 C3 이후 배타 분기

- 상담 종료 분기: `C3 → C4`
- 방문 판단 분기: `C3 → V1`
  - 방문 불필요: `V1 → V2-A`
  - 방문 필요: `V1 → V2-B → V3 → V4`

각 Action의 성공·Replay·409·재조회까지 끝낸 후 다음 Action으로 이동한다. 9개를 한 번에 화면에 연결하지 않는다.

## 6. 공통 구현 규칙

### 6.1 `state_version`과 `allowed_actions`

- 모든 Write body에는 서버가 마지막으로 준 `state_version`을 보낸다.
- Client가 `state_version + 1`을 계산하지 않는다.
- 성공 후 응답의 `status`, `state_version`, `allowed_actions`, `resource`를 반영하고 상세 GET을 재조회한다.
- `allowed_actions`는 서버 권한·상태 힌트다. Repository 연결·Runtime 준비·Smoke 통과 전에는 Action이 있어도 버튼을 활성화하지 않는다.

### 6.2 Idempotency와 중복 클릭

- 모든 Write에 `Idempotency-Key`를 보낸다.
- 같은 논리 요청의 네트워크 재시도만 같은 Key와 같은 Payload를 사용한다.
- Payload 또는 Action이 바뀌면 새 Key를 만든다.
- 요청 중 버튼을 잠가 이중 제출을 막는다.
- 성공 응답의 `idempotent_replay=true`를 정상 Replay로 처리한다.

### 6.3 Correlation

- 모든 Write에 `X-Correlation-ID`를 보낸다.
- 응답 헤더와 공통 응답 `metadata.correlation_id`를 오류 화면·로그 추적 기준으로 보존한다.
- 사용자에게 오류 문의용 확인 번호를 표시할 수 있어야 한다.

### 6.4 409 처리

- `STATE-CONFLICT-01`: 자동 재전송하지 않는다. 입력을 유지하고 상세 GET을 재조회한 뒤 최신 상태·버전·Action으로 교체하고 사용자 재확인을 받는다.
- `DUPLICATE-EVENT-01`: 같은 Key를 다른 요청에 사용한 충돌로 처리한다. 새 Key로 무조건 자동 재전송하지 말고 요청 의도를 다시 확인한다.
- 409 뒤 화면 상태를 추측하거나 Client가 상태를 전진시키지 않는다.

### 6.5 null과 날짜

- `reason_detail`, `preferred_date`, `confirmed_date`, 성공 결과의 `resource`는 `null`일 수 있다.
- `UpdateVisitScheduleRequest`의 두 날짜는 키가 필수지만 값은 `null` 가능하다.
- 기사 배정 전 Visit의 기사 정보도 `null`일 수 있다.
- `null`, 필드 없음, 빈 문자열을 Mapper에서 같은 값으로 뭉개지 않는다.
- 날짜는 `YYYY-MM-DD`만 전송하고 timezone timestamp로 바꾸지 않는다.

### 6.6 Mock Gate

- 기존 Mock 시나리오와 화면은 회귀 확인용으로 유지한다.
- Mock과 Remote 데이터 소스를 명시적으로 선택한다.
- Remote 모드에서 네트워크·인증·계약 오류가 나면 실패로 표시하며 Mock으로 자동 전환하지 않는다.
- 실제 Runtime 검증이 끝난 Action만 Remote 버튼을 연다.

## 7. Action별 시작 조건

다음 항목이 모두 충족될 때 한 Action 구현을 시작한다.

- [ ] 작업 기준 main SHA가 기록되어 있다.
- [ ] 상담사 GET 목록·상세 Remote Smoke가 통과했다.
- [ ] 공유 PostgreSQL Runtime과 인증 계정에 접근할 수 있다.
- [ ] 담당 상담사에게 배정된 Seed 문의가 정확한 `from_state`에 있다.
- [ ] Endpoint·Method·요청 DTO·오류 형식이 확정되어 있다.
- [ ] 방문 구성 스키마의 상태 불일치가 PM·Backend에 의해 정리되었다.
- [ ] 구현할 Action 하나와 성공 후 재조회 경로가 선택되어 있다.
- [ ] Remote 실패 시 Mock fallback 금지 조건이 유지되어 있다.

## 8. Action별 완료 조건

- [ ] 정확한 Method·Endpoint·body를 전송한다.
- [ ] Bearer, `Idempotency-Key`, `X-Correlation-ID`가 전송된다.
- [ ] 200 공통 응답과 `StateTransitionResult`를 계약대로 변환한다.
- [ ] 성공 후 상세 GET 재조회로 DB 반영 상태를 확인한다.
- [ ] 동일 Key·동일 Payload Replay를 확인한다.
- [ ] 오래된 `state_version`의 `STATE-CONFLICT-01`을 확인한다.
- [ ] 동일 Key·다른 Payload의 `DUPLICATE-EVENT-01`을 확인한다.
- [ ] 401·403·404·409·422와 네트워크 오류를 화면에서 구분한다.
- [ ] 오류·충돌 시 사용자가 작성한 값을 유지한다.
- [ ] 응답 Correlation ID를 확인 번호로 추적할 수 있다.
- [ ] Remote 실패가 Mock 성공처럼 보이지 않는다.
- [ ] 해당 Action 테스트와 기존 GET·Mock 회귀가 통과한다.

## 9. 한예나 담당자 요청사항

| ID | 요청 | 완료 회신에 필요한 근거 |
|---|---|---|
| WEB-W01 | 상담 Repository를 `PREPARED`, 화면 연결을 `NOT_CONNECTED`로 구분 | 실제 import·Hook 연결 위치 |
| WEB-W02 | V2-A `markVisitNotNeeded` Repository·DTO 추가 | Method·URL·Payload 단위 테스트 |
| WEB-W03 | C4 요청 DTO를 `state_version` 전용으로 축소 | 타입 정의와 계약 대조 |
| WEB-W04 | 성공 `resource`를 필수 키 + 상담/방문/null union으로 좁힘 | Mapper 테스트 |
| WEB-W05 | 한 번에 한 Action만 Remote로 연결 | 첫 Action과 작업 순서 회신 |
| WEB-W06 | 중복 클릭 잠금, 확인 Dialog, Loading, 입력 유지 구현 | UI·Hook 테스트 |
| WEB-W07 | 성공·409 후 상세 GET 재조회 | Query invalidation/refetch 근거 |
| WEB-W08 | Remote 오류 시 Mock fallback 금지 | Remote 실패 테스트 |
| WEB-W09 | `state_version`, 두 409 코드, Correlation ID 처리 | 오류 Mapper·화면 근거 |
| WEB-W10 | nullable 필드와 date-only 보존 | DTO Mapper·경계값 테스트 |

회신 시 아래 6가지만 먼저 알려주면 Backend가 다음 Smoke Seed를 준비할 수 있다.

1. 첫 연결 Action 선택값
2. 수정할 Hook·Query·Repository 파일
3. 필요한 Seed 시작 상태
4. 예상 요청 body 예시
5. 성공·409 뒤 재조회 방식
6. Mock/Remote 전환과 fail-closed 검증 방식

## 10. Backend·DB 지원 경계

최지용은 다음을 지원한다.

- 선택된 Action의 시작 상태를 만족하는 Seed와 담당자 배정 조건 확인
- 공유 Runtime URL·인증·DB 반영 여부 확인
- 요청/응답·상태 전환·409·Idempotency·Correlation 계약 질의 응답
- Web Smoke 중 재현된 Backend 오류의 로그·DB 원인 분석

최지용이 대신 결정하지 않는 항목은 Web Query 구조, 화면 Loading·Dialog, 입력 임시 보존 방식, 버튼 배치, Mock/Remote UI 표시다. 다만 이 선택들이 본 문서의 계약 Gate를 약화하면 연결 완료로 승인할 수 없다.

## 11. 2026-08-10 독립 검증 보강

현재 `main@c6848a9`에서 다음을 재실행했다.

| 검증 | 결과 |
|---|---|
| 상담사 조회·QA Seed·실제 HTTP·상담/방문 Write·OpenAPI/G2 표적 Backend 회귀 | `33 passed` |
| Web 조회 Remote·Query·상세·Write Repository·상담/방문 Schema | `24 passed` |
| Web ESLint | `PASS` |
| Web Production Build | `PASS` — 133 modules transformed |
| Backend 전체 회귀 | `905 passed, 14 skipped` |
| Web 전체 Unit | `32 files, 137 tests passed` |

Vitest 기본 fork worker는 이 Windows 실행환경에서 timeout이 발생해
`--pool=threads --maxWorkers=1`로 같은 6개 파일을 재실행했다. 이 결과는
Repository·DTO 준비 상태의 증거이지 Production 화면이 Write Repository를
호출한다는 증거가 아니다. 실제 UI Wiring과 공동 PostgreSQL Write Smoke는
한예나 후속 범위로 유지한다.

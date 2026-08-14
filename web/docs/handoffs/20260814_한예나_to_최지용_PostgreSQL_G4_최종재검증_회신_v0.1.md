# Web 공통 Backend 연결 PostgreSQL G4 최종 재검증 회신

- 작성일: 2026-08-14
- 작성자: 한예나(Web)
- 수신: 최지용(Backend)
- 결과: **PASS**

## 필수 회신

```text
main_sha=a29ec0f966bdefb309ee925503b0302f9e0402e8
web_candidate_commit=86069d99ae756b0fa6a66d04723c67bb4caaf34f
health_url=http://192.168.0.41:8000/health (Vite proxy http://localhost:5173/health에서 확인)
health_status=200 OK
new_inquiry_id=d8494dd1-d169-416b-9352-b3d9b8fb51c4
complete_browser_confirm_200=PASS (브라우저 native confirm 승인 경로 실행, HTTP 200 계약 응답 및 완료 성공 화면 확인)
refresh_consultation_projection=PASS (새로고침 후 상담 기록·수정 요약·확정 요약·고객 안내 복구)
header_identity_alignment=PASS (로그인 사용자와 목록·상세 Header 모두 합성 상담사 001로 일치)
final_status=COMPLETION_PENDING
final_state_version=5
tests=PASS (35 files, 156 tests)
lint=PASS
typecheck=PASS
build=PASS
result=PASS
blocker=NONE
```

## 실제 검증 내용

| 순서 | 확인 내용 | 결과 |
|---|---|---|
| 1 | `main@a29ec0f`가 포함된 개인 브랜치에서 실행 | PASS |
| 2 | Mock OFF 및 `/api/v1` Remote 설정 | PASS |
| 3 | Vite `/health` → 우선 Backend 연결 | HTTP 200 |
| 4 | `DEMO-CONSULTANT-001` 로그인 | PASS |
| 5 | 인증 사용자와 목록·상세 Header 이름 일치 | PASS |
| 6 | 새 합성 전화문의 생성 | PASS |
| 7 | 동일 Inquiry 상담 시작 → 저장 → 확정 → 완료 | PASS |
| 8 | 브라우저 native confirm 승인 경로 | PASS |
| 9 | 완료 후 상태 | `COMPLETION_PENDING · 5` |
| 10 | 새로고침 후 Consultation Projection 복구 | PASS |

### 새 검증 문의

- `inquiry_id`: `d8494dd1-d169-416b-9352-b3d9b8fb51c4`
- `inquiry_code`: `INQ-A5A7122F6E964170A955C46B50AD4B47`
- 기존 증거 문의 `8532ac21-3428-4b12-bbec-6c5e74c22259`는 조회·재사용·상태 변경하지 않았습니다.

### 상태 전이

```text
CONSULTATION_REQUIRED · 1
→ 상담 시작
CONSULTATION_IN_PROGRESS · 2
→ 상담 내용 저장
CONSULTATION_IN_PROGRESS · 3
→ 상담 요약 확정
CONSULTATION_IN_PROGRESS · 4
→ 상담 처리 완료
COMPLETION_PENDING · 5
```

### 새로고침 후 복구 확인 항목

- 상담 결과: `COMPLETED_NO_VISIT`
- 상담 기록: 복구됨
- 상담사 수정 요약: 복구됨
- 확정 요약: 복구됨
- 고객 안내: 복구됨
- 최종 상태·버전: `COMPLETION_PENDING · 5`

## Web 변경

- 상세·방문 공용 Header의 고정 사용자명과 고정 직원 코드를 제거했습니다.
- Header가 인증 세션의 `displayName`, `roleCode`를 사용하도록 변경했습니다.
- 로그인 세션 사용자와 Header 표시가 일치하는 컴포넌트 테스트를 추가했습니다.
- Backend·Mobile·AI·계약 파일은 수정하지 않았습니다.

## 검증 명령 결과

```text
npm.cmd test -- --maxWorkers=1
→ 35 files / 156 tests PASS

npm.cmd run lint
→ PASS

npm.cmd run typecheck
→ PASS

npm.cmd run build
→ PASS
```

## 참고

- `migration_status=APPLIED_EXCEPT_VISITS_0005_HOLD`를 실행 기준으로 유지했습니다.
- 이번 검증은 `방문 불필요` 상담 완료 흐름이므로 보류된 Visits Migration은 G4 완주를 차단하지 않았습니다.
- Token 및 Authorization 원문은 문서와 채팅에 기록하지 않았습니다.

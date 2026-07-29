# 3주차 Web 테스트 결과

- 기준일: 2026-07-29
- 실행 위치: `web/`
- 자동화 도구: Vitest, jsdom, React Testing Library
- 실행 시각: 2026-07-29 16:29 KST
- 실행 기준: `yena` 브랜치 본 변경 작업 트리
- 실행 환경: Windows, Node.js `v26.4.0`, npm `11.17.0`
- 깨끗한 재현 환경: 저장소 전체 임시 복사본에서 `npm.cmd ci` 후 lint·test·build 수행

## 자동화 범위

| 구분 | 검증 내용 |
| --- | --- |
| 단위 | 상담 임시 저장·완료·방문 검토 Validation |
| 단위 | 방문 일정 저장·확정 필수값과 날짜 순서 Validation |
| 단위 | 논리 쓰기별 UUID `Idempotency-Key`, 전송별 `X-Correlation-ID` 생성 |
| 단위 | 네트워크 재시도 키 보존, 성공·새 행동·요청 변경 후 키 교체 |
| 단위 | 성공 Action 객체와 상태 충돌 Action code 배열 Mapper 분리 |
| 단위 | `DUPLICATE-EVENT-01` 빈 details의 Snapshot 미적용 |
| 단위 | 공통 API Wrapper·HTTP 오류 분류·PageInfo 정규화 |
| 단위 | 로그인 응답 DTO의 메모리 인증 세션 Mapper |
| 단위 | Access Token 자동 Authorization·요청별 Correlation Header |
| 단위 | 동시 401 Refresh single-flight·원요청 1회 재시도 |
| 단위 | Refresh 실패·재시도 401의 세션 제거와 인증 제외 요청 |
| 단위 | 401 쓰기 재시도의 멱등 키 보존·추적 ID 교체 |
| 단위 | 담당자·우선순위·기간 필터와 페이지 범위 보정 |
| 단위 | API Base URL 형식 검증과 알 수 없는 상태·위험도 `UNKNOWN` 정규화 |
| 단위 | `+09:00` 일시의 날짜 경계·오전/오후 값을 시간대 재변환 없이 표시 |
| 단위 | 일반 문의의 방문기사 자동 인계와 주의·긴급 문의의 상담사 라우팅 |
| 단위 | 공식 합성 원천 기반 정상·위험·재개·무근거·빈 목록 Fixture |
| 단위 | UUID `inquiry_id`와 표시용 `inquiry_code` 분리·검증 |
| 컴포넌트 | `allowed_actions` 기반 버튼 노출 |
| 컴포넌트 | 완료 필수값과 필드 오류 연결 |
| 컴포넌트 | 409 충돌 후 입력 유지, 최신 `stateVersion` 반영 |
| 컴포넌트 | 멱등 키 재사용 409 입력 유지, 상태 Snapshot 미적용 |
| 컴포넌트 | 허용 행동이 없는 상태의 버튼 미노출 |
| 컴포넌트 | 저장 중 중복 클릭 전송 차단과 성공 후 최신 상세 Snapshot 갱신 |
| 컴포넌트 | 방문 전환 필드 노출, 입력 유지, Mock 저장·확정 |
| 컴포넌트 | 공통 EvidenceCard 공개 필드·HTTPS 링크 제한 |
| 컴포넌트 | 공통 DataTable 행·빈 상태 접근성 |
| 통합 | 상담 큐에서 문의 선택 후 상세·상담 Form 전환 |
| 통합 | 긴급 필터와 상담사 라우팅 대상 문의 조회 |
| 통합 | 일반 문의의 상담사 큐 미노출 |
| 통합 | 담당자·페이지 조건 URL Query 복원 |
| 통합 | 목록 로딩·초기 빈 목록·검색 결과 없음·403·조회 오류 분리 |
| 통합 | 목록 선택 후 UUID `/consultant/inquiries/{inquiry_id}` 상세 경로 전환 |
| 통합 | 표시용 `inquiry_code`의 상세 URL 리소스 ID 사용 차단 |
| 통합 | 상세 근거 부분 실패 시 다른 영역 유지 |
| 통합 | 상세 로딩·403·404·지원 불가 모델·AI 실패·무근거 분리 |
| 통합 | 방문 행동이 없는 문의의 CONS-03 진입 차단 |
| 통합 | 미인증 사용자의 로그인 이동 |
| 통합 | Mock 로그인 후 원래 요청 경로 복귀 |
| 통합 | 로그아웃 세션 제거와 401 Refresh 재시도 실패 시 로그인 상태 제거 |
| 통합 | 상담사·운영자 Route 역할 허용과 403 차단 |
| 통합 | ADMIN-01 Placeholder 접근 |
| 통합 | 등록되지 않은 경로의 404 분리 |

## 실행 명령

```powershell
npm.cmd run test
npm.cmd run lint
npm.cmd run build
```

## 2026-07-29 실행 결과

- `npm.cmd run test`: **23개 Test File, 92개 Test 통과**
- `npm.cmd run lint`: 통과
- `npm.cmd run build`: 통과
- Production 번들: Vite `8.1.5`, 107 modules transformed, Build 성공
- README 재현: 저장소 전체를 받은 조건에서 설치·검증 명령 통과. `web/`만 단독 복사하면 상위 `data/` Fixture 참조를 해석할 수 없으므로 지원하지 않음

## 수동 브라우저 검증 병행 항목

| Case ID | 입력·환경 | 기대 결과 | 실제 결과 |
| --- | --- | --- | --- |
| WEB-MANUAL-01 | 1920×1080, `/consultant/inquiries` | 기본 상담 화면이 문서 전체 스크롤 없이 표시됨 | 통과. page·목록·처리 영역 `clientHeight === scrollHeight` 확인 |
| WEB-MANUAL-02 | `추가 필터` 선택 | 위험도·담당자 필터가 필요할 때만 펼쳐짐 | 통과. 필터 `open`, 위험도 Select 표시 확인 |
| WEB-MANUAL-03 | `완료 내용과 AI 요약 확인` 선택 | 고객 안내·처리 결과·AI 요약이 펼쳐짐 | 통과. 처리 결과 입력 표시 확인 |
| WEB-MANUAL-04 | `http://192.168.0.15:5173/consultant/inquiries` | 같은 내부망에서 개발 화면 응답 | 통과. HTTP 200 확인 |

아래 항목은 자동 테스트와 수동 확인을 함께 유지한다.

- 상담 진행 문의 Form 레이아웃
- 빈 값 완료 처리 시 필드별 오류
- Mock 성공 후 `stateVersion` 증가
- 409 충돌 후 작성 내용 유지와 자동 재시도 방지
- 문진 상태에서 행동 버튼 미노출
- 공식 근거에서 `chunk_id`, 내부 `document_id` 미노출
- UUID `/consultant/inquiries/{inquiry_id}` 상세 경로 회귀
- `/consultant/inquiries/a6bdf6b7-b9ba-553a-8447-f928384c1ad1/visit-transition` 직접 접근과 v13 레이아웃
- 방문 전환 필수값 오류, 희망일·기사 선택, Mock 저장·확정, `stateVersion` 증가
- 검색·상태·위험도·우선순위·담당자·기간·정렬 조건의 URL 유지
- 목록 페이지 이동 후 상세 진입과 검색 조건 복귀
- 목록 초기 빈 상태·조회 오류 문구와 상담 성공 후 최신 상세 Snapshot 갱신
- 로컬 브라우저 콘솔 오류 없음

## 아직 자동화하지 않은 항목

- 실제 Backend API 통합
- 실제 Backend 인증 토큰 만료와 401 Redirect E2E(Runtime 준비 후)
- 브라우저 간 E2E
- API 확정 후 403·409·422 실제 응답 Mapper

# 3주차 Web 검토 공유안

- 작성자: 한예나
- 기준일: 2026-07-29
- 검토 대상: 상담사 `CONS-01 → CONS-02 → CONS-03` Mock 흐름과 공통 Web 계약
- 공유 대상: 최지용, 김은진, 이동윤
- 공유 경로: `yena` 브랜치와 본 문서

## 실행·검증 결과

- 실행 기준: `yena` 브랜치 본 변경 작업 트리
- 실행 환경: Node.js `v26.4.0`, npm `11.17.0`
- 저장소 전체의 깨끗한 임시 복사본에서 `npm.cmd ci` 후 아래 검증을 재현
- `npm.cmd run test`: 23개 Test File, 92개 Test 통과
- `npm.cmd run lint`: 통과
- `npm.cmd run build`: 통과
- 실제 고객 개인정보 없이 합성 데이터만 사용
- 로컬 브라우저 기본 목록·초기 빈 목록·조회 오류·상담 저장 후 상세 갱신 확인, Console Error 0건
- 1920×1080 기본 상담 화면 문서 스크롤 없음, 접이식 추가 필터·완료 내용 동작 확인
- 일반 문의→AI 방문기사 자동 인계, 주의·긴급 문의→상담사 확인 Mock 라우팅 테스트 통과
- `+09:00` 일시를 브라우저 실행 환경에 따라 재변환하지 않는 날짜 경계 테스트 통과
- `web/`은 상위 `data/` Fixture를 참조하므로 저장소 전체 clone·pull 후 실행해야 함

## 최지용 확인 요청

1. 상담 저장·완료·방문 검토 Endpoint별 요청 Body
2. `allowed_actions`, `state_version` 성공 응답 위치
3. 409의 최신 상태·버전·허용 행동과 422의 필드 오류 Wrapper
4. 상담 목록의 담당자·기간·정렬 Query 이름
5. 일반→방문기사, 주의·긴급→상담사 최초 분기 규칙의 Backend `assigned_role`·상태 이벤트 확정

## 김은진 확인 요청

1. 403·409·422·네트워크 Mock 시나리오와 실제 API Fixture의 대응
2. 동일 요청 중복 클릭·멱등 키·상태 버전 충돌 테스트 기준
3. 실제 API 준비 후 로그인→목록→상세→저장→방문 전환 E2E 범위

## 이동윤 확인 요청

1. EvidenceCard 공개 필드와 검증 상태 표시명
2. 공식 URL·직접 다운로드 URL의 공개 허용 범위
3. 근거 없음·근거 부분 실패 시 AI 초안 사용 제한 문구

## Web에서 선반영한 안전 원칙

- 상태·위험도·우선순위와 행동 가능 여부를 Web에서 추론하지 않는다.
- `chunk_id`, 내부 문서 ID, 검색 점수, 내부 경로, 원문 전체, Prompt, Trace를 표시하지 않는다.
- 409에서 사용자 입력을 버리거나 자동 덮어쓰기·자동 재전송하지 않는다.
- 알 수 없는 상태·위험도·우선순위는 `미확인`으로 표시하고 화면을 중단하지 않는다.
- 저장 중 중복 클릭은 전송하지 않고 성공 뒤 최신 상세 Snapshot을 다시 반영한다.
- 실제 Backend가 없는 동작은 화면에 Mock이라고 명시한다.

## 관련 문서

- `web/docs/week3-completion-checklist.md`
- `web/docs/week3-screen-api-db-map.md`
- `web/docs/week3-test-result.md`
- `web/docs/week3-open-issues.md`
- `docs/screens/admin-dashboard-field-plan.md`

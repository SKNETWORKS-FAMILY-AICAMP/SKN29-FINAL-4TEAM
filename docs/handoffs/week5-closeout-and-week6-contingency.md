# 5주차 종료·6주차 비상 인계

> 작성일: 2026-08-12 KST  
> 기준 Commit: `main@f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`  
> 상태: **ACTIVE · NO_SILENT_ROLLOVER**

## 목적

5주차 미완료 업무가 6주차에 담당자·완료 조건 없이 넘어가 흐려지는 것을 막는다. 8월 14일까지 증거가 없는 항목은 완료로 간주하지 않고 `HOLD` 상태와 아래 첫 실행 단위를 그대로 인계한다.

## 즉시 실행 순서

| 순서 | 작업 | 담당 | 완료 증거 | 기한 | 미완료 시 처리 |
|---:|---|---|---|---|---|
| 1 | `f781e92` 기준 AI·Web Contract ACK 수집·Baseline 고정 | 이동윤·한예나, 판정 윤승혁 | ACK 5/5, Contract CI·Data CI PASS URL, 고정 SHA | 8/13 | 3.3 `HOLD`, 6주차 첫 Gate로 고정 |
| 2 | Web 상담사 실제 Remote Smoke | 한예나·최지용·김은진 | 로그인→목록→상세→상담→Visit, 409 입력 보존, Mock 비대체, 명령·Exit Code | 8/13 | 3.6 `HOLD`, 화면 기능 추가 중단 |
| 3 | Mobile 상담요청 재Smoke와 공개 Route 결정 | 양정현·최지용·김은진 | 상담요청 실단말 결과, Guidance·Evidence와 기사 Visit Route 또는 명시적 차단 응답 | 8/14 | 3.6 `HOLD`, 6주차 Route 구현을 최우선 배치 |
| 4 | 실제 Backend↔AI 수직 연결 | 이동윤·최지용·김은진 | 동일 Inquiry의 Local HTTP·Multi-Agent·LLM·팀 pgvector·Evidence·DB·Trace, 정상·위험·근거 없음·오류 | 8/14 | 3.5 `HOLD`, Mock PASS와 분리 인계 |
| 5 | 5주차 최종 Exit | 윤승혁·김은진 | `week5-exit-gate.md`의 최종 SHA·Gate별 판정·잔여 Blocker | 8/14 | 미판정 금지, 증거 부족은 `HOLD` |

## 6주차 첫 작업으로 고정할 범위

8월 14일까지 닫히지 않은 경우 다음 순서를 바꾸지 않는다.

1. 고객 Guidance·Evidence 공개 DTO와 Route
2. 기사 배정 Visit 목록·상세·시작·완료 Route와 객체 권한
3. 실제 LLM·팀 pgvector·Evidence Verifier를 포함한 Backend↔AI Gate
4. 상담 요약·기사 리포트 고도화
5. 위 선행 Gate가 통과한 뒤에만 대표 E2E

신규 P1, UI 재설계, 추가 Agent 확대는 위 1~3의 인력과 시간을 사용하지 않는다.

## PM 판정 규칙

- 코드 병합만으로 담당자 ACK나 실제 Remote PASS를 대신하지 않는다.
- Mock·Fixture·단위 Test PASS를 실제 Runtime PASS로 올리지 않는다.
- 담당자 회신이 없거나 실행 환경이 없으면 상태를 비워두지 않고 `HOLD`로 기록한다.
- 6주차에 일정 재협의가 필요해도 담당자, 해제 조건, 다음 확인 시점 중 하나를 삭제하지 않는다.

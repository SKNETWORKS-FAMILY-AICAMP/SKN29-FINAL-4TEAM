# 5주차 Web·Mobile Consumer Integration Gate

> 착수일: **2026-08-11 KST**
> 기준 Commit: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 관련 업무: `윤승혁_5주차_업무_지침서.md` 3.6
> 현재 판정: **IN_PROGRESS · PRECHECK_HOLD**

## 1. 판정 요약

계약 소비 회신과 영역별 작성자 Test는 접수했지만, 같은 기준 Commit에서 실제 Backend를 호출한 Web·Mobile Remote 증거가 아직 완성되지 않았다. 따라서 3.6은 착수하되 현재 `PASS`로 닫지 않는다.

| 영역 | 확인된 증거 | 미충족 조건 | 현재 판정 |
|---|---|---|---|
| Web | 상태·`state_version`·`allowed_actions`·Date·403/404/409 소비, Remote 표적 34 Test·Mock 142 Test·Lint·TypeScript·Build PASS 보고 | 보고 Commit의 현재 기준선 포함 확인, 실제 Backend 목록·상세·상담·Visit·Evidence Remote Smoke | `HOLD` |
| Mobile | DTO·UiState·Action·Date·Error·Remote/Mock 경계, Unit·Connected·APK·실단말 설치 PASS 보고; 구현 Commit은 현재 main 포함 | Guidance·Follow-up·기사 Visit Backend Route와 같은 Commit의 고객·기사 Remote Smoke | `HOLD` |

3.3 계약 소비 승인과 3.6 실제 Remote 통합 승인은 별도다. 작성자 Test가 통과했더라도 실제 Backend 소비 증거가 없으면 3.6 ACK로 계산하지 않는다.

## 2. Web 완료 확인 항목

- [ ] 현재 기준 Commit 또는 후속 후보 Commit에서 Web 변경 SHA를 확인한다.
- [ ] `VITE_USE_MOCK_API=false`에서 Mock 자동 대체가 없음을 확인한다.
- [ ] 상담사 로그인→문의 목록→상세→AI·Evidence→상담→Visit 흐름을 실제 Backend로 실행한다.
- [ ] `allowed_actions`를 서버 응답에서 사용하고 상태를 자체 계산하지 않음을 확인한다.
- [ ] 403·404·409·422·Network와 409 이후 입력 보존을 확인한다.
- [ ] Date-only·주소 비노출·Correlation ID를 확인한다.
- [ ] Test·Lint·TypeScript·Build 결과와 Exit Code를 남긴다.

## 3. Mobile 완료 확인 항목

- [ ] 현재 기준 Commit 또는 후속 후보 Commit에서 Mobile 변경 SHA를 확인한다.
- [ ] Remote Mode에서 Fake Repository 자동 대체가 없음을 확인한다.
- [ ] 고객 로그인→구독→문의→증상→추가 질문→AI 안내를 실제 Backend로 실행한다.
- [ ] 기사 로그인→배정 Visit→상세→승인 Action을 실제 Backend로 실행한다.
- [ ] `allowed_actions`·`state_version`·Date·Error와 409 입력 보존을 확인한다.
- [ ] Unit·UI·Build·APK·Remote 결과와 Exit Code를 같은 후보 Commit에 연결한다.

## 4. 해제 조건

1. Backend 계약 소비 `CHANGE_REQUEST`가 해소된다.
2. Web의 현재 기준선 포함 여부와 실제 Remote Smoke가 확인된다.
3. Mobile에 필요한 Backend Route가 제공되고 고객·기사 Remote Smoke가 통과한다.
4. Web·Mobile·Backend 결과가 같은 후보 Commit을 가리킨다.
5. 김은진이 실행 결과와 Mock 비대체를 독립 재현한다.

## 5. 회신 형식

```text
reviewer=<한예나 | 양정현 | 김은진>
review_scope=WEEK5_WEB_MOBILE_CONSUMER_INTEGRATION
baseline_commit=<전체 SHA>
area=WEB | MOBILE | QA
remote_mode=PASS | FAIL | NOT_RUN
mock_fallback=NONE | FOUND | NOT_RUN
scenario_result=<실행 시나리오별 결과>
tests=<명령·passed/skipped/failed>
build=<명령·Exit Code>
backend_routes=<확인한 Route>
decision=APPROVE | CHANGE_REQUEST | HOLD
remaining_blocker=<없으면 NONE>
```

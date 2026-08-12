# 5주차 Web·Mobile Consumer Integration Gate

> 착수일: **2026-08-11 KST**
> 기준 Commit: `main@f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`
> 관련 업무: `윤승혁_5주차_업무_지침서.md` 3.6
> 현재 판정: **IN_PROGRESS · HOLD**

## 1. 판정 요약

계약 소비 회신과 영역별 작성자 Test는 접수했지만, 같은 기준 Commit에서 실제 Backend를 호출한 Web·Mobile Remote 증거가 아직 완성되지 않았다. 따라서 3.6은 착수하되 현재 `PASS`로 닫지 않는다.

| 영역 | 확인된 증거 | 미충족 조건 | 현재 판정 |
|---|---|---|---|
| Web | 상담·Visit 소비 코드와 CONS-04 전화문의 Remote Repository·공동 Smoke Fixture가 main에 포함됨. 작성자 Test·Lint·Build 보고 존재 | 실제 Backend 목록·상세·상담·Visit·Evidence Remote Smoke와 409 입력 보존 재현 | `HOLD` |
| Mobile | 고객 Snapshot·Questions·Answers Follow-up 3 API 실단말 Remote PASS, Mock 자동 성공 없음. 상담요청 Backend Runtime 제공 | 상담요청 실단말 재검증, Guidance·Evidence 및 기사 Visit 공개 Route와 고객·기사 Remote Smoke | `HOLD` |

3.3 계약 소비 승인과 3.6 실제 Remote 통합 승인은 별도다. 작성자 Test가 통과했더라도 실제 Backend 소비 증거가 없으면 3.6 ACK로 계산하지 않는다.

## 2. Web 완료 확인 항목

- [x] 현재 기준 Commit에 Web 변경이 포함됐음을 확인했다.
- [ ] `VITE_USE_MOCK_API=false`에서 Mock 자동 대체가 없음을 확인한다.
- [ ] 상담사 로그인→문의 목록→상세→AI·Evidence→상담→Visit 흐름을 실제 Backend로 실행한다.
- [ ] `allowed_actions`를 서버 응답에서 사용하고 상태를 자체 계산하지 않음을 확인한다.
- [ ] 403·404·409·422·Network와 409 이후 입력 보존을 확인한다.
- [ ] Date-only·주소 비노출·Correlation ID를 확인한다.
- [ ] Test·Lint·TypeScript·Build 결과와 Exit Code를 남긴다.

## 3. Mobile 완료 확인 항목

- [x] 현재 기준 Commit에 Mobile 변경이 포함됐음을 확인했다.
- [x] Remote Mode에서 Follow-up 실패를 Fake 성공으로 자동 대체하지 않음을 확인했다.
- [x] 고객 로그인→구독→문의→증상→추가 질문·답변까지 실제 Backend로 실행했다.
- [ ] 고객 AI Guidance·Evidence를 실제 Backend로 실행한다.
- [ ] 기사 로그인→배정 Visit→상세→승인 Action을 실제 Backend로 실행한다.
- [ ] `allowed_actions`·`state_version`·Date·Error와 409 입력 보존을 확인한다.
- [ ] Unit·UI·Build·APK·Remote 결과와 Exit Code를 같은 후보 Commit에 연결한다.

## 4. 해제 조건

1. Backend 후속 계약과 독립 QA가 완료된다.
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

## 6. 2026-08-12 재판정

- Web 코드의 main 포함 여부는 해소됐다. 남은 조건은 상담사 계정의 실제 Backend Smoke다.
- Mobile Follow-up 3 API는 완료 범위로 닫는다.
- `REQUEST_CONSULTATION` Runtime은 `60046c5`에 포함됐으나 Mobile 실단말 소비 결과가 아직 없다.
- 고객 Guidance·Evidence와 기사 Visit Route는 여전히 Backend 차단이며 Mobile은 fail-closed를 유지한다.
- 따라서 부분 성과는 승인하지만 3.6 전체 판정은 `HOLD`다.

## 7. 2026-08-12 PM 로컬 회귀

기준 Commit `f781e92`에서 Web 소비 코드의 표적 회귀와 Build를 다시 실행했다.

| 항목 | 결과 |
|---|---|
| `PhoneInquiryCreatePage`, 상담·Visit Write Repository 표적 Test | `3 files / 10 tests PASS` |
| TypeScript Project Build | `PASS` |
| Vite Production Build | `PASS` |

기본 셸의 Node `v20.11.0`은 `node:util.styleText`가 없어 Vitest 시작에 실패했다. 코드 판정에는 Node `v24.14.0`으로 재실행한 결과를 사용했다. 이 결과는 Web 로컬 소비 코드의 회귀 증거이며 실제 Backend Remote Smoke를 대신하지 않는다.

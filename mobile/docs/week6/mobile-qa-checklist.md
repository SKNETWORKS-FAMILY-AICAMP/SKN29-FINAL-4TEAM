# Week 6 Mobile QA Checklist

寃利앹씪: 2026-08-18

## Build / Unit

- [x] `:core:testDebugUnitTest`
- [x] `:customer-app:testDebugUnitTest`
- [x] `:customer-app:assembleDebug`
- [x] `:customer-app:assembleDebugAndroidTest`
- [x] `:customer-app:assembleRelease`
- [x] Release lintVital
- [x] `compileDebugKotlin`
- [x] `git diff --check`

## Customer Physical AndroidTest

- [x] `CustomerMinimumFlowTest` ??8
- [x] `FollowUpQuestionsSectionTest` ??4
- [x] `GuidanceFallbackStateTest` ??3
- [x] `CustomerBackStackNavigationTest` ??3

```text
18 unique tests
0 failed
0 skipped
```

500 targeted physical test??蹂꾨룄 ?ъ떎?됲븯??PASS ?뺤씤.

## Clean Install

- [x] App data clear
- [x] Uninstall
- [x] Package ?쒓굅 ?뺤씤
- [x] Debug APK install
- [x] Launcher ?ㅽ뻾
- [x] Process ?앹〈
- [x] adb reverse

## Lifecycle

- [x] Portrait process stability
- [x] Landscape process stability
- [x] Font scale 130% process stability
- [x] Background ??Foreground process survival
- [ ] Portrait clipping visual ??NOT VERIFIED
- [ ] Landscape clipping visual ??NOT VERIFIED
- [ ] Font 130% visual overlap ??NOT VERIFIED

## Keyboard / CTA

- [ ] Physical keyboard opened ??NOT VERIFIED
- [ ] Keyboard CTA obstruction ??NOT VERIFIED
- [ ] Physical typed Draft rotation ??NOT VERIFIED

## Network Failure

- [x] ?ㅼ젣 connection failure 諛쒖깮
- [x] Network error log ?뺤씤
- [x] Crash ?놁쓬
- [x] Process ?앹〈
- [x] reverse 蹂듦뎄
- [ ] Network customer copy visual ??NOT VERIFIED

```text
NETWORK_FAILURE_LOG_MATCH_COUNT=3
CRASH_MATCH_COUNT=0
NETWORK_FAILURE_CRASH_SAFETY=PASS
REVERSE_RESTORED=True
```

## HTTP Error

- [x] 401 handling
- [x] 403 safe handling
- [x] 404 safe handling
- [x] 409 latest-state recovery
- [x] 500 mapping / retryable / draft preservation
- [x] Network failure handling

## Logcat

```text
SENSITIVE_LOG_MATCH_COUNT=0
LOGCAT_SENSITIVE_AUDIT=PASS
```

## Release

- [x] Release APK build
- [x] Developer tools audit
- [x] 怨좉컼 ?붾㈃ ?대? 湲곗닠?⑹뼱 static audit

## Remote E2E

- [x] ?ㅼ젣 Backend ?곌껐
- [x] ?ㅼ젣 Login / Subscription
- [x] ?ㅼ젣 Inquiry ?앹꽦
- [x] ?ㅼ젣 Snapshot / Question 議고쉶
- [x] ?ㅼ젣 409 state conflict
- [x] ?ㅼ젣 ?곷떞 ?붿껌
- [x] ?숈씪 Inquiry latest-state 媛깆떊

Backend/AI blocker:

- [ ] ?뺤긽 `SUBMIT_ANSWERS`
- [ ] ?뺤긽 AI Guidance
- [ ] 怨듭떇 Evidence
- [ ] `SAFE_GUIDANCE_READY`
- [ ] ?뺤긽 Guidance 湲곕컲 final same-inquiry E2E

## Git

- [x] branch = `jeonghyun`
- [x] HEAD baseline ?쇱튂
- [x] origin/jeonghyun baseline ?쇱튂
- [x] origin/main baseline ?쇱튂
- [x] staged changes ?놁쓬
- [x] Backend / AI 蹂寃??놁쓬
- [x] Mobile ?몃? 蹂寃??놁쓬
- [x] commit ?놁쓬
- [x] push ?놁쓬

```text
FINAL_GIT_AUDIT_PASS=True
```
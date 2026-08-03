# Week 3 Mobile Test Result

- Verified: 2026-08-03 20:32:24 +09:00
- Branch: $branch
- Baseline commit before this change: $headBefore

## Verification command

`cmd
gradlew.bat :customer-app:clean :technician-app:clean :customer-app:testDebugUnitTest :customer-app:connectedDebugAndroidTest :customer-app:assembleDebug :technician-app:assembleDebug
`

## Result

- Customer unit tests: PASS
- Customer connected Compose UI tests: PASS
- Customer Debug APK: PASS
- Technician Debug APK: PASS
- Protected backend/contract paths included in this commit: NO

## Device connection

`	ext
List of devices attached
R3CT8076D7B            device product:b4qksx model:SM_F721N device:b4q transport_id:2

`

## ADB reverse

`	ext
UsbFfs tcp:8000 tcp:8000

`

## Java

`	ext
openjdk version "17.0.19" 2026-04-21 LTS
OpenJDK Runtime Environment Microsoft-13877129 (build 17.0.19+10-LTS)
OpenJDK 64-Bit Server VM Microsoft-13877129 (build 17.0.19+10-LTS, mixed mode, sharing)
`

## Gradle

`	ext

------------------------------------------------------------
Gradle 9.5.0
------------------------------------------------------------

Build time:    2026-04-28 12:05:30 UTC
Revision:      3fe117d68f3907790f3809f121aa36303a9151f8

Kotlin:        2.3.20
Groovy:        4.0.29
Ant:           Apache Ant(TM) version 1.10.15 compiled on August 25 2024
Launcher JVM:  17.0.19 (Microsoft 17.0.19+10-LTS)
Daemon JVM:    Compatible with Java 21, any vendor, nativeImageCapable=false (from gradle/gradle-daemon-jvm.properties)
OS:            Windows 11 10.0 amd64

`
"@

     = @"
# Week 3 Mobile Open Issues

- Updated: 2026-08-03 20:32:24 +09:00

## Remaining team verification

1. Verify all production inquiry, consultation, visit, technician schedule, and location endpoints against the latest approved backend contract.
2. Re-run token refresh, logout revocation, 403/404 distinction, and 409 conflict scenarios in the shared integration environment.
3. Confirm llowed_actions, workflow states, evidence fields, and customer safety wording with backend, AI, and PM owners.
4. Capture distinct final screenshots for CUST-01, CUST-02, CUST-04, consultation request, and technician dashboard.
5. Confirm another team member can reproduce the build from the repository README.
6. Create a review PR after pushing jeonghyun; do not merge until API and safety wording are reviewed.

## Deferred scope

- CUST-03 additional AI questions
- CUST-06 complete inquiry detail and post-completion workflow
- Full technician production workflow
- FCM, Room, WorkManager, and non-essential infrastructure
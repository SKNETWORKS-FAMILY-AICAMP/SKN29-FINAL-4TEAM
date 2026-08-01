# Week 3 Mobile Test Result

- Verified: 2026-07-31 15:56:02 +09:00
- Local branch: jeonghyun
- GitHub connection/push: not performed

## Automated verification

`cmd
gradlew.bat :core:test :customer-app:clean :technician-app:clean :customer-app:testDebugUnitTest :customer-app:connectedDebugAndroidTest :customer-app:assembleDebug :technician-app:assembleDebug
`

- Build/test verification: PASS: reused the successful V3 build/test outputs.
- Core tests: PASS
- Customer unit tests: PASS
- Customer connected Compose UI tests: PASS
- Customer Debug APK: PASS
- Technician Debug APK: PASS
- Backend: SKIPPED
- Device installation: SKIPPED
- Backend source diff: PASS, no changes
- Contracts diff: PASS, no changes
- Sensitive/generated file check: PASS

## Environment

### Java

`	ext
openjdk version "17.0.19" 2026-04-21 LTS
OpenJDK Runtime Environment Microsoft-13877129 (build 17.0.19+10-LTS)
OpenJDK 64-Bit Server VM Microsoft-13877129 (build 17.0.19+10-LTS, mixed mode, sharing)
`

### Gradle

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

### Android device

`	ext
Device verification skipped.
`

## Verified customer flow

- CUST-01 customer home
- CUST-02 multiple symptom input and submit action
- CUST-04 guidance rendering
- Danger consultation action visible
- Danger resolved action hidden
- General, caution, danger, no-evidence, AI-failure, and network-failure scenarios
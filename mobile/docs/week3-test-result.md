# Week 3 Mobile Test Result

## Verification command

```cmd
gradlew.bat :customer-app:clean :technician-app:clean :customer-app:testDebugUnitTest :customer-app:connectedDebugAndroidTest :customer-app:assembleDebug :technician-app:assembleDebug
```

## Result

- Customer unit tests: PASS
- Customer connected Compose UI tests: PASS
- Customer Debug APK: PASS
- Technician Debug APK: PASS
- Protected backend/contract paths included in this commit: NO

## Test device

- Model: `SM_F721N`
- ADB serial: `R3CT8076D7B`

## Backend integration

- PostgreSQL container: PASS
- Django system check: PASS
- Django migrations: PASS
- Demo data preparation: PASS
- Health endpoint: PASS
- Customer demo login: PASS
- Technician demo login: PASS
- Physical-device forwarding: `tcp:8000 -> tcp:8000`
- Mobile base URL: `http://127.0.0.1:8000/`

## Environment

- Java: OpenJDK 17.0.19
- Gradle: 9.5.0
- Kotlin: 2.3.20
- OS: Windows 11
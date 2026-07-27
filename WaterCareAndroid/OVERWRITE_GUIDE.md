# 기존 Android 프로젝트 덮어쓰기 안내

## 1. 기존 프로젝트 백업

기존 프로젝트 폴더를 먼저 복사합니다.

```text
WaterCareAndroid
→ WaterCareAndroid_backup
```

## 2. 덮어쓰기용 ZIP 사용

별도로 제공된 `WaterCare_정수기딜러_캐릭터통합_v0.4_덮어쓰기용.zip`의 압축을 풉니다.

압축 내부의 다음 항목을 기존 `WaterCareAndroid` 폴더에 복사합니다.

```text
app/
build.gradle.kts
settings.gradle.kts
gradle.properties
gradle/
gradlew
gradlew.bat
README.md
OVERWRITE_GUIDE.md
```

Windows에서 파일 충돌 창이 나오면 다음을 선택합니다.

```text
대상 폴더의 파일 덮어쓰기
```

## 3. 유지해야 하는 파일

다음 파일과 폴더는 기존 내용을 유지합니다.

```text
local.properties
.idea/
.gradle/
build/
app/build/
```

특히 `local.properties`는 Android SDK 경로와 카카오 네이티브 앱 키가 들어 있으므로 삭제하거나 공유하지 않습니다.

## 4. Android Studio 갱신

덮어쓰기 후 Android Studio에서 다음 순서로 실행합니다.

```text
File
→ Sync Project with Gradle Files
→ Build
→ Clean Project
→ Run
```

캐시 때문에 이전 화면이 보이면 다음을 실행합니다.

```text
File
→ Invalidate Caches
→ Invalidate and Restart
```

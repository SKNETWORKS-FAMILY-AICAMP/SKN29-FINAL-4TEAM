import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localProperties = Properties().apply {
    val file = rootProject.file(
        "local.properties"
    )

    if (file.exists()) {
        file.inputStream().use(::load)
    }
}

fun String.asBuildConfigString(): String =
    replace("\\", "\\\\")
        .replace("\"", "\\\"")

android {
    namespace = "com.skn29.watercare"
    compileSdk = 37

    defaultConfig {
        applicationId =
            "com.skn29.watercare.technician"

        minSdk = 26
        targetSdk = 37

        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner =
            "androidx.test.runner." +
                "AndroidJUnitRunner"

        buildConfigField(
            "String",
            "KAKAO_NATIVE_APP_KEY",
            "\"${
                localProperties.getProperty(
                    "KAKAO_NATIVE_APP_KEY",
                    ""
                ).asBuildConfigString()
            }\""
        )

        buildConfigField(
            "String",
            "BACKEND_BASE_URL",
            "\"${
                localProperties.getProperty(
                    "BACKEND_BASE_URL",
                    "http://10.0.2.2:8000/"
                ).asBuildConfigString()
            }\""
        )
    }

    /**
     * AGP 9 Built-in Kotlin 공식 DSL 형식입니다.
     *
     * directories는 File 객체가 아니라 String 경로를 받으므로
     * technicianApp 모듈을 기준으로 customerApp의 공통 소스와
     * 리소스 경로를 문자열로 추가합니다.
     */
    sourceSets.named("main") {
        kotlin.directories +=
            "../app/src/main/java"

        res.directories +=
            "../app/src/main/res"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility =
            JavaVersion.VERSION_17

        targetCompatibility =
            JavaVersion.VERSION_17
    }

    packaging {
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "META-INF/LICENSE*",
            "META-INF/NOTICE*"
        )
    }
}

dependencies {
    implementation(
        platform(
            "androidx.compose:" +
                "compose-bom:2026.06.00"
        )
    )

    implementation(
        "androidx.core:core-ktx:1.17.0"
    )
    implementation(
        "androidx.activity:" +
            "activity-compose:1.13.0"
    )
    implementation(
        "androidx.lifecycle:" +
            "lifecycle-runtime-ktx:2.10.0"
    )
    implementation(
        "androidx.lifecycle:" +
            "lifecycle-runtime-compose:2.10.0"
    )
    implementation(
        "androidx.navigation:" +
            "navigation-compose:2.9.8"
    )

    implementation("androidx.compose.ui:ui")
    implementation(
        "androidx.compose.ui:" +
            "ui-tooling-preview"
    )
    implementation(
        "androidx.compose.foundation:foundation"
    )
    implementation(
        "androidx.compose.material3:material3"
    )

    debugImplementation(
        "androidx.compose.ui:ui-tooling"
    )

    implementation(
        "com.google.android.gms:" +
            "play-services-code-scanner:16.1.0"
    )
    implementation(
        "com.google.android.gms:" +
            "play-services-location:21.4.0"
    )
    implementation(
        "com.google.mlkit:" +
            "text-recognition-korean:16.0.1"
    )
    implementation(
        "com.kakao.maps.open:android:2.14.0"
    )

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation(
        "androidx.test.ext:junit:1.2.1"
    )
    androidTestImplementation(
        "androidx.test.espresso:" +
            "espresso-core:3.6.1"
    )
    androidTestImplementation(
        "androidx.compose.ui:" +
            "ui-test-junit4"
    )
    debugImplementation(
        "androidx.compose.ui:" +
            "ui-test-manifest"
    )
}

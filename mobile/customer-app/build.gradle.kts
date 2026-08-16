import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use(::load)
}
fun String.asBuildConfigString() = replace("\\", "\\\\").replace("\"", "\\\"")

val customerCareMode = localProperties
    .getProperty("CUSTOMER_CARE_MODE", "REMOTE")
    .trim()
    .uppercase()
val demoSubscriptionId = localProperties
    .getProperty("DEMO_SUBSCRIPTION_ID", "")
    .trim()
val e2eCustomerCode = localProperties
    .getProperty("E2E_CUSTOMER_CODE", "SYN-CUSTOMER-001")
    .trim()
    .ifBlank { "SYN-CUSTOMER-001" }
val showDeveloperTools = localProperties
    .getProperty("SHOW_DEVELOPER_TOOLS", "false")
    .trim()
    .toBooleanStrictOrNull()
    ?: false

android {
    namespace = "com.skn29.watercare.customer"
    compileSdk = 37
    defaultConfig {
        applicationId = "com.skn29.watercare.customer"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "1.0.0-rebuild"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "BACKEND_BASE_URL", "\"${localProperties.getProperty("BACKEND_BASE_URL", "http://127.0.0.1:8000/").asBuildConfigString()}\"")
        buildConfigField("String", "CUSTOMER_CARE_MODE", "\"${customerCareMode.asBuildConfigString()}\"")
        buildConfigField("String", "E2E_CUSTOMER_CODE", "\"${e2eCustomerCode.asBuildConfigString()}\"")
        buildConfigField("String", "DEMO_SUBSCRIPTION_ID", "\"${demoSubscriptionId.asBuildConfigString()}\"")
        buildConfigField("boolean", "SHOW_DEVELOPER_TOOLS", showDeveloperTools.toString())
        buildConfigField("String", "KAKAO_NATIVE_APP_KEY", "\"${localProperties.getProperty("KAKAO_NATIVE_APP_KEY", "").asBuildConfigString()}\"")
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    packaging { resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "META-INF/LICENSE*", "META-INF/NOTICE*") }
}

dependencies {
    implementation(project(":core"))
    implementation(platform("androidx.compose:compose-bom:2026.06.00"))
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.11.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.11.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.11.0")
    implementation("androidx.navigation:navigation-compose:2.9.8")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.11.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.11.0")

    androidTestImplementation(platform("androidx.compose:compose-bom:2026.06.00"))
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("com.squareup.retrofit2:retrofit:3.0.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

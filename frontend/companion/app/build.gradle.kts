import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use(::load)
}
fun localValue(name: String, fallback: String = "") = localProperties.getProperty(name)
    ?: providers.gradleProperty(name).orNull
    ?: fallback

android {
    namespace = "com.mindmesh.companion"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.mindmesh.clone.companion"
        minSdk = 24
        targetSdk = 35
        versionCode = 5
        versionName = "2.0.3"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    val apiBaseUrl = localValue("MINDMESH_API_BASE_URL", "http://10.0.2.2:8000/api/")
    val supabaseUrl = localValue("SUPABASE_URL")
    val supabaseKey = localValue("SUPABASE_PUBLISHABLE_KEY")
    buildTypes {
        debug { buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"") }
        release { isMinifyEnabled = false; buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"") }
    }
    buildFeatures { compose = true; buildConfig = true }
    defaultConfig {
        buildConfigField("String", "SUPABASE_URL", "\"$supabaseUrl\"")
        buildConfigField("String", "SUPABASE_PUBLISHABLE_KEY", "\"$supabaseKey\"")
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
    implementation(libs.androidx.work.runtime)
    implementation(libs.retrofit)
    implementation(libs.retrofit.gson)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.androidx.security)
    implementation(libs.kotlinx.coroutines.android)
    testImplementation(libs.junit)
}

package com.skn29.watercare

import android.app.Application
import android.os.Build
import android.util.Log
import com.kakao.vectormap.KakaoMapSdk
import com.skn29.watercare.util.AppKeyHashLogger

/**
 * 카카오맵 SDK 사용 가능 여부를 앱 전체에서 공유합니다.
 *
 * - 실제 ARM Android 기기: 카카오맵 사용
 * - x86/x86_64 에뮬레이터: 카카오맵 초기화를 건너뛰고 시연 지도 사용
 */
object KakaoMapRuntime {

    @Volatile
    var isReady: Boolean = false
        private set

    internal fun markReady() {
        isReady = true
    }

    internal fun markUnavailable() {
        isReady = false
    }
}

class WaterPurifierDealerApplication : Application() {

    override fun onCreate() {
        super.onCreate()

        AppKeyHashLogger.log(this)

        val appKey = BuildConfig.KAKAO_NATIVE_APP_KEY.trim()

        val hasValidAppKey =
            appKey.isNotBlank() &&
                !appKey.startsWith("YOUR_", ignoreCase = true) &&
                !appKey.contains("본인의_")

        val supportsKakaoNativeLibrary =
            Build.SUPPORTED_ABIS.any { abi ->
                abi == "arm64-v8a" || abi == "armeabi-v7a"
            }

        if (!hasValidAppKey) {
            KakaoMapRuntime.markUnavailable()

            Log.w(
                TAG,
                "KAKAO_NATIVE_APP_KEY가 설정되지 않아 시연 지도를 사용합니다."
            )
            return
        }

        if (!supportsKakaoNativeLibrary) {
            KakaoMapRuntime.markUnavailable()

            Log.w(
                TAG,
                "현재 ABI에서는 카카오맵 네이티브 라이브러리를 사용할 수 없습니다. " +
                    "시연 지도로 전환합니다. " +
                    "ABI=${Build.SUPPORTED_ABIS.joinToString()}"
            )
            return
        }

        try {
            KakaoMapSdk.init(this, appKey)
            KakaoMapRuntime.markReady()

            Log.i(TAG, "카카오맵 SDK 초기화 완료")
        } catch (error: UnsatisfiedLinkError) {
            KakaoMapRuntime.markUnavailable()

            Log.e(
                TAG,
                "카카오맵 네이티브 라이브러리를 찾지 못해 시연 지도로 전환합니다.",
                error
            )
        } catch (error: RuntimeException) {
            KakaoMapRuntime.markUnavailable()

            Log.e(
                TAG,
                "카카오맵 SDK 초기화에 실패해 시연 지도로 전환합니다.",
                error
            )
        }
    }

    private companion object {
        const val TAG = "KAKAO_MAP"
    }
}

package com.skn29.watercare

import android.app.Application
import android.os.Build
import android.util.Log
import com.kakao.vectormap.KakaoMapSdk
import com.skn29.watercare.util.AppKeyHashLogger

/**
 * 카카오맵 SDK의 실제 초기화 성공 여부를 앱 전체에서 공유한다.
 *
 * Kakao Maps SDK의 네이티브 라이브러리를 지원하지 않는 에뮬레이터에서는
 * 초기화를 건너뛰고 시연용 지도를 사용한다.
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

        val appKey = BuildConfig.KAKAO_NATIVE_APP_KEY
        val hasValidAppKey =
            appKey.isNotBlank() && !appKey.startsWith("YOUR_")

        val supportsKakaoNativeLibrary =
            Build.SUPPORTED_ABIS.any { abi ->
                abi == "arm64-v8a" || abi == "armeabi-v7a"
            }

        if (!hasValidAppKey) {
            KakaoMapRuntime.markUnavailable()
            Log.w(
                "KAKAO_MAP",
                "KAKAO_NATIVE_APP_KEY가 없어 시연용 지도를 사용합니다."
            )
            return
        }

        if (!supportsKakaoNativeLibrary) {
            KakaoMapRuntime.markUnavailable()
            Log.w(
                "KAKAO_MAP",
                "현재 기기 ABI가 카카오맵 네이티브 라이브러리를 지원하지 않아 " +
                    "시연용 지도를 사용합니다. " +
                    "ABI=${Build.SUPPORTED_ABIS.joinToString()}"
            )
            return
        }

        try {
            KakaoMapSdk.init(this, appKey)
            KakaoMapRuntime.markReady()
            Log.i("KAKAO_MAP", "카카오맵 SDK 초기화 완료")
        } catch (error: UnsatisfiedLinkError) {
            KakaoMapRuntime.markUnavailable()
            Log.e(
                "KAKAO_MAP",
                "카카오맵 네이티브 라이브러리를 불러오지 못해 시연용 지도로 전환합니다.",
                error
            )
        } catch (error: RuntimeException) {
            KakaoMapRuntime.markUnavailable()
            Log.e(
                "KAKAO_MAP",
                "카카오맵 SDK 초기화에 실패해 시연용 지도로 전환합니다.",
                error
            )
        }
    }
}

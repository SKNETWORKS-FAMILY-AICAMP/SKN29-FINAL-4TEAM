package com.skn29.watercare.util

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.util.Base64
import android.util.Log
import java.security.MessageDigest

object AppKeyHashLogger {
    private const val TAG = "KAKAO_KEY_HASH"

    @Suppress("DEPRECATION")
    fun log(context: Context) {
        runCatching {
            val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val packageInfo = context.packageManager.getPackageInfo(
                    context.packageName,
                    PackageManager.GET_SIGNING_CERTIFICATES
                )
                packageInfo.signingInfo?.apkContentsSigners.orEmpty()
            } else {
                val packageInfo = context.packageManager.getPackageInfo(
                    context.packageName,
                    PackageManager.GET_SIGNATURES
                )
                packageInfo.signatures.orEmpty()
            }

            signatures.forEach { signature ->
                val digest = MessageDigest.getInstance("SHA-1")
                val hash = Base64.encodeToString(
                    digest.digest(signature.toByteArray()),
                    Base64.NO_WRAP
                )
                Log.i(TAG, "package=${context.packageName}, keyHash=$hash")
            }
        }.onFailure { throwable ->
            Log.e(TAG, "키 해시 계산 실패", throwable)
        }
    }
}

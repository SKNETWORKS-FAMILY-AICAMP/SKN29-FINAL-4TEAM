package com.skn29.watercare.technician.tracking

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * 기사 GPS 수집과 백엔드 업로드만 담당한다.
 * 고객 앱의 로컬 TrackingRepository에는 의존하지 않는다.
 */
class TechnicianTrackingCoordinator(
    context: Context,
    private val scope: CoroutineScope,
    private val visitId: String,
    private val accessToken: String
) {
    private var lastUploadedAtMillis = 0L

    private val tracker = TechnicianLocationTracker(
        context = context,
        onLocation = { sample ->
            val shouldUpload =
                sample.recordedAtMillis -
                    lastUploadedAtMillis >= 2_500L

            if (shouldUpload) {
                scope.launch {
                    TechnicianVisitTrackingApi
                        .sendTechnicianLocation(
                            visitId = visitId,
                            accessToken = accessToken,
                            sample = sample
                        )
                        .onSuccess {
                            lastUploadedAtMillis =
                                sample.recordedAtMillis
                        }
                        .onFailure { error ->
                            Log.e(
                                "TECHNICIAN_TRACKING",
                                "기사 위치 업로드 실패",
                                error
                            )
                        }
                }
            }
        },
        onError = { error ->
            Log.e(
                "TECHNICIAN_TRACKING",
                "기사 GPS 추적 시작 실패",
                error
            )
        }
    )

    fun hasLocationPermission(): Boolean =
        tracker.hasPermission()

    fun start(): Boolean =
        tracker.start()

    fun stop() {
        tracker.stop()
    }
}

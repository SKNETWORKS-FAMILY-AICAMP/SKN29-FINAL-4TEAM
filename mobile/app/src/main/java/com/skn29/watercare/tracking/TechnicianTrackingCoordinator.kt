package com.skn29.watercare.tracking

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * 기사 GPS 수집 → 위치 보정 → 백엔드 업로드를 한 곳에서 처리한다.
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
            scope.launch {
                val accepted = TrackingRepository.updateLiveLocation(
                    point = sample.point,
                    speedMps = sample.speedMps,
                    headingDegrees = sample.headingDegrees,
                    accuracyMeters = sample.accuracyMeters,
                    recordedAtMillis = sample.recordedAtMillis
                )

                if (
                    accepted &&
                    sample.recordedAtMillis - lastUploadedAtMillis >= 2_500L
                ) {
                    VisitTrackingApi.sendTechnicianLocation(
                        visitId = visitId,
                        accessToken = accessToken,
                        sample = sample
                    ).onSuccess {
                        lastUploadedAtMillis = sample.recordedAtMillis
                    }.onFailure { error ->
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

    fun start(): Boolean {
        TrackingRepository.acceptCall()
        return tracker.start()
    }

    fun stop() {
        tracker.stop()
    }
}

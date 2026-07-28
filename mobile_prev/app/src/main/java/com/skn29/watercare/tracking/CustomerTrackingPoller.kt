package com.skn29.watercare.tracking

import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay

/**
 * WebSocket 적용 전 단계에서 고객 앱이 최신 기사 위치를 주기적으로 조회한다.
 *
 * 이후 Django Channels를 도입하면 이 클래스만 WebSocket 수신기로 교체하면 된다.
 */
class CustomerTrackingPoller(
    private val visitId: String,
    private val accessToken: String,
    private val pollingIntervalMillis: Long = 3_000L
) {
    suspend fun run() {
        while (true) {
            try {
                VisitTrackingApi.fetchLatestLocation(
                    visitId = visitId,
                    accessToken = accessToken
                ).onSuccess { latest ->
                    if (latest != null) {
                        TrackingRepository.updateLiveLocation(
                            point = latest.point,
                            speedMps = latest.speedMps,
                            headingDegrees = latest.headingDegrees,
                            accuracyMeters = latest.accuracyMeters,
                            recordedAtMillis = latest.recordedAtMillis
                        )
                    }
                }.onFailure { error ->
                    TrackingRepository.refreshTrackingHealth()
                    Log.e(
                        "CUSTOMER_TRACKING",
                        "최근 기사 위치 조회 실패",
                        error
                    )
                }

                TrackingRepository.refreshTrackingHealth()
                delay(pollingIntervalMillis)
            } catch (cancellation: CancellationException) {
                throw cancellation
            }
        }
    }
}

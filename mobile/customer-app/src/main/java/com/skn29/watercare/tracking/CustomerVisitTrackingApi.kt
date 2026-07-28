package com.skn29.watercare.tracking

import com.skn29.watercare.BuildConfig
import com.skn29.watercare.model.GeoPoint
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class RemoteTrackingLocation(
    val point: GeoPoint,
    val speedMps: Float?,
    val headingDegrees: Double?,
    val accuracyMeters: Float?,
    val recordedAtMillis: Long
)

/**
 * 고객 앱에서 최근 방문기사 위치를 조회한다.
 */
object CustomerVisitTrackingApi {
    suspend fun fetchLatestLocation(
        visitId: String,
        accessToken: String
    ): Result<RemoteTrackingLocation?> =
        withContext(Dispatchers.IO) {
            runCatching {
                val endpoint =
                    BuildConfig.BACKEND_BASE_URL.trimEnd('/') +
                        "/api/visits/$visitId/tracking/"

                val root = JSONObject(
                    executeJsonRequest(
                        endpoint = endpoint,
                        accessToken = accessToken
                    )
                )

                val latest = root.optJSONObject("latest_location")
                    ?: return@runCatching null

                val recordedAtMillis =
                    latest.optLong("recorded_at_epoch_millis", 0L)
                        .takeIf { it > 0L }
                        ?: System.currentTimeMillis()

                RemoteTrackingLocation(
                    point = GeoPoint(
                        latitude = latest.getDouble("latitude"),
                        longitude = latest.getDouble("longitude")
                    ),
                    speedMps = latest
                        .optDouble("speed_mps", Double.NaN)
                        .takeIf { it.isFinite() }
                        ?.toFloat(),
                    headingDegrees = latest
                        .optDouble("heading", Double.NaN)
                        .takeIf { it.isFinite() },
                    accuracyMeters = latest
                        .optDouble("accuracy_meters", Double.NaN)
                        .takeIf { it.isFinite() }
                        ?.toFloat(),
                    recordedAtMillis = recordedAtMillis
                )
            }
        }

    private fun executeJsonRequest(
        endpoint: String,
        accessToken: String
    ): String {
        val connection =
            URL(endpoint).openConnection() as HttpURLConnection

        return try {
            connection.requestMethod = "GET"
            connection.connectTimeout = 8_000
            connection.readTimeout = 12_000
            connection.setRequestProperty("Accept", "application/json")

            if (accessToken.isNotBlank()) {
                connection.setRequestProperty(
                    "Authorization",
                    "Bearer $accessToken"
                )
            }

            val responseCode = connection.responseCode
            val responseText = (
                if (responseCode in 200..299) {
                    connection.inputStream
                } else {
                    connection.errorStream
                }
                )?.bufferedReader()?.use { it.readText() }.orEmpty()

            check(responseCode in 200..299) {
                "방문 위치 API 오류($responseCode): $responseText"
            }

            responseText
        } finally {
            connection.disconnect()
        }
    }
}

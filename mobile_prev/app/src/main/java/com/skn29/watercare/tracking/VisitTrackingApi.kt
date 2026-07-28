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
 * 실제 기사 단말과 고객 단말이 Django 백엔드를 통해 위치를 공유할 때 사용한다.
 *
 * accessToken에는 로그인 후 받은 JWT access token을 전달한다.
 */
object VisitTrackingApi {
    suspend fun sendTechnicianLocation(
        visitId: String,
        accessToken: String,
        sample: TechnicianLocationSample
    ): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val endpoint =
                BuildConfig.BACKEND_BASE_URL.trimEnd('/') +
                    "/api/visits/$visitId/location/"

            val body = JSONObject()
                .put("latitude", sample.point.latitude)
                .put("longitude", sample.point.longitude)
                .put("accuracy_meters", sample.accuracyMeters)
                .put("speed_mps", sample.speedMps)
                .put("heading", sample.headingDegrees)
                .toString()

            executeJsonRequest(
                endpoint = endpoint,
                method = "POST",
                accessToken = accessToken,
                requestBody = body
            )
            Unit
        }
    }

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
                        method = "GET",
                        accessToken = accessToken,
                        requestBody = null
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
        method: String,
        accessToken: String,
        requestBody: String?
    ): String {
        val connection =
            URL(endpoint).openConnection() as HttpURLConnection

        return try {
            connection.requestMethod = method
            connection.connectTimeout = 8_000
            connection.readTimeout = 12_000
            connection.setRequestProperty(
                "Accept",
                "application/json"
            )

            if (accessToken.isNotBlank()) {
                connection.setRequestProperty(
                    "Authorization",
                    "Bearer $accessToken"
                )
            }

            if (requestBody != null) {
                connection.doOutput = true
                connection.setRequestProperty(
                    "Content-Type",
                    "application/json"
                )
                connection.outputStream
                    .bufferedWriter()
                    .use { it.write(requestBody) }
            }

            val responseCode = connection.responseCode
            val responseText = (
                if (responseCode in 200..299) {
                    connection.inputStream
                } else {
                    connection.errorStream
                }
                ).bufferedReader().use { it.readText() }

            check(responseCode in 200..299) {
                "방문 위치 API 오류($responseCode): $responseText"
            }

            responseText
        } finally {
            connection.disconnect()
        }
    }
}

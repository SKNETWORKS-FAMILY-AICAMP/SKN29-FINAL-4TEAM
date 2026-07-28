package com.skn29.watercare.technician.tracking

import com.skn29.watercare.technician.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object TechnicianVisitTrackingApi {
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

            val connection =
                URL(endpoint).openConnection() as HttpURLConnection

            try {
                connection.requestMethod = "POST"
                connection.connectTimeout = 8_000
                connection.readTimeout = 12_000
                connection.doOutput = true
                connection.setRequestProperty(
                    "Accept",
                    "application/json"
                )
                connection.setRequestProperty(
                    "Content-Type",
                    "application/json"
                )

                if (accessToken.isNotBlank()) {
                    connection.setRequestProperty(
                        "Authorization",
                        "Bearer $accessToken"
                    )
                }

                connection.outputStream
                    .bufferedWriter()
                    .use { it.write(body) }

                val responseCode = connection.responseCode
                val responseText = (
                    if (responseCode in 200..299) {
                        connection.inputStream
                    } else {
                        connection.errorStream
                    }
                    )?.bufferedReader()?.use { it.readText() }.orEmpty()

                check(responseCode in 200..299) {
                    "기사 위치 업로드 오류($responseCode): $responseText"
                }
            } finally {
                connection.disconnect()
            }
        }
    }
}

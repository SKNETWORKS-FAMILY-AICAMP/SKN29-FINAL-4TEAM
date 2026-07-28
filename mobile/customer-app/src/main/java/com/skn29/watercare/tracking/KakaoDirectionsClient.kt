package com.skn29.watercare.tracking

import com.skn29.watercare.BuildConfig
import com.skn29.watercare.model.GeoPoint
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException

internal data class RoadRouteResult(
    val points: List<GeoPoint>,
    val distanceMeters: Int,
    val durationSeconds: Int
)

internal object KakaoDirectionsClient {
    suspend fun fetchDrivingRoute(
        origin: GeoPoint,
        destination: GeoPoint
    ): Result<RoadRouteResult> =
        withContext(Dispatchers.IO) {
            runCatching {
                val baseUrl =
                    BuildConfig.BACKEND_BASE_URL
                        .trim()
                        .trimEnd('/')

                check(baseUrl.startsWith("http")) {
                    "BACKEND_BASE_URL 설정이 올바르지 않습니다."
                }

                val endpoint =
                    "$baseUrl/api/routes/driving/" +
                        "?origin_lat=${origin.latitude}" +
                        "&origin_lng=${origin.longitude}" +
                        "&destination_lat=${destination.latitude}" +
                        "&destination_lng=${destination.longitude}"

                val connection = (
                    URL(endpoint).openConnection()
                        as HttpURLConnection
                    ).apply {
                    requestMethod = "GET"
                    connectTimeout = 10_000
                    readTimeout = 20_000
                    useCaches = false
                    setRequestProperty(
                        "Accept",
                        "application/json"
                    )
                }

                try {
                    val responseCode =
                        connection.responseCode

                    val responseText = (
                        if (responseCode in 200..299) {
                            connection.inputStream
                        } else {
                            connection.errorStream
                        }
                        )
                        ?.bufferedReader()
                        ?.use { reader ->
                            reader.readText()
                        }
                        .orEmpty()

                    if (responseCode !in 200..299) {
                        error(
                            readableServerError(
                                responseCode =
                                    responseCode,
                                responseText =
                                    responseText
                            )
                        )
                    }

                    parseRoute(
                        JSONObject(responseText)
                    )
                } finally {
                    connection.disconnect()
                }
            }.recoverCatching { error ->
                throw when (error) {
                    is ConnectException ->
                        IllegalStateException(
                            "Django 서버에 연결할 수 없습니다. " +
                                "서버 실행과 BACKEND_BASE_URL을 확인하세요.",
                            error
                        )

                    is SocketTimeoutException ->
                        IllegalStateException(
                            "경로 서버 응답 시간이 초과되었습니다. " +
                                "네트워크와 Django 서버를 확인하세요.",
                            error
                        )

                    is UnknownHostException ->
                        IllegalStateException(
                            "백엔드 주소를 찾을 수 없습니다. " +
                                "BACKEND_BASE_URL을 확인하세요.",
                            error
                        )

                    else -> error
                }
            }
        }

    private fun readableServerError(
        responseCode: Int,
        responseText: String
    ): String {
        val detail = runCatching {
            JSONObject(responseText)
                .optString("detail")
                .takeIf { it.isNotBlank() }
        }.getOrNull()

        return when (responseCode) {
            404 ->
                "백엔드 경로 API를 찾지 못했습니다. " +
                    "/api/routes/driving/ 등록을 확인하세요."

            401,
            403 ->
                "경로 API 접근 권한이 없습니다."

            502 ->
                detail
                    ?: "Django에서 카카오 길찾기 호출에 실패했습니다. " +
                        "REST API 키를 확인하세요."

            else ->
                detail
                    ?: "백엔드 길찾기 오류($responseCode)"
        }
    }

    private fun parseRoute(
        root: JSONObject
    ): RoadRouteResult {
        val pointArray =
            root.optJSONArray("points")
                ?: error(
                    root.optString(
                        "detail",
                        "도로 경로 좌표가 없습니다."
                    )
                )

        val points = buildList {
            for (
                index in 0 until pointArray.length()
            ) {
                val point =
                    pointArray.getJSONObject(index)

                add(
                    GeoPoint(
                        latitude =
                            point.getDouble("lat"),
                        longitude =
                            point.getDouble("lng")
                    )
                )
            }
        }

        check(points.size >= 2) {
            "도로 경로 좌표가 부족합니다."
        }

        return RoadRouteResult(
            points = points,
            distanceMeters =
                root.optInt(
                    "distance_meters",
                    0
                ),
            durationSeconds =
                root.optInt(
                    "duration_seconds",
                    0
                )
        )
    }
}

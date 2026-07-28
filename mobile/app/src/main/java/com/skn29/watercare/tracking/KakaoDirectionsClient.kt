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

                val endpoints = buildEndpoints(
                    baseUrl = baseUrl,
                    origin = origin,
                    destination = destination
                )

                var lastNotFoundBody = ""

                for (endpoint in endpoints) {
                    val response = requestRoute(endpoint)

                    if (
                        response.code ==
                        HttpURLConnection.HTTP_NOT_FOUND
                    ) {
                        lastNotFoundBody = response.body
                        continue
                    }

                    if (response.code !in 200..299) {
                        error(
                            readableServerError(
                                responseCode = response.code,
                                responseText = response.body
                            )
                        )
                    }

                    return@runCatching parseRoute(
                        JSONObject(response.body)
                    )
                }

                error(
                    readableServerError(
                        responseCode =
                            HttpURLConnection.HTTP_NOT_FOUND,
                        responseText = lastNotFoundBody
                    )
                )
            }.recoverCatching { error ->
                throw when (error) {
                    is ConnectException ->
                        IllegalStateException(
                            "Django 경로 서버에 연결할 수 없습니다. " +
                                "WaterCareBackend 서버와 " +
                                "adb reverse tcp:8000 설정을 확인하세요.",
                            error
                        )

                    is SocketTimeoutException ->
                        IllegalStateException(
                            "경로 서버 응답 시간이 초과되었습니다. " +
                                "Django 서버와 네트워크를 확인하세요.",
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

    private data class HttpResult(
        val code: Int,
        val body: String
    )

    /**
     * 이전 백엔드와 main 백엔드의 URL 접두사가 달라도
     * 경로 API를 자동으로 탐색한다.
     */
    private fun buildEndpoints(
        baseUrl: String,
        origin: GeoPoint,
        destination: GeoPoint
    ): List<String> {
        val normalized = baseUrl.trimEnd('/')
        val routeUrls = linkedSetOf<String>()

        fun addRoute(path: String) {
            routeUrls +=
                "$normalized$path" +
                    "?origin_lat=${origin.latitude}" +
                    "&origin_lng=${origin.longitude}" +
                    "&destination_lat=${destination.latitude}" +
                    "&destination_lng=${destination.longitude}"
        }

        when {
            normalized.endsWith("/api/v1") -> {
                addRoute("/routes/driving/")

                val root =
                    normalized.removeSuffix("/api/v1")

                routeUrls +=
                    "$root/api/routes/driving/" +
                        "?origin_lat=${origin.latitude}" +
                        "&origin_lng=${origin.longitude}" +
                        "&destination_lat=${destination.latitude}" +
                        "&destination_lng=${destination.longitude}"
            }

            normalized.endsWith("/api") -> {
                addRoute("/routes/driving/")

                val root =
                    normalized.removeSuffix("/api")

                routeUrls +=
                    "$root/api/v1/routes/driving/" +
                        "?origin_lat=${origin.latitude}" +
                        "&origin_lng=${origin.longitude}" +
                        "&destination_lat=${destination.latitude}" +
                        "&destination_lng=${destination.longitude}"
            }

            else -> {
                addRoute("/api/routes/driving/")
                addRoute("/api/v1/routes/driving/")
            }
        }

        return routeUrls.toList()
    }

    private fun requestRoute(
        endpoint: String
    ): HttpResult {
        val connection = (
            URL(endpoint).openConnection()
                as HttpURLConnection
            ).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout = 20_000
            useCaches = false
            instanceFollowRedirects = true
            setRequestProperty(
                "Accept",
                "application/json"
            )
        }

        return try {
            val responseCode = connection.responseCode
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

            HttpResult(
                code = responseCode,
                body = responseText
            )
        } finally {
            connection.disconnect()
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
                "경로 API를 찾지 못했습니다. " +
                    "8000번 포트에서 WaterCareBackend가 " +
                    "실행 중인지 확인하세요."

            401,
            403 ->
                detail
                    ?: "경로 API 접근 권한이 없습니다."

            502 ->
                detail
                    ?: "Django에서 카카오 길찾기 호출에 실패했습니다. " +
                        "WaterCareBackend의 REST API 키를 확인하세요."

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

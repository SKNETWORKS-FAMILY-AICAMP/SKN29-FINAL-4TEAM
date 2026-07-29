package com.skn29.watercare.data.dispatch

import com.skn29.watercare.BuildConfig
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

object ServiceCallApi {
    private val baseUrl: String =
        BuildConfig.BACKEND_BASE_URL.trimEnd('/') + "/"

    suspend fun create(
        request: CreateServiceCallRequest
    ): ServiceCall {
        val body = JSONObject()
            .put("customer_device_id", request.customerDeviceId)
            .put("customer_name", request.customerName)
            .put("customer_phone", request.customerPhone)
            .put("customer_address", request.customerAddress)
            .put("customer_latitude", request.customerLatitude)
            .put("customer_longitude", request.customerLongitude)
            .put("product_name", request.productName)
            .put("product_model", request.productModel)
            .put("symptom", request.symptom)

        return parseCall(
            JSONObject(
                execute(
                    method = "POST",
                    path = "api/service-calls/",
                    body = body
                )
            )
        )
    }

    suspend fun get(callId: String): ServiceCall =
        parseCall(
            JSONObject(
                execute(
                    method = "GET",
                    path = "api/service-calls/$callId/"
                )
            )
        )

    suspend fun cancel(
        callId: String,
        customerDeviceId: String
    ): ServiceCall {
        val body = JSONObject()
            .put("customer_device_id", customerDeviceId)

        return parseCall(
            JSONObject(
                execute(
                    method = "POST",
                    path = "api/service-calls/$callId/cancel/",
                    body = body
                )
            )
        )
    }

    suspend fun drivingRoute(
        originLatitude: Double,
        originLongitude: Double,
        destinationLatitude: Double,
        destinationLongitude: Double
    ): DrivingRoute {
        val query = listOf(
            "origin_lat" to originLatitude.toString(),
            "origin_lng" to originLongitude.toString(),
            "destination_lat" to destinationLatitude.toString(),
            "destination_lng" to destinationLongitude.toString()
        ).joinToString("&") { (key, value) ->
            "${encode(key)}=${encode(value)}"
        }

        val json = JSONObject(
            execute(
                method = "GET",
                path = "api/routes/driving/?$query"
            )
        )
        val pointsJson = json.optJSONArray("points")
            ?: JSONArray()

        val points = buildList {
            for (index in 0 until pointsJson.length()) {
                val item = pointsJson.getJSONObject(index)
                add(
                    RoutePoint(
                        latitude = item.numberAsDouble("lat")
                            ?: continue,
                        longitude = item.numberAsDouble("lng")
                            ?: continue
                    )
                )
            }
        }

        return DrivingRoute(
            distanceMeters = json.optInt("distance_meters", 0),
            durationSeconds = json.optInt(
                "duration_seconds",
                0
            ),
            points = points
        )
    }

    private suspend fun execute(
        method: String,
        path: String,
        body: JSONObject? = null
    ): String = withContext(Dispatchers.IO) {
        val connection = (
            URL(baseUrl + path).openConnection()
                as HttpURLConnection
            ).apply {
                requestMethod = method
                connectTimeout = 10_000
                readTimeout = 15_000
                setRequestProperty(
                    "Accept",
                    "application/json"
                )
                setRequestProperty(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )
                doInput = true
            }

        try {
            if (body != null) {
                connection.doOutput = true
                connection.outputStream.bufferedWriter(
                    Charsets.UTF_8
                ).use {
                    it.write(body.toString())
                }
            }

            val code = connection.responseCode
            val stream = if (code in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream
            }

            val response = stream
                ?.bufferedReader(Charsets.UTF_8)
                ?.use { it.readText() }
                .orEmpty()

            if (code !in 200..299) {
                val detail = runCatching {
                    JSONObject(response).optString(
                        "detail",
                        response
                    )
                }.getOrDefault(response)

                throw IOException(
                    detail.ifBlank {
                        "서버 요청에 실패했습니다. HTTP $code"
                    }
                )
            }

            response
        } finally {
            connection.disconnect()
        }
    }

    private fun parseCall(json: JSONObject): ServiceCall =
        ServiceCall(
            id = json.getString("id"),
            customerDeviceId = json.getString(
                "customer_device_id"
            ),
            customerName = json.getString("customer_name"),
            customerPhone = json.getString("customer_phone"),
            customerAddress = json.getString(
                "customer_address"
            ),
            customerLatitude = json.numberAsDouble(
                "customer_latitude"
            ) ?: 0.0,
            customerLongitude = json.numberAsDouble(
                "customer_longitude"
            ) ?: 0.0,
            productName = json.getString("product_name"),
            productModel = json.getString("product_model"),
            symptom = json.getString("symptom"),
            status = ServiceCallStatus.from(
                json.getString("status")
            ),
            technicianDeviceId = json.nullableString(
                "technician_device_id"
            ),
            technicianName = json.nullableString(
                "technician_name"
            ),
            technicianLatitude = json.numberAsDouble(
                "technician_latitude"
            ),
            technicianLongitude = json.numberAsDouble(
                "technician_longitude"
            ),
            technicianAccuracyMeters = json.numberAsDouble(
                "technician_accuracy_meters"
            ),
            technicianSpeedMps = json.numberAsDouble(
                "technician_speed_mps"
            ),
            technicianHeading = json.numberAsDouble(
                "technician_heading"
            ),
            trackingConnectionState = json.optString(
                "tracking_connection_state",
                "CONNECTING"
            ),
            locationAgeSeconds = json.numberAsInt(
                "location_age_seconds"
            ),
            distanceMeters = json.numberAsInt(
                "distance_meters"
            ),
            etaMinutes = json.numberAsInt("eta_minutes"),
            resultType = json.nullableString("result_type"),
            diagnosis = json.optString("diagnosis"),
            actionTaken = json.optString("action_taken"),
            partsUsed = json.optString("parts_used"),
            customerNote = json.optString("customer_note"),
            followUpRequired = json.optBoolean(
                "follow_up_required",
                false
            )
        )

    private fun JSONObject.nullableString(
        key: String
    ): String? {
        if (!has(key) || isNull(key)) return null
        return optString(key).takeIf { it.isNotBlank() }
    }

    private fun JSONObject.numberAsDouble(
        key: String
    ): Double? {
        if (!has(key) || isNull(key)) return null
        return when (val value = get(key)) {
            is Number -> value.toDouble()
            is String -> value.toDoubleOrNull()
            else -> null
        }
    }

    private fun JSONObject.numberAsInt(
        key: String
    ): Int? = numberAsDouble(key)?.toInt()

    private fun encode(value: String): String =
        URLEncoder.encode(value, Charsets.UTF_8.name())
}

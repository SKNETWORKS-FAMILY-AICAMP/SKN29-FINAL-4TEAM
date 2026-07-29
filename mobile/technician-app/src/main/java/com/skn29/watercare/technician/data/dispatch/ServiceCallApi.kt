package com.skn29.watercare.technician.data.dispatch

import com.skn29.watercare.technician.BuildConfig
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener

object ServiceCallApi {
    private val baseUrl: String =
        BuildConfig.BACKEND_BASE_URL.trimEnd('/') + "/"

    suspend fun pendingCalls(): List<ServiceCall> =
        list("scope=pending")

    suspend fun technicianCalls(
        technicianDeviceId: String
    ): List<ServiceCall> =
        list(
            "technician_device_id=${
                encode(technicianDeviceId)
            }"
        )

    suspend fun get(callId: String): ServiceCall =
        parseCall(
            JSONObject(
                execute(
                    method = "GET",
                    path = "api/service-calls/$callId/"
                )
            )
        )

    suspend fun accept(
        callId: String,
        technicianDeviceId: String,
        technicianName: String
    ): ServiceCall = action(
        callId = callId,
        action = "accept",
        body = JSONObject()
            .put(
                "technician_device_id",
                technicianDeviceId
            )
            .put("technician_name", technicianName)
    )

    suspend fun depart(
        callId: String,
        technicianDeviceId: String
    ): ServiceCall = technicianAction(
        callId,
        "depart",
        technicianDeviceId
    )

    suspend fun arrive(
        callId: String,
        technicianDeviceId: String
    ): ServiceCall = technicianAction(
        callId,
        "arrive",
        technicianDeviceId
    )

    suspend fun sendLocation(
        callId: String,
        technicianDeviceId: String,
        latitude: Double,
        longitude: Double,
        accuracyMeters: Double?,
        speedMps: Double?,
        heading: Double?
    ): ServiceCall {
        val body = JSONObject()
            .put(
                "technician_device_id",
                technicianDeviceId
            )
            .put("latitude", latitude)
            .put("longitude", longitude)

        accuracyMeters?.let {
            body.put("accuracy_meters", it)
        }
        speedMps?.let {
            body.put("speed_mps", it)
        }
        heading?.let {
            body.put("heading", it)
        }

        return action(
            callId = callId,
            action = "location",
            body = body
        )
    }

    suspend fun complete(
        callId: String,
        technicianDeviceId: String,
        request: CompleteServiceCallRequest
    ): ServiceCall {
        val body = JSONObject()
            .put(
                "technician_device_id",
                technicianDeviceId
            )
            .put("result_type", request.resultType)
            .put("diagnosis", request.diagnosis)
            .put("action_taken", request.actionTaken)
            .put("parts_used", request.partsUsed)
            .put("customer_note", request.customerNote)
            .put(
                "follow_up_required",
                request.followUpRequired
            )

        return action(
            callId = callId,
            action = "complete",
            body = body
        )
    }

    private suspend fun technicianAction(
        callId: String,
        action: String,
        technicianDeviceId: String
    ): ServiceCall = action(
        callId = callId,
        action = action,
        body = JSONObject().put(
            "technician_device_id",
            technicianDeviceId
        )
    )

    private suspend fun action(
        callId: String,
        action: String,
        body: JSONObject
    ): ServiceCall = parseCall(
        JSONObject(
            execute(
                method = "POST",
                path =
                    "api/service-calls/$callId/$action/",
                body = body
            )
        )
    )

    private suspend fun list(
        query: String
    ): List<ServiceCall> {
        val response = execute(
            method = "GET",
            path = "api/service-calls/?$query"
        )
        val parsed = JSONTokener(response).nextValue()
        val array = when (parsed) {
            is JSONArray -> parsed
            is JSONObject ->
                parsed.optJSONArray("results")
                    ?: JSONArray()
            else -> JSONArray()
        }

        return buildList {
            for (index in 0 until array.length()) {
                add(
                    parseCall(
                        array.getJSONObject(index)
                    )
                )
            }
        }
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

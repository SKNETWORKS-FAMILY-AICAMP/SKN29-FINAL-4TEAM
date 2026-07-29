package com.skn29.watercare.data.dispatch

enum class ServiceCallStatus(
    val label: String
) {
    REQUESTED("방문기사 수락 대기"),
    ACCEPTED("방문기사 수락"),
    EN_ROUTE("방문기사 이동 중"),
    ARRIVED("방문기사 도착"),
    COMPLETED("처리 완료"),
    CANCELLED("요청 취소");

    companion object {
        fun from(raw: String): ServiceCallStatus =
            entries.firstOrNull { it.name == raw }
                ?: REQUESTED
    }
}

data class ServiceCall(
    val id: String,
    val customerDeviceId: String,
    val customerName: String,
    val customerPhone: String,
    val customerAddress: String,
    val customerLatitude: Double,
    val customerLongitude: Double,
    val productName: String,
    val productModel: String,
    val symptom: String,
    val status: ServiceCallStatus,
    val technicianDeviceId: String?,
    val technicianName: String?,
    val technicianLatitude: Double?,
    val technicianLongitude: Double?,
    val technicianAccuracyMeters: Double?,
    val technicianSpeedMps: Double?,
    val technicianHeading: Double?,
    val trackingConnectionState: String,
    val locationAgeSeconds: Int?,
    val distanceMeters: Int?,
    val etaMinutes: Int?,
    val resultType: String?,
    val diagnosis: String,
    val actionTaken: String,
    val partsUsed: String,
    val customerNote: String,
    val followUpRequired: Boolean
)

data class CreateServiceCallRequest(
    val customerDeviceId: String,
    val customerName: String,
    val customerPhone: String,
    val customerAddress: String,
    val customerLatitude: Double,
    val customerLongitude: Double,
    val productName: String,
    val productModel: String,
    val symptom: String
)

data class DrivingRoute(
    val distanceMeters: Int,
    val durationSeconds: Int,
    val points: List<RoutePoint>
)

data class RoutePoint(
    val latitude: Double,
    val longitude: Double
)

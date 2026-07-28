package com.skn29.watercare.model

enum class InquiryEntryMode {
    QR_SCAN,
    QUESTIONNAIRE
}

enum class InquiryState {
    DRAFT,
    QUESTIONNAIRE_IN_PROGRESS,
    ERROR_CONFIRMED,
    VISIT_REVIEW_PENDING,
    VISIT_SCHEDULED,
    COMPLETION_PENDING,
    RESOLVED,
    CANCELLED
}

enum class VisitScheduleStatus {
    ASSIGNING,
    CONFIRMED,
    EN_ROUTE,
    NEARBY,
    ARRIVED,
    IN_PROGRESS,
    COMPLETED,
    CANCELLED
}

enum class TravelMode {
    WAITING,
    DRIVING,
    WALKING,
    ARRIVED
}

/**
 * 고객 앱과 기사 앱 사이의 위치 연결 상태.
 */
enum class TrackingConnectionState {
    CONNECTING,
    LIVE,
    STALE,
    OFFLINE
}

/**
 * GPS 정확도에 따른 신호 상태.
 */
enum class LocationSignalStatus {
    EXCELLENT,
    GOOD,
    WEAK,
    REJECTED
}

data class ErrorDetectionResult(
    val entryMode: InquiryEntryMode = InquiryEntryMode.QR_SCAN,
    val productCode: String = "WPUJAC104DWH",
    val errorCode: String? = null,
    val errorName: String = "확인 전",
    val symptomSummary: String = "",
    val requiresVisit: Boolean = false,
    val sourceRawValue: String? = null
)

data class InquiryDraft(
    val inquiryId: String = "DEMO-INQ-002",
    val state: InquiryState = InquiryState.DRAFT,
    val detection: ErrorDetectionResult = ErrorDetectionResult()
)

data class GeoPoint(
    val latitude: Double,
    val longitude: Double
)

data class TrackingSnapshot(
    val visitId: String = "DEMO-VISIT-001",
    val technicianName: String = "김정수 기사",
    val technicianPhoneMasked: String = "010-****-2731",
    val vehicleNumberMasked: String = "12가 ****",
    val status: VisitScheduleStatus = VisitScheduleStatus.CONFIRMED,
    val travelMode: TravelMode = TravelMode.WAITING,
    val technicianLocation: GeoPoint = GeoPoint(37.55860, 126.98600),
    val customerLocation: GeoPoint = GeoPoint(37.56650, 126.97800),
    val remainingDistanceMeters: Int = 3200,
    val etaMinutes: Int = 12,
    val lastUpdatedLabel: String = "출발 전",
    val lastUpdatedEpochMillis: Long = 0L,
    val staleSeconds: Int = 0,
    val callAccepted: Boolean = false,
    val isLive: Boolean = false,
    val connectionState: TrackingConnectionState = TrackingConnectionState.CONNECTING,
    val locationSignalStatus: LocationSignalStatus = LocationSignalStatus.GOOD,
    val routeProgress: Float = 0f,
    val speedKph: Int = 0,
    val headingDegrees: Double = 0.0,
    val locationAccuracyMeters: Int = 0,
    val routeDeviationMeters: Int = 0,
    val routeRecalculating: Boolean = false,
    val locationRejectedReason: String? = null
)

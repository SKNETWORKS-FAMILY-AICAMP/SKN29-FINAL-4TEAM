package com.skn29.watercare.model

enum class InquiryEntryMode {
    QR_SCAN,
    QUESTIONNAIRE
}

/**
 * 문의 업무 상태.
 * contracts/state-machine/inquiry-states.yaml 의 13개 코드와 1:1로 일치한다.
 * 서버 응답 역직렬화에 그대로 쓰이므로 임의로 추가·변경하지 않는다.
 */
enum class InquiryState {
    DRAFT,
    QUESTIONNAIRE_IN_PROGRESS,
    AI_GUIDANCE,
    CONSULTATION_REQUIRED,
    CONSULTATION_IN_PROGRESS,
    VISIT_REVIEW_PENDING,
    VISIT_SCHEDULING,
    VISIT_SCHEDULED,
    COMPLETION_PENDING,
    REVISIT_REQUIRED,
    REOPENED,
    RESOLVED,
    CANCELLED
}

/**
 * 방문 진행 상태.
 * ASSIGNING·SCHEDULING·CONFIRMED·IN_PROGRESS·COMPLETED·FOLLOW_UP_REQUIRED·CANCELLED 는
 * contracts/state-machine/inquiry-states.yaml 의 visit_status_codes 와 동일하다.
 * EN_ROUTE·NEARBY·ARRIVED 는 계약 코드가 아닌 앱 내부 이동 표시용 하위 상태이며,
 * 서버 전송 시 toContractCode() 로 계약 코드에 매핑한다.
 */
enum class VisitScheduleStatus {
    ASSIGNING,
    SCHEDULING,
    CONFIRMED,
    EN_ROUTE,
    NEARBY,
    ARRIVED,
    IN_PROGRESS,
    COMPLETED,
    FOLLOW_UP_REQUIRED,
    CANCELLED;

    /** 앱 내부 이동 추적 상태를 계약 visit_status_codes 값으로 변환한다. */
    fun toContractCode(): String = when (this) {
        EN_ROUTE, NEARBY, ARRIVED -> CONFIRMED.name
        else -> name
    }
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

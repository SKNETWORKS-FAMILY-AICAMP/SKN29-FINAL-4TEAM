package com.skn29.watercare.tracking

import android.util.Log
import com.skn29.watercare.model.GeoPoint
import com.skn29.watercare.model.LocationSignalStatus
import com.skn29.watercare.model.TrackingConnectionState
import com.skn29.watercare.model.TrackingSnapshot
import com.skn29.watercare.model.TravelMode
import com.skn29.watercare.model.VisitScheduleStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

object TrackingRepository {
    private const val ROUTE_LOG_TAG = "VISIT_ROUTE"
    private const val ANIMATION_POINT_COUNT = 300
    private const val MAX_ROAD_SNAP_DISTANCE_METERS = 45.0
    private const val WALKING_SWITCH_DISTANCE_METERS = 220
    private const val MAX_ACCEPTABLE_ACCURACY_METERS = 80f
    private const val ROUTE_DEVIATION_RECALCULATE_METERS = 70.0
    private const val ROUTE_RECALCULATE_COOLDOWN_MILLIS = 30_000L
    private const val STALE_AFTER_MILLIS = 15_000L
    private const val OFFLINE_AFTER_MILLIS = 60_000L

    private val customer = GeoPoint(37.56650, 126.97800)

    /**
     * 길찾기 API를 사용할 수 없을 때도 건물을 가로지르지 않고
     * 큰 도로를 따라 꺾여 이동하도록 만든 발표용 예비 경로.
     */
    private val fallbackRoadRoute = listOf(
        GeoPoint(37.55860, 126.98600),
        GeoPoint(37.55886, 126.98590),
        GeoPoint(37.55910, 126.98555),
        GeoPoint(37.55930, 126.98505),
        GeoPoint(37.55939, 126.98442),
        GeoPoint(37.55947, 126.98370),
        GeoPoint(37.55953, 126.98295),
        GeoPoint(37.55958, 126.98218),
        GeoPoint(37.55964, 126.98142),
        GeoPoint(37.55970, 126.98068),
        GeoPoint(37.55977, 126.97992),
        GeoPoint(37.55985, 126.97920),
        GeoPoint(37.55996, 126.97858),
        GeoPoint(37.56030, 126.97818),
        GeoPoint(37.56086, 126.97812),
        GeoPoint(37.56144, 126.97810),
        GeoPoint(37.56204, 126.97809),
        GeoPoint(37.56267, 126.97808),
        GeoPoint(37.56331, 126.97807),
        GeoPoint(37.56396, 126.97806),
        GeoPoint(37.56460, 126.97805),
        GeoPoint(37.56522, 126.97804),
        GeoPoint(37.56578, 126.97803),
        customer
    )

    private val defaultStart = fallbackRoadRoute.first()

    /*
     * 실제 카카오 도로 경로가 로딩되기 전에는 예비 좌표를 지도에 그리지 않는다.
     * 예비 좌표를 경로처럼 사용하면 건물 위를 가로지르는 현상이 발생할 수 있다.
     */
    private val _route = MutableStateFlow<List<GeoPoint>>(emptyList())
    val route: StateFlow<List<GeoPoint>> = _route.asStateFlow()

    private var animationRoute = listOf(defaultStart)
    private var verifiedRoadRouteLoaded = false
    private var routeIndex = 0
    private var routeDistanceMeters = 0
    private var routeDurationSeconds = 0
    private var lastAcceptedPoint = defaultStart
    private var lastAcceptedAtMillis = 0L
    private var lastRouteRecalculationAtMillis = 0L
    private val rerouteMutex = Mutex()

    private val _snapshot = MutableStateFlow(
        TrackingSnapshot(
            technicianLocation = defaultStart,
            customerLocation = customer,
            remainingDistanceMeters = 0,
            etaMinutes = 0
        )
    )
    val snapshot: StateFlow<TrackingSnapshot> = _snapshot.asStateFlow()

    /** REST API 키는 Android가 아니라 Django 백엔드에서만 사용한다. */
    suspend fun loadRoadRoute(
        origin: GeoPoint = _snapshot.value.technicianLocation
    ): Boolean {
        _snapshot.value = _snapshot.value.copy(
            connectionState =
                TrackingConnectionState.CONNECTING,
            isLive = false,
            locationRejectedReason = null
        )

        val result = KakaoDirectionsClient.fetchDrivingRoute(
            origin = origin,
            destination = customer
        )

        return result.fold(
            onSuccess = { routeResult ->
                applyRoute(
                    points = routeResult.points,
                    distanceMeters = routeResult.distanceMeters,
                    durationSeconds = routeResult.durationSeconds
                )
                verifiedRoadRouteLoaded = true
                _snapshot.value = _snapshot.value.copy(
                    locationRejectedReason = null
                )
                Log.i(
                    ROUTE_LOG_TAG,
                    "백엔드 카카오 도로 경로 적용: ${routeResult.points.size} points"
                )
                true
            },
            onFailure = { error ->
                verifiedRoadRouteLoaded = false
                _route.value = emptyList()
                animationRoute = listOf(origin)
                routeIndex = 0
                routeDistanceMeters = 0
                routeDurationSeconds = 0

                _snapshot.value = _snapshot.value.copy(
                    technicianLocation = origin,
                    remainingDistanceMeters = 0,
                    etaMinutes = 0,
                    isLive = false,
                    connectionState = TrackingConnectionState.OFFLINE,
                    locationRejectedReason = buildString {
                        append("경로 조회 실패")

                        error.message
                            ?.takeIf { it.isNotBlank() }
                            ?.let { message ->
                                append(": ")
                                append(message)
                            }
                    }
                )

                Log.e(
                    ROUTE_LOG_TAG,
                    "카카오 도로 경로 조회 실패. 건물 관통 방지를 위해 이동을 중지합니다.",
                    error
                )
                false
            }
        )
    }

    fun prepareVisit() {
        routeIndex = 0
        val startPoint = animationRoute.firstOrNull() ?: defaultStart
        lastAcceptedPoint = startPoint
        lastAcceptedAtMillis = 0L

        _snapshot.value = TrackingSnapshot(
            status = VisitScheduleStatus.CONFIRMED,
            travelMode = TravelMode.WAITING,
            technicianLocation = startPoint,
            customerLocation = customer,
            remainingDistanceMeters = routeDistanceMeters,
            etaMinutes = secondsToMinutes(routeDurationSeconds),
            lastUpdatedLabel = "기사 배정 완료",
            callAccepted = false,
            isLive = false,
            connectionState = TrackingConnectionState.CONNECTING,
            routeProgress = 0f
        )
    }

    fun acceptCall() {
        _snapshot.value = _snapshot.value.copy(
            status = VisitScheduleStatus.CONFIRMED,
            travelMode = TravelMode.WAITING,
            callAccepted = true,
            isLive = false,
            connectionState =
                TrackingConnectionState.CONNECTING,
            lastUpdatedLabel =
                "기사님이 콜을 수락했습니다",
            locationRejectedReason = null
        )
    }

    /**
     * 방문기사가 현장 도착 버튼을 누른다.
     */
    fun markArrived() {
        if (!_snapshot.value.callAccepted) {
            return
        }

        _snapshot.value =
            _snapshot.value.copy(
                status =
                    VisitScheduleStatus.ARRIVED,
                travelMode =
                    TravelMode.ARRIVED,
                remainingDistanceMeters = 0,
                etaMinutes = 0,
                lastUpdatedLabel =
                    "기사님이 현장에 도착했습니다",
                isLive = false,
                connectionState =
                    TrackingConnectionState.LIVE,
                routeProgress = 1f,
                speedKph = 0,
                locationRejectedReason = null
            )
    }

    /**
     * 방문기사가 고객 확인 후 점검을 시작한다.
     */
    fun startInspection() {
        if (
            _snapshot.value.status !=
            VisitScheduleStatus.ARRIVED
        ) {
            return
        }

        _snapshot.value =
            _snapshot.value.copy(
                status =
                    VisitScheduleStatus
                        .IN_PROGRESS,
                travelMode =
                    TravelMode.ARRIVED,
                lastUpdatedLabel =
                    "현장 점검을 시작했습니다",
                isLive = false,
                speedKph = 0,
                locationRejectedReason = null
            )
    }

    /**
     * 기사 작업 보고 저장 후 방문 업무를 완료한다.
     */
    fun completeVisit() {
        if (
            _snapshot.value.status !=
            VisitScheduleStatus
                .IN_PROGRESS
        ) {
            return
        }

        _snapshot.value =
            _snapshot.value.copy(
                status =
                    VisitScheduleStatus
                        .COMPLETED,
                travelMode =
                    TravelMode.ARRIVED,
                remainingDistanceMeters = 0,
                etaMinutes = 0,
                lastUpdatedLabel =
                    "방문 작업이 완료되었습니다",
                isLive = false,
                routeProgress = 1f,
                speedKph = 0,
                locationRejectedReason = null
            )
    }

    /**
     * 경로 재시도 버튼을 눌렀을 때 이전 오류 표시를 제거한다.
     */
    fun beginRouteRetry() {
        _snapshot.value = _snapshot.value.copy(
            connectionState =
                TrackingConnectionState.CONNECTING,
            isLive = false,
            routeRecalculating = false,
            locationRejectedReason = null,
            lastUpdatedLabel =
                "도로 경로를 다시 확인하고 있습니다"
        )
    }

    fun startDemoTracking(): Boolean {
        if (
            !verifiedRoadRouteLoaded ||
            animationRoute.size < 2
        ) {
            rejectLocation(
                reason = "실제 도로 경로가 없어 차량 이동을 시작하지 않았습니다.",
                accuracyMeters = 0
            )
            return false
        }

        if (!_snapshot.value.callAccepted) {
            _snapshot.value =
                _snapshot.value.copy(
                    locationRejectedReason =
                        "방문기사 앱에서 콜을 수락한 뒤 출발해 주세요.",
                    lastUpdatedLabel =
                        "기사 콜 수락 대기"
                )
            return false
        }

        routeIndex = 0
        applyAnimationPoint(routeIndex)
        return true
    }

    /** 다음 시연 위치가 있으면 true, 마지막 좌표라면 false를 반환한다. */
    fun advanceDemoTracking(): Boolean {
        if (
            !verifiedRoadRouteLoaded ||
            animationRoute.size < 2 ||
            routeIndex >= animationRoute.lastIndex
        ) {
            return false
        }

        routeIndex += 1
        applyAnimationPoint(routeIndex)
        return routeIndex < animationRoute.lastIndex
    }

    /**
     * 기사 단말의 실제 GPS 위치를 적용한다.
     *
     * - 정확도가 지나치게 낮은 좌표 제외
     * - 짧은 시간 동안 비정상적으로 멀리 이동한 좌표 제외
     * - GPS 떨림을 줄이기 위한 좌표 평활화
     * - 예정 경로에서 벗어나면 일정 간격으로 경로 재탐색
     */
    suspend fun updateLiveLocation(
        point: GeoPoint,
        speedMps: Float?,
        headingDegrees: Double?,
        accuracyMeters: Float?,
        recordedAtMillis: Long = System.currentTimeMillis()
    ): Boolean {
        if (!verifiedRoadRouteLoaded || animationRoute.size < 2) {
            val loaded = loadRoadRoute(origin = point)
            if (!loaded) return false
        }

        val accuracy = accuracyMeters ?: 0f

        if (accuracy > MAX_ACCEPTABLE_ACCURACY_METERS) {
            rejectLocation(
                reason = "GPS 정확도가 낮아 위치 반영을 보류했습니다.",
                accuracyMeters = accuracy.roundToInt()
            )
            return false
        }

        if (lastAcceptedAtMillis > 0L) {
            val elapsedSeconds = max(
                1.0,
                (recordedAtMillis - lastAcceptedAtMillis).toDouble() / 1_000.0
            )
            val jumpDistance = distanceMeters(lastAcceptedPoint, point)
            val maximumPlausibleDistance = max(180.0, elapsedSeconds * 55.0)

            if (jumpDistance > maximumPlausibleDistance) {
                rejectLocation(
                    reason = "비정상적인 GPS 위치 이동을 감지했습니다.",
                    accuracyMeters = accuracy.roundToInt()
                )
                return false
            }
        }

        val smoothedPoint = if (lastAcceptedAtMillis == 0L) {
            point
        } else {
            smoothPoint(
                previous = lastAcceptedPoint,
                current = point,
                accuracyMeters = accuracy
            )
        }

        val roadMatch = matchPointToRoad(
            points = animationRoute,
            rawPoint = smoothedPoint
        )

        val resolvedSpeedKph = ((speedMps ?: 0f) * 3.6f)
            .roundToInt()
            .coerceAtLeast(0)

        /*
         * GPS가 예정 도로와 가까울 때만 도로 중심선으로 스냅해서 표시한다.
         * 경로에서 멀리 벗어난 좌표는 건물 위로 이동시키지 않고,
         * 마지막 정상 도로 위치에 멈춘 뒤 새 경로를 요청한다.
         */
        if (roadMatch.deviationMeters <= MAX_ROAD_SNAP_DISTANCE_METERS) {
            routeIndex = roadMatch.routeIndex

            applyTrackingPoint(
                index = roadMatch.routeIndex,
                point = roadMatch.snappedPoint,
                headingDegrees = roadMatch.headingDegrees,
                speedKph = resolvedSpeedKph,
                accuracyMeters = accuracy.roundToInt().coerceAtLeast(0),
                deviationMeters =
                    roadMatch.deviationMeters.roundToInt().coerceAtLeast(0),
                sourceIsLive = true,
                updatedAtMillis = recordedAtMillis
            )
        } else {
            _snapshot.value = _snapshot.value.copy(
                speedKph = 0,
                routeDeviationMeters =
                    roadMatch.deviationMeters.roundToInt().coerceAtLeast(0),
                locationRejectedReason =
                    "기사 위치가 예정 도로에서 벗어나 새 경로를 계산하고 있습니다."
            )
        }

        lastAcceptedPoint = smoothedPoint
        lastAcceptedAtMillis = recordedAtMillis

        if (
            roadMatch.deviationMeters >=
                ROUTE_DEVIATION_RECALCULATE_METERS &&
            recordedAtMillis - lastRouteRecalculationAtMillis >=
                ROUTE_RECALCULATE_COOLDOWN_MILLIS
        ) {
            recalculateRouteFrom(smoothedPoint, recordedAtMillis)
        }

        return true
    }

    /**
     * 고객 앱이 1초 간격으로 호출하면 최근 위치가 오래됐는지 자동 판정한다.
     */
    fun refreshTrackingHealth(
        nowMillis: Long = System.currentTimeMillis()
    ) {
        val current = _snapshot.value
        if (
            current.lastUpdatedEpochMillis <= 0L ||
            current.status == VisitScheduleStatus.ARRIVED
        ) {
            return
        }

        val ageMillis =
            (nowMillis - current.lastUpdatedEpochMillis).coerceAtLeast(0L)
        val ageSeconds = (ageMillis / 1_000L).toInt()

        val connectionState = when {
            ageMillis >= OFFLINE_AFTER_MILLIS ->
                TrackingConnectionState.OFFLINE
            ageMillis >= STALE_AFTER_MILLIS ->
                TrackingConnectionState.STALE
            else -> TrackingConnectionState.LIVE
        }

        _snapshot.value = current.copy(
            staleSeconds = ageSeconds,
            connectionState = connectionState,
            isLive = connectionState == TrackingConnectionState.LIVE
        )
    }

    fun markConnectionOffline() {
        _snapshot.value = _snapshot.value.copy(
            isLive = false,
            connectionState = TrackingConnectionState.OFFLINE
        )
    }

    fun nextDemoDelayMillis(): Long = when (_snapshot.value.travelMode) {
        TravelMode.WALKING -> 680L
        TravelMode.ARRIVED -> 1_000L
        TravelMode.DRIVING -> 460L
        TravelMode.WAITING -> 850L
    }

    private suspend fun recalculateRouteFrom(
        origin: GeoPoint,
        requestedAtMillis: Long
    ) {
        rerouteMutex.withLock {
            if (
                requestedAtMillis - lastRouteRecalculationAtMillis <
                ROUTE_RECALCULATE_COOLDOWN_MILLIS
            ) {
                return
            }

            lastRouteRecalculationAtMillis = requestedAtMillis
            _snapshot.value = _snapshot.value.copy(
                routeRecalculating = true
            )

            try {
                val result = KakaoDirectionsClient.fetchDrivingRoute(
                    origin = origin,
                    destination = customer
                )

                result.onSuccess { routeResult ->
                    applyRoute(
                        points = routeResult.points,
                        distanceMeters = routeResult.distanceMeters,
                        durationSeconds = routeResult.durationSeconds
                    )
                    verifiedRoadRouteLoaded = true

                    val roadMatch = matchPointToRoad(
                        points = animationRoute,
                        rawPoint = origin
                    )

                    routeIndex = roadMatch.routeIndex
                    lastAcceptedPoint = origin

                    applyTrackingPoint(
                        index = roadMatch.routeIndex,
                        point = roadMatch.snappedPoint,
                        headingDegrees = roadMatch.headingDegrees,
                        speedKph = _snapshot.value.speedKph,
                        accuracyMeters = _snapshot.value.locationAccuracyMeters,
                        deviationMeters =
                            roadMatch.deviationMeters.roundToInt(),
                        sourceIsLive = true,
                        updatedAtMillis = requestedAtMillis
                    )
                }.onFailure { error ->
                    Log.e(
                        ROUTE_LOG_TAG,
                        "경로 이탈 후 재탐색에 실패했습니다.",
                        error
                    )
                }
            } finally {
                _snapshot.value = _snapshot.value.copy(
                    routeRecalculating = false
                )
            }
        }
    }

    private fun rejectLocation(
        reason: String,
        accuracyMeters: Int
    ) {
        _snapshot.value = _snapshot.value.copy(
            locationSignalStatus = LocationSignalStatus.REJECTED,
            locationAccuracyMeters = accuracyMeters,
            locationRejectedReason = reason
        )
        Log.w(ROUTE_LOG_TAG, reason)
    }

    private fun applyRoute(
        points: List<GeoPoint>,
        distanceMeters: Int,
        durationSeconds: Int
    ) {
        val sanitized = points
            .fold(mutableListOf<GeoPoint>()) { output, point ->
                if (output.lastOrNull() != point) output.add(point)
                output
            }

        require(sanitized.size >= 2) {
            "실제 도로 경로 좌표가 부족합니다."
        }

        _route.value = sanitized
        verifiedRoadRouteLoaded = true
        animationRoute = resampleRoute(
            sanitized,
            ANIMATION_POINT_COUNT
        )
        routeDistanceMeters = distanceMeters
            .takeIf { it > 0 }
            ?: routeLengthMeters(animationRoute).toInt()
        routeDurationSeconds =
            durationSeconds.takeIf { it > 0 } ?: 12 * 60
        routeIndex = 0
    }

    private fun applyAnimationPoint(index: Int) {
        val current = animationRoute[index]
        val previous = animationRoute.getOrElse(
            (index - 1).coerceAtLeast(0)
        ) {
            current
        }
        val next = animationRoute.getOrElse(
            (index + 1).coerceAtMost(animationRoute.lastIndex)
        ) {
            current
        }

        val heading = if (index == 0) {
            bearingDegrees(current, next)
        } else {
            bearingDegrees(previous, current)
        }

        val lastIndex = animationRoute.lastIndex.coerceAtLeast(1)
        val progress = index.toDouble() / lastIndex.toDouble()
        val remainingDistance =
            (routeDistanceMeters * (1.0 - progress))
                .toInt()
                .coerceAtLeast(0)

        val speedKph = when {
            index >= animationRoute.lastIndex -> 0
            remainingDistance <= WALKING_SWITCH_DISTANCE_METERS -> 4
            else -> (24 + 12 * sin(progress * Math.PI))
                .roundToInt()
        }

        applyTrackingPoint(
            index = index,
            point = current,
            headingDegrees = heading,
            speedKph = speedKph,
            accuracyMeters =
                if (remainingDistance <= WALKING_SWITCH_DISTANCE_METERS) 8 else 5,
            deviationMeters = 0,
            sourceIsLive = true,
            updatedAtMillis = System.currentTimeMillis()
        )

        lastAcceptedPoint = current
        lastAcceptedAtMillis = _snapshot.value.lastUpdatedEpochMillis
    }

    private fun applyTrackingPoint(
        index: Int,
        point: GeoPoint,
        headingDegrees: Double,
        speedKph: Int,
        accuracyMeters: Int,
        deviationMeters: Int,
        sourceIsLive: Boolean,
        updatedAtMillis: Long
    ) {
        val lastIndex = animationRoute.lastIndex.coerceAtLeast(1)
        val progress = index.toDouble() / lastIndex.toDouble()
        val remainingDistance =
            (routeDistanceMeters * (1.0 - progress))
                .toInt()
                .coerceAtLeast(0)
        val remainingDuration =
            (routeDurationSeconds * (1.0 - progress))
                .toInt()
                .coerceAtLeast(0)

        val travelMode = when {
            index >= animationRoute.lastIndex -> TravelMode.ARRIVED
            remainingDistance <= WALKING_SWITCH_DISTANCE_METERS ->
                TravelMode.WALKING
            else -> TravelMode.DRIVING
        }

        val status = when (travelMode) {
            TravelMode.ARRIVED -> VisitScheduleStatus.ARRIVED
            TravelMode.WALKING -> VisitScheduleStatus.NEARBY
            TravelMode.DRIVING -> VisitScheduleStatus.EN_ROUTE
            TravelMode.WAITING -> VisitScheduleStatus.CONFIRMED
        }

        _snapshot.value = _snapshot.value.copy(
            status = status,
            travelMode = travelMode,
            technicianLocation = point,
            customerLocation = customer,
            remainingDistanceMeters = remainingDistance,
            etaMinutes = secondsToMinutes(remainingDuration),
            lastUpdatedLabel = nowLabel(),
            lastUpdatedEpochMillis = updatedAtMillis,
            staleSeconds = 0,
            callAccepted = true,
            isLive =
                sourceIsLive && travelMode != TravelMode.ARRIVED,
            connectionState = when {
                travelMode == TravelMode.ARRIVED ->
                    TrackingConnectionState.LIVE
                sourceIsLive -> TrackingConnectionState.LIVE
                else -> TrackingConnectionState.CONNECTING
            },
            locationSignalStatus =
                signalStatusForAccuracy(accuracyMeters),
            routeProgress = progress
                .toFloat()
                .coerceIn(0f, 1f),
            speedKph = speedKph,
            headingDegrees = normalizeHeading(headingDegrees),
            locationAccuracyMeters = accuracyMeters,
            routeDeviationMeters = deviationMeters,
            locationRejectedReason = null
        )
    }

    private fun signalStatusForAccuracy(
        accuracyMeters: Int
    ): LocationSignalStatus = when {
        accuracyMeters <= 0 -> LocationSignalStatus.GOOD
        accuracyMeters <= 10 -> LocationSignalStatus.EXCELLENT
        accuracyMeters <= 30 -> LocationSignalStatus.GOOD
        accuracyMeters <= MAX_ACCEPTABLE_ACCURACY_METERS ->
            LocationSignalStatus.WEAK
        else -> LocationSignalStatus.REJECTED
    }

    private fun smoothPoint(
        previous: GeoPoint,
        current: GeoPoint,
        accuracyMeters: Float
    ): GeoPoint {
        val alpha = when {
            accuracyMeters <= 10f -> 0.78
            accuracyMeters <= 25f -> 0.58
            else -> 0.38
        }

        return GeoPoint(
            latitude =
                previous.latitude +
                    (current.latitude - previous.latitude) * alpha,
            longitude =
                previous.longitude +
                    (current.longitude - previous.longitude) * alpha
        )
    }

    private data class RoadMatch(
        val routeIndex: Int,
        val snappedPoint: GeoPoint,
        val deviationMeters: Double,
        val headingDegrees: Double
    )

    /**
     * GPS 좌표를 가장 가까운 도로 선분 위로 투영한다.
     * 단순히 가장 가까운 꼭짓점만 찾는 방식보다 커브와 교차로에서 자연스럽다.
     */
    private fun matchPointToRoad(
        points: List<GeoPoint>,
        rawPoint: GeoPoint
    ): RoadMatch {
        require(points.size >= 2) {
            "도로 매칭에는 두 개 이상의 좌표가 필요합니다."
        }

        val referenceLatitudeRadians =
            Math.toRadians(rawPoint.latitude)
        val metersPerLatitudeDegree = 111_320.0
        val metersPerLongitudeDegree =
            111_320.0 * cos(referenceLatitudeRadians)

        var bestSegmentIndex = 0
        var bestPoint = points.first()
        var bestDistance = Double.MAX_VALUE

        for (index in 0 until points.lastIndex) {
            val start = points[index]
            val end = points[index + 1]

            val startX =
                (start.longitude - rawPoint.longitude) *
                    metersPerLongitudeDegree
            val startY =
                (start.latitude - rawPoint.latitude) *
                    metersPerLatitudeDegree
            val endX =
                (end.longitude - rawPoint.longitude) *
                    metersPerLongitudeDegree
            val endY =
                (end.latitude - rawPoint.latitude) *
                    metersPerLatitudeDegree

            val segmentX = endX - startX
            val segmentY = endY - startY
            val segmentLengthSquared =
                segmentX * segmentX + segmentY * segmentY

            val projection = if (segmentLengthSquared <= 0.0001) {
                0.0
            } else {
                (
                    -(startX * segmentX + startY * segmentY) /
                        segmentLengthSquared
                    ).coerceIn(0.0, 1.0)
            }

            val projectedX = startX + segmentX * projection
            val projectedY = startY + segmentY * projection
            val projectedDistance =
                sqrt(
                    projectedX * projectedX +
                        projectedY * projectedY
                )

            if (projectedDistance < bestDistance) {
                bestDistance = projectedDistance
                bestSegmentIndex = index
                bestPoint = GeoPoint(
                    latitude =
                        start.latitude +
                            (end.latitude - start.latitude) *
                            projection,
                    longitude =
                        start.longitude +
                            (end.longitude - start.longitude) *
                            projection
                )
            }
        }

        val segmentStart = points[bestSegmentIndex]
        val segmentEnd = points[
            (bestSegmentIndex + 1).coerceAtMost(points.lastIndex)
        ]

        return RoadMatch(
            routeIndex =
                (bestSegmentIndex + 1).coerceAtMost(points.lastIndex),
            snappedPoint = bestPoint,
            deviationMeters = bestDistance,
            headingDegrees =
                bearingDegrees(segmentStart, segmentEnd)
        )
    }

    private fun secondsToMinutes(seconds: Int): Int =
        if (seconds <= 0) 0
        else ceil(seconds / 60.0).toInt()

    private fun resampleRoute(
        points: List<GeoPoint>,
        targetCount: Int
    ): List<GeoPoint> {
        if (points.size < 2 || targetCount <= 2) return points

        val segmentLengths = points.zipWithNext(::distanceMeters)
        val totalLength = segmentLengths.sum()
        if (totalLength <= 0.0) return points

        val result = ArrayList<GeoPoint>(targetCount)
        var segmentIndex = 0
        var segmentStartDistance = 0.0

        for (sampleIndex in 0 until targetCount) {
            val targetDistance =
                totalLength *
                    sampleIndex.toDouble() /
                    (targetCount - 1).toDouble()

            while (
                segmentIndex < segmentLengths.lastIndex &&
                segmentStartDistance +
                    segmentLengths[segmentIndex] <
                    targetDistance
            ) {
                segmentStartDistance += segmentLengths[segmentIndex]
                segmentIndex += 1
            }

            val segmentLength =
                segmentLengths[segmentIndex].coerceAtLeast(0.001)
            val fraction = (
                (targetDistance - segmentStartDistance) /
                    segmentLength
                ).coerceIn(0.0, 1.0)

            val start = points[segmentIndex]
            val end = points[segmentIndex + 1]

            result += GeoPoint(
                latitude =
                    start.latitude +
                        (end.latitude - start.latitude) * fraction,
                longitude =
                    start.longitude +
                        (end.longitude - start.longitude) * fraction
            )
        }

        return result
    }

    private fun routeLengthMeters(
        points: List<GeoPoint>
    ): Double = points.zipWithNext(::distanceMeters).sum()

    private fun distanceMeters(
        start: GeoPoint,
        end: GeoPoint
    ): Double {
        val earthRadius = 6_371_000.0
        val latitudeDelta =
            Math.toRadians(end.latitude - start.latitude)
        val longitudeDelta =
            Math.toRadians(end.longitude - start.longitude)
        val startLatitude = Math.toRadians(start.latitude)
        val endLatitude = Math.toRadians(end.latitude)

        val a =
            sin(latitudeDelta / 2) * sin(latitudeDelta / 2) +
                cos(startLatitude) * cos(endLatitude) *
                sin(longitudeDelta / 2) *
                sin(longitudeDelta / 2)

        val c = 2 * asin(sqrt(a.coerceIn(0.0, 1.0)))
        return earthRadius * c
    }

    private fun bearingDegrees(
        start: GeoPoint,
        end: GeoPoint
    ): Double {
        val startLatitude = Math.toRadians(start.latitude)
        val endLatitude = Math.toRadians(end.latitude)
        val longitudeDelta =
            Math.toRadians(end.longitude - start.longitude)

        val y = sin(longitudeDelta) * cos(endLatitude)
        val x =
            cos(startLatitude) * sin(endLatitude) -
                sin(startLatitude) * cos(endLatitude) *
                cos(longitudeDelta)

        return normalizeHeading(
            Math.toDegrees(atan2(y, x))
        )
    }

    private fun normalizeHeading(
        headingDegrees: Double
    ): Double = (headingDegrees % 360.0 + 360.0) % 360.0

    private fun nowLabel(): String =
        LocalTime.now().format(
            DateTimeFormatter.ofPattern("HH:mm:ss")
        )
}

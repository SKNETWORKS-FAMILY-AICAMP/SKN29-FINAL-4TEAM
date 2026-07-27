package com.skn29.watercare.ui.map

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color as AndroidColor
import androidx.annotation.DrawableRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.kakao.vectormap.KakaoMap
import com.kakao.vectormap.KakaoMapReadyCallback
import com.kakao.vectormap.LatLng
import com.kakao.vectormap.MapLifeCycleCallback
import com.kakao.vectormap.MapView
import com.kakao.vectormap.camera.CameraAnimation
import com.kakao.vectormap.camera.CameraUpdateFactory
import com.kakao.vectormap.label.Label
import com.kakao.vectormap.label.LabelOptions
import com.kakao.vectormap.label.LabelStyle
import com.kakao.vectormap.label.LabelStyles
import com.kakao.vectormap.label.TransformMethod
import com.kakao.vectormap.route.RouteLineOptions
import com.kakao.vectormap.route.RouteLineSegment
import com.kakao.vectormap.route.RouteLineStyle
import com.kakao.vectormap.route.RouteLineStyles
import com.kakao.vectormap.route.RouteLineStylesSet
import com.skn29.watercare.R
import com.skn29.watercare.model.GeoPoint
import com.skn29.watercare.model.TravelMode
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

@Composable
fun KakaoTrackingMap(
    route: List<GeoPoint>,
    technician: GeoPoint,
    customer: GeoPoint,
    travelMode: TravelMode,
    headingDegrees: Double,
    autoFollow: Boolean = true,
    routeRecalculating: Boolean = false,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val mapView = remember { MapView(context) }

    var kakaoMap by remember { mutableStateOf<KakaoMap?>(null) }
    var technicianLabel by remember { mutableStateOf<Label?>(null) }
    var mapError by remember { mutableStateOf<String?>(null) }

    DisposableEffect(mapView) {
        mapView.start(
            object : MapLifeCycleCallback() {
                override fun onMapDestroy() = Unit

                override fun onMapError(error: Exception) {
                    mapError = error.message ?: "카카오맵을 불러오지 못했습니다."
                }
            },
            object : KakaoMapReadyCallback() {
                override fun onMapReady(map: KakaoMap) {
                    kakaoMap = map
                    mapError = null

                    val labelManager = map.labelManager ?: return
                    val labelLayer = labelManager.layer ?: return

                    val technicianStyles = labelManager.addLabelStyles(
                        LabelStyles.from(
                            markerStyle(
                                context = context,
                                travelMode = travelMode
                            )
                        )
                    )
                    val customerStyles = labelManager.addLabelStyles(
                        LabelStyles.from(
                            LabelStyle.from(
                                markerBitmap(
                                    context = context,
                                    drawableRes = R.drawable.ic_marker_customer_map
                                )
                            )
                                .setApplyDpScale(false)
                                .setAnchorPoint(0.5f, 0.9f)
                        )
                    )

                    technicianLabel = labelLayer.addLabel(
                        LabelOptions.from(
                            "technician",
                            LatLng.from(technician.latitude, technician.longitude)
                        )
                            .setStyles(technicianStyles)
                            .setTransform(TransformMethod.AbsoluteRotation)
                    )

                    labelLayer.addLabel(
                        LabelOptions.from(
                            "customer",
                            LatLng.from(customer.latitude, customer.longitude)
                        ).setStyles(customerStyles)
                    )

                    map.moveCamera(
                        CameraUpdateFactory.newCenterPosition(
                            LatLng.from(technician.latitude, technician.longitude),
                            16
                        )
                    )
                }

                override fun getPosition(): LatLng =
                    LatLng.from(technician.latitude, technician.longitude)

                override fun getZoomLevel(): Int = 16
            }
        )

        onDispose {
            mapView.finish()
        }
    }

    DisposableEffect(lifecycleOwner, mapView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> mapView.resume()
                Lifecycle.Event.ON_PAUSE -> mapView.pause()
                else -> Unit
            }
        }

        lifecycleOwner.lifecycle.addObserver(observer)
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            mapView.resume()
        }

        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mapView.pause()
        }
    }

    /** 주행 완료 구간은 회색, 남은 구간은 파란색으로 표시한다. */
    LaunchedEffect(route, technician, kakaoMap) {
        val map = kakaoMap ?: return@LaunchedEffect
        if (route.size < 2) return@LaunchedEffect

        val routeLineManager = map.routeLineManager ?: return@LaunchedEffect
        val routeLineLayer = routeLineManager.layer ?: return@LaunchedEffect
        routeLineLayer.removeAll()

        val nearestIndex = nearestRouteIndex(route, technician)
        val completedRoute = route.take(nearestIndex + 1)
        val remainingRoute = route.drop(nearestIndex)

        if (completedRoute.size >= 2) {
            addRouteLine(
                map = map,
                routeId = "watercare-completed-route",
                points = completedRoute,
                width = 10f,
                lineColor = AndroidColor.rgb(170, 181, 194),
                borderWidth = 0f,
                borderColor = AndroidColor.TRANSPARENT
            )
        }

        if (remainingRoute.size >= 2) {
            addRouteLine(
                map = map,
                routeId = "watercare-remaining-route",
                points = remainingRoute,
                width = 13f,
                lineColor = AndroidColor.rgb(32, 112, 232),
                borderWidth = 4f,
                borderColor = AndroidColor.WHITE
            )
        }
    }

    /** 차량/도보 상태 변경 시 지도 자체를 재생성하지 않고 마커 스타일만 교체한다. */
    LaunchedEffect(travelMode, technicianLabel) {
        technicianLabel?.setStyles(
            markerStyle(
                context = context,
                travelMode = travelMode
            )
        )
        technicianLabel?.invalidate(true)
    }

    /** 차량은 진행 방향으로 회전하고, 카메라는 차량 앞쪽을 살짝 바라본다. */
    LaunchedEffect(technician, headingDegrees, travelMode, kakaoMap, technicianLabel) {
        val position = LatLng.from(technician.latitude, technician.longitude)
        val moveDuration = if (travelMode == TravelMode.WALKING) 760 else 590
        val rotationRadians = Math.toRadians(headingDegrees).toFloat()

        technicianLabel?.rotateTo(rotationRadians, moveDuration)
        technicianLabel?.moveTo(position, moveDuration)

        val cameraPoint = when (travelMode) {
            TravelMode.DRIVING -> offsetPoint(technician, headingDegrees, 55.0)
            TravelMode.WALKING -> offsetPoint(technician, headingDegrees, 24.0)
            TravelMode.ARRIVED -> customer
            TravelMode.WAITING -> technician
        }
        val zoomLevel = when (travelMode) {
            TravelMode.WALKING,
            TravelMode.ARRIVED -> 17
            else -> 16
        }

        if (autoFollow) {
            kakaoMap?.moveCamera(
                CameraUpdateFactory.newCenterPosition(
                    LatLng.from(cameraPoint.latitude, cameraPoint.longitude),
                    zoomLevel
                ),
                CameraAnimation.from(moveDuration, true, true)
            )
        }
    }

    /** 경로가 처음 로딩될 때 전체 경로가 한 번 보이도록 카메라를 맞춘다. */
    LaunchedEffect(route, kakaoMap) {
        val map = kakaoMap ?: return@LaunchedEffect
        if (route.size < 2) return@LaunchedEffect

        val routePoints = route.map { LatLng.from(it.latitude, it.longitude) }
        map.moveCamera(
            CameraUpdateFactory.fitMapPoints(
                routePoints.toTypedArray(),
                110,
                16
            ),
            CameraAnimation.from(500, true, true)
        )
    }

    Box(modifier = modifier) {
        AndroidView(
            factory = { mapView },
            modifier = Modifier.fillMaxSize()
        )

        if (routeRecalculating) {
            Text(
                text = "경로를 다시 계산하고 있어요",
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 64.dp)
                    .background(
                        MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
                        RoundedCornerShape(18.dp)
                    )
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.SemiBold
            )
        }

        mapError?.let { message ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = message,
                    modifier = Modifier
                        .background(
                            MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
                            RoundedCornerShape(18.dp)
                        )
                        .padding(horizontal = 18.dp, vertical = 14.dp),
                    color = MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
    }
}

private fun addRouteLine(
    map: KakaoMap,
    routeId: String,
    points: List<GeoPoint>,
    width: Float,
    lineColor: Int,
    borderWidth: Float,
    borderColor: Int
) {
    val routeLineLayer = map.routeLineManager?.layer ?: return
    val latLngPoints = points.map { LatLng.from(it.latitude, it.longitude) }
    val styleSet = RouteLineStylesSet.from(
        "$routeId-style",
        RouteLineStyles.from(
            RouteLineStyle.from(
                width,
                lineColor,
                borderWidth,
                borderColor
            )
        )
    )
    val segment = RouteLineSegment.from(latLngPoints)
        .setStyles(styleSet.getStyles(0))
    val options = RouteLineOptions.from(routeId, segment)
        .setStylesSet(styleSet)

    routeLineLayer.addRouteLine(options)
}

private fun markerStyle(
    context: Context,
    travelMode: TravelMode
): LabelStyle {
    val markerResource = when (travelMode) {
        TravelMode.DRIVING -> R.drawable.ic_marker_vehicle_map
        TravelMode.WAITING,
        TravelMode.WALKING,
        TravelMode.ARRIVED -> R.drawable.ic_marker_technician_map
    }

    return LabelStyle.from(
        markerBitmap(
            context = context,
            drawableRes = markerResource
        )
    )
        .setApplyDpScale(false)
        .setAnchorPoint(0.5f, 0.78f)
}

private fun markerBitmap(
    context: Context,
    @DrawableRes drawableRes: Int
): Bitmap {
    val decodedBitmap = requireNotNull(
        BitmapFactory.decodeResource(context.resources, drawableRes)
    ) {
        "마커 이미지를 Bitmap으로 변환하지 못했습니다: $drawableRes"
    }

    return if (decodedBitmap.config == Bitmap.Config.ARGB_8888) {
        decodedBitmap
    } else {
        decodedBitmap.copy(Bitmap.Config.ARGB_8888, false)
    }
}

private fun nearestRouteIndex(
    route: List<GeoPoint>,
    point: GeoPoint
): Int = route.indices.minByOrNull { index ->
    distanceMeters(route[index], point)
} ?: 0

private fun distanceMeters(start: GeoPoint, end: GeoPoint): Double {
    val earthRadius = 6_371_000.0
    val latitudeDelta = Math.toRadians(end.latitude - start.latitude)
    val longitudeDelta = Math.toRadians(end.longitude - start.longitude)
    val startLatitude = Math.toRadians(start.latitude)
    val endLatitude = Math.toRadians(end.latitude)

    val a = sin(latitudeDelta / 2) * sin(latitudeDelta / 2) +
        cos(startLatitude) * cos(endLatitude) *
        sin(longitudeDelta / 2) * sin(longitudeDelta / 2)
    val c = 2 * asin(sqrt(a.coerceIn(0.0, 1.0)))
    return earthRadius * c
}

private fun offsetPoint(
    point: GeoPoint,
    headingDegrees: Double,
    distanceMeters: Double
): GeoPoint {
    val earthRadius = 6_371_000.0
    val bearing = Math.toRadians(headingDegrees)
    val latitude = Math.toRadians(point.latitude)
    val longitude = Math.toRadians(point.longitude)
    val angularDistance = distanceMeters / earthRadius

    val newLatitude = asin(
        sin(latitude) * cos(angularDistance) +
            cos(latitude) * sin(angularDistance) * cos(bearing)
    )
    val newLongitude = longitude + kotlin.math.atan2(
        sin(bearing) * sin(angularDistance) * cos(latitude),
        cos(angularDistance) - sin(latitude) * sin(newLatitude)
    )

    return GeoPoint(
        latitude = Math.toDegrees(newLatitude),
        longitude = Math.toDegrees(newLongitude)
    )
}

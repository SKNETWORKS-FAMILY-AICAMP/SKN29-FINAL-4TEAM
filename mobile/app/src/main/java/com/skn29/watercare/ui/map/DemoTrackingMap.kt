package com.skn29.watercare.ui.map

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.skn29.watercare.R
import com.skn29.watercare.model.GeoPoint
import com.skn29.watercare.model.TravelMode

@Composable
fun DemoTrackingMap(
    route: List<GeoPoint>,
    technician: GeoPoint,
    customer: GeoPoint,
    travelMode: TravelMode,
    modifier: Modifier = Modifier
) {
    val primary = MaterialTheme.colorScheme.primary
    val secondary = MaterialTheme.colorScheme.secondary
    val technicianImage = ImageBitmap.imageResource(
        when (travelMode) {
            TravelMode.DRIVING -> R.drawable.ic_marker_vehicle_map
            TravelMode.WAITING,
            TravelMode.WALKING,
            TravelMode.ARRIVED -> R.drawable.ic_marker_technician_map
        }
    )
    val customerImage = ImageBitmap.imageResource(R.drawable.ic_marker_customer_map)

    Box(
        modifier = modifier.background(Color(0xFFEAF1F7))
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val padding = 30.dp.toPx()
            val left = padding
            val top = padding
            val right = size.width - padding
            val bottom = size.height - padding

            val allPoints = route + technician + customer
            val minLatitude = allPoints.minOf { it.latitude } - 0.0008
            val maxLatitude = allPoints.maxOf { it.latitude } + 0.0008
            val minLongitude = allPoints.minOf { it.longitude } - 0.0008
            val maxLongitude = allPoints.maxOf { it.longitude } + 0.0008

            fun pointToOffset(point: GeoPoint): Offset {
                val xRatio = (
                    (point.longitude - minLongitude) /
                        (maxLongitude - minLongitude)
                    ).toFloat()
                val yRatio = (
                    (maxLatitude - point.latitude) /
                        (maxLatitude - minLatitude)
                    ).toFloat()

                return Offset(
                    x = left + (right - left) * xRatio,
                    y = top + (bottom - top) * yRatio
                )
            }

            val roadColor = Color(0xFFFFFFFF)
            repeat(6) { index ->
                val x = left + (right - left) * index / 5f
                drawLine(
                    color = roadColor,
                    start = Offset(x, top),
                    end = Offset(x, bottom),
                    strokeWidth = 11.dp.toPx(),
                    cap = StrokeCap.Round
                )
            }
            repeat(7) { index ->
                val y = top + (bottom - top) * index / 6f
                drawLine(
                    color = roadColor,
                    start = Offset(left, y),
                    end = Offset(right, y),
                    strokeWidth = 11.dp.toPx(),
                    cap = StrokeCap.Round
                )
            }

            if (route.size >= 2) {
                val routePath = Path().apply {
                    val first = pointToOffset(route.first())
                    moveTo(first.x, first.y)
                    route.drop(1).forEach { point ->
                        val offset = pointToOffset(point)
                        lineTo(offset.x, offset.y)
                    }
                }
                drawPath(
                    path = routePath,
                    color = primary.copy(alpha = 0.18f),
                    style = Stroke(width = 13.dp.toPx(), cap = StrokeCap.Round)
                )
                drawPath(
                    path = routePath,
                    color = primary,
                    style = Stroke(width = 5.dp.toPx(), cap = StrokeCap.Round)
                )
            }

            val technicianOffset = pointToOffset(technician)
            val customerOffset = pointToOffset(customer)
            val technicianSize = (
                if (travelMode == TravelMode.DRIVING) 48.dp else 52.dp
                ).toPx().toInt()
            val customerSize = 38.dp.toPx().toInt()

            drawCircle(
                color = primary.copy(alpha = 0.18f),
                radius = 27.dp.toPx(),
                center = technicianOffset
            )
            drawImage(
                image = technicianImage,
                dstOffset = IntOffset(
                    technicianOffset.x.toInt() - technicianSize / 2,
                    technicianOffset.y.toInt() - technicianSize / 2
                ),
                dstSize = IntSize(technicianSize, technicianSize)
            )

            drawCircle(
                color = secondary.copy(alpha = 0.18f),
                radius = 23.dp.toPx(),
                center = customerOffset
            )
            drawImage(
                image = customerImage,
                dstOffset = IntOffset(
                    customerOffset.x.toInt() - customerSize / 2,
                    customerOffset.y.toInt() - customerSize / 2
                ),
                dstSize = IntSize(customerSize, customerSize)
            )
        }

        Text(
            text = if (travelMode == TravelMode.DRIVING) "차량 이동 시연" else "도보 이동 시연",
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(14.dp)
                .background(
                    MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
                    RoundedCornerShape(14.dp)
                )
                .padding(horizontal = 12.dp, vertical = 8.dp),
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.Bold
        )
    }
}

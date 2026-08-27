package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.skn29.watercare.customer.R

enum class CustomerModelMascotKind {
    DROP,
    ICE,
    CARE,
}

data class CustomerModelVisualSpec(
    val modelCode: String,
    val modelName: String,
    val accent: Color,
    val softAccent: Color,
    val badgeIconRes: Int,
    val mascotKind: CustomerModelMascotKind,
    val productImageRes: Int? = null,
)

data class CustomerModelSelection(
    val modelCode: String,
    val subscriptionId: String?,
)

val CustomerModelCatalog = listOf(
    CustomerModelVisualSpec(
        modelCode = "WPUJAC104DWH",
        modelName = "WPU-JAC104 (D)",
        accent = Color(0xFF2A8CF6),
        softAccent = Color(0xFFDFF2FF),
        badgeIconRes = R.drawable.ref_filter,
        mascotKind = CustomerModelMascotKind.DROP,
        productImageRes = R.drawable.product_wpujac104dwh,
    ),
    CustomerModelVisualSpec(
        modelCode = "WPUIAC425SNW",
        modelName = "WPU-IAC425",
        accent = Color(0xFF59C8F3),
        softAccent = Color(0xFFE9FBFF),
        badgeIconRes = R.drawable.ref_dispense,
        mascotKind = CustomerModelMascotKind.ICE,
        productImageRes = R.drawable.product_wpuiac425snw,
    ),
    CustomerModelVisualSpec(
        modelCode = "WPUIAC606SNW",
        modelName = "WPU-IAC606",
        accent = Color(0xFF42C39D),
        softAccent = Color(0xFFE9FBF2),
        badgeIconRes = R.drawable.ref_care,
        mascotKind = CustomerModelMascotKind.CARE,
        productImageRes = R.drawable.product_wpuiac606snw,
    ),
)

fun customerModelVisualSpec(
    modelCode: String?,
    fallbackModelName: String? = null,
): CustomerModelVisualSpec {
    val normalized = modelCode
        ?.trim()
        .orEmpty()

    return CustomerModelCatalog
        .firstOrNull {
            it.modelCode.equals(
                normalized,
                ignoreCase = true,
            )
        }
        ?: CustomerModelCatalog.first().copy(
            modelCode = normalized.ifBlank {
                CustomerModelCatalog.first().modelCode
            },
            modelName = fallbackModelName
                ?.trim()
                ?.takeIf(String::isNotEmpty)
                ?: CustomerModelCatalog.first().modelName,
            productImageRes = null,
        )
}

@Composable
fun CustomerModelMascot(
    model: CustomerModelVisualSpec,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        Canvas(
            modifier = Modifier.fillMaxSize(),
        ) {
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(
                        Color.White.copy(alpha = 0.62f),
                        model.softAccent.copy(alpha = 0.82f),
                        model.accent.copy(alpha = 0.10f),
                        Color.Transparent,
                    )
                ),
                radius = size.minDimension * 0.48f,
                center = center,
            )

            when (model.mascotKind) {
                CustomerModelMascotKind.DROP -> {
                    drawCircle(
                        color = Color.White.copy(alpha = 0.50f),
                        radius = size.minDimension * 0.025f,
                        center = Offset(
                            x = size.width * 0.22f,
                            y = size.height * 0.28f,
                        ),
                    )
                    drawCircle(
                        color = model.accent.copy(alpha = 0.16f),
                        radius = size.minDimension * 0.020f,
                        center = Offset(
                            x = size.width * 0.78f,
                            y = size.height * 0.70f,
                        ),
                    )
                }

                CustomerModelMascotKind.ICE -> {
                    drawCircle(
                        color = model.accent.copy(alpha = 0.12f),
                        radius = size.minDimension * 0.030f,
                        center = Offset(
                            x = size.width * 0.26f,
                            y = size.height * 0.74f,
                        ),
                    )
                    drawCircle(
                        color = Color.White.copy(alpha = 0.54f),
                        radius = size.minDimension * 0.020f,
                        center = Offset(
                            x = size.width * 0.76f,
                            y = size.height * 0.24f,
                        ),
                    )
                }

                CustomerModelMascotKind.CARE -> {
                    drawRoundRect(
                        color = model.accent.copy(alpha = 0.10f),
                        topLeft = Offset(
                            x = size.width * 0.18f,
                            y = size.height * 0.66f,
                        ),
                        size = Size(
                            width = size.width * 0.16f,
                            height = size.height * 0.16f,
                        ),
                        cornerRadius = CornerRadius(
                            x = size.minDimension * 0.08f,
                            y = size.minDimension * 0.08f,
                        ),
                    )
                    drawCircle(
                        color = Color.White.copy(alpha = 0.48f),
                        radius = size.minDimension * 0.024f,
                        center = Offset(
                            x = size.width * 0.78f,
                            y = size.height * 0.26f,
                        ),
                    )
                }
            }
        }

        val productImage =
            model.productImageRes

        if (productImage != null) {
            Image(
                painter =
                    painterResource(
                        productImage
                    ),
                contentDescription =
                    model.modelName,
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(6.dp),
                contentScale =
                    ContentScale.Fit,
            )
        } else {
            when (model.mascotKind) {
                CustomerModelMascotKind.DROP -> {
                    Image(
                        painter = painterResource(
                            R.drawable.mascot_customer
                        ),
                        contentDescription = model.modelName,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(10.dp),
                        contentScale = ContentScale.Fit,
                    )
                }

                CustomerModelMascotKind.ICE -> {
                    IceModelCharacter(
                        accent = model.accent,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(22.dp),
                    )
                }

                CustomerModelMascotKind.CARE -> {
                    CareModelCharacter(
                        accent = model.accent,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(20.dp),
                    )
                }
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .size(32.dp)
                .clip(CircleShape)
                .background(
                    Color.White.copy(alpha = 0.82f)
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(model.badgeIconRes),
                contentDescription = null,
                modifier = Modifier.size(19.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }
}

@Composable
private fun IceModelCharacter(
    accent: Color,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val left = size.width * 0.15f
        val top = size.height * 0.16f
        val bodyWidth = size.width * 0.70f
        val bodyHeight = size.height * 0.66f

        drawRoundRect(
            brush = Brush.verticalGradient(
                listOf(
                    Color.White.copy(alpha = 0.96f),
                    Color(0xFFDDF6FF),
                    accent.copy(alpha = 0.62f),
                )
            ),
            topLeft = Offset(left, top),
            size = Size(bodyWidth, bodyHeight),
            cornerRadius = CornerRadius(
                x = size.minDimension * 0.16f,
                y = size.minDimension * 0.16f,
            ),
        )

        drawRoundRect(
            color = Color.White.copy(alpha = 0.65f),
            topLeft = Offset(
                x = left + bodyWidth * 0.12f,
                y = top + bodyHeight * 0.10f,
            ),
            size = Size(
                width = bodyWidth * 0.76f,
                height = bodyHeight * 0.12f,
            ),
            cornerRadius = CornerRadius(
                x = size.minDimension * 0.06f,
                y = size.minDimension * 0.06f,
            ),
        )

        val eyeY = top + bodyHeight * 0.48f
        drawCircle(
            color = Color(0xFF174D75),
            radius = size.minDimension * 0.035f,
            center = Offset(
                x = left + bodyWidth * 0.38f,
                y = eyeY,
            ),
        )
        drawCircle(
            color = Color(0xFF174D75),
            radius = size.minDimension * 0.035f,
            center = Offset(
                x = left + bodyWidth * 0.62f,
                y = eyeY,
            ),
        )
        drawArc(
            color = Color(0xFF174D75),
            startAngle = 18f,
            sweepAngle = 144f,
            useCenter = false,
            topLeft = Offset(
                x = left + bodyWidth * 0.39f,
                y = top + bodyHeight * 0.54f,
            ),
            size = Size(
                width = bodyWidth * 0.22f,
                height = bodyHeight * 0.18f,
            ),
            style = Stroke(
                width = size.minDimension * 0.025f,
                cap = StrokeCap.Round,
            ),
        )

        val sparkleCenter = Offset(
            x = size.width * 0.84f,
            y = size.height * 0.22f,
        )
        val sparkle = size.minDimension * 0.08f
        drawLine(
            color = accent,
            start = Offset(
                sparkleCenter.x - sparkle,
                sparkleCenter.y,
            ),
            end = Offset(
                sparkleCenter.x + sparkle,
                sparkleCenter.y,
            ),
            strokeWidth = size.minDimension * 0.018f,
            cap = StrokeCap.Round,
        )
        drawLine(
            color = accent,
            start = Offset(
                sparkleCenter.x,
                sparkleCenter.y - sparkle,
            ),
            end = Offset(
                sparkleCenter.x,
                sparkleCenter.y + sparkle,
            ),
            strokeWidth = size.minDimension * 0.018f,
            cap = StrokeCap.Round,
        )
    }
}

@Composable
private fun CareModelCharacter(
    accent: Color,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val bodyWidth = size.width * 0.56f
        val bodyHeight = size.height * 0.76f
        val left = (size.width - bodyWidth) / 2f
        val top = size.height * 0.10f

        drawRoundRect(
            brush = Brush.verticalGradient(
                listOf(
                    Color.White.copy(alpha = 0.96f),
                    Color(0xFFE8FBF5),
                    accent.copy(alpha = 0.58f),
                )
            ),
            topLeft = Offset(left, top),
            size = Size(bodyWidth, bodyHeight),
            cornerRadius = CornerRadius(
                x = bodyWidth * 0.48f,
                y = bodyWidth * 0.48f,
            ),
        )

        drawRoundRect(
            color = accent.copy(alpha = 0.26f),
            topLeft = Offset(
                x = left + bodyWidth * 0.12f,
                y = top + bodyHeight * 0.58f,
            ),
            size = Size(
                width = bodyWidth * 0.76f,
                height = bodyHeight * 0.12f,
            ),
            cornerRadius = CornerRadius(
                x = size.minDimension * 0.08f,
                y = size.minDimension * 0.08f,
            ),
        )

        val eyeY = top + bodyHeight * 0.40f
        drawCircle(
            color = Color(0xFF245B55),
            radius = size.minDimension * 0.032f,
            center = Offset(
                x = left + bodyWidth * 0.36f,
                y = eyeY,
            ),
        )
        drawCircle(
            color = Color(0xFF245B55),
            radius = size.minDimension * 0.032f,
            center = Offset(
                x = left + bodyWidth * 0.64f,
                y = eyeY,
            ),
        )
        drawArc(
            color = Color(0xFF245B55),
            startAngle = 20f,
            sweepAngle = 140f,
            useCenter = false,
            topLeft = Offset(
                x = left + bodyWidth * 0.38f,
                y = top + bodyHeight * 0.46f,
            ),
            size = Size(
                width = bodyWidth * 0.24f,
                height = bodyHeight * 0.16f,
            ),
            style = Stroke(
                width = size.minDimension * 0.022f,
                cap = StrokeCap.Round,
            ),
        )

        drawCircle(
            color = Color.White.copy(alpha = 0.58f),
            radius = size.minDimension * 0.055f,
            center = Offset(
                x = size.width * 0.76f,
                y = size.height * 0.22f,
            ),
        )
        drawCircle(
            color = accent.copy(alpha = 0.20f),
            radius = size.minDimension * 0.035f,
            center = Offset(
                x = size.width * 0.20f,
                y = size.height * 0.70f,
            ),
        )
    }
}

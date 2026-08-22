package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.animation.core.animateFloat
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.LinearEasing
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.Spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ReferencePearlBackground
import com.skn29.watercare.customer.R

@Composable
fun CustomerCleanScaffold(
    displayName: String?,
    showBottomBar: Boolean,
    careEnabled: Boolean = true,
    onOpenCare: () -> Unit = {},
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val palette = CustomerReferencePalette

    ReferencePearlBackground(
        palette = palette,
        backgroundRes = R.drawable.water_splash_customer_r19,
        imageAlpha = 0.13f,
        modifier = modifier,
    ) {
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                if (showBottomBar) {
                    CustomerCleanBottomBar(
                        careEnabled = careEnabled,
                        onOpenCare = onOpenCare,
                    )
                }
            },
        ) { innerPadding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .verticalScroll(rememberScrollState())
                    .padding(
                        start = 16.dp,
                        end = 16.dp,
                        top = 8.dp,
                        bottom = if (showBottomBar) 86.dp else 28.dp,
                    ),
                verticalArrangement = Arrangement.spacedBy(11.dp),
            ) {
                CustomerCleanHeader(
                    displayName = displayName,
                )
                content()
            }
        }
    }
}

@Composable
private fun CustomerCleanHeader(
    displayName: String?,
) {
    val palette = CustomerReferencePalette
    val name = displayName
        ?.trim()
        ?.takeIf { it.isNotEmpty() }
        ?: "WaterBridge 고객"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 54.dp)
            .padding(horizontal = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Image(
                painter = painterResource(R.drawable.waterbridge_brand_logo),
                contentDescription = "WaterBridge",
                modifier = Modifier.size(38.dp),
                contentScale = ContentScale.Fit,
            )
            Column(
                verticalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                Text(
                    text = "${name}님",
                    color = palette.textStrong,
                    fontSize = 20.sp,
                    lineHeight = 24.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "WaterBridge",
                    color = palette.textMuted,
                    fontSize = 10.5.sp,
                    lineHeight = 13.sp,
                    fontWeight = FontWeight.Medium,
                    letterSpacing = 0.2.sp,
                    maxLines = 1,
                )
            }
        }

        Box(
            modifier = Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.66f),
                            palette.accentSoft.copy(alpha = 0.10f),
                        )
                    )
                )
                .border(
                    BorderStroke(
                        1.dp,
                        Color.White.copy(alpha = 0.86f),
                    ),
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(R.drawable.ref_notice),
                contentDescription = "알림",
                modifier = Modifier.size(21.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }
}

@Composable
private fun CustomerCleanBottomBar(
    careEnabled: Boolean,
    onOpenCare: () -> Unit,
) {
    val palette = CustomerReferencePalette

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .padding(
                start = 16.dp,
                end = 16.dp,
                bottom = 7.dp,
            ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(58.dp)
                .padding(horizontal = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CustomerCleanBottomItem(
                iconRes = R.drawable.ref_home,
                label = "홈",
                selected = true,
                enabled = true,
                onClick = {},
                modifier = Modifier.weight(1f),
            )
            CustomerCleanBottomItem(
                iconRes = R.drawable.ref_care,
                label = "케어",
                selected = false,
                enabled = careEnabled,
                onClick = onOpenCare,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun CustomerCleanBottomItem(
    iconRes: Int,
    label: String,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette
    val shape = RoundedCornerShape(22.dp)
    val tabTransition =
        rememberInfiniteTransition(
            label = "bottomTab_$label",
        )
    val tabMotion by tabTransition.animateFloat(
        initialValue = 0f,
        targetValue =
            if (selected) 1f
            else 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 620,
            ),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "bottomTabMotion",
    )

    Column(
        modifier = modifier
            .fillMaxHeight()
            .clip(shape)
            .background(
                if (selected) {
                    Color.White.copy(alpha = 0.15f)
                } else {
                    Color.Transparent
                }
            )
            .clickable(
                enabled = enabled,
                onClick = onClick,
            )
            .padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Image(
            painter = painterResource(iconRes),
            contentDescription = label,
            modifier = Modifier
                .size(22.dp)
                .graphicsLayer {
                    translationY = -2.dp.toPx() * tabMotion
                    scaleX = 1f + (0.04f * tabMotion)
                    scaleY = 1f + (0.04f * tabMotion)
                    rotationZ = 0f
                },
            contentScale = ContentScale.Fit,
            alpha = if (enabled) 1f else 0.38f,
        )
        Text(
            text = label,
            modifier = Modifier.padding(top = 1.dp),
            color = when {
                !enabled -> palette.textMuted.copy(alpha = 0.48f)
                selected -> palette.accent
                else -> palette.textMuted
            },
            fontSize = 11.5.sp,
            lineHeight = 14.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
        )
        Box(
            modifier = Modifier
                .padding(top = 2.dp)
                .size(
                    width = if (selected) 18.dp else 0.dp,
                    height = 2.dp,
                )
                .clip(RoundedCornerShape(999.dp))
                .background(
                    if (selected) palette.accent else Color.Transparent
                ),
        )
    }
}

@Composable
fun CustomerCleanCard(
    modifier: Modifier = Modifier,
    contentPadding: PaddingValues = PaddingValues(14.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    val palette = CustomerReferencePalette
    val shape = RoundedCornerShape(
        topStart = 28.dp,
        topEnd = 28.dp,
        bottomStart = 28.dp,
        bottomEnd = 24.dp,
    )
    val glassBrush = Brush.verticalGradient(
        listOf(
            Color.White.copy(alpha = 0.40f),
            Color.White.copy(alpha = 0.20f),
            palette.accentSoft.copy(alpha = 0.028f),
        )
    )
    val borderBrush = Brush.linearGradient(
        listOf(
            Color.White.copy(alpha = 0.68f),
            palette.accent.copy(alpha = 0.06f),
            palette.accentSecondary.copy(alpha = 0.045f),
            Color.White.copy(alpha = 0.46f),
        )
    )

    Column(
        modifier = modifier
            .shadow(
                elevation = 2.dp,
                shape = shape,
                ambientColor = palette.accent.copy(alpha = 0.07f),
                spotColor = palette.accentSecondary.copy(alpha = 0.06f),
                clip = false,
            )
            .clip(shape)
            .background(glassBrush)
            .drawBehind {
                drawLine(
                    color = Color.White.copy(alpha = 0.40f),
                    start = Offset(
                        x = size.width * 0.10f,
                        y = 1.4.dp.toPx(),
                    ),
                    end = Offset(
                        x = size.width * 0.76f,
                        y = 1.4.dp.toPx(),
                    ),
                    strokeWidth = 1.dp.toPx(),
                )
                drawCircle(
                    color = palette.accentSecondary.copy(alpha = 0.014f),
                    radius = size.minDimension * 0.28f,
                    center = Offset(
                        x = size.width * 0.93f,
                        y = size.height * 0.90f,
                    ),
                )
            }
            .border(
                BorderStroke(
                    width = 1.dp,
                    brush = borderBrush,
                ),
                shape,
            )
            .padding(contentPadding),
        verticalArrangement = Arrangement.spacedBy(7.dp),
        content = content,
    )
}

@Composable
fun CustomerPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val palette = CustomerReferencePalette
    val interactionSource = remember {
        MutableInteractionSource()
    }
    val pressed by
        interactionSource.collectIsPressedAsState()
    val pressScale by animateFloatAsState(
        targetValue =
            if (pressed) 0.96f
            else 1f,
        animationSpec = spring(
            dampingRatio =
                Spring.DampingRatioHighBouncy,
            stiffness = Spring.StiffnessMediumLow,
        ),
        label = "customerPrimaryButtonScale",
    )
    val shineTransition =
        rememberInfiniteTransition(
            label = "customerPrimaryShine",
        )
    val shineProgress by
        shineTransition.animateFloat(
            initialValue = -0.35f,
            targetValue = 1.35f,
            animationSpec =
                infiniteRepeatable(
                    animation = tween(
                        durationMillis = 1250,
                        easing = LinearEasing,
                    ),
                    repeatMode =
                        RepeatMode.Restart,
                ),
            label = "customerPrimaryShineProgress",
        )

    Button(
        onClick = onClick,
        modifier = modifier
            .heightIn(min = 50.dp)
            .graphicsLayer {
                scaleX = pressScale
                scaleY = pressScale
            }
            .drawWithContent {
                drawContent()

                if (enabled) {
                    val centerX =
                        size.width *
                            shineProgress
                    val halfBand =
                        size.width *
                            0.16f

                    drawRect(
                        brush =
                            Brush.linearGradient(
                                colors = listOf(
                                    Color.Transparent,
                                    Color.White.copy(
                                        alpha = 0.06f
                                    ),
                                    Color.White.copy(
                                        alpha = 0.62f
                                    ),
                                    Color.White.copy(
                                        alpha = 0.06f
                                    ),
                                    Color.Transparent,
                                ),
                                start = Offset(
                                    x =
                                        centerX -
                                            halfBand,
                                    y = 0f,
                                ),
                                end = Offset(
                                    x =
                                        centerX +
                                            halfBand,
                                    y = size.height,
                                ),
                            ),
                        topLeft = Offset.Zero,
                        size = Size(
                            width = size.width,
                            height = size.height,
                        ),
                    )
                }
            },
        enabled = enabled,
        interactionSource = interactionSource,
        shape = RoundedCornerShape(24.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = palette.accent,
            contentColor = Color.White,
            disabledContainerColor = palette.accent.copy(alpha = 0.28f),
            disabledContentColor = Color.White.copy(alpha = 0.78f),
        ),
        contentPadding = PaddingValues(
            horizontal = 20.dp,
            vertical = 12.dp,
        ),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
fun CustomerTextAction(
    text: String,
    onClick: () -> Unit,
    enabled: Boolean = true,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette
    TextButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
    ) {
        Text(
            text = text,
            color = if (enabled) {
                palette.accent
            } else {
                palette.textMuted.copy(alpha = 0.45f)
            },
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

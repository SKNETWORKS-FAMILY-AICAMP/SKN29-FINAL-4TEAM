package com.skn29.watercare.core.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun WaterBridgeCustomerStatusRow(
    items: List<ReferenceStatusItem>,
    palette: ReferenceDashboardPalette,
) {
    val shape = RoundedCornerShape(26.dp)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(
                elevation = 8.dp,
                shape = shape,
                ambientColor = palette.accent.copy(alpha = 0.10f),
                spotColor = palette.accent.copy(alpha = 0.08f),
                clip = false,
            )
            .clip(shape)
            .background(Color.White.copy(alpha = 0.94f))
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.98f),
                ),
                shape,
            )
            .padding(
                horizontal = 8.dp,
                vertical = 16.dp,
            ),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        items.take(4).forEachIndexed { index, item ->
            if (index > 0) {
                Box(
                    modifier = Modifier
                        .width(1.dp)
                        .height(82.dp)
                        .background(
                            palette.accent.copy(alpha = 0.12f)
                        )
                )
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 4.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(38.dp)
                        .clip(CircleShape)
                        .background(
                            palette.accentSoft.copy(alpha = 0.34f)
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Image(
                        painter = painterResource(item.iconRes),
                        contentDescription = item.label,
                        modifier = Modifier.size(24.dp),
                    )
                }

                Text(
                    text = item.label,
                    color = palette.textMuted,
                    fontSize = 10.5.sp,
                    lineHeight = 13.sp,
                    fontWeight = FontWeight.Medium,
                    textAlign = TextAlign.Center,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = item.value,
                    color = if (item.healthy) {
                        palette.accent
                    } else {
                        palette.danger
                    },
                    fontSize = 13.sp,
                    lineHeight = 16.sp,
                    fontWeight = FontWeight.ExtraBold,
                    textAlign = TextAlign.Center,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
fun WaterBridgeCustomerActionRow(
    items: List<ReferenceActionItem>,
    palette: ReferenceDashboardPalette,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items.take(4).forEach { item ->
            val shape = RoundedCornerShape(22.dp)

            Column(
                modifier = Modifier
                    .weight(1f)
                    .height(132.dp)
                    .shadow(
                        elevation = if (item.enabled) 7.dp else 2.dp,
                        shape = shape,
                        ambientColor = palette.accent.copy(alpha = 0.08f),
                        spotColor = palette.accent.copy(alpha = 0.06f),
                        clip = false,
                    )
                    .clip(shape)
                    .background(Color.White.copy(alpha = 0.94f))
                    .border(
                        BorderStroke(
                            1.dp,
                            Color.White.copy(alpha = 0.98f),
                        ),
                        shape,
                    )
                    .alpha(if (item.enabled) 1f else 0.58f)
                    .clickable(
                        enabled = item.enabled,
                        onClick = item.onClick,
                    )
                    .padding(
                        horizontal = 5.dp,
                        vertical = 11.dp,
                    ),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(
                            palette.accentSoft.copy(alpha = 0.32f)
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Image(
                        painter = painterResource(item.iconRes),
                        contentDescription = item.label,
                        modifier = Modifier.size(27.dp),
                    )
                }

                Text(
                    text = item.label,
                    modifier = Modifier.padding(top = 8.dp),
                    color = palette.textStrong,
                    fontSize = 11.5.sp,
                    lineHeight = 14.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )

                if (item.subtitle.isNotBlank()) {
                    Text(
                        text = if (item.enabled) {
                            item.subtitle
                        } else {
                            "준비 중"
                        },
                        modifier = Modifier.padding(top = 3.dp),
                        color = palette.textMuted,
                        fontSize = 9.5.sp,
                        lineHeight = 12.sp,
                        fontWeight = FontWeight.Medium,
                        textAlign = TextAlign.Center,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Suppress("UNUSED_PARAMETER")
@Composable
fun WaterBridgeCustomerDetailCard(
    @DrawableRes imageRes: Int,
    title: String,
    badge: String,
    lines: List<String>,
    status: String,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
    primaryActionLabel: String,
    secondaryActionLabel: String,
    onPrimaryAction: () -> Unit,
    onSecondaryAction: () -> Unit,
    primaryActionEnabled: Boolean = true,
    secondaryActionEnabled: Boolean = true,
    timeline: List<String> = emptyList(),
    selectedTimelineIndex: Int = 0,
) {
    val shape = RoundedCornerShape(26.dp)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .shadow(
                elevation = 8.dp,
                shape = shape,
                ambientColor = palette.accent.copy(alpha = 0.09f),
                spotColor = palette.accent.copy(alpha = 0.07f),
                clip = false,
            )
            .clip(shape)
            .background(Color.White.copy(alpha = 0.95f))
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.98f),
                ),
                shape,
            )
            .padding(
                horizontal = 14.dp,
                vertical = 14.dp,
            ),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(
            modifier = Modifier
                .size(82.dp)
                .clip(RoundedCornerShape(18.dp))
                .background(
                    palette.accentSoft.copy(alpha = 0.12f)
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(imageRes),
                contentDescription = title,
                modifier = Modifier.size(72.dp),
                contentScale = ContentScale.Fit,
            )
        }

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Text(
                text = title,
                color = palette.textStrong,
                fontSize = 18.sp,
                lineHeight = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            Text(
                text = if (badge.isNotBlank()) {
                    badge
                } else {
                    status
                },
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(
                        Color(0xFFE6F8F4)
                    )
                    .padding(
                        horizontal = 10.dp,
                        vertical = 5.dp,
                    ),
                color = Color(0xFF159B7D),
                fontSize = 10.5.sp,
                lineHeight = 13.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            lines.take(1).forEach { line ->
                Text(
                    text = line,
                    color = palette.textMuted,
                    fontSize = 10.5.sp,
                    lineHeight = 14.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Text(
            text = "›",
            color = palette.accent,
            fontSize = 30.sp,
            lineHeight = 30.sp,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
fun WaterBridgeTechnicianScheduleCard(
    time: String,
    customerName: String,
    badge: String,
    lines: List<String>,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val shape = RoundedCornerShape(20.dp)
    val amber = Color(0xFFFFA23A)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .shadow(
                elevation = 5.dp,
                shape = shape,
                ambientColor = Color.Black.copy(alpha = 0.20f),
                spotColor = amber.copy(alpha = 0.08f),
                clip = false,
            )
            .clip(shape)
            .background(
                Color(0xFF10263A).copy(alpha = 0.96f)
            )
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.16f),
                ),
                shape,
            )
            .alpha(if (enabled) 1f else 0.58f)
            .padding(
                horizontal = 12.dp,
                vertical = 11.dp,
            ),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(
            modifier = Modifier.width(72.dp),
            horizontalAlignment = Alignment.Start,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = customerName,
                color = Color.White.copy(alpha = 0.88f),
                fontSize = 12.sp,
                lineHeight = 15.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            Text(
                text = time,
                color = amber,
                fontSize = 19.sp,
                lineHeight = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                maxLines = 1,
            )
        }

        Box(
            modifier = Modifier
                .width(1.dp)
                .height(60.dp)
                .background(Color.White.copy(alpha = 0.12f))
        )

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = badge,
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(amber.copy(alpha = 0.13f))
                    .border(
                        BorderStroke(
                            1.dp,
                            amber.copy(alpha = 0.34f),
                        ),
                        RoundedCornerShape(999.dp),
                    )
                    .padding(
                        horizontal = 8.dp,
                        vertical = 4.dp,
                    ),
                color = amber,
                fontSize = 10.sp,
                lineHeight = 12.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
            )

            lines.take(2).forEachIndexed { index, line ->
                Text(
                    text = line,
                    color = if (index == 0) {
                        Color.White.copy(alpha = 0.94f)
                    } else {
                        Color.White.copy(alpha = 0.54f)
                    },
                    fontSize = if (index == 0) 12.sp else 10.5.sp,
                    lineHeight = if (index == 0) 15.sp else 13.sp,
                    fontWeight = if (index == 0) {
                        FontWeight.Bold
                    } else {
                        FontWeight.Medium
                    },
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Text(
            text = "상세 보기",
            modifier = Modifier
                .clip(RoundedCornerShape(999.dp))
                .border(
                    BorderStroke(
                        1.dp,
                        amber.copy(alpha = 0.48f),
                    ),
                    RoundedCornerShape(999.dp),
                )
                .clickable(
                    enabled = enabled,
                    onClick = onClick,
                )
                .padding(
                    horizontal = 11.dp,
                    vertical = 9.dp,
                ),
            color = amber,
            fontSize = 10.5.sp,
            lineHeight = 13.sp,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
        )
    }
}

@Composable
fun WaterBridgeTechnicianActionRow(
    items: List<ReferenceActionItem>,
    palette: ReferenceDashboardPalette,
) {
    val amber = Color(0xFFFFA23A)

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items.take(4).forEach { item ->
            val shape = RoundedCornerShape(18.dp)

            Column(
                modifier = Modifier
                    .weight(1f)
                    .height(116.dp)
                    .clip(shape)
                    .background(
                        Color(0xFF152B3E).copy(alpha = 0.96f)
                    )
                    .border(
                        BorderStroke(
                            1.dp,
                            Color.White.copy(alpha = 0.16f),
                        ),
                        shape,
                    )
                    .alpha(if (item.enabled) 1f else 0.48f)
                    .clickable(
                        enabled = item.enabled,
                        onClick = item.onClick,
                    )
                    .padding(
                        horizontal = 5.dp,
                        vertical = 10.dp,
                    ),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Image(
                    painter = painterResource(item.iconRes),
                    contentDescription = item.label,
                    modifier = Modifier.size(34.dp),
                )

                Text(
                    text = item.label,
                    modifier = Modifier.padding(top = 8.dp),
                    color = if (item.enabled) {
                        Color.White.copy(alpha = 0.96f)
                    } else {
                        Color.White.copy(alpha = 0.54f)
                    },
                    fontSize = 11.sp,
                    lineHeight = 14.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )

                if (item.enabled) {
                    Box(
                        modifier = Modifier
                            .padding(top = 6.dp)
                            .width(26.dp)
                            .height(2.dp)
                            .clip(RoundedCornerShape(999.dp))
                            .background(amber)
                    )
                }
            }
        }
    }
}

@Suppress("UNUSED_PARAMETER")
@Composable
fun WaterBridgeTechnicianLogoutButton(
    text: String,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    accent: Boolean = false,
    danger: Boolean = false,
    compact: Boolean = false,
) {
    val shape = RoundedCornerShape(18.dp)
    val red = Color(0xFFFF625C)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 58.dp)
            .clip(shape)
            .background(Color(0xFF13283A).copy(alpha = 0.98f))
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.14f),
                ),
                shape,
            )
            .alpha(if (enabled) 1f else 0.50f)
            .clickable(
                enabled = enabled,
                onClick = onClick,
            )
            .padding(
                horizontal = 16.dp,
                vertical = 12.dp,
            ),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "⏻",
            color = red,
            fontSize = 23.sp,
            lineHeight = 24.sp,
            fontWeight = FontWeight.Bold,
        )

        Text(
            text = text,
            modifier = Modifier
                .weight(1f)
                .padding(start = 13.dp),
            color = red,
            fontSize = 14.sp,
            lineHeight = 18.sp,
            fontWeight = FontWeight.ExtraBold,
        )

        Text(
            text = "›",
            color = Color.White.copy(alpha = 0.62f),
            fontSize = 25.sp,
            lineHeight = 25.sp,
            fontWeight = FontWeight.Medium,
        )
    }
}

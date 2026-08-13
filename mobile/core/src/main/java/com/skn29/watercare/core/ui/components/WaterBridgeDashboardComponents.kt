package com.skn29.watercare.core.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * WaterBridge UI V2.1
 *
 * Runtime/Repository/State/allowed_actions 로직은 변경하지 않는다.
 * 배경보다 카드/버튼이 먼저 보이도록 대비를 높이고,
 * 작은 화면에서 텍스트가 잘리지 않도록 minHeight + 2열 fallback을 사용한다.
 */
val WaterBridgeCustomerPalette = CustomerReferencePalette.copy(
    accent = Color(0xFF176BDE),
    accentSecondary = Color(0xFF2D8CF0),
    accentSoft = Color(0x1F176BDE),
    accentSoftSecondary = Color(0x162D8CF0),
    backgroundStart = Color(0xFFF5FAFD),
    backgroundEnd = Color(0xFFEDF5F9),
    textStrong = Color(0xFF10213A),
    textMuted = Color(0xFF53667A),
)

val WaterBridgeTechnicianPalette = TechnicianReferencePalette.copy(
    accent = Color(0xFF334E68),
    accentSecondary = Color(0xFFF59E0B),
    accentSoft = Color(0x20334E68),
    accentSoftSecondary = Color(0x26F59E0B),
    backgroundStart = Color(0xFF0B263D),
    backgroundEnd = Color(0xFF8C5135),
    textStrong = Color(0xFF172B3A),
    textMuted = Color(0xFF607383),
    success = Color(0xFF2F9E76),
    warning = Color(0xFFF59E0B),
    danger = Color(0xFFD95763),
    darkSurface = false,
    sunsetBackground = true,
)

@Composable
fun WaterBridgeStatusRow(
    items: List<ReferenceStatusItem>,
    palette: ReferenceDashboardPalette,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val visibleItems = items.take(4)
        val twoColumns = maxWidth < 360.dp && visibleItems.size > 2

        if (twoColumns) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                visibleItems.chunked(2).forEach { rowItems ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        rowItems.forEach { item ->
                            WaterBridgeStatusTile(
                                item = item,
                                palette = palette,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        if (rowItems.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                visibleItems.forEach { item ->
                    WaterBridgeStatusTile(
                        item = item,
                        palette = palette,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun WaterBridgeStatusTile(
    item: ReferenceStatusItem,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    val shape = RoundedCornerShape(24.dp)
    val cardBrush = if (palette.darkSurface) {
        Brush.verticalGradient(
            listOf(
                Color(0xFF155C75),
                Color(0xFF0E4961),
            )
        )
    } else {
        Brush.verticalGradient(
            listOf(
                Color(0xFFFFFFFF),
                Color(0xFFF8FBFE),
                Color(0xFFF0F7FB),
            )
        )
    }

    Column(
        modifier = modifier
            .heightIn(min = 132.dp)
            .shadow(
                elevation = 12.dp,
                shape = shape,
                ambientColor = Color.Black.copy(alpha = 0.10f),
                spotColor = palette.accent.copy(alpha = 0.16f),
                clip = false,
            )
            .clip(shape)
            .background(cardBrush)
            .border(
                BorderStroke(
                    1.4.dp,
                    if (palette.darkSurface) {
                        Color.White.copy(alpha = 0.36f)
                    } else {
                        palette.accent.copy(alpha = 0.18f)
                    },
                ),
                shape,
            )
            .padding(horizontal = 8.dp, vertical = 13.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Box(
            modifier = Modifier
                .size(48.dp)
                .clip(CircleShape)
                .background(
                    if (palette.darkSurface) {
                        Color.White.copy(alpha = 0.14f)
                    } else {
                        Color(0xFFEAF3FF)
                    }
                )
                .border(
                    BorderStroke(
                        1.dp,
                        if (palette.darkSurface) {
                            Color.White.copy(alpha = 0.30f)
                        } else {
                            Color(0xFFCFE2FF)
                        },
                    ),
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(item.iconRes),
                contentDescription = item.label,
                modifier = Modifier.size(28.dp),
                colorFilter = ColorFilter.tint(
                    if (item.healthy) palette.accent else palette.danger
                ),
            )
        }

        Text(
            text = item.label,
            color = palette.textMuted,
            fontSize = 11.5.sp,
            lineHeight = 15.sp,
            fontWeight = FontWeight.Medium,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )

        Text(
            text = item.value,
            color = if (item.healthy) palette.accent else palette.danger,
            fontSize = 16.5.sp,
            lineHeight = 21.sp,
            fontWeight = FontWeight.Black,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
fun WaterBridgeActionRow(
    items: List<ReferenceActionItem>,
    palette: ReferenceDashboardPalette,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val visibleItems = items.take(4)
        val twoColumns = maxWidth < 390.dp && visibleItems.size > 2

        if (twoColumns) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                visibleItems.chunked(2).forEach { rowItems ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        rowItems.forEach { item ->
                            WaterBridgeActionTile(
                                item = item,
                                palette = palette,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        if (rowItems.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                visibleItems.forEach { item ->
                    WaterBridgeActionTile(
                        item = item,
                        palette = palette,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun WaterBridgeActionTile(
    item: ReferenceActionItem,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    val shape = RoundedCornerShape(23.dp)
    val interactionSource = remember { MutableInteractionSource() }
    val tagModifier = if (item.testTag.isNullOrBlank()) {
        Modifier
    } else {
        Modifier.testTag(item.testTag)
    }

    val enabledCard = Brush.verticalGradient(
        listOf(
            Color(0xFFFFFFFF),
            Color(0xFFF7FAFD),
            Color(0xFFEDF4F8),
        )
    )
    val disabledCard = Brush.verticalGradient(
        listOf(
            Color(0xFFF4F6F8),
            Color(0xFFE8EDF1),
        )
    )

    Column(
        modifier = modifier
            .then(tagModifier)
            .heightIn(min = 140.dp)
            .shadow(
                elevation = if (item.enabled) 13.dp else 4.dp,
                shape = shape,
                ambientColor = Color.Black.copy(
                    alpha = if (item.enabled) 0.11f else 0.05f
                ),
                spotColor = palette.accent.copy(
                    alpha = if (item.enabled) 0.17f else 0.05f
                ),
                clip = false,
            )
            .clip(shape)
            .clickable(
                enabled = item.enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = item.onClick,
            )
            .background(if (item.enabled) enabledCard else disabledCard)
            .border(
                BorderStroke(
                    1.45.dp,
                    if (item.enabled) Color.White else Color(0xFFDCE3E8),
                ),
                shape,
            )
            .padding(horizontal = 8.dp, vertical = 13.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(CircleShape)
                .background(
                    if (item.enabled) {
                        Brush.linearGradient(
                            listOf(
                                Color(0xFFE8F2FF),
                                Color(0xFFDDEBFF),
                            )
                        )
                    } else {
                        Brush.linearGradient(
                            listOf(
                                Color(0xFFEDF1F4),
                                Color(0xFFE4E9ED),
                            )
                        )
                    }
                )
                .border(
                    BorderStroke(
                        1.dp,
                        if (item.enabled) Color(0xFFC6DCFF)
                        else Color(0xFFD6DEE4),
                    ),
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(item.iconRes),
                contentDescription = item.label,
                modifier = Modifier.size(32.dp),
                colorFilter = ColorFilter.tint(
                    if (item.enabled) Color(0xFF176BDE)
                    else Color(0xFF98A4AF)
                ),
            )
        }

        Text(
            text = item.label,
            modifier = Modifier.padding(top = 8.dp),
            color = if (item.enabled) Color(0xFF10213A)
            else Color(0xFF8794A2),
            fontSize = 13.sp,
            lineHeight = 17.sp,
            fontWeight = FontWeight.Black,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )

        if (item.subtitle.isNotBlank()) {
            Text(
                text = if (item.enabled) item.subtitle else "준비 중",
                color = if (item.enabled) Color(0xFF5D6D7D)
                else Color(0xFF9AA5AF),
                fontSize = 10.5.sp,
                lineHeight = 14.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
fun WaterBridgeScheduleCard(
    time: String,
    customerName: String,
    badge: String,
    lines: List<String>,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val shape = RoundedCornerShape(24.dp)
    val interactionSource = remember { MutableInteractionSource() }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .shadow(
                elevation = 13.dp,
                shape = shape,
                ambientColor = Color.Black.copy(alpha = 0.12f),
                spotColor = palette.accent.copy(alpha = 0.13f),
                clip = false,
            )
            .clip(shape)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = onClick,
            )
            .background(
                Brush.verticalGradient(
                    listOf(
                        Color(0xFFFFFFFF),
                        Color(0xFFF8FAFC),
                        Color(0xFFECF2F6),
                    )
                )
            )
            .border(BorderStroke(1.4.dp, Color.White), shape)
            .padding(horizontal = 15.dp, vertical = 15.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(52.dp)
                .clip(CircleShape)
                .background(
                    Brush.linearGradient(
                        listOf(
                            Color(0xFF2D82ED),
                            Color(0xFF165FCF),
                        )
                    )
                ),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = customerName.take(2),
                color = Color.White,
                fontWeight = FontWeight.Black,
                fontSize = 14.sp,
                maxLines = 1,
            )
        }

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = time,
                    color = Color(0xFF10213A),
                    fontSize = 22.sp,
                    lineHeight = 26.sp,
                    fontWeight = FontWeight.Black,
                    maxLines = 1,
                )
                WaterBridgeBadge(
                    text = badge,
                    accent = palette.accentSecondary,
                )
            }

            Text(
                text = customerName,
                color = Color(0xFF10213A),
                fontSize = 14.sp,
                lineHeight = 18.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            lines.take(2).forEach { line ->
                Text(
                    text = line,
                    color = Color(0xFF5A6A7B),
                    fontSize = 11.5.sp,
                    lineHeight = 15.5.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Text(
            text = if (enabled) "상세  ›" else "대기",
            modifier = Modifier
                .clip(RoundedCornerShape(999.dp))
                .background(Color(0xFFE7F1FF))
                .border(
                    BorderStroke(1.dp, Color(0xFFB8D2FA)),
                    RoundedCornerShape(999.dp),
                )
                .padding(horizontal = 12.dp, vertical = 9.dp),
            color = Color(0xFF176BDE),
            fontSize = 12.sp,
            fontWeight = FontWeight.Black,
            maxLines = 1,
        )
    }
}

@Composable
private fun WaterBridgeBadge(
    text: String,
    accent: Color,
) {
    Text(
        text = text,
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(accent.copy(alpha = 0.12f))
            .border(
                BorderStroke(1.dp, accent.copy(alpha = 0.25f)),
                RoundedCornerShape(999.dp),
            )
            .padding(horizontal = 9.dp, vertical = 5.dp),
        color = Color(0xFF176BDE),
        fontSize = 10.5.sp,
        lineHeight = 13.sp,
        fontWeight = FontWeight.Bold,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}

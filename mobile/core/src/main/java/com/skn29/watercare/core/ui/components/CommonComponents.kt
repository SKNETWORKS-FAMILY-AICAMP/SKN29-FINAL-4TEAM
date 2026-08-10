package com.skn29.watercare.core.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.skn29.watercare.core.ui.theme.WaterSubText
import com.skn29.watercare.core.ui.theme.WaterTokens

@Composable
fun WaterCareHeader(
    title: String,
    subtitle: String? = null,
) {
    LiquidGlassPanel(strong = true) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(58.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.linearGradient(
                            listOf(
                                WaterTokens.PearlBlue.copy(alpha = 0.70f),
                                WaterTokens.PearlLavender.copy(alpha = 0.56f),
                                WaterTokens.PearlPink.copy(alpha = 0.48f),
                            )
                        )
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Text("💧", fontSize = 27.sp)
            }

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                LiquidGlassPill("정수기 딜러")

                Text(
                    title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.ExtraBold,
                )

                if (!subtitle.isNullOrBlank()) {
                    Text(
                        subtitle,
                        color = WaterSubText,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }
    }
}

@Composable
fun LoadingBlock(message: String = "불러오는 중입니다") {
    LiquidGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        strong = true,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            CircularProgressIndicator(
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                message,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun ErrorCard(
    message: String,
    onRetry: (() -> Unit)? = null,
) {
    LiquidGlassPanel(danger = true) {
        Text(
            "확인이 필요해요",
            color = MaterialTheme.colorScheme.error,
            fontWeight = FontWeight.ExtraBold,
        )
        Text(message)

        if (onRetry != null) {
            LiquidGlassButton(
                text = "다시 시도",
                onClick = onRetry,
                modifier = Modifier.fillMaxWidth(),
                accent = true,
            )
        }
    }
}

@Composable
fun PendingFeatureCard(
    title: String,
    description: String,
) {
    LiquidGlassPanel {
        LiquidGlassPill("준비 중")

        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.ExtraBold,
        )
        Text(
            description,
            color = WaterSubText,
        )
        Text(
            "제공되는 API부터 안전하게 연결합니다.",
            style = MaterialTheme.typography.bodySmall,
            color = WaterSubText,
        )
    }
}

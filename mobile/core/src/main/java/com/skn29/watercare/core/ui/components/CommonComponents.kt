package com.skn29.watercare.core.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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
    Card(
        shape = RoundedCornerShape(WaterTokens.RadiusCard),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(56.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.secondaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Text("💧", fontSize = 27.sp)
            }

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Surface(
                    shape = RoundedCornerShape(WaterTokens.RadiusPill),
                    color = MaterialTheme.colorScheme.secondaryContainer,
                ) {
                    Text(
                        "정수기 딜러",
                        modifier = Modifier.padding(
                            horizontal = 10.dp,
                            vertical = 4.dp,
                        ),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }

                Text(
                    title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
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
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(WaterTokens.RadiusCard),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline,
        ),
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
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
    Card(
        shape = RoundedCornerShape(WaterTokens.RadiusCard),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.error,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                "확인이 필요해요",
                color = MaterialTheme.colorScheme.error,
                fontWeight = FontWeight.SemiBold,
            )
            Text(message)

            if (onRetry != null) {
                Button(onClick = onRetry) {
                    Text("다시 시도")
                }
            }
        }
    }
}

@Composable
fun PendingFeatureCard(
    title: String,
    description: String,
) {
    Card(
        shape = RoundedCornerShape(WaterTokens.RadiusCard),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Surface(
                shape = RoundedCornerShape(WaterTokens.RadiusPill),
                color = MaterialTheme.colorScheme.secondaryContainer,
            ) {
                Text(
                    "준비 중",
                    modifier = Modifier.padding(
                        horizontal = 10.dp,
                        vertical = 4.dp,
                    ),
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
            }

            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
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
}

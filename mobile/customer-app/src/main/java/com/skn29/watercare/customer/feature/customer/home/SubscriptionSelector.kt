package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.isP0SupportedActiveSubscription
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.core.ui.components.ReferenceSectionHeader

@Composable
fun SubscriptionSelector(
    state: CustomerHomeUiState,
    onSelect: (String) -> Unit,
) {
    if (
        state.customerCareMode != CustomerCareMode.REMOTE ||
        state.offlinePreview ||
        state.subscriptions.isEmpty()
    ) {
        return
    }

    val palette = CustomerReferencePalette
    ReferenceSectionHeader(
        title = "내 구독",
        trailing = if (state.subscriptions.size > 1) "문의할 제품을 선택하세요" else "실제 Backend 조회",
        palette = palette,
    )
    ReferenceGlassPanel(palette = palette) {
        Column(
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            state.subscriptions.forEach { subscription ->
                val selected =
                    state.selectedSubscriptionId == subscription.subscriptionId
                val supported = subscription.isP0SupportedActiveSubscription()
                Text(
                    text = buildString {
                        append(subscription.product.modelName)
                        append(" · ")
                        append(subscription.statusCode ?: "상태 확인")
                        if (!supported) append(" · P0 문의 제한")
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = if (selected) FontWeight.ExtraBold else FontWeight.Medium,
                )
                ReferenceGlassButton(
                    text = if (selected) "선택됨" else "이 구독 선택",
                    palette = palette,
                    accent = selected,
                    enabled = !selected && !state.selectingSubscription,
                    onClick = { onSelect(subscription.subscriptionId) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("subscription_${subscription.subscriptionId}"),
                )
            }
        }
    }
}

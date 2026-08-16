package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.WaterBridgeCustomerPalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceBackendStatusCard
import com.skn29.watercare.core.ui.components.ReferenceDashboardScaffold
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceWelcomeCard
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory

@Composable
fun LoginScreen(
    onAuthenticated: (offlinePreview: Boolean) -> Unit,
) {
    val viewModel: AuthViewModel = viewModel(
        factory = VmFactory { _ ->
            AuthViewModel(
                WaterCareCore.authRepository,
                WaterCareCore.backendStatusRepository,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    val palette = WaterBridgeCustomerPalette

    LaunchedEffect(state.authenticated) {
        if (state.authenticated) {
            onAuthenticated(state.offlinePreview)
        }
    }

    ReferenceDashboardScaffold(
        title = "WaterBridge",
        roleLabel = "고객용",
        palette = palette,
                                brandLogoRes = R.drawable.waterbridge_brand_logo,
backgroundRes = R.drawable.water_background_customer,
        backgroundImageAlpha = 0.12f,
    ) {
        ReferenceWelcomeCard(
            title = "안녕하세요!",
            subtitle = "정수기 상태 확인부터 안전 안내까지 쉽고 빠르게 도와드릴게요.",
            imageRes = R.drawable.waterbridge_brand_logo,
            palette = palette,
        )

        when {
            state.checkingBackend -> {
                ReferenceBackendStatusCard(
                    title = "서비스 준비 중",
                    message = "서비스를 시작할 수 있는지 확인하고 있어요.",
                    palette = palette,
                )
            }

            state.backendAvailable == true -> {
                ReferenceBackendStatusCard(
                    title = "서비스 이용 가능",
                    message = "바로 서비스를 시작할 수 있어요.",
                    palette = palette,
                )
            }

            else -> {
                ReferenceBackendStatusCard(
                    title = "연결을 확인해주세요",
                    message = "인터넷 연결을 확인한 뒤 다시 시도해주세요.",
                    palette = palette,
                    warning = true,
                    actionLabel = "다시 확인",
                    onAction = viewModel::checkBackend,
                )
            }
        }

        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            ReferenceGlassButton(
                text = "시작하기",
                palette = palette,
                onClick = viewModel::demoLogin,
                enabled = !state.submitting &&
                    state.backendAvailable == true,
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )
            ReferenceGlassButton(
                text = "서비스 둘러보기",
                palette = palette,
                onClick = viewModel::startOfflinePreview,
                enabled = !state.submitting,
                accent = false,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        if (state.submitting) {
            LoadingBlock("서비스를 시작하고 있어요")
        }

        state.error?.let {
            ErrorCard(it, onRetry = viewModel::demoLogin)
        }

        Text(
            "일부 기능은 연결 상태에 따라 이용이 제한될 수 있어요.",
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
            textAlign = TextAlign.Center,
        )
    }
}

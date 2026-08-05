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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceCompactBanner
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
    val palette = CustomerReferencePalette

    LaunchedEffect(state.authenticated) {
        if (state.authenticated) {
            onAuthenticated(state.offlinePreview)
        }
    }

    ReferenceDashboardScaffold(
        title = "정수기 딜러",
        roleLabel = "고객용",
        palette = palette,
    ) {
        ReferenceWelcomeCard(
            title = "안녕하세요!",
            subtitle = "정수기 상태 확인부터 안전 안내까지 쉽고 빠르게 도와드릴게요.",
            imageRes = R.drawable.dashboard_purifier,
            palette = palette,
        )

        when {
            state.checkingBackend -> {
                ReferenceCompactBanner(
                    title = "Backend 확인 중",
                    message = "Demo 로그인 가능 여부를 확인하고 있습니다.",
                    palette = palette,
                )
            }

            state.backendAvailable == true -> {
                ReferenceCompactBanner(
                    title = "Backend 연결됨",
                    message = "실제 Demo 인증으로 로그인할 수 있습니다.",
                    palette = palette,
                )
            }

            else -> {
                ReferenceCompactBanner(
                    title = "Backend 연결 확인 필요",
                    message = "대시보드 디자인은 오프라인 미리보기로 바로 확인할 수 있습니다.",
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
                text = "고객 Demo 로그인",
                palette = palette,
                onClick = viewModel::demoLogin,
                enabled = !state.submitting &&
                    state.backendAvailable == true,
                accent = state.backendAvailable == true,
                modifier = Modifier.fillMaxWidth(),
            )
            ReferenceGlassButton(
                text = "오프라인 대시보드 미리보기",
                palette = palette,
                onClick = viewModel::startOfflinePreview,
                enabled = !state.submitting,
                accent = state.backendAvailable != true,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        if (state.submitting) {
            LoadingBlock("Demo 로그인 중입니다")
        }

        state.error?.let {
            ErrorCard(it, onRetry = viewModel::demoLogin)
        }

        Text(
            "현재 Backend 계약에 존재하는 Demo 인증만 사용합니다. 제공되지 않은 기능은 임시 API로 표시하지 않습니다.",
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
        )
    }
}

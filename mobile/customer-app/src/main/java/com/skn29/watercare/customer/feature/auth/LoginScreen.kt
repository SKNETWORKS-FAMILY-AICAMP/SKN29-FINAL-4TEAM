package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun LoginScreen(onAuthenticated: (offlinePreview: Boolean) -> Unit) {
    val viewModel: AuthViewModel = viewModel(
        factory = VmFactory { _ ->
            AuthViewModel(
                WaterCareCore.authRepository,
                WaterCareCore.backendStatusRepository,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.authenticated) {
        if (state.authenticated) {
            onAuthenticated(state.offlinePreview)
        }
    }

    WaterCareScreen(title = "정수기 딜러") {
        LiquidGlassPanel(strong = true) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 190.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(9.dp),
                ) {
                    LiquidGlassPill("고객용")
                    Text(
                        "안녕하세요!",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        "정수기 상태 확인부터 안전 안내까지 쉽고 빠르게 도와드릴게요.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Image(
                    painter = painterResource(R.drawable.mascot_customer),
                    contentDescription = "정수기 딜러 고객 안내 캐릭터",
                    modifier = Modifier.size(145.dp),
                    contentScale = ContentScale.Fit,
                )
            }
        }

        LiquidGlassPanel {
            Text(
                "Backend 상태",
                fontWeight = FontWeight.ExtraBold,
            )
            when {
                state.checkingBackend -> {
                    LoadingBlock("Backend 연결 확인 중")
                }

                state.backendAvailable == true -> {
                    LiquidGlassPill("연결됨 · 실제 Demo 로그인 가능")
                }

                else -> {
                    Text(
                        "Backend 연결을 확인하지 못했습니다.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    LiquidGlassButton(
                        text = "연결 다시 확인",
                        onClick = viewModel::checkBackend,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }

        LiquidGlassButton(
            text = "고객 Demo 로그인",
            leadingIcon = "💧",
            onClick = viewModel::demoLogin,
            enabled = !state.submitting,
            accent = true,
            modifier = Modifier.fillMaxWidth(),
        )

        LiquidGlassButton(
            text = "오프라인 화면 미리보기",
            leadingIcon = "◇",
            onClick = viewModel::startOfflinePreview,
            enabled = !state.submitting,
            modifier = Modifier.fillMaxWidth(),
        )

        if (state.submitting) {
            LoadingBlock("Demo 로그인 중입니다")
        }
        state.error?.let {
            ErrorCard(it, onRetry = viewModel::demoLogin)
        }

        Text(
            "현재 Backend 계약에 존재하는 Demo 인증을 우선 사용합니다. 제공되지 않은 기능은 임시 API를 만들지 않습니다.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

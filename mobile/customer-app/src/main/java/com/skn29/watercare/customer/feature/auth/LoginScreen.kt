package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
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
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun LoginScreen(onAuthenticated: (offlinePreview: Boolean) -> Unit) {
    val viewModel: AuthViewModel = viewModel(
        factory = VmFactory { _ ->
            AuthViewModel(WaterCareCore.authRepository, WaterCareCore.backendStatusRepository)
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.authenticated) {
        if (state.authenticated) onAuthenticated(state.offlinePreview)
    }

    WaterCareScreen(title = "정수기 딜러") {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surfaceVariant,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().heightIn(min = 190.dp).padding(18.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Surface(shape = RoundedCornerShape(999.dp), color = MaterialTheme.colorScheme.tertiaryContainer) {
                        Text(
                            "고객용",
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 5.dp),
                            color = MaterialTheme.colorScheme.onTertiaryContainer,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    Text("안녕하세요!", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.ExtraBold)
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

        Card(
            shape = RoundedCornerShape(24.dp),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("Backend 상태", fontWeight = FontWeight.ExtraBold)
                when {
                    state.checkingBackend -> LoadingBlock("Backend 연결 확인 중")
                    state.backendAvailable == true -> AssistChip(
                        onClick = {},
                        label = { Text("연결됨 · 실제 Demo 로그인 가능") },
                    )
                    else -> AssistChip(
                        onClick = viewModel::checkBackend,
                        label = { Text("연결 안 됨 · 눌러서 다시 확인") },
                    )
                }
            }
        }

        Button(
            onClick = viewModel::demoLogin,
            enabled = !state.submitting,
            modifier = Modifier.fillMaxWidth().height(54.dp),
        ) {
            Text("고객 Demo 로그인", fontWeight = FontWeight.Bold)
        }

        OutlinedButton(
            onClick = viewModel::startOfflinePreview,
            enabled = !state.submitting,
            modifier = Modifier.fillMaxWidth().height(52.dp),
        ) {
            Text("오프라인 화면 미리보기")
        }

        if (state.submitting) LoadingBlock("Demo 로그인 중입니다")
        state.error?.let { ErrorCard(it, onRetry = viewModel::demoLogin) }

        Text(
            "현재 Backend 계약에 존재하는 Demo 인증을 우선 사용합니다. 제공되지 않은 기능은 임시 API를 만들지 않습니다.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

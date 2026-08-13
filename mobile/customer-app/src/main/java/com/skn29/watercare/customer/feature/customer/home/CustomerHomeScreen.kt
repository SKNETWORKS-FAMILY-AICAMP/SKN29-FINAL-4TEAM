package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceBottomItem
import com.skn29.watercare.core.ui.components.ReferenceDashboardScaffold
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.customer.BuildConfig
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory

@Composable
fun CustomerHomeScreen(
    offlinePreview: Boolean,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onLogout: () -> Unit,
) {
    val careRepository = if (offlinePreview) {
        FakeCustomerCareRepository(
            fixtureSubscriptionId =
                WaterCareCore.customerCareRuntimeConfig.fixtureSubscriptionId,
        )
    } else {
        WaterCareCore.customerCareRepository
    }

    val viewModel: CustomerHomeViewModel = viewModel(
        factory = VmFactory { _ ->
            CustomerHomeViewModel(
                authRepository = WaterCareCore.authRepository,
                careRepository = careRepository,
                subscriptionRepository = WaterCareCore.subscriptionRepository,
                backendStatusRepository = WaterCareCore.backendStatusRepository,
                runtimeConfig = WaterCareCore.customerCareRuntimeConfig,
                offlinePreview = offlinePreview,
            )
        }
    )

    val state by viewModel.state.collectAsStateWithLifecycle()

    CustomerHomeContent(
        state = state,
        onStartIntake = onStartIntake,
        onOpenGuidance = onOpenGuidance,
        onRetry = viewModel::load,
        onLogout = {
            viewModel.logout(onLogout)
        },
        showDeveloperTools = BuildConfig.SHOW_DEVELOPER_TOOLS,
    )
}

@Composable
fun CustomerHomeContent(
    state: CustomerHomeUiState,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onRetry: () -> Unit,
    onLogout: () -> Unit,
    onSelectSubscription: (String) -> Unit = {},
    showDeveloperTools: Boolean = false,
) {
    val palette = CustomerReferencePalette

    ReferenceDashboardScaffold(
        title = "WaterBridge",
        roleLabel = "WaterBridge Home Service",
        palette = palette,
        backgroundRes = R.drawable.water_splash_customer_r19,
        backgroundImageAlpha = 0.30f,
        brandLogoRes = R.drawable.waterbridge_brand_logo,
        bottomItems = listOf(
            ReferenceBottomItem(
                iconRes = R.drawable.ref_home,
                label = "홈",
                selected = true,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_care,
                label = "케어",
                enabled = false,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_notice,
                label = "문의",
                enabled = false,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_profile,
                label = "마이",
                enabled = false,
            ),
        ),
    ) {
        if (state.loading) {
            LoadingBlock("정수기 정보를 불러오고 있어요")
        }

        state.error?.let { message ->
            ErrorCard(
                message = customerHomeErrorMessage(message),
                onRetry = onRetry,
            )
        }

        state.home?.let { home ->
            CustomerCareHeroBanner(
                home = home,
                intakeAvailable = state.intakeAvailable,
                intakeUnavailableReason = state.intakeUnavailableReason,
                onStartIntake = onStartIntake,
                onOpenInquiry = { inquiryId ->
                    onOpenGuidance(
                        inquiryId,
                        MockScenario.NORMAL,
                    )
                },
            )
            CustomerProductInfoCard(
                home = home,
            )

            val fixtureGuidanceAvailable =
                state.offlinePreview ||
                    state.customerCareMode == CustomerCareMode.FAKE

            if (
                showDeveloperTools &&
                fixtureGuidanceAvailable
            ) {
                ReferenceGlassPanel(
                    palette = palette,
                ) {
                    Text(
                        "개발 검증 도구",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Black,
                    )

                    Column(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        MockScenario.entries.forEach { scenario ->
                            ReferenceGlassButton(
                                text = scenarioLabel(scenario),
                                palette = palette,
                                onClick = {
                                    onOpenGuidance(
                                        home.activeInquiry?.inquiryId
                                            ?: home.subscriptionId,
                                        scenario,
                                    )
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(
                                        "scenario_${scenario.name}"
                                    ),
                            )
                        }
                    }
                }
            }

            ReferenceGlassButton(
                text = "로그아웃",
                palette = palette,
                onClick = onLogout,
                enabled = !state.loggingOut,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

private fun customerHomeErrorMessage(
    message: String,
): String = when {
    message.contains("Backend", ignoreCase = true) ||
        message.contains("API", ignoreCase = true) ||
        message.contains("Remote", ignoreCase = true) ->
        "정수기 정보를 불러오지 못했어요. 잠시 후 다시 시도해주세요."

    else -> message
}

private fun scenarioLabel(
    scenario: MockScenario,
): String = when (scenario) {
    MockScenario.NORMAL -> "일반 안내"
    MockScenario.CAUTION -> "주의 안내"
    MockScenario.DANGER -> "위험 누수"
    MockScenario.NO_EVIDENCE -> "근거 없음"
    MockScenario.BACKEND_PROCESSING -> "처리 중"
    MockScenario.AI_FAILURE -> "AI 실패"
    MockScenario.NETWORK_FAILURE -> "네트워크 실패"
}
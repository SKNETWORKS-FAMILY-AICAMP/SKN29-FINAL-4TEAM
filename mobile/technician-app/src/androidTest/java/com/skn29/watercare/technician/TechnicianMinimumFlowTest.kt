package com.skn29.watercare.technician

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import org.junit.Rule
import org.junit.Test

class TechnicianMinimumFlowTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun backendUnavailable_loginScreenShowsExplicitFixturePreview() {
        composeRule.setContent {
            WaterCareTheme {
                TechnicianReferenceLogin(
                    state = TechnicianUiState(
                        checkingBackend = false,
                        backendAvailable = false,
                    ),
                    onLogin = {},
                    onOfflinePreview = {},
                    onRetryBackend = {},
                )
            }
        }

        composeRule.onNodeWithText("Backend 연결 확인 필요")
            .performScrollTo()
            .assertIsDisplayed()
        composeRule.onNodeWithTag("technicianOfflinePreview")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun offlineDashboard_isExplicitlyMarkedAsSyntheticFixture() {
        composeRule.setContent {
            WaterCareTheme {
                TechnicianReferenceDashboard(
                    state = TechnicianUiState(
                        checkingBackend = false,
                        backendAvailable = false,
                        user = technicianUser(),
                        offlinePreview = true,
                        visits = emptyList(),
                    ),
                    onVisitClick = {},
                    onRefresh = {},
                    onLogout = {},
                )
            }
        }

        composeRule.onNodeWithText("오프라인 합성 Fixture")
            .performScrollTo()
            .assertIsDisplayed()
        composeRule.onNodeWithText("현재 배정된 방문이 없습니다.")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun remoteDashboard_neverLabelsFixtureAsRealVisitData() {
        composeRule.setContent {
            WaterCareTheme {
                TechnicianReferenceDashboard(
                    state = TechnicianUiState(
                        checkingBackend = false,
                        backendAvailable = true,
                        user = technicianUser(),
                        offlinePreview = false,
                        visitRuntimeBlocked = true,
                        visits = emptyList(),
                        error = "방문 Runtime 미제공",
                    ),
                    onVisitClick = {},
                    onRefresh = {},
                    onLogout = {},
                )
            }
        }

        composeRule.onNodeWithText("실제 방문 API · BLOCKED_BY_BACKEND")
            .performScrollTo()
            .assertIsDisplayed()
    }

    private fun technicianUser() = UserData(
        id = "tech-id",
        displayName = "합성 기사",
        roleCode = "TECHNICIAN",
        isActive = true,
    )
}

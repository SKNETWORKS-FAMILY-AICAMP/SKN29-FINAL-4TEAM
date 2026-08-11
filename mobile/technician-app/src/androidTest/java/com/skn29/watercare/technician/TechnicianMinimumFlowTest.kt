package com.skn29.watercare.technician

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runAndroidComposeUiTest
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.technician.testing.ComposeTestActivity
import org.junit.Test

class TechnicianMinimumFlowTest {
    @Test
    @OptIn(ExperimentalTestApi::class)
    fun backendUnavailable_loginScreenShowsExplicitFixturePreview() = runAndroidComposeUiTest<ComposeTestActivity> {
        setContent {
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

        onNodeWithText("Backend 연결 확인 필요")
            .performScrollTo()
            .assertIsDisplayed()
        onNodeWithTag("technicianOfflinePreview")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun offlineDashboard_isExplicitlyMarkedAsSyntheticFixture() = runAndroidComposeUiTest<ComposeTestActivity> {
        setContent {
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

        onNodeWithText("오프라인 합성 Fixture")
            .performScrollTo()
            .assertIsDisplayed()
        onNodeWithText("현재 배정된 방문이 없습니다.")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun remoteDashboard_neverLabelsFixtureAsRealVisitData() = runAndroidComposeUiTest<ComposeTestActivity> {
        setContent {
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

        onNodeWithText("실제 방문 API · BLOCKED_BY_BACKEND")
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

package com.skn29.watercare.technician

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.technician.testing.ComposeTestActivity
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith


private class ManualComposeTestScope(
    private val delegate: ComposeTestRule,
    private val scenario: ActivityScenario<ComposeTestActivity>,
) : ComposeTestRule by delegate {
    fun setContent(
        content: @Composable () -> Unit,
    ) {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(Lifecycle.State.RESUMED)
        }

        scenario.onActivity { activity ->
            activity.setContent {
                content()
            }
        }

        delegate.waitForIdle()
    }
}
@RunWith(AndroidJUnit4::class)
class TechnicianMinimumFlowTest {
    @get:Rule
    val composeTestRule = createEmptyComposeRule()

    private fun runManualComposeUiTest(
        block: ManualComposeTestScope.() -> Unit,
    ) {
        val scenario = ActivityScenario.launch(ComposeTestActivity::class.java)
        try {
            if (scenario.state != Lifecycle.State.RESUMED) {
                scenario.moveToState(Lifecycle.State.RESUMED)
            }

            ManualComposeTestScope(
                delegate = composeTestRule,
                scenario = scenario,
            ).block()
        } finally {
            scenario.close()
        }
    }
    @Test
    @OptIn(ExperimentalTestApi::class)
    fun backendUnavailable_loginScreenShowsExplicitFixturePreview() = runManualComposeUiTest {
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
    fun offlineDashboard_isExplicitlyMarkedAsSyntheticFixture() = runManualComposeUiTest {
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

        onNodeWithText("오프라인 합성 데이터")
            .performScrollTo()
            .assertIsDisplayed()
        onNodeWithText("현재 배정된 방문이 없습니다.")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun remoteDashboard_neverLabelsFixtureAsRealVisitData() = runManualComposeUiTest {
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

        onNodeWithText("방문 API 연결 대기")
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

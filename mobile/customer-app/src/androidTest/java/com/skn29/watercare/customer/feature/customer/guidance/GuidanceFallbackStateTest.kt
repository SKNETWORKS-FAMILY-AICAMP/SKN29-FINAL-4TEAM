package com.skn29.watercare.customer.feature.customer.guidance

import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

private class GuidanceFallbackManualScope(
    private val delegate: ComposeTestRule,
    private val scenario: ActivityScenario<ComposeTestActivity>,
) : ComposeTestRule by delegate {
    fun setContent(
        content: @Composable () -> Unit,
    ) {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(
                Lifecycle.State.RESUMED
            )
        }

        scenario.onActivity { activity ->
            activity.setContent {
                content()
            }
        }

        delegate.waitForIdle()
    }
}

private fun SemanticsNodeInteraction.assertDoesNotExistCompat() {
    assertTrue(
        "화면에 존재하지 않아야 하는 기술 메시지가 표시되었습니다.",
        runCatching {
            fetchSemanticsNode()
        }.isFailure,
    )
}

@RunWith(AndroidJUnit4::class)
class GuidanceFallbackStateTest {
    @get:Rule
    val composeTestRule =
        createEmptyComposeRule()

    private fun runManual(
        block:
            GuidanceFallbackManualScope.() -> Unit,
    ) {
        val scenario =
            ActivityScenario.launch(
                ComposeTestActivity::class.java
            )

        try {
            if (
                scenario.state !=
                Lifecycle.State.RESUMED
            ) {
                scenario.moveToState(
                    Lifecycle.State.RESUMED
                )
            }

            GuidanceFallbackManualScope(
                delegate = composeTestRule,
                scenario = scenario,
            ).block()
        } finally {
            scenario.close()
        }
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun notReady_showsCustomerCopyAndHidesRawMessage() =
        runManual {
            setContent {
                WaterCareTheme {
                    GuidanceFailureStateContent(
                        state =
                            GuidanceUiState.NotReady(
                                message =
                                    "AI_GUIDANCE_NOT_READY raw backend detail",
                            ),
                        onRetry = {},
                    )
                }
            }

            waitForIdle()

            onNodeWithText(
                "맞춤 안내 준비 중"
            ).assertIsDisplayed()

            onNodeWithText(
                "맞춤 안내를 준비하고 있어요. 잠시 후 다시 확인해주세요."
            ).assertIsDisplayed()

            onNodeWithText(
                "AI_GUIDANCE_NOT_READY raw backend detail"
            ).assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun aiFailure_showsCustomerCopyAndHidesRawMessage() =
        runManual {
            setContent {
                WaterCareTheme {
                    GuidanceFailureStateContent(
                        state =
                            GuidanceUiState.AiFailure(
                                message =
                                    "AI_PROVIDER_TIMEOUT internal detail",
                                retryable = true,
                            ),
                        onRetry = {},
                    )
                }
            }

            waitForIdle()

            onNodeWithText(
                "지금은 안내를 준비하지 못했어요"
            ).assertIsDisplayed()

            onNodeWithText(
                "지금은 맞춤 안내를 준비하지 못했어요. 잠시 후 다시 시도해주세요."
            ).assertIsDisplayed()

            onNodeWithText(
                "AI_PROVIDER_TIMEOUT internal detail"
            ).assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun networkFailure_showsCustomerCopyAndHidesRawMessage() =
        runManual {
            setContent {
                WaterCareTheme {
                    GuidanceFailureStateContent(
                        state =
                            GuidanceUiState.NetworkFailure(
                                message =
                                    "java.net.SocketTimeoutException raw detail",
                                retryable = true,
                            ),
                        onRetry = {},
                    )
                }
            }

            waitForIdle()

            onNodeWithText(
                "연결이 잠시 불안정해요"
            ).assertIsDisplayed()

            onNodeWithText(
                "서비스에 연결할 수 없어요. 잠시 후 다시 시도해주세요."
            ).assertIsDisplayed()

            onNodeWithText(
                "java.net.SocketTimeoutException raw detail"
            ).assertDoesNotExistCompat()
        }
}
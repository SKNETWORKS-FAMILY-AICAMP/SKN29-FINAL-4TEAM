package com.skn29.watercare.customer

import android.content.pm.ActivityInfo
import android.content.res.Configuration
import androidx.activity.compose.setContent
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextReplacement
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeScreen
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerDraftRotationPhysicalTest {

    @get:Rule
    val composeTestRule = createEmptyComposeRule()

    private fun ensureResumed(
        scenario: ActivityScenario<ComposeTestActivity>,
    ) {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(Lifecycle.State.RESUMED)
        }
    }

    private fun renderIntake(
        scenario: ActivityScenario<ComposeTestActivity>,
    ) {
        ensureResumed(scenario)

        scenario.onActivity { activity ->
            activity.setContent {
                WaterCareTheme {
                    SymptomIntakeScreen(
                        subscriptionId = "rotation-physical-test",
                        onBack = {},
                        onCompleted = {},
                        onAuthExpired = {},
                    )
                }
            }
        }

        composeTestRule.waitForIdle()
    }

    private fun requestOrientation(
        scenario: ActivityScenario<ComposeTestActivity>,
        orientation: Int,
    ) {
        ensureResumed(scenario)

        scenario.onActivity { activity ->
            activity.requestedOrientation = orientation
        }

        Thread.sleep(1500)

        ensureResumed(scenario)
    }

    private fun currentOrientation(
        scenario: ActivityScenario<ComposeTestActivity>,
    ): Int {
        ensureResumed(scenario)

        var orientation =
            Configuration.ORIENTATION_UNDEFINED

        scenario.onActivity { activity ->
            orientation =
                activity.resources.configuration.orientation
        }

        return orientation
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun symptomIntake_typedDraft_survivesRotation() {
        val scenario =
            ActivityScenario.launch(
                ComposeTestActivity::class.java
            )

        try {
            requestOrientation(
                scenario,
                ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,
            )

            renderIntake(scenario)

            assertTrue(
                currentOrientation(scenario) ==
                    Configuration.ORIENTATION_PORTRAIT
            )

            composeTestRule
                .onNodeWithTag("rawText")
                .performScrollTo()
                .assertIsDisplayed()
                .performClick()
                .performTextReplacement(
                    "회전 전 작성한 고객 증상 내용"
                )

            composeTestRule.waitForIdle()

            composeTestRule
                .onNodeWithTag("rawText")
                .assertTextContains(
                    "회전 전 작성한 고객 증상 내용",
                    substring = true,
                )

            requestOrientation(
                scenario,
                ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE,
            )

            renderIntake(scenario)

            assertTrue(
                currentOrientation(scenario) ==
                    Configuration.ORIENTATION_LANDSCAPE
            )

            composeTestRule
                .onNodeWithTag("rawText")
                .performScrollTo()
                .assertIsDisplayed()
                .assertTextContains(
                    "회전 전 작성한 고객 증상 내용",
                    substring = true,
                )
        } finally {
            runCatching {
                ensureResumed(scenario)

                scenario.onActivity { activity ->
                    activity.requestedOrientation =
                        ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
                }
            }

            scenario.close()
        }
    }
}
package com.skn29.watercare.customer

import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeContent
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeUiState
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerKeyboardCtaPhysicalTest {

    @get:Rule
    val composeTestRule = createEmptyComposeRule()

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun symptomIntake_keyboardInput_keepsSubmitCtaReachable() {
        val scenario =
            ActivityScenario.launch(ComposeTestActivity::class.java)

        try {
            scenario.onActivity { activity ->
                activity.setContent {
                    var rawText by remember {
                        mutableStateOf("")
                    }

                    WaterCareTheme {
                        SymptomIntakeContent(
                            state = SymptomIntakeUiState(
                                rawText = rawText,
                            ),
                            onBack = {},
                            onEntryModeChange = { _: EntryMode -> },
                            onToggleSymptom = { _: SymptomTopic -> },
                            onRawTextChange = {
                                rawText = it
                            },
                            onOccurrenceConditionChange = { _: String -> },
                            onDisplayTextChange = { _: String -> },
                            onScenarioChange = { _: MockScenario? -> },
                            onRetry = {},
                            onSubmit = {},
                        )
                    }
                }
            }

            composeTestRule.waitForIdle()

            val input =
                composeTestRule
                    .onNodeWithTag("rawText")
                    .performScrollTo()
                    .assertIsDisplayed()
                    .performClick()

            input.performTextInput(
                "keyboard CTA test"
            )

            composeTestRule.waitForIdle()

            input.assertTextContains(
                "keyboard CTA test",
                substring = true,
            )

            composeTestRule.waitUntil(
                timeoutMillis = 5_000,
            ) {
                var imeVisible = false

                scenario.onActivity { activity ->
                    imeVisible =
                        ViewCompat
                            .getRootWindowInsets(
                                activity.window.decorView
                            )
                            ?.isVisible(
                                WindowInsetsCompat.Type.ime()
                            ) == true
                }

                imeVisible
            }

            var imeVisible = false

            scenario.onActivity { activity ->
                imeVisible =
                    ViewCompat
                        .getRootWindowInsets(
                            activity.window.decorView
                        )
                        ?.isVisible(
                            WindowInsetsCompat.Type.ime()
                        ) == true
            }

            assertTrue(
                "실기기 키보드가 표시되어야 합니다.",
                imeVisible,
            )

            composeTestRule
                .onNodeWithTag("submitIntake")
                .performScrollTo()
                .assertIsDisplayed()
                .assertIsEnabled()
        } finally {
            scenario.close()
        }
    }
}
package com.skn29.watercare.customer

import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.CustomerInquiryQuestionOption
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.feature.customer.guidance.FollowUpDraft
import com.skn29.watercare.customer.feature.customer.guidance.FollowUpQuestionsSection
import com.skn29.watercare.customer.feature.customer.guidance.FollowUpUiState
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

private class FollowUpManualScope(
    private val delegate: ComposeTestRule,
    private val scenario: ActivityScenario<ComposeTestActivity>,
) : ComposeTestRule by delegate {
    fun setContent(content: @Composable () -> Unit) {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(Lifecycle.State.RESUMED)
        }
        scenario.onActivity { activity -> activity.setContent { content() } }
        delegate.waitForIdle()
    }
}


private fun androidx.compose.ui.test.SemanticsNodeInteraction.assertDoesNotExistCompat() {
    assertTrue(
        "화면에 존재하지 않아야 하는 UI가 표시되었습니다.",
        runCatching {
            fetchSemanticsNode()
        }.isFailure,
    )
}
@RunWith(AndroidJUnit4::class)
class FollowUpQuestionsSectionTest {
    @get:Rule
    val composeTestRule = createEmptyComposeRule()

    private fun runManual(block: FollowUpManualScope.() -> Unit) {
        val scenario = ActivityScenario.launch(ComposeTestActivity::class.java)
        try {
            if (scenario.state != Lifecycle.State.RESUMED) {
                scenario.moveToState(Lifecycle.State.RESUMED)
            }
            FollowUpManualScope(composeTestRule, scenario).block()
        } finally {
            scenario.close()
        }
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun emptyQuestions_doesNotRenderEmptyCard() = runManual {
        setContent {
            WaterCareTheme {
                FollowUpQuestionsSection(
                    state = FollowUpUiState.Empty(snapshot(2)),
                    onTextChange = { _, _ -> },
                    onSelectOption = { _, _ -> },
                    onSubmit = {},
                    onRetryConflict = {},
                    onReload = {},
                )
            }
        }

        waitForIdle()

        onNodeWithTag("followUpEmpty")
            .assertDoesNotExistCompat()
    }
    @Test
    @OptIn(ExperimentalTestApi::class)
    fun loading_showsCustomerFriendlyProgress() = runManual {
        setContent {
            WaterCareTheme {
                FollowUpQuestionsSection(
                    state = FollowUpUiState.Loading,
                    onTextChange = { _, _ -> },
                    onSelectOption = { _, _ -> },
                    onSubmit = {},
                    onRetryConflict = {},
                    onReload = {},
                )
            }
        }

        waitForIdle()

        onNodeWithText("몇 가지만 더 확인할게요")
            .assertIsDisplayed()
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun retryableError_hidesRawMessageAndShowsCustomerCopy() = runManual {
        setContent {
            WaterCareTheme {
                FollowUpQuestionsSection(
                    state = FollowUpUiState.Error(
                        message = "Backend API timeout",
                        code = "NETWORK_ERROR",
                        httpStatus = 500,
                        retryable = true,
                    ),
                    onTextChange = { _, _ -> },
                    onSelectOption = { _, _ -> },
                    onSubmit = {},
                    onRetryConflict = {},
                    onReload = {},
                )
            }
        }

        waitForIdle()

        onNodeWithText(
            "추가 질문을 확인하는 중 문제가 생겼어요. 잠시 후 다시 시도해주세요."
        ).assertIsDisplayed()

        onNodeWithText("Backend API timeout")
            .assertDoesNotExistCompat()
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun completedForm_enablesExplicitSubmit() = runManual {
        var submitted = false
        setContent {
            WaterCareTheme {
                FollowUpQuestionsSection(
                    state = FollowUpUiState.Form(
                        snapshot = snapshot(2),
                        questions = listOf(
                            CustomerInquiryQuestion(
                                questionId = TEXT_ID,
                                questionType = "FREE_TEXT",
                                prompt = "언제부터인가요?",
                                required = true,
                                options = emptyList(),
                            ),
                            CustomerInquiryQuestion(
                                questionId = CHOICE_ID,
                                questionType = "SINGLE_CHOICE",
                                prompt = "필터를 교체했나요?",
                                required = true,
                                options = listOf(
                                    CustomerInquiryQuestionOption("YES", "예"),
                                    CustomerInquiryQuestionOption("NO", "아니오"),
                                ),
                            ),
                        ),
                        drafts = mapOf(
                            TEXT_ID to FollowUpDraft(text = "이틀 전부터입니다."),
                            CHOICE_ID to FollowUpDraft(selectedOption = "YES"),
                        ),
                    ),
                    onTextChange = { _, _ -> },
                    onSelectOption = { _, _ -> },
                    onSubmit = { submitted = true },
                    onRetryConflict = {},
                    onReload = {},
                )
            }
        }
        waitForIdle()
        onNodeWithTag("followUpText_$TEXT_ID").assertIsDisplayed()
        onNodeWithTag("followUpOption_${CHOICE_ID}_0").assertIsDisplayed()
        onNodeWithTag("submitFollowUpAnswers")
            .assertIsDisplayed()
            .assertIsEnabled()
            .performClick()
        assertTrue(submitted)
    }

    private fun snapshot(version: Int) = CustomerInquirySnapshot(
        inquiryId = INQUIRY_ID,
        statusCode = "QUESTIONNAIRE_IN_PROGRESS",
        stateVersion = version,
        subscriptionId = SUBSCRIPTION_ID,
        productModelCode = "WPUJAC104DWH",
        allowedActions = if (version < 4) {
            listOf(
                AllowedAction(
                    code = InquiryActionLabels.SUBMIT_ANSWERS,
                    label = "추가 답변 제출",
                )
            )
        } else {
            emptyList()
        },
        updatedAtRfc3339 = "2026-08-11T15:10:00+09:00",
    )

    companion object {
        private const val INQUIRY_ID = "00000000-0000-4000-8000-000000000301"
        private const val SUBSCRIPTION_ID = "00000000-0000-4000-8000-000000000101"
        private const val TEXT_ID = "00000000-0000-4000-8000-000000000401"
        private const val CHOICE_ID = "00000000-0000-4000-8000-000000000402"
    }
}

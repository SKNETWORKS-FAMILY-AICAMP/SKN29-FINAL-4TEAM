package com.skn29.watercare.customer

import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.feature.customer.guidance.CancelInquiryUiState
import com.skn29.watercare.customer.feature.customer.guidance.FollowUpCancelSection
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

private class FollowUpCancelManualScope(
    private val delegate: ComposeTestRule,
    private val scenario: ActivityScenario<ComposeTestActivity>,
) : ComposeTestRule by delegate {
    fun setContent(
        content: @Composable () -> Unit,
    ) {
        if (
            scenario.state !=
                Lifecycle.State.RESUMED
        ) {
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

private fun SemanticsNodeInteraction
    .assertDoesNotExistCompat() {
    assertTrue(
        "해당 요소는 화면에 표시되지 않아야 합니다.",
        runCatching {
            fetchSemanticsNode()
        }.isFailure,
    )
}

@RunWith(AndroidJUnit4::class)
class FollowUpCancelSectionTest {
    @get:Rule
    val composeTestRule =
        createEmptyComposeRule()

    private fun runManual(
        block:
            FollowUpCancelManualScope.() -> Unit,
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

            FollowUpCancelManualScope(
                composeTestRule,
                scenario,
            ).block()
        } finally {
            scenario.close()
        }
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun allowedQuestionnaire_showsCancelButton() =
        runManual {
            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Idle,
                        onConfirmCancel = {},
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "cancelInquiry"
            )
                .assertIsDisplayed()

            onNodeWithText(
                "진행 중인 문의는 상황에 따라 취소할 수 있어요."
            ).assertIsDisplayed()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun cancelDialog_dismiss_doesNotConfirm() =
        runManual {
            var confirmed = false

            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Idle,
                        onConfirmCancel = {
                            confirmed = true
                        },
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "cancelInquiry"
            ).performClick()

            onNodeWithText(
                "문의를 취소할까요?"
            ).assertIsDisplayed()

            onNodeWithText(
                "취소 후에는 현재 문의 흐름을 계속 진행할 수 없습니다."
            ).assertIsDisplayed()

            onNodeWithTag(
                "dismissCancelFollowUpInquiry"
            )
                .assertIsDisplayed()
                .performClick()

            assertFalse(confirmed)

            onNodeWithTag(
                "confirmCancelFollowUpInquiry"
            )
                .assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun cancelDialog_confirm_usesSnapshotVersion() =
        runManual {
            var confirmedVersion:
                Int? = null

            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                version = 2,
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Idle,
                        onConfirmCancel = {
                            confirmedVersion = it
                        },
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "cancelInquiry"
            ).performClick()

            onNodeWithTag(
                "confirmCancelFollowUpInquiry"
            )
                .assertIsDisplayed()
                .performClick()

            assertEquals(
                2,
                confirmedVersion,
            )
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun cancelledSuccess_showsCancelledState() =
        runManual {
            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Success(
                                state =
                                    "CANCELLED",
                                stateVersion = 3,
                                idempotentReplay =
                                    false,
                            ),
                        onConfirmCancel = {},
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "cancelledFollowUpInquiry"
            )
                .assertIsDisplayed()

            onNodeWithText(
                "문의가 취소됐어요."
            ).assertIsDisplayed()

            onNodeWithTag(
                "cancelInquiry"
            )
                .assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun conflictWithCancelAction_showsRetry() =
        runManual {
            var retried = false

            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Conflict(
                                message =
                                    "state changed",
                                currentStatus =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                currentStateVersion =
                                    3,
                                allowedActions =
                                    listOf(
                                        AllowedAction(
                                            code =
                                                InquiryActionLabels
                                                    .CANCEL_INQUIRY
                                        )
                                    ),
                            ),
                        onConfirmCancel = {},
                        onRetryConflict = {
                            retried = true
                        },
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "retryFollowUpCancelAfterConflict"
            )
                .assertIsDisplayed()
                .performClick()

            assertTrue(retried)
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun conflictWithoutCancelAction_hidesRetry() =
        runManual {
            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Conflict(
                                message =
                                    "already changed",
                                currentStatus =
                                    "CANCELLED",
                                currentStateVersion =
                                    3,
                                allowedActions =
                                    emptyList(),
                            ),
                        onConfirmCancel = {},
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "retryFollowUpCancelAfterConflict"
            )
                .assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun aiGuidance_hidesCancelButtonEvenWhenActionInjected() =
        runManual {
            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "AI_GUIDANCE",
                                allowCancel =
                                    true,
                            ),
                        cancelState =
                            CancelInquiryUiState.Idle,
                        onConfirmCancel = {},
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "cancelInquiry"
            )
                .assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun missingCancelAction_hidesCancelButton() =
        runManual {
            setContent {
                WaterCareTheme {
                    FollowUpCancelSection(
                        snapshot =
                            snapshot(
                                status =
                                    "QUESTIONNAIRE_IN_PROGRESS",
                                allowCancel =
                                    false,
                            ),
                        cancelState =
                            CancelInquiryUiState.Idle,
                        onConfirmCancel = {},
                        onRetryConflict = {},
                        onRetryFailure = {},
                        onReloadLatest = {},
                        onCancelledDone = {},
                    )
                }
            }

            onNodeWithTag(
                "cancelInquiry"
            )
                .assertDoesNotExistCompat()
        }

    private fun snapshot(
        status: String,
        version: Int = 2,
        allowCancel: Boolean,
    ) =
        CustomerInquirySnapshot(
            inquiryId =
                INQUIRY_ID,
            statusCode =
                status,
            stateVersion =
                version,
            subscriptionId =
                SUBSCRIPTION_ID,
            productModelCode =
                "WPUJAC104DWH",
            allowedActions =
                if (allowCancel) {
                    listOf(
                        AllowedAction(
                            code =
                                InquiryActionLabels
                                    .CANCEL_INQUIRY,
                            label =
                                "문의 취소",
                        )
                    )
                } else {
                    emptyList()
                },
            updatedAtRfc3339 =
                "2026-08-18T19:25:42+09:00",
        )

    companion object {
        private const val INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"

        private const val SUBSCRIPTION_ID =
            "00000000-0000-4000-8000-000000000101"
    }
}

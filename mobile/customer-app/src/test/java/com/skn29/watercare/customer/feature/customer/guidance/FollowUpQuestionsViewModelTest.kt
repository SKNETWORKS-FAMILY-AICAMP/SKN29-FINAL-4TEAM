package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class FollowUpQuestionsViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun emptyQuestions_isExplicitEmptyState() = runTest(mainDispatcherRule.dispatcher) {
        val remote = QueueRepository(
            snapshots = mutableListOf(
                ApiResult.Success(
                    snapshot(
                        version = 2,
                        allowSubmit = false,
                        statusCode = "AI_GUIDANCE",
                    )
                )
            ),
            questions = mutableListOf(
                ApiResult.Success(
                    questions(2, emptyList())
                )
            ),
        )
        val viewModel = newViewModel(remote)
        advanceUntilIdle()
        assertTrue(viewModel.state.value is FollowUpUiState.Empty)
        val event = viewModel.navigationEvents.first() as FollowUpNavigationEvent.OpenGuidance
        assertEquals(2, event.snapshot.stateVersion)
    }

    @Test
    fun submitSuccess_reloadsSnapshotAndQuestions() = runTest(mainDispatcherRule.dispatcher) {
        val remote = QueueRepository(
            snapshots = mutableListOf(
                ApiResult.Success(snapshot(2)),
                ApiResult.Success(
                    snapshot(
                        version = 3,
                        allowSubmit = false,
                        statusCode = "AI_GUIDANCE",
                    )
                ),
            ),
            questions = mutableListOf(
                ApiResult.Success(questions(2, listOf(freeTextQuestion()))),
                ApiResult.Success(questions(3, emptyList())),
            ),
            submits = mutableListOf(ApiResult.Success(submitResult(3))),
        )
        val viewModel = newViewModel(remote)
        advanceUntilIdle()
        viewModel.updateText(QUESTION_ID, "이틀 전부터 발생했습니다.")
        viewModel.submitAnswers()
        advanceUntilIdle()

        val state = viewModel.state.value as FollowUpUiState.Success
        assertEquals(3, state.snapshot.stateVersion)
        assertTrue(state.questions.isEmpty())
        assertEquals(listOf(2), remote.submittedVersions)
        assertEquals("이틀 전부터 발생했습니다.", remote.submittedAnswers.single().single().answerText)
        val event = viewModel.navigationEvents.first() as FollowUpNavigationEvent.OpenGuidance
        assertEquals(3, event.snapshot.stateVersion)
    }

    @Test
    fun rapidDoubleSubmit_callsRepositoryOnce() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote = QueueRepository(
                snapshots = mutableListOf(
                    ApiResult.Success(snapshot(2)),
                    ApiResult.Success(snapshot(3)),
                ),
                questions = mutableListOf(
                    ApiResult.Success(
                        questions(
                            2,
                            listOf(freeTextQuestion()),
                        )
                    ),
                    ApiResult.Success(
                        questions(3, emptyList())
                    ),
                ),
                submits = mutableListOf(
                    ApiResult.Success(submitResult(3))
                ),
            )

            val viewModel = newViewModel(remote)
            advanceUntilIdle()

            viewModel.updateText(
                QUESTION_ID,
                "빠른 연속 제출 테스트",
            )

            viewModel.submitAnswers()
            viewModel.submitAnswers()

            assertTrue(
                viewModel.state.value is
                    FollowUpUiState.Submitting
            )

            advanceUntilIdle()

            assertEquals(1, remote.submittedVersions.size)
            assertEquals(listOf(2), remote.submittedVersions)
        }

    @Test
    fun stale409_preservesInputAndExplicitRetryUsesLatestVersion() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote = QueueRepository(
                snapshots = mutableListOf(
                    ApiResult.Success(snapshot(2)),
                    ApiResult.Success(snapshot(3)),
                    ApiResult.Success(snapshot(4)),
                ),
                questions = mutableListOf(
                    ApiResult.Success(questions(2, listOf(freeTextQuestion()))),
                    ApiResult.Success(questions(3, listOf(freeTextQuestion()))),
                    ApiResult.Success(questions(4, emptyList())),
                ),
                submits = mutableListOf(
                    ApiResult.Failure(
                        code = "STATE-CONFLICT-01",
                        message = "문의 상태가 변경되었습니다.",
                        httpStatus = 409,
                        conflict = StateConflictSnapshot(
                            currentStatus = "QUESTIONNAIRE_IN_PROGRESS",
                            currentStateVersion = 3,
                            allowedActions = listOf(
                                AllowedAction(code = InquiryActionLabels.SUBMIT_ANSWERS)
                            ),
                        ),
                    ),
                    ApiResult.Success(submitResult(4)),
                ),
            )
            val viewModel = newViewModel(remote)
            advanceUntilIdle()
            viewModel.updateText(QUESTION_ID, "작성 중인 답변")
            viewModel.submitAnswers()
            advanceUntilIdle()

            val conflict = viewModel.state.value as FollowUpUiState.Conflict
            assertEquals("작성 중인 답변", conflict.drafts[QUESTION_ID]?.text)
            assertTrue(conflict.canRetry)
            assertEquals(3, conflict.snapshot.stateVersion)

            viewModel.retryAfterConflict()
            advanceUntilIdle()
            assertTrue(viewModel.state.value is FollowUpUiState.Success)
            assertEquals(listOf(2, 3), remote.submittedVersions)
        }

    @Test
    fun notFound404_usesUniformErrorAndDoesNotKeepRemoteForm() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote = QueueRepository(
                snapshots = mutableListOf(ApiResult.Success(snapshot(2))),
                questions = mutableListOf(
                    ApiResult.Success(questions(2, listOf(freeTextQuestion())))
                ),
                submits = mutableListOf(
                    ApiResult.Failure(
                        code = "RESOURCE_NOT_FOUND",
                        message = "요청한 정보를 찾을 수 없습니다.",
                        httpStatus = 404,
                    )
                ),
            )
            val viewModel = newViewModel(remote)
            advanceUntilIdle()
            viewModel.updateText(QUESTION_ID, "작성 중 입력")
            viewModel.submitAnswers()
            advanceUntilIdle()

            val error = viewModel.state.value as FollowUpUiState.Error
            assertEquals(404, error.httpStatus)
            assertEquals("RESOURCE_NOT_FOUND", error.code)
            assertEquals(null, error.snapshot)
            assertTrue(error.questions.isEmpty())
            assertTrue(error.drafts.isEmpty())
        }

    @Test
    fun duplicateEvent_requiresInputChangeBeforeSubmitIsAvailableAgain() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote = QueueRepository(
                snapshots = mutableListOf(ApiResult.Success(snapshot(2))),
                questions = mutableListOf(
                    ApiResult.Success(questions(2, listOf(freeTextQuestion())))
                ),
                submits = mutableListOf(
                    ApiResult.Failure(
                        code = "DUPLICATE-EVENT-01",
                        message = "동일 멱등 Key 충돌",
                        httpStatus = 409,
                    )
                ),
            )
            val viewModel = newViewModel(remote)
            advanceUntilIdle()
            viewModel.updateText(QUESTION_ID, "첫 입력")
            viewModel.submitAnswers()
            advanceUntilIdle()

            assertTrue(
                viewModel.state.value is FollowUpUiState.DuplicateConflict
            )
            viewModel.updateText(QUESTION_ID, "사용자가 수정한 입력")
            assertTrue(viewModel.state.value is FollowUpUiState.Form)
        }


    @Test
    fun missingSubmitAction_blocksSubmissionAndPreservesDraft() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote = QueueRepository(
                snapshots = mutableListOf(
                    ApiResult.Success(snapshot(2, allowSubmit = false))
                ),
                questions = mutableListOf(
                    ApiResult.Success(
                        questions(2, listOf(freeTextQuestion()))
                    )
                ),
            )
            val viewModel = newViewModel(remote)
            advanceUntilIdle()
            viewModel.updateText(
                QUESTION_ID,
                "Backend 허용 행동이 없는 상태의 입력",
            )
            viewModel.submitAnswers()
            advanceUntilIdle()

            val error =
                viewModel.state.value as FollowUpUiState.Error
            assertEquals("ACTION_NOT_ALLOWED", error.code)
            assertEquals(
                "Backend 허용 행동이 없는 상태의 입력",
                error.drafts[QUESTION_ID]?.text,
            )
            assertTrue(remote.submittedVersions.isEmpty())
        }

    @Test
    fun validation422_preservesDraftForUserCorrection() = runTest(mainDispatcherRule.dispatcher) {
        val remote = QueueRepository(
            snapshots = mutableListOf(ApiResult.Success(snapshot(2))),
            questions = mutableListOf(
                ApiResult.Success(questions(2, listOf(freeTextQuestion())))
            ),
            submits = mutableListOf(
                ApiResult.Failure(
                    code = "INVALID_FOLLOWUP_ANSWERS",
                    message = "답변을 확인해 주세요.",
                    httpStatus = 422,
                )
            ),
        )
        val viewModel = newViewModel(remote)
        advanceUntilIdle()
        viewModel.updateText(QUESTION_ID, "유지되어야 하는 입력")
        viewModel.submitAnswers()
        advanceUntilIdle()

        val error = viewModel.state.value as FollowUpUiState.Error
        assertEquals(422, error.httpStatus)
        assertEquals("유지되어야 하는 입력", error.drafts[QUESTION_ID]?.text)
    }

    private fun newViewModel(remote: CustomerInquiryRepository) = FollowUpQuestionsViewModel(
        inquiryId = INQUIRY_ID,
        repository = remote,
    )

    private fun snapshot(
        version: Int,
        allowSubmit: Boolean = version < 4,
        statusCode: String = "QUESTIONNAIRE_IN_PROGRESS",
    ) = CustomerInquirySnapshot(
        inquiryId = INQUIRY_ID,
        statusCode = statusCode,
        stateVersion = version,
        subscriptionId = SUBSCRIPTION_ID,
        productModelCode = "WPUJAC104DWH",
        allowedActions = if (allowSubmit) {
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

    private fun questions(version: Int, items: List<CustomerInquiryQuestion>) =
        CustomerInquiryQuestions(INQUIRY_ID, version, items)

    private fun freeTextQuestion() = CustomerInquiryQuestion(
        questionId = QUESTION_ID,
        questionType = "FREE_TEXT",
        prompt = "언제부터 증상이 시작되었나요?",
        required = true,
        options = emptyList(),
    )

    private fun submitResult(version: Int) = SubmitFollowUpAnswersResult(
        message = "Follow-up answers were saved.",
        inquiryId = INQUIRY_ID,
        statusCode = "QUESTIONNAIRE_IN_PROGRESS",
        stateVersion = version,
        allowedActions = listOf(AllowedAction(code = InquiryActionLabels.SUBMIT_ANSWERS)),
        idempotentReplay = false,
    )

    private class QueueRepository(
        private val snapshots: MutableList<ApiResult<CustomerInquirySnapshot>>,
        private val questions: MutableList<ApiResult<CustomerInquiryQuestions>>,
        private val submits: MutableList<ApiResult<SubmitFollowUpAnswersResult>> = mutableListOf(),
    ) : CustomerInquiryRepository {
        val submittedVersions = mutableListOf<Int>()
        val submittedAnswers = mutableListOf<List<FollowUpAnswer>>()

        override suspend fun snapshot(inquiryId: String) = snapshots.removeAt(0)
        override suspend fun questions(inquiryId: String) = questions.removeAt(0)
        override suspend fun submitAnswers(
            inquiryId: String,
            stateVersion: Int,
            answers: List<FollowUpAnswer>,
        ): ApiResult<SubmitFollowUpAnswersResult> {
            submittedVersions += stateVersion
            submittedAnswers += listOf(answers)
            return submits.removeAt(0)
        }
    }

    companion object {
        private const val INQUIRY_ID = "00000000-0000-4000-8000-000000000301"
        private const val SUBSCRIPTION_ID = "00000000-0000-4000-8000-000000000101"
        private const val QUESTION_ID = "00000000-0000-4000-8000-000000000401"
    }
}

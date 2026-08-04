package com.skn29.watercare.customer.feature.customer.intake

import androidx.lifecycle.SavedStateHandle
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SymptomIntakeRequest
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.repository.CustomerCareRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SymptomIntakeViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun failedSubmission_keepsInputAndAllowsRetry() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = SymptomIntakeViewModel(
                subscriptionId = "subscription",
                repository = failureRepository(
                    ApiResult.Failure(
                        code = "NETWORK_ERROR",
                        message = "network",
                        retryable = true,
                    )
                ),
                savedStateHandle = SavedStateHandle(),
            )
            viewModel.updateRawText("입력 유지 테스트")
            viewModel.submit()
            advanceUntilIdle()

            assertEquals("입력 유지 테스트", viewModel.state.value.rawText)
            assertFalse(viewModel.state.value.isSubmitting)
            assertNotNull(viewModel.state.value.globalError)
            assertEquals(
                IntakeErrorKind.NETWORK,
                viewModel.state.value.errorKind,
            )
            assertTrue(viewModel.state.value.retryable)
        }

    @Test
    fun savedStateHandle_restoresOnlyCustomerDraftInput() {
        val handle = SavedStateHandle()
        val first = SymptomIntakeViewModel(
            subscriptionId = "subscription",
            repository = unusedRepository(),
            savedStateHandle = handle,
        )

        first.toggleSymptom(SymptomTopic.LOW_FLOW)
        first.updateRawText("화면 재생성 입력")
        first.updateOccurrenceCondition("냉수 출수 시")
        first.updateDisplayText("E01")
        first.updateEntryMode(EntryMode.CARE_PRECHECK)
        first.updateScenario(MockScenario.CAUTION)

        val recreated = SymptomIntakeViewModel(
            subscriptionId = "subscription",
            repository = unusedRepository(),
            savedStateHandle = handle,
        )
        val state = recreated.state.value

        assertEquals(setOf(SymptomTopic.LOW_FLOW), state.selectedSymptoms)
        assertEquals("화면 재생성 입력", state.rawText)
        assertEquals("냉수 출수 시", state.occurrenceCondition)
        assertEquals("E01", state.displayText)
        assertEquals(EntryMode.CARE_PRECHECK, state.entryMode)
        assertEquals(MockScenario.CAUTION, state.forcedScenario)
        assertFalse(state.isSubmitting)
        assertNull(state.completed)
        assertNull(state.globalError)
    }

    @Test
    fun successfulSubmission_clearsPersistedDraft() =
        runTest(mainDispatcherRule.dispatcher) {
            val handle = SavedStateHandle()
            val success = IntakeSubmission(
                inquiryId = "inquiry",
                inquiryCode = "INQ-001",
                guidanceScenario = MockScenario.BACKEND_PROCESSING.name,
                statusCode = "QUESTIONNAIRE_IN_PROGRESS",
                stateVersion = 2,
            )
            val viewModel = SymptomIntakeViewModel(
                subscriptionId = "subscription",
                repository = successRepository(success),
                savedStateHandle = handle,
            )

            viewModel.updateRawText("제출 성공 후 제거")
            viewModel.submit()
            advanceUntilIdle()

            assertEquals(success, viewModel.state.value.completed)

            val recreated = SymptomIntakeViewModel(
                subscriptionId = "subscription",
                repository = unusedRepository(),
                savedStateHandle = handle,
            )
            assertEquals("", recreated.state.value.rawText)
            assertTrue(recreated.state.value.selectedSymptoms.isEmpty())
        }

    @Test
    fun stateConflict_keepsInputAndAppliesLatestTypedActions() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = SymptomIntakeViewModel(
                subscriptionId = "subscription",
                repository = failureRepository(
                    ApiResult.Failure(
                        code = "STATE-CONFLICT-01",
                        message = "latest state",
                        httpStatus = 409,
                        conflict = StateConflictSnapshot(
                            currentStatus = "CONSULTATION_REQUIRED",
                            currentStateVersion = 4,
                            allowedActions = listOf(
                                AllowedAction(
                                    code = "REQUEST_CONSULTATION",
                                    label = "상담 요청",
                                )
                            ),
                        ),
                    )
                ),
                savedStateHandle = SavedStateHandle(),
            )
            viewModel.updateRawText("충돌 뒤에도 유지")
            viewModel.submit()
            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals("충돌 뒤에도 유지", state.rawText)
            assertEquals(IntakeErrorKind.CONFLICT, state.errorKind)
            assertEquals(
                "CONSULTATION_REQUIRED",
                state.conflictStatus,
            )
            assertEquals(4, state.conflictStateVersion)
            assertEquals(
                listOf("REQUEST_CONSULTATION"),
                state.conflictAllowedActions.map { it.code },
            )
            assertEquals(
                "상담 요청",
                state.conflictAllowedActions.single().displayLabel,
            )
        }

    @Test
    fun finalUnauthorized_marksAuthExpiredWithoutDeletingDraft() =
        runTest(mainDispatcherRule.dispatcher) {
            val handle = SavedStateHandle()
            val viewModel = SymptomIntakeViewModel(
                subscriptionId = "subscription",
                repository = failureRepository(
                    ApiResult.Failure(
                        code = "AUTH_REQUIRED",
                        message = "로그인이 만료되었습니다.",
                        httpStatus = 401,
                    )
                ),
                savedStateHandle = handle,
            )
            viewModel.updateRawText("로그인 후에도 다시 입력할 내용")
            viewModel.submit()
            advanceUntilIdle()

            assertEquals(
                IntakeErrorKind.AUTH_EXPIRED,
                viewModel.state.value.errorKind,
            )
            assertEquals(
                "로그인 후에도 다시 입력할 내용",
                viewModel.state.value.rawText,
            )

            val recreated = SymptomIntakeViewModel(
                subscriptionId = "subscription",
                repository = unusedRepository(),
                savedStateHandle = handle,
            )
            assertEquals(
                "로그인 후에도 다시 입력할 내용",
                recreated.state.value.rawText,
            )
        }

    @Test
    fun forbiddenAndNotFound_areMappedSeparately() =
        runTest(mainDispatcherRule.dispatcher) {
            val forbidden = SymptomIntakeViewModel(
                "subscription",
                failureRepository(
                    ApiResult.Failure(
                        code = "FORBIDDEN",
                        message = "권한 부족",
                        httpStatus = 403,
                    )
                ),
                SavedStateHandle(),
            )
            forbidden.updateRawText("권한 테스트")
            forbidden.submit()
            advanceUntilIdle()
            assertEquals(
                IntakeErrorKind.FORBIDDEN,
                forbidden.state.value.errorKind,
            )

            val notFound = SymptomIntakeViewModel(
                "subscription",
                failureRepository(
                    ApiResult.Failure(
                        code = "RESOURCE_NOT_FOUND",
                        message = "정보 없음",
                        httpStatus = 404,
                    )
                ),
                SavedStateHandle(),
            )
            notFound.updateRawText("소유권 테스트")
            notFound.submit()
            advanceUntilIdle()
            assertEquals(
                IntakeErrorKind.NOT_FOUND,
                notFound.state.value.errorKind,
            )
        }

    private fun failureRepository(
        failure: ApiResult.Failure,
    ): CustomerCareRepository = object : CustomerCareRepository {
        override suspend fun getHome(): ApiResult<CustomerHomeData> =
            error("unused")

        override suspend fun submitIntake(
            request: SymptomIntakeRequest,
        ): ApiResult<IntakeSubmission> = failure

        override suspend fun getGuidance(
            inquiryId: String,
            scenario: MockScenario,
        ): ApiResult<GuidanceData> = error("unused")
    }

    private fun successRepository(
        submission: IntakeSubmission,
    ): CustomerCareRepository = object : CustomerCareRepository {
        override suspend fun getHome(): ApiResult<CustomerHomeData> =
            error("unused")

        override suspend fun submitIntake(
            request: SymptomIntakeRequest,
        ): ApiResult<IntakeSubmission> =
            ApiResult.Success(submission)

        override suspend fun getGuidance(
            inquiryId: String,
            scenario: MockScenario,
        ): ApiResult<GuidanceData> = error("unused")
    }

    private fun unusedRepository(): CustomerCareRepository =
        object : CustomerCareRepository {
            override suspend fun getHome(): ApiResult<CustomerHomeData> =
                error("unused")

            override suspend fun submitIntake(
                request: SymptomIntakeRequest,
            ): ApiResult<IntakeSubmission> = error("unused")

            override suspend fun getGuidance(
                inquiryId: String,
                scenario: MockScenario,
            ): ApiResult<GuidanceData> = error("unused")
        }
}

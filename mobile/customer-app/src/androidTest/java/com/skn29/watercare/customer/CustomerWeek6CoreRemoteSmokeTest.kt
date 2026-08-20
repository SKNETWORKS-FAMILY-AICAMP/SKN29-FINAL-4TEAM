package com.skn29.watercare.customer

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.SymptomIntakeRequest
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerWeek6CoreRemoteSmokeTest {

    @Test
    fun loginToFollowUpSubmit_sameInquiry_realBackend() = runBlocking<Unit> {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteSmoke") == "true")

        val context =
            InstrumentationRegistry.getInstrumentation().targetContext

        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )

        // 1. 실제 고객 로그인
        val login =
            WaterCareCore.authRepository.demoLogin(
                BuildConfig.E2E_CUSTOMER_CODE
            )

        assertTrue(login is ApiResult.Success<*>)

        val session =
            (login as ApiResult.Success<SessionResponse>).value

        assertEquals("CUSTOMER", session.user.roleCode)

        // 2. 실제 ACTIVE 지원 구독 조회
        val subscriptions =
            WaterCareCore.subscriptionRepository.list()

        assertTrue(subscriptions is ApiResult.Success<*>)

        val subscriptionList =
            (subscriptions as ApiResult.Success<SubscriptionListDataDto>).value

        val subscription =
            requireNotNull(
                subscriptionList.items.firstOrNull {
                    it.statusCode == "ACTIVE" &&
                        it.product.modelCode == P0_SUPPORTED_MODEL_CODE
                }
            ) {
                "ACTIVE supported subscription not found."
            }

        val detail =
            WaterCareCore.subscriptionRepository.detail(
                subscription.subscriptionId
            )

        assertTrue(detail is ApiResult.Success<*>)

        // 3. 실제 Inquiry 생성 + 증상 Submit
        val intake =
            WaterCareCore.customerCareRepository.submitIntake(
                SymptomIntakeRequest(
                    subscriptionId = subscription.subscriptionId,
                    symptomCodes = listOf("LOW_FLOW"),
                    rawText = "출수량이 줄었어요",
                    occurrenceCondition = "냉수 출수 시",
                    displayText = null,
                    entryMode = "ADHOC_INQUIRY",
                    idempotencyKey = "instrumentation-managed-by-repository",
                )
            )

        assertTrue(intake is ApiResult.Success<*>)

        val submission =
            (intake as ApiResult.Success<IntakeSubmission>).value

        val inquiryId = submission.inquiryId

        assertTrue(inquiryId.isNotBlank())
        assertEquals(
            "QUESTIONNAIRE_IN_PROGRESS",
            submission.statusCode
        )

        // 4. 실제 Questions 즉시 조회
        val questionsResult =
            WaterCareCore.customerInquiryRepository.questions(inquiryId)

        assertTrue(questionsResult is ApiResult.Success<*>)

        val questionData =
            (questionsResult as ApiResult.Success<CustomerInquiryQuestions>).value

        assertEquals(inquiryId, questionData.inquiryId)
        assertTrue(questionData.questions.isNotEmpty())

        // 5. Submit 직전 최신 Snapshot 재조회
        val beforeResult =
            WaterCareCore.customerInquiryRepository.snapshot(inquiryId)

        assertTrue(beforeResult is ApiResult.Success<*>)

        val before =
            (beforeResult as ApiResult.Success<CustomerInquirySnapshot>).value

        val beforeActions =
            before.allowedActions.map { it.normalizedCode }

        if (
            before.statusCode != "QUESTIONNAIRE_IN_PROGRESS" ||
            InquiryActionLabels.SUBMIT_ANSWERS !in beforeActions
        ) {
            throw AssertionError(
                "SUBMIT_ANSWERS unavailable before submit: " +
                    "inquiryId=$inquiryId, " +
                    "status=${before.statusCode}, " +
                    "stateVersion=${before.stateVersion}, " +
                    "allowedActions=${beforeActions.joinToString(",")}"
            )
        }

        if (questionData.stateVersion != before.stateVersion) {
            throw AssertionError(
                "Question/Snapshot version changed before submit: " +
                    "inquiryId=$inquiryId, " +
                    "questionVersion=${questionData.stateVersion}, " +
                    "snapshotVersion=${before.stateVersion}"
            )
        }

        // 6. 내려온 N개 질문 전체에 답변
        val answers =
            questionData.questions.map { question ->
                when {
                    question.isFreeText -> {
                        FollowUpAnswer(
                            questionId = question.questionId,
                            answerText =
                                "오늘 아침부터 증상이 계속되고 있습니다.",
                        )
                    }

                    question.isSingleChoice -> {
                        val selected =
                            question.options.firstOrNull()?.value

                        require(!selected.isNullOrBlank()) {
                            "SINGLE_CHOICE question has no option."
                        }

                        FollowUpAnswer(
                            questionId = question.questionId,
                            selectedOption = selected,
                        )
                    }

                    else -> {
                        error(
                            "Unsupported question type: " +
                                question.questionType
                        )
                    }
                }
            }

        assertEquals(questionData.questions.size, answers.size)
        assertTrue(answers.all { it.isValid })

        // 7. 실제 Answers Submit
        val submitResult =
            WaterCareCore.customerInquiryRepository.submitAnswers(
                inquiryId = inquiryId,
                stateVersion = before.stateVersion,
                answers = answers,
            )

        if (submitResult is ApiResult.Failure) {
            throw AssertionError(
                "submitAnswers failed: " +
                    "inquiryId=$inquiryId, " +
                    "code=${submitResult.code}, " +
                    "httpStatus=${submitResult.httpStatus}, " +
                    "retryable=${submitResult.retryable}, " +
                    "conflictStatus=${submitResult.conflict?.currentStatus}, " +
                    "conflictStateVersion=" +
                    "${submitResult.conflict?.currentStateVersion}"
            )
        }

        assertTrue(submitResult is ApiResult.Success<*>)

        val submitted =
            (submitResult as ApiResult.Success<SubmitFollowUpAnswersResult>).value

        assertEquals(inquiryId, submitted.inquiryId)
        assertTrue(submitted.stateVersion > before.stateVersion)
        assertFalse(submitted.idempotentReplay)

        // 8. 실제 최신 Snapshot
        val afterResult =
            WaterCareCore.customerInquiryRepository.snapshot(inquiryId)

        assertTrue(afterResult is ApiResult.Success<*>)

        val after =
            (afterResult as ApiResult.Success<CustomerInquirySnapshot>).value

        assertEquals(inquiryId, after.inquiryId)
        assertTrue(after.stateVersion >= submitted.stateVersion)

        val afterActions =
            after.allowedActions
                .map { it.normalizedCode }
                .joinToString(",")

        Log.i(
            "CustomerWeek6CoreSmoke",
            "inquiry_id=$inquiryId " +
                "questions=${questionData.questions.size} " +
                "before_status=${before.statusCode} " +
                "before_version=${before.stateVersion} " +
                "submitted_version=${submitted.stateVersion} " +
                "after_status=${after.statusCode} " +
                "after_version=${after.stateVersion} " +
                "allowed_after=${afterActions.ifBlank { "NONE" }} " +
                "idempotent_replay=${submitted.idempotentReplay}",
        )
    }
}
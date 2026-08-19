package com.skn29.watercare.customer

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerFollowUpRemoteSmokeTest {

    @Test
    fun snapshotQuestionsAndAnswers_useRealBackend() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteSmoke") == "true")

        val inquiryId = requireNotNull(
            args.getString("followUpInquiryId")
        ) {
            "followUpInquiryId instrumentation argument is required."
        }.trim()

        require(inquiryId.isNotEmpty()) {
            "followUpInquiryId instrumentation argument must not be blank."
        }

        val context =
            InstrumentationRegistry.getInstrumentation().targetContext

        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )

        val login =
            WaterCareCore.authRepository.demoLogin(
                "DEMO-CUSTOMER-001"
            )

        assertTrue(login is ApiResult.Success<*>)

        val session =
            (login as ApiResult.Success<SessionResponse>).value

        assertEquals("CUSTOMER", session.user.roleCode)

        val snapshotResult =
            WaterCareCore.customerInquiryRepository.snapshot(inquiryId)

        assertTrue(snapshotResult is ApiResult.Success<*>)

        val snapshot =
            (snapshotResult as ApiResult.Success<CustomerInquirySnapshot>).value

        assertEquals(inquiryId, snapshot.inquiryId)
        assertTrue(snapshot.stateVersion >= 1)

        val questionsResult =
            WaterCareCore.customerInquiryRepository.questions(inquiryId)

        assertTrue(questionsResult is ApiResult.Success<*>)

        val questionData =
            (questionsResult as ApiResult.Success<CustomerInquiryQuestions>).value

        assertEquals(inquiryId, questionData.inquiryId)
        assertEquals(snapshot.stateVersion, questionData.stateVersion)
        assertTrue(questionData.questions.isNotEmpty())

        val answers = questionData.questions.map { question ->
            when {
                question.isFreeText -> {
                    FollowUpAnswer(
                        questionId = question.questionId,
                        answerText = "오늘 아침부터 증상이 계속되고 있습니다.",
                    )
                }

                question.isSingleChoice -> {
                    val selected =
                        question.options.firstOrNull()?.value

                    require(!selected.isNullOrBlank()) {
                        "SINGLE_CHOICE question must expose at least one option."
                    }

                    FollowUpAnswer(
                        questionId = question.questionId,
                        selectedOption = selected,
                    )
                }

                else -> {
                    error(
                        "Unsupported follow-up question type: ${question.questionType}"
                    )
                }
            }
        }

        assertEquals(questionData.questions.size, answers.size)
        assertTrue(answers.all { it.isValid })

        val submitResult =
            WaterCareCore.customerInquiryRepository.submitAnswers(
                inquiryId = inquiryId,
                stateVersion = snapshot.stateVersion,
                answers = answers,
            )

        if (submitResult is ApiResult.Failure) {
            throw AssertionError(
                "submitAnswers failed: " +
                    "code=${submitResult.code}, " +
                    "httpStatus=${submitResult.httpStatus}, " +
                    "retryable=${submitResult.retryable}, " +
                    "conflictStatus=${submitResult.conflict?.currentStatus}, " +
                    "conflictStateVersion=${submitResult.conflict?.currentStateVersion}"
            )
        }
        assertTrue(submitResult is ApiResult.Success<*>)

        val submitted =
            (submitResult as ApiResult.Success<SubmitFollowUpAnswersResult>).value

        assertEquals(inquiryId, submitted.inquiryId)
        assertTrue(submitted.stateVersion > snapshot.stateVersion)
        assertFalse(submitted.idempotentReplay)

        val refreshedQuestionsResult =
            WaterCareCore.customerInquiryRepository.questions(inquiryId)

        assertTrue(
            refreshedQuestionsResult is ApiResult.Success<*>
        )

        val refreshedQuestions =
            (refreshedQuestionsResult as ApiResult.Success<CustomerInquiryQuestions>).value

        assertEquals(
            submitted.stateVersion,
            refreshedQuestions.stateVersion
        )

        assertTrue(refreshedQuestions.questions.isEmpty())

        val refreshedSnapshotResult =
            WaterCareCore.customerInquiryRepository.snapshot(inquiryId)

        assertTrue(
            refreshedSnapshotResult is ApiResult.Success<*>
        )

        val refreshedSnapshot =
            (refreshedSnapshotResult as ApiResult.Success<CustomerInquirySnapshot>).value

        assertEquals(inquiryId, refreshedSnapshot.inquiryId)
        assertEquals(
            submitted.stateVersion,
            refreshedSnapshot.stateVersion
        )
    }
}

package com.skn29.watercare.customer

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CarePrecheckSessionDto
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubscriptionListDataDto
import java.util.UUID
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith


/**
 * T-021 CARE_PRECHECK 물리기기 + 실제 Backend Smoke Test.
 *
 * 검증 흐름:
 *
 * 실제 고객 로그인
 *      ↓
 * ACTIVE 지원 구독 조회
 *      ↓
 * CARE_PRECHECK 시작
 *      ↓
 * GET으로 시작 상태 복구
 *      ↓
 * 답변 임시 저장
 *      ↓
 * GET으로 저장 답변 복구
 *      ↓
 * 최종 제출
 *      ↓
 * GET으로 최종 상태 복구
 *
 * 이 테스트에서는 Fake Repository를 사용하지 않습니다.
 */
@RunWith(AndroidJUnit4::class)
class CustomerCarePrecheckRemoteSmokeTest {

    @Test
    fun startSaveRecoverSubmit_realBackend() =
        runBlocking<Unit> {

            // -------------------------------------------------------
            // 1. 명시적으로 Remote Smoke를 요청했을 때만 실행합니다.
            //
            // 일반 connectedDebugAndroidTest에서
            // 실수로 실제 Backend 데이터를 변경하지 않기 위한 장치입니다.
            // -------------------------------------------------------

            val args =
                InstrumentationRegistry
                    .getArguments()

            assumeTrue(
                args.getString(
                    "runRemoteCarePrecheckSmoke"
                ) == "true"
            )

            val context =
                InstrumentationRegistry
                    .getInstrumentation()
                    .targetContext

            // -------------------------------------------------------
            // 2. 실제 Backend를 사용하는 REMOTE 모드 초기화
            // -------------------------------------------------------

            WaterCareCore.initialize(
                context = context,
                baseUrl =
                    BuildConfig
                        .BACKEND_BASE_URL,
                debug = true,
                customerCareMode =
                    "REMOTE",
                demoSubscriptionId = "",
            )

            // -------------------------------------------------------
            // 3. 실제 E2E 고객 로그인
            // -------------------------------------------------------

            val login =
                WaterCareCore
                    .authRepository
                    .demoLogin(
                        BuildConfig
                            .E2E_CUSTOMER_CODE
                    )

            assertTrue(
                "고객 로그인이 성공해야 합니다.",
                login is ApiResult.Success<*>,
            )

            val session =
                (
                    login as
                        ApiResult.Success<
                            SessionResponse
                        >
                    ).value

            assertEquals(
                "CUSTOMER",
                session.user.roleCode,
            )

            // -------------------------------------------------------
            // 4. 실제 ACTIVE + Runtime 지원 제품 구독을 찾습니다.
            //
            // 다른 제품이나 종료된 구독을 임의로 사용하지 않습니다.
            // -------------------------------------------------------

            val subscriptions =
                WaterCareCore
                    .subscriptionRepository
                    .list(
                        page = 1,
                        size = 100,
                    )

            assertTrue(
                "구독 목록 조회가 성공해야 합니다.",
                subscriptions is ApiResult.Success<*>,
            )

            val subscriptionData =
                (
                    subscriptions as
                        ApiResult.Success<
                            SubscriptionListDataDto
                        >
                    ).value

            val target =
                subscriptionData
                    .items
                    .firstOrNull {
                        it.statusCode ==
                            "ACTIVE" &&
                            it.product.modelCode ==
                            P0_SUPPORTED_MODEL_CODE
                    }

            assumeTrue(
                "ACTIVE 지원 구독이 있어야 합니다.",
                target != null,
            )

            val subscription =
                requireNotNull(target)

            // 테스트를 다시 실행해도
            // 이전 Idempotency-Key와 충돌하지 않도록
            // 이번 실행 전용 prefix를 만듭니다.
            val runId =
                UUID.randomUUID()
                    .toString()

            // -------------------------------------------------------
            // 5. CARE_PRECHECK START
            //
            // 예상:
            // status = UNANSWERED
            // state_version = 1
            // answers = {}
            // -------------------------------------------------------

            val startedResult =
                WaterCareCore
                    .carePrecheckRepository
                    .start(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        idempotencyKeyOverride =
                            "mobile-t021-start-$runId",
                    )

            if (startedResult is ApiResult.Failure) {
                throw AssertionError(
                    "CARE_PRECHECK start failed: " +
                        "code=${startedResult.code}, " +
                        "httpStatus=${startedResult.httpStatus}, " +
                        "retryable=${startedResult.retryable}"
                )
            }

            assertTrue(
                startedResult is ApiResult.Success<*>
            )

            val started =
                (
                    startedResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                subscription.subscriptionId,
                started.subscriptionId,
            )

            assertEquals(
                "CARE_PRECHECK",
                started.questionnaireTypeCode,
            )

            assertEquals(
                "CARE_PRECHECK-v1",
                started.questionnaireVersion,
            )

            assertEquals(
                "UNANSWERED",
                started.statusCode,
            )

            assertEquals(
                1,
                started.stateVersion,
            )

            assertTrue(
                started.answers.isEmpty()
            )

            assertNull(
                started.submittedAt
            )

            // 중요한 계약:
            //
            // CARE_PRECHECK를 시작했다고
            // Inquiry가 자동 생성되는 것이 아닙니다.
            assertNull(
                started.linkedInquiryId
            )

            assertFalse(
                started.idempotentReplay ?: true
            )

            val questionnaireSessionId =
                started.questionnaireSessionId

            // -------------------------------------------------------
            // 6. START 직후 GET
            //
            // Backend에서 실제로 저장된 세션을
            // 다시 읽을 수 있는지 확인합니다.
            // -------------------------------------------------------

            val firstRecoverResult =
                WaterCareCore
                    .carePrecheckRepository
                    .get(
                        questionnaireSessionId
                    )

            assertTrue(
                firstRecoverResult is
                    ApiResult.Success<*>
            )

            val firstRecovered =
                (
                    firstRecoverResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                questionnaireSessionId,
                firstRecovered
                    .questionnaireSessionId,
            )

            assertEquals(
                "UNANSWERED",
                firstRecovered.statusCode,
            )

            assertEquals(
                1,
                firstRecovered.stateVersion,
            )

            // -------------------------------------------------------
            // 7. 실제 Backend T-021 테스트와 같은 형태의 답변 생성
            //
            // {
            //   "WATER_FLOW": "LOW",
            //   "LEAK": false
            // }
            // -------------------------------------------------------

            val answers =
                buildJsonObject {
                    put(
                        "WATER_FLOW",
                        JsonPrimitive("LOW"),
                    )

                    put(
                        "LEAK",
                        JsonPrimitive(false),
                    )
                }

            // -------------------------------------------------------
            // 8. SAVE
            //
            // state_version=1을 기준으로 저장하면
            //
            // IN_PROGRESS
            // state_version=2
            //
            // 로 바뀌어야 합니다.
            // -------------------------------------------------------

            val saveResult =
                WaterCareCore
                    .carePrecheckRepository
                    .save(
                        questionnaireSessionId =
                            questionnaireSessionId,
                        stateVersion =
                            firstRecovered
                                .stateVersion,
                        answers = answers,
                        idempotencyKeyOverride =
                            "mobile-t021-save-$runId",
                    )

            if (saveResult is ApiResult.Failure) {
                throw AssertionError(
                    "CARE_PRECHECK save failed: " +
                        "sessionId=$questionnaireSessionId, " +
                        "code=${saveResult.code}, " +
                        "httpStatus=${saveResult.httpStatus}, " +
                        "retryable=${saveResult.retryable}"
                )
            }

            val saved =
                (
                    saveResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                "IN_PROGRESS",
                saved.statusCode,
            )

            assertEquals(
                2,
                saved.stateVersion,
            )

            assertEquals(
                answers,
                saved.answers,
            )

            assertFalse(
                saved.idempotentReplay ?: true
            )

            // -------------------------------------------------------
            // 9. SAVE 이후 다시 GET
            //
            // 이것이 실제 "복구" 검증입니다.
            //
            // 화면을 다시 열었다고 가정했을 때
            // Mobile 메모리가 아니라 Backend에 저장된 답변을
            // 다시 받아올 수 있어야 합니다.
            // -------------------------------------------------------

            val recoveredResult =
                WaterCareCore
                    .carePrecheckRepository
                    .get(
                        questionnaireSessionId
                    )

            assertTrue(
                recoveredResult is
                    ApiResult.Success<*>
            )

            val recovered =
                (
                    recoveredResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                "IN_PROGRESS",
                recovered.statusCode,
            )

            assertEquals(
                2,
                recovered.stateVersion,
            )

            assertEquals(
                answers,
                recovered.answers,
            )

            assertNull(
                recovered.submittedAt
            )

            // -------------------------------------------------------
            // 10. SUBMIT
            //
            // 최신 state_version=2를 사용해야 합니다.
            //
            // 정상 결과:
            // SUBMITTED
            // state_version=3
            // submitted_at != null
            // -------------------------------------------------------

            val submitResult =
                WaterCareCore
                    .carePrecheckRepository
                    .submit(
                        questionnaireSessionId =
                            questionnaireSessionId,
                        stateVersion =
                            recovered.stateVersion,
                        answers = answers,
                        idempotencyKeyOverride =
                            "mobile-t021-submit-$runId",
                    )

            if (submitResult is ApiResult.Failure) {
                throw AssertionError(
                    "CARE_PRECHECK submit failed: " +
                        "sessionId=$questionnaireSessionId, " +
                        "code=${submitResult.code}, " +
                        "httpStatus=${submitResult.httpStatus}, " +
                        "retryable=${submitResult.retryable}"
                )
            }

            val submitted =
                (
                    submitResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                "SUBMITTED",
                submitted.statusCode,
            )

            assertEquals(
                3,
                submitted.stateVersion,
            )

            assertEquals(
                answers,
                submitted.answers,
            )

            assertNotNull(
                submitted.submittedAt
            )

            // 제출만으로 Inquiry가 만들어지는 것은 아닙니다.
            //
            // 이후 Create Inquiry가 이 session ID를 사용해야
            // linked_inquiry_id가 연결됩니다.
            assertNull(
                submitted.linkedInquiryId
            )

            // -------------------------------------------------------
            // 11. SUBMIT 이후 마지막 GET
            //
            // 최종 상태도 Backend에서 다시 복구되는지 확인합니다.
            // -------------------------------------------------------

            val finalRecoverResult =
                WaterCareCore
                    .carePrecheckRepository
                    .get(
                        questionnaireSessionId
                    )

            assertTrue(
                finalRecoverResult is
                    ApiResult.Success<*>
            )

            val finalRecovered =
                (
                    finalRecoverResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                "SUBMITTED",
                finalRecovered.statusCode,
            )

            assertEquals(
                3,
                finalRecovered.stateVersion,
            )

            assertEquals(
                answers,
                finalRecovered.answers,
            )

            assertNotNull(
                finalRecovered.submittedAt
            )

            assertNull(
                finalRecovered.linkedInquiryId
            )

            // -------------------------------------------------------
            // 12. 나중 E2E 증거 확보용 Log
            // -------------------------------------------------------

            // -------------------------------------------------------
            // SUBMITTED CARE_PRECHECK -> ?? Inquiry ?? ??
            //
            // CARE_PRECHECK ?????? Inquiry? ??? ????.
            //
            // Inquiry ?? ???? questionnaire_session_id?
            // ???? Backend? ? ???? ?????.
            //
            // ???? Inquiry CREATE??? ?????.
            // ?? ?? ?? / ?? ?? ????? ???? ????.
            // -------------------------------------------------------

            val inquiryResult =
                WaterCareCore
                    .inquiryRepository
                    .create(
                        request =
                            CreateInquiryRequest(
                                subscriptionId =
                                    subscription.subscriptionId,
                                channelCode =
                                    "MOBILE",
                                rawText =
                                    "?? ?? ?? ??? ?? ??? ?????.",
                                representativeSymptomCode =
                                    "LOW_FLOW",
                                questionnaireSessionId =
                                    questionnaireSessionId,
                            ),
                        idempotencyKey =
                            "mobile-t021-inquiry-$runId",
                    )

            if (inquiryResult is ApiResult.Failure) {
                throw AssertionError(
                    "CARE_PRECHECK inquiry link failed: " +
                        "sessionId=$questionnaireSessionId, " +
                        "code=${inquiryResult.code}, " +
                        "httpStatus=${inquiryResult.httpStatus}, " +
                        "retryable=${inquiryResult.retryable}"
                )
            }

            assertTrue(
                "Inquiry ??? ???? ???.",
                inquiryResult is ApiResult.Success<*>,
            )

            val inquiry =
                (
                    inquiryResult as
                        ApiResult.Success<
                            InquiryResponse
                        >
                    ).value

            assertTrue(
                "??? inquiry_id? ?? ??? ? ???.",
                inquiry.inquiryId.isNotBlank(),
            )

            // -------------------------------------------------------
            // Inquiry ?? ? CARE_PRECHECK ???
            //
            // linked_inquiry_id? ?? ??? inquiry_id?
            // ??? ??? Backend ???? ?????.
            // -------------------------------------------------------

            val linkedRecoverResult =
                WaterCareCore
                    .carePrecheckRepository
                    .get(
                        questionnaireSessionId
                    )

            if (linkedRecoverResult is ApiResult.Failure) {
                throw AssertionError(
                    "linked CARE_PRECHECK recovery failed: " +
                        "sessionId=$questionnaireSessionId, " +
                        "code=${linkedRecoverResult.code}, " +
                        "httpStatus=${linkedRecoverResult.httpStatus}"
                )
            }

            assertTrue(
                linkedRecoverResult is
                    ApiResult.Success<*>
            )

            val linkedRecovered =
                (
                    linkedRecoverResult as
                        ApiResult.Success<
                            CarePrecheckSessionDto
                        >
                    ).value

            assertEquals(
                "CARE_PRECHECK? ??? Inquiry? ???? ???.",
                inquiry.inquiryId,
                linkedRecovered.linkedInquiryId,
            )

            // Inquiry ?? ???? ?? ?? ???
            // SUBMITTED? ???? ???.
            assertEquals(
                "SUBMITTED",
                linkedRecovered.statusCode,
            )

            Log.i(
                "CustomerCarePrecheckSmoke",
                "subscription_id=" +
                    "${subscription.subscriptionId} " +
                    "questionnaire_session_id=" +
                    "$questionnaireSessionId " +
                    "start_status=${started.statusCode} " +
                    "saved_status=${saved.statusCode} " +
                    "submitted_status=${submitted.statusCode} " +
                    "final_state_version=" +
                    "${finalRecovered.stateVersion} " +
                    "answer_count=" +
                    "${finalRecovered.answers.size} " +
                    "inquiry_id=" +
                    "${inquiry.inquiryId} " +
                    "linked_inquiry_id=" +
                    "${linkedRecovered.linkedInquiryId ?: "NONE"}"
            )
        }
}

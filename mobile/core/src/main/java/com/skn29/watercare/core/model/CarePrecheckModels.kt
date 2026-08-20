package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * T-021 CARE_PRECHECK 시작 요청.
 *
 * 고객이 어떤 구독 제품에 대해
 * 사전 점검을 시작할지 Backend에 전달합니다.
 */
@Serializable
data class StartCarePrecheckRequestDto(
    @SerialName("subscription_id")
    val subscriptionId: String,
)

/**
 * 작성 중인 CARE_PRECHECK 답변을 임시 저장할 때 사용합니다.
 *
 * stateVersion:
 *   오래된 화면이 최신 데이터를 덮어쓰는 것을 막기 위한 버전입니다.
 *
 * answers:
 *   질문 코드 → 고객 답변 형태의 JSON Object입니다.
 */
@Serializable
data class SaveCarePrecheckRequestDto(
    @SerialName("state_version")
    val stateVersion: Int,

    val answers: JsonObject,
)

/**
 * CARE_PRECHECK를 최종 제출할 때 사용하는 요청입니다.
 */
@Serializable
data class SubmitCarePrecheckRequestDto(
    @SerialName("state_version")
    val stateVersion: Int,

    val answers: JsonObject,
)

/**
 * Backend가 반환하는 CARE_PRECHECK 세션 정본입니다.
 *
 * Start / Get / Save / Submit 모두 이 형태를 사용합니다.
 */
@Serializable
data class CarePrecheckSessionDto(
    @SerialName("questionnaire_session_id")
    val questionnaireSessionId: String,

    @SerialName("subscription_id")
    val subscriptionId: String,

    @SerialName("questionnaire_type_code")
    val questionnaireTypeCode: String,

    @SerialName("questionnaire_version")
    val questionnaireVersion: String,

    @SerialName("status_code")
    val statusCode: String,

    @SerialName("state_version")
    val stateVersion: Int,

    val answers: JsonObject,

    @SerialName("started_at")
    val startedAt: String,

    @SerialName("submitted_at")
    val submittedAt: String? = null,

    @SerialName("linked_inquiry_id")
    val linkedInquiryId: String? = null,

    @SerialName("idempotent_replay")
    val idempotentReplay: Boolean? = null,
)

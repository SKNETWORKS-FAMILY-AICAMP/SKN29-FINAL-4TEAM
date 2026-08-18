package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CareHistoryItemDto(
    @SerialName("care_record_id") val careRecordId: String,
    @SerialName("subscription_id") val subscriptionId: String,
    @SerialName("care_type_code") val careTypeCode: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("performed_on") val performedOn: String,
    @SerialName("result_code") val resultCode: String? = null,
    @SerialName("source_code") val sourceCode: String,
)

@Serializable
data class CareHistoryListDataDto(
    val items: List<CareHistoryItemDto>,
    val page: Int,
    val size: Int,
    val total: Int,
)

@Serializable
data class CareHistoryCreateRequestDto(
    @SerialName("care_type_code") val careTypeCode: String,
    @SerialName("performed_on") val performedOn: String,
)

@Serializable
data class CareHistoryMutationResultDto(
    @SerialName("care_record_id") val careRecordId: String,
    @SerialName("subscription_id") val subscriptionId: String,
    @SerialName("care_type_code") val careTypeCode: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("performed_on") val performedOn: String,
    @SerialName("result_code") val resultCode: String? = null,
    @SerialName("source_code") val sourceCode: String,
    @SerialName("idempotent_replay") val idempotentReplay: Boolean,
)

enum class CustomerSelfCareType(
    val code: String,
) {
    FILTER_REPLACEMENT("FILTER_REPLACEMENT"),
    CLEANING("CLEANING"),
}

fun CareHistoryMutationResultDto.toCareHistoryItem(): CareHistoryItemDto =
    CareHistoryItemDto(
        careRecordId = careRecordId,
        subscriptionId = subscriptionId,
        careTypeCode = careTypeCode,
        statusCode = statusCode,
        performedOn = performedOn,
        resultCode = resultCode,
        sourceCode = sourceCode,
    )
package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

const val P0_SUPPORTED_MODEL_CODE = "WPUJAC104DWH"

@Serializable
data class SubscriptionProductDto(
    @SerialName("product_model_id") val productModelId: String,
    @SerialName("model_code") val modelCode: String,
    @SerialName("model_name") val modelName: String,
    @SerialName("generation_code") val generationCode: String? = null,
    val manufacturer: String,
)

@Serializable
data class SubscriptionSummaryDto(
    @SerialName("subscription_id") val subscriptionId: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("management_type_code") val managementTypeCode: String,
    @SerialName("started_on") val startedOn: String,
    @SerialName("last_care_on") val lastCareOn: String? = null,
    @SerialName("next_care_on") val nextCareOn: String? = null,
    val product: SubscriptionProductDto,
)

@Serializable
data class SubscriptionDetailDto(
    @SerialName("subscription_id") val subscriptionId: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("management_type_code") val managementTypeCode: String,
    @SerialName("started_on") val startedOn: String,
    @SerialName("last_care_on") val lastCareOn: String? = null,
    @SerialName("next_care_on") val nextCareOn: String? = null,
    @SerialName("ended_on") val endedOn: String? = null,
    val product: SubscriptionProductDto,
)

@Serializable
data class SubscriptionListDataDto(
    val items: List<SubscriptionSummaryDto>,
    val page: Int,
    val size: Int,
    val total: Int,
)

private fun subscriptionHome(
    subscriptionId: String,
    statusCode: String,
    managementTypeCode: String,
    startedOn: String,
    lastCareOn: String?,
    nextCareOn: String?,
    product: SubscriptionProductDto,
): CustomerHomeData =
    CustomerHomeData(
        subscriptionId = subscriptionId,
        product = ProductSummary(
            productId = product.productModelId,
            modelCode = product.modelCode,
            modelName = product.modelName,
            serialNo = "API 미제공",
            managementTypeCode = managementTypeCode,
            managementTypeLabel = when (managementTypeCode) {
                "VISIT_CARE" -> "방문 관리"
                "SELF_MANAGED" -> "자가 관리"
                else -> managementTypeCode
            },
            // Public subscription API does not expose a synthetic/private flag.
            isSynthetic = false,
        ),
        questionnaireStatus = when {
            statusCode != "ACTIVE" -> "비활성 구독"
            product.modelCode != P0_SUPPORTED_MODEL_CODE -> "현재 P0 미지원 모델"
            else -> "사전 문진 가능"
        },
        nextCareOn = nextCareOn ?: "미정",
        activeInquiry = null,
        statusCode = statusCode,
        startedOn = startedOn,
        lastCareOn = lastCareOn,
    )

fun SubscriptionSummaryDto.toCustomerHomeData(): CustomerHomeData =
    subscriptionHome(
        subscriptionId = subscriptionId,
        statusCode = statusCode,
        managementTypeCode = managementTypeCode,
        startedOn = startedOn,
        lastCareOn = lastCareOn,
        nextCareOn = nextCareOn,
        product = product,
    )

fun SubscriptionDetailDto.toCustomerHomeData(): CustomerHomeData =
    subscriptionHome(
        subscriptionId = subscriptionId,
        statusCode = statusCode,
        managementTypeCode = managementTypeCode,
        startedOn = startedOn,
        lastCareOn = lastCareOn,
        nextCareOn = nextCareOn,
        product = product,
    )

fun CustomerHomeData.isP0SupportedActiveSubscription(): Boolean =
    statusCode == "ACTIVE" && product.modelCode == P0_SUPPORTED_MODEL_CODE

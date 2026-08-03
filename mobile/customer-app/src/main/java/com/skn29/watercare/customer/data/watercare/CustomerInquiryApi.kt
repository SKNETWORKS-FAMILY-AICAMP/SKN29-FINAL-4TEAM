package com.skn29.watercare.customer.data.watercare

import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.InquiryResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

/** Customer-only WaterCare business endpoints that are available in Django Runtime. */
interface CustomerInquiryApi {
    @POST("api/v1/inquiries")
    suspend fun createInquiry(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: CreateInquiryRequest,
    ): Response<ApiEnvelope<InquiryResponse>>

    @POST("api/v1/inquiries/{inquiryId}/cancel")
    suspend fun cancelInquiry(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: CancelInquiryRequest,
    ): Response<ApiEnvelope<CancelInquiryResponse>>
}

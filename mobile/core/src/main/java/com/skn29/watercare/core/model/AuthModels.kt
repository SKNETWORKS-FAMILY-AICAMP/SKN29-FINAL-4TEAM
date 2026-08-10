package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

const val P0_SYNTHETIC_CUSTOMER_LOGIN_CODE = "SYN-CUSTOMER-001"

@Serializable
data class DemoLoginRequest(
    @SerialName("demo_user_code") val demoUserCode: String,
)

@Serializable
data class RefreshTokenRequest(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class SessionResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("access_expires_in") val accessExpiresIn: Long,
    @SerialName("refresh_expires_in") val refreshExpiresIn: Long,
    val user: UserData,
)

@Serializable
data class UserData(
    val id: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("role_code") val roleCode: String,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("customer_profile") val customerProfile: CustomerProfileData? = null,
    @SerialName("allowed_actions") val allowedActions: List<String> = emptyList(),
)

@Serializable
data class CustomerProfileData(
    val id: String,
    @SerialName("customer_no") val customerNo: String,
    @SerialName("customer_name") val customerName: String,
    @SerialName("is_synthetic") val isSynthetic: Boolean = false,
)

@Serializable
data class LogoutResponse(val revoked: Boolean)

data class AuthTokens(val accessToken: String, val refreshToken: String)

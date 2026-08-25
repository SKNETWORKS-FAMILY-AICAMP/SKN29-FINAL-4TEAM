package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * P1-A G2 CONFIRMED 계약용 인증 DTO.
 *
 * 중요:
 * - OTP / Password / claim_ticket / reset_ticket은 영속 저장하거나 로그에 남기지 않는다.
 * - customer_number / contract_number 역시 인증 흐름 중에만 사용한다.
 */

@Serializable
data class P1ChallengeRequest(
    @SerialName("customer_number")
    val customerNumber: String? = null,
    @SerialName("contract_number")
    val contractNumber: String? = null,
    val name: String? = null,
    val username: String? = null,
    val email: String? = null,
) {
    override fun toString(): String =
        "P1ChallengeRequest(" +
            "customerNumber=<redacted>, " +
            "contractNumber=<redacted>, " +
            "name=<redacted>, " +
            "username=<redacted>, " +
            "email=<redacted>" +
            ")"
}

@Serializable
data class P1ChallengeAccepted(
    @SerialName("challenge_id")
    val challengeId: String,
    @SerialName("expires_in")
    val expiresIn: Int,
    @SerialName("resend_after")
    val resendAfter: Int,
    val message: String,
)

@Serializable
data class P1OtpVerificationRequest(
    @SerialName("otp_code")
    val otpCode: String,
) {
    override fun toString(): String =
        "P1OtpVerificationRequest(otpCode=<redacted>)"
}

@Serializable
data class P1ClaimTicket(
    @SerialName("claim_ticket")
    val claimTicket: String,
    @SerialName("expires_in")
    val expiresIn: Int,
) {
    override fun toString(): String =
        "P1ClaimTicket(claimTicket=<redacted>, expiresIn=$expiresIn)"
}

@Serializable
data class P1ConsentRequest(
    val code: String,
    val version: String,
    val agreed: Boolean,
)

@Serializable
data class P1SignupRequest(
    @SerialName("claim_ticket")
    val claimTicket: String,
    val name: String,
    val email: String,
    val username: String,
    val password: String,
    val consents: List<P1ConsentRequest>,
) {
    override fun toString(): String =
        "P1SignupRequest(" +
            "claimTicket=<redacted>, " +
            "name=<redacted>, " +
            "email=<redacted>, " +
            "username=<redacted>, " +
            "password=<redacted>, " +
            "consents=${consents.size}" +
            ")"
}

@Serializable
data class P1PasswordLoginRequest(
    val username: String,
    val password: String,
) {
    override fun toString(): String =
        "P1PasswordLoginRequest(username=<redacted>, password=<redacted>)"
}

@Serializable
data class P1UsernameRecoveryResult(
    @SerialName("masked_username")
    val maskedUsername: String,
)

@Serializable
data class P1PasswordResetTicket(
    @SerialName("reset_ticket")
    val resetTicket: String,
    @SerialName("expires_in")
    val expiresIn: Int,
) {
    override fun toString(): String =
        "P1PasswordResetTicket(resetTicket=<redacted>, expiresIn=$expiresIn)"
}

@Serializable
data class P1PasswordResetConfirmRequest(
    @SerialName("reset_ticket")
    val resetTicket: String,
    val password: String,
) {
    override fun toString(): String =
        "P1PasswordResetConfirmRequest(resetTicket=<redacted>, password=<redacted>)"
}

@Serializable
data class P1PasswordResetResult(
    @SerialName("password_reset")
    val passwordReset: Boolean,
    @SerialName("sessions_revoked")
    val sessionsRevoked: Boolean,
)

object P1ConsentCode {
    const val TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    const val PRIVACY_COLLECTION_USE = "PRIVACY_COLLECTION_USE"
    const val MARKETING = "MARKETING"
}
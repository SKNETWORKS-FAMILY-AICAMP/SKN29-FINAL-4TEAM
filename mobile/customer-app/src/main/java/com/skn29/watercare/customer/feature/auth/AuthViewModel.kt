package com.skn29.watercare.customer.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
import com.skn29.watercare.core.model.P1ChallengeRequest
import com.skn29.watercare.core.model.P1ConsentCode
import com.skn29.watercare.core.model.P1ConsentRequest
import com.skn29.watercare.core.model.P1OtpVerificationRequest
import com.skn29.watercare.core.model.P1PasswordLoginRequest
import com.skn29.watercare.core.model.P1PasswordResetConfirmRequest
import com.skn29.watercare.core.model.P1SignupRequest
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.P1AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.customer.BuildConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

enum class SignupStage {
    IDLE,
    OTP_REQUIRED,
    ACCOUNT_REQUIRED,
}

enum class UsernameRecoveryStage {
    IDLE,
    OTP_REQUIRED,
    RESULT,
}

enum class PasswordResetStage {
    IDLE,
    OTP_REQUIRED,
    PASSWORD_REQUIRED,
    RESULT,
}

data class AuthUiState(
    val checkingBackend: Boolean = true,
    val backendAvailable: Boolean? = null,
    val submitting: Boolean = false,
    val error: String? = null,
    val authenticated: Boolean = false,
    val offlinePreview: Boolean = false,
    val fieldErrors: Map<String, List<String>> = emptyMap(),
    val retryAfterSeconds: Int? = null,
    val signupStage: SignupStage = SignupStage.IDLE,
    val signupMessage: String? = null,
    val signupCompletedUsername: String? = null,
    val challengeExpiresInSeconds: Int? = null,
    val resendAfterSeconds: Int? = null,
    val usernameRecoveryStage: UsernameRecoveryStage =
        UsernameRecoveryStage.IDLE,
    val usernameRecoveryMessage: String? = null,
    val recoveredMaskedUsername: String? = null,
    val passwordResetStage: PasswordResetStage =
        PasswordResetStage.IDLE,
    val passwordResetMessage: String? = null,
    val passwordResetTicketExpiresInSeconds: Int? = null,
)

class AuthViewModel(
    private val authRepository: AuthRepository,
    private val backendStatusRepository: BackendStatusRepository,
    private val demoCustomerCode: String = BuildConfig.E2E_CUSTOMER_CODE,
    private val p1AuthRepository: P1AuthRepository? = null,
) : ViewModel() {
    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    // P1-A 회원가입 중에만 메모리에 존재한다.
    // UI State / TokenStore / 로그에 claim_ticket을 노출하지 않는다.
    private var signupChallengeId: String? = null
    private var signupClaimTicket: String? = null
    private var signupIdempotencyKey: String? = null
    private var signupName: String? = null
    private var signupEmail: String? = null

    // 아이디 찾기 OTP Challenge 역시 화면 상태나 영속 저장소에 노출하지 않는다.
    private var usernameRecoveryChallengeId: String? = null

    // 비밀번호 재설정 중에만 메모리에 존재한다.
    // reset_ticket은 UI State / TokenStore / 로그에 노출하지 않는다.
    private var passwordResetChallengeId: String? = null
    private var passwordResetTicket: String? = null
    private var passwordResetConfirmIdempotencyKey: String? = null

    init {
        checkBackend()
    }

    fun checkBackend() {
        viewModelScope.launch {
            _state.value = _state.value.copy(checkingBackend = true, error = null)
            val available = backendStatusRepository.health() is ApiResult.Success
            _state.value = _state.value.copy(checkingBackend = false, backendAvailable = available)
        }
    }

    fun startSignupVerification(
        name: String,
        email: String,
        username: String,
        password: String,
    ) {
        if (_state.value.submitting) return

        val normalizedName = name.trim()
        val normalizedEmail =
            email.trim().lowercase()
        val normalizedUsername =
            username.trim()

        val emailPattern =
            Regex("""^[^\s@]+@[^\s@]+\.[^\s@]+$""")

        val usernamePattern =
            Regex("""^[A-Za-z0-9._-]+$""")

        val hasLetter =
            password.any {
                it in 'A'..'Z' ||
                    it in 'a'..'z'
            }

        val hasDigit =
            password.any(Char::isDigit)

        val localErrors =
            buildMap<String, List<String>> {
                if (normalizedName.isEmpty()) {
                    put(
                        "name",
                        listOf("이름을 입력해 주세요."),
                    )
                } else if (
                    normalizedName.length > 100
                ) {
                    put(
                        "name",
                        listOf(
                            "이름은 100자 이하로 입력해 주세요."
                        ),
                    )
                }

                if (normalizedEmail.isEmpty()) {
                    put(
                        "email",
                        listOf("이메일을 입력해 주세요."),
                    )
                } else if (
                    normalizedEmail.length > 254 ||
                    !emailPattern.matches(
                        normalizedEmail
                    )
                ) {
                    put(
                        "email",
                        listOf(
                            "올바른 이메일 주소를 입력해 주세요."
                        ),
                    )
                }

                when {
                    normalizedUsername.isEmpty() ->
                        put(
                            "username",
                            listOf(
                                "아이디를 입력해 주세요."
                            ),
                        )

                    normalizedUsername.length !in
                        4..150 ->
                        put(
                            "username",
                            listOf(
                                "아이디는 4~150자로 입력해 주세요."
                            ),
                        )

                    !usernamePattern.matches(
                        normalizedUsername
                    ) ->
                        put(
                            "username",
                            listOf(
                                "아이디는 영문, 숫자, ., _, -만 사용할 수 있습니다."
                            ),
                        )
                }

                if (
                    password.length !in 12..64 ||
                    !hasLetter ||
                    !hasDigit
                ) {
                    put(
                        "password",
                        listOf(
                            "비밀번호는 12~64자이며 영문과 숫자를 포함해야 합니다."
                        ),
                    )
                }
            }

        if (localErrors.isNotEmpty()) {
            _state.value =
                _state.value.copy(
                    error = null,
                    fieldErrors = localErrors,
                    retryAfterSeconds = null,
                )
            return
        }

        val repository = p1AuthRepository

        if (repository == null) {
            _state.value =
                _state.value.copy(
                    error =
                        "회원가입 기능을 사용할 수 없습니다.",
                    fieldErrors = emptyMap(),
                )
            return
        }

        signupChallengeId = null
        signupClaimTicket = null
        signupIdempotencyKey = null

        signupName = normalizedName
        signupEmail = normalizedEmail

        viewModelScope.launch {
            _state.value =
                _state.value.copy(
                    submitting = true,
                    error = null,
                    fieldErrors = emptyMap(),
                    retryAfterSeconds = null,
                    signupStage =
                        SignupStage.IDLE,
                    signupMessage = null,
                )

            when (
                val result =
                    repository
                        .createContractVerificationChallenge(
                            request =
                                P1ChallengeRequest(
                                    name =
                                        normalizedName,
                                    email =
                                        normalizedEmail,
                                ),
                            idempotencyKey =
                                UUID.randomUUID()
                                    .toString(),
                        )
            ) {
                is ApiResult.Success -> {
                    signupChallengeId =
                        result.value.challengeId

                    _state.value =
                        _state.value.copy(
                            submitting = false,
                            signupStage =
                                SignupStage
                                    .OTP_REQUIRED,
                            signupMessage =
                                result.value.message,
                            challengeExpiresInSeconds =
                                result.value
                                    .expiresIn,
                            resendAfterSeconds =
                                result.value
                                    .resendAfter,
                            fieldErrors =
                                emptyMap(),
                            retryAfterSeconds =
                                null,
                        )
                }

                is ApiResult.Failure -> {
                    _state.value =
                        _state.value.copy(
                            submitting = false,
                            error =
                                result.message,
                            fieldErrors =
                                result.fieldErrors,
                            retryAfterSeconds =
                                result
                                    .retryAfterSeconds,
                        )
                }
            }
        }
    }

    fun verifySignupOtp(
        otpCode: String,
    ) {
        if (_state.value.submitting) return

        val normalizedOtp = otpCode.trim()

        if (!Regex("""\d{6}""").matches(normalizedOtp)) {
            _state.value = _state.value.copy(
                error = null,
                fieldErrors = mapOf(
                    "otp_code" to listOf("인증번호 6자리를 입력해 주세요.")
                ),
                retryAfterSeconds = null,
            )
            return
        }

        val challengeId = signupChallengeId
        if (challengeId == null) {
            _state.value = _state.value.copy(
                error = "인증 요청을 다시 시작해 주세요.",
                fieldErrors = emptyMap(),
            )
            return
        }

        val repository = p1AuthRepository
        if (repository == null) {
            _state.value = _state.value.copy(
                error = "회원가입 기능을 사용할 수 없습니다.",
                fieldErrors = emptyMap(),
            )
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )

            when (
                val result = repository.verifyContractVerificationChallenge(
                    challengeId = challengeId,
                    request = P1OtpVerificationRequest(
                        otpCode = normalizedOtp,
                    ),
                )
            ) {
                is ApiResult.Success -> {
                    signupClaimTicket = result.value.claimTicket
                    signupChallengeId = null

                    // 같은 회원가입 제출을 재시도할 때 동일 키를 사용한다.
                    signupIdempotencyKey = UUID.randomUUID().toString()

                    _state.value = _state.value.copy(
                        submitting = false,
                        signupStage = SignupStage.ACCOUNT_REQUIRED,
                        signupMessage = "인증이 완료되었습니다. 사용할 아이디와 비밀번호를 입력해 주세요.",
                        challengeExpiresInSeconds = null,
                        resendAfterSeconds = null,
                        fieldErrors = emptyMap(),
                        retryAfterSeconds = null,
                    )
                }

                is ApiResult.Failure -> {
                    _state.value = _state.value.copy(
                        submitting = false,
                        error = result.message,
                        fieldErrors = result.fieldErrors,
                        retryAfterSeconds = result.retryAfterSeconds,
                    )
                }
            }
        }
    }

    fun completeSignup(
        username: String,
        password: String,
        consents: List<P1ConsentRequest>,
    ) {
        if (_state.value.submitting) return

        val normalizedUsername = username.trim()

        val localErrors = buildMap<String, List<String>> {
            when {
                normalizedUsername.length !in 4..150 ->
                    put("username", listOf("아이디는 4~150자로 입력해 주세요."))

                !Regex("""[A-Za-z0-9._-]+""").matches(normalizedUsername) ->
                    put("username", listOf("아이디는 영문, 숫자, ., _, -만 사용할 수 있습니다."))
            }

            val hasLetter = password.any {
                it in 'A'..'Z' || it in 'a'..'z'
            }
            val hasDigit = password.any(Char::isDigit)

            if (password.length !in 12..64 || !hasLetter || !hasDigit) {
                put(
                    "password",
                    listOf("비밀번호는 12~64자이며 영문과 숫자를 포함해야 합니다."),
                )
            }

            val consentMap = consents.associateBy { it.code }

            if (consentMap[P1ConsentCode.TERMS_OF_SERVICE]?.agreed != true) {
                put("terms", listOf("이용약관 동의가 필요합니다."))
            }

            if (consentMap[P1ConsentCode.PRIVACY_COLLECTION_USE]?.agreed != true) {
                put("privacy", listOf("개인정보 수집·이용 동의가 필요합니다."))
            }
        }

        if (localErrors.isNotEmpty()) {
            _state.value = _state.value.copy(
                error = null,
                fieldErrors = localErrors,
                retryAfterSeconds = null,
            )
            return
        }

        val claimTicket = signupClaimTicket
        if (claimTicket == null) {
            _state.value = _state.value.copy(
                error = "계약 인증을 다시 진행해 주세요.",
                fieldErrors = emptyMap(),
            )
            return
        }

        val repository = p1AuthRepository
        if (repository == null) {
            _state.value = _state.value.copy(
                error = "회원가입 기능을 사용할 수 없습니다.",
                fieldErrors = emptyMap(),
            )
            return
        }

        val idempotencyKey =
            signupIdempotencyKey ?: UUID.randomUUID().toString().also {
                signupIdempotencyKey = it
            }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )

            when (
                val result = repository.signup(
                    request = P1SignupRequest(
                        claimTicket = claimTicket,
                        name = signupName
                            ?: return@launch,
                        email = signupEmail
                            ?: return@launch,
                        username = normalizedUsername,
                        password = password,
                        consents = consents,
                    ),
                    idempotencyKey = idempotencyKey,
                )
            ) {
                is ApiResult.Success -> {
                    signupClaimTicket = null
                    signupChallengeId = null
                    signupIdempotencyKey = null
                    signupName = null
                    signupEmail = null

                    if (result.value.user.roleCode != "CUSTOMER") {
                        authRepository.logout()

                        _state.value = _state.value.copy(
                            submitting = false,
                            authenticated = false,
                            error = "고객 계정으로 로그인해 주세요.",
                            fieldErrors = emptyMap(),
                            retryAfterSeconds = null,
                        )
                    } else {
                        // signup() success stores the returned session.
                        // This UX intentionally returns to login, so clear it.
                        authRepository.logout()

                        _state.value = _state.value.copy(
                            submitting = false,
                            authenticated = false,
                            offlinePreview = false,
                            error = null,
                            fieldErrors = emptyMap(),
                            retryAfterSeconds = null,
                            signupStage = SignupStage.IDLE,
                            signupMessage = null,
                            challengeExpiresInSeconds = null,
                            resendAfterSeconds = null,
                            signupCompletedUsername =
                                normalizedUsername,
                        )
                    }
                }

                is ApiResult.Failure -> {
                    _state.value = _state.value.copy(
                        submitting = false,
                        error = result.message,
                        fieldErrors = result.fieldErrors,
                        retryAfterSeconds = result.retryAfterSeconds,
                    )
                }
            }
        }
    }

    fun consumeSignupCompletion() {
        if (
            _state.value.signupCompletedUsername ==
                null
        ) {
            return
        }

        _state.value =
            _state.value.copy(
                signupCompletedUsername = null,
            )
    }

    fun startPasswordReset(
        name: String,
        username: String,
        email: String,
    ) {
        if (_state.value.submitting) return

        val normalizedName =
            name.trim()

        val normalizedUsername =
            username.trim()

        val normalizedEmail =
            email.trim().lowercase()

        val emailPattern =
            Regex("""^[^\s@]+@[^\s@]+\.[^\s@]+$""")

        val usernamePattern =
            Regex("""^[A-Za-z0-9._-]+$""")

        val localErrors =
            buildMap<String, List<String>> {
                if (normalizedName.isEmpty()) {
                    put(
                        "name",
                        listOf(
                            "이름을 입력해 주세요."
                        ),
                    )
                } else if (
                    normalizedName.length > 100
                ) {
                    put(
                        "name",
                        listOf(
                            "이름은 100자 이하로 입력해 주세요."
                        ),
                    )
                }

                when {
                    normalizedUsername.isEmpty() ->
                        put(
                            "username",
                            listOf(
                                "아이디를 입력해 주세요."
                            ),
                        )

                    normalizedUsername.length !in
                        4..150 ->
                        put(
                            "username",
                            listOf(
                                "아이디는 4~150자로 입력해 주세요."
                            ),
                        )

                    !usernamePattern.matches(
                        normalizedUsername
                    ) ->
                        put(
                            "username",
                            listOf(
                                "아이디는 영문, 숫자, ., _, -만 사용할 수 있습니다."
                            ),
                        )
                }

                if (normalizedEmail.isEmpty()) {
                    put(
                        "email",
                        listOf(
                            "이메일을 입력해 주세요."
                        ),
                    )
                } else if (
                    normalizedEmail.length > 254 ||
                    !emailPattern.matches(
                        normalizedEmail
                    )
                ) {
                    put(
                        "email",
                        listOf(
                            "올바른 이메일 주소를 입력해 주세요."
                        ),
                    )
                }
            }

        if (localErrors.isNotEmpty()) {
            _state.value =
                _state.value.copy(
                    error = null,
                    fieldErrors = localErrors,
                    retryAfterSeconds = null,
                )
            return
        }

        val repository =
            p1AuthRepository

        if (repository == null) {
            _state.value =
                _state.value.copy(
                    error =
                        "비밀번호 재설정 기능을 사용할 수 없습니다.",
                    fieldErrors = emptyMap(),
                )
            return
        }

        passwordResetChallengeId = null
        passwordResetTicket = null
        passwordResetConfirmIdempotencyKey =
            null

        viewModelScope.launch {
            _state.value =
                _state.value.copy(
                    submitting = true,
                    error = null,
                    fieldErrors = emptyMap(),
                    retryAfterSeconds = null,
                    passwordResetStage =
                        PasswordResetStage.IDLE,
                    passwordResetMessage = null,
                    passwordResetTicketExpiresInSeconds =
                        null,
                )

            when (
                val result =
                    repository
                        .createPasswordResetChallenge(
                            request =
                                P1ChallengeRequest(
                                    name =
                                        normalizedName,
                                    username =
                                        normalizedUsername,
                                    email =
                                        normalizedEmail,
                                ),
                            idempotencyKey =
                                UUID.randomUUID()
                                    .toString(),
                        )
            ) {
                is ApiResult.Success -> {
                    passwordResetChallengeId =
                        result.value.challengeId

                    _state.value =
                        _state.value.copy(
                            submitting = false,
                            passwordResetStage =
                                PasswordResetStage
                                    .OTP_REQUIRED,
                            passwordResetMessage =
                                result.value.message,
                            challengeExpiresInSeconds =
                                result.value
                                    .expiresIn,
                            resendAfterSeconds =
                                result.value
                                    .resendAfter,
                            fieldErrors =
                                emptyMap(),
                            retryAfterSeconds =
                                null,
                        )
                }

                is ApiResult.Failure -> {
                    _state.value =
                        _state.value.copy(
                            submitting = false,
                            error =
                                result.message,
                            fieldErrors =
                                result.fieldErrors,
                            retryAfterSeconds =
                                result
                                    .retryAfterSeconds,
                        )
                }
            }
        }
    }

    fun verifyPasswordResetOtp(
        otpCode: String,
    ) {
        if (_state.value.submitting) return

        val normalizedOtp = otpCode.trim()

        if (!Regex("""\d{6}""").matches(normalizedOtp)) {
            _state.value = _state.value.copy(
                error = null,
                fieldErrors = mapOf(
                    "otp_code" to listOf(
                        "인증번호 6자리를 입력해 주세요."
                    )
                ),
                retryAfterSeconds = null,
            )
            return
        }

        val challengeId = passwordResetChallengeId
        if (challengeId == null) {
            _state.value = _state.value.copy(
                error = "인증 요청을 다시 시작해 주세요.",
                fieldErrors = emptyMap(),
            )
            return
        }

        val repository = p1AuthRepository
        if (repository == null) {
            _state.value = _state.value.copy(
                error = "비밀번호 재설정 기능을 사용할 수 없습니다.",
                fieldErrors = emptyMap(),
            )
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )

            when (
                val result =
                    repository.verifyPasswordResetChallenge(
                        challengeId = challengeId,
                        request = P1OtpVerificationRequest(
                            otpCode = normalizedOtp,
                        ),
                    )
            ) {
                is ApiResult.Success -> {
                    passwordResetChallengeId = null
                    passwordResetTicket =
                        result.value.resetTicket
                    passwordResetConfirmIdempotencyKey = null

                    _state.value = _state.value.copy(
                        submitting = false,
                        passwordResetStage =
                            PasswordResetStage.PASSWORD_REQUIRED,
                        passwordResetMessage =
                            "인증이 완료되었습니다. 새 비밀번호를 입력해 주세요.",
                        passwordResetTicketExpiresInSeconds =
                            result.value.expiresIn,
                        challengeExpiresInSeconds = null,
                        resendAfterSeconds = null,
                        fieldErrors = emptyMap(),
                        retryAfterSeconds = null,
                    )
                }

                is ApiResult.Failure -> {
                    _state.value = _state.value.copy(
                        submitting = false,
                        error = result.message,
                        fieldErrors = result.fieldErrors,
                        retryAfterSeconds =
                            result.retryAfterSeconds,
                    )
                }
            }
        }
    }

    fun confirmPasswordReset(
        newPassword: String,
    ) {
        if (_state.value.submitting) return

        val hasAsciiLetter =
            newPassword.any {
                it in 'A'..'Z' || it in 'a'..'z'
            }
        val hasDigit =
            newPassword.any { it in '0'..'9' }

        if (
            newPassword.length !in 12..64 ||
            !hasAsciiLetter ||
            !hasDigit
        ) {
            _state.value = _state.value.copy(
                error = null,
                fieldErrors = mapOf(
                    "password" to listOf(
                        "비밀번호는 12~64자이며 영문과 숫자를 포함해야 합니다."
                    )
                ),
                retryAfterSeconds = null,
            )
            return
        }

        val resetTicket = passwordResetTicket
        if (resetTicket == null) {
            _state.value = _state.value.copy(
                error = "비밀번호 재설정 인증을 다시 진행해 주세요.",
                fieldErrors = emptyMap(),
            )
            return
        }

        val repository = p1AuthRepository
        if (repository == null) {
            _state.value = _state.value.copy(
                error = "비밀번호 재설정 기능을 사용할 수 없습니다.",
                fieldErrors = emptyMap(),
            )
            return
        }

        /*
         * Confirm 요청이 네트워크 오류 등으로 재시도되어도
         * 동일한 Idempotency-Key를 사용한다.
         */
        val idempotencyKey =
            passwordResetConfirmIdempotencyKey
                ?: UUID.randomUUID().toString().also {
                    passwordResetConfirmIdempotencyKey = it
                }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )

            when (
                val result =
                    repository.confirmPasswordReset(
                        request =
                            P1PasswordResetConfirmRequest(
                                resetTicket = resetTicket,
                                password = newPassword,
                            ),
                        idempotencyKey = idempotencyKey,
                    )
            ) {
                is ApiResult.Success -> {
                    passwordResetTicket = null
                    passwordResetChallengeId = null
                    passwordResetConfirmIdempotencyKey = null

                    if (
                        result.value.passwordReset &&
                        result.value.sessionsRevoked
                    ) {
                        _state.value = _state.value.copy(
                            submitting = false,
                            passwordResetStage =
                                PasswordResetStage.RESULT,
                            passwordResetMessage =
                                "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.",
                            passwordResetTicketExpiresInSeconds =
                                null,
                            challengeExpiresInSeconds = null,
                            resendAfterSeconds = null,
                            fieldErrors = emptyMap(),
                            retryAfterSeconds = null,
                        )
                    } else {
                        _state.value = _state.value.copy(
                            submitting = false,
                            error =
                                "비밀번호 변경 결과를 확인하지 못했습니다.",
                            fieldErrors = emptyMap(),
                        )
                    }
                }

                is ApiResult.Failure -> {
                    _state.value = _state.value.copy(
                        submitting = false,
                        error = result.message,
                        fieldErrors = result.fieldErrors,
                        retryAfterSeconds =
                            result.retryAfterSeconds,
                    )
                }
            }
        }
    }

    fun cancelPasswordReset() {
        if (_state.value.submitting) return

        passwordResetChallengeId = null
        passwordResetTicket = null
        passwordResetConfirmIdempotencyKey = null

        _state.value = _state.value.copy(
            passwordResetStage =
                PasswordResetStage.IDLE,
            passwordResetMessage = null,
            passwordResetTicketExpiresInSeconds = null,
            challengeExpiresInSeconds = null,
            resendAfterSeconds = null,
            error = null,
            fieldErrors = emptyMap(),
            retryAfterSeconds = null,
        )
    }

    fun startUsernameRecovery(
        name: String,
        email: String,
    ) {
        if (_state.value.submitting) return

        val normalizedName =
            name.trim()

        val normalizedEmail =
            email.trim().lowercase()

        val emailPattern =
            Regex("""^[^\s@]+@[^\s@]+\.[^\s@]+$""")

        val localErrors =
            buildMap<String, List<String>> {
                if (normalizedName.isEmpty()) {
                    put(
                        "name",
                        listOf(
                            "이름을 입력해 주세요."
                        ),
                    )
                } else if (
                    normalizedName.length > 100
                ) {
                    put(
                        "name",
                        listOf(
                            "이름은 100자 이하로 입력해 주세요."
                        ),
                    )
                }

                if (normalizedEmail.isEmpty()) {
                    put(
                        "email",
                        listOf(
                            "이메일을 입력해 주세요."
                        ),
                    )
                } else if (
                    normalizedEmail.length > 254 ||
                    !emailPattern.matches(
                        normalizedEmail
                    )
                ) {
                    put(
                        "email",
                        listOf(
                            "올바른 이메일 주소를 입력해 주세요."
                        ),
                    )
                }
            }

        if (localErrors.isNotEmpty()) {
            _state.value =
                _state.value.copy(
                    error = null,
                    fieldErrors = localErrors,
                    retryAfterSeconds = null,
                )
            return
        }

        val repository =
            p1AuthRepository

        if (repository == null) {
            _state.value =
                _state.value.copy(
                    error =
                        "아이디 찾기 기능을 사용할 수 없습니다.",
                    fieldErrors = emptyMap(),
                )
            return
        }

        usernameRecoveryChallengeId = null

        viewModelScope.launch {
            _state.value =
                _state.value.copy(
                    submitting = true,
                    error = null,
                    fieldErrors = emptyMap(),
                    retryAfterSeconds = null,
                    usernameRecoveryStage =
                        UsernameRecoveryStage.IDLE,
                    usernameRecoveryMessage = null,
                    recoveredMaskedUsername = null,
                )

            when (
                val result =
                    repository
                        .createUsernameRecoveryChallenge(
                            request =
                                P1ChallengeRequest(
                                    name =
                                        normalizedName,
                                    email =
                                        normalizedEmail,
                                ),
                            idempotencyKey =
                                UUID.randomUUID()
                                    .toString(),
                        )
            ) {
                is ApiResult.Success -> {
                    usernameRecoveryChallengeId =
                        result.value.challengeId

                    _state.value =
                        _state.value.copy(
                            submitting = false,
                            usernameRecoveryStage =
                                UsernameRecoveryStage
                                    .OTP_REQUIRED,
                            usernameRecoveryMessage =
                                result.value.message,
                            challengeExpiresInSeconds =
                                result.value
                                    .expiresIn,
                            resendAfterSeconds =
                                result.value
                                    .resendAfter,
                            fieldErrors =
                                emptyMap(),
                            retryAfterSeconds =
                                null,
                        )
                }

                is ApiResult.Failure -> {
                    _state.value =
                        _state.value.copy(
                            submitting = false,
                            error =
                                result.message,
                            fieldErrors =
                                result.fieldErrors,
                            retryAfterSeconds =
                                result
                                    .retryAfterSeconds,
                        )
                }
            }
        }
    }

    fun verifyUsernameRecoveryOtp(
        otpCode: String,
    ) {
        if (_state.value.submitting) return

        val normalizedOtp = otpCode.trim()

        if (!Regex("""\d{6}""").matches(normalizedOtp)) {
            _state.value = _state.value.copy(
                error = null,
                fieldErrors = mapOf(
                    "otp_code" to listOf(
                        "인증번호 6자리를 입력해 주세요."
                    )
                ),
                retryAfterSeconds = null,
            )
            return
        }

        val challengeId = usernameRecoveryChallengeId
        if (challengeId == null) {
            _state.value = _state.value.copy(
                error = "인증 요청을 다시 시작해 주세요.",
                fieldErrors = emptyMap(),
            )
            return
        }

        val repository = p1AuthRepository
        if (repository == null) {
            _state.value = _state.value.copy(
                error = "아이디 찾기 기능을 사용할 수 없습니다.",
                fieldErrors = emptyMap(),
            )
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )

            when (
                val result =
                    repository.verifyUsernameRecoveryChallenge(
                        challengeId = challengeId,
                        request = P1OtpVerificationRequest(
                            otpCode = normalizedOtp,
                        ),
                    )
            ) {
                is ApiResult.Success -> {
                    usernameRecoveryChallengeId = null

                    _state.value = _state.value.copy(
                        submitting = false,
                        usernameRecoveryStage =
                            UsernameRecoveryStage.RESULT,
                        usernameRecoveryMessage =
                            "아이디 확인이 완료되었습니다.",
                        recoveredMaskedUsername =
                            result.value.maskedUsername,
                        challengeExpiresInSeconds = null,
                        resendAfterSeconds = null,
                        fieldErrors = emptyMap(),
                        retryAfterSeconds = null,
                    )
                }

                is ApiResult.Failure -> {
                    _state.value = _state.value.copy(
                        submitting = false,
                        error = result.message,
                        fieldErrors = result.fieldErrors,
                        retryAfterSeconds =
                            result.retryAfterSeconds,
                    )
                }
            }
        }
    }

    fun cancelUsernameRecovery() {
        if (_state.value.submitting) return

        usernameRecoveryChallengeId = null

        _state.value = _state.value.copy(
            usernameRecoveryStage =
                UsernameRecoveryStage.IDLE,
            usernameRecoveryMessage = null,
            recoveredMaskedUsername = null,
            challengeExpiresInSeconds = null,
            resendAfterSeconds = null,
            error = null,
            fieldErrors = emptyMap(),
            retryAfterSeconds = null,
        )
    }

    fun cancelSignup() {
        if (_state.value.submitting) return

        signupChallengeId = null
        signupClaimTicket = null
        signupIdempotencyKey = null
        signupName = null
        signupEmail = null

        _state.value = _state.value.copy(
            signupStage = SignupStage.IDLE,
            signupMessage = null,
            challengeExpiresInSeconds = null,
            resendAfterSeconds = null,
            error = null,
            fieldErrors = emptyMap(),
            retryAfterSeconds = null,
        )
    }

    fun login(
        username: String,
        password: String,
    ) {
        if (_state.value.submitting) return

        val normalizedUsername = username.trim()

        val localErrors = buildMap<String, List<String>> {
            if (normalizedUsername.isEmpty()) {
                put("username", listOf("아이디를 입력해 주세요."))
            } else if (normalizedUsername.length > 150) {
                put("username", listOf("아이디는 150자 이하로 입력해 주세요."))
            }

            if (password.isEmpty()) {
                put("password", listOf("비밀번호를 입력해 주세요."))
            } else if (password.length > 64) {
                put("password", listOf("비밀번호는 64자 이하로 입력해 주세요."))
            }
        }

        if (localErrors.isNotEmpty()) {
            _state.value = _state.value.copy(
                error = null,
                fieldErrors = localErrors,
                retryAfterSeconds = null,
            )
            return
        }

        val repository = p1AuthRepository
        if (repository == null) {
            _state.value = _state.value.copy(
                error = "로그인 기능을 사용할 수 없습니다.",
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
                fieldErrors = emptyMap(),
                retryAfterSeconds = null,
            )

            _state.value = when (
                val result = repository.login(
                    P1PasswordLoginRequest(
                        username = normalizedUsername,
                        password = password,
                    )
                )
            ) {
                is ApiResult.Success -> {
                    if (result.value.user.roleCode != "CUSTOMER") {
                        authRepository.logout()

                        _state.value.copy(
                            submitting = false,
                            authenticated = false,
                            offlinePreview = false,
                            error = "고객 계정으로 로그인해 주세요.",
                            fieldErrors = emptyMap(),
                            retryAfterSeconds = null,
                        )
                    } else {
                        _state.value.copy(
                            submitting = false,
                            authenticated = true,
                            offlinePreview = false,
                            error = null,
                            fieldErrors = emptyMap(),
                            retryAfterSeconds = null,
                        )
                    }
                }

                is ApiResult.Failure -> _state.value.copy(
                    submitting = false,
                    authenticated = false,
                    error = result.message,
                    fieldErrors = result.fieldErrors,
                    retryAfterSeconds = result.retryAfterSeconds,
                    backendAvailable = result.code != "NETWORK_ERROR",
                )
            }
        }
    }

    fun demoLogin() {
        if (_state.value.submitting) return
        viewModelScope.launch {
            _state.value = _state.value.copy(submitting = true, error = null)
            val loginCode = demoCustomerCode.trim().ifBlank {
                P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
            }
            _state.value = when (val result = authRepository.demoLogin(loginCode)) {
                is ApiResult.Success -> {
                    if (result.value.user.roleCode != "CUSTOMER") {
                        authRepository.logout()
                        _state.value.copy(
                            submitting = false,
                            authenticated = false,
                            offlinePreview = false,
                            error = "고객 계정으로 로그인해 주세요.",
                        )
                    } else {
                        _state.value.copy(
                            submitting = false,
                            authenticated = true,
                            offlinePreview = false,
                        )
                    }
                }
                is ApiResult.Failure -> _state.value.copy(
                    submitting = false,
                    error = result.message,
                    backendAvailable = result.code != "NETWORK_ERROR",
                )
            }
        }
    }

    fun startOfflinePreview() {
        _state.value = _state.value.copy(authenticated = true, offlinePreview = true, error = null)
    }
}

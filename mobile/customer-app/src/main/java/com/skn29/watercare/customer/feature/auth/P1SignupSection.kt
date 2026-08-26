package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.P1ConsentCode
import com.skn29.watercare.core.model.P1ConsentRequest
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.WaterBridgeCustomerPalette
import kotlinx.coroutines.delay

/*
 * P1-A G2는 consent version을 필수 문자열로 정의하지만
 * 실제 운영 version 값 자체는 동결하지 않았다.
 *
 * 따라서 아래 값은 G3 Runtime 연동 전 Mobile fixture다.
 * 실제 API Smoke 전에 Backend와 운영 version을 확정해서 교체해야 한다.
 */
private const val P1A_MOBILE_CONSENT_VERSION_FIXTURE = "v1"

@Composable
internal fun P1SignupSection(
    viewModel: AuthViewModel,
    state: AuthUiState,
    onBackToLogin: () -> Unit,
) {
    val palette = WaterBridgeCustomerPalette

    // 인증/계약/OTP/비밀번호는 영속 저장하지 않고
    // 현재 Compose 생명주기 메모리에서만 유지한다.
    var signupName by remember { mutableStateOf("") }
    var signupEmail by remember { mutableStateOf("") }
    var otpCode by remember { mutableStateOf("") }
    var signupUsername by remember { mutableStateOf("") }
    var signupPassword by remember { mutableStateOf("") }

    var termsAgreed by remember { mutableStateOf(false) }
    var privacyAgreed by remember { mutableStateOf(false) }
    var marketingAgreed by remember { mutableStateOf(false) }

    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .p1AuthFormContainer(),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(
            text = "회원가입",
            style = MaterialTheme.typography.headlineSmall,
        )

        when (state.signupStage) {
            SignupStage.IDLE -> {
                Text(
                    text =
                        "회원가입 정보를 입력한 뒤 이메일 인증을 진행합니다.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color = palette.textMuted,
                )

                P1AuthField(
                    value = signupName,
                    onValueChange = {
                        signupName = it
                    },
                    modifier =
                        Modifier.fillMaxWidth(),
                    label = {
                        Text("이름")
                    },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["name"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions =
                        KeyboardOptions(
                            keyboardType =
                                KeyboardType.Text,
                            imeAction =
                                ImeAction.Next,
                        ),
                )

                FieldError(
                    state.fieldErrors["name"]
                        ?.firstOrNull()
                )

                P1AuthField(
                    value = signupEmail,
                    onValueChange = {
                        signupEmail = it
                    },
                    modifier =
                        Modifier.fillMaxWidth(),
                    label = {
                        Text("이메일")
                    },
                    placeholder = {
                        Text(
                            "name@example.com"
                        )
                    },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["email"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions =
                        KeyboardOptions(
                            keyboardType =
                                KeyboardType.Email,
                            imeAction =
                                ImeAction.Next,
                        ),
                )

                FieldError(
                    state.fieldErrors["email"]
                        ?.firstOrNull()
                )

                ReferenceGlassButton(
                    text =
                        "이메일 인증번호 받기",
                    palette = palette,
                    onClick = {
                        viewModel
                            .startSignupVerification(
                                name =
                                    signupName,
                                email =
                                    signupEmail,
                                username =
                                    signupUsername,
                                password =
                                    signupPassword,
                            )
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable ==
                                true,
                    accent = true,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }

            SignupStage.OTP_REQUIRED -> {
                var resendRemaining by
                    remember(
                        state.signupChallengeVersion
                    ) {
                        mutableIntStateOf(
                            state.resendAfterSeconds
                                ?: 0
                        )
                    }

                var otpExpiresRemaining by
                    remember(
                        state.signupChallengeVersion
                    ) {
                        mutableIntStateOf(
                            state.challengeExpiresInSeconds
                                ?: 0
                        )
                    }

                LaunchedEffect(
                    state.signupChallengeVersion
                ) {
                    resendRemaining =
                        state.resendAfterSeconds
                            ?: 0

                    otpExpiresRemaining =
                        state.challengeExpiresInSeconds
                            ?: 0

                    while (
                        resendRemaining > 0 ||
                        otpExpiresRemaining > 0
                    ) {
                        delay(1_000L)

                        if (resendRemaining > 0) {
                            resendRemaining -= 1
                        }

                        if (otpExpiresRemaining > 0) {
                            otpExpiresRemaining -= 1
                        }
                    }
                }

                LaunchedEffect(
                    state.retryAfterSeconds
                ) {
                    val retry =
                        state.retryAfterSeconds
                            ?: return@LaunchedEffect

                    if (retry > resendRemaining) {
                        resendRemaining = retry
                    }
                }

                state.signupMessage?.let { message ->
                    Text(
                        text = message,
                        style =
                            MaterialTheme
                                .typography
                                .bodyMedium,
                    )
                }

                if (otpExpiresRemaining > 0) {
                    Text(
                        text =
                            "인증번호 유효시간: " +
                                "${otpExpiresRemaining}초",
                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,
                        color = palette.textMuted,
                    )
                } else {
                    Text(
                        text =
                            "인증번호가 만료되었어요. 새 인증번호를 받아 주세요.",
                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,
                        color =
                            MaterialTheme
                                .colorScheme
                                .error,
                    )
                }

                val otpVerificationFailed =
                    state.fieldErrors["otp_code"]
                        .isNullOrEmpty()
                        .not()

                val challengeNeedsReplacement =
                    otpExpiresRemaining <= 0 ||
                        state.retryAfterSeconds != null

                if (resendRemaining > 0) {
                    Text(
                        text =
                            "\uC778\uC99D\uBC88\uD638\uB97C \uBC1B\uC9C0 \uBABB\uD588\uB2E4\uBA74 " +
                                "${resendRemaining}\uCD08 \uD6C4 \uC7AC\uC804\uC1A1\uD560 \uC218 \uC788\uC5B4\uC694.",
                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,
                        color = palette.textMuted,
                    )
                } else {
                    Text(
                        text =
                            "\uC778\uC99D\uBC88\uD638\uAC00 \uC624\uC9C0 \uC54A\uC558\uB2E4\uBA74 \uC7AC\uC804\uC1A1\uD574 \uC8FC\uC138\uC694.",
                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,
                        color = palette.textMuted,
                    )
                }

                P1AuthField(
                    value = otpCode,
                    onValueChange = { value ->
                        val nextValue =
                            value
                                .filter(Char::isDigit)
                                .take(6)

                        if (nextValue != otpCode) {
                            viewModel
                                .clearSignupOtpFeedback()
                        }

                        otpCode = nextValue
                    },
                    modifier =
                        Modifier.fillMaxWidth(),
                    label = {
                        Text(
                            "\uC778\uC99D\uBC88\uD638 6\uC790\uB9AC"
                        )
                    },
                    singleLine = true,
                    enabled =
                        !state.submitting &&
                            !challengeNeedsReplacement,
                    isError =
                        otpVerificationFailed,
                    keyboardOptions =
                        KeyboardOptions(
                            keyboardType =
                                KeyboardType
                                    .NumberPassword,
                            imeAction =
                                ImeAction.Done,
                        ),
                )

                FieldError(
                    state.fieldErrors["otp_code"]
                        ?.firstOrNull()
                )

                ReferenceGlassButton(
                    text =
                        "\uC778\uC99D \uD655\uC778",
                    palette = palette,
                    onClick = {
                        viewModel
                            .verifySignupOtp(
                                otpCode
                            )
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable ==
                                true &&
                            !challengeNeedsReplacement &&
                            otpCode.length == 6,
                    accent = true,
                    modifier =
                        Modifier.fillMaxWidth(),
                )

                ReferenceGlassButton(
                    text =
                        if (resendRemaining > 0) {
                            "\uC778\uC99D\uBC88\uD638 \uC7AC\uC804\uC1A1 " +
                                "${resendRemaining}\uCD08"
                        } else {
                            "\uC778\uC99D\uBC88\uD638 \uC7AC\uC804\uC1A1"
                        },
                    palette = palette,
                    onClick = {
                        otpCode = ""

                        viewModel
                            .resendSignupVerification()
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable ==
                                true &&
                            resendRemaining <= 0,
                    accent = false,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }
            SignupStage.ACCOUNT_REQUIRED -> {
                state.signupMessage?.let { message ->
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

                Text(
                    text =
                        "이메일 인증이 완료되었습니다. 약관을 확인하고 회원가입을 완료해 주세요.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color = palette.textMuted,
                )

                P1AuthField(
                    value = signupUsername,
                    onValueChange = { value ->
                        signupUsername =
                            value.take(20)
                    },
                    modifier =
                        Modifier.fillMaxWidth(),
                    label = {
                        Text(
                            "\uC544\uC774\uB514"
                        )
                    },
                    supportingText = {
                        Text(
                            "4~20\uC790, \uC601\uBB38\u00B7\uC22B\uC790\u00B7.\u00B7_\u00B7- \uC0AC\uC6A9"
                        )
                    },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["username"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions =
                        KeyboardOptions(
                            keyboardType =
                                KeyboardType.Text,
                            imeAction =
                                ImeAction.Next,
                        ),
                )

                FieldError(
                    state.fieldErrors["username"]
                        ?.firstOrNull()
                )

                P1AuthField(
                    value = signupPassword,
                    onValueChange = { value ->
                        signupPassword =
                            value.take(20)
                    },
                    modifier =
                        Modifier.fillMaxWidth(),
                    label = {
                        Text(
                            "\uBE44\uBC00\uBC88\uD638"
                        )
                    },
                    supportingText = {
                        Text(
                            "12~20\uC790, \uC601\uBB38\uACFC \uC22B\uC790\uB97C \uD3EC\uD568\uD574 \uC8FC\uC138\uC694."
                        )
                    },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["password"]
                            .isNullOrEmpty()
                            .not(),
                    visualTransformation =
                        PasswordVisualTransformation(),
                    keyboardOptions =
                        KeyboardOptions(
                            keyboardType =
                                KeyboardType.Password,
                            imeAction =
                                ImeAction.Done,
                        ),
                )

                FieldError(
                    state.fieldErrors["password"]
                        ?.firstOrNull()
                )
                ConsentRow(
                    checked = termsAgreed,
                    onCheckedChange = { termsAgreed = it },
                    label = "[필수] 이용약관 동의",
                    enabled = !state.submitting,
                )

                FieldError(
                    state.fieldErrors["terms"]
                        ?.firstOrNull()
                )

                ConsentRow(
                    checked = privacyAgreed,
                    onCheckedChange = { privacyAgreed = it },
                    label = "[필수] 개인정보 수집·이용 동의",
                    enabled = !state.submitting,
                )

                FieldError(
                    state.fieldErrors["privacy"]
                        ?.firstOrNull()
                )

                ConsentRow(
                    checked = marketingAgreed,
                    onCheckedChange = { marketingAgreed = it },
                    label = "[선택] 마케팅 정보 수신 동의",
                    enabled = !state.submitting,
                )

                ReferenceGlassButton(
                    text = "회원가입 완료",
                    palette = palette,
                    onClick = {
                        viewModel.completeSignup(
                            username = signupUsername,
                            password = signupPassword,
                            consents = listOf(
                                P1ConsentRequest(
                                    code =
                                        P1ConsentCode.TERMS_OF_SERVICE,
                                    version =
                                        P1A_MOBILE_CONSENT_VERSION_FIXTURE,
                                    agreed = termsAgreed,
                                ),
                                P1ConsentRequest(
                                    code =
                                        P1ConsentCode.PRIVACY_COLLECTION_USE,
                                    version =
                                        P1A_MOBILE_CONSENT_VERSION_FIXTURE,
                                    agreed = privacyAgreed,
                                ),
                                P1ConsentRequest(
                                    code =
                                        P1ConsentCode.MARKETING,
                                    version =
                                        P1A_MOBILE_CONSENT_VERSION_FIXTURE,
                                    agreed = marketingAgreed,
                                ),
                            ),
                        )
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable == true,
                    accent = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        state.retryAfterSeconds?.let { seconds ->
            Text(
                text = "${seconds}초 후 다시 시도해 주세요.",
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodySmall,
                color = palette.textMuted,
            )
        }

        if (
            state.error != null &&
            state.fieldErrors.isEmpty()
        ) {
            Text(
                text = state.error,
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }

        ReferenceGlassButton(
            text = "로그인으로 돌아가기",
            palette = palette,
            onClick = {
                viewModel.cancelSignup()
                onBackToLogin()
            },
            enabled = !state.submitting,
            accent = false,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun ConsentRow(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    label: String,
    enabled: Boolean,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Start,
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange,
            enabled = enabled,
        )

        Text(
            text = label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun FieldError(
    message: String?,
) {
    message ?: return

    Text(
        text = message,
        modifier = Modifier.fillMaxWidth(),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.error,
    )
}
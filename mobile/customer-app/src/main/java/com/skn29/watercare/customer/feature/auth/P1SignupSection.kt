package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
    var customerNumber by remember { mutableStateOf("") }
    var contractNumber by remember { mutableStateOf("") }
    var otpCode by remember { mutableStateOf("") }
    var signupUsername by remember { mutableStateOf("") }
    var signupPassword by remember { mutableStateOf("") }

    var termsAgreed by remember { mutableStateOf(false) }
    var privacyAgreed by remember { mutableStateOf(false) }
    var marketingAgreed by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            text = "회원가입",
            style = MaterialTheme.typography.titleMedium,
        )

        when (state.signupStage) {
            SignupStage.IDLE -> {
                Text(
                    text = "고객번호와 계약번호를 확인한 뒤 인증을 진행합니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = palette.textMuted,
                )

                OutlinedTextField(
                    value = customerNumber,
                    onValueChange = { customerNumber = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("고객번호") },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["customer_number"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Text,
                        imeAction = ImeAction.Next,
                    ),
                )

                FieldError(
                    state.fieldErrors["customer_number"]
                        ?.firstOrNull()
                )

                OutlinedTextField(
                    value = contractNumber,
                    onValueChange = { contractNumber = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("계약번호") },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["contract_number"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Text,
                        imeAction = ImeAction.Done,
                    ),
                )

                FieldError(
                    state.fieldErrors["contract_number"]
                        ?.firstOrNull()
                )

                ReferenceGlassButton(
                    text = "인증번호 받기",
                    palette = palette,
                    onClick = {
                        viewModel.startSignupVerification(
                            customerNumber = customerNumber,
                            contractNumber = contractNumber,
                        )
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable == true,
                    accent = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            SignupStage.OTP_REQUIRED -> {
                state.signupMessage?.let { message ->
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

                state.challengeExpiresInSeconds?.let { seconds ->
                    Text(
                        text = "인증번호 유효시간: ${seconds}초",
                        style = MaterialTheme.typography.bodySmall,
                        color = palette.textMuted,
                    )
                }

                state.resendAfterSeconds?.let { seconds ->
                    Text(
                        text = "재전송은 ${seconds}초 후 가능합니다.",
                        style = MaterialTheme.typography.bodySmall,
                        color = palette.textMuted,
                    )
                }

                OutlinedTextField(
                    value = otpCode,
                    onValueChange = { value ->
                        otpCode =
                            value
                                .filter(Char::isDigit)
                                .take(6)
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("인증번호 6자리") },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["otp_code"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.NumberPassword,
                        imeAction = ImeAction.Done,
                    ),
                )

                FieldError(
                    state.fieldErrors["otp_code"]
                        ?.firstOrNull()
                )

                ReferenceGlassButton(
                    text = "인증 확인",
                    palette = palette,
                    onClick = {
                        viewModel.verifySignupOtp(otpCode)
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable == true,
                    accent = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            SignupStage.ACCOUNT_REQUIRED -> {
                state.signupMessage?.let { message ->
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

                OutlinedTextField(
                    value = signupUsername,
                    onValueChange = { signupUsername = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("사용할 아이디") },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["username"]
                            .isNullOrEmpty()
                            .not(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Text,
                        imeAction = ImeAction.Next,
                    ),
                )

                FieldError(
                    state.fieldErrors["username"]
                        ?.firstOrNull()
                )

                OutlinedTextField(
                    value = signupPassword,
                    onValueChange = { signupPassword = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("사용할 비밀번호") },
                    supportingText = {
                        Text("12~64자, 영문과 숫자를 포함해 주세요.")
                    },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        state.fieldErrors["password"]
                            .isNullOrEmpty()
                            .not(),
                    visualTransformation =
                        PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Done,
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
                text = "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.",
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
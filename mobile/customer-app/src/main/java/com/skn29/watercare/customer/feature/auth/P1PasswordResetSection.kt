package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.WaterBridgeCustomerPalette

@Composable
internal fun P1PasswordResetSection(
    viewModel: AuthViewModel,
    state: AuthUiState,
    onBackToLogin: () -> Unit,
) {
    val palette = WaterBridgeCustomerPalette

    // 고객번호, 계약번호, OTP, 비밀번호는 현재 화면 메모리에서만 유지한다.
    var customerNumber by remember { mutableStateOf("") }
    var contractNumber by remember { mutableStateOf("") }
    var otpCode by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var passwordMismatch by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            text = "비밀번호 재설정",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )

        when (state.passwordResetStage) {
            PasswordResetStage.IDLE -> {
                Text(
                    text = "고객번호와 계약번호 확인 후 인증 절차를 진행합니다.",
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

                ResetFieldError(
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

                ResetFieldError(
                    state.fieldErrors["contract_number"]
                        ?.firstOrNull()
                )

                ReferenceGlassButton(
                    text = "인증번호 받기",
                    palette = palette,
                    onClick = {
                        viewModel.startPasswordReset(
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

            PasswordResetStage.OTP_REQUIRED -> {
                state.passwordResetMessage?.let { message ->
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
                        text = "재요청은 ${seconds}초 후 가능합니다.",
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

                ResetFieldError(
                    state.fieldErrors["otp_code"]
                        ?.firstOrNull()
                )

                ReferenceGlassButton(
                    text = "인증 확인",
                    palette = palette,
                    onClick = {
                        viewModel.verifyPasswordResetOtp(
                            otpCode
                        )
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable == true,
                    accent = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            PasswordResetStage.PASSWORD_REQUIRED -> {
                state.passwordResetMessage?.let { message ->
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

                state.passwordResetTicketExpiresInSeconds
                    ?.let { seconds ->
                        Text(
                            text = "비밀번호 변경 가능 시간: ${seconds}초",
                            style = MaterialTheme.typography.bodySmall,
                            color = palette.textMuted,
                        )
                    }

                OutlinedTextField(
                    value = newPassword,
                    onValueChange = {
                        newPassword = it
                        passwordMismatch = false
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("새 비밀번호") },
                    supportingText = {
                        Text("12~64자, 영문과 숫자를 포함해 주세요.")
                    },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError =
                        passwordMismatch ||
                            state.fieldErrors["password"]
                                .isNullOrEmpty()
                                .not(),
                    visualTransformation =
                        PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Next,
                    ),
                )

                ResetFieldError(
                    state.fieldErrors["password"]
                        ?.firstOrNull()
                )

                OutlinedTextField(
                    value = confirmPassword,
                    onValueChange = {
                        confirmPassword = it
                        passwordMismatch = false
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("새 비밀번호 확인") },
                    singleLine = true,
                    enabled = !state.submitting,
                    isError = passwordMismatch,
                    visualTransformation =
                        PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Done,
                    ),
                )

                if (passwordMismatch) {
                    Text(
                        text = "입력한 비밀번호가 서로 다릅니다.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }

                ReferenceGlassButton(
                    text = "비밀번호 변경",
                    palette = palette,
                    onClick = {
                        if (newPassword != confirmPassword) {
                            passwordMismatch = true
                        } else {
                            passwordMismatch = false
                            viewModel.confirmPasswordReset(
                                newPassword = newPassword,
                            )
                        }
                    },
                    enabled =
                        !state.submitting &&
                            state.backendAvailable == true,
                    accent = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            PasswordResetStage.RESULT -> {
                Text(
                    text = state.passwordResetMessage
                        ?: "비밀번호가 변경되었습니다.",
                    modifier = Modifier.fillMaxWidth(),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                )

                Text(
                    text = "기존 인증 세션은 폐기되었습니다. 새 비밀번호로 다시 로그인해 주세요.",
                    modifier = Modifier.fillMaxWidth(),
                    style = MaterialTheme.typography.bodySmall,
                    color = palette.textMuted,
                    textAlign = TextAlign.Center,
                )
            }
        }

        state.retryAfterSeconds?.let { seconds ->
            Text(
                text = "${seconds}초 후 다시 시도해 주세요.",
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodySmall,
                color = palette.textMuted,
                textAlign = TextAlign.Center,
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
                textAlign = TextAlign.Center,
            )
        }

        ReferenceGlassButton(
            text = "로그인으로 돌아가기",
            palette = palette,
            onClick = {
                viewModel.cancelPasswordReset()
                onBackToLogin()
            },
            enabled = !state.submitting,
            accent = false,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun ResetFieldError(
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
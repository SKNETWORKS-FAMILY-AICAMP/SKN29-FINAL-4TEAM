package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.WaterBridgeCustomerPalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceBackendStatusCard
import com.skn29.watercare.core.ui.components.ReferenceDashboardScaffold
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceWelcomeCard
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory

@Composable
fun LoginScreen(
    onAuthenticated: (offlinePreview: Boolean) -> Unit,
) {
    val viewModel: AuthViewModel = viewModel(
        factory = VmFactory { _ ->
            AuthViewModel(
                authRepository = WaterCareCore.authRepository,
                backendStatusRepository = WaterCareCore.backendStatusRepository,
                p1AuthRepository = WaterCareCore.p1AuthRepository,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    val palette = WaterBridgeCustomerPalette

    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var signupMode by remember { mutableStateOf(false) }
    var usernameRecoveryMode by remember { mutableStateOf(false) }
    var passwordResetMode by remember { mutableStateOf(false) }

    LaunchedEffect(state.authenticated) {
        if (state.authenticated) {
            onAuthenticated(state.offlinePreview)
        }
    }

    ReferenceDashboardScaffold(
        title = "WaterBridge",
        roleLabel = "고객 서비스",
        palette = palette,
                                brandLogoRes = R.drawable.waterbridge_brand_logo,
backgroundRes = R.drawable.water_background_customer,
        backgroundImageAlpha = 0.12f,
    ) {
        ReferenceWelcomeCard(
            title = "안녕하세요!",
            subtitle = "정수기 관리부터 문제 해결까지 필요한 내용을 쉽게 안내해드릴게요.",
            imageRes = R.drawable.waterbridge_brand_logo,
            palette = palette,
        )

        when {
            state.checkingBackend -> {
                ReferenceBackendStatusCard(
                    title = "서비스를 확인하고 있어요",
                    message = "잠시만 기다려주세요. 연결 상태를 확인하고 있어요.",
                    palette = palette,
                )
            }

            state.backendAvailable == true -> {
                ReferenceBackendStatusCard(
                    title = "서비스에 연결됐어요",
                    message = "정수기 정보와 문의 기능을 바로 이용할 수 있어요.",
                    palette = palette,
                )
            }

            else -> {
                ReferenceBackendStatusCard(
                    title = "서비스에 연결할 수 없어요",
                    message = "인터넷과 서비스 연결을 확인한 뒤 다시 시도해주세요.",
                    palette = palette,
                    warning = true,
                    actionLabel = "다시 확인",
                    onAction = viewModel::checkBackend,
                )
            }
        }

        if (signupMode) {
            P1SignupSection(
                viewModel = viewModel,
                state = state,
                onBackToLogin = {
                    signupMode = false
                },
            )
        } else if (usernameRecoveryMode) {
            P1UsernameRecoverySection(
                viewModel = viewModel,
                state = state,
                onBackToLogin = {
                    usernameRecoveryMode = false
                },
            )
        } else if (passwordResetMode) {
            P1PasswordResetSection(
                viewModel = viewModel,
                state = state,
                onBackToLogin = {
                    passwordResetMode = false
                },
            )
        } else {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                OutlinedTextField(
                value = username,
                onValueChange = { username = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("아이디") },
                singleLine = true,
                enabled = !state.submitting,
                isError = state.fieldErrors["username"].isNullOrEmpty().not(),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Next,
                ),
            )

            state.fieldErrors["username"]
                ?.firstOrNull()
                ?.let { message ->
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }

            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("비밀번호") },
                singleLine = true,
                enabled = !state.submitting,
                isError = state.fieldErrors["password"].isNullOrEmpty().not(),
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Password,
                    imeAction = ImeAction.Done,
                ),
            )

            state.fieldErrors["password"]
                ?.firstOrNull()
                ?.let { message ->
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }

            ReferenceGlassButton(
                text = "로그인",
                palette = palette,
                onClick = {
                    viewModel.login(
                        username = username,
                        password = password,
                    )
                },
                enabled = !state.submitting &&
                    state.backendAvailable == true,
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )

            state.retryAfterSeconds?.let { seconds ->
                Text(
                    text = "${seconds}초 후 다시 시도해 주세요.",
                    modifier = Modifier.fillMaxWidth(),
                    style = MaterialTheme.typography.bodySmall,
                    color = palette.textMuted,
                    textAlign = TextAlign.Center,
                )
            }

            ReferenceGlassButton(
                text = "아이디 찾기",
                palette = palette,
                onClick = {
                    viewModel.cancelSignup()
                    viewModel.cancelUsernameRecovery()
                    viewModel.cancelPasswordReset()
                    signupMode = false
                    passwordResetMode = false
                    usernameRecoveryMode = true
                },
                enabled = !state.submitting,
                accent = false,
                modifier = Modifier.fillMaxWidth(),
            )

            ReferenceGlassButton(
                text = "비밀번호 재설정",
                palette = palette,
                onClick = {
                    viewModel.cancelSignup()
                    viewModel.cancelUsernameRecovery()
                    viewModel.cancelPasswordReset()
                    signupMode = false
                    usernameRecoveryMode = false
                    passwordResetMode = true
                },
                enabled = !state.submitting,
                accent = false,
                modifier = Modifier.fillMaxWidth(),
            )

            ReferenceGlassButton(
                text = "시작하기",
                palette = palette,
                onClick = viewModel::demoLogin,
                enabled = !state.submitting &&
                    state.backendAvailable == true,
                accent = false,
                modifier = Modifier.fillMaxWidth(),
            )

            ReferenceGlassButton(
                text = "회원가입",
                palette = palette,
                onClick = {
                    viewModel.cancelUsernameRecovery()
                    viewModel.cancelPasswordReset()
                    viewModel.cancelSignup()
                    usernameRecoveryMode = false
                    passwordResetMode = false
                    signupMode = true
                },
                enabled = !state.submitting,
                accent = false,
                modifier = Modifier.fillMaxWidth(),
            )

            ReferenceGlassButton(
                text = "서비스 둘러보기",
                palette = palette,
                onClick = viewModel::startOfflinePreview,
                enabled = !state.submitting,
                accent = false,
                modifier = Modifier.fillMaxWidth(),
            )
            }
        }

        if (state.submitting) {
            LoadingBlock(
                when {
                    signupMode ->
                        "회원가입 요청을 처리하고 있어요"

                    usernameRecoveryMode ->
                        "아이디 확인 요청을 처리하고 있어요"

                    passwordResetMode ->
                        "비밀번호 재설정 요청을 처리하고 있어요"

                    else ->
                        "서비스를 시작하고 있어요"
                }
            )
        }

        if (!signupMode && !usernameRecoveryMode && !passwordResetMode) {
            state.error?.let {
                ErrorCard(
                    customerLoginErrorMessage(it),
                    onRetry = {
                        if (username.isNotBlank() || password.isNotBlank()) {
                            viewModel.login(username, password)
                        } else {
                            viewModel.demoLogin()
                        }
                    },
                )
            }
        }

        Text(
            "연결 상태에 따라 일부 기능을 잠시 이용하지 못할 수 있어요.",
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
            textAlign = TextAlign.Center,
        )
    }
}

private fun customerLoginErrorMessage(
    message: String,
): String = when {
    message.contains("고객 계정", ignoreCase = true) ->
        "고객 계정으로 로그인해 주세요."

    else ->
        "서비스를 시작하지 못했어요. 잠시 후 다시 시도해주세요."
}
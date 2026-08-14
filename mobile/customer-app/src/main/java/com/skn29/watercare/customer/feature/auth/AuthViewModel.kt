package com.skn29.watercare.customer.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.customer.BuildConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val checkingBackend: Boolean = true,
    val backendAvailable: Boolean? = null,
    val submitting: Boolean = false,
    val error: String? = null,
    val authenticated: Boolean = false,
    val offlinePreview: Boolean = false,
)

class AuthViewModel(
    private val authRepository: AuthRepository,
    private val backendStatusRepository: BackendStatusRepository,
    private val demoCustomerCode: String = BuildConfig.E2E_CUSTOMER_CODE,
) : ViewModel() {
    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

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

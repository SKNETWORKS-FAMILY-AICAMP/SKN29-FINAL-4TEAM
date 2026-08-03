package com.skn29.watercare.customer.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
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
) : ViewModel() {

    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    init {
        checkBackend()
    }

    fun checkBackend() {
        viewModelScope.launch {
            _state.value = _state.value.copy(
                checkingBackend = true,
                error = null,
            )

            val backendAvailable =
                backendStatusRepository.health() is ApiResult.Success

            if (!backendAvailable) {
                _state.value = _state.value.copy(
                    checkingBackend = false,
                    backendAvailable = false,
                    authenticated = false,
                )
                return@launch
            }

            if (!authRepository.hasSession()) {
                _state.value = _state.value.copy(
                    checkingBackend = false,
                    backendAvailable = true,
                    authenticated = false,
                )
                return@launch
            }

            _state.value = when (val result = authRepository.me()) {
                is ApiResult.Success -> {
                    _state.value.copy(
                        checkingBackend = false,
                        backendAvailable = true,
                        authenticated = true,
                        offlinePreview = false,
                        error = null,
                    )
                }

                is ApiResult.Failure -> {
                    _state.value.copy(
                        checkingBackend = false,
                        backendAvailable = result.code != "NETWORK_ERROR",
                        authenticated = false,
                        offlinePreview = false,
                        error = result.message,
                    )
                }
            }
        }
    }

    fun demoLogin() {
        if (_state.value.submitting) return

        viewModelScope.launch {
            _state.value = _state.value.copy(
                submitting = true,
                error = null,
            )

            _state.value = when (
                val result = authRepository.demoLogin("DEMO-CUSTOMER-001")
            ) {
                is ApiResult.Success -> {
                    _state.value.copy(
                        submitting = false,
                        authenticated = true,
                        offlinePreview = false,
                        error = null,
                    )
                }

                is ApiResult.Failure -> {
                    _state.value.copy(
                        submitting = false,
                        authenticated = false,
                        error = result.message,
                        backendAvailable = result.code != "NETWORK_ERROR",
                    )
                }
            }
        }
    }

    fun startOfflinePreview() {
        _state.value = _state.value.copy(
            authenticated = true,
            offlinePreview = true,
            error = null,
        )
    }
}
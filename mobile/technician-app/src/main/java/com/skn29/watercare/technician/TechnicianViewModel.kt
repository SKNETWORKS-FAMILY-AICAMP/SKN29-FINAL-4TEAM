package com.skn29.watercare.technician

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class TechnicianUiState(
    val checkingBackend: Boolean = true,
    val backendAvailable: Boolean? = null,
    val loading: Boolean = false,
    val user: UserData? = null,
    val offlinePreview: Boolean = false,
    val error: String? = null,
)

class TechnicianViewModel(
    private val authRepository: AuthRepository,
    private val backendStatusRepository: BackendStatusRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(TechnicianUiState())
    val state: StateFlow<TechnicianUiState> = _state.asStateFlow()

    init { checkBackend() }

    fun checkBackend() {
        viewModelScope.launch {
            _state.value = _state.value.copy(checkingBackend = true)
            _state.value = _state.value.copy(
                checkingBackend = false,
                backendAvailable = backendStatusRepository.health() is ApiResult.Success,
            )
        }
    }

    fun demoLogin() {
        if (_state.value.loading) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            _state.value = when (val result = authRepository.demoLogin("DEMO-TECHNICIAN-001")) {
                is ApiResult.Success -> _state.value.copy(loading = false, user = result.value.user)
                is ApiResult.Failure -> _state.value.copy(loading = false, error = result.message)
            }
        }
    }

    fun startOfflinePreview() {
        _state.value = _state.value.copy(
            offlinePreview = true,
            user = UserData(
                id = "00000000-0000-4000-8000-000000000901",
                displayName = "합성 기사 001",
                roleCode = "TECHNICIAN",
                isActive = true,
            ),
        )
    }

    fun logout() {
        viewModelScope.launch {
            if (!_state.value.offlinePreview) authRepository.logout()
            _state.value = TechnicianUiState(
                checkingBackend = false,
                backendAvailable = _state.value.backendAvailable,
            )
        }
    }
}

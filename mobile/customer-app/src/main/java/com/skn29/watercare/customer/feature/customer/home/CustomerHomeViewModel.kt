package com.skn29.watercare.customer.feature.customer.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.CustomerCareRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CustomerHomeViewModel(
    private val authRepository: AuthRepository,
    private val careRepository: CustomerCareRepository,
    private val backendStatusRepository: BackendStatusRepository,
    offlinePreview: Boolean,
) : ViewModel() {
    private val _state = MutableStateFlow(CustomerHomeUiState(offlinePreview = offlinePreview))
    val state: StateFlow<CustomerHomeUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)

            val offlinePreview = _state.value.offlinePreview
            val homeDeferred = async { careRepository.getHome() }
            val healthDeferred =
                if (offlinePreview) null else async { backendStatusRepository.health() }
            val userDeferred =
                if (offlinePreview) null else async { authRepository.me() }

            val home = homeDeferred.await()
            val health = healthDeferred?.await()
            val user = userDeferred?.await()

            val error = when {
                home is ApiResult.Failure -> home.message
                user is ApiResult.Failure -> user.message
                else -> null
            }
            val homeData = when (home) {
                is ApiResult.Success -> home.value
                is ApiResult.Failure -> null
            }
            val userData = when (user) {
                is ApiResult.Success -> user.value
                else -> null
            }

            _state.value = _state.value.copy(
                loading = false,
                home = homeData,
                user = userData,
                backendAvailable =
                    if (offlinePreview) false else health is ApiResult.Success<*>,
                error = error,
            )
        }
    }

    fun logout(onDone: () -> Unit) {
        if (_state.value.loggingOut) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loggingOut = true)
            if (!_state.value.offlinePreview) authRepository.logout()
            onDone()
        }
    }
}
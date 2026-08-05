package com.skn29.watercare.technician

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class TechnicianUiState(
    val checkingBackend: Boolean = true,
    val backendAvailable: Boolean? = null,
    val restoringSession: Boolean = false,
    val loginLoading: Boolean = false,
    val user: UserData? = null,
    val offlinePreview: Boolean = false,
    val visitsLoading: Boolean = false,
    val visits: List<TechnicianVisitSummary> = emptyList(),
    val selectedVisitId: String? = null,
    val reportLoading: Boolean = false,
    val selectedReport: TechnicianPrecheckReport? = null,
    val error: String? = null,
    val reportError: String? = null,
)

class TechnicianViewModel(
    private val authRepository: AuthRepository,
    private val backendStatusRepository: BackendStatusRepository,
    private val visitRepository: TechnicianVisitRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(TechnicianUiState())
    val state: StateFlow<TechnicianUiState> = _state.asStateFlow()

    init {
        initialize()
    }

    private fun initialize() {
        viewModelScope.launch {
            val hasStoredSession = authRepository.hasSession()
            _state.update {
                it.copy(
                    checkingBackend = true,
                    restoringSession = hasStoredSession,
                    error = null,
                )
            }

            val available = backendStatusRepository.health() is ApiResult.Success
            _state.update {
                it.copy(
                    checkingBackend = false,
                    backendAvailable = available,
                )
            }

            if (available && hasStoredSession) {
                restoreSession()
            } else {
                _state.update { it.copy(restoringSession = false) }
            }
        }
    }

    fun checkBackend() {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    checkingBackend = true,
                    error = null,
                )
            }

            val available = backendStatusRepository.health() is ApiResult.Success
            _state.update {
                it.copy(
                    checkingBackend = false,
                    backendAvailable = available,
                )
            }

            val shouldRestoreSession =
                available &&
                    _state.value.user == null &&
                    !_state.value.offlinePreview &&
                    authRepository.hasSession()

            if (shouldRestoreSession) {
                restoreSession()
            }
        }
    }

    private suspend fun restoreSession() {
        _state.update {
            it.copy(
                restoringSession = true,
                loginLoading = false,
                error = null,
            )
        }

        when (val result = authRepository.me()) {
            is ApiResult.Success -> {
                val user = result.value
                if (user.roleCode != "TECHNICIAN") {
                    authRepository.logout()
                    _state.update {
                        it.copy(
                            restoringSession = false,
                            user = null,
                            visits = emptyList(),
                            error = "저장된 계정에 방문기사 권한이 없습니다. 다시 로그인해 주세요.",
                        )
                    }
                } else {
                    _state.update {
                        it.copy(
                            restoringSession = false,
                            user = user,
                            offlinePreview = false,
                            error = null,
                        )
                    }
                    loadVisits()
                }
            }

            is ApiResult.Failure -> {
                val sessionExpired =
                    result.httpStatus == 401 ||
                        result.httpStatus == 403

                if (sessionExpired) {
                    authRepository.logout()
                }

                _state.update {
                    it.copy(
                        restoringSession = false,
                        user = null,
                        visits = emptyList(),
                        error = if (sessionExpired) {
                            "로그인 세션이 만료되었습니다. 다시 로그인해 주세요."
                        } else {
                            result.message
                        },
                    )
                }
            }
        }
    }

    fun demoLogin() {
        if (_state.value.loginLoading || _state.value.restoringSession) return

        viewModelScope.launch {
            _state.update {
                it.copy(
                    loginLoading = true,
                    error = null,
                    offlinePreview = false,
                )
            }

            when (val result = authRepository.demoLogin("DEMO-TECHNICIAN-001")) {
                is ApiResult.Success -> {
                    val user = result.value.user
                    if (user.roleCode != "TECHNICIAN") {
                        authRepository.logout()
                        _state.update {
                            it.copy(
                                loginLoading = false,
                                user = null,
                                error = "방문기사 권한이 없는 계정입니다.",
                            )
                        }
                    } else {
                        _state.update {
                            it.copy(
                                loginLoading = false,
                                user = user,
                            )
                        }
                        loadVisits()
                    }
                }

                is ApiResult.Failure -> {
                    _state.update {
                        it.copy(
                            loginLoading = false,
                            error = result.message,
                        )
                    }
                }
            }
        }
    }

    fun startOfflinePreview() {
        if (_state.value.restoringSession) return

        _state.update {
            it.copy(
                restoringSession = false,
                offlinePreview = true,
                user = UserData(
                    id = "00000000-0000-4000-8000-000000000901",
                    displayName = "합성 기사 001",
                    roleCode = "TECHNICIAN",
                    isActive = true,
                ),
                error = null,
            )
        }
        loadVisits()
    }

    fun loadVisits() {
        if (_state.value.user?.roleCode != "TECHNICIAN") return

        viewModelScope.launch {
            _state.update {
                it.copy(
                    visitsLoading = true,
                    error = null,
                )
            }

            when (val result = visitRepository.getAssignedVisits()) {
                is ApiResult.Success -> {
                    _state.update {
                        it.copy(
                            visitsLoading = false,
                            visits = result.value,
                        )
                    }
                }

                is ApiResult.Failure -> {
                    _state.update {
                        it.copy(
                            visitsLoading = false,
                            error = result.message,
                        )
                    }
                }
            }
        }
    }

    fun openVisit(visitId: String) {
        if (_state.value.reportLoading) return

        viewModelScope.launch {
            _state.update {
                it.copy(
                    selectedVisitId = visitId,
                    selectedReport = null,
                    reportLoading = true,
                    reportError = null,
                )
            }

            when (val result = visitRepository.getPrecheckReport(visitId)) {
                is ApiResult.Success -> {
                    _state.update {
                        it.copy(
                            reportLoading = false,
                            selectedReport = result.value,
                        )
                    }
                }

                is ApiResult.Failure -> {
                    _state.update {
                        it.copy(
                            reportLoading = false,
                            reportError = result.message,
                        )
                    }
                }
            }
        }
    }

    fun closeVisit() {
        _state.update {
            it.copy(
                selectedVisitId = null,
                selectedReport = null,
                reportLoading = false,
                reportError = null,
            )
        }
    }

    fun logout() {
        viewModelScope.launch {
            if (!_state.value.offlinePreview) {
                authRepository.logout()
            }

            _state.value = TechnicianUiState(
                checkingBackend = false,
                backendAvailable = _state.value.backendAvailable,
            )
        }
    }
}

class TechnicianViewModelFactory(
    private val authRepository: AuthRepository,
    private val backendStatusRepository: BackendStatusRepository,
    private val visitRepository: TechnicianVisitRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass.isAssignableFrom(TechnicianViewModel::class.java)) {
            "Unsupported ViewModel: ${modelClass.name}"
        }

        return TechnicianViewModel(
            authRepository = authRepository,
            backendStatusRepository = backendStatusRepository,
            visitRepository = visitRepository,
        ) as T
    }
}

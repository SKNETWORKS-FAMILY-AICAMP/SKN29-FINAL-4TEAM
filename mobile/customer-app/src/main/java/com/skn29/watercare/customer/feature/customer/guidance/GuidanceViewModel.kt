package com.skn29.watercare.customer.feature.customer.guidance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.GuidanceMapper
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.repository.CustomerCareRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class GuidanceViewModel(
    private val inquiryId: String,
    private val scenario: MockScenario,
    private val repository: CustomerCareRepository,
) : ViewModel() {
    private val _state = MutableStateFlow<GuidanceUiState>(GuidanceUiState.Loading)
    val state: StateFlow<GuidanceUiState> = _state.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = GuidanceUiState.Loading
            _state.value = when (val result = repository.getGuidance(inquiryId, scenario)) {
                is ApiResult.Success -> {
                    val mapped = GuidanceMapper.map(result.value)
                    if (mapped.evidence.isEmpty()) GuidanceUiState.NoEvidence(mapped)
                    else GuidanceUiState.Content(mapped)
                }
                is ApiResult.Failure -> when {
                    result.code.startsWith("AI_") -> GuidanceUiState.AiFailure(result.message, result.retryable)
                    result.code == "NETWORK_ERROR" -> GuidanceUiState.NetworkFailure(result.message, result.retryable)
                    else -> GuidanceUiState.Error(result.message, result.retryable)
                }
            }
        }
    }
}

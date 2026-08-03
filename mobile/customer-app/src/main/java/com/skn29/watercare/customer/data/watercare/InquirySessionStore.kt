package com.skn29.watercare.customer.data.watercare

import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.InquiryDisplayState
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.InquiryRuntimeSnapshot
import com.skn29.watercare.core.model.InquiryStatusMapper
import com.skn29.watercare.core.model.ServerInquiryStatus
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.toRuntimeAction
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

interface InquirySessionStore {
    val current: StateFlow<InquiryRuntimeSnapshot?>

    fun find(inquiryId: String): InquiryRuntimeSnapshot?
    fun saveCreated(response: InquiryResponse, correlationId: String?)
    fun applyConflict(conflict: StateConflictSnapshot, correlationId: String?)
    fun saveCancelled(response: CancelInquiryResponse, correlationId: String?)
    fun clear()
}

class InMemoryInquirySessionStore : InquirySessionStore {
    private val _current = MutableStateFlow<InquiryRuntimeSnapshot?>(null)
    override val current: StateFlow<InquiryRuntimeSnapshot?> = _current.asStateFlow()

    override fun find(inquiryId: String): InquiryRuntimeSnapshot? =
        _current.value?.takeIf { it.inquiryId == inquiryId }

    override fun saveCreated(response: InquiryResponse, correlationId: String?) {
        val status = ServerInquiryStatus.parse(response.statusCode)
        _current.value = InquiryRuntimeSnapshot(
            inquiryId = response.inquiryId,
            inquiryCode = response.inquiryCode,
            serverStatus = status,
            displayState = InquiryStatusMapper.displayState(status),
            stateVersion = response.stateVersion,
            allowedActions = response.allowedActions.map { it.toRuntimeAction() },
            correlationId = correlationId,
            idempotentReplay = response.idempotentReplay,
        )
    }

    override fun applyConflict(conflict: StateConflictSnapshot, correlationId: String?) {
        val existing = _current.value ?: return
        val status = conflict.currentStatus
            ?.let(ServerInquiryStatus::parse)
            ?: existing.serverStatus
        _current.value = existing.copy(
            serverStatus = status,
            displayState = InquiryStatusMapper.displayState(status),
            stateVersion = conflict.currentStateVersion ?: existing.stateVersion,
            allowedActions = conflict.allowedActions,
            correlationId = correlationId ?: existing.correlationId,
        )
    }

    override fun saveCancelled(response: CancelInquiryResponse, correlationId: String?) {
        val existing = _current.value
        val status = ServerInquiryStatus.parse(response.state)
        _current.value = InquiryRuntimeSnapshot(
            inquiryId = response.inquiryId,
            inquiryCode = existing?.inquiryCode.orEmpty(),
            serverStatus = status,
            displayState = InquiryDisplayState.CANCELLED,
            stateVersion = response.stateVersion,
            allowedActions = emptyList(),
            correlationId = correlationId ?: existing?.correlationId,
            idempotentReplay = response.idempotentReplay,
        )
    }

    override fun clear() {
        _current.value = null
    }
}

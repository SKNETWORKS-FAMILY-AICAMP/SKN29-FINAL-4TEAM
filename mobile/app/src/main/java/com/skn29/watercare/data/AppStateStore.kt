package com.skn29.watercare.data

import com.skn29.watercare.model.ErrorDetectionResult
import com.skn29.watercare.model.InquiryDraft
import com.skn29.watercare.model.InquiryEntryMode
import com.skn29.watercare.model.InquiryState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

object AppStateStore {
    private val _inquiry = MutableStateFlow(InquiryDraft())
    val inquiry: StateFlow<InquiryDraft> = _inquiry.asStateFlow()

    fun resetInquiry() {
        _inquiry.value = InquiryDraft()
    }

    /**
     * QR 예시:
     * product_code=WPUJAC104DWH;error_code=E01
     * 오류 코드가 있으면 true, 없으면 false를 반환한다.
     */
    fun applyQrResult(rawValue: String): Boolean {
        val productCode = readValue(rawValue, "product_code", "product", "model")
            ?: PRODUCT_CODE_REGEX.find(rawValue)?.value
            ?: "WPUJAC104DWH"
        val errorCode = readValue(rawValue, "error_code", "error", "code")
            ?.uppercase()
            ?: ERROR_CODE_REGEX.find(rawValue.uppercase())?.value

        if (errorCode == null) {
            _inquiry.value = InquiryDraft(
                state = InquiryState.QUESTIONNAIRE_IN_PROGRESS,
                detection = ErrorDetectionResult(
                    entryMode = InquiryEntryMode.QR_SCAN,
                    productCode = productCode,
                    errorName = "QR에 오류 코드 없음",
                    symptomSummary = "제품은 확인되었지만 오류 코드가 없어 문진이 필요합니다.",
                    sourceRawValue = rawValue
                )
            )
            return false
        }

        val (errorName, summary) = errorCatalog(errorCode)
        _inquiry.value = InquiryDraft(
            state = InquiryState.AI_GUIDANCE,
            detection = ErrorDetectionResult(
                entryMode = InquiryEntryMode.QR_SCAN,
                productCode = productCode,
                errorCode = errorCode,
                errorName = errorName,
                symptomSummary = summary,
                requiresVisit = true,
                sourceRawValue = rawValue
            )
        )
        return true
    }

    fun applyQuestionnaire(
        symptom: String,
        description: String,
        hasLeak: Boolean,
        hasErrorDisplay: Boolean
    ) {
        val summary = buildString {
            append(symptom)
            if (description.isNotBlank()) append(" · ").append(description.trim())
            if (hasLeak) append(" · 누수 확인")
            if (hasErrorDisplay) append(" · 표시창 오류 확인")
        }

        val errorName = when {
            hasLeak -> "누수 이상"
            hasErrorDisplay -> "표시창 오류"
            symptom == "출수량 저하" -> "급수·출수 이상"
            symptom == "냉·온수 온도 이상" -> "온도 제어 이상"
            symptom == "물맛·냄새 이상" -> "수질 체감 이상"
            else -> "방문 확인이 필요한 증상"
        }

        _inquiry.value = InquiryDraft(
            state = InquiryState.AI_GUIDANCE,
            detection = ErrorDetectionResult(
                entryMode = InquiryEntryMode.QUESTIONNAIRE,
                productCode = "WPUJAC104DWH",
                errorName = errorName,
                symptomSummary = summary,
                requiresVisit = true
            )
        )
    }

    fun requestVisit() {
        _inquiry.value = _inquiry.value.copy(state = InquiryState.VISIT_SCHEDULED)
    }

    private fun readValue(rawValue: String, vararg keys: String): String? {
        val pairs = rawValue
            .split(';', '&', '\n', ',')
            .mapNotNull { token ->
                val separatorIndex = token.indexOfAny(charArrayOf('=', ':'))
                if (separatorIndex <= 0) return@mapNotNull null
                token.substring(0, separatorIndex).trim().lowercase() to
                    token.substring(separatorIndex + 1).trim()
            }
            .toMap()

        return keys.firstNotNullOfOrNull { key -> pairs[key.lowercase()] }
            ?.takeIf { it.isNotBlank() }
    }

    private fun errorCatalog(code: String): Pair<String, String> = when (code) {
        "E01" -> "급수 이상" to "정수기 급수 또는 출수 계통 확인이 필요합니다."
        "E02" -> "배수 이상" to "배수 계통과 누수 여부 확인이 필요합니다."
        "E03" -> "온도 센서 이상" to "냉·온수 온도 센서 점검이 필요합니다."
        else -> "등록 오류 코드 $code" to "오류 코드가 확인되어 방문기사 점검이 필요합니다."
    }

    private val PRODUCT_CODE_REGEX = Regex("WPU[A-Z0-9-]{5,}", RegexOption.IGNORE_CASE)
    private val ERROR_CODE_REGEX = Regex("\\b[A-Z][0-9]{2,3}\\b")
}

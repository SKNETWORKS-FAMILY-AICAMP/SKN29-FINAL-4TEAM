package com.skn29.watercare.customer.feature.customer.intake.data

import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic

object SymptomIntakeMapper {
    fun toCreateInquiryRequest(
        subscriptionId: String,
        selected: Set<SymptomTopic>,
        rawText: String,
        occurrenceCondition: String,
        displayText: String,
        entryMode: EntryMode,
    ): CreateInquiryRequest {
        val sortedTopics = selected.sortedBy { it.ordinal }
        val sections = buildList {
            if (sortedTopics.isNotEmpty()) {
                add("대표 증상: ${sortedTopics.joinToString { it.label }}")
            }
            rawText.trim().takeIf(String::isNotBlank)?.let(::add)
            occurrenceCondition.trim().takeIf(String::isNotBlank)
                ?.let { add("발생 조건: $it") }
            displayText.trim().takeIf(String::isNotBlank)
                ?.let { add("제품 표시 문구·오류 코드: $it") }
            if (entryMode == EntryMode.CARE_PRECHECK) {
                add("접수 유형: 케어 사전 문진")
            }
        }
        return CreateInquiryRequest(
            subscriptionId = subscriptionId,
            channelCode = "MOBILE",
            rawText = sections.joinToString("\n").take(5000),
            representativeSymptomCode = sortedTopics.firstOrNull()?.code,
            questionnaireSessionId = null,
        )
    }

    fun previewScenario(forcedScenario: MockScenario?): String =
        (forcedScenario ?: MockScenario.NO_EVIDENCE).name
}

package com.skn29.watercare.technician

import com.skn29.watercare.core.model.ApiResult
import kotlinx.coroutines.delay

interface TechnicianVisitRepository {
    suspend fun getAssignedVisits(): ApiResult<List<TechnicianVisitSummary>>

    suspend fun getPrecheckReport(
        visitId: String,
    ): ApiResult<TechnicianPrecheckReport>
}

/**
 * Backend 방문 API가 제공되기 전까지 사용하는 명시적 합성 Fixture입니다.
 * 실제 고객 개인정보나 실제 방문 완료 기능을 포함하지 않습니다.
 */
class FakeTechnicianVisitRepository(
    private val delayMillis: Long = 120L,
) : TechnicianVisitRepository {
    private val visits = listOf(
        TechnicianVisitSummary(
            visitId = "00000000-0000-4000-8000-000000001001",
            visitCode = "SYN-VISIT-001",
            customerMaskedName = "김○○",
            maskedAddress = "서울시 강남구 테헤란로 ***",
            productModel = "WPU-JAC104D",
            scheduledAt = "2026-08-07 10:30",
            scheduleStatusCode = "CONFIRMED",
            symptomSummary = "출수량 저하가 반복되고 있습니다.",
            risk = TechnicianVisitRisk.GENERAL,
            usageRestrictionLabel = "현재 즉시 사용 중지 징후 없음",
            scenarioId = "SYN-TECH-LOW-FLOW-001",
        ),
        TechnicianVisitSummary(
            visitId = "00000000-0000-4000-8000-000000001002",
            visitCode = "SYN-VISIT-002",
            customerMaskedName = "이○○",
            maskedAddress = "인천시 계양구 장제로 ***",
            productModel = "WPU-JAC104D",
            scheduledAt = "2026-08-07 13:20",
            scheduleStatusCode = "COORDINATING",
            symptomSummary = "온수 온도가 일정하지 않습니다.",
            risk = TechnicianVisitRisk.CAUTION,
            usageRestrictionLabel = "온수 기능 사용 제한",
            scenarioId = "SYN-TECH-TEMPERATURE-001",
        ),
        TechnicianVisitSummary(
            visitId = "00000000-0000-4000-8000-000000001003",
            visitCode = "SYN-VISIT-003",
            customerMaskedName = "박○○",
            maskedAddress = "서울시 마포구 양화로 ***",
            productModel = "WPU-JAC104D",
            scheduledAt = "2026-08-07 15:40",
            scheduleStatusCode = "ASSIGNING",
            symptomSummary = "제품 하단에서 물이 확인되었습니다.",
            risk = TechnicianVisitRisk.DANGER,
            usageRestrictionLabel = "제품 전체 사용 중지",
            scenarioId = "SYN-TECH-LEAK-001",
        ),
    )

    private val reports = listOf(
        TechnicianPrecheckReport(
            visitId = visits[0].visitId,
            visitCode = visits[0].visitCode,
            customerMaskedName = visits[0].customerMaskedName,
            customerMaskedPhone = "010-****-2184",
            maskedAddress = visits[0].maskedAddress,
            productModel = visits[0].productModel,
            scheduledAt = visits[0].scheduledAt,
            symptomSummary = visits[0].symptomSummary,
            consultationSummary =
                "필터 교체 이후에도 출수량 저하가 반복된다고 고객이 전달했습니다.",
            inspectionCandidates = listOf(
                "출수구 외부 이물 여부 확인",
                "필터 장착 상태 확인",
                "급수 압력과 연결부 육안 점검",
            ),
            safetyNotice = "현재 위험 징후는 없지만 제품 분해 전 전원과 급수 상태를 확인합니다.",
            prohibitedActions = listOf(
                "고객에게 내부 부품 분해를 요청하지 않습니다.",
                "확인되지 않은 부품 교체를 확정 안내하지 않습니다.",
            ),
            evidence = listOf(
                TechnicianEvidence(
                    documentName = "WPU-JAC104D 사용설명서",
                    revision = "REV.00",
                    page = 38,
                    summary =
                        "출수량 저하 시 외부 상태를 확인하고 지속될 경우 점검을 요청하도록 안내합니다.",
                    verificationStatus = "VERIFIED",
                )
            ),
            scenarioId = visits[0].scenarioId,
        ),
        TechnicianPrecheckReport(
            visitId = visits[1].visitId,
            visitCode = visits[1].visitCode,
            customerMaskedName = visits[1].customerMaskedName,
            customerMaskedPhone = "010-****-7041",
            maskedAddress = visits[1].maskedAddress,
            productModel = visits[1].productModel,
            scheduledAt = visits[1].scheduledAt,
            symptomSummary = visits[1].symptomSummary,
            consultationSummary =
                "온수 사용 중 체감 온도가 일정하지 않아 사용을 중단한 상태입니다.",
            inspectionCandidates = listOf(
                "온수 기능 제한 상태 확인",
                "표시부 오류 문구 확인",
                "온도 센서 관련 점검 항목 확인",
            ),
            safetyNotice = "화상 위험을 피하기 위해 점검 전까지 온수 사용을 제한합니다.",
            prohibitedActions = listOf(
                "고객에게 온수를 손으로 반복 확인하도록 요청하지 않습니다.",
                "현장 확인 전 정상 사용 가능하다고 단정하지 않습니다.",
            ),
            evidence = listOf(
                TechnicianEvidence(
                    documentName = "WPU-JAC104D 안전 주의사항",
                    revision = "REV.00",
                    page = 12,
                    summary =
                        "온수 이상이 의심되면 화상에 주의하고 점검을 요청하도록 안내합니다.",
                    verificationStatus = "VERIFIED",
                )
            ),
            scenarioId = visits[1].scenarioId,
        ),
        TechnicianPrecheckReport(
            visitId = visits[2].visitId,
            visitCode = visits[2].visitCode,
            customerMaskedName = visits[2].customerMaskedName,
            customerMaskedPhone = "010-****-9932",
            maskedAddress = visits[2].maskedAddress,
            productModel = visits[2].productModel,
            scheduledAt = visits[2].scheduledAt,
            symptomSummary = visits[2].symptomSummary,
            consultationSummary =
                "제품 하단에서 물이 보여 고객이 제품 사용을 즉시 중지했습니다.",
            inspectionCandidates = listOf(
                "주변 누수 범위와 전기 위험 여부 확인",
                "급수 차단 상태 확인",
                "제품 접근 전 안전 공간 확보",
            ),
            safetyNotice =
                "누수·전기 위험이 있으므로 젖은 손으로 전원부에 접근하지 않고 사용 중지를 유지합니다.",
            prohibitedActions = listOf(
                "고객에게 누수 부위를 직접 조이도록 요청하지 않습니다.",
                "전기 냄새나 스파크가 있으면 제품에 접근하지 않습니다.",
            ),
            evidence = listOf(
                TechnicianEvidence(
                    documentName = "WPU-JAC104D 안전 주의사항",
                    revision = "REV.00",
                    page = 5,
                    summary =
                        "누수 또는 전기 위험 징후가 있으면 사용을 중지하고 임의 분해하지 않도록 안내합니다.",
                    verificationStatus = "VERIFIED",
                )
            ),
            scenarioId = visits[2].scenarioId,
        ),
    )

    override suspend fun getAssignedVisits(): ApiResult<List<TechnicianVisitSummary>> {
        delay(delayMillis)
        return ApiResult.Success(visits)
    }

    override suspend fun getPrecheckReport(
        visitId: String,
    ): ApiResult<TechnicianPrecheckReport> {
        delay(delayMillis)
        val report = reports.firstOrNull { it.visitId == visitId }
            ?: return ApiResult.Failure(
                code = "VISIT_NOT_FOUND",
                message = "배정된 방문 정보를 찾을 수 없습니다.",
                httpStatus = 404,
            )
        return ApiResult.Success(report)
    }
}

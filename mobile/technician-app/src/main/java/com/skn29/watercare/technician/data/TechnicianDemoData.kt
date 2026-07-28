package com.skn29.watercare.technician.data

enum class TechnicianVisitStatus(
    val label: String
) {
    CONFIRMED("방문 확정"),
    URGENT("긴급"),
    EN_ROUTE("이동 중"),
    IN_PROGRESS("점검 중"),
    COMPLETED("완료")
}

data class TechnicianVisit(
    val visitId: String,
    val customerName: String,
    val phone: String,
    val address: String,
    val schedule: String,
    val productName: String,
    val productCode: String,
    val symptom: String,
    val customerAction: String,
    val consultationSummary: String,
    val priorityChecks: List<String>,
    val officialEvidence: String,
    val status: TechnicianVisitStatus,
    val distanceKm: Double
)

object TechnicianDemoData {
    val visits: List<TechnicianVisit> = listOf(
        TechnicianVisit(
            visitId = "DEMO-VISIT-002",
            customerName = "김민수",
            phone = "010-1234-5678",
            address = "서울특별시 강남구 테헤란로 123",
            schedule = "오늘 14:00",
            productName = "SK매직 올인원 플러스",
            productCode = "WPUJAC104DWH",
            symptom = "출수량이 평소보다 줄어들고 물줄기가 불규칙함",
            customerAction = "전원 재연결과 급수 밸브 확인을 완료했으나 증상이 지속됨",
            consultationSummary = "필터 사용 기간이 길고 최근 수압 저하가 반복됨. 누수와 전기 위험 징후는 없음.",
            priorityChecks = listOf(
                "필터 사용 기간과 체결 상태 확인",
                "급수 밸브 및 원수 유입 상태 확인",
                "출수 노즐과 내부 유로 막힘 여부 확인"
            ),
            officialEvidence = "사용설명서 REV.00 · 출수 이상 점검 항목 · 38페이지",
            status = TechnicianVisitStatus.CONFIRMED,
            distanceKm = 2.4
        ),
        TechnicianVisit(
            visitId = "DEMO-VISIT-005",
            customerName = "이서연",
            phone = "010-9876-5432",
            address = "서울특별시 송파구 올림픽로 88",
            schedule = "오늘 16:30",
            productName = "SK매직 스스로 직수",
            productCode = "WPUA100C",
            symptom = "제품 하단에서 소량의 물이 확인됨",
            customerAction = "급수 밸브를 잠그고 제품 사용을 중단함",
            consultationSummary = "누수 가능성이 있어 자가조치를 중단하고 방문 점검으로 즉시 전환함.",
            priorityChecks = listOf(
                "급수 연결부와 호스 체결 상태 확인",
                "누수 흔적과 내부 트레이 상태 확인",
                "전장부 수분 유입 여부 확인"
            ),
            officialEvidence = "안전 점검 지침 · 누수 발생 시 조치 · 12페이지",
            status = TechnicianVisitStatus.URGENT,
            distanceKm = 5.8
        ),
        TechnicianVisit(
            visitId = "DEMO-VISIT-007",
            customerName = "박지훈",
            phone = "010-5555-1212",
            address = "서울특별시 광진구 아차산로 210",
            schedule = "내일 10:00",
            productName = "SK매직 초소형 직수",
            productCode = "WPUJAC115",
            symptom = "냉수 온도가 충분히 낮아지지 않음",
            customerAction = "냉수 기능과 주변 환기 공간을 확인함",
            consultationSummary = "냉각 기능 저하 가능성. 설치 환경과 냉각부 상태를 우선 확인할 필요가 있음.",
            priorityChecks = listOf(
                "제품 후면 환기 공간 확인",
                "냉각 모듈 작동 소음과 온도 확인",
                "설정 온도와 절전 모드 확인"
            ),
            officialEvidence = "제품 사용설명서 · 냉수 이상 점검 · 44페이지",
            status = TechnicianVisitStatus.CONFIRMED,
            distanceKm = 8.1
        )
    )

    fun findVisit(visitId: String): TechnicianVisit? =
        visits.firstOrNull { it.visitId == visitId }
}

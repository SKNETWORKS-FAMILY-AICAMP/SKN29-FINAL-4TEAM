package com.skn29.watercare.technician.app.navigation

object TechnicianRoute {
    const val WORK_LIST = "work-list"
    const val VISIT_DETAIL = "visit-detail/{visitId}"
    const val VISIT_RESULT = "visit-result/{visitId}"

    fun visitDetail(visitId: String): String = "visit-detail/$visitId"
    fun visitResult(visitId: String): String = "visit-result/$visitId"
}

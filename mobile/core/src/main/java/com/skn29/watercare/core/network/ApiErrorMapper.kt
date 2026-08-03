package com.skn29.watercare.core.network

object ApiErrorMapper {
    fun userMessage(
        status: Int,
        serverCode: String? = null,
        serverMessage: String? = null,
    ): String = when {
        status == 400 -> serverMessage ?: "요청 내용을 확인해 주세요."
        status == 401 || serverCode == "AUTH_REQUIRED" ->
            "로그인이 만료되었습니다. 다시 로그인해 주세요."
        status == 403 || serverCode == "FORBIDDEN" ->
            "현재 계정 역할로는 이 기능을 사용할 수 없습니다."
        status == 404 || serverCode == "RESOURCE_NOT_FOUND" ->
            "요청한 정보를 찾을 수 없습니다. 구독 또는 문의 정보를 확인해 주세요."
        status == 409 || serverCode == "STATE-CONFLICT-01" ->
            "다른 작업으로 상태가 변경되었습니다. 최신 상태를 확인한 뒤 다시 시도해 주세요."
        status == 422 || serverCode == "VALIDATION_ERROR" ->
            serverMessage ?: "입력값을 확인해 주세요."
        status == 503 && serverCode == "AI-FAILED-01" ->
            "AI 안내를 생성하지 못했습니다. 입력을 유지한 채 다시 시도하거나 상담을 이용해 주세요."
        status == 503 && serverCode == "SEARCH-FAILED-01" ->
            "공식 근거를 확인하지 못했습니다. 임의 안내 없이 상담 확인이 필요합니다."
        status == 504 || serverCode == "AI-TIMEOUT-01" ->
            "안내 생성 시간이 초과되었습니다. 입력을 유지한 채 다시 시도해 주세요."
        status in 500..599 ->
            "서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        else -> serverMessage ?: "요청을 처리하지 못했습니다."
    }
}

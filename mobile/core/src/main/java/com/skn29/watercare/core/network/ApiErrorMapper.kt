package com.skn29.watercare.core.network

object ApiErrorMapper {
    fun userMessage(status: Int, serverMessage: String? = null): String = when (status) {
        400, 422 -> serverMessage ?: "입력 내용을 확인해 주세요."
        401 -> "로그인이 만료되었습니다. 다시 로그인해 주세요."
        403 -> "현재 계정 역할로는 이 기능을 사용할 수 없습니다."
        404 -> "요청한 정보를 찾을 수 없습니다."
        409 -> "다른 작업으로 상태가 변경되었습니다. 최신 상태를 확인한 뒤 다시 시도해 주세요."
        in 500..599 -> "서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        else -> serverMessage ?: "요청을 처리하지 못했습니다."
    }
}

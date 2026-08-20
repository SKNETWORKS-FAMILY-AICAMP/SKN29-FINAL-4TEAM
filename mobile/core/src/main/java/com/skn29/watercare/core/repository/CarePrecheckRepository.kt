package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CarePrecheckSessionDto
import com.skn29.watercare.core.model.SaveCarePrecheckRequestDto
import com.skn29.watercare.core.model.StartCarePrecheckRequestDto
import com.skn29.watercare.core.model.SubmitCarePrecheckRequestDto
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import java.util.UUID
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject


/**
 * T-021 CARE_PRECHECK Backend 접근 규칙입니다.
 *
 * 화면에서는 Retrofit API를 직접 부르지 않고
 * 항상 Repository를 통해 접근합니다.
 */
interface CarePrecheckRepository {

    /** 새로운 CARE_PRECHECK 세션 시작 */
    suspend fun start(
        subscriptionId: String,
        idempotencyKeyOverride: String? = null,
    ): ApiResult<CarePrecheckSessionDto>

    /** 이미 만들어진 세션을 다시 조회 */
    suspend fun get(
        questionnaireSessionId: String,
    ): ApiResult<CarePrecheckSessionDto>

    /** 작성 중인 답변 임시 저장 */
    suspend fun save(
        questionnaireSessionId: String,
        stateVersion: Int,
        answers: JsonObject,
        idempotencyKeyOverride: String? = null,
    ): ApiResult<CarePrecheckSessionDto>

    /** 작성이 끝난 답변 최종 제출 */
    suspend fun submit(
        questionnaireSessionId: String,
        stateVersion: Int,
        answers: JsonObject,
        idempotencyKeyOverride: String? = null,
    ): ApiResult<CarePrecheckSessionDto>
}


/**
 * 실제 Backend를 사용하는 CARE_PRECHECK Repository입니다.
 */
class RemoteCarePrecheckRepository(
    private val api: WaterCareApi,
    private val json: Json,
) : CarePrecheckRepository {

    override suspend fun start(
        subscriptionId: String,
        idempotencyKeyOverride: String?,
    ): ApiResult<CarePrecheckSessionDto> {

        // Start는 같은 요청을 안전하게 다시 보낼 수 있도록
        // Idempotency-Key를 함께 전달합니다.
        val key =
            idempotencyKeyOverride
                ?: UUID.randomUUID().toString()

        return safeApiCall(json) {
            api.startCarePrecheck(
                idempotencyKey = key,
                body =
                    StartCarePrecheckRequestDto(
                        subscriptionId =
                            subscriptionId,
                    ),
            )
        }
    }

    override suspend fun get(
        questionnaireSessionId: String,
    ): ApiResult<CarePrecheckSessionDto> =
        safeApiCall(json) {
            api.carePrecheckDetail(
                questionnaireSessionId =
                    questionnaireSessionId,
            )
        }

    override suspend fun save(
        questionnaireSessionId: String,
        stateVersion: Int,
        answers: JsonObject,
        idempotencyKeyOverride: String?,
    ): ApiResult<CarePrecheckSessionDto> {

        val key =
            idempotencyKeyOverride
                ?: UUID.randomUUID().toString()

        return safeApiCall(json) {
            api.saveCarePrecheck(
                questionnaireSessionId =
                    questionnaireSessionId,
                idempotencyKey = key,
                body =
                    SaveCarePrecheckRequestDto(
                        stateVersion =
                            stateVersion,
                        answers = answers,
                    ),
            )
        }
    }

    override suspend fun submit(
        questionnaireSessionId: String,
        stateVersion: Int,
        answers: JsonObject,
        idempotencyKeyOverride: String?,
    ): ApiResult<CarePrecheckSessionDto> {

        val key =
            idempotencyKeyOverride
                ?: UUID.randomUUID().toString()

        return safeApiCall(json) {
            api.submitCarePrecheck(
                questionnaireSessionId =
                    questionnaireSessionId,
                idempotencyKey = key,
                body =
                    SubmitCarePrecheckRequestDto(
                        stateVersion =
                            stateVersion,
                        answers = answers,
                    ),
            )
        }
    }
}

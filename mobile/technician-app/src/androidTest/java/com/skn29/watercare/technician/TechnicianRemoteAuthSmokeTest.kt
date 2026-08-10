package com.skn29.watercare.technician

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.UserData
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TechnicianRemoteAuthSmokeTest {
    @Test
    fun technicianLoginAndMe_useRealBackend() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteSmoke") == "true")

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )

        val login = WaterCareCore.authRepository.demoLogin("DEMO-TECHNICIAN-001")
        assertTrue(login is ApiResult.Success<*>)
        val session = (login as ApiResult.Success<SessionResponse>).value
        assertEquals("TECHNICIAN", session.user.roleCode)

        val me = WaterCareCore.authRepository.me()
        assertTrue(me is ApiResult.Success<*>)
        assertEquals(
            "TECHNICIAN",
            (me as ApiResult.Success<UserData>).value.roleCode,
        )
    }
}

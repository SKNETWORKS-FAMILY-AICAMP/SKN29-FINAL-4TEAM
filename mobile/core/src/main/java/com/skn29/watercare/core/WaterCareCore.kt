package com.skn29.watercare.core

import android.content.Context
import com.skn29.watercare.core.network.NetworkFactory
import kotlinx.serialization.json.Json
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.repository.RemoteAuthRepository
import com.skn29.watercare.core.repository.RemoteBackendStatusRepository

object WaterCareCore {
    lateinit var authRepository: AuthRepository
        private set
    lateinit var backendStatusRepository: BackendStatusRepository
        private set
    lateinit var customerCareRepository: CustomerCareRepository
        private set
    private lateinit var networkFactory: NetworkFactory

    val json: Json
        get() = networkFactory.json

    fun <T> createAuthenticatedService(serviceClass: Class<T>): T =
        networkFactory.createService(serviceClass)

    fun initialize(context: Context, baseUrl: String, debug: Boolean) {
        if (::authRepository.isInitialized) return
        networkFactory = NetworkFactory(context.applicationContext, baseUrl, debug)
        authRepository = RemoteAuthRepository(
            api = networkFactory.api,
            tokenStore = networkFactory.tokenStore,
            json = networkFactory.json,
        )
        backendStatusRepository = RemoteBackendStatusRepository(networkFactory.api)

        // Home and Guidance endpoints are not routed yet. Keep those screens explicitly Mock/Blocked.
        customerCareRepository = FakeCustomerCareRepository()
    }
}

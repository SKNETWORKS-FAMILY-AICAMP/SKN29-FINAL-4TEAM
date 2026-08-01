package com.skn29.watercare.core

import android.content.Context
import com.skn29.watercare.core.network.NetworkFactory
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.repository.InquiryRepository
import com.skn29.watercare.core.repository.RemoteAuthRepository
import com.skn29.watercare.core.repository.RemoteBackendStatusRepository
import com.skn29.watercare.core.repository.RemoteInquiryRepository

object WaterCareCore {
    lateinit var authRepository: AuthRepository
        private set
    lateinit var inquiryRepository: InquiryRepository
        private set
    lateinit var backendStatusRepository: BackendStatusRepository
        private set
    lateinit var customerCareRepository: CustomerCareRepository
        private set

    fun initialize(context: Context, baseUrl: String, debug: Boolean) {
        if (::authRepository.isInitialized) return
        val network = NetworkFactory(context.applicationContext, baseUrl, debug)
        authRepository = RemoteAuthRepository(network.api, network.tokenStore, network.json)
        inquiryRepository = RemoteInquiryRepository(network.api, network.json)
        backendStatusRepository = RemoteBackendStatusRepository(network.api)
        customerCareRepository = FakeCustomerCareRepository()
    }
}

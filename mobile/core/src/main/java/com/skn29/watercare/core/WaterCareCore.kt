package com.skn29.watercare.core

import android.content.Context
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.config.CustomerCareRuntimeConfig
import com.skn29.watercare.core.network.NetworkFactory
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.repository.InquiryRepository
import com.skn29.watercare.core.repository.RemoteAuthRepository
import com.skn29.watercare.core.repository.RemoteBackendStatusRepository
import com.skn29.watercare.core.repository.RemoteCustomerInquiryRepository
import com.skn29.watercare.core.repository.RemoteInquiryRepository
import com.skn29.watercare.core.repository.RemoteIntakeCustomerCareRepository
import com.skn29.watercare.core.repository.RemoteSubscriptionRepository
import com.skn29.watercare.core.repository.SubscriptionRepository

object WaterCareCore {
    lateinit var authRepository: AuthRepository
        private set
    lateinit var inquiryRepository: InquiryRepository
        private set
    lateinit var customerInquiryRepository: CustomerInquiryRepository
        private set
    lateinit var subscriptionRepository: SubscriptionRepository
        private set
    lateinit var backendStatusRepository: BackendStatusRepository
        private set
    lateinit var customerCareRepository: CustomerCareRepository
        private set
    lateinit var customerCareRuntimeConfig: CustomerCareRuntimeConfig
        private set

    fun initialize(
        context: Context,
        baseUrl: String,
        debug: Boolean,
        customerCareMode: String = CustomerCareMode.REMOTE.name,
        demoSubscriptionId: String = "",
    ) {
        if (::authRepository.isInitialized) return

        customerCareRuntimeConfig = CustomerCareRuntimeConfig.from(
            rawMode = customerCareMode,
            rawDemoSubscriptionId = demoSubscriptionId,
        )

        val network = NetworkFactory(context.applicationContext, baseUrl, debug)
        authRepository = RemoteAuthRepository(network.api, network.tokenStore, network.json)
        inquiryRepository = RemoteInquiryRepository(network.api, network.json)
        customerInquiryRepository = RemoteCustomerInquiryRepository(
            network.api,
            network.json,
        )
        subscriptionRepository = RemoteSubscriptionRepository(network.api, network.json)
        backendStatusRepository = RemoteBackendStatusRepository(network.api)

        val fixtureRepository = FakeCustomerCareRepository(
            fixtureSubscriptionId = customerCareRuntimeConfig.fixtureSubscriptionId,
        )
        customerCareRepository = when (customerCareRuntimeConfig.mode) {
            CustomerCareMode.REMOTE -> RemoteIntakeCustomerCareRepository(
                inquiryRepository = inquiryRepository,
                subscriptionRepository = subscriptionRepository,
                customerInquiryRepository = customerInquiryRepository,
            )
            CustomerCareMode.FAKE -> fixtureRepository
        }
    }
}

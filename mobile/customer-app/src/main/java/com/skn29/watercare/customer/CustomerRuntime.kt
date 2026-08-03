package com.skn29.watercare.customer

import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.customer.data.watercare.CustomerInquiryApi
import com.skn29.watercare.customer.data.watercare.InMemoryInquirySessionStore
import com.skn29.watercare.customer.data.watercare.InquirySessionStore
import com.skn29.watercare.customer.repository.InquiryRepository
import com.skn29.watercare.customer.repository.RemoteInquiryRepository

/** Customer-app-only runtime boundary for inquiry business APIs. */
object CustomerRuntime {
    lateinit var inquiryRepository: InquiryRepository
        private set
    lateinit var inquirySessionStore: InquirySessionStore
        private set

    fun initialize() {
        if (::inquiryRepository.isInitialized) return
        inquirySessionStore = InMemoryInquirySessionStore()
        val api = WaterCareCore.createAuthenticatedService(CustomerInquiryApi::class.java)
        inquiryRepository = RemoteInquiryRepository(
            api = api,
            json = WaterCareCore.json,
            sessionStore = inquirySessionStore,
        )
    }

    fun clear() {
        if (::inquirySessionStore.isInitialized) inquirySessionStore.clear()
    }
}

package com.skn29.watercare.customer

import android.app.Application
import com.skn29.watercare.core.WaterCareCore

class CustomerApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        WaterCareCore.initialize(
            context = this,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = BuildConfig.DEBUG,
            customerCareMode = BuildConfig.CUSTOMER_CARE_MODE,
            demoSubscriptionId = BuildConfig.DEMO_SUBSCRIPTION_ID,
        )
    }
}

package com.skn29.watercare.customer

import androidx.compose.runtime.Composable
import com.skn29.watercare.customer.navigation.CustomerNavigation

@Composable
fun CustomerApp() {
    CustomerNavigation(runtimeSubscriptionId = BuildConfig.DEMO_SUBSCRIPTION_ID)
}

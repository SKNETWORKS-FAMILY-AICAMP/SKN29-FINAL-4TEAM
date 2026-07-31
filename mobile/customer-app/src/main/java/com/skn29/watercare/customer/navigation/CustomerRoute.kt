package com.skn29.watercare.customer.navigation

object CustomerRoute {
    const val LOGIN = "login"
    const val HOME = "home?offline={offline}"
    const val INTAKE = "intake/{subscriptionId}"
    const val GUIDANCE = "guidance/{inquiryId}/{scenario}"

    fun home(offline: Boolean) = "home?offline=$offline"
    fun intake(subscriptionId: String) = "intake/$subscriptionId"
    fun guidance(inquiryId: String, scenario: String) = "guidance/$inquiryId/$scenario"
}

package com.skn29.watercare.customer.navigation

object CustomerRoute {
    const val LOGIN = "login"
    const val HOME = "home?offline={offline}"
    const val INTAKE = "intake/{subscriptionId}"
    const val INQUIRY_CREATED = "inquiry-created/{inquiryId}/{scenario}"
    const val GUIDANCE = "guidance/{inquiryId}/{scenario}"

    fun home(offline: Boolean) = "home?offline=$offline"
    fun intake(subscriptionId: String) = "intake/$subscriptionId"
    fun inquiryCreated(inquiryId: String, scenario: String) =
        "inquiry-created/$inquiryId/$scenario"
    fun guidance(inquiryId: String, scenario: String) = "guidance/$inquiryId/$scenario"
}

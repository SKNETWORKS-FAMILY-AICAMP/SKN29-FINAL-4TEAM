package com.skn29.watercare.core.network

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PublicAuthNetworkPolicyTest {

    @Test
    fun publicAuthEndpoints_areClassifiedAsPublic() {
        val paths =
            listOf(
                "/api/v1/auth/demo-login",
                "/api/v1/auth/login",
                "/api/v1/auth/login/",
                "/api/v1/auth/signup",
                "/api/v1/auth/refresh",
                "/api/v1/auth/contract-verification/challenges",
                "/api/v1/auth/contract-verification/challenges/abc/verify",
                "/api/v1/auth/account-recovery/username/challenges",
                "/api/v1/auth/account-recovery/username/challenges/abc/verify",
                "/api/v1/auth/password-reset/challenges",
                "/api/v1/auth/password-reset/challenges/abc/verify",
                "/api/v1/auth/password-reset/confirm",
            )

        paths.forEach { path ->
            assertTrue(
                "expected public auth path: $path",
                isPublicAuthPath(path),
            )
        }
    }

    @Test
    fun authenticatedEndpoints_areNotClassifiedAsPublic() {
        val paths =
            listOf(
                "/api/v1/auth/logout",
                "/api/v1/me",
                "/api/v1/me/subscriptions",
                "/api/v1/inquiries",
                "/api/v1/inquiries/abc/submit",
            )

        paths.forEach { path ->
            assertFalse(
                "expected protected path: $path",
                isPublicAuthPath(path),
            )
        }
    }

    @Test
    fun similarButUnknownAuthPaths_areNotPublic() {
        val paths =
            listOf(
                "/api/v1/auth/login-extra",
                "/api/v1/auth/signup-extra",
                "/api/v1/auth/logout-all",
            )

        paths.forEach { path ->
            assertFalse(
                "unexpected public auth path: $path",
                isPublicAuthPath(path),
            )
        }
    }
}

package com.skn29.watercare.core.network

import com.skn29.watercare.core.auth.TokenStore
import com.skn29.watercare.core.model.AuthTokens
import com.skn29.watercare.core.model.RefreshTokenRequest
import java.util.UUID
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

class CorrelationIdInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request().newBuilder()
            .header("X-Correlation-ID", UUID.randomUUID().toString())
            .build()
        return chain.proceed(request)
    }
}

class AuthInterceptor(private val tokenStore: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenStore.current()?.accessToken
        val builder = chain.request().newBuilder()
        if (!token.isNullOrBlank()) builder.header("Authorization", "Bearer $token")
        return chain.proceed(builder.build())
    }
}

class TokenAuthenticator(
    private val tokenStore: TokenStore,
    private val refreshApi: RefreshApi,
) : Authenticator {
    private val lock = Any()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) return null
        if (response.request.url.encodedPath.endsWith("/auth/refresh")) return null

        val failedToken = response.request.header("Authorization")
            ?.removePrefix("Bearer ")
            ?.trim()
        val before = tokenStore.current() ?: return null

        synchronized(lock) {
            val latest = tokenStore.current() ?: return null
            if (!failedToken.isNullOrBlank() && latest.accessToken != failedToken) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer ${latest.accessToken}")
                    .build()
            }

            val refreshed = runCatching {
                refreshApi.refreshSync(RefreshTokenRequest(before.refreshToken)).execute()
            }.getOrNull()

            val session = refreshed?.body()?.takeIf { refreshed.isSuccessful && it.success }?.data
            if (session == null) {
                tokenStore.clearBlocking()
                return null
            }

            val tokens = AuthTokens(session.accessToken, session.refreshToken)
            tokenStore.saveBlocking(tokens)
            return response.request.newBuilder()
                .header("Authorization", "Bearer ${tokens.accessToken}")
                .build()
        }
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var current = response.priorResponse
        while (current != null) {
            count++
            current = current.priorResponse
        }
        return count
    }
}

package com.skn29.watercare.core.auth

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.skn29.watercare.core.model.AuthTokens
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

private val Context.authDataStore by preferencesDataStore(name = "watercare_auth")

class TokenStore(context: Context) {
    private val dataStore = context.applicationContext.authDataStore
    private val current = AtomicReference<AuthTokens?>(null)

    init {
        current.set(runBlocking {
            val preferences = dataStore.data.first()
            val access = preferences[ACCESS_TOKEN]
            val refresh = preferences[REFRESH_TOKEN]
            if (access.isNullOrBlank() || refresh.isNullOrBlank()) null else AuthTokens(access, refresh)
        })
    }

    fun current(): AuthTokens? = current.get()

    suspend fun save(tokens: AuthTokens) {
        current.set(tokens)
        dataStore.edit {
            it[ACCESS_TOKEN] = tokens.accessToken
            it[REFRESH_TOKEN] = tokens.refreshToken
        }
    }

    suspend fun clear() {
        current.set(null)
        dataStore.edit {
            it.remove(ACCESS_TOKEN)
            it.remove(REFRESH_TOKEN)
        }
    }

    fun saveBlocking(tokens: AuthTokens) = runBlocking { save(tokens) }
    fun clearBlocking() = runBlocking { clear() }

    private companion object {
        val ACCESS_TOKEN = stringPreferencesKey("access_token")
        val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
    }
}

package com.skn29.watercare.technician.data.dispatch

import android.content.Context
import java.util.UUID

object TechnicianIdentity {
    private const val PREFS_NAME =
        "watercare_technician_identity"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_NAME = "technician_name"

    fun deviceId(context: Context): String {
        val preferences = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )
        return preferences.getString(
            KEY_DEVICE_ID,
            null
        ) ?: UUID.randomUUID().toString().also { created ->
            preferences.edit()
                .putString(KEY_DEVICE_ID, created)
                .apply()
        }
    }

    fun name(context: Context): String =
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        ).getString(
            KEY_NAME,
            "WaterCare 방문기사"
        ).orEmpty()

    fun saveName(
        context: Context,
        name: String
    ) {
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        ).edit()
            .putString(KEY_NAME, name.trim())
            .apply()
    }
}

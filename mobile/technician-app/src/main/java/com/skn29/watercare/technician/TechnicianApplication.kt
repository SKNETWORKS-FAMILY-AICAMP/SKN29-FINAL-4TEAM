package com.skn29.watercare.technician
import android.app.Application
import com.skn29.watercare.core.WaterCareCore
class TechnicianApplication: Application(){ override fun onCreate(){ super.onCreate(); WaterCareCore.initialize(this,BuildConfig.BACKEND_BASE_URL,BuildConfig.DEBUG) } }

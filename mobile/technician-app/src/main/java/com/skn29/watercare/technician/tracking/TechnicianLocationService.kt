package com.skn29.watercare.technician.tracking

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.IBinder
import android.os.Looper
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.skn29.watercare.technician.data.dispatch.ServiceCallApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class TechnicianLocationService : Service() {
    private val serviceScope =
        CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val locationClient by lazy {
        LocationServices.getFusedLocationProviderClient(this)
    }

    private var callback: LocationCallback? = null
    private var callId: String? = null
    private var technicianDeviceId: String? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int
    ): Int {
        callId = intent?.getStringExtra(EXTRA_CALL_ID)
            ?: callId
        technicianDeviceId =
            intent?.getStringExtra(EXTRA_TECHNICIAN_DEVICE_ID)
                ?: technicianDeviceId

        if (
            callId.isNullOrBlank() ||
            technicianDeviceId.isNullOrBlank()
        ) {
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(
            NOTIFICATION_ID,
            buildNotification()
        )
        startLocationUpdates()
        return START_STICKY
    }

    @SuppressLint("MissingPermission")
    private fun startLocationUpdates() {
        if (callback != null) return

        val granted =
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission
                        .ACCESS_COARSE_LOCATION
                ) == PackageManager.PERMISSION_GRANTED

        if (!granted) {
            stopSelf()
            return
        }

        val request = LocationRequest.Builder(
            Priority.PRIORITY_HIGH_ACCURACY,
            3_000L
        )
            .setMinUpdateIntervalMillis(2_000L)
            .setMinUpdateDistanceMeters(3f)
            .build()

        callback = object : LocationCallback() {
            override fun onLocationResult(
                result: LocationResult
            ) {
                val location =
                    result.lastLocation ?: return
                val activeCallId = callId ?: return
                val activeDeviceId =
                    technicianDeviceId ?: return

                serviceScope.launch {
                    runCatching {
                        ServiceCallApi.sendLocation(
                            callId = activeCallId,
                            technicianDeviceId =
                                activeDeviceId,
                            latitude = location.latitude,
                            longitude = location.longitude,
                            accuracyMeters =
                                location.accuracy.toDouble(),
                            speedMps =
                                if (location.hasSpeed()) {
                                    location.speed.toDouble()
                                } else {
                                    null
                                },
                            heading =
                                if (location.hasBearing()) {
                                    location.bearing.toDouble()
                                } else {
                                    null
                                }
                        )
                    }
                }
            }
        }

        locationClient.requestLocationUpdates(
            request,
            callback!!,
            Looper.getMainLooper()
        )
    }

    override fun onDestroy() {
        callback?.let {
            locationClient.removeLocationUpdates(it)
        }
        callback = null
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        val manager = getSystemService(
            NotificationManager::class.java
        )
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "방문기사 위치 공유",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description =
                    "고객에게 차량 이동 위치를 공유합니다."
            }
        )
    }

    private fun buildNotification(): Notification =
        Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(
                android.R.drawable.ic_menu_mylocation
            )
            .setContentTitle("WaterCare 차량 이동 중")
            .setContentText(
                "고객에게 실제 GPS 위치를 공유하고 있습니다."
            )
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build()

    companion object {
        private const val CHANNEL_ID =
            "watercare_technician_location"
        private const val NOTIFICATION_ID = 4102
        private const val EXTRA_CALL_ID = "call_id"
        private const val EXTRA_TECHNICIAN_DEVICE_ID =
            "technician_device_id"

        fun start(
            context: Context,
            callId: String,
            technicianDeviceId: String
        ) {
            val intent = Intent(
                context,
                TechnicianLocationService::class.java
            )
                .putExtra(EXTRA_CALL_ID, callId)
                .putExtra(
                    EXTRA_TECHNICIAN_DEVICE_ID,
                    technicianDeviceId
                )

            ContextCompat.startForegroundService(
                context,
                intent
            )
        }

        fun stop(context: Context) {
            context.stopService(
                Intent(
                    context,
                    TechnicianLocationService::class.java
                )
            )
        }
    }
}

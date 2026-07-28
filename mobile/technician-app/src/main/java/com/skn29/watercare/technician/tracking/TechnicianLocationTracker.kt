package com.skn29.watercare.technician.tracking

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.os.Looper
import androidx.core.content.ContextCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.skn29.watercare.model.GeoPoint

data class TechnicianLocationSample(
    val point: GeoPoint,
    val speedMps: Float?,
    val headingDegrees: Double?,
    val accuracyMeters: Float?,
    val recordedAtMillis: Long
)

/**
 * 기사 화면이 열려 있는 동안 실제 GPS를 수집한다.
 *
 * 화면 밖에서도 계속 추적하려면 추후 Foreground Service로 감싸면 된다.
 */
class TechnicianLocationTracker(
    context: Context,
    private val onLocation: (TechnicianLocationSample) -> Unit,
    private val onError: (Throwable) -> Unit = {}
) {
    private val appContext = context.applicationContext

    private val fusedLocationClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(appContext)

    private val request = LocationRequest.Builder(
        Priority.PRIORITY_HIGH_ACCURACY,
        3_000L
    )
        .setMinUpdateIntervalMillis(1_500L)
        .setMinUpdateDistanceMeters(3f)
        .setWaitForAccurateLocation(false)
        .build()

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.locations.forEach(::dispatchLocation)
        }
    }

    fun hasPermission(): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarse = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        return fine || coarse
    }

    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        if (!hasPermission()) return false

        return runCatching {
            fusedLocationClient.requestLocationUpdates(
                request,
                callback,
                Looper.getMainLooper()
            )
            true
        }.getOrElse { error ->
            onError(error)
            false
        }
    }

    fun stop() {
        fusedLocationClient.removeLocationUpdates(callback)
    }

    private fun dispatchLocation(location: Location) {
        onLocation(
            TechnicianLocationSample(
                point = GeoPoint(
                    latitude = location.latitude,
                    longitude = location.longitude
                ),
                speedMps =
                    location.speed.takeIf { location.hasSpeed() },
                headingDegrees =
                    location.bearing
                        .toDouble()
                        .takeIf { location.hasBearing() },
                accuracyMeters =
                    location.accuracy.takeIf { location.hasAccuracy() },
                recordedAtMillis = location.time
            )
        )
    }
}

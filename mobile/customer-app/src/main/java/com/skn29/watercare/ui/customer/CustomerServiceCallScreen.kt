package com.skn29.watercare.ui.customer

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.skn29.watercare.data.dispatch.CreateServiceCallRequest
import com.skn29.watercare.data.dispatch.ServiceCall
import com.skn29.watercare.data.dispatch.ServiceCallApi
import com.skn29.watercare.data.dispatch.ServiceCallStatus
import com.skn29.watercare.model.GeoPoint
import com.skn29.watercare.model.TravelMode
import com.skn29.watercare.ui.map.KakaoTrackingMap
import java.util.UUID
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private const val CUSTOMER_PREFS =
    "watercare_customer_service_call"
private const val KEY_CUSTOMER_DEVICE_ID =
    "customer_device_id"
private const val KEY_ACTIVE_CALL_ID =
    "active_call_id"

@SuppressLint("MissingPermission")
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerServiceCallScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val preferences = remember {
        context.getSharedPreferences(
            CUSTOMER_PREFS,
            Context.MODE_PRIVATE
        )
    }
    val customerDeviceId = remember {
        preferences.getString(
            KEY_CUSTOMER_DEVICE_ID,
            null
        ) ?: UUID.randomUUID().toString().also { created ->
            preferences.edit()
                .putString(KEY_CUSTOMER_DEVICE_ID, created)
                .apply()
        }
    }

    var activeCallId by rememberSaveable {
        mutableStateOf(
            preferences.getString(
                KEY_ACTIVE_CALL_ID,
                null
            )
        )
    }
    var activeCall by remember {
        mutableStateOf<ServiceCall?>(null)
    }
    var customerName by rememberSaveable {
        mutableStateOf("")
    }
    var customerPhone by rememberSaveable {
        mutableStateOf("")
    }
    var address by rememberSaveable {
        mutableStateOf("")
    }
    var productName by rememberSaveable {
        mutableStateOf("SK매직 정수기")
    }
    var productModel by rememberSaveable {
        mutableStateOf("")
    }
    var symptom by rememberSaveable {
        mutableStateOf("")
    }
    var customerLatitude by rememberSaveable {
        mutableStateOf<Double?>(null)
    }
    var customerLongitude by rememberSaveable {
        mutableStateOf<Double?>(null)
    }
    var busy by remember {
        mutableStateOf(false)
    }
    var locationLoading by remember {
        mutableStateOf(false)
    }
    var errorMessage by remember {
        mutableStateOf<String?>(null)
    }
    var route by remember {
        mutableStateOf<List<GeoPoint>>(emptyList())
    }
    var roadDistanceMeters by remember {
        mutableStateOf<Int?>(null)
    }
    var roadDurationSeconds by remember {
        mutableStateOf<Int?>(null)
    }

    val fusedLocationClient = remember {
        LocationServices.getFusedLocationProviderClient(
            context
        )
    }

    fun requestCurrentLocation() {
        val permissionGranted =
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                ) == PackageManager.PERMISSION_GRANTED

        if (!permissionGranted) return

        locationLoading = true
        errorMessage = null
        fusedLocationClient.lastLocation
            .addOnSuccessListener { location ->
                locationLoading = false
                if (location == null) {
                    errorMessage =
                        "현재 위치를 가져오지 못했습니다. 위치 기능을 켠 뒤 다시 눌러 주세요."
                } else {
                    customerLatitude = location.latitude
                    customerLongitude = location.longitude
                }
            }
            .addOnFailureListener { error ->
                locationLoading = false
                errorMessage =
                    error.message ?: "현재 위치 확인에 실패했습니다."
            }
    }

    val permissionLauncher =
        rememberLauncherForActivityResult(
            contract =
                ActivityResultContracts.RequestMultiplePermissions()
        ) { result ->
            val granted =
                result[Manifest.permission.ACCESS_FINE_LOCATION] ==
                    true ||
                    result[
                        Manifest.permission.ACCESS_COARSE_LOCATION
                    ] == true
            if (granted) {
                requestCurrentLocation()
            } else {
                errorMessage =
                    "방문 위치를 전달하려면 위치 권한이 필요합니다."
            }
        }

    fun captureLocation() {
        val granted =
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                ) == PackageManager.PERMISSION_GRANTED

        if (granted) {
            requestCurrentLocation()
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }

    suspend fun refreshCall(callId: String) {
        activeCall = ServiceCallApi.get(callId)
    }

    LaunchedEffect(activeCallId) {
        val callId = activeCallId ?: return@LaunchedEffect

        while (isActive) {
            try {
                refreshCall(callId)
                errorMessage = null
            } catch (error: Exception) {
                errorMessage =
                    error.message ?: "요청 상태를 불러오지 못했습니다."
            }
            delay(3_000)
        }
    }

    LaunchedEffect(
        activeCall?.technicianLatitude,
        activeCall?.technicianLongitude,
        activeCall?.status
    ) {
        val call = activeCall ?: return@LaunchedEffect
        val technicianLatitude =
            call.technicianLatitude ?: return@LaunchedEffect
        val technicianLongitude =
            call.technicianLongitude ?: return@LaunchedEffect

        val fallback = listOf(
            GeoPoint(
                technicianLatitude,
                technicianLongitude
            ),
            GeoPoint(
                call.customerLatitude,
                call.customerLongitude
            )
        )
        route = fallback

        if (call.status == ServiceCallStatus.EN_ROUTE) {
            runCatching {
                ServiceCallApi.drivingRoute(
                    originLatitude = technicianLatitude,
                    originLongitude = technicianLongitude,
                    destinationLatitude =
                        call.customerLatitude,
                    destinationLongitude =
                        call.customerLongitude
                )
            }.onSuccess { drivingRoute ->
                val roadPoints = drivingRoute.points.map {
                    GeoPoint(
                        latitude = it.latitude,
                        longitude = it.longitude
                    )
                }
                if (roadPoints.size >= 2) {
                    route = roadPoints
                }
                roadDistanceMeters =
                    drivingRoute.distanceMeters
                roadDurationSeconds =
                    drivingRoute.durationSeconds
            }
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor =
                        MaterialTheme.colorScheme.surface
                ),
                title = {
                    Column {
                        Text(
                            text = "방문기사 요청",
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text =
                                "고객 요청 후 방문기사가 콜을 수락합니다.",
                            style =
                                MaterialTheme.typography.bodySmall,
                            color =
                                MaterialTheme.colorScheme
                                    .onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("뒤로")
                    }
                }
            )
        }
    ) { padding ->
        val call = activeCall
        if (
            call == null &&
            activeCallId != null &&
            !busy
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                verticalArrangement =
                    Arrangement.Center
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.padding(24.dp)
                )
            }
        } else if (
            call == null ||
            call.status == ServiceCallStatus.CANCELLED
        ) {
            RequestForm(
                modifier = Modifier.padding(padding),
                customerName = customerName,
                onCustomerNameChange = {
                    customerName = it
                },
                customerPhone = customerPhone,
                onCustomerPhoneChange = {
                    customerPhone = it
                },
                address = address,
                onAddressChange = {
                    address = it
                },
                productName = productName,
                onProductNameChange = {
                    productName = it
                },
                productModel = productModel,
                onProductModelChange = {
                    productModel = it
                },
                symptom = symptom,
                onSymptomChange = {
                    symptom = it
                },
                customerLatitude = customerLatitude,
                customerLongitude = customerLongitude,
                locationLoading = locationLoading,
                busy = busy,
                errorMessage = errorMessage,
                onCaptureLocation = ::captureLocation,
                onSubmit = {
                    val latitude = customerLatitude
                    val longitude = customerLongitude

                    when {
                        customerName.isBlank() ->
                            errorMessage =
                                "고객 이름을 입력해 주세요."

                        customerPhone.isBlank() ->
                            errorMessage =
                                "연락처를 입력해 주세요."

                        address.isBlank() ->
                            errorMessage =
                                "방문 주소를 입력해 주세요."

                        productModel.isBlank() ->
                            errorMessage =
                                "정수기 모델을 입력해 주세요."

                        symptom.isBlank() ->
                            errorMessage =
                                "증상을 입력해 주세요."

                        latitude == null ||
                            longitude == null ->
                            errorMessage =
                                "현재 위치 사용 버튼을 눌러 방문 위치를 확인해 주세요."

                        else -> scope.launch {
                            busy = true
                            errorMessage = null
                            try {
                                val created =
                                    ServiceCallApi.create(
                                        CreateServiceCallRequest(
                                            customerDeviceId =
                                                customerDeviceId,
                                            customerName =
                                                customerName.trim(),
                                            customerPhone =
                                                customerPhone.trim(),
                                            customerAddress =
                                                address.trim(),
                                            customerLatitude =
                                                latitude,
                                            customerLongitude =
                                                longitude,
                                            productName =
                                                productName.trim(),
                                            productModel =
                                                productModel.trim(),
                                            symptom =
                                                symptom.trim()
                                        )
                                    )
                                activeCall = created
                                activeCallId = created.id
                                preferences.edit()
                                    .putString(
                                        KEY_ACTIVE_CALL_ID,
                                        created.id
                                    )
                                    .apply()
                            } catch (error: Exception) {
                                errorMessage =
                                    error.message
                                        ?: "방문 요청 등록에 실패했습니다."
                            } finally {
                                busy = false
                            }
                        }
                    }
                }
            )
        } else {
            ActiveCallContent(
                modifier = Modifier.padding(padding),
                call = call,
                route = route,
                roadDistanceMeters = roadDistanceMeters,
                roadDurationSeconds = roadDurationSeconds,
                busy = busy,
                errorMessage = errorMessage,
                onCancel = {
                    scope.launch {
                        busy = true
                        errorMessage = null
                        try {
                            activeCall =
                                ServiceCallApi.cancel(
                                    callId = call.id,
                                    customerDeviceId =
                                        customerDeviceId
                                )
                        } catch (error: Exception) {
                            errorMessage =
                                error.message
                                    ?: "요청 취소에 실패했습니다."
                        } finally {
                            busy = false
                        }
                    }
                },
                onNewRequest = {
                    activeCall = null
                    activeCallId = null
                    route = emptyList()
                    preferences.edit()
                        .remove(KEY_ACTIVE_CALL_ID)
                        .apply()
                }
            )
        }
    }
}

@Composable
private fun RequestForm(
    modifier: Modifier,
    customerName: String,
    onCustomerNameChange: (String) -> Unit,
    customerPhone: String,
    onCustomerPhoneChange: (String) -> Unit,
    address: String,
    onAddressChange: (String) -> Unit,
    productName: String,
    onProductNameChange: (String) -> Unit,
    productModel: String,
    onProductModelChange: (String) -> Unit,
    symptom: String,
    onSymptomChange: (String) -> Unit,
    customerLatitude: Double?,
    customerLongitude: Double?,
    locationLoading: Boolean,
    busy: Boolean,
    errorMessage: String?,
    onCaptureLocation: () -> Unit,
    onSubmit: () -> Unit
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 18.dp,
            end = 18.dp,
            top = 18.dp,
            bottom = 32.dp
        ),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            InfoBanner(
                title = "고객은 요청만 합니다",
                body =
                    "요청이 등록되면 주변 방문기사 앱에 새 콜이 표시되고, 기사 수락 후 실제 이동 위치를 확인할 수 있습니다."
            )
        }

        item {
            FormSection(title = "고객 정보") {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = customerName,
                    onValueChange = onCustomerNameChange,
                    label = { Text("고객 이름") },
                    singleLine = true
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = customerPhone,
                    onValueChange = onCustomerPhoneChange,
                    label = { Text("연락처") },
                    placeholder = {
                        Text("010-0000-0000")
                    },
                    singleLine = true
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = address,
                    onValueChange = onAddressChange,
                    label = { Text("방문 주소") },
                    minLines = 2
                )

                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !locationLoading,
                    onClick = onCaptureLocation
                ) {
                    Text(
                        if (locationLoading) {
                            "현재 위치 확인 중..."
                        } else {
                            "현재 위치 사용"
                        }
                    )
                }

                val locationText =
                    if (
                        customerLatitude != null &&
                        customerLongitude != null
                    ) {
                        "방문 위치 확인 완료 · %.5f, %.5f".format(
                            customerLatitude,
                            customerLongitude
                        )
                    } else {
                        "방문기사 이동 경로 계산을 위해 현재 위치가 필요합니다."
                    }

                Text(
                    text = locationText,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (customerLatitude != null) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme
                            .onSurfaceVariant
                    }
                )
            }
        }

        item {
            FormSection(title = "제품 및 증상") {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = productName,
                    onValueChange = onProductNameChange,
                    label = { Text("제품명") },
                    singleLine = true
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = productModel,
                    onValueChange = onProductModelChange,
                    label = { Text("모델명") },
                    placeholder = {
                        Text("예: WPUJAC104DWH")
                    },
                    singleLine = true
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = symptom,
                    onValueChange = onSymptomChange,
                    label = { Text("현재 증상") },
                    placeholder = {
                        Text(
                            "언제부터 어떤 증상이 발생했는지 작성해 주세요."
                        )
                    },
                    minLines = 4
                )
            }
        }

        errorMessage?.let { message ->
            item {
                ErrorBanner(message)
            }
        }

        item {
            Button(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp),
                enabled = !busy,
                onClick = onSubmit
            ) {
                Text(
                    if (busy) {
                        "요청 등록 중..."
                    } else {
                        "방문기사 호출 요청"
                    },
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun ActiveCallContent(
    modifier: Modifier,
    call: ServiceCall,
    route: List<GeoPoint>,
    roadDistanceMeters: Int?,
    roadDurationSeconds: Int?,
    busy: Boolean,
    errorMessage: String?,
    onCancel: () -> Unit,
    onNewRequest: () -> Unit
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 18.dp,
            end = 18.dp,
            top = 18.dp,
            bottom = 32.dp
        ),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            StatusHero(call)
        }

        item {
            CallTimeline(status = call.status)
        }

        if (
            call.status == ServiceCallStatus.EN_ROUTE &&
            call.technicianLatitude != null &&
            call.technicianLongitude != null
        ) {
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(390.dp),
                    shape = RoundedCornerShape(24.dp),
                    elevation =
                        CardDefaults.cardElevation(2.dp)
                ) {
                    KakaoTrackingMap(
                        route = if (route.size >= 2) {
                            route
                        } else {
                            listOf(
                                GeoPoint(
                                    call.technicianLatitude,
                                    call.technicianLongitude
                                ),
                                GeoPoint(
                                    call.customerLatitude,
                                    call.customerLongitude
                                )
                            )
                        },
                        technician = GeoPoint(
                            call.technicianLatitude,
                            call.technicianLongitude
                        ),
                        customer = GeoPoint(
                            call.customerLatitude,
                            call.customerLongitude
                        ),
                        travelMode = TravelMode.DRIVING,
                        headingDegrees =
                            call.technicianHeading ?: 0.0,
                        routeRecalculating = false,
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }

            item {
                DrivingSummary(
                    call = call,
                    roadDistanceMeters =
                        roadDistanceMeters,
                    roadDurationSeconds =
                        roadDurationSeconds
                )
            }
        }

        item {
            FormSection(title = "요청 정보") {
                DetailLine("고객", call.customerName)
                DetailLine("주소", call.customerAddress)
                DetailLine(
                    "제품",
                    "${call.productName} · ${call.productModel}"
                )
                DetailLine("증상", call.symptom)
            }
        }

        if (call.status == ServiceCallStatus.COMPLETED) {
            item {
                FormSection(title = "방문 처리 결과") {
                    DetailLine(
                        "처리 유형",
                        call.resultType ?: "-"
                    )
                    DetailLine(
                        "점검 결과",
                        call.diagnosis.ifBlank { "-" }
                    )
                    DetailLine(
                        "수행 조치",
                        call.actionTaken.ifBlank { "-" }
                    )
                    DetailLine(
                        "교체 부품",
                        call.partsUsed.ifBlank { "없음" }
                    )
                    DetailLine(
                        "기사 안내",
                        call.customerNote.ifBlank { "-" }
                    )
                }
            }
        }

        errorMessage?.let { message ->
            item {
                ErrorBanner(message)
            }
        }

        if (
            call.status == ServiceCallStatus.REQUESTED ||
            call.status == ServiceCallStatus.ACCEPTED
        ) {
            item {
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !busy,
                    onClick = onCancel
                ) {
                    Text("방문 요청 취소")
                }
            }
        }

        if (
            call.status == ServiceCallStatus.COMPLETED ||
            call.status == ServiceCallStatus.CANCELLED
        ) {
            item {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onNewRequest
                ) {
                    Text("새 방문 요청 작성")
                }
            }
        }
    }
}

@Composable
private fun StatusHero(
    call: ServiceCall
) {
    val description = when (call.status) {
        ServiceCallStatus.REQUESTED ->
            "방문기사가 콜을 확인하고 있습니다."

        ServiceCallStatus.ACCEPTED ->
            "${call.technicianName ?: "방문기사"}님이 요청을 수락했습니다."

        ServiceCallStatus.EN_ROUTE ->
            "${call.technicianName ?: "방문기사"}님이 차량으로 이동 중입니다."

        ServiceCallStatus.ARRIVED ->
            "방문기사가 고객 위치에 도착했습니다."

        ServiceCallStatus.COMPLETED ->
            "방문 점검과 처리가 완료됐습니다."

        ServiceCallStatus.CANCELLED ->
            "방문 요청이 취소됐습니다."
    }

    Card(
        colors = CardDefaults.cardColors(
            containerColor =
                MaterialTheme.colorScheme.primaryContainer
        ),
        shape = RoundedCornerShape(24.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = call.status.label,
                style = MaterialTheme.typography.titleLarge,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer,
                fontWeight = FontWeight.ExtraBold
            )
            Text(
                text = description,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer
            )
            Text(
                text = "요청 번호 ${call.id.take(8)}",
                style = MaterialTheme.typography.bodySmall,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer
            )
        }
    }
}

@Composable
private fun DrivingSummary(
    call: ServiceCall,
    roadDistanceMeters: Int?,
    roadDurationSeconds: Int?
) {
    val distance = roadDistanceMeters
        ?: call.distanceMeters
    val minutes = roadDurationSeconds
        ?.let { (it / 60).coerceAtLeast(1) }
        ?: call.etaMinutes

    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp)
        ) {
            Text(
                text = "실시간 차량 이동",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = buildString {
                    if (minutes != null) {
                        append("약 ${minutes}분")
                    } else {
                        append("도착 시간 계산 중")
                    }
                    if (distance != null) {
                        append(" · ")
                        append(
                            if (distance >= 1000) {
                                "%.1fkm".format(
                                    distance / 1000.0
                                )
                            } else {
                                "${distance}m"
                            }
                        )
                    }
                },
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = when (
                    call.trackingConnectionState
                ) {
                    "LIVE" -> "기사 위치가 실시간으로 연결됐습니다."
                    "STALE" -> "기사 위치 신호가 잠시 지연되고 있습니다."
                    "OFFLINE" -> "기사 위치 연결이 끊겼습니다."
                    else -> "기사 위치 연결 중입니다."
                },
                style = MaterialTheme.typography.bodySmall,
                color =
                    MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun CallTimeline(
    status: ServiceCallStatus
) {
    val steps = listOf(
        ServiceCallStatus.REQUESTED to "요청 접수",
        ServiceCallStatus.ACCEPTED to "기사 수락",
        ServiceCallStatus.EN_ROUTE to "차량 이동",
        ServiceCallStatus.ARRIVED to "기사 도착",
        ServiceCallStatus.COMPLETED to "처리 완료"
    )
    val currentIndex = steps.indexOfFirst {
        it.first == status
    }

    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp)
        ) {
            Text(
                text = "진행 단계",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            steps.forEachIndexed { index, pair ->
                val reached =
                    currentIndex >= index &&
                        status != ServiceCallStatus.CANCELLED
                Text(
                    text =
                        "${if (reached) "●" else "○"} ${pair.second}",
                    color = if (reached) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme
                            .onSurfaceVariant
                    },
                    fontWeight = if (reached) {
                        FontWeight.SemiBold
                    } else {
                        FontWeight.Normal
                    }
                )
            }
        }
    }
}

@Composable
private fun FormSection(
    title: String,
    content: @Composable
        androidx.compose.foundation.layout.ColumnScope.() -> Unit
) {
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            content()
        }
    }
}

@Composable
private fun InfoBanner(
    title: String,
    body: String
) {
    Surface(
        color =
            MaterialTheme.colorScheme.secondaryContainer,
        shape = RoundedCornerShape(20.dp)
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(
                text = title,
                fontWeight = FontWeight.Bold,
                color =
                    MaterialTheme.colorScheme
                        .onSecondaryContainer
            )
            Text(
                text = body,
                style = MaterialTheme.typography.bodyMedium,
                color =
                    MaterialTheme.colorScheme
                        .onSecondaryContainer
            )
        }
    }
}

@Composable
private fun ErrorBanner(
    message: String
) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(14.dp),
            color =
                MaterialTheme.colorScheme.onErrorContainer
        )
    }
}

@Composable
private fun DetailLine(
    label: String,
    value: String
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(3.dp)
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color =
                MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium
        )
        HorizontalDivider()
    }
}

package com.skn29.watercare.technician.feature.visitdetail

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.skn29.watercare.technician.data.dispatch.ServiceCall
import com.skn29.watercare.technician.data.dispatch.ServiceCallApi
import com.skn29.watercare.technician.data.dispatch.ServiceCallStatus
import com.skn29.watercare.technician.data.dispatch.TechnicianIdentity
import com.skn29.watercare.technician.tracking.TechnicianLocationService
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitDetailScreen(
    visitId: String,
    onBack: () -> Unit,
    onRegisterResult: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val technicianDeviceId = remember {
        TechnicianIdentity.deviceId(context)
    }
    val technicianName = remember {
        TechnicianIdentity.name(context)
    }

    var call by remember {
        mutableStateOf<ServiceCall?>(null)
    }
    var busy by remember {
        mutableStateOf(false)
    }
    var errorMessage by remember {
        mutableStateOf<String?>(null)
    }
    var hasLocationPermission by remember {
        mutableStateOf(
            hasLocationPermission(context)
        )
    }

    suspend fun refresh() {
        try {
            call = ServiceCallApi.get(visitId)
            errorMessage = null
        } catch (error: Exception) {
            errorMessage =
                error.message ?: "콜 상세를 불러오지 못했습니다."
        }
    }

    LaunchedEffect(visitId) {
        while (isActive) {
            refresh()
            delay(3_000)
        }
    }

    val permissionLauncher =
        rememberLauncherForActivityResult(
            contract =
                ActivityResultContracts.RequestMultiplePermissions()
        ) { result ->
            hasLocationPermission =
                result[Manifest.permission.ACCESS_FINE_LOCATION] ==
                    true ||
                    result[
                        Manifest.permission.ACCESS_COARSE_LOCATION
                    ] == true

            if (!hasLocationPermission) {
                errorMessage =
                    "차량 이동 위치 전송을 위해 위치 권한이 필요합니다."
            }
        }

    LaunchedEffect(
        call?.status,
        hasLocationPermission,
        visitId
    ) {
        when (call?.status) {
            ServiceCallStatus.EN_ROUTE -> {
                if (hasLocationPermission) {
                    TechnicianLocationService.start(
                        context = context,
                        callId = visitId,
                        technicianDeviceId =
                            technicianDeviceId
                    )
                }
            }

            ServiceCallStatus.ARRIVED,
            ServiceCallStatus.COMPLETED,
            ServiceCallStatus.CANCELLED -> {
                TechnicianLocationService.stop(context)
            }

            else -> Unit
        }
    }

    fun executeAction(
        action: suspend () -> ServiceCall,
        fallbackMessage: String,
        afterSuccess: (() -> Unit)? = null
    ) {
        scope.launch {
            busy = true
            errorMessage = null
            try {
                call = action()
                afterSuccess?.invoke()
            } catch (error: Exception) {
                errorMessage =
                    error.message ?: fallbackMessage
            } finally {
                busy = false
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
                    Text(
                        text = "콜 업무 상세",
                        fontWeight = FontWeight.Bold
                    )
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("뒤로")
                    }
                }
            )
        }
    ) { padding ->
        val currentCall = call

        if (currentCall == null) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center
            ) {
                Text(
                    text = errorMessage
                        ?: "콜 정보를 불러오는 중입니다."
                )
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(
                start = 18.dp,
                end = 18.dp,
                top = 18.dp,
                bottom = 32.dp
            ),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                CallStatusHeader(currentCall)
            }

            item {
                ActionFlowCard(currentCall.status)
            }

            item {
                SectionCard(title = "고객 및 방문 위치") {
                    DetailLine(
                        "고객",
                        currentCall.customerName
                    )
                    DetailLine(
                        "연락처",
                        currentCall.customerPhone
                    )
                    DetailLine(
                        "주소",
                        currentCall.customerAddress
                    )
                    DetailLine(
                        "고객 GPS",
                        "%.5f, %.5f".format(
                            currentCall.customerLatitude,
                            currentCall.customerLongitude
                        )
                    )

                    OutlinedButton(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            openDialer(
                                context,
                                currentCall.customerPhone
                            )
                        }
                    ) {
                        Text("고객에게 전화")
                    }

                    OutlinedButton(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            openNavigation(
                                context,
                                currentCall.customerLatitude,
                                currentCall.customerLongitude,
                                currentCall.customerAddress
                            )
                        }
                    ) {
                        Text("차량 길찾기 실행")
                    }
                }
            }

            item {
                SectionCard(title = "제품 및 증상") {
                    DetailLine(
                        "제품",
                        currentCall.productName
                    )
                    DetailLine(
                        "모델",
                        currentCall.productModel
                    )
                    DetailLine(
                        "고객 증상",
                        currentCall.symptom
                    )
                }
            }

            if (
                currentCall.status ==
                    ServiceCallStatus.EN_ROUTE
            ) {
                item {
                    GpsTransmissionCard(
                        hasPermission =
                            hasLocationPermission,
                        connectionState =
                            currentCall
                                .trackingConnectionState,
                        locationMessage =
                            when (
                                currentCall
                                    .trackingConnectionState
                            ) {
                                "LIVE" ->
                                    "실제 GPS 위치가 고객 앱에 실시간 전송 중입니다."
                                "STALE" ->
                                    "위치 신호가 잠시 지연되고 있습니다."
                                "OFFLINE" ->
                                    "위치 연결이 끊겼습니다. GPS와 네트워크를 확인해 주세요."
                                else ->
                                    "위치 서비스 연결 중입니다."
                            },
                        onRequestPermission = {
                            permissionLauncher.launch(
                                arrayOf(
                                    Manifest.permission
                                        .ACCESS_FINE_LOCATION,
                                    Manifest.permission
                                        .ACCESS_COARSE_LOCATION
                                )
                            )
                        }
                    )
                }
            }

            errorMessage?.let { message ->
                item {
                    ErrorBanner(message)
                }
            }

            item {
                when (currentCall.status) {
                    ServiceCallStatus.REQUESTED -> {
                        Button(
                            modifier =
                                Modifier.fillMaxWidth(),
                            enabled =
                                !busy &&
                                    technicianName.isNotBlank(),
                            onClick = {
                                executeAction(
                                    action = {
                                        ServiceCallApi.accept(
                                            callId =
                                                currentCall.id,
                                            technicianDeviceId =
                                                technicianDeviceId,
                                            technicianName =
                                                technicianName
                                        )
                                    },
                                    fallbackMessage =
                                        "콜 수락에 실패했습니다."
                                )
                            }
                        ) {
                            Text(
                                if (busy) {
                                    "콜 수락 처리 중..."
                                } else {
                                    "콜 수락"
                                },
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    ServiceCallStatus.ACCEPTED -> {
                        Button(
                            modifier =
                                Modifier.fillMaxWidth(),
                            enabled = !busy,
                            onClick = {
                                if (
                                    !hasLocationPermission
                                ) {
                                    errorMessage =
                                        "위치 권한을 허용한 뒤 차량 출발 버튼을 다시 눌러 주세요."
                                    permissionLauncher.launch(
                                        arrayOf(
                                            Manifest.permission
                                                .ACCESS_FINE_LOCATION,
                                            Manifest.permission
                                                .ACCESS_COARSE_LOCATION
                                        )
                                    )
                                } else {
                                    executeAction(
                                        action = {
                                            ServiceCallApi.depart(
                                                callId =
                                                    currentCall.id,
                                                technicianDeviceId =
                                                    technicianDeviceId
                                            )
                                        },
                                        fallbackMessage =
                                            "차량 출발 처리에 실패했습니다."
                                    )
                                }
                            }
                        ) {
                            Text(
                                if (busy) {
                                    "출발 처리 중..."
                                } else {
                                    "차량 출발 및 위치 공유 시작"
                                },
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    ServiceCallStatus.EN_ROUTE -> {
                        Button(
                            modifier =
                                Modifier.fillMaxWidth(),
                            enabled = !busy,
                            onClick = {
                                executeAction(
                                    action = {
                                        ServiceCallApi.arrive(
                                            callId =
                                                currentCall.id,
                                            technicianDeviceId =
                                                technicianDeviceId
                                        )
                                    },
                                    fallbackMessage =
                                        "도착 처리에 실패했습니다."
                                )
                            }
                        ) {
                            Text(
                                if (busy) {
                                    "도착 처리 중..."
                                } else {
                                    "고객 위치 도착"
                                },
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    ServiceCallStatus.ARRIVED -> {
                        Button(
                            modifier =
                                Modifier.fillMaxWidth(),
                            enabled = !busy,
                            onClick = onRegisterResult
                        ) {
                            Text(
                                "방문 점검 결과 등록",
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    ServiceCallStatus.COMPLETED -> {
                        Surface(
                            color =
                                MaterialTheme.colorScheme
                                    .secondaryContainer,
                            shape =
                                RoundedCornerShape(18.dp)
                        ) {
                            Text(
                                text =
                                    "이 콜의 방문 처리가 완료됐습니다.",
                                modifier =
                                    Modifier.padding(16.dp),
                                color =
                                    MaterialTheme.colorScheme
                                        .onSecondaryContainer,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    ServiceCallStatus.CANCELLED -> {
                        Surface(
                            color =
                                MaterialTheme.colorScheme
                                    .surfaceVariant,
                            shape =
                                RoundedCornerShape(18.dp)
                        ) {
                            Text(
                                text =
                                    "고객이 요청을 취소했습니다.",
                                modifier =
                                    Modifier.padding(16.dp),
                                color =
                                    MaterialTheme.colorScheme
                                        .onSurfaceVariant
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CallStatusHeader(
    call: ServiceCall
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor =
                MaterialTheme.colorScheme.primaryContainer
        ),
        shape = RoundedCornerShape(24.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp)
        ) {
            Text(
                text = call.status.label,
                style = MaterialTheme.typography.titleLarge,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer,
                fontWeight = FontWeight.ExtraBold
            )
            Text(
                text =
                    "${call.customerName} · ${call.productModel}",
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer
            )
            Text(
                text = "콜 번호 ${call.id.take(8)}",
                style = MaterialTheme.typography.bodySmall,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer
            )
        }
    }
}

@Composable
private fun ActionFlowCard(
    status: ServiceCallStatus
) {
    val flow = listOf(
        "콜 수락",
        "차량 출발",
        "실시간 위치 전송",
        "고객 위치 도착",
        "점검 결과 등록"
    )
    val current = when (status) {
        ServiceCallStatus.REQUESTED -> 0
        ServiceCallStatus.ACCEPTED -> 1
        ServiceCallStatus.EN_ROUTE -> 2
        ServiceCallStatus.ARRIVED -> 4
        ServiceCallStatus.COMPLETED -> 5
        ServiceCallStatus.CANCELLED -> -1
    }

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
                text = "기사 업무 흐름",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            flow.forEachIndexed { index, label ->
                Text(
                    text =
                        "${if (index < current) "✓" else if (index == current) "▶" else "○"} $label",
                    color = if (
                        index <= current &&
                        current >= 0
                    ) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme
                            .onSurfaceVariant
                    },
                    fontWeight = if (index == current) {
                        FontWeight.Bold
                    } else {
                        FontWeight.Normal
                    }
                )
            }
        }
    }
}

@Composable
private fun GpsTransmissionCard(
    hasPermission: Boolean,
    connectionState: String,
    locationMessage: String,
    onRequestPermission: () -> Unit
) {
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor =
                MaterialTheme.colorScheme.tertiaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "실시간 차량 위치 공유",
                style = MaterialTheme.typography.titleMedium,
                color =
                    MaterialTheme.colorScheme
                        .onTertiaryContainer,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = if (hasPermission) {
                    locationMessage
                } else {
                    "위치 권한이 없어 고객 앱에 차량 위치를 전송할 수 없습니다."
                },
                color =
                    MaterialTheme.colorScheme
                        .onTertiaryContainer
            )
            Text(
                text = "서버 연결 상태: $connectionState",
                style = MaterialTheme.typography.bodySmall,
                color =
                    MaterialTheme.colorScheme
                        .onTertiaryContainer
            )
            if (!hasPermission) {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onRequestPermission
                ) {
                    Text("위치 권한 허용")
                }
            }
        }
    }
}

@Composable
private fun SectionCard(
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
            verticalArrangement = Arrangement.spacedBy(11.dp)
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

private fun hasLocationPermission(
    context: Context
): Boolean =
    ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.ACCESS_FINE_LOCATION
    ) == PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

private fun openDialer(
    context: Context,
    phone: String
) {
    context.startActivity(
        Intent(
            Intent.ACTION_DIAL,
            Uri.parse("tel:$phone")
        )
    )
}

private fun openNavigation(
    context: Context,
    latitude: Double,
    longitude: Double,
    address: String
) {
    val uri = Uri.parse(
        "geo:$latitude,$longitude?q=$latitude,$longitude(${
            Uri.encode(address)
        })"
    )
    context.startActivity(
        Intent.createChooser(
            Intent(Intent.ACTION_VIEW, uri),
            "차량 길찾기 앱 선택"
        )
    )
}

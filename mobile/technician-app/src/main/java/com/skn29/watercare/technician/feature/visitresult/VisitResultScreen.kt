package com.skn29.watercare.technician.feature.visitresult

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
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
import com.skn29.watercare.technician.data.dispatch.CompleteServiceCallRequest
import com.skn29.watercare.technician.data.dispatch.ServiceCall
import com.skn29.watercare.technician.data.dispatch.ServiceCallApi
import com.skn29.watercare.technician.data.dispatch.ServiceCallStatus
import com.skn29.watercare.technician.data.dispatch.TechnicianIdentity
import kotlinx.coroutines.launch

private enum class ResultType(
    val apiValue: String,
    val label: String
) {
    NORMAL("NORMAL", "정상 처리"),
    PART_REPLACED("PART_REPLACED", "부품 교체"),
    REVISIT("REVISIT", "재방문 필요")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitResultScreen(
    visitId: String,
    onBack: () -> Unit,
    onCompleted: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val technicianDeviceId = remember {
        TechnicianIdentity.deviceId(context)
    }

    var call by remember {
        mutableStateOf<ServiceCall?>(null)
    }
    var selectedType by rememberSaveable {
        mutableStateOf(ResultType.NORMAL)
    }
    var diagnosis by rememberSaveable {
        mutableStateOf("")
    }
    var actionTaken by rememberSaveable {
        mutableStateOf("")
    }
    var partsUsed by rememberSaveable {
        mutableStateOf("")
    }
    var customerNote by rememberSaveable {
        mutableStateOf("")
    }
    var followUpRequired by rememberSaveable {
        mutableStateOf(false)
    }
    var busy by remember {
        mutableStateOf(false)
    }
    var errorMessage by remember {
        mutableStateOf<String?>(null)
    }
    var showConfirmDialog by remember {
        mutableStateOf(false)
    }

    LaunchedEffect(visitId) {
        try {
            call = ServiceCallApi.get(visitId)
        } catch (error: Exception) {
            errorMessage =
                error.message ?: "콜 정보를 불러오지 못했습니다."
        }
    }

    if (showConfirmDialog) {
        AlertDialog(
            onDismissRequest = {
                showConfirmDialog = false
            },
            title = {
                Text("방문 처리를 완료할까요?")
            },
            text = {
                Text(
                    "저장한 점검 결과는 고객 앱에 즉시 표시됩니다."
                )
            },
            confirmButton = {
                TextButton(
                    enabled = !busy,
                    onClick = {
                        scope.launch {
                            busy = true
                            errorMessage = null
                            try {
                                call =
                                    ServiceCallApi.complete(
                                        callId = visitId,
                                        technicianDeviceId =
                                            technicianDeviceId,
                                        request =
                                            CompleteServiceCallRequest(
                                                resultType =
                                                    selectedType.apiValue,
                                                diagnosis =
                                                    diagnosis.trim(),
                                                actionTaken =
                                                    actionTaken.trim(),
                                                partsUsed =
                                                    partsUsed.trim(),
                                                customerNote =
                                                    customerNote.trim(),
                                                followUpRequired =
                                                    followUpRequired
                                            )
                                    )
                                showConfirmDialog = false
                                onCompleted()
                            } catch (
                                error: Exception
                            ) {
                                showConfirmDialog = false
                                errorMessage =
                                    error.message
                                        ?: "처리 완료 저장에 실패했습니다."
                            } finally {
                                busy = false
                            }
                        }
                    }
                ) {
                    Text(
                        if (busy) {
                            "저장 중..."
                        } else {
                            "완료"
                        }
                    )
                }
            },
            dismissButton = {
                TextButton(
                    enabled = !busy,
                    onClick = {
                        showConfirmDialog = false
                    }
                ) {
                    Text("취소")
                }
            }
        )
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
                        text = "방문 점검 결과",
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
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor =
                            MaterialTheme.colorScheme
                                .primaryContainer
                    ),
                    shape = RoundedCornerShape(22.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement =
                            Arrangement.spacedBy(6.dp)
                    ) {
                        Text(
                            text =
                                currentCall?.customerName
                                    ?: "고객 정보 확인 중",
                            style =
                                MaterialTheme.typography
                                    .titleMedium,
                            color =
                                MaterialTheme.colorScheme
                                    .onPrimaryContainer,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = currentCall?.let {
                                "${it.productName} · ${it.productModel}"
                            } ?: visitId.take(8),
                            color =
                                MaterialTheme.colorScheme
                                    .onPrimaryContainer
                        )
                        Text(
                            text =
                                "현재 단계: ${currentCall?.status?.label ?: "확인 중"}",
                            style =
                                MaterialTheme.typography
                                    .bodySmall,
                            color =
                                MaterialTheme.colorScheme
                                    .onPrimaryContainer
                        )
                    }
                }
            }

            if (
                currentCall != null &&
                currentCall.status !=
                    ServiceCallStatus.ARRIVED
            ) {
                item {
                    Surface(
                        color =
                            MaterialTheme.colorScheme
                                .errorContainer,
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Text(
                            text =
                                "고객 위치 도착 처리 후 결과를 등록할 수 있습니다.",
                            modifier = Modifier.padding(14.dp),
                            color =
                                MaterialTheme.colorScheme
                                    .onErrorContainer
                        )
                    }
                }
            }

            item {
                Text(
                    text = "처리 유형",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(
                            rememberScrollState()
                        ),
                    horizontalArrangement =
                        Arrangement.spacedBy(8.dp)
                ) {
                    ResultType.entries.forEach { type ->
                        FilterChip(
                            selected =
                                selectedType == type,
                            onClick = {
                                selectedType = type
                                if (
                                    type ==
                                        ResultType.REVISIT
                                ) {
                                    followUpRequired = true
                                }
                            },
                            label = {
                                Text(type.label)
                            }
                        )
                    }
                }
            }

            item {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = diagnosis,
                    onValueChange = {
                        diagnosis = it
                    },
                    label = {
                        Text("점검 결과")
                    },
                    placeholder = {
                        Text(
                            "확인한 원인과 제품 상태를 작성해 주세요."
                        )
                    },
                    minLines = 3
                )
            }

            item {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = actionTaken,
                    onValueChange = {
                        actionTaken = it
                    },
                    label = {
                        Text("수행 조치")
                    },
                    placeholder = {
                        Text(
                            "세척, 조정, 부품 교체 등 실제 조치를 작성해 주세요."
                        )
                    },
                    minLines = 3
                )
            }

            item {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = partsUsed,
                    onValueChange = {
                        partsUsed = it
                    },
                    label = {
                        Text("사용 또는 교체 부품")
                    },
                    placeholder = {
                        Text("없음")
                    }
                )
            }

            item {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = customerNote,
                    onValueChange = {
                        customerNote = it
                    },
                    label = {
                        Text("고객 안내 및 특이사항")
                    },
                    minLines = 2
                )
            }

            item {
                Surface(
                    color =
                        MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(18.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement =
                            Arrangement.spacedBy(10.dp)
                    ) {
                        Checkbox(
                            checked =
                                followUpRequired,
                            onCheckedChange = {
                                followUpRequired = it
                            }
                        )
                        Column(
                            modifier =
                                Modifier.padding(top = 9.dp)
                        ) {
                            Text(
                                text = "후속 확인 필요",
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text =
                                    "재방문 또는 상담사 확인이 필요하면 선택합니다.",
                                style =
                                    MaterialTheme.typography
                                        .bodySmall,
                                color =
                                    MaterialTheme.colorScheme
                                        .onSurfaceVariant
                            )
                        }
                    }
                }
            }

            errorMessage?.let { message ->
                item {
                    Surface(
                        color =
                            MaterialTheme.colorScheme
                                .errorContainer,
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Text(
                            text = message,
                            modifier =
                                Modifier.padding(14.dp),
                            color =
                                MaterialTheme.colorScheme
                                    .onErrorContainer
                        )
                    }
                }
            }

            item {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    enabled =
                        !busy &&
                            diagnosis.isNotBlank() &&
                            actionTaken.isNotBlank() &&
                            currentCall?.status ==
                                ServiceCallStatus.ARRIVED,
                    onClick = {
                        showConfirmDialog = true
                    }
                ) {
                    Text(
                        "처리 완료 및 고객에게 전송",
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

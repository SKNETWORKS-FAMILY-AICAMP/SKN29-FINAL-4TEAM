package com.skn29.watercare.ui.customer

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.skn29.watercare.KakaoMapRuntime
import com.skn29.watercare.R
import com.skn29.watercare.data.AppStateStore
import com.skn29.watercare.model.InquiryEntryMode
import com.skn29.watercare.model.InquiryState
import com.skn29.watercare.model.LocationSignalStatus
import com.skn29.watercare.model.TrackingConnectionState
import com.skn29.watercare.model.TravelMode
import com.skn29.watercare.model.VisitScheduleStatus
import com.skn29.watercare.tracking.TrackingRepository
import com.skn29.watercare.ui.map.DemoTrackingMap
import com.skn29.watercare.ui.map.KakaoTrackingMap
import com.skn29.watercare.ui.shared.InfoRow
import com.skn29.watercare.ui.shared.MascotMessage
import com.skn29.watercare.ui.shared.SectionCard
import com.skn29.watercare.ui.shared.StatusPill
import com.skn29.watercare.ui.shared.StepHeader
import com.skn29.watercare.ui.shared.WaterCareScaffold
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Locale
import kotlin.time.Duration.Companion.milliseconds

private val HeroBlue = Color(0xFF1768E5)
private val HeroTeal = Color(0xFF00A6A6)
private val SoftWarning = Color(0xFFFFF5E7)
private val WarningText = Color(0xFF8B5200)
private val SuccessGreen = Color(0xFF17865B)

@Composable
fun CustomerHomeScreen(
    onQrScan: () -> Unit,
    onQuestionnaire: () -> Unit,
    onOpenVisit: () -> Unit
) {
    val inquiry by AppStateStore.inquiry.collectAsState()

    WaterCareScaffold(title = "정수기 딜러") { modifier ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            HomeHero()

            Text(
                text = "빠른 오류 확인",
                style = MaterialTheme.typography.titleLarge
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                HomeActionCard(
                    icon = "📝",
                    title = "문진 작성",
                    description = "증상을 직접 알려주세요",
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    modifier = Modifier.weight(1f),
                    onClick = onQuestionnaire
                )
                HomeActionCard(
                    icon = "▦",
                    title = "QR 확인",
                    description = "오류코드를 빠르게 확인",
                    containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                    modifier = Modifier.weight(1f),
                    onClick = onQrScan
                )
            }

            SectionCard(
                title = "내 정수기",
                icon = "💧"
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(58.dp)
                            .background(
                                MaterialTheme.colorScheme.primaryContainer,
                                RoundedCornerShape(18.dp)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("W", style = MaterialTheme.typography.headlineSmall)
                    }
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .padding(start = 14.dp),
                        verticalArrangement = Arrangement.spacedBy(3.dp)
                    ) {
                        Text(
                            "SK매직 WPU-JAC104D",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            "방문 관리형 · 정상 사용 중",
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    StatusPill(
                        text = "관리 중",
                        color = HeroTeal
                    )
                }

                Spacer(Modifier.height(16.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Spacer(Modifier.height(14.dp))
                InfoRow("최근 케어", "2026. 6. 12.")
                Spacer(Modifier.height(8.dp))
                InfoRow("다음 케어", "2026. 8. 12.")
            }

            if (inquiry.state == InquiryState.VISIT_SCHEDULED) {
                SectionCard(
                    title = "진행 중인 방문",
                    icon = "🚙",
                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                ) {
                    StatusPill(
                        text = "방문 일정 확정",
                        color = HeroTeal,
                        backgroundColor = Color.White.copy(alpha = 0.75f)
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        "김정수 기사님이 배정되었습니다.",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        "기사 출발 후 지도에서 이동 현황을 확인할 수 있어요.",
                        color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.72f)
                    )
                    Spacer(Modifier.height(14.dp))
                    Button(
                        onClick = onOpenVisit,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = HeroTeal)
                    ) {
                        Text("방문 현황 확인")
                    }
                }
            }

            Text(
                text = "정수기 관리, 쉽고 빠르게. 믿을 수 있는 케어 파트너",
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}

@Composable
private fun HomeHero() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(30.dp))
            .background(
                Brush.linearGradient(
                    colors = listOf(Color(0xFF0E61DA), Color(0xFF16A8C7))
                )
            )
            .padding(start = 22.dp, top = 22.dp, end = 8.dp, bottom = 14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(9.dp)
            ) {
                StatusPill(
                    text = "AI 고객 케어",
                    color = Color.White,
                    backgroundColor = Color.White.copy(alpha = 0.18f)
                )
                Text(
                    text = "안녕하세요!\n무엇을 도와드릴까요?",
                    style = MaterialTheme.typography.headlineMedium,
                    color = Color.White
                )
                Text(
                    text = "증상은 한 번만 알려주세요.\n상담과 방문까지 이어서 도와드려요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.86f)
                )
            }
            Image(
                painter = painterResource(R.drawable.mascot_water_dealer),
                contentDescription = "정수기 딜러 마스코트",
                modifier = Modifier.size(148.dp),
                contentScale = ContentScale.Fit
            )
        }
    }
}

@Composable
private fun HomeActionCard(
    icon: String,
    title: String,
    description: String,
    containerColor: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(Color.White.copy(alpha = 0.75f), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(icon, style = MaterialTheme.typography.titleLarge)
            }
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = contentColor
            )
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = contentColor.copy(alpha = 0.72f)
            )
        }
    }
}

@Composable
fun QrScanScreen(
    onBack: () -> Unit,
    onErrorFound: () -> Unit,
    onQuestionnaireRequired: () -> Unit
) {
    val context = LocalContext.current
    val options = remember {
        GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .enableAutoZoom()
            .build()
    }
    val scanner = remember(context, options) {
        GmsBarcodeScanning.getClient(context, options)
    }

    var scanning by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var lastRawValue by remember { mutableStateOf<String?>(null) }

    fun handleQr(rawValue: String) {
        lastRawValue = rawValue
        errorMessage = null
        val hasErrorCode = AppStateStore.applyQrResult(rawValue)
        if (hasErrorCode) onErrorFound() else onQuestionnaireRequired()
    }

    WaterCareScaffold(title = "QR 오류 확인", onBack = onBack) { modifier ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            StepHeader(
                current = 1,
                total = 3,
                title = "정수기 QR을 촬영해 주세요",
                description = "제품과 오류코드를 자동으로 확인합니다."
            )

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(280.dp)
                    .background(Color(0xFF101827), RoundedCornerShape(28.dp))
                    .padding(20.dp),
                contentAlignment = Alignment.Center
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .border(
                            width = 2.dp,
                            color = Color.White.copy(alpha = 0.8f),
                            shape = RoundedCornerShape(26.dp)
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text("▦", color = Color.White, style = MaterialTheme.typography.headlineMedium)
                        Text(
                            "QR을 프레임 안에 맞춰주세요",
                            color = Color.White,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            "자동으로 인식됩니다",
                            color = Color.White.copy(alpha = 0.7f),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }

            Button(
                onClick = {
                    scanning = true
                    errorMessage = null
                    scanner.startScan()
                        .addOnSuccessListener { barcode ->
                            scanning = false
                            val rawValue = barcode.rawValue
                            if (rawValue.isNullOrBlank()) {
                                errorMessage = "QR 내용을 읽지 못했습니다."
                            } else {
                                handleQr(rawValue)
                            }
                        }
                        .addOnCanceledListener {
                            scanning = false
                        }
                        .addOnFailureListener { throwable ->
                            scanning = false
                            errorMessage = throwable.message ?: "QR 스캔을 시작하지 못했습니다."
                        }
                },
                enabled = !scanning,
                modifier = Modifier.fillMaxWidth()
            ) {
                if (scanning) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                    Text("  카메라 여는 중")
                } else {
                    Text("카메라로 QR 촬영")
                }
            }

            OutlinedButton(
                onClick = {
                    handleQr("product_code=WPUJAC104DWH;error_code=E01")
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("발표용 샘플 QR 실행")
            }

            SectionCard(title = "인식 후 진행", icon = "✓") {
                Text(
                    "오류코드가 확인되면 안전 안내 화면으로 이동합니다.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "오류코드가 없으면 문진을 이어서 작성합니다.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            errorMessage?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            lastRawValue?.let {
                Text(
                    text = "최근 인식값: $it",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun QuestionnaireScreen(
    onBack: () -> Unit,
    onErrorFound: () -> Unit
) {
    val symptoms = listOf(
        "출수량 저하",
        "제품 누수",
        "냉·온수 온도 이상",
        "물맛·냄새 이상",
        "기타"
    )
    var selectedSymptom by remember { mutableStateOf("출수량 저하") }
    var description by remember {
        mutableStateOf("정수 물줄기가 평소보다 약하고 한 컵 받는 시간이 길어졌습니다.")
    }
    var hasLeak by remember { mutableStateOf(false) }
    var hasErrorDisplay by remember { mutableStateOf(false) }

    WaterCareScaffold(title = "고객 문진", onBack = onBack) { modifier ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            StepHeader(
                current = 1,
                total = 3,
                title = "어떤 증상이 있나요?",
                description = "입력한 내용은 상담사와 방문기사에게 그대로 전달됩니다."
            )

            MascotMessage("정확하지 않아도 괜찮아요. 고객님이 느낀 그대로 알려주세요.")

            SectionCard(title = "대표 증상", icon = "●") {
                Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    symptoms.chunked(2).forEach { rowItems ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            rowItems.forEach { symptom ->
                                FilterChip(
                                    selected = selectedSymptom == symptom,
                                    onClick = { selectedSymptom = symptom },
                                    label = { Text(symptom) },
                                    modifier = Modifier.weight(1f)
                                )
                            }
                            if (rowItems.size == 1) {
                                Spacer(Modifier.weight(1f))
                            }
                        }
                    }
                }
            }

            SectionCard(title = "상세 설명", icon = "✎") {
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("증상을 자세히 알려주세요") },
                    supportingText = {
                        Text("언제부터, 어떤 상황에서 발생했는지 작성해 주세요.")
                    },
                    minLines = 5,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(18.dp)
                )
                Text(
                    text = "${description.length}자 입력",
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.End,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            SectionCard(
                title = "안전 확인",
                icon = "!",
                containerColor = SoftWarning
            ) {
                SafetyCheckRow(
                    checked = hasLeak,
                    text = "제품 주변에 물이 고이거나 누수가 있습니다.",
                    onCheckedChange = { hasLeak = it }
                )
                Spacer(Modifier.height(4.dp))
                SafetyCheckRow(
                    checked = hasErrorDisplay,
                    text = "표시창에 오류 문구가 나타납니다.",
                    onCheckedChange = { hasErrorDisplay = it }
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "누수·전기 이상이 있으면 제품 사용을 중지해 주세요.",
                    color = WarningText,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }

            Button(
                onClick = {
                    AppStateStore.applyQuestionnaire(
                        symptom = selectedSymptom,
                        description = description,
                        hasLeak = hasLeak,
                        hasErrorDisplay = hasErrorDisplay
                    )
                    onErrorFound()
                },
                enabled = description.isNotBlank(),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("문진 제출하고 결과 확인")
            }
        }
    }
}

@Composable
private fun SafetyCheckRow(
    checked: Boolean,
    text: String,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Checkbox(checked = checked, onCheckedChange = onCheckedChange)
        Text(
            text = text,
            modifier = Modifier.weight(1f),
            color = WarningText
        )
    }
}

@Composable
fun ErrorResultScreen(
    onBack: () -> Unit,
    onVisitRequested: () -> Unit
) {
    val inquiry by AppStateStore.inquiry.collectAsState()
    val result = inquiry.detection

    WaterCareScaffold(title = "오류 확인 결과", onBack = onBack) { modifier ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            StepHeader(
                current = 2,
                total = 3,
                title = "확인 결과를 안내해 드릴게요",
                description = "공식 근거와 안전 안내를 먼저 확인해 주세요."
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(28.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Column(
                    modifier = Modifier.padding(22.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(52.dp)
                                .background(Color.White.copy(alpha = 0.85f), CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("!", style = MaterialTheme.typography.headlineSmall)
                        }
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .padding(start = 14.dp)
                        ) {
                            Text(
                                text = result.errorName,
                                style = MaterialTheme.typography.headlineSmall,
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                            Text(
                                text = result.errorCode?.let { "오류 코드 $it" }
                                    ?: "문진 기반 증상 확인",
                                color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.72f)
                            )
                        }
                        StatusPill(
                            text = "점검 필요",
                            color = MaterialTheme.colorScheme.primary,
                            backgroundColor = Color.White.copy(alpha = 0.8f)
                        )
                    }
                    HorizontalDivider(
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                    )
                    Text(
                        result.symptomSummary,
                        color = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
            }

            SectionCard(title = "확인 정보", icon = "✓") {
                InfoRow("접수 방식", entryModeLabel(result.entryMode))
                Spacer(Modifier.height(8.dp))
                InfoRow("제품 코드", result.productCode)
                Spacer(Modifier.height(8.dp))
                InfoRow("방문 필요", if (result.requiresVisit) "필요" else "검토 중")
            }

            SectionCard(
                title = "현재 사용 안내",
                icon = "!",
                containerColor = SoftWarning
            ) {
                Text(
                    "방문 점검 전까지 이상이 있는 기능 사용을 줄여주세요.",
                    color = WarningText,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "누수, 타는 냄새, 전기 이상이 있으면 제품 전체 사용을 중지하고 상담을 우선해 주세요.",
                    color = WarningText
                )
            }

            SectionCard(title = "공식 근거", icon = "▤") {
                InfoRow("문서", "WPU-JAC104D 공식 사용설명서")
                Spacer(Modifier.height(8.dp))
                InfoRow("적용 제품", "WPU-JAC104D")
                Spacer(Modifier.height(8.dp))
                InfoRow("검증 상태", "검증 완료", valueColor = SuccessGreen)
                Spacer(Modifier.height(12.dp))
                Text(
                    "AI 안내와 공식 문서 근거를 구분하여 제공합니다.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Button(
                onClick = {
                    AppStateStore.requestVisit()
                    TrackingRepository.prepareVisit()
                    onVisitRequested()
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("방문기사 요청")
            }
        }
    }
}

@Composable
fun VisitStatusScreen(
    onBack: () -> Unit,
    onTracking: () -> Unit
) {
    val inquiry by AppStateStore.inquiry.collectAsState()
    val tracking by TrackingRepository.snapshot.collectAsState()

    WaterCareScaffold(title = "방문 접수 현황", onBack = onBack) { modifier ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            StepHeader(
                current = 3,
                total = 3,
                title = "방문 접수가 완료됐어요",
                description = "담당 기사와 다음 진행 단계를 확인해 주세요."
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(28.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 20.dp, top = 16.dp, end = 8.dp, bottom = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(7.dp)
                    ) {
                        StatusPill(
                            text = "방문 일정 확정",
                            color = HeroTeal,
                            backgroundColor = Color.White.copy(alpha = 0.75f)
                        )
                        Text(
                            "김정수 기사님이\n방문할 예정입니다.",
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.onSecondaryContainer
                        )
                        Text(
                            "기사 출발 후 실시간 이동 화면으로 전환됩니다.",
                            color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.72f)
                        )
                    }
                    Image(
                        painter = painterResource(R.drawable.mascot_water_dealer),
                        contentDescription = "방문기사 캐릭터",
                        modifier = Modifier.size(130.dp),
                        contentScale = ContentScale.Fit
                    )
                }
            }

            SectionCard(title = "접수 정보", icon = "✓") {
                InfoRow("문의 번호", inquiry.inquiryId)
                Spacer(Modifier.height(8.dp))
                InfoRow("방문 번호", tracking.visitId)
                Spacer(Modifier.height(8.dp))
                InfoRow("오류 유형", inquiry.detection.errorName)
            }

            SectionCard(title = "담당 방문기사", icon = "👨") {
                Text(
                    tracking.technicianName,
                    style = MaterialTheme.typography.titleLarge
                )
                Text(
                    tracking.technicianPhoneMasked,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(14.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Spacer(Modifier.height(14.dp))
                VisitTimeline()
            }

            Button(
                onClick = onTracking,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = HeroTeal)
            ) {
                Text("기사 출발 및 위치 확인")
            }
        }
    }
}

@Composable
private fun VisitTimeline() {
    val steps = listOf(
        "접수 완료" to true,
        "기사 배정" to true,
        "방문 예정" to false
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        steps.forEachIndexed { index, (label, completed) ->
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(34.dp)
                        .background(
                            if (completed) HeroTeal else MaterialTheme.colorScheme.surfaceVariant,
                            CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        if (completed) "✓" else "${index + 1}",
                        color = if (completed) Color.White
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = FontWeight.Bold
                    )
                }
                Text(
                    label,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (completed) HeroTeal
                    else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun CustomerTrackingScreen(onBack: () -> Unit) {
    val tracking by TrackingRepository.snapshot.collectAsState()
    val roadRoute by TrackingRepository.route.collectAsState()

    val useKakaoMap = KakaoMapRuntime.isReady
    val coroutineScope = rememberCoroutineScope()

    var isRouteLoading by remember { mutableStateOf(false) }
    var routeStartRequest by remember { mutableStateOf(0) }
    var actionError by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        /*
         * 화면 진입 시 기사 배정 상태까지만 준비한다.
         * 콜 수락과 경로 요청은 사용자가 실제 버튼을 눌렀을 때 실행한다.
         */
        TrackingRepository.prepareVisit()
    }

    LaunchedEffect(routeStartRequest) {
        if (routeStartRequest <= 0) return@LaunchedEffect

        val trackingStarted = TrackingRepository.startDemoTracking()

        if (!trackingStarted) {
            actionError =
                TrackingRepository.snapshot.value.locationRejectedReason
                    ?: "도로 경로가 준비되지 않아 이동을 시작하지 못했습니다."
            return@LaunchedEffect
        }

        while (true) {
            delay(
                TrackingRepository
                    .nextDemoDelayMillis()
                    .milliseconds
            )

            val hasNext =
                TrackingRepository.advanceDemoTracking()

            if (!hasNext) break
        }
    }

    LaunchedEffect(Unit) {
        while (true) {
            delay(1_000.milliseconds)
            TrackingRepository.refreshTrackingHealth()
        }
    }

    fun requestRoadRoute(
        acceptCallFirst: Boolean
    ) {
        if (isRouteLoading) return

        coroutineScope.launch {
            isRouteLoading = true
            actionError = null

            if (acceptCallFirst) {
                TrackingRepository.acceptCall()
            } else {
                TrackingRepository.beginRouteRetry()
            }

            val routeLoaded =
                TrackingRepository.loadRoadRoute()

            if (routeLoaded) {
                /*
                 * 같은 값으로는 LaunchedEffect가 다시 실행되지 않으므로
                 * 성공할 때마다 요청 번호를 증가시킨다.
                 */
                routeStartRequest += 1
            } else {
                actionError =
                    TrackingRepository.snapshot.value.locationRejectedReason
                        ?: "도로 경로를 불러오지 못했습니다."
            }

            isRouteLoading = false
        }
    }

    WaterCareScaffold(
        title = "방문기사 이동 현황",
        onBack = onBack
    ) { modifier ->
        Column(
            modifier = modifier.fillMaxSize()
        ) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                if (useKakaoMap) {
                    KakaoTrackingMap(
                        route = roadRoute,
                        technician = tracking.technicianLocation,
                        customer = tracking.customerLocation,
                        travelMode = tracking.travelMode,
                        headingDegrees = tracking.headingDegrees,
                        autoFollow = true,
                        routeRecalculating =
                            tracking.routeRecalculating,
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    DemoTrackingMap(
                        route = roadRoute,
                        technician = tracking.technicianLocation,
                        customer = tracking.customerLocation,
                        travelMode = tracking.travelMode,
                        modifier = Modifier.fillMaxSize()
                    )
                }

                Row(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .fillMaxWidth()
                        .padding(14.dp),
                    horizontalArrangement =
                        Arrangement.SpaceBetween,
                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    StatusPill(
                        text = if (useKakaoMap) {
                            "실제 카카오맵"
                        } else {
                            "시연 지도"
                        },
                        color = if (useKakaoMap) {
                            SuccessGreen
                        } else {
                            HeroBlue
                        },
                        backgroundColor =
                            Color.White.copy(alpha = 0.94f)
                    )

                    StatusPill(
                        text = when {
                            isRouteLoading ->
                                "경로 확인 중"
                            roadRoute.size < 2 &&
                                tracking.locationRejectedReason != null ->
                                "경로 오류"
                            tracking.status ==
                                VisitScheduleStatus.ARRIVED ->
                                "도착 완료"
                            tracking.routeRecalculating ->
                                "경로 재탐색"
                            tracking.travelMode ==
                                TravelMode.DRIVING &&
                                tracking.connectionState ==
                                TrackingConnectionState.LIVE ->
                                "🚙 차량 이동 중"
                            tracking.travelMode ==
                                TravelMode.WALKING &&
                                tracking.connectionState ==
                                TrackingConnectionState.LIVE ->
                                "도보 이동 중"
                            tracking.connectionState ==
                                TrackingConnectionState.LIVE ->
                                "● LIVE"
                            tracking.connectionState ==
                                TrackingConnectionState.STALE ->
                                "위치 지연"
                            tracking.connectionState ==
                                TrackingConnectionState.OFFLINE ->
                                "연결 끊김"
                            tracking.callAccepted ->
                                "콜 수락"
                            else ->
                                "콜 대기"
                        },
                        color = when {
                            isRouteLoading ->
                                HeroBlue
                            roadRoute.size < 2 &&
                                tracking.locationRejectedReason != null ->
                                MaterialTheme.colorScheme.error
                            tracking.connectionState ==
                                TrackingConnectionState.LIVE ->
                                SuccessGreen
                            tracking.connectionState ==
                                TrackingConnectionState.STALE ->
                                WarningText
                            tracking.connectionState ==
                                TrackingConnectionState.OFFLINE ->
                                MaterialTheme.colorScheme.error
                            else ->
                                HeroBlue
                        },
                        backgroundColor =
                            Color.White.copy(alpha = 0.94f)
                    )
                }
            }

            TrackingBottomCard(
                status = tracking.status,
                travelMode = tracking.travelMode,
                technicianName = tracking.technicianName,
                remainingDistanceMeters =
                    tracking.remainingDistanceMeters,
                etaMinutes = tracking.etaMinutes,
                lastUpdatedLabel =
                    tracking.lastUpdatedLabel,
                callAccepted = tracking.callAccepted,
                isLive = tracking.isLive,
                routeProgress = tracking.routeProgress,
                speedKph = tracking.speedKph,
                locationAccuracyMeters =
                    tracking.locationAccuracyMeters,
                vehicleNumberMasked =
                    tracking.vehicleNumberMasked,
                connectionState =
                    tracking.connectionState,
                locationSignalStatus =
                    tracking.locationSignalStatus,
                staleSeconds = tracking.staleSeconds,
                routeDeviationMeters =
                    tracking.routeDeviationMeters,
                routeRecalculating =
                    tracking.routeRecalculating,
                locationRejectedReason =
                    actionError
                        ?: tracking.locationRejectedReason,
                routeReady = roadRoute.size >= 2,
                isRouteLoading = isRouteLoading,
                onAcceptCall = {
                    requestRoadRoute(
                        acceptCallFirst = true
                    )
                },
                onRetryRoute = {
                    requestRoadRoute(
                        acceptCallFirst = false
                    )
                }
            )
        }
    }
}

@Composable
private fun TrackingBottomCard(
    status: VisitScheduleStatus,
    travelMode: TravelMode,
    technicianName: String,
    remainingDistanceMeters: Int,
    etaMinutes: Int,
    lastUpdatedLabel: String,
    callAccepted: Boolean,
    isLive: Boolean,
    routeProgress: Float,
    speedKph: Int,
    locationAccuracyMeters: Int,
    vehicleNumberMasked: String,
    connectionState: TrackingConnectionState,
    locationSignalStatus: LocationSignalStatus,
    staleSeconds: Int,
    routeDeviationMeters: Int,
    routeRecalculating: Boolean,
    locationRejectedReason: String?,
    routeReady: Boolean,
    isRouteLoading: Boolean,
    onAcceptCall: () -> Unit,
    onRetryRoute: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = 12.dp,
                vertical = 12.dp
            ),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(
            containerColor =
                MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 4.dp
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement =
                Arrangement.spacedBy(13.dp)
        ) {
            Row(
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(52.dp)
                        .background(
                            MaterialTheme
                                .colorScheme
                                .primaryContainer,
                            CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Image(
                        painter = painterResource(
                            trackingMarkerResource(
                                travelMode
                            )
                        ),
                        contentDescription = when (
                            travelMode
                        ) {
                            TravelMode.DRIVING ->
                                "차량으로 이동 중인 방문기사"
                            TravelMode.WALKING ->
                                "도보로 이동 중인 방문기사"
                            TravelMode.ARRIVED ->
                                "도착한 방문기사"
                            TravelMode.WAITING ->
                                "출발 준비 중인 방문기사"
                        },
                        modifier = Modifier.size(
                            if (
                                travelMode ==
                                TravelMode.DRIVING
                            ) {
                                44.dp
                            } else {
                                48.dp
                            }
                        )
                    )
                }

                Column(
                    modifier = Modifier
                        .weight(1f)
                        .padding(start = 12.dp)
                ) {
                    Text(
                        text = trackingTitle(
                            status,
                            travelMode
                        ),
                        style =
                            MaterialTheme
                                .typography
                                .titleMedium
                    )

                    Text(
                        text = when {
                            status ==
                                VisitScheduleStatus.ARRIVED ->
                                "$technicianName · 고객님 댁에 도착"
                            callAccepted ->
                                "$technicianName · $vehicleNumberMasked"
                            else ->
                                "$technicianName · 콜 수락 대기"
                        },
                        color =
                            MaterialTheme
                                .colorScheme
                                .onSurfaceVariant
                    )
                }

                StatusPill(
                    text = when {
                        isRouteLoading ->
                            "확인 중"
                        etaMinutes == 0 &&
                            status ==
                            VisitScheduleStatus.ARRIVED ->
                            "도착"
                        etaMinutes > 0 ->
                            "${etaMinutes}분"
                        else ->
                            "대기"
                    },
                    color = if (
                        status ==
                        VisitScheduleStatus.ARRIVED
                    ) {
                        SuccessGreen
                    } else {
                        HeroBlue
                    }
                )
            }

            LinearProgressIndicator(
                progress = {
                    routeProgress.coerceIn(
                        0f,
                        1f
                    )
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(
                        RoundedCornerShape(100.dp)
                    ),
                color = HeroTeal,
                trackColor =
                    MaterialTheme
                        .colorScheme
                        .surfaceVariant
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {
                TrackingMetric(
                    label = "남은 거리",
                    value = if (routeReady) {
                        distanceLabel(
                            remainingDistanceMeters
                        )
                    } else {
                        "경로 확인 전"
                    },
                    modifier = Modifier.weight(1f)
                )

                TrackingMetric(
                    label = "예상 도착",
                    value = when {
                        status ==
                            VisitScheduleStatus.ARRIVED ->
                            "도착 완료"
                        routeReady &&
                            etaMinutes > 0 ->
                            "${etaMinutes}분"
                        else ->
                            "확인 전"
                    },
                    modifier = Modifier.weight(1f)
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {
                TrackingMetric(
                    label = "현재 속도",
                    value = if (
                        travelMode ==
                        TravelMode.ARRIVED
                    ) {
                        "정차"
                    } else {
                        "${speedKph}km/h"
                    },
                    modifier = Modifier.weight(1f)
                )

                TrackingMetric(
                    label = "GPS 정확도",
                    value = if (
                        locationAccuracyMeters > 0
                    ) {
                        "±${locationAccuracyMeters}m"
                    } else {
                        "확인 중"
                    },
                    modifier = Modifier.weight(1f)
                )
            }

            if (routeRecalculating) {
                Text(
                    text =
                        "기사가 예정 경로를 벗어나 새 경로를 계산하고 있습니다.",
                    style =
                        MaterialTheme
                            .typography
                            .bodyMedium,
                    color = HeroBlue,
                    fontWeight =
                        FontWeight.SemiBold
                )
            }

            if (
                routeDeviationMeters >= 40 &&
                !routeRecalculating
            ) {
                Text(
                    text =
                        "예정 경로와 약 ${routeDeviationMeters}m 차이가 있습니다.",
                    style =
                        MaterialTheme
                            .typography
                            .bodyMedium,
                    color = WarningText
                )
            }

            locationRejectedReason?.let { reason ->
                Text(
                    text = reason,
                    style =
                        MaterialTheme
                            .typography
                            .bodyMedium,
                    color =
                        MaterialTheme
                            .colorScheme
                            .error
                )
            }

            Text(
                text = when {
                    isRouteLoading ->
                        "실제 자동차 도로 경로를 확인하고 있습니다."
                    status ==
                        VisitScheduleStatus.ARRIVED ->
                        "기사님이 도착했습니다. 잠시만 기다려 주세요."
                    connectionState ==
                        TrackingConnectionState.OFFLINE &&
                        callAccepted ->
                        "경로 연결에 실패했습니다. 아래 버튼으로 다시 시도해 주세요."
                    connectionState ==
                        TrackingConnectionState.STALE ->
                        "최근 위치 갱신이 ${staleSeconds}초 지연되고 있습니다."
                    travelMode == TravelMode.DRIVING &&
                        isLive ->
                        "실제 차량이 도로 경로를 따라 이동 중 · " +
                            "현재 ${speedKph}km/h · 최근 갱신 $lastUpdatedLabel"
                    travelMode == TravelMode.WALKING &&
                        isLive ->
                        "기사님이 차량에서 내려 고객님 댁으로 이동 중입니다."
                    isLive ->
                        "실시간 위치 수신 중 · 최근 갱신 $lastUpdatedLabel · " +
                            signalStatusLabel(
                                locationSignalStatus
                            )
                    callAccepted &&
                        routeReady ->
                        "기사님이 콜을 수락하고 이동을 시작했습니다."
                    callAccepted ->
                        "콜 수락 완료 · 실제 도로 경로를 확인해 주세요."
                    else ->
                        "기사님이 콜을 수락하면 실제 이동 경로가 표시됩니다."
                },
                style =
                    MaterialTheme
                        .typography
                        .bodyMedium,
                color =
                    MaterialTheme
                        .colorScheme
                        .onSurfaceVariant
            )

            when {
                !callAccepted -> {
                    Button(
                        onClick = onAcceptCall,
                        enabled = !isRouteLoading,
                        modifier =
                            Modifier.fillMaxWidth(),
                        colors =
                            ButtonDefaults.buttonColors(
                                containerColor =
                                    HeroTeal
                            )
                    ) {
                        if (isRouteLoading) {
                            CircularProgressIndicator(
                                modifier =
                                    Modifier.size(20.dp),
                                strokeWidth = 2.dp,
                                color =
                                    MaterialTheme
                                        .colorScheme
                                        .onPrimary
                            )
                            Text("  콜 수락 처리 중")
                        } else {
                            Text("기사 콜 수락")
                        }
                    }
                }

                !routeReady -> {
                    Button(
                        onClick = onRetryRoute,
                        enabled = !isRouteLoading,
                        modifier =
                            Modifier.fillMaxWidth()
                    ) {
                        if (isRouteLoading) {
                            CircularProgressIndicator(
                                modifier =
                                    Modifier.size(20.dp),
                                strokeWidth = 2.dp,
                                color =
                                    MaterialTheme
                                        .colorScheme
                                        .onPrimary
                            )
                            Text("  경로 불러오는 중")
                        } else {
                            Text("실제 도로 경로 다시 불러오기")
                        }
                    }
                }

                status !=
                    VisitScheduleStatus.ARRIVED -> {
                    OutlinedButton(
                        onClick = onRetryRoute,
                        enabled =
                            !isRouteLoading &&
                                !routeRecalculating,
                        modifier =
                            Modifier.fillMaxWidth()
                    ) {
                        Text("경로 새로고침")
                    }
                }
            }
        }
    }
}

@Composable
private fun TrackingMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(18.dp))
            .padding(horizontal = 14.dp, vertical = 12.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(
                label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                value,
                style = MaterialTheme.typography.titleMedium
            )
        }
    }
}

private fun entryModeLabel(entryMode: InquiryEntryMode): String = when (entryMode) {
    InquiryEntryMode.QR_SCAN -> "QR 촬영"
    InquiryEntryMode.QUESTIONNAIRE -> "고객 문진"
}

private fun trackingMarkerResource(travelMode: TravelMode): Int = when (travelMode) {
    TravelMode.DRIVING -> R.drawable.ic_marker_vehicle_driving
    TravelMode.WAITING,
    TravelMode.WALKING,
    TravelMode.ARRIVED -> R.drawable.ic_marker_technician
}



private fun signalStatusLabel(
    status: LocationSignalStatus
): String = when (status) {
    LocationSignalStatus.EXCELLENT -> "GPS 매우 좋음"
    LocationSignalStatus.GOOD -> "GPS 양호"
    LocationSignalStatus.WEAK -> "GPS 약함"
    LocationSignalStatus.REJECTED -> "GPS 보정 중"
}

private fun trackingTitle(
    status: VisitScheduleStatus,
    travelMode: TravelMode
): String = when {
    status == VisitScheduleStatus.IN_PROGRESS -> "제품을 점검하고 있습니다"
    status == VisitScheduleStatus.ARRIVED -> "기사님이 도착했습니다"
    travelMode == TravelMode.WALKING -> "고객님 댁으로 걸어가고 있어요"
    travelMode == TravelMode.DRIVING -> "기사님이 차량으로 이동 중이에요"
    else -> "방문 일정이 확정되었습니다"
}

private fun distanceLabel(distanceMeters: Int): String =
    if (distanceMeters >= 1_000) {
        String.format(Locale.KOREA, "%.1fkm", distanceMeters / 1_000.0)
    } else {
        "${distanceMeters}m"
    }

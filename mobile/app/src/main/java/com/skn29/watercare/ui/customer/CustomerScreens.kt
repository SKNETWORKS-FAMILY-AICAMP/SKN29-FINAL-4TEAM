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
import androidx.compose.material3.Surface
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
    val inquiry by
        AppStateStore.inquiry.collectAsState()

    WaterCareScaffold(
        title = "정수기 딜러"
    ) { modifier ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .background(Color(0xFFF5F9FA))
                .verticalScroll(
                    rememberScrollState()
                )
                .padding(
                    horizontal = 16.dp,
                    vertical = 12.dp
                ),
            verticalArrangement =
                Arrangement.spacedBy(16.dp)
        ) {
            CustomerHeroCard()

            Text(
                text = "무엇을 도와드릴까요?",
                style =
                    MaterialTheme.typography
                        .titleLarge,
                fontWeight = FontWeight.Bold
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {
                CustomerQuickAction(
                    icon = "✍️",
                    title = "문진 작성",
                    description = "증상 입력",
                    accent = Color(0xFF00A99D),
                    modifier = Modifier.weight(1f),
                    onClick = onQuestionnaire
                )

                CustomerQuickAction(
                    icon = "▦",
                    title = "QR 확인",
                    description = "제품 확인",
                    accent = Color(0xFF1677E8),
                    modifier = Modifier.weight(1f),
                    onClick = onQrScan
                )

                CustomerQuickAction(
                    icon = "🚙",
                    title = "방문 현황",
                    description = "기사 위치",
                    accent = Color(0xFF6A5AE0),
                    modifier = Modifier.weight(1f),
                    onClick = onOpenVisit
                )
            }

            CustomerServiceOverview()

            if (
                inquiry.state ==
                InquiryState.VISIT_SCHEDULED
            ) {
                CustomerVisitNowCard(
                    onOpenVisit = onOpenVisit
                )
            } else {
                CustomerCareTipCard()
            }

            Text(
                text =
                    "고객님이 입력한 내용은 상담과 방문까지 " +
                        "안전하게 이어집니다.",
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        top = 2.dp,
                        bottom = 10.dp
                    ),
                textAlign = TextAlign.Center,
                color =
                    MaterialTheme.colorScheme
                        .onSurfaceVariant,
                style =
                    MaterialTheme.typography
                        .bodySmall
            )
        }
    }
}

@Composable
private fun CustomerHeroCard() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(
                RoundedCornerShape(30.dp)
            )
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color(0xFFDDF9F5),
                        Color(0xFFF8FFFF),
                        Color.White
                    )
                )
            )
            .border(
                width = 1.dp,
                color =
                    Color(0xFFBCEDE7),
                shape =
                    RoundedCornerShape(30.dp)
            )
            .padding(
                start = 22.dp,
                top = 22.dp,
                end = 8.dp,
                bottom = 18.dp
            )
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Column(
                modifier =
                    Modifier.weight(1f),
                verticalArrangement =
                    Arrangement.spacedBy(9.dp)
            ) {
                Box(
                    modifier = Modifier
                        .clip(
                            RoundedCornerShape(
                                99.dp
                            )
                        )
                        .background(
                            Color(0xFF00A99D)
                                .copy(
                                    alpha = 0.12f
                                )
                        )
                        .padding(
                            horizontal = 12.dp,
                            vertical = 6.dp
                        )
                ) {
                    Text(
                        text = "고객용 WaterCare",
                        color =
                            Color(0xFF007D75),
                        style =
                            MaterialTheme
                                .typography
                                .labelLarge,
                        fontWeight =
                            FontWeight.Bold
                    )
                }

                Text(
                    text =
                        "깨끗한 물,\n안심되는 관리",
                    style =
                        MaterialTheme.typography
                            .headlineMedium,
                    color =
                        Color(0xFF102A3A),
                    fontWeight =
                        FontWeight.ExtraBold
                )

                Text(
                    text =
                        "정수기 상태부터 방문기사 위치까지\n" +
                            "한눈에 확인하세요.",
                    style =
                        MaterialTheme.typography
                            .bodyMedium,
                    color =
                        Color(0xFF526572)
                )
            }

            Image(
                painter =
                    painterResource(
                        R.drawable
                            .mascot_water_dealer
                    ),
                contentDescription =
                    "WaterCare 물방울 캐릭터",
                modifier =
                    Modifier.size(142.dp),
                contentScale =
                    ContentScale.Fit
            )
        }
    }
}

@Composable
private fun CustomerQuickAction(
    icon: String,
    title: String,
    description: String,
    accent: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier
            .clickable(onClick = onClick),
        shape =
            RoundedCornerShape(22.dp),
        colors =
            CardDefaults.cardColors(
                containerColor = Color.White
            ),
        elevation =
            CardDefaults.cardElevation(
                defaultElevation = 1.dp
            )
    ) {
        Column(
            modifier = Modifier.padding(
                horizontal = 12.dp,
                vertical = 15.dp
            ),
            horizontalAlignment =
                Alignment.CenterHorizontally,
            verticalArrangement =
                Arrangement.spacedBy(7.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(
                        accent.copy(
                            alpha = 0.12f
                        ),
                        CircleShape
                    ),
                contentAlignment =
                    Alignment.Center
            ) {
                Text(
                    text = icon,
                    style =
                        MaterialTheme.typography
                            .titleLarge
                )
            }

            Text(
                text = title,
                color = Color(0xFF162B3A),
                fontWeight = FontWeight.Bold,
                style =
                    MaterialTheme.typography
                        .bodyMedium,
                textAlign = TextAlign.Center
            )

            Text(
                text = description,
                color = Color(0xFF7B8993),
                style =
                    MaterialTheme.typography
                        .bodySmall,
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun CustomerServiceOverview() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape =
            RoundedCornerShape(28.dp),
        colors =
            CardDefaults.cardColors(
                containerColor = Color.White
            ),
        elevation =
            CardDefaults.cardElevation(
                defaultElevation = 1.dp
            )
    ) {
        Column(
            modifier =
                Modifier.padding(20.dp),
            verticalArrangement =
                Arrangement.spacedBy(14.dp)
        ) {
            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.SpaceBetween,
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "서비스 현황",
                        style =
                            MaterialTheme
                                .typography
                                .titleLarge,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Text(
                        text =
                            "내 정수기 관리 정보를 " +
                                "확인하세요.",
                        color =
                            Color(0xFF7B8993),
                        style =
                            MaterialTheme
                                .typography
                                .bodyMedium
                    )
                }

                StatusPill(
                    text = "정상 사용 중",
                    color = SuccessGreen,
                    backgroundColor =
                        Color(0xFFE7F7F0)
                )
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(
                        RoundedCornerShape(
                            22.dp
                        )
                    )
                    .background(
                        Color(0xFFF5F8FA)
                    )
                    .padding(16.dp)
            ) {
                Row(
                    modifier =
                        Modifier.fillMaxWidth(),
                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(58.dp)
                            .background(
                                Color(0xFFDDF4F1),
                                RoundedCornerShape(
                                    18.dp
                                )
                            ),
                        contentAlignment =
                            Alignment.Center
                    ) {
                        Text(
                            text = "💧",
                            style =
                                MaterialTheme
                                    .typography
                                    .headlineSmall
                        )
                    }

                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .padding(start = 14.dp),
                        verticalArrangement =
                            Arrangement.spacedBy(
                                3.dp
                            )
                    ) {
                        Text(
                            text =
                                "SK매직 " +
                                    "WPU-JAC104D",
                            style =
                                MaterialTheme
                                    .typography
                                    .titleMedium,
                            fontWeight =
                                FontWeight.Bold
                        )

                        Text(
                            text =
                                "방문 관리형 · " +
                                    "필터 상태 양호",
                            color =
                                Color(0xFF6C7A86),
                            style =
                                MaterialTheme
                                    .typography
                                    .bodyMedium
                        )
                    }
                }
            }

            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {
                CustomerInfoMetric(
                    label = "최근 케어",
                    value = "6월 12일",
                    modifier =
                        Modifier.weight(1f)
                )

                CustomerInfoMetric(
                    label = "다음 케어",
                    value = "8월 12일",
                    modifier =
                        Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun CustomerInfoMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(
                RoundedCornerShape(18.dp)
            )
            .background(
                Color(0xFFF2F7F8)
            )
            .padding(
                horizontal = 14.dp,
                vertical = 12.dp
            )
    ) {
        Column(
            verticalArrangement =
                Arrangement.spacedBy(4.dp)
        ) {
            Text(
                text = label,
                color = Color(0xFF7A8993),
                style =
                    MaterialTheme.typography
                        .bodySmall
            )

            Text(
                text = value,
                color = Color(0xFF142B3A),
                fontWeight = FontWeight.Bold,
                style =
                    MaterialTheme.typography
                        .titleMedium
            )
        }
    }
}

@Composable
private fun CustomerVisitNowCard(
    onOpenVisit: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape =
            RoundedCornerShape(28.dp),
        colors =
            CardDefaults.cardColors(
                containerColor =
                    Color(0xFF0B7E79)
            )
    ) {
        Column(
            modifier =
                Modifier.padding(20.dp),
            verticalArrangement =
                Arrangement.spacedBy(14.dp)
        ) {
            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.SpaceBetween,
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .clip(
                            RoundedCornerShape(
                                99.dp
                            )
                        )
                        .background(
                            Color.White.copy(
                                alpha = 0.16f
                            )
                        )
                        .padding(
                            horizontal = 11.dp,
                            vertical = 6.dp
                        )
                ) {
                    Text(
                        text = "기사 이동 중",
                        color = Color.White,
                        style =
                            MaterialTheme
                                .typography
                                .labelLarge,
                        fontWeight =
                            FontWeight.Bold
                    )
                }

                Text(
                    text = "LIVE",
                    color =
                        Color(0xFF8DFFF4),
                    fontWeight =
                        FontWeight.ExtraBold
                )
            }

            Text(
                text =
                    "김정수 기사님이\n" +
                        "고객님 댁으로 이동 중이에요",
                color = Color.White,
                style =
                    MaterialTheme.typography
                        .titleLarge,
                fontWeight =
                    FontWeight.ExtraBold
            )

            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {
                CustomerVisitMetric(
                    label = "예상 도착",
                    value = "10:24",
                    modifier =
                        Modifier.weight(1f)
                )

                CustomerVisitMetric(
                    label = "남은 거리",
                    value = "1.2km",
                    modifier =
                        Modifier.weight(1f)
                )

                CustomerVisitMetric(
                    label = "소요 시간",
                    value = "약 7분",
                    modifier =
                        Modifier.weight(1f)
                )
            }

            Button(
                onClick = onOpenVisit,
                modifier =
                    Modifier.fillMaxWidth(),
                colors =
                    ButtonDefaults.buttonColors(
                        containerColor =
                            Color.White,
                        contentColor =
                            Color(0xFF08736E)
                    ),
                shape =
                    RoundedCornerShape(18.dp)
            ) {
                Text(
                    text =
                        "실시간 방문 현황 보기",
                    fontWeight =
                        FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun CustomerVisitMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(
                RoundedCornerShape(17.dp)
            )
            .background(
                Color.White.copy(
                    alpha = 0.12f
                )
            )
            .padding(
                horizontal = 10.dp,
                vertical = 11.dp
            )
    ) {
        Column(
            verticalArrangement =
                Arrangement.spacedBy(3.dp)
        ) {
            Text(
                text = label,
                color =
                    Color.White.copy(
                        alpha = 0.72f
                    ),
                style =
                    MaterialTheme.typography
                        .bodySmall
            )

            Text(
                text = value,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                style =
                    MaterialTheme.typography
                        .titleMedium
            )
        }
    }
}

@Composable
private fun CustomerCareTipCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape =
            RoundedCornerShape(26.dp),
        colors =
            CardDefaults.cardColors(
                containerColor =
                    Color(0xFFEAF7FF)
            )
    ) {
        Row(
            modifier = Modifier.padding(18.dp),
            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .background(
                        Color.White,
                        CircleShape
                    ),
                contentAlignment =
                    Alignment.Center
            ) {
                Text(
                    text = "🛡️",
                    style =
                        MaterialTheme.typography
                            .titleLarge
                )
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 14.dp),
                verticalArrangement =
                    Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = "오늘의 안심 케어",
                    color = Color(0xFF183B56),
                    fontWeight =
                        FontWeight.ExtraBold
                )

                Text(
                    text =
                        "이상 소음·누수·냄새가 있다면 " +
                            "바로 문진을 시작해 주세요.",
                    color = Color(0xFF5C7180),
                    style =
                        MaterialTheme.typography
                            .bodyMedium
                )
            }
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
fun CustomerTrackingScreen(
    onBack: () -> Unit
) {
    val tracking by
        TrackingRepository.snapshot
            .collectAsState()
    val roadRoute by
        TrackingRepository.route
            .collectAsState()

    val useKakaoMap =
        KakaoMapRuntime.isReady
    val coroutineScope =
        rememberCoroutineScope()

    var isRouteLoading by remember {
        mutableStateOf(false)
    }
    var actionError by remember {
        mutableStateOf<String?>(null)
    }

    LaunchedEffect(Unit) {
        while (true) {
            delay(1_000.milliseconds)
            TrackingRepository
                .refreshTrackingHealth()
        }
    }

    fun refreshCustomerStatus() {
        actionError = null
        TrackingRepository
            .refreshTrackingHealth()
    }

    fun refreshRoadRoute() {
        if (isRouteLoading) {
            return
        }

        if (!tracking.callAccepted) {
            actionError =
                "방문기사가 콜을 수락하면 " +
                    "이동 경로가 자동으로 표시됩니다."
            return
        }

        coroutineScope.launch {
            isRouteLoading = true
            actionError = null

            TrackingRepository
                .beginRouteRetry()

            val loaded =
                TrackingRepository
                    .loadRoadRoute()

            if (!loaded) {
                actionError =
                    TrackingRepository
                        .snapshot
                        .value
                        .locationRejectedReason
                        ?: "도로 경로를 불러오지 못했습니다."
            }

            isRouteLoading = false
        }
    }

    WaterCareScaffold(
        title = "방문기사 이동 현황",
        onBack = onBack
    ) { modifier ->
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(
                    Color(0xFFF2F5F7)
                )
        ) {
            /*
             * 배달 추적 앱처럼 지도를 화면 전체 배경으로 사용한다.
             * 정보 카드는 지도 위에 떠 있는 오버레이 형태로 배치한다.
             */
            if (useKakaoMap) {
                KakaoTrackingMap(
                    route = roadRoute,
                    technician =
                        tracking
                            .technicianLocation,
                    customer =
                        tracking
                            .customerLocation,
                    travelMode =
                        tracking.travelMode,
                    headingDegrees =
                        tracking
                            .headingDegrees,
                    autoFollow = true,
                    routeRecalculating =
                        tracking
                            .routeRecalculating,
                    modifier =
                        Modifier.fillMaxSize()
                )
            } else {
                DemoTrackingMap(
                    route = roadRoute.ifEmpty {
                        listOf(
                            tracking
                                .technicianLocation,
                            tracking
                                .customerLocation
                        )
                    },
                    technician =
                        tracking
                            .technicianLocation,
                    customer =
                        tracking
                            .customerLocation,
                    travelMode =
                        tracking.travelMode,
                    modifier =
                        Modifier.fillMaxSize()
                )
            }

            CustomerMapHeadline(
                callAccepted =
                    tracking.callAccepted,
                status = tracking.status,
                etaMinutes =
                    tracking.etaMinutes,
                isRouteLoading =
                    isRouteLoading,
                connectionState =
                    tracking.connectionState,
                modifier = Modifier
                    .align(
                        Alignment.TopCenter
                    )
                    .padding(
                        horizontal = 14.dp,
                        vertical = 12.dp
                    )
            )

            TrackingBottomCard(
                modifier = Modifier
                    .align(
                        Alignment.BottomCenter
                    )
                    .padding(
                        horizontal = 12.dp,
                        vertical = 12.dp
                    ),
                status = tracking.status,
                travelMode =
                    tracking.travelMode,
                technicianName =
                    tracking.technicianName,
                remainingDistanceMeters =
                    tracking
                        .remainingDistanceMeters,
                etaMinutes =
                    tracking.etaMinutes,
                lastUpdatedLabel =
                    tracking.lastUpdatedLabel,
                callAccepted =
                    tracking.callAccepted,
                routeProgress =
                    tracking.routeProgress,
                vehicleNumberMasked =
                    tracking
                        .vehicleNumberMasked,
                connectionState =
                    tracking.connectionState,
                routeRecalculating =
                    tracking
                        .routeRecalculating,
                locationRejectedReason =
                    actionError
                        ?: tracking
                            .locationRejectedReason,
                routeReady =
                    roadRoute.size >= 2,
                isRouteLoading =
                    isRouteLoading,
                onRefreshStatus = {
                    refreshCustomerStatus()
                },
                onRetryRoute = {
                    refreshRoadRoute()
                }
            )
        }
    }
}

@Composable
private fun CustomerMapHeadline(
    callAccepted: Boolean,
    status: VisitScheduleStatus,
    etaMinutes: Int,
    isRouteLoading: Boolean,
    connectionState: TrackingConnectionState,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color =
            Color.White.copy(
                alpha = 0.96f
            ),
        shape =
            RoundedCornerShape(24.dp),
        shadowElevation = 6.dp
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = 18.dp,
                vertical = 15.dp
            ),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Column(
                modifier =
                    Modifier.weight(1f)
            ) {
                Text(
                    text = when {
                        status ==
                            VisitScheduleStatus
                                .ARRIVED ->
                            "기사님이 도착했어요"

                        etaMinutes > 0 &&
                            callAccepted ->
                            "약 ${etaMinutes}분 후 도착해요"

                        callAccepted ->
                            "기사님이 출발을 준비 중이에요"

                        else ->
                            "기사 응답을 기다리고 있어요"
                    },
                    color = Color(0xFF102A3A),
                    style =
                        MaterialTheme.typography
                            .titleLarge,
                    fontWeight =
                        FontWeight.ExtraBold
                )

                Spacer(
                    modifier =
                        Modifier.height(3.dp)
                )

                Text(
                    text = when {
                        isRouteLoading ->
                            "실제 도로 경로를 확인하고 있어요."

                        connectionState ==
                            TrackingConnectionState
                                .LIVE ->
                            "기사 위치가 실시간으로 갱신됩니다."

                        connectionState ==
                            TrackingConnectionState
                                .STALE ->
                            "최근 위치가 조금 늦게 도착하고 있어요."

                        else ->
                            "방문 진행 상태를 확인하고 있습니다."
                    },
                    color = Color(0xFF687987),
                    style =
                        MaterialTheme.typography
                            .bodyMedium
                )
            }

            StatusPill(
                text = when {
                    status ==
                        VisitScheduleStatus
                            .ARRIVED ->
                        "도착"

                    connectionState ==
                        TrackingConnectionState
                            .LIVE ->
                        "LIVE"

                    callAccepted ->
                        "수락 완료"

                    else ->
                        "배정 대기"
                },
                color = when {
                    status ==
                        VisitScheduleStatus
                            .ARRIVED ->
                        SuccessGreen

                    connectionState ==
                        TrackingConnectionState
                            .LIVE ->
                        HeroTeal

                    else ->
                        HeroBlue
                },
                backgroundColor =
                    Color(0xFFF0F6F7)
            )
        }
    }
}

@Composable
private fun TrackingBottomCard(
    modifier: Modifier = Modifier,
    status: VisitScheduleStatus,
    travelMode: TravelMode,
    technicianName: String,
    remainingDistanceMeters: Int,
    etaMinutes: Int,
    lastUpdatedLabel: String,
    callAccepted: Boolean,
    routeProgress: Float,
    vehicleNumberMasked: String,
    connectionState: TrackingConnectionState,
    routeRecalculating: Boolean,
    locationRejectedReason: String?,
    routeReady: Boolean,
    isRouteLoading: Boolean,
    onRefreshStatus: () -> Unit,
    onRetryRoute: () -> Unit
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape =
            RoundedCornerShape(30.dp),
        colors =
            CardDefaults.cardColors(
                containerColor =
                    Color.White.copy(
                        alpha = 0.98f
                    )
            ),
        elevation =
            CardDefaults.cardElevation(
                defaultElevation = 10.dp
            )
    ) {
        Column(
            modifier = Modifier.padding(
                start = 18.dp,
                top = 10.dp,
                end = 18.dp,
                bottom = 16.dp
            ),
            verticalArrangement =
                Arrangement.spacedBy(11.dp)
        ) {
            Box(
                modifier = Modifier
                    .align(
                        Alignment.CenterHorizontally
                    )
                    .size(
                        width = 42.dp,
                        height = 5.dp
                    )
                    .background(
                        Color(0xFFD8DEE3),
                        RoundedCornerShape(
                            99.dp
                        )
                    )
            )

            Row(
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .background(
                            Color(0xFFE4F7F4),
                            CircleShape
                        ),
                    contentAlignment =
                        Alignment.Center
                ) {
                    Image(
                        painter =
                            painterResource(
                                trackingMarkerResource(
                                    travelMode
                                )
                            ),
                        contentDescription =
                            "방문기사 이동 상태",
                        modifier =
                            Modifier.size(40.dp)
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
                        color = Color(0xFF142B3A),
                        style =
                            MaterialTheme.typography
                                .titleMedium,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Text(
                        text = when {
                            callAccepted ->
                                "$technicianName · " +
                                    vehicleNumberMasked

                            else ->
                                "배정된 기사 응답 대기"
                        },
                        color = Color(0xFF74828D),
                        style =
                            MaterialTheme.typography
                                .bodyMedium
                    )
                }

                Text(
                    text = when {
                        status ==
                            VisitScheduleStatus
                                .ARRIVED ->
                            "도착"

                        etaMinutes > 0 ->
                            "${etaMinutes}분"

                        else ->
                            "대기"
                    },
                    color = HeroTeal,
                    style =
                        MaterialTheme.typography
                            .headlineSmall,
                    fontWeight =
                        FontWeight.ExtraBold
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
                    .height(7.dp)
                    .clip(
                        RoundedCornerShape(
                            99.dp
                        )
                    ),
                color = HeroTeal,
                trackColor =
                    Color(0xFFE6EBEE)
            )

            CustomerTrackingStageRow(
                status = status,
                callAccepted = callAccepted
            )

            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(8.dp)
            ) {
                TrackingMetric(
                    label = "남은 거리",
                    value = if (routeReady) {
                        distanceLabel(
                            remainingDistanceMeters
                        )
                    } else {
                        "확인 전"
                    },
                    modifier =
                        Modifier.weight(1f)
                )

                TrackingMetric(
                    label = "예상 도착",
                    value = when {
                        status ==
                            VisitScheduleStatus
                                .ARRIVED ->
                            "도착 완료"

                        etaMinutes > 0 ->
                            "${etaMinutes}분"

                        else ->
                            "확인 전"
                    },
                    modifier =
                        Modifier.weight(1f)
                )

                TrackingMetric(
                    label = "최근 갱신",
                    value =
                        lastUpdatedLabel.take(
                            8
                        ),
                    modifier =
                        Modifier.weight(1f)
                )
            }

            if (routeRecalculating) {
                Text(
                    text =
                        "경로를 벗어나 새로운 길을 찾고 있어요.",
                    color = HeroBlue,
                    fontWeight =
                        FontWeight.SemiBold,
                    style =
                        MaterialTheme.typography
                            .bodyMedium
                )
            }

            locationRejectedReason?.let {
                Text(
                    text = it,
                    color =
                        MaterialTheme
                            .colorScheme
                            .error,
                    style =
                        MaterialTheme.typography
                            .bodySmall
                )
            }

            when {
                !callAccepted -> {
                    Start-Sleep -Seconds 2OutlinedButton(
                        onClick =
                            onRefreshStatus,
                        modifier =
                            Modifier.fillMaxWidth(),
                        shape =
                            RoundedCornerShape(
                                17.dp
                            )
                    ) {
                        Text(
                            "기사 상태 새로고침"
                        )
                    }
                }

                !routeReady -> {
                    Button(
                        onClick = onRetryRoute,
                        enabled =
                            !isRouteLoading,
                        modifier =
                            Modifier.fillMaxWidth(),
                        shape =
                            RoundedCornerShape(
                                17.dp
                            )
                    ) {
                        Text(
                            if (isRouteLoading) {
                                "경로 확인 중"
                            } else {
                                "이동 경로 불러오기"
                            }
                        )
                    }
                }

                connectionState !=
                    TrackingConnectionState
                        .LIVE -> {
                    OutlinedButton(
                        onClick = onRetryRoute,
                        enabled =
                            !isRouteLoading,
                        modifier =
                            Modifier.fillMaxWidth(),
                        shape =
                            RoundedCornerShape(
                                17.dp
                            )
                    ) {
                        Text(
                            "위치·경로 새로고침"
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CustomerTrackingStageRow(
    status: VisitScheduleStatus,
    callAccepted: Boolean
) {
    val currentIndex = when {
        status ==
            VisitScheduleStatus.ARRIVED ||
            status ==
            VisitScheduleStatus.IN_PROGRESS ||
            status ==
            VisitScheduleStatus.COMPLETED ->
            3

        status ==
            VisitScheduleStatus.NEARBY ->
            2

        status ==
            VisitScheduleStatus.EN_ROUTE ->
            1

        callAccepted ->
            0

        else ->
            -1
    }

    val labels = listOf(
        "수락",
        "이동",
        "근처",
        "도착"
    )

    Row(
        modifier =
            Modifier.fillMaxWidth(),
        horizontalArrangement =
            Arrangement.SpaceBetween
    ) {
        labels.forEachIndexed {
                index,
                label ->
            Column(
                horizontalAlignment =
                    Alignment.CenterHorizontally
            ) {
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(
                            if (
                                index <=
                                currentIndex
                            ) {
                                HeroTeal
                            } else {
                                Color(
                                    0xFFDDE3E7
                                )
                            },
                            CircleShape
                        ),
                    contentAlignment =
                        Alignment.Center
                ) {
                    Text(
                        text =
                            if (
                                index <=
                                currentIndex
                            ) {
                                "✓"
                            } else {
                                "${index + 1}"
                            },
                        color =
                            if (
                                index <=
                                currentIndex
                            ) {
                                Color.White
                            } else {
                                Color(
                                    0xFF82909A
                                )
                            },
                        fontWeight =
                            FontWeight.Bold,
                        style =
                            MaterialTheme
                                .typography
                                .labelSmall
                    )
                }

                Spacer(
                    modifier =
                        Modifier.height(3.dp)
                )

                Text(
                    text = label,
                    color =
                        if (
                            index <=
                            currentIndex
                        ) {
                            Color(0xFF166E69)
                        } else {
                            Color(0xFF85929C)
                        },
                    style =
                        MaterialTheme.typography
                            .labelSmall,
                    fontWeight =
                        FontWeight.SemiBold
                )
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

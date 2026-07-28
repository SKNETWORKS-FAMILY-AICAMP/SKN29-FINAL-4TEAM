package com.skn29.watercare.technician.feature.visitresult

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.technician.data.TechnicianDemoData

private enum class VisitOutcome(
    val label: String
) {
    NORMAL("정상 처리"),
    PART_REPLACED("부품 교체"),
    REVISIT("재방문 필요")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitResultScreen(
    visitId: String,
    onBack: () -> Unit,
    onCompleted: () -> Unit
) {
    val visit = TechnicianDemoData.findVisit(visitId)

    var outcome by rememberSaveable {
        mutableStateOf(VisitOutcome.NORMAL)
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
    var showConfirmDialog by rememberSaveable {
        mutableStateOf(false)
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
                    "저장 후 고객 케어 이력에 반영되고 업무 목록으로 이동합니다."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showConfirmDialog = false
                        onCompleted()
                    }
                ) {
                    Text("완료")
                }
            },
            dismissButton = {
                TextButton(
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
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                title = {
                    Text("방문 결과 등록")
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("뒤로")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(
                    start = 18.dp,
                    end = 18.dp,
                    top = 18.dp,
                    bottom = 30.dp
                ),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor =
                        MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(5.dp)
                ) {
                    Text(
                        text = visit?.customerName ?: "고객 정보 없음",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color =
                            MaterialTheme.colorScheme.onPrimaryContainer
                    )
                    Text(
                        text = visit?.let {
                            "${it.productName} · ${it.productCode}"
                        } ?: visitId,
                        style = MaterialTheme.typography.bodyMedium,
                        color =
                            MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
            }

            Text(
                text = "처리 유형",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                VisitOutcome.entries.forEach { item ->
                    FilterChip(
                        selected = outcome == item,
                        onClick = {
                            outcome = item
                        },
                        label = {
                            Text(item.label)
                        }
                    )
                }
            }

            OutlinedTextField(
                value = diagnosis,
                onValueChange = {
                    diagnosis = it
                },
                modifier = Modifier.fillMaxWidth(),
                label = {
                    Text("점검 결과")
                },
                supportingText = {
                    Text("확인된 원인과 상태를 작성해 주세요.")
                },
                minLines = 3
            )

            OutlinedTextField(
                value = actionTaken,
                onValueChange = {
                    actionTaken = it
                },
                modifier = Modifier.fillMaxWidth(),
                label = {
                    Text("수행 조치")
                },
                supportingText = {
                    Text("세척, 조정, 교체 등 수행 내용을 작성해 주세요.")
                },
                minLines = 3
            )

            OutlinedTextField(
                value = partsUsed,
                onValueChange = {
                    partsUsed = it
                },
                modifier = Modifier.fillMaxWidth(),
                label = {
                    Text("사용 또는 교체 부품")
                },
                placeholder = {
                    Text("없음")
                }
            )

            OutlinedTextField(
                value = customerNote,
                onValueChange = {
                    customerNote = it
                },
                modifier = Modifier.fillMaxWidth(),
                label = {
                    Text("고객 안내 및 특이사항")
                },
                minLines = 2
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Checkbox(
                    checked = followUpRequired,
                    onCheckedChange = {
                        followUpRequired = it
                    }
                )
                Column(
                    modifier = Modifier.padding(top = 10.dp)
                ) {
                    Text(
                        text = "후속 확인 필요",
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "재방문 또는 상담사 확인이 필요한 경우 선택",
                        style = MaterialTheme.typography.bodySmall,
                        color =
                            MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Button(
                modifier = Modifier.fillMaxWidth(),
                enabled = diagnosis.isNotBlank() &&
                    actionTaken.isNotBlank(),
                onClick = {
                    showConfirmDialog = true
                }
            ) {
                Text("처리 완료")
            }
        }
    }
}

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateRange(1, 60)]
    [int]$CaseNumber
)

$ErrorActionPreference = 'Stop'
$taskUtf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $taskUtf8
$OutputEncoding = $taskUtf8

$taskRepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$taskGoldPath = Join-Path $taskRepositoryRoot 'ai\evaluation\datasets\gold\rag_gold_v1.jsonl'
$taskPacketPath = Join-Path $taskRepositoryRoot 'data\processed\validation\rag_experiments\gold_v1_post_query_label_revalidation_packet.json'

$taskPacket = Get-Content -Encoding UTF8 -Raw -LiteralPath $taskPacketPath |
    ConvertFrom-Json
$taskActualGoldHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskGoldPath).Hash
if ($taskActualGoldHash -ne $taskPacket.source_dataset.sha256) {
    throw "Gold source hash mismatch. expected=$($taskPacket.source_dataset.sha256) actual=$taskActualGoldHash"
}

$taskCaseId = 'RAGV2-GOLD-{0:D4}' -f $CaseNumber
$taskReview = $taskPacket.reviews |
    Where-Object { $_.case_id -eq $taskCaseId }
if ($null -eq $taskReview) {
    throw "Label revalidation row not found: $taskCaseId"
}

[pscustomobject]@{
    case_id             = $taskReview.case_id
    approved_query      = $taskReview.approved_query
    assessment          = $taskReview.assistant_assessment
    priority            = $taskReview.review_priority
    assistant_reason    = $taskReview.assistant_reason
    human_signoff       = $taskReview.human_signoff_status
} | Format-List

'CURRENT LABELS'
$taskReview.current_labels | ConvertTo-Json -Depth 10

'PROPOSED CHANGES'
if ($taskReview.proposed_changes.Count -eq 0) {
    '(none)'
} else {
    $taskReview.proposed_changes | ConvertTo-Json -Depth 10
}

'REQUIRED HUMAN CHECKS'
$taskReview.required_human_checks | ForEach-Object { "- $_" }

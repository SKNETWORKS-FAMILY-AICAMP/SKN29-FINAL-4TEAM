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
$taskProposalPath = Join-Path $taskRepositoryRoot 'data\config\rag\gold_v1_query_rewrite_proposals.json'

$taskProposalPack = Get-Content -Encoding UTF8 -Raw -LiteralPath $taskProposalPath |
    ConvertFrom-Json
$taskActualGoldHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskGoldPath).Hash
if ($taskActualGoldHash -ne $taskProposalPack.source_dataset.sha256) {
    throw "Gold source hash mismatch. expected=$($taskProposalPack.source_dataset.sha256) actual=$taskActualGoldHash"
}

$taskGoldRow = (Get-Content -Encoding UTF8 -LiteralPath $taskGoldPath)[$CaseNumber - 1] |
    ConvertFrom-Json
$taskProposal = $taskProposalPack.proposals |
    Where-Object { $_.case_id -eq $taskGoldRow.case_id }

if ($null -eq $taskProposal) {
    throw "Case proposal not found: $($taskGoldRow.case_id)"
}

[pscustomobject]@{
    case_id            = $taskGoldRow.case_id
    variant_type       = $taskGoldRow.query_variant_type
    original_query     = $taskGoldRow.query
    proposed_query     = $taskProposal.proposed_query
    rewrite_class      = $taskProposal.rewrite_class
    intent_change      = $taskProposal.intent_change
    review_note        = $taskProposal.review_note
    label_revalidation = 'REQUIRED_AFTER_QUERY_APPROVAL'
    gold_source_status = 'UNMODIFIED'
} | Format-List

'DECISION CODES'
'A = APPROVE PROPOSED QUERY'
'B = REQUEST WORDING CHANGE'
'C = KEEP ORIGINAL QUERY'
'D = PROPOSE QUERY REJECTION'

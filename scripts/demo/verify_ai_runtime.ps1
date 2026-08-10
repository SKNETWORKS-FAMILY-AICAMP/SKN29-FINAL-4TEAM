param(
    [string]$BaseUrl = "http://127.0.0.1:8001",
    [switch]$IncludeLocalRetrieval
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Equal {
    param(
        [object]$Actual,
        [object]$Expected,
        [string]$Label
    )
    if ($Actual -ne $Expected) {
        throw "$Label mismatch: expected=$Expected actual=$Actual"
    }
}

function Invoke-Analysis {
    param(
        [string]$Mode,
        [string]$CorrelationId,
        [object]$Scenario
    )
    $payload = @{
        inquiry_id = "018f2f9b-7c30-7981-b541-1a987c88b450"
        correlation_id = $CorrelationId
        ai_request_id = "ai-$CorrelationId"
        state_version = 1
        raw_symptom = $Scenario.raw_symptom
        model_code = "WPUJAC104DWH"
        selected_symptoms = @($Scenario.selected_symptoms)
        previous_answers = @()
    }
    return Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/v1/ai/analyze?mode=$Mode" `
        -Headers @{ "X-Correlation-ID" = $CorrelationId } `
        -ContentType "application/json; charset=utf-8" `
        -Body ($payload | ConvertTo-Json -Depth 10)
}

$scenarioPath = Join-Path $PSScriptRoot "scenarios.json"
$scenarios = Get-Content -LiteralPath $scenarioPath -Raw -Encoding UTF8 | ConvertFrom-Json

$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/ai/health"
Assert-Equal $health.status "ok" "health.status"
Assert-Equal $health.config_loaded $true "health.config_loaded"

$mock = Invoke-Analysis -Mode "mock" -CorrelationId "demo-mock-001" -Scenario $scenarios.mock
Assert-Equal $mock.correlation_id "demo-mock-001" "mock.correlation_id"
Assert-Equal $mock.status "SUCCEEDED" "mock.status"

$danger = Invoke-Analysis -Mode "local" -CorrelationId "demo-danger-001" -Scenario $scenarios.danger
Assert-Equal $danger.status "SUCCEEDED" "danger.status"
Assert-Equal $danger.safety_assessment.risk_level "danger" "danger.risk_level"
Assert-Equal $danger.usage_guidance.guidance_status "TOTAL_STOP" "danger.guidance_status"

$retrievalStatus = "SKIPPED"
if ($IncludeLocalRetrieval) {
    $retrieval = Invoke-Analysis `
        -Mode "local" `
        -CorrelationId "demo-local-rag-001" `
        -Scenario $scenarios.retrieval
    Assert-Equal $retrieval.correlation_id "demo-local-rag-001" "retrieval.correlation_id"
    if ($retrieval.status -notin @("SUCCEEDED", "FALLBACK")) {
        throw "retrieval.status is not allowed: $($retrieval.status)"
    }
    $retrievalStatus = $retrieval.status
}

[pscustomobject]@{
    health = "PASS"
    mock_contract = "PASS"
    local_danger_without_vector_dependency = "PASS"
    local_retrieval = $retrievalStatus
    base_url = $BaseUrl
}

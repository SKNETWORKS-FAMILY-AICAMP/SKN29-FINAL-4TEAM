param(
    [string]$RepoPath = "C:\skn29\WaterCare",
    [string]$ReportPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = [IO.Path]::GetFullPath($RepoPath)

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path $RepoPath `
        "mobile\build\reports\t057-backend-runtime-capabilities.txt"
}

function Git-Show([string]$Path) {
    $Result = & git -C $RepoPath show "origin/main:$Path" 2>$null
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    return ($Result -join "`n")
}

& git -C $RepoPath fetch origin main | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "origin/main fetch failed."
}

$ApiUrls = Git-Show "backend/config/api_urls.py"
$AccountUrls = Git-Show "backend/apps/accounts/api/urls.py"
$InquiryUrls = Git-Show "backend/apps/inquiries/api/urls.py"

$AllRoutes = @(
    $ApiUrls,
    $AccountUrls,
    $InquiryUrls
) -join "`n"

$Capabilities = @(
    [pscustomobject]@{
        Name = "Auth /me"
        Route = "GET /api/v1/me"
        Available = $AccountUrls.Contains('"me"')
    },
    [pscustomobject]@{
        Name = "Inquiry create"
        Route = "POST /api/v1/inquiries"
        Available = $InquiryUrls.Contains('"inquiries"')
    },
    [pscustomobject]@{
        Name = "Inquiry submit"
        Route = "POST /api/v1/inquiries/{id}/submit"
        Available = $InquiryUrls.Contains('/submit')
    },
    [pscustomobject]@{
        Name = "Inquiry cancel"
        Route = "POST /api/v1/inquiries/{id}/cancel"
        Available = $InquiryUrls.Contains('/cancel')
    },
    [pscustomobject]@{
        Name = "Customer subscriptions"
        Route = "GET /api/v1/me/subscriptions"
        Available = $AllRoutes.Contains('subscriptions')
    },
    [pscustomobject]@{
        Name = "Guidance / evidence"
        Route = "Guidance/Evidence Runtime"
        Available = (
            $AllRoutes.Contains('guidance') -or
            $AllRoutes.Contains('evidence')
        )
    },
    [pscustomobject]@{
        Name = "Consultation request"
        Route = "REQUEST_CONSULTATION Runtime"
        Available = $AllRoutes.Contains('consult')
    },
    [pscustomobject]@{
        Name = "Inquiry detail refresh"
        Route = "GET /api/v1/inquiries/{id}"
        Available = (
            $InquiryUrls -match
            'path\(\s*"inquiries/<uuid:inquiry_id>"\s*,'
        )
    },
    [pscustomobject]@{
        Name = "Technician visits"
        Route = "Technician visit list/detail Runtime"
        Available = (
            $AllRoutes.Contains('visits') -or
            $AllRoutes.Contains('technician')
        )
    }
)

$Lines = @(
    "T-057 Backend Runtime Capability Matrix",
    "Checked origin/main at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    ""
)

foreach ($Capability in $Capabilities) {
    $Status = if ($Capability.Available) {
        "RUNTIME_AVAILABLE"
    } else {
        "BLOCKED_BY_BACKEND"
    }

    $Lines += (
        "$Status | $($Capability.Name) | $($Capability.Route)"
    )
}

$Directory = Split-Path -Parent $ReportPath
New-Item -ItemType Directory -Path $Directory -Force | Out-Null

[IO.File]::WriteAllLines(
    $ReportPath,
    $Lines,
    [Text.UTF8Encoding]::new($false)
)

Write-Host "T057_BACKEND_CAPABILITY_MATRIX_PASS" -ForegroundColor Green
Write-Host "Report: $ReportPath"
$Lines | ForEach-Object { Write-Host $_ }

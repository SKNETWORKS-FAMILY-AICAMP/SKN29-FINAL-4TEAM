param(
    [string]$RepoPath = "C:\skn29\WaterCare"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([Parameter(Mandatory)][string]$Text)

    Write-Host ""
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

$RepoPath = [IO.Path]::GetFullPath($RepoPath)
$MobilePath = Join-Path $RepoPath "mobile"
$GradleWrapper = Join-Path $MobilePath "gradlew.bat"

Write-Section "T-045 strict Gradle verification"

if (-not (Test-Path -LiteralPath $GradleWrapper)) {
    throw "Gradle wrapper not found: $GradleWrapper"
}

$GradleCommand = @(
    "call"
    "gradlew.bat"
    ":core:test"
    ":customer-app:testDebugUnitTest"
    ":customer-app:assembleDebug"
    ":technician-app:testDebugUnitTest"
    ":technician-app:assembleDebug"
    "--no-daemon"
) -join " "

$Process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/d"
        "/s"
        "/c"
        $GradleCommand
    ) `
    -WorkingDirectory $MobilePath `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($Process.ExitCode -ne 0) {
    throw "Gradle verification failed with exit code $($Process.ExitCode)"
}

$CustomerApk = Join-Path $MobilePath `
    "customer-app\build\outputs\apk\debug\customer-app-debug.apk"
$TechnicianApk = Join-Path $MobilePath `
    "technician-app\build\outputs\apk\debug\technician-app-debug.apk"

if (-not (Test-Path -LiteralPath $CustomerApk)) {
    throw "Customer APK not found after successful build: $CustomerApk"
}

if (-not (Test-Path -LiteralPath $TechnicianApk)) {
    throw "Technician APK not found after successful build: $TechnicianApk"
}

Write-Host ""
Write-Host "T045_STRICT_GRADLE_PASS" -ForegroundColor Green
Write-Host "Customer APK: $CustomerApk"
Write-Host "Technician APK: $TechnicianApk"

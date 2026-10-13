<#!
.SYNOPSIS
Installs the MindMesh debug build directly to one USB-connected Android phone.

.DESCRIPTION
Creates ADB reverse tunnels for the website (port 3000) and API (port 8000),
then builds, replaces, and opens the debug app. Run this after each companion
code change while USB debugging is on.
#>

$ErrorActionPreference = "Stop"

$adbCandidates = @(
    "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe",
    "$env:ANDROID_HOME\platform-tools\adb.exe",
    "$env:ANDROID_SDK_ROOT\platform-tools\adb.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if (!$adbCandidates) {
    throw "ADB was not found. Install Android SDK Platform Tools, then reconnect the phone."
}

$adb = @($adbCandidates)[0]
$device = & $adb devices | Select-String "\tdevice$" | Select-Object -First 1
if (!$device) {
    throw "No authorized USB device found. Unlock the phone and accept the USB debugging prompt."
}

& $adb reverse tcp:8000 tcp:8000
if ($LASTEXITCODE -ne 0) { throw "Could not create the phone-to-backend USB tunnel." }
& $adb reverse tcp:3000 tcp:3000
if ($LASTEXITCODE -ne 0) { throw "Could not create the phone-to-website USB tunnel." }

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & .\gradlew.bat --no-daemon --offline installDebug
    if ($LASTEXITCODE -ne 0) { throw "MindMesh Companion could not be installed." }

    & $adb shell am force-stop com.mindmesh.clone.companion
    & $adb shell monkey -p com.mindmesh.clone.companion -c android.intent.category.LAUNCHER 1 | Out-Null
    Write-Host "MindMesh Companion was updated and opened on the connected phone."
} finally {
    Pop-Location
}

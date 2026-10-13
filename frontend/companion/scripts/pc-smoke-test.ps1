#Requires -Version 5.1
<#
.SYNOPSIS
  MindMesh companion smoke test for a real phone driven from the PC.

.DESCRIPTION
  Verifies the whole companion chain without touching the phone's UI by hand:
  device attached, backend reachable, adb reverse bridge, APK installed, app
  launches, share intent fills the draft, save -> status transitions, and the
  "Backend offline" truth state. Screenshots and crash logs land in
  android-companion/artifacts/smoke/<timestamp>/.

  The phone screen itself is mirrored and operated with scrcpy (Option B), so
  sign-in and real share-sheets can also be driven manually while this script
  records evidence.

.EXAMPLE
  .\pc-smoke-test.ps1
  .\pc-smoke-test.ps1 -SkipInstall
  .\pc-smoke-test.ps1 -Email you@example.com -Password 'secret'
  .\pc-smoke-test.ps1 -StopBackend
#>
[CmdletBinding()]
param(
    [string]$Apk,
    [string]$Email,
    [string]$Password,
    [string]$ShareUrl = "https://www.youtube.com/shorts/abc123XYZ90",
    [switch]$SkipInstall,
    [switch]$SkipBackend,
    [switch]$StopBackend
)

$ErrorActionPreference = "Stop"
$Package = "com.mindmesh.clone.companion"
$Activity = "$Package/.MainActivity"
$HealthUrl = "http://127.0.0.1:8000/api/health"

$ScriptDir = $PSScriptRoot
$CompanionRoot = Split-Path -Parent $ScriptDir
$RepoRoot = Split-Path -Parent $CompanionRoot
$BackendDir = Join-Path $RepoRoot "backend"
if (-not $Apk) { $Apk = Join-Path $CompanionRoot "artifacts\MindMesh-native-companion-debug.apk" }

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Artifacts = Join-Path $CompanionRoot "artifacts\smoke\$Stamp"
New-Item -ItemType Directory -Path $Artifacts -Force | Out-Null

$Results = New-Object System.Collections.Generic.List[object]
$script:BackendProc = $null

function Add-Result {
    param([string]$Name, [ValidateSet("PASS", "FAIL", "SKIP", "INFO")][string]$Status, [string]$Detail = "")
    $Results.Add([pscustomobject]@{ Step = $Name; Status = $Status; Detail = $Detail })
    $color = switch ($Status) { "PASS" { "Green" } "FAIL" { "Red" } "SKIP" { "Yellow" } default { "Gray" } }
    Write-Host ("  [{0}] {1}{2}" -f $Status, $Name, $(if ($Detail) { " - $Detail" } else { "" })) -ForegroundColor $color
}

function Resolve-Adb {
    $candidates = @()
    if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe") }
    if ($env:ANDROID_HOME) { $candidates += (Join-Path $env:ANDROID_HOME "platform-tools\adb.exe") }
    if ($env:ANDROID_SDK_ROOT) { $candidates += (Join-Path $env:ANDROID_SDK_ROOT "platform-tools\adb.exe") }
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "adb.exe not found. Install Android SDK platform-tools."
}

function Resolve-Scrcpy {
    $cmd = Get-Command scrcpy -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $winget = Get-ChildItem (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") -Recurse -Filter "scrcpy.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if ($winget) { return $winget }
    return $null
}

function Invoke-Adb {
    # NOTE: deliberately no param() block - a [ValueFromRemainingArguments] string[]
    # parameter makes PowerShell 5.1 deadlock while draining adb's streams.
    # $args forwards every token (including flags like -d / --es) verbatim.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & "$script:Adb" @args } finally { $ErrorActionPreference = $previous }
}

function Get-DeviceState {
    $lines = Invoke-Adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\S" }
    foreach ($line in $lines) {
        $parts = $line -split "\s+"
        if ($parts.Count -ge 2) { return [pscustomobject]@{ Serial = $parts[0]; State = $parts[1] } }
    }
    return $null
}

function Save-Screenshot {
    param([string]$Name)
    $path = Join-Path $Artifacts ("{0}.png" -f $Name)
    cmd /c "`"$script:Adb`" exec-out screencap -p > `"$path`""
    if ((Test-Path $path) -and ((Get-Item $path).Length -gt 1000)) { return $path }
    return $null
}

function Get-UiRaw {
    Invoke-Adb shell uiautomator dump /sdcard/ui.xml | Out-Null
    $raw = (Invoke-Adb shell cat /sdcard/ui.xml 2>$null) -join "`n"
    if ($raw -notmatch "<hierarchy") { return "" }
    return $raw
}

function Get-UiNodes {
    param([string]$Raw)
    if (-not $Raw) { return @() }
    $nodes = @()
    foreach ($m in [regex]::Matches($Raw, '<node\s+([^>]+?)/?>')) {
        $attrs = $m.Groups[1].Value
        $get = {
            param($name)
            if ($attrs -match "(?:^|\s)$name=`"([^`"]*)`"") { return $Matches[1] }
            return ""
        }
        $text = & $get "text"
        $desc = & $get "content-desc"
        $class = & $get "class"
        $bounds = & $get "bounds"
        $bm = [regex]::Match($bounds, "\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
        if (-not $bm.Success) { continue }
        $x1 = [int]$bm.Groups[1].Value; $y1 = [int]$bm.Groups[2].Value
        $x2 = [int]$bm.Groups[3].Value; $y2 = [int]$bm.Groups[4].Value
        $nodes += [pscustomobject]@{
            Text    = $text
            Desc    = $desc
            Class   = $class
            Bounds  = $bounds
            CenterX = [int](($x1 + $x2) / 2)
            CenterY = [int](($y1 + $y2) / 2)
        }
    }
    return $nodes
}

function Find-UiNode {
    param([Parameter(Mandatory = $true)][string]$Pattern, [string]$Raw)
    if (-not $Raw) { $Raw = Get-UiRaw }
    foreach ($n in (Get-UiNodes -Raw $Raw)) {
        if ($n.Text -match $Pattern -or $n.Desc -match $Pattern) { return $n }
    }
    return $null
}

function Invoke-Tap {
    param([int]$X, [int]$Y)
    Invoke-Adb shell input tap $X $Y | Out-Null
    Start-Sleep -Milliseconds 700
}

function Send-AdbText {
    param([string]$Text)
    $escaped = $Text -replace "'", "'\''"
    Invoke-Adb shell "input text '$escaped'" | Out-Null
    Start-Sleep -Milliseconds 400
}

function Wait-UiText {
    param([string]$Pattern, [int]$TimeoutSec = 25)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $raw = Get-UiRaw
        if ($raw -and ($raw -match $Pattern)) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Get-CrashLog {
    $log = (Invoke-Adb logcat -d -s AndroidRuntime:E AndroidRuntime:F 2>$null) -join "`n"
    if ($log -match "FATAL EXCEPTION" -and $log -match [regex]::Escape($Package)) { return $log }
    if ($log -match [regex]::Escape($Package)) { return $log }
    return $null
}

function Test-BackendHealth {
    try {
        $resp = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing
        if ($resp.StatusCode -eq 200) { return $true }
    } catch { }
    return $false
}

function Start-Backend {
    if (Test-BackendHealth) { return $true }
    if (-not (Test-Path (Join-Path $BackendDir "app\main.py"))) { return $false }
    $log = Join-Path $Artifacts "backend.log"
    $script:BackendProc = Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $BackendDir -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -WindowStyle Hidden -PassThru
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-BackendHealth) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Stop-Backend {
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 }
    elseif ($script:BackendProc -and -not $script:BackendProc.HasExited) {
        Stop-Process -Id $script:BackendProc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

function Invoke-ShareIntent {
    param([string]$Url)
    Invoke-Adb shell am start -n $Activity -a "android.intent.action.SEND" -t "text/plain" `
        --es "android.intent.extra.TEXT" $Url | Out-Null
    Start-Sleep -Seconds 3
}

function Get-FieldNodes {
    param([string]$Raw)
    if (-not $Raw) { $Raw = Get-UiRaw }
    return @(Get-UiNodes -Raw $Raw | Where-Object { $_.Class -match "EditText" })
}

Write-Host ""
Write-Host "MindMesh companion smoke test - $Stamp" -ForegroundColor Cyan
Write-Host "artifacts: $Artifacts"
Write-Host ""

# --- 1. preflight ----------------------------------------------------------
Write-Host "1. Preflight" -ForegroundColor Cyan
try { $script:Adb = Resolve-Adb; Add-Result "adb found" "PASS" (Split-Path $script:Adb -Parent) }
catch {
    Add-Result "adb found" "FAIL" $_.Exception.Message
    $Results | Format-Table -AutoSize | Out-String | Write-Host
    exit 1
}

$scrcpy = Resolve-Scrcpy
if ($scrcpy) { Add-Result "scrcpy found" "PASS" $scrcpy } else { Add-Result "scrcpy found" "SKIP" "install: winget install Genymobile.scrcpy" }

if (Test-Path $Apk) {
    $hash = (Get-FileHash -Algorithm SHA256 $Apk).Hash.Substring(0, 12)
    Add-Result "APK present" "PASS" "$(Split-Path $Apk -Leaf) sha256:$hash..."
} else { Add-Result "APK present" "FAIL" $Apk }

$device = Get-DeviceState
if ($device -and $device.State -eq "device") { Add-Result "phone attached" "PASS" $device.Serial }
else {
    $state = if ($device) { $device.State } else { "none" }
    Add-Result "phone attached" "FAIL" "state=$state (check USB cable + authorize debugging on the phone)"
    Write-Host "`nStopping here - connect the phone and re-run." -ForegroundColor Red
    $Results | Format-Table -AutoSize | Out-String | Write-Host
    exit 1
}

if ($Results | Where-Object { $_.Status -eq "FAIL" }) {
    Write-Host "`nPreflight failed - fix the items above and re-run." -ForegroundColor Red
    $Results | Format-Table -AutoSize | Out-String | Write-Host
    exit 1
}

# --- 2. backend ------------------------------------------------------------
Write-Host "2. Backend" -ForegroundColor Cyan
if ($SkipBackend) { Add-Result "backend check" "SKIP" "-SkipBackend" }
else {
    $up = Start-Backend
    if ($up) { Add-Result "backend health" "PASS" $HealthUrl }
    else { Add-Result "backend health" "FAIL" "uvicorn did not answer on 127.0.0.1:8000" }
}

# --- 3. bridge -------------------------------------------------------------
Write-Host "3. USB bridge" -ForegroundColor Cyan
Invoke-Adb reverse tcp:8000 tcp:8000 | Out-Null
$reverse = (Invoke-Adb reverse --list) -join ""
if ($reverse -match "tcp:8000") { Add-Result "adb reverse 8000" "PASS" $reverse.Trim() }
else { Add-Result "adb reverse 8000" "FAIL" "no reverse tunnel - app cannot reach the PC backend" }

# --- 4. install ------------------------------------------------------------
Write-Host "4. Install" -ForegroundColor Cyan
if ($SkipInstall) { Add-Result "APK install" "SKIP" "-SkipInstall" }
else {
    $out = (Invoke-Adb install -r $Apk 2>&1) -join "`n"
    if ($LASTEXITCODE -eq 0 -and $out -match "Success") { Add-Result "APK install" "PASS" "reinstalled" }
    else { Add-Result "APK install" "FAIL" ($out.Trim() -replace "`n", " ") }
}

# --- 5. launch -------------------------------------------------------------
Write-Host "5. Launch" -ForegroundColor Cyan
Invoke-Adb logcat -c | Out-Null
Invoke-Adb shell am start -n $Activity | Out-Null
Start-Sleep -Seconds 4
$shot1 = Save-Screenshot "01-launch"
Add-Result "app launch" "PASS" $(if ($shot1) { "screenshot 01-launch.png" } else { "launched (screenshot failed)" })
$crash = Get-CrashLog
if ($crash) { Add-Result "no crash on launch" "FAIL" "see logcat"; $crash | Set-Content (Join-Path $Artifacts "crash-launch.log") }
else { Add-Result "no crash on launch" "PASS" "logcat clean" }

$raw = Get-UiRaw
if ($raw -match "MindMesh") { Add-Result "companion UI rendered" "PASS" "brand/header text found" }
else { Add-Result "companion UI rendered" "FAIL" "no MindMesh text in the UI dump" }

# --- 6. share intent -------------------------------------------------------
Write-Host "6. Share intent" -ForegroundColor Cyan
Invoke-ShareIntent -Url $ShareUrl
$shot2 = Save-Screenshot "02-share-intent"
$raw2 = Get-UiRaw
if ($raw2 -match [regex]::Escape($ShareUrl.Split("?")[0])) {
    Add-Result "shared link captured" "PASS" "URL visible in UI (draft or pending card)"
} else {
    Add-Result "shared link captured" "FAIL" "URL missing after ACTION_SEND"
}
$crash = Get-CrashLog
if ($crash) { Add-Result "no crash on share" "FAIL" "see crash-share.log"; $crash | Set-Content (Join-Path $Artifacts "crash-share.log") }
else { Add-Result "no crash on share" "PASS" }

# --- 7. sign in (optional) -------------------------------------------------
$signedIn = $false
$raw3 = Get-UiRaw
if ($raw3 -match "Save to MindMesh") {
    Add-Result "already signed in" "PASS" "home screen visible"
    $signedIn = $true
} elseif ($Email -and $Password) {
    Write-Host "7. Sign in" -ForegroundColor Cyan
    # go to the login screen from wherever we are
        $loginTab = Find-UiNode -Pattern "^Sign in$" -Raw $raw3
        if ($loginTab) { Invoke-Tap $loginTab.CenterX $loginTab.CenterY; Start-Sleep -Seconds 2 }
        $raw3 = Get-UiRaw
        $fields = Get-FieldNodes -Raw $raw3
        if ($fields.Count -ge 2) {
            Invoke-Tap $fields[0].CenterX $fields[0].CenterY
            Send-AdbText $Email
            $fields = Get-FieldNodes
            $pwField = $fields | Sort-Object CenterY | Select-Object -Last 1
            Invoke-Tap $pwField.CenterX $pwField.CenterY
            Send-AdbText $Password
            $signInBtn = Find-UiNode -Pattern "^\s*Sign in\s*$"
            if ($signInBtn) { Invoke-Tap $signInBtn.CenterX $signInBtn.CenterY } else { Invoke-Adb shell input keyevent 66 | Out-Null }
            if (Wait-UiText -Pattern "Save to MindMesh" -TimeoutSec 25) {
                Add-Result "sign in" "PASS" "home screen reached"
                $signedIn = $true
            } else {
                Add-Result "sign in" "FAIL" "home screen not reached - finish it in the scrcpy window and re-run with -SkipInstall"
                Save-Screenshot "03-signin-failed" | Out-Null
            }
            Save-Screenshot "03-home" | Out-Null
        } else {
            Add-Result "sign in" "SKIP" "no EditText nodes found - sign in manually in the scrcpy window"
        }
} else {
    Add-Result "sign in" "SKIP" "no -Email/-Password supplied"
}

# --- 8. save + status ------------------------------------------------------
if ($signedIn) {
    Write-Host "8. Save + status" -ForegroundColor Cyan
    Invoke-ShareIntent -Url $ShareUrl
    Start-Sleep -Seconds 1
    $saveBtn = Find-UiNode -Pattern "Save to MindMesh"
    if ($saveBtn) { Invoke-Tap $saveBtn.CenterX $saveBtn.CenterY } else { Add-Result "save button" "FAIL" "not found" }

    $states = "Sending|Accepted|Processing|Synced|Failed|Backend offline|Needs sign-in|On device"
    if (Wait-UiText -Pattern $states -TimeoutSec 30) {
        Save-Screenshot "04-save-status" | Out-Null
        $raw4 = Get-UiRaw
        $hit = [regex]::Match($raw4, "($states)").Groups[1].Value
        Add-Result "save status reported" "PASS" "state visible: $hit"
    } else {
        Save-Screenshot "04-save-status-missing" | Out-Null
        Add-Result "save status reported" "FAIL" "no status pill within 30s"
    }
} else {
    Add-Result "save status" "SKIP" "requires sign-in"
}

# --- 9. offline truth ------------------------------------------------------
Write-Host "9. Offline truth state" -ForegroundColor Cyan
$wasRunning = Test-BackendHealth
Stop-Backend
Invoke-Adb shell am start -n $Activity | Out-Null
Start-Sleep -Seconds 3
$syncBtn = Find-UiNode -Pattern "Sync now"
if ($syncBtn) { Invoke-Tap $syncBtn.CenterX $syncBtn.CenterY } else { Invoke-Adb shell am start -n $Activity | Out-Null }
Start-Sleep -Seconds 4
$raw5 = Get-UiRaw
Save-Screenshot "05-backend-offline" | Out-Null
if ($raw5 -match "Backend offline|backend unreachable|not reachable|Backend not reachable") {
    Add-Result "offline state shown" "PASS" "row/chip reports the backend is unreachable"
} else {
    Add-Result "offline state shown" "FAIL" "no offline copy in UI dump"
}

if ($wasRunning -or $script:BackendProc) {
    if (Start-Backend) {
        Add-Result "backend restarted" "PASS"
        $syncBtn = Find-UiNode -Pattern "Sync now"
        if ($syncBtn) { Invoke-Tap $syncBtn.CenterX $syncBtn.CenterY }
        if (Wait-UiText -Pattern "Backend online|Synced|Accepted|Processing" -TimeoutSec 30) {
            Save-Screenshot "06-recovered" | Out-Null
            Add-Result "recovery after restart" "PASS" "health chip/status updated"
        } else {
            Add-Result "recovery after restart" "FAIL" "still not online after 30s"
        }
    } else { Add-Result "backend restarted" "FAIL" "could not restart uvicorn" }
} else { Add-Result "backend restarted" "SKIP" "backend was not started by this run" }

# --- 10. crash sweep + report ---------------------------------------------
Write-Host "10. Report" -ForegroundColor Cyan
$finalCrash = Get-CrashLog
if ($finalCrash) {
    Add-Result "session crash-free" "FAIL" "FATAL EXCEPTION captured"
    $finalCrash | Set-Content (Join-Path $Artifacts "crash-session.log")
} else { Add-Result "session crash-free" "PASS" }

if ($StopBackend) { Stop-Backend; Add-Result "backend stopped" "INFO" "-StopBackend" }

Write-Host ""
Write-Host "==== Results ====" -ForegroundColor Cyan
$Results | Format-Table -AutoSize | Out-String | Write-Host
$fail = @($Results | Where-Object Status -eq "FAIL").Count
$pass = @($Results | Where-Object Status -eq "PASS").Count
Write-Host ("PASS {0} / FAIL {1} / total {2}" -f $pass, $fail, $Results.Count) -ForegroundColor $(if ($fail) { "Red" } else { "Green" })
Write-Host "artifacts: $Artifacts"
if ($fail) { exit 1 } else { exit 0 }

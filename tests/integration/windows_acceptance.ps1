# Run from a clean source archive. This test needs only inbox Windows PowerShell.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ReportDir,
    [switch]$RequireNonAdmin,
    [switch]$NetworkIsolationHandshake,
    [string]$CompletionNonce = ''
)
$ErrorActionPreference = 'Stop'
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$reportPath = [IO.Path]::GetFullPath($ReportDir)
New-Item -ItemType Directory -Force -Path $reportPath | Out-Null
$envBefore = [Environment]::GetEnvironmentVariables()
$oldLocation = Get-Location
$outputEncodingBefore = $OutputEncoding
$consoleEncodingBefore = [Console]::OutputEncoding
$stopwatch = [Diagnostics.Stopwatch]::StartNew()
$phaseTimes = @{}
$cachedDownloadBytes = $null
$succeeded = $false
$driverExitCode = 1
$failureText = $null

function Invoke-LoggedNative([string]$Executable, [string[]]$NativeArguments, [string]$LogFile) {
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw "Missing executable: $Executable" }
    # Transcript alone omits native stdout/stderr in a hidden PowerShell 5
    # process. Consume both streams explicitly while retaining the native code.
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Executable @NativeArguments 2>&1 | ForEach-Object {
            $line = $_.ToString()
            [IO.File]::AppendAllText($LogFile, $line + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
            Write-Host $line
        }
        $nativeExitCode = $LASTEXITCODE
        if ($null -eq $nativeExitCode) { throw 'Native command did not supply an exit code.' }
    } finally { $ErrorActionPreference = $priorPreference }
    return $nativeExitCode
}

Start-Transcript -Path (Join-Path $reportPath 'acceptance.log') -Force | Out-Null
try {
    Set-Location $projectDir
    foreach ($name in @('.forge', '.venv')) {
        if (Test-Path -LiteralPath (Join-Path $projectDir $name)) {
            throw "Cold bootstrap requires a source-only copy; $name already exists."
        }
    }
    $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($RequireNonAdmin -and $isAdmin) { throw 'The actual acceptance process must be a standard user.' }

    # Process-local isolation: never change the user's persistent environment.
    foreach ($variableName in @([Environment]::GetEnvironmentVariables().Keys)) {
        if ($variableName -match '^(UV_|PYTHON|PLAYWRIGHT_|ACF_|PIP_|VIRTUAL_ENV$|TESSDATA_PREFIX$|TESSERACT_)') {
            [Environment]::SetEnvironmentVariable($variableName, $null, 'Process')
        }
    }
    # GitHub's Windows image installs Docker directly into System32. Only
    # expose inbox PowerShell; the launcher addresses tar.exe by absolute path.
    $env:PATH = "$env:SystemRoot\System32\WindowsPowerShell\v1.0"
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $OutputEncoding = [Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $OutputEncoding
    $preflight = @{}
    $unexpected = @()
    foreach ($name in @('python', 'python3', 'py', 'uv', 'docker', 'git', 'tesseract')) {
        $found = @(Get-Command $name -All -ErrorAction SilentlyContinue)
        $preflight[$name] = @($found | ForEach-Object {
            @{ command_type = $_.CommandType.ToString(); source = $_.Source; path = $_.Path }
        })
        if ($found) { $unexpected += $name }
    }
    @{ project = $projectDir; elevated = $isAdmin; tools = $preflight;
       path = $env:PATH; windows = [Environment]::OSVersion.VersionString } |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $reportPath 'before.json') -Encoding UTF8
    if ($unexpected) {
        throw ('Cold bootstrap unexpectedly resolves host tools: ' + ($unexpected -join ', ') + '. See before.json for command paths.')
    }

    $phase = [Diagnostics.Stopwatch]::StartNew()
    $nativeExit = Invoke-LoggedNative (Join-Path $projectDir 'forge.cmd') @('setup') (Join-Path $reportPath 'cold-setup.log')
    if ($nativeExit -ne 0) { throw "Cold setup failed: $nativeExit" }
    $phaseTimes.cold_setup_seconds = $phase.Elapsed.TotalSeconds
    $python = Join-Path $projectDir '.venv\Scripts\python.exe'
    $nativeExit = Invoke-LoggedNative $python @((Join-Path $PSScriptRoot 'check_native_environment.py'),
        '--output', (Join-Path $reportPath 'provenance.json')) (Join-Path $reportPath 'provenance.log')
    if ($nativeExit -ne 0) { throw "Managed runtime provenance check failed: $nativeExit" }
    $nativeExit = Invoke-LoggedNative $python @('-m', 'unittest', 'discover', '-s',
        (Join-Path $projectDir 'tests'), '-p', 'test_*.py', '-v') (Join-Path $reportPath 'unit-tests.log')
    if ($nativeExit -ne 0) { throw "Native Python tests failed: $nativeExit" }

    # In Sandbox, its privileged guest coordinator disables the guest NICs.
    # Hosted CI uses downloader offline flags; that is a narrower guarantee.
    if ($NetworkIsolationHandshake) {
        $nonce = [guid]::NewGuid().ToString('N')
        $requestTemp = Join-Path $reportPath 'request-network-offline.json.tmp'
        @{ nonce = $nonce } | ConvertTo-Json |
            Set-Content -LiteralPath $requestTemp -Encoding UTF8
        Move-Item -LiteralPath $requestTemp -Destination (Join-Path $reportPath 'request-network-offline.json')
        $response = Join-Path $reportPath 'network-isolated.json'
        $deadline = [DateTime]::UtcNow.AddMinutes(2)
        do {
            if ([DateTime]::UtcNow -gt $deadline) { throw 'Guest coordinator did not disable networking.' }
            Start-Sleep -Seconds 1
            $isolation = if (Test-Path -LiteralPath $response) {
                Get-Content -LiteralPath $response -Raw | ConvertFrom-Json
            } else { $null }
        } until ($isolation -and $isolation.nonce -eq $nonce -and $isolation.network_isolated -eq $true)
    }
    # Setup itself runs build and visual integration on each invocation.
    $phase.Restart()
    $env:UV_OFFLINE = '1'
    $nativeExit = Invoke-LoggedNative (Join-Path $projectDir 'forge.cmd') @('setup', '--offline') (Join-Path $reportPath 'offline-setup.log')
    if ($nativeExit -ne 0) { throw "Offline repeat setup failed: $nativeExit" }
    $phaseTimes.offline_setup_seconds = $phase.Elapsed.TotalSeconds
    $nativeExit = Invoke-LoggedNative $python @((Join-Path $projectDir 'tools\forge.py'),
        '--backend', 'native', 'doctor', '--json') (Join-Path $reportPath 'doctor.json')
    if ($nativeExit -ne 0) { throw "Final doctor failed: $nativeExit" }
    Copy-Item -LiteralPath (Join-Path $projectDir '.forge\setup-state.json') -Destination $reportPath
    $cachedDownloadBytes = (Get-ChildItem -LiteralPath (Join-Path $projectDir '.forge\cache') -File -Recurse |
        Measure-Object -Property Length -Sum).Sum
    $succeeded = $true
    $driverExitCode = 0
}
catch {
    $failureText = $_ | Out-String
    $failureText | Set-Content -LiteralPath (Join-Path $reportPath 'driver-error.txt') -Encoding UTF8
    Write-Host $failureText
}
finally {
    @{ success = $succeeded; elapsed_seconds = $stopwatch.Elapsed.TotalSeconds; phases = $phaseTimes;
       cache_bytes = $cachedDownloadBytes; network_isolation_requested = [bool]$NetworkIsolationHandshake;
       exit_code = $driverExitCode; error = $failureText } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $reportPath 'result.json') -Encoding UTF8
    if (-not $succeeded) {
        $runtimeLogs = Join-Path $projectDir '.forge\logs'
        if ((Test-Path -LiteralPath $runtimeLogs) -and
            -not ((Get-Item -LiteralPath $runtimeLogs).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            $logDestination = Join-Path $reportPath 'runtime-logs'
            New-Item -ItemType Directory -Path $logDestination -Force | Out-Null
            Get-ChildItem -LiteralPath $runtimeLogs -File -Filter '*.log' |
                Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
                ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $logDestination }
        }
        foreach ($folder in @('decks', 'extracted')) {
            $parent = Join-Path $projectDir $folder
            if (Test-Path -LiteralPath $parent) {
                $dest = Join-Path $reportPath $folder
                New-Item -ItemType Directory -Force -Path $dest | Out-Null
                Get-ChildItem -LiteralPath $parent -Directory -Filter '_ci-*' |
                    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse }
            }
        }
    }
    Stop-Transcript | Out-Null
    foreach ($variableName in @([Environment]::GetEnvironmentVariables().Keys)) {
        if (-not $envBefore.ContainsKey($variableName)) {
            [Environment]::SetEnvironmentVariable($variableName, $null, 'Process')
        }
    }
    foreach ($variableName in $envBefore.Keys) {
        [Environment]::SetEnvironmentVariable($variableName, $envBefore[$variableName], 'Process')
    }
    $OutputEncoding = $outputEncodingBefore
    [Console]::OutputEncoding = $consoleEncodingBefore
    Set-Location $oldLocation
}
# Publish only after transcript closure, diagnostic copying and environment
# restoration. A killed/crashed driver has no trustworthy completion marker.
$completionTemp = Join-Path $reportPath 'driver-complete.json.tmp'
@{ completed = $true; success = $succeeded; exit_code = $driverExitCode;
   process_id = $PID; nonce = $CompletionNonce } | ConvertTo-Json |
    Set-Content -LiteralPath $completionTemp -Encoding UTF8
Move-Item -LiteralPath $completionTemp -Destination (Join-Path $reportPath 'driver-complete.json')
if ($driverExitCode -ne 0) { throw $failureText }
exit $driverExitCode

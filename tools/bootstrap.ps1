# Windows 11 x64 starter. Downloads happen only for an explicit setup command.
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]] $ForgeArguments)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if (-not $ForgeArguments) { $ForgeArguments = @('--help') }
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$managedRoot = Join-Path $projectRoot '.forge'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$basePython = Join-Path $managedRoot 'python\python.exe'
$uvExecutable = Join-Path $managedRoot 'uv\uv.exe'
$manifestPath = Join-Path $PSScriptRoot 'runtime-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$offline = $ForgeArguments -contains '--offline'
$commandArguments = @($ForgeArguments)
$requestedBackend = 'native'
if ($commandArguments.Count -ge 2 -and $commandArguments[0] -eq '--backend') {
    $requestedBackend = $commandArguments[1]
    $commandArguments = @($commandArguments | Select-Object -Skip 2)
} elseif ($commandArguments.Count -ge 1 -and $commandArguments[0] -like '--backend=*') {
    $requestedBackend = $commandArguments[0].Substring('--backend='.Length)
    $commandArguments = @($commandArguments | Select-Object -Skip 1)
}
$commandName = if ($commandArguments.Count) { $commandArguments[0] } else { '--help' }
$isHelp = $commandName -in @('--help', '-h', 'help') -or $ForgeArguments -contains '--help' -or $ForgeArguments -contains '-h'

function Show-BootstrapHelp {
    Write-Output 'Anki Card Forge - Windows 11 x64'
    Write-Output 'Usage: .\forge.cmd [--backend native] COMMAND [arguments]'
    Write-Output 'The Docker backend uses the documented Linux/WSL entry point.'
    Write-Output 'Commands: setup, doctor, prep, extract, figindex, figextract, detect,'
    Write-Output '          preview, build, validate, finish, lint, grounding, coverage,'
    Write-Output '          diff, decode, anki, test'
    Write-Output 'First use: .\forge.cmd setup'
    Write-Output 'Setup downloads a private Python, packages, OCR and browser into this project.'
    Write-Output 'Repeat without downloads: .\forge.cmd setup --offline'
    Write-Output 'Add OCR languages: .\forge.cmd setup --lang eng+deu+fra'
}

function Assert-ManagedPath([string] $Candidate) {
    $resolved = [IO.Path]::GetFullPath($Candidate)
    $prefix = [IO.Path]::GetFullPath($managedRoot).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Managed runtime path escapes .forge: $resolved"
    }
}

function Get-SHA256([string] $FilePath) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($FilePath)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Test-BootstrapInventory($State) {
    if (-not $State -or -not $State.files) { return $false }
    $entries = @($State.files.PSObject.Properties)
    if ($entries.Count -eq 0) { return $false }
    foreach ($entry in $entries) {
        # CPython regenerates shipped bytecode when archive timestamps change.
        # It is a derived cache, not an immutable runtime payload.
        if ($entry.Name.EndsWith('.pyc', [StringComparison]::OrdinalIgnoreCase)) { continue }
        $installedFile = Join-Path $managedRoot $entry.Name
        try {
            Assert-ManagedPath $installedFile
            if (-not (Test-Path -LiteralPath $installedFile -PathType Leaf) -or
                (Get-SHA256 $installedFile) -ne $entry.Value) { return $false }
        } catch { return $false }
    }
    return $true
}

function Get-VerifiedAsset($Asset) {
    $downloadCache = Join-Path $managedRoot 'cache\downloads'
    New-Item -ItemType Directory -Path $downloadCache -Force | Out-Null
    $destination = Join-Path $downloadCache $Asset.filename
    Assert-ManagedPath $destination
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $actual = Get-SHA256 $destination
        if ($actual -eq $Asset.sha256) { return $destination }
        if ($offline) { throw "Cached checksum mismatch: $destination. Run setup online to repair it." }
    } elseif ($offline) {
        throw "Offline setup needs cached asset: $($Asset.filename). Run setup once with internet access."
    }
    $partial = $destination + '.part-' + [Guid]::NewGuid().ToString('N')
    try {
        Write-Host "Downloading $($Asset.filename)..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $Asset.url -OutFile $partial -UseBasicParsing
        $actual = Get-SHA256 $partial
        if ($actual -ne $Asset.sha256) { throw "SHA-256 mismatch for $($Asset.filename); nothing was executed." }
        Move-Item -LiteralPath $partial -Destination $destination -Force
    } finally {
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    }
    return $destination
}

function Expand-VerifiedZip([string] $Archive, [string] $Destination) {
    Assert-ManagedPath $Destination
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $prefix = [IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
        foreach ($entry in $zip.Entries) {
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
            if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Unsafe archive entry: $($entry.FullName)"
            }
            if (-not $entry.Name) {
                New-Item -ItemType Directory -Path $target -Force | Out-Null
            } else {
                New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
            }
        }
    } finally { $zip.Dispose() }
}

function Publish-Runtime([string] $Staged, [string] $Destination) {
    Assert-ManagedPath $Staged
    Assert-ManagedPath $Destination
    $oldRuntime = $null
    if (Test-Path -LiteralPath $Destination) {
        $oldRuntime = Join-Path $managedRoot ('staging\previous-' + [Guid]::NewGuid().ToString('N'))
        Assert-ManagedPath $oldRuntime
        Move-Item -LiteralPath $Destination -Destination $oldRuntime
    }
    try { Move-Item -LiteralPath $Staged -Destination $Destination }
    catch {
        if ($oldRuntime -and -not (Test-Path -LiteralPath $Destination)) {
            Move-Item -LiteralPath $oldRuntime -Destination $Destination
        }
        throw
    }
}

function Set-ChildEnvironment {
    # Managed commands use their own locked runtime/configuration. Preserve
    # ordinary proxy/certificate settings, but ignore inherited tool overrides.
    # CMD may preserve environment keys differing only in case. PowerShell 5's
    # Env: enumeration throws on those; .NET's process dictionary tolerates them.
    foreach ($variableName in @([Environment]::GetEnvironmentVariables().Keys)) {
        if ($variableName -match '^(UV_|PLAYWRIGHT_|npm_config_playwright_|npm_package_config_playwright_|NODE_OPTIONS$|NODE_PATH$)') {
            [Environment]::SetEnvironmentVariable($variableName, $null, 'Process')
        }
    }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONNOUSERSITE = '1'
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    $env:UV_CACHE_DIR = Join-Path $managedRoot 'cache\uv'
    $env:UV_PYTHON_DOWNLOADS = 'never'
    $env:UV_LINK_MODE = 'copy'
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $projectRoot '.venv'
    $env:VIRTUAL_ENV = Join-Path $projectRoot '.venv'
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $managedRoot 'browsers'
    $env:TESSDATA_PREFIX = Join-Path $managedRoot ('tools\tesseract-' + $manifest.tesseract_version + '\tessdata')
    $env:ACF_MATHJAX_DIR = Join-Path $managedRoot ('assets\mathjax-' + $manifest.mathjax_version + '\es5')
    $env:PATH = (Join-Path $projectRoot '.venv\Scripts') + ';' +
        (Join-Path $managedRoot ('tools\tesseract-' + $manifest.tesseract_version)) + ';' + $env:PATH
}

$setupLock = $null
$previousConsoleEncoding = [Console]::OutputEncoding
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding
try {
    if ($requestedBackend -ne 'native') {
        throw 'forge.cmd supports the native Windows backend. Use the documented Linux/WSL entry point for Docker.'
    }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if ($isHelp) { Show-BootstrapHelp; exit 0 }
        if ($commandName -ne 'setup') {
            if ($commandName -eq 'doctor' -and $ForgeArguments -contains '--json') {
                Write-Output '{"ready":false,"error":"Managed runtime is missing. Run .\\forge.cmd setup."}'
            } else { Write-Host 'Managed runtime is missing. Run .\forge.cmd setup.' }
            exit 1
        }
    }
    if ($commandName -eq 'setup' -and -not $isHelp) {
        if (-not [Environment]::Is64BitOperatingSystem -or
            ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64' -and $env:PROCESSOR_ARCHITEW6432 -ne 'AMD64') -or
            [Environment]::OSVersion.Version.Build -lt 22000) {
            throw 'Native setup currently supports Windows 11 x64. Use the documented Linux/Docker workflow elsewhere.'
        }
        New-Item -ItemType Directory -Path $managedRoot -Force | Out-Null
        try {
            $setupLock = [IO.File]::Open((Join-Path $managedRoot 'setup.lock'), [IO.FileMode]::OpenOrCreate,
                [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        } catch { throw 'Another setup is using this project. Wait for it to finish, then try again.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $bootstrapStamp = Join-Path $managedRoot 'bootstrap-state.json'
        $bootstrapIdentity = $manifest.assets.uv.sha256 + ':' + $manifest.assets.python.sha256 + ':' + $manifest.assets.crt.sha256
        $stamp = $null
        if (Test-Path -LiteralPath $bootstrapStamp) {
            try { $stamp = Get-Content -Raw -LiteralPath $bootstrapStamp | ConvertFrom-Json }
            catch { $stamp = $null }
        }
        if (-not $stamp -or $stamp.identity -ne $bootstrapIdentity -or
            -not (Test-Path -LiteralPath $basePython) -or -not (Test-Path -LiteralPath $uvExecutable) -or
            -not (Test-BootstrapInventory $stamp)) {
            $uvArchive = Get-VerifiedAsset $manifest.assets.uv
            $pythonArchive = Get-VerifiedAsset $manifest.assets.python
            $crtArchive = Get-VerifiedAsset $manifest.assets.crt
            $stage = Join-Path $managedRoot ('staging\bootstrap-' + [Guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $stage -Force | Out-Null
            Expand-VerifiedZip $uvArchive (Join-Path $stage 'uv')
            Expand-VerifiedZip $crtArchive (Join-Path $stage 'crt')
            $tarExecutable = Join-Path $env:SystemRoot 'System32\tar.exe'
            if (-not (Test-Path -LiteralPath $tarExecutable)) { throw 'Windows tar.exe is missing; repair the Windows 11 installation.' }
            & $tarExecutable -xzf $pythonArchive -C $stage
            if ($LASTEXITCODE -ne 0) { throw 'Python archive extraction failed.' }
            $crtFolder = Join-Path (Join-Path $stage 'crt') $manifest.assets.crt.archive_prefix
            $crtFiles = @(Get-ChildItem -LiteralPath $crtFolder -Filter '*.dll' -File)
            if ($crtFiles.Count -eq 0) { throw 'The pinned Microsoft CRT archive has an unexpected layout.' }
            foreach ($crtFile in $crtFiles) { Copy-Item -LiteralPath $crtFile.FullName -Destination (Join-Path $stage 'python') }
            $stagedUv = Get-ChildItem -LiteralPath (Join-Path $stage 'uv') -Filter 'uv.exe' -File -Recurse | Select-Object -First 1
            if (-not $stagedUv -or -not (Test-Path -LiteralPath (Join-Path $stage 'python\python.exe'))) {
                throw 'The pinned runtime archives have an unexpected layout.'
            }
            Publish-Runtime $stagedUv.Directory.FullName (Join-Path $managedRoot 'uv')
            Publish-Runtime (Join-Path $stage 'python') (Join-Path $managedRoot 'python')
            $crtTarget = Join-Path $managedRoot 'tools\crt'
            New-Item -ItemType Directory -Path $crtTarget -Force | Out-Null
            foreach ($crtFile in $crtFiles) { Copy-Item -LiteralPath $crtFile.FullName -Destination $crtTarget -Force }
            $installedFiles = @{}
            foreach ($runtimeFolder in @((Join-Path $managedRoot 'uv'), (Join-Path $managedRoot 'python'), $crtTarget)) {
                foreach ($runtimeFile in Get-ChildItem -LiteralPath $runtimeFolder -File -Recurse) {
                    if ($runtimeFile.Extension -eq '.pyc') { continue }
                    $relativeName = $runtimeFile.FullName.Substring($managedRoot.Length + 1)
                    $installedFiles[$relativeName] = Get-SHA256 $runtimeFile.FullName
                }
            }
            $stampPart = $bootstrapStamp + '.part'
            @{ identity = $bootstrapIdentity; files = $installedFiles } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stampPart -Encoding UTF8
            Move-Item -LiteralPath $stampPart -Destination $bootstrapStamp -Force
        }
        Set-ChildEnvironment
        Push-Location -LiteralPath $projectRoot
        try {
            $syncArgs = @('sync', '--locked', '--no-config', '--python', $basePython, '--no-python-downloads')
            if ($offline) { $syncArgs += '--offline' }
            & $uvExecutable @syncArgs
            if ($LASTEXITCODE -ne 0) { throw 'Locked Python dependency setup failed. Check network access or run online to populate the cache.' }
            foreach ($crtFile in Get-ChildItem -LiteralPath (Join-Path $managedRoot 'tools\crt') -Filter '*.dll' -File) {
                Copy-Item -LiteralPath $crtFile.FullName -Destination (Join-Path $projectRoot '.venv\Scripts') -Force
            }
            $repairArgs = @((Join-Path $PSScriptRoot 'native_setup.py'), 'repair-packages')
            if ($offline) { $repairArgs += '--offline' }
            & $basePython @repairArgs
            if ($LASTEXITCODE -ne 0) { throw 'Installed Python package verification or repair failed.' }
        } finally { Pop-Location }
    }
    Set-ChildEnvironment
    if (-not $isHelp -and $commandName -notin @('setup', 'doctor')) {
        $statePath = Join-Path $managedRoot 'setup-state.json'
        if (-not (Test-Path -LiteralPath $statePath)) { throw 'Setup has not passed its checks. Run .\forge.cmd setup.' }
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $manifestHash = Get-SHA256 $manifestPath
        $lockHash = Get-SHA256 (Join-Path $projectRoot 'uv.lock')
        if ($state.manifest_sha256 -ne $manifestHash -or $state.lock_sha256 -ne $lockHash -or $state.root -ne $projectRoot) {
            throw 'The managed setup is outdated or the project was moved. Run .\forge.cmd setup.'
        }
    }
    & $venvPython (Join-Path $PSScriptRoot 'forge.py') @ForgeArguments
    $result = $LASTEXITCODE
} catch {
    Write-Host ("Setup/launcher error: " + $_.Exception.Message)
    $result = 1
} finally {
    if ($setupLock) { $setupLock.Dispose() }
    [Console]::OutputEncoding = $previousConsoleEncoding
}
exit $result

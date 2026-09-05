# Prepare a reviewable .wsb and source-only archive of the exact current commit.
# This does not enable Windows features or launch/reboot the computer.
[CmdletBinding()]
param([string]$Destination)
$ErrorActionPreference = 'Stop'
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Destination) {
    $Destination = Join-Path $projectDir ('decks\_sandbox-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '_rebuild')
}
$target = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $target) { throw 'Choose a new directory so previous reports remain intact.' }
$inputDir = Join-Path $target 'input'
$reportDir = Join-Path $target 'reports'
New-Item -ItemType Directory -Path $inputDir, $reportDir | Out-Null
$revision = (& git -C $projectDir rev-parse --verify HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the candidate commit.' }
foreach ($required in @('forge.cmd', 'uv.lock', 'tests/integration/sandbox_run.ps1', 'tests/integration/windows_acceptance.ps1')) {
    & git -C $projectDir cat-file -e ($revision + ':' + $required)
    if ($LASTEXITCODE -ne 0) { throw "Candidate commit lacks $required. Commit the complete setup before preparing its Sandbox test." }
}
& git -C $projectDir archive --format=zip ('--output=' + (Join-Path $inputDir 'source.zip')) $revision
if ($LASTEXITCODE -ne 0) { throw 'Could not archive the candidate commit.' }
$revision | Set-Content -LiteralPath (Join-Path $reportDir 'candidate-commit.txt') -Encoding ASCII
function Escape-Xml([string]$value) { [Security.SecurityElement]::Escape($value) }
$command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath C:\ACF-Input\source.zip -DestinationPath C:\ACF-Source; & C:\ACF-Source\tests\integration\sandbox_run.ps1 -ReportDir C:\ACF-Reports"'
$xml = @"
<Configuration>
  <MemoryInMB>6144</MemoryInMB>
  <Networking>Enable</Networking>
  <AudioInput>Disable</AudioInput>
  <VideoInput>Disable</VideoInput>
  <PrinterRedirection>Disable</PrinterRedirection>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <MappedFolders>
    <MappedFolder><HostFolder>$(Escape-Xml $inputDir)</HostFolder><SandboxFolder>C:\ACF-Input</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$(Escape-Xml $reportDir)</HostFolder><SandboxFolder>C:\ACF-Reports</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>$(Escape-Xml $command)</Command></LogonCommand>
</Configuration>
"@
$wsb = Join-Path $target 'acceptance.wsb'
$xml | Set-Content -LiteralPath $wsb -Encoding UTF8
Write-Output "Prepared commit $revision. Launch $wsb; reports will appear in $reportDir."

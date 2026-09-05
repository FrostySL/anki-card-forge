# PowerShell entry point for literal HTML, quotes, ampersands and empty values.
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][AllowEmptyString()][string[]] $ForgeArguments)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'tools/native_process.ps1')
try {
    # Run bootstrap in a child so managed PATH/tool settings never leak into
    # the calling PowerShell session. No persistent execution policy changes.
    $powershell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $forward = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                 (Join-Path $PSScriptRoot 'tools/bootstrap.ps1')) + @($ForgeArguments)
    $result = Invoke-ManagedProcess -Executable $powershell -Arguments $forward
} catch {
    [Console]::Error.WriteLine('Forge launcher error: ' + $_.Exception.Message)
    $result = 1
}
exit $result

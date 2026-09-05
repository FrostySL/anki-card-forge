# Shared Windows process boundary. Dot-sourcing this file changes no environment.
function ConvertTo-NativeArgument([AllowEmptyString()][string] $Value) {
    # Windows C-runtime quoting; PowerShell 5's native binder drops embedded
    # quotes and empty arguments, so ProcessStartInfo receives this string.
    $quoted = [Text.StringBuilder]::new()
    [void]$quoted.Append('"')
    $slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') { $slashes++; continue }
        if ($character -eq '"') {
            [void]$quoted.Append(('\' * (2 * $slashes + 1)))
        } else {
            [void]$quoted.Append(('\' * $slashes))
        }
        [void]$quoted.Append($character)
        $slashes = 0
    }
    [void]$quoted.Append(('\' * (2 * $slashes)))
    [void]$quoted.Append('"')
    return $quoted.ToString()
}

function Invoke-ManagedProcess([string] $Executable, [string[]] $Arguments) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.WorkingDirectory = (Get-Location).ProviderPath
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.Arguments = (@($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' ')
    $child = [Diagnostics.Process]::Start($start)
    try {
        # Copy concurrently: preserve progress and UTF-8 bytes without filling
        # either pipe while the other one is being read.
        $stdoutCopy = $child.StandardOutput.BaseStream.CopyToAsync([Console]::OpenStandardOutput())
        $stderrCopy = $child.StandardError.BaseStream.CopyToAsync([Console]::OpenStandardError())
        $child.WaitForExit()
        [void]$stdoutCopy.GetAwaiter().GetResult()
        [void]$stderrCopy.GetAwaiter().GetResult()
        return $child.ExitCode
    }
    finally { $child.Dispose() }
}

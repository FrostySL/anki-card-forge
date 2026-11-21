# Run by bootstrap.ps1 in the same Windows PowerShell as managed setup.
function Test-ForgeWorkspaceWrite([string] $Root) {
    $downloads = Join-Path $Root '.forge\cache\downloads'
    $probe = Join-Path $downloads ('probe-' + [Guid]::NewGuid().ToString('N'))
    $file = Join-Path $probe 'write-test'
    try {
        [IO.Directory]::CreateDirectory($probe) | Out-Null
        [IO.File]::WriteAllText($file, 'forge')
        if (-not [IO.File]::Exists($file)) { throw 'The write did not create a file.' }
        [IO.File]::Delete($file)
        [IO.Directory]::Delete($probe)
    } catch {
        throw ('Windows PowerShell could not write at {0}: {1}' -f $downloads, $_.Exception.GetBaseException().Message)
    }
}

function Select-ForgeWorkspace([string] $Source, [string] $FallbackParent) {
    try {
        Test-ForgeWorkspaceWrite $Source
        Write-Output $Source
        return
    } catch {
        [Console]::Error.WriteLine($_.Exception.Message)
    }

    if (-not $FallbackParent) {
        # Keep the default path stable across tool invocations. A sandbox can
        # redirect LocalAppData to a different scratch directory for each call.
        $FallbackParent = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'AppData\Local\AnkiCardForge'
    }
    if ($FallbackParent -notmatch '^[a-zA-Z]:[\\/]') {
        throw "Expected an absolute local drive path for the fallback parent: $FallbackParent"
    }
    $fallback = [IO.Path]::GetFullPath($FallbackParent).TrimEnd('\') + '\'
    if ($fallback.StartsWith($Source.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Fallback parent is inside the blocked source: $fallback. Pass an allowed local folder outside it."
    }
    $target = Join-Path $fallback ('forge-' + [Guid]::NewGuid().ToString('N').Substring(0, 12))
    try {
        Test-ForgeWorkspaceWrite $target
        # Copy tooling and authoring instructions. Personal material and
        # path-bound runtimes are kept in the original project.
        foreach ($path in @('forge.cmd', 'forge.ps1', 'pyproject.toml', 'uv.lock',
                'README.md', 'AGENTS.md', 'LICENSE', '.githooks', 'tools', 'tests', 'skills', 'workflows')) {
            Copy-Item -LiteralPath (Join-Path $Source $path) -Destination $target -Recurse
        }
        New-Item -ItemType Directory -Path (Join-Path $target 'sources'), (Join-Path $target 'decks') | Out-Null
        Copy-Item -LiteralPath (Join-Path $Source 'decks\example.cards.json') -Destination (Join-Path $target 'decks')
    } catch {
        throw "Cannot prepare Forge at $target. $($_.Exception.Message) Run forge.cmd workspace with an allowed, writable local fallback parent or request permission for this folder."
    }
    [Console]::Error.WriteLine("Using a separate Forge copy at $target.")
    Write-Output $target
}

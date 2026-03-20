param(
    [string[]]$AllowedPrefixes = @()
)

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) {
    Write-Error "Not inside a git repository."
}

Set-Location $repoRoot

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Output "No staged files."
    exit 0
}

Write-Output "Staged files:"
$staged | ForEach-Object { Write-Output " - $_" }

if ($AllowedPrefixes.Count -eq 0) {
    Write-Output "No AllowedPrefixes supplied; only listing staged files."
    exit 0
}

$unexpected = @()
foreach ($path in $staged) {
    $isAllowed = $false
    foreach ($prefix in $AllowedPrefixes) {
        if ($path.StartsWith($prefix)) {
            $isAllowed = $true
            break
        }
    }

    if (-not $isAllowed) {
        $unexpected += $path
    }
}

if ($unexpected.Count -gt 0) {
    Write-Error "Unexpected staged files found outside allowed prefixes:`n$($unexpected -join "`n")"
}

Write-Output "All staged files are within allowed prefixes."

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Split-Path -Parent $scriptDir
$sourceRoot = Join-Path $repoRoot "src"

if ($env:PYTHONPATH) {
    if (-not ($env:PYTHONPATH -split ";" | Where-Object { $_ -eq $sourceRoot })) {
        $env:PYTHONPATH = "$sourceRoot;$($env:PYTHONPATH)"
    }
} else {
    $env:PYTHONPATH = $sourceRoot
}

python -m tfind @args
exit $LASTEXITCODE

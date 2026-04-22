$script:TFindRepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:TFindSourceRoot = Join-Path $script:TFindRepoRoot "src"
$script:TFindStateRoot = if ($env:TFIND_STATE_ROOT) {
    $env:TFIND_STATE_ROOT
} elseif ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA "tfind"
} else {
    Join-Path $HOME ".tfind"
}

function script:TFind-EnsurePythonPath {
    if ($env:PYTHONPATH) {
        if (-not ($env:PYTHONPATH -split ";" | Where-Object { $_ -eq $script:TFindSourceRoot })) {
            $env:PYTHONPATH = "$script:TFindSourceRoot;$($env:PYTHONPATH)"
        }
    } else {
        $env:PYTHONPATH = $script:TFindSourceRoot
    }
}

function script:TFind-IsTextMode {
    param(
        [string[]]$TFindArgs
    )

    if (-not $TFindArgs -or $TFindArgs.Count -eq 0) {
        return $true
    }

    $firstArg = $TFindArgs[0]
    if ($firstArg -in @("doctor", "bootstrap")) {
        return $true
    }

    foreach ($arg in $TFindArgs) {
        if (
            $arg -eq "-h" -or
            $arg -like "--h*" -or
            $arg -like "--v*" -or
            $arg -eq "--plain"
        ) {
            return $true
        }
    }

    return $false
}

function global:tfind {
    TFind-EnsurePythonPath
    $historyPath = $null
    try {
        $sessionsDir = Join-Path $script:TFindStateRoot "sessions"
        New-Item -ItemType Directory -Force -Path $sessionsDir | Out-Null

        if (-not $env:TFIND_SESSION_ID) {
            $env:TFIND_SESSION_ID = "{0:yyyyMMdd-HHmmss}-{1}" -f (Get-Date), $PID
        }

        $historyPath = Join-Path $sessionsDir "powershell-history-$($env:TFIND_SESSION_ID).log"
        $historyLines = Get-History | Sort-Object Id | ForEach-Object {
            if ($_.CommandLine) {
                "PS> $($_.CommandLine)"
            }
        }
        Set-Content -Path $historyPath -Value $historyLines -Encoding utf8
        $env:TFIND_POWERSHELL_HISTORY_SNAPSHOT = $historyPath
    } catch {
        Remove-Item Env:\TFIND_POWERSHELL_HISTORY_SNAPSHOT -ErrorAction SilentlyContinue
    }

    if (TFind-IsTextMode -TFindArgs $args) {
        $outputLines = @(& python -m tfind @args 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE

        foreach ($line in $outputLines) {
            Write-Host $line
        }

        $global:LASTEXITCODE = $exitCode
        return
    }

    python -m tfind @args
}

function global:Enable-TFindCapture {
    $sessionsDir = Join-Path $script:TFindStateRoot "sessions"
    New-Item -ItemType Directory -Force -Path $sessionsDir | Out-Null

    if (-not $env:TFIND_SESSION_ID) {
        $env:TFIND_SESSION_ID = "{0:yyyyMMdd-HHmmss}-{1}" -f (Get-Date), $PID
    }

    if (-not $env:TFIND_CURRENT_LOG) {
        $env:TFIND_CURRENT_LOG = Join-Path $sessionsDir "powershell-$($env:TFIND_SESSION_ID).log"
    }

    Set-Content -Path (Join-Path $script:TFindStateRoot "current-session.txt") -Value $env:TFIND_CURRENT_LOG -Encoding utf8

    if (-not $script:TFindTranscriptStarted) {
        try {
            Start-Transcript -Path $env:TFIND_CURRENT_LOG -Append -ErrorAction Stop | Out-Null
            $script:TFindTranscriptStarted = $true
        } catch {
            Write-Verbose "tfind could not start Start-Transcript automatically."
        }
    }
}

function global:Disable-TFindCapture {
    if ($script:TFindTranscriptStarted) {
        Stop-Transcript | Out-Null
        $script:TFindTranscriptStarted = $false
    }
}

TFind-EnsurePythonPath
Enable-TFindCapture

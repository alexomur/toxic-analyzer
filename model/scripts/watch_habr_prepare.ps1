param(
    [string]$ProjectRoot = "C:\Users\Alexomur\Desktop\projects\toxic-analyzer",
    [int]$CheckIntervalSeconds = 60,
    [int]$StallMinutes = 20
)

$ErrorActionPreference = "Stop"

$modelRoot = Join-Path $ProjectRoot "model"
$pythonExe = Join-Path $modelRoot ".venv312\Scripts\python.exe"
$configPath = Join-Path $modelRoot "configs\habr_comments.toml"
$outputPath = Join-Path $modelRoot "data\processed\habr_comments_russian_annotation_pool.jsonl"
$reportPath = Join-Path $modelRoot "artifacts\habr_comments_preparation_report.json"
$progressPath = Join-Path $modelRoot "artifacts\habr_comments_preparation_progress.json"
$watchdogLog = Join-Path $modelRoot "artifacts\habr_comments_watchdog.log"
$hubCacheDataDir = Join-Path $env:USERPROFILE ".cache\huggingface\hub\datasets--IlyaGusev--habr\snapshots\fef3b1e7f2d1e967d4771669be64e7ce3d280a39\data"

function Write-Log {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
    $line = "$timestamp $Message"
    Add-Content -Path $watchdogLog -Value $line -Encoding UTF8
}

function Get-PreparationProcesses {
    $processes = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*toxic_analyzer.prepare_habr_comments*" }

    $cpuById = @{}
    foreach ($proc in Get-Process -Name python -ErrorAction SilentlyContinue) {
        $cpuById[$proc.Id] = $proc.CPU
    }

    return $processes |
        Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine,
            @{Name = "Cpu"; Expression = { if ($cpuById.ContainsKey($_.ProcessId)) { $cpuById[$_.ProcessId] } else { 0 } } }
}

function Get-LeafWorkers {
    param([array]$Processes)

    $parentIds = @($Processes.ParentProcessId)
    return $Processes | Where-Object { $_.ProcessId -notin $parentIds }
}

function Stop-PreparationProcesses {
    $processes = Get-PreparationProcesses
    $ordered = $processes | Sort-Object ProcessId -Descending
    foreach ($proc in $ordered) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Log "Stopped process $($proc.ProcessId)"
        } catch {
            Write-Log "Failed to stop process $($proc.ProcessId): $($_.Exception.Message)"
        }
    }
}

function Get-ResumeShard {
    if (Test-Path $progressPath) {
        $progress = Get-Content $progressPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($progress.next_shard_index) {
            return [int]$progress.next_shard_index
        }
    }

    if (Test-Path $hubCacheDataDir) {
        $latest = Get-ChildItem $hubCacheDataDir -Filter "train-*.parquet" |
            Sort-Object Name -Descending |
            Select-Object -First 1

        if ($latest -and $latest.Name -match "train-(\d+)-of-\d+\.parquet") {
            return ([int]$Matches[1]) + 1
        }
    }

    return 1
}

function Start-PreparationResume {
    $startShard = Get-ResumeShard
    $arguments = @(
        "-m",
        "toxic_analyzer.prepare_habr_comments",
        "--config",
        $configPath,
        "--resume",
        "--start-shard",
        $startShard
    )

    Write-Log "Starting resume from shard $startShard"
    Start-Process -FilePath $pythonExe -ArgumentList $arguments -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
}

function Remove-DuplicateWorkers {
    $processes = Get-PreparationProcesses
    if ($processes.Count -le 2) {
        return
    }

    $leafWorkers = Get-LeafWorkers -Processes $processes | Sort-Object Cpu -Descending
    $keepWorker = $leafWorkers | Select-Object -First 1

    foreach ($proc in $leafWorkers | Select-Object -Skip 1) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Log "Stopped duplicate worker $($proc.ProcessId); keeping $($keepWorker.ProcessId)"
        } catch {
            Write-Log "Failed to stop duplicate worker $($proc.ProcessId): $($_.Exception.Message)"
        }
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path $watchdogLog -Parent) | Out-Null
Write-Log "Watchdog started. interval=${CheckIntervalSeconds}s stall=${StallMinutes}m"

$lastSize = if (Test-Path $outputPath) { (Get-Item $outputPath).Length } else { 0 }
$lastProgressAt = Get-Date

while ($true) {
    if (Test-Path $reportPath) {
        Write-Log "Report detected. Watchdog exiting."
        break
    }

    Remove-DuplicateWorkers
    $processes = Get-PreparationProcesses
    $leafWorkers = Get-LeafWorkers -Processes $processes

    if ($leafWorkers.Count -eq 0) {
        Write-Log "No active worker found. Launching resume."
        Start-PreparationResume
        Start-Sleep -Seconds $CheckIntervalSeconds
        continue
    }

    $currentSize = if (Test-Path $outputPath) { (Get-Item $outputPath).Length } else { 0 }
    if ($currentSize -gt $lastSize) {
        $lastSize = $currentSize
        $lastProgressAt = Get-Date
        Write-Log "Progress observed. output_size=$currentSize"
    } else {
        $minutesWithoutProgress = ((Get-Date) - $lastProgressAt).TotalMinutes
        if ($minutesWithoutProgress -ge $StallMinutes) {
            Write-Log "Stall detected (${minutesWithoutProgress}m without output growth). Restarting."
            Stop-PreparationProcesses
            Start-Sleep -Seconds 5
            Start-PreparationResume
            $lastProgressAt = Get-Date
        }
    }

    Start-Sleep -Seconds $CheckIntervalSeconds
}

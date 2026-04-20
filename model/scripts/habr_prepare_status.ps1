param(
    [string]$ProjectRoot = "C:\Users\Alexomur\Desktop\projects\toxic-analyzer"
)

$ErrorActionPreference = "Stop"

$modelRoot = Join-Path $ProjectRoot "model"
$outputPath = Join-Path $modelRoot "data\processed\habr_comments_russian_annotation_pool.jsonl"
$reportPath = Join-Path $modelRoot "artifacts\habr_comments_preparation_report.json"
$progressPath = Join-Path $modelRoot "artifacts\habr_comments_preparation_progress.json"
$watchdogLog = Join-Path $modelRoot "artifacts\habr_comments_watchdog.log"
$hubCacheDataDir = Join-Path $env:USERPROFILE ".cache\huggingface\hub\datasets--IlyaGusev--habr\snapshots\fef3b1e7f2d1e967d4771669be64e7ce3d280a39\data"

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

function Get-WatchdogProcesses {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -like "powershell*" -and $_.CommandLine -like "*watch_habr_prepare.ps1*" } |
        Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine
}

Write-Output "=== Habr Prepare Status ==="
Write-Output ("Checked at: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"))
Write-Output ""

$workers = Get-PreparationProcesses
Write-Output ("Workers: " + $workers.Count)
if ($workers.Count -gt 0) {
    $workers | Sort-Object Cpu -Descending | Format-Table ProcessId, ParentProcessId, CreationDate, Cpu -AutoSize | Out-String | Write-Output
} else {
    Write-Output "No active prepare_habr_comments workers found."
}

$watchdogs = Get-WatchdogProcesses
Write-Output ("Watchdogs: " + $watchdogs.Count)
if ($watchdogs.Count -gt 0) {
    $watchdogs | Format-Table ProcessId, ParentProcessId, CreationDate -AutoSize | Out-String | Write-Output
} else {
    Write-Output "No watchdog process found."
}

if (Test-Path $outputPath) {
    $item = Get-Item $outputPath
    $sizeGb = [math]::Round($item.Length / 1GB, 3)
    Write-Output "Output file:"
    Write-Output ("  Path: " + $item.FullName)
    Write-Output ("  Size bytes: " + $item.Length)
    Write-Output ("  Size GB: " + $sizeGb)
    Write-Output ("  LastWriteTime: " + $item.LastWriteTime)
} else {
    Write-Output "Output file is missing."
}

if (Test-Path $progressPath) {
    $progress = Get-Content $progressPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Output "Progress checkpoint:"
    Write-Output ("  Status: " + $progress.status)
    Write-Output ("  Last completed shard: " + $progress.last_completed_shard_index)
    Write-Output ("  Next shard: " + $progress.next_shard_index)
    Write-Output ("  Total shards: " + $progress.total_shards)
    if ($progress.counters.comments_kept) {
        Write-Output ("  Kept comments: " + $progress.counters.comments_kept)
    }
} else {
    Write-Output "Progress checkpoint is missing."
}

if (Test-Path $hubCacheDataDir) {
    $cached = Get-ChildItem $hubCacheDataDir -Filter "train-*.parquet" | Sort-Object Name
    Write-Output ("Cached shards: " + $cached.Count)
    if ($cached.Count -gt 0) {
        $lastCached = $cached | Select-Object -Last 1
        Write-Output ("  Last cached shard: " + $lastCached.Name)
        Write-Output ("  Cached at: " + $lastCached.LastWriteTime)
    }
} else {
    Write-Output "HF cache directory not found yet."
}

if (Test-Path $watchdogLog) {
    Write-Output ""
    Write-Output "Watchdog tail:"
    Get-Content $watchdogLog -Tail 10 | ForEach-Object { Write-Output ("  " + $_) }
} else {
    Write-Output "Watchdog log is missing."
}

Write-Output ""
if (Test-Path $reportPath) {
    Write-Output "Final report exists."
    Write-Output ("  " + $reportPath)
} else {
    Write-Output "Final report not created yet."
}

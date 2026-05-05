<#
.SYNOPSIS
    SysInfo Skill — Windows hardware configuration collector
    Version: 1.0.0
    Writes: hardware-report.json (current directory)
    Safe: read-only, no network calls, no secret collection
#>
param(
    [switch]$GPU,
    [switch]$Temps,
    [switch]$Bench
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'SilentlyContinue'

$SCRIPT_VERSION = '1.0.0'
$OUT_FILE = if ($env:SYSINFO_OUT) { $env:SYSINFO_OUT } else { 'hardware-report.json' }
$GeneratedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$HostnameVal = $env:COMPUTERNAME

function Sanitize([string]$s) {
    # escape double-quotes for JSON embedding
    $s -replace '\\', '\\' -replace '"', '\"' -replace "`n", ' ' -replace "`r", ''
}

function Trunc([string]$s, [int]$max = 4000) {
    if ($s.Length -gt $max) { return $s.Substring(0, $max) + '[truncated]' }
    return $s
}

# ─── OS Baseline ──────────────────────────────────────────────────────────────
function Get-OsInfo {
    $os  = Get-CimInstance Win32_OperatingSystem
    $tz  = (Get-TimeZone).Id
    $boot = $os.LastBootUpTime
    $uptime = [int]([datetime]::UtcNow - $boot.ToUniversalTime()).TotalSeconds
    [ordered]@{
        name          = Sanitize $os.Caption
        version       = Sanitize $os.Version
        build         = Sanitize $os.BuildNumber
        architecture  = Sanitize $os.OSArchitecture
        install_date  = $os.InstallDate.ToString('yyyy-MM-dd')
        locale        = Sanitize (Get-WinUserLanguageList | Select-Object -First 1 -ExpandProperty LanguageTag -ErrorAction SilentlyContinue)
        timezone      = Sanitize $tz
        uptime_seconds = $uptime
    }
}

# ─── CPU ──────────────────────────────────────────────────────────────────────
function Get-CpuInfo {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $logicalCores = (Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
    [ordered]@{
        model           = Sanitize $cpu.Name.Trim()
        architecture    = 'x86_64'
        physical_cores  = $cpu.NumberOfCores
        logical_cores   = $logicalCores
        base_ghz        = [math]::Round($cpu.MaxClockSpeed / 1000, 2)
        l2_cache_kb     = $cpu.L2CacheSize
        l3_cache_kb     = $cpu.L3CacheSize
        socket          = Sanitize $cpu.SocketDesignation
        manufacturer    = Sanitize $cpu.Manufacturer
    }
}

# ─── Memory ──────────────────────────────────────────────────────────────────
function Get-MemoryInfo {
    $os = Get-CimInstance Win32_OperatingSystem
    $totalGB  = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $availGB  = [math]::Round($os.FreePhysicalMemory / 1MB, 1)

    $modules = @(Get-CimInstance Win32_PhysicalMemory)
    $slotsUsed  = ($modules | Where-Object { $_.Capacity -gt 0 }).Count
    $slotsTotal = (Get-CimInstance Win32_PhysicalMemoryArray | Select-Object -First 1).MemoryDevices
    $speedMts   = ($modules | Select-Object -First 1).ConfiguredClockSpeed
    $memType    = switch (($modules | Select-Object -First 1).SMBIOSMemoryType) {
        26 { 'DDR4' }
        34 { 'DDR5' }
        21 { 'DDR3' }
        20 { 'DDR2' }
        default { 'Unknown' }
    }
    $eccRaw = (Get-CimInstance Win32_PhysicalMemoryArray | Select-Object -First 1).MemoryErrorCorrection
    $ecc = if ($eccRaw -ge 4) { 'Yes' } else { 'No' }

    [ordered]@{
        total_gb    = $totalGB
        available_gb = $availGB
        slots_used  = $slotsUsed
        slots_total = $slotsTotal
        speed_mts   = $speedMts
        type        = $memType
        ecc         = $ecc
    }
}

# ─── Storage ─────────────────────────────────────────────────────────────────
function Get-StorageInfo {
    $disks = Get-CimInstance Win32_DiskDrive | ForEach-Object {
        $sizeGB = [math]::Round($_.Size / 1GB, 1)
        $serial = $_.SerialNumber -replace '^\s+|\s+$', ''
        $serialMasked = if ($serial.Length -gt 4) { '****' + $serial.Substring($serial.Length - 4) } else { '****' }
        [ordered]@{
            model         = Sanitize $_.Model.Trim()
            interface     = Sanitize $_.InterfaceType
            size_gb       = $sizeGB
            serial_last4  = Sanitize $serialMasked
            partitions    = $_.Partitions
            media_type    = Sanitize $_.MediaType
        }
    }
    $disks
}

# ─── GPU ─────────────────────────────────────────────────────────────────────
function Get-GpuInfo {
    Get-CimInstance Win32_VideoController | ForEach-Object {
        $vramGB = if ($_.AdapterRAM -gt 0) { [math]::Round($_.AdapterRAM / 1GB, 1) } else { 'unknown' }
        [ordered]@{
            model          = Sanitize $_.Name
            vram_gb        = $vramGB
            driver_version = Sanitize $_.DriverVersion
            resolution     = "$($_.CurrentHorizontalResolution)x$($_.CurrentVerticalResolution)"
            refresh_hz     = $_.CurrentRefreshRate
        }
    }
}

# ─── Network ─────────────────────────────────────────────────────────────────
function Get-NetworkInfo {
    Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -eq $true } | ForEach-Object {
        $mac = $_.MACAddress
        $macMasked = if ($mac -and $mac.Length -ge 8) {
            '**:**:**:' + ($mac -split ':' | Select-Object -Last 3) -join ':'
        } else { 'unknown' }
        $speed = if ($_.Speed) { [math]::Round($_.Speed / 1MB, 0).ToString() + ' Mbps' } else { 'unknown' }
        [ordered]@{
            name         = Sanitize $_.Name
            mac_partial  = $macMasked
            link_speed   = $speed
            adapter_type = Sanitize $_.AdapterType
        }
    }
}

# ─── Motherboard / BIOS ──────────────────────────────────────────────────────
function Get-BoardInfo {
    $board = Get-CimInstance Win32_BaseBoard
    $bios  = Get-CimInstance Win32_BIOS
    $sb    = try { (Confirm-SecureBootUEFI 2>$null) } catch { $null }
    $sbState = if ($null -eq $sb) { 'unknown' } elseif ($sb) { 'enabled' } else { 'disabled' }
    [ordered]@{
        board_manufacturer = Sanitize $board.Manufacturer
        board_model        = Sanitize $board.Product
        board_version      = Sanitize $board.Version
        bios_vendor        = Sanitize $bios.Manufacturer
        bios_version       = Sanitize $bios.SMBIOSBIOSVersion
        bios_release_date  = $bios.ReleaseDate.ToString('yyyy-MM-dd')
        secure_boot        = $sbState
    }
}

# ─── Thermal sensors (optional) ──────────────────────────────────────────────
function Get-ThermalInfo {
    $sensors = Get-CimInstance -Namespace 'root/WMI' MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue
    if ($sensors) {
        $sensors | ForEach-Object {
            $celsius = [math]::Round(($_.CurrentTemperature - 2732) / 10, 1)
            [ordered]@{ zone = Sanitize $_.InstanceName; celsius = $celsius }
        }
    } else {
        @([ordered]@{ zone = 'unavailable'; note = 'WMI thermal data not exposed by firmware' })
    }
}

# ─── CPU benchmark (optional) ────────────────────────────────────────────────
function Get-BenchInfo {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $count = 0
    $limit = [DateTime]::UtcNow.AddSeconds(5)
    while ([DateTime]::UtcNow -lt $limit) {
        # lightweight compute: integer multiply loop
        $x = 1
        for ($i = 1; $i -le 1000; $i++) { $x = ($x * $i) % 999983 }
        $count++
    }
    $sw.Stop()
    [ordered]@{
        tool              = 'powershell_loop'
        iterations        = $count
        duration_seconds  = [math]::Round($sw.Elapsed.TotalSeconds, 2)
        loops_per_second  = [math]::Round($count / $sw.Elapsed.TotalSeconds, 0)
    }
}

# ─── Assemble report ─────────────────────────────────────────────────────────
$report = [ordered]@{
    meta = [ordered]@{
        script_version = $SCRIPT_VERSION
        generated_at   = $GeneratedAt
        hostname       = $HostnameVal
        os_type        = 'windows'
    }
    os        = Get-OsInfo
    cpu       = Get-CpuInfo
    memory    = Get-MemoryInfo
    storage   = @(Get-StorageInfo)
    gpu       = if ($GPU)   { @(Get-GpuInfo)    } else { @([ordered]@{ skipped = 'pass -GPU to collect' }) }
    network   = @(Get-NetworkInfo)
    board     = Get-BoardInfo
    thermals  = if ($Temps) { @(Get-ThermalInfo) } else { @([ordered]@{ skipped = 'pass -Temps to collect' }) }
    benchmark = if ($Bench) { Get-BenchInfo      } else { [ordered]@{ skipped = 'pass -Bench to run' } }
}

$json = $report | ConvertTo-Json -Depth 6
$json | Out-File -FilePath $OUT_FILE -Encoding utf8 -Force
Write-Host "SysInfo: hardware-report.json written to $((Get-Location).Path)\$OUT_FILE"

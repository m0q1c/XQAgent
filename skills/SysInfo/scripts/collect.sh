#!/usr/bin/env bash
# SysInfo Skill — Linux/macOS hardware collection script
# Version: 1.0.0
# Writes: hardware-report.json (current directory)
# Safe: read-only, no network calls, no secret collection

set -euo pipefail

SCRIPT_VERSION="1.0.0"
OPT_GPU=false
OPT_TEMPS=false
OPT_BENCH=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gpu)   OPT_GPU=true  ;;
    --temps) OPT_TEMPS=true ;;
    --bench) OPT_BENCH=true ;;
    *) echo "Unknown flag: $1" >&2 ; exit 1 ;;
  esac
  shift
done

OUT_FILE="${SYSINFO_OUT:-hardware-report.json}"
GENERATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOSTNAME_VAL=$(hostname 2>/dev/null || echo "unknown")

has_cmd() { command -v "$1" >/dev/null 2>&1; }

capture() {
  local out
  out=$("$@" 2>/dev/null || true)
  # truncate at 4000 chars
  if [ ${#out} -gt 4000 ]; then
    out="${out:0:4000}[truncated]"
  fi
  printf '%s' "$out"
}

# ─── Detect OS ───────────────────────────────────────────────────────────────
OS_TYPE="linux"
UNAME_S=$(uname -s 2>/dev/null || echo "Linux")
case "$UNAME_S" in
  Darwin) OS_TYPE="macos" ;;
  Linux)  OS_TYPE="linux" ;;
  *)      OS_TYPE="unknown" ;;
esac

# ─── OS Baseline ─────────────────────────────────────────────────────────────
collect_os_linux() {
  local name version kernel install_date uptime_s locale tz
  name=$(grep -oP '(?<=^PRETTY_NAME=").*(?=")' /etc/os-release 2>/dev/null \
         || cat /etc/issue 2>/dev/null | head -1 | tr -d '\n' \
         || echo "unknown")
  kernel=$(uname -r 2>/dev/null || echo "unknown")
  uptime_s=$(awk '{printf "%.0f", $1}' /proc/uptime 2>/dev/null || echo "0")
  install_date=$(stat -c '%y' /lost+found 2>/dev/null | cut -d' ' -f1 || echo "unknown")
  locale=$(locale 2>/dev/null | grep LANG= | head -1 | cut -d= -f2 || echo "unknown")
  tz=$(cat /etc/timezone 2>/dev/null || timedatectl show -p Timezone --value 2>/dev/null || echo "unknown")
  printf '{"name":"%s","kernel":"%s","uptime_seconds":%s,"install_date":"%s","locale":"%s","timezone":"%s"}' \
    "$name" "$kernel" "$uptime_s" "$install_date" "$locale" "$tz"
}

collect_os_macos() {
  local name kernel uptime_s
  name=$(sw_vers -productName 2>/dev/null || echo "macOS")
  ver=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
  build=$(sw_vers -buildVersion 2>/dev/null || echo "unknown")
  kernel=$(uname -r 2>/dev/null || echo "unknown")
  uptime_s=$(sysctl -n kern.boottime 2>/dev/null | awk -F'[=, ]' '{print $5}' \
    | awk -v now="$(date +%s)" '{print now - $1}' || echo "0")
  tz=$(readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' || echo "unknown")
  printf '{"name":"%s %s","build":"%s","kernel":"%s","uptime_seconds":%s,"timezone":"%s"}' \
    "$name" "$ver" "$build" "$kernel" "$uptime_s" "$tz"
}

# ─── CPU ─────────────────────────────────────────────────────────────────────
collect_cpu_linux() {
  local model phys_cores logical_cores arch
  model=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "unknown")
  phys_cores=$(grep -m1 'cpu cores' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "unknown")
  logical_cores=$(nproc 2>/dev/null || grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo "unknown")
  arch=$(uname -m 2>/dev/null || echo "unknown")
  local base_ghz max_ghz l1d_kb l2_kb l3_kb
  if has_cmd lscpu; then
    base_ghz=$(lscpu 2>/dev/null | awk -F: '/^CPU MHz/{printf "%.2f", $2/1000}' || echo "")
    max_ghz=$(lscpu 2>/dev/null | awk -F: '/^CPU max MHz/{printf "%.2f", $2/1000}' || echo "")
    l1d_kb=$(lscpu --caches 2>/dev/null | awk '/^L1d/{print $2}' || echo "")
    l2_kb=$(lscpu --caches 2>/dev/null | awk '/^L2/{print $2}' || echo "")
    l3_kb=$(lscpu --caches 2>/dev/null | awk '/^L3/{print $2}' || echo "")
  fi
  printf '{"model":"%s","architecture":"%s","physical_cores":%s,"logical_cores":%s,"base_ghz":"%s","max_ghz":"%s","l1d_cache":"%s","l2_cache":"%s","l3_cache":"%s"}' \
    "$model" "$arch" "${phys_cores:-0}" "${logical_cores:-0}" \
    "${base_ghz:-unknown}" "${max_ghz:-unknown}" \
    "${l1d_kb:-unknown}" "${l2_kb:-unknown}" "${l3_kb:-unknown}"
}

collect_cpu_macos() {
  local model phys logical arch base_ghz
  model=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || system_profiler SPHardwareDataType 2>/dev/null | awk -F: '/Chip/{print $2}' | xargs || echo "unknown")
  phys=$(sysctl -n hw.physicalcpu 2>/dev/null || echo "0")
  logical=$(sysctl -n hw.logicalcpu 2>/dev/null || echo "0")
  arch=$(uname -m 2>/dev/null || echo "unknown")
  base_ghz=$(sysctl -n hw.cpufrequency_max 2>/dev/null | awk '{printf "%.2f", $1/1e9}' || echo "unknown")
  l2=$(sysctl -n hw.l2cachesize 2>/dev/null | awk '{printf "%d KB", $1/1024}' || echo "unknown")
  l3=$(sysctl -n hw.l3cachesize 2>/dev/null | awk '{printf "%d KB", $1/1024}' || echo "unknown")
  printf '{"model":"%s","architecture":"%s","physical_cores":%s,"logical_cores":%s,"base_ghz":"%s","l2_cache":"%s","l3_cache":"%s"}' \
    "$model" "$arch" "$phys" "$logical" "$base_ghz" "$l2" "$l3"
}

# ─── Memory ──────────────────────────────────────────────────────────────────
collect_memory_linux() {
  local total_kb avail_kb total_gb avail_gb
  total_kb=$(awk '/^MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo "0")
  avail_kb=$(awk '/^MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo "0")
  total_gb=$(awk "BEGIN{printf \"%.1f\", $total_kb/1048576}")
  avail_gb=$(awk "BEGIN{printf \"%.1f\", $avail_kb/1048576}")
  local slots_used slots_total speed ecc
  slots_used="unknown"; slots_total="unknown"; speed="unknown"; ecc="unknown"
  if has_cmd dmidecode && [ "$(id -u)" -eq 0 ]; then
    slots_total=$(dmidecode -t memory 2>/dev/null | grep -c 'Memory Device$' || echo "unknown")
    slots_used=$(dmidecode -t memory 2>/dev/null | grep -c 'Size:.*GB\|Size:.*MB' || echo "unknown")
    speed=$(dmidecode -t memory 2>/dev/null | grep -m1 'Speed:' | awk '{print $2, $3}' || echo "unknown")
    ecc=$(dmidecode -t memory 2>/dev/null | grep -m1 'Error Correction' | cut -d: -f2 | xargs || echo "unknown")
  fi
  printf '{"total_gb":"%s","available_gb":"%s","slots_used":"%s","slots_total":"%s","speed_mts":"%s","ecc":"%s"}' \
    "$total_gb" "$avail_gb" "$slots_used" "$slots_total" "$speed" "$ecc"
}

collect_memory_macos() {
  local total_bytes total_gb avail_gb
  total_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
  total_gb=$(awk "BEGIN{printf \"%.1f\", $total_bytes/1073741824}")
  avail_gb=$(vm_stat 2>/dev/null | awk '
    /Pages free/{free=$3}
    /Pages inactive/{inact=$3}
    END{printf "%.1f", (free+inact)*4096/1073741824}' || echo "unknown")
  local speed type
  speed=$(system_profiler SPMemoryDataType 2>/dev/null | awk -F: '/Speed/{print $2; exit}' | xargs || echo "unknown")
  type=$(system_profiler SPMemoryDataType 2>/dev/null | awk -F: '/Type/{print $2; exit}' | xargs || echo "unknown")
  printf '{"total_gb":"%s","available_gb":"%s","speed_mts":"%s","type":"%s"}' \
    "$total_gb" "$avail_gb" "$speed" "$type"
}

# ─── Storage ─────────────────────────────────────────────────────────────────
collect_storage_linux() {
  local disks
  if has_cmd lsblk; then
    disks=$(lsblk -d -o NAME,MODEL,SIZE,ROTA,TRAN,SERIAL 2>/dev/null \
      | grep -v '^loop\|^sr' \
      | head -20 \
      | sed 's/"/\\"/g' \
      | awk 'NR>1{printf "{\"name\":\"%s\",\"model\":\"%s\",\"size\":\"%s\",\"rotational\":\"%s\",\"transport\":\"%s\",\"serial_last4\":\"%s\"},",
               $1, $2, $3, $4, $5, substr($6,length($6)-3)}' \
      | sed 's/,$//')
    # SMART health (best-effort)
    if has_cmd smartctl && [ "$(id -u)" -eq 0 ]; then
      local first_disk
      first_disk=$(lsblk -d -o NAME 2>/dev/null | grep -v 'loop\|sr\|NAME' | head -1)
      local smart_health
      smart_health=$(smartctl -H "/dev/$first_disk" 2>/dev/null | grep -oP '(PASSED|FAILED|OK)' | head -1 || echo "unknown")
      disks="${disks% }"  # trim trailing space, health will be appended separately
    fi
  else
    disks=''
  fi
  printf '[%s]' "${disks:-}"
}

collect_storage_macos() {
  local disks
  if has_cmd diskutil; then
    disks=$(diskutil list 2>/dev/null \
      | awk '/^\/dev\/disk[0-9]+ \(/{name=$1; gsub(/[()]/,"",$2); type=$2} /^\s+[0-9]+:/{size=$3; unit=$4; print name, type, size, unit}' \
      | head -20 \
      | awk '{printf "{\"disk\":\"%s\",\"type\":\"%s\",\"size\":\"%s %s\"},", $1, $2, $3, $4}' \
      | sed 's/,$//')
  else
    disks=''
  fi
  printf '[%s]' "${disks:-}"
}

# ─── GPU (optional) ──────────────────────────────────────────────────────────
collect_gpu_linux() {
  local gpu
  if has_cmd lspci; then
    gpu=$(lspci 2>/dev/null | grep -iE 'VGA|3D|Display' | head -5 \
      | sed 's/"/\\"/g' \
      | awk '{printf "{\"pci_entry\":\"%s\"},", $0}' \
      | sed 's/,$//')
  fi
  printf '[%s]' "${gpu:-}"
}

collect_gpu_macos() {
  local gpu
  gpu=$(system_profiler SPDisplaysDataType 2>/dev/null \
    | grep -E 'Chipset Model|VRAM|Resolution' \
    | sed 's/"/\\"/g' \
    | awk -F: '{printf "{\"field\":\"%s\",\"value\":\"%s\"},", $1, $2}' \
    | sed 's/,$//')
  printf '[%s]' "${gpu:-}"
}

# ─── Network ─────────────────────────────────────────────────────────────────
collect_network_linux() {
  local adapters
  if has_cmd ip; then
    adapters=$(ip -o link show 2>/dev/null | awk '{
      name=$2; gsub(/@.*/,"",name)
      mac=$17
      n=split(mac,a,":")
      # show only last 3 octets
      masked="**:**:**:" a[4] ":" a[5] ":" a[6]
      printf "{\"name\":\"%s\",\"mac_partial\":\"%s\"},", name, masked
    }' | sed 's/,$//')
  fi
  printf '[%s]' "${adapters:-}"
}

collect_network_macos() {
  local adapters
  adapters=$(networksetup -listallhardwareports 2>/dev/null \
    | awk '/Hardware Port/{port=$NF} /Ethernet Address/{mac=$NF; n=split(mac,a,":"); masked="**:**:**:"a[4]":"a[5]":"a[6]; printf "{\"port\":\"%s\",\"mac_partial\":\"%s\"},", port, masked}' \
    | sed 's/,$//')
  printf '[%s]' "${adapters:-}"
}

# ─── Motherboard / BIOS ──────────────────────────────────────────────────────
collect_board() {
  local board_mfr board_model bios_vendor bios_ver bios_date
  board_mfr="unknown"; board_model="unknown"; bios_vendor="unknown"; bios_ver="unknown"; bios_date="unknown"
  if has_cmd dmidecode && [ "$(id -u)" -eq 0 ]; then
    board_mfr=$(dmidecode -s baseboard-manufacturer 2>/dev/null | head -1 || echo "unknown")
    board_model=$(dmidecode -s baseboard-product-name 2>/dev/null | head -1 || echo "unknown")
    bios_vendor=$(dmidecode -s bios-vendor 2>/dev/null | head -1 || echo "unknown")
    bios_ver=$(dmidecode -s bios-version 2>/dev/null | head -1 || echo "unknown")
    bios_date=$(dmidecode -s bios-release-date 2>/dev/null | head -1 || echo "unknown")
  elif [ "$OS_TYPE" = "macos" ]; then
    board_model=$(system_profiler SPHardwareDataType 2>/dev/null | awk -F: '/Model Identifier/{print $2}' | xargs || echo "unknown")
    bios_ver=$(system_profiler SPiBridgeDataType 2>/dev/null | awk -F: '/System Firmware/{print $2}' | xargs || echo "unknown")
  fi
  printf '{"board_manufacturer":"%s","board_model":"%s","bios_vendor":"%s","bios_version":"%s","bios_release_date":"%s"}' \
    "$board_mfr" "$board_model" "$bios_vendor" "$bios_ver" "$bios_date"
}

# ─── Thermal sensors (optional) ──────────────────────────────────────────────
collect_temps_linux() {
  if has_cmd sensors; then
    local out
    out=$(sensors 2>/dev/null | grep -E '°C|\+[0-9]+' | head -20 | sed 's/"/\\"/g' | tr '\n' '|')
    printf '{"raw":"%s"}' "${out:-unavailable}"
  else
    printf '{"raw":"lm-sensors not installed"}'
  fi
}

collect_temps_macos() {
  # macOS does not expose temps without third-party tools
  printf '{"raw":"not available on macOS without third-party tools"}'
}

# ─── CPU benchmark (optional) ────────────────────────────────────────────────
collect_bench() {
  if has_cmd sysbench; then
    local result
    result=$(sysbench --test=cpu --cpu-max-prime=20000 --time=5 run 2>/dev/null \
      | grep -E 'total time|events per second' | tr '\n' '|')
    printf '{"tool":"sysbench","result":"%s"}' "${result:-failed}"
  else
    # Fallback: pure bash timing
    local start end elapsed count
    start=$(date +%s%N 2>/dev/null || echo "0")
    count=0
    local end_t=$(( $(date +%s) + 5 ))
    while [ "$(date +%s)" -lt "$end_t" ]; do
      count=$(( count + 1 ))
      # intentional lightweight busy-wait
      echo "$count" > /dev/null
    done
    end=$(date +%s%N 2>/dev/null || echo "0")
    printf '{"tool":"bash_loop","iterations":%d,"duration_seconds":5}' "$count"
  fi
}

# ─── Assemble JSON ────────────────────────────────────────────────────────────
{
  printf '{\n'
  printf '  "meta": {"script_version":"%s","generated_at":"%s","hostname":"%s","os_type":"%s"},\n' \
    "$SCRIPT_VERSION" "$GENERATED_AT" "$HOSTNAME_VAL" "$OS_TYPE"

  # OS
  printf '  "os": '
  if [ "$OS_TYPE" = "macos" ]; then collect_os_macos; else collect_os_linux; fi
  printf ',\n'

  # CPU
  printf '  "cpu": '
  if [ "$OS_TYPE" = "macos" ]; then collect_cpu_macos; else collect_cpu_linux; fi
  printf ',\n'

  # Memory
  printf '  "memory": '
  if [ "$OS_TYPE" = "macos" ]; then collect_memory_macos; else collect_memory_linux; fi
  printf ',\n'

  # Storage
  printf '  "storage": '
  if [ "$OS_TYPE" = "macos" ]; then collect_storage_macos; else collect_storage_linux; fi
  printf ',\n'

  # GPU
  printf '  "gpu": '
  if $OPT_GPU; then
    if [ "$OS_TYPE" = "macos" ]; then collect_gpu_macos; else collect_gpu_linux; fi
  else
    printf '{"skipped":"pass --gpu to collect"}'
  fi
  printf ',\n'

  # Network
  printf '  "network": '
  if [ "$OS_TYPE" = "macos" ]; then collect_network_macos; else collect_network_linux; fi
  printf ',\n'

  # Board / BIOS
  printf '  "board": '
  collect_board
  printf ',\n'

  # Temps
  printf '  "thermals": '
  if $OPT_TEMPS; then
    if [ "$OS_TYPE" = "macos" ]; then collect_temps_macos; else collect_temps_linux; fi
  else
    printf '{"skipped":"pass --temps to collect"}'
  fi
  printf ',\n'

  # Bench
  printf '  "benchmark": '
  if $OPT_BENCH; then
    collect_bench
  else
    printf '{"skipped":"pass --bench to run"}'
  fi
  printf '\n'

  printf '}\n'
} > "$OUT_FILE"

echo "SysInfo: hardware-report.json written to $(pwd)/$OUT_FILE"

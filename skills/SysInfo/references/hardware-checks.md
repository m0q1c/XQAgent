# Hardware Checks

Evaluate every check below using `hardware-report.json`. Emit anomaly rows only for triggered checks.

---

## CPU

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-CPU-01 | Very old architecture | `cpu.architecture` is not `x86_64` or `arm64` | NOTICE | Verify compatibility with current software |
| HW-CPU-02 | Single physical core | `cpu.physical_cores` == 1 | WARNING | Multi-threaded workloads will be severely constrained |
| HW-CPU-03 | Thermal throttle risk | `thermals[*].celsius` > 90 | WARNING | Check cooling, reapply thermal paste |
| HW-CPU-04 | Benchmark unusually low | `benchmark.loops_per_second` < 500 (if collected) | NOTICE | Possible thermal throttle or background load |

---

## Memory

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-MEM-01 | Very low total RAM | `memory.total_gb` < 4 | WARNING | Modern OS and apps require ≥ 8 GB for comfortable use |
| HW-MEM-02 | Low available RAM | `memory.available_gb` / `memory.total_gb` < 0.1 | WARNING | Less than 10 % free — check for memory leaks |
| HW-MEM-03 | Single-channel (one slot used) | `memory.slots_used` == 1 and `memory.slots_total` >= 2 | NOTICE | Adding a matched DIMM enables dual-channel for ~15 % bandwidth gain |
| HW-MEM-04 | No ECC on server workload | `memory.ecc` == "No" and hostname matches server naming pattern | NOTICE | ECC memory reduces risk of silent data corruption |

---

## Storage

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-STG-01 | SMART failure | `disk.smart_health` == "FAILED" | CRITICAL | Back up immediately and replace the disk |
| HW-STG-02 | Very small disk | `disk.size_gb` < 32 | WARNING | Insufficient space for OS updates and application data |
| HW-STG-03 | Spinning HDD on primary | `disk.media_type` contains "Fixed Hard Disk" or `disk.interface` == "IDE" | NOTICE | Consider migration to SSD for significant performance improvement |
| HW-STG-04 | USB boot media detected | `disk.interface` == "USB" and is primary disk | NOTICE | USB boot is unreliable for production use |

---

## GPU / Display

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-GPU-01 | No dedicated GPU | All `gpu[*].vram_gb` == 0 or "unknown" | NOTICE | Integrated graphics only — GPU-intensive tasks will be slow |
| HW-GPU-02 | Driver version very old | Driver date > 2 years ago (compare to `meta.generated_at`) | NOTICE | Update GPU drivers to improve stability and security |

---

## Network

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-NET-01 | No physical adapters found | `network[]` is empty | WARNING | No network hardware detected — check device manager |
| HW-NET-02 | Very slow link | `adapter.link_speed` < 100 Mbps | NOTICE | 100 Mbps or slower NIC may bottleneck data transfer |

---

## Motherboard / BIOS

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-BRD-01 | BIOS release date > 5 years old | `board.bios_release_date` more than 5 years before `meta.generated_at` | NOTICE | Check vendor site for BIOS/UEFI updates to fix known vulnerabilities |
| HW-BRD-02 | Secure Boot disabled | `board.secure_boot` == "disabled" | NOTICE | Enable Secure Boot in UEFI settings to protect against bootkit attacks |
| HW-BRD-03 | Unknown board manufacturer | `board.board_manufacturer` == "unknown" | WARNING | dmidecode/WMI could not read board data; run with elevated privileges |

---

## OS Baseline

| ID | Check | Condition | Severity | Recommendation |
|---|---|---|---|---|
| HW-OS-01 | 32-bit OS on 64-bit CPU | `os.architecture` contains "32" and `cpu.architecture` == "x86_64" | NOTICE | Consider upgrading to 64-bit OS to use full RAM and modern software |
| HW-OS-02 | Very long uptime | `os.uptime_seconds` > 2592000 (30 days) | NOTICE | Reboot to apply pending OS and firmware updates |

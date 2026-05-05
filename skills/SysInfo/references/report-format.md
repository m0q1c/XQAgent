# Hardware Report Format

Use this template exactly when generating the Markdown summary from `hardware-report.json`.

---

## Hardware Report — `{meta.hostname}`
Generated: `{meta.generated_at}` | OS: `{os.name}` | Script: v`{meta.script_version}`

---

### CPU
| Field | Value |
|---|---|
| Model | `{cpu.model}` |
| Architecture | `{cpu.architecture}` |
| Physical Cores | `{cpu.physical_cores}` |
| Logical Cores | `{cpu.logical_cores}` |
| Base Clock | `{cpu.base_ghz}` GHz |
| Max / Boost | `{cpu.max_ghz}` GHz _(if available)_ |
| L2 Cache | `{cpu.l2_cache}` |
| L3 Cache | `{cpu.l3_cache}` |

---

### Memory
| Field | Value |
|---|---|
| Total | `{memory.total_gb}` GB |
| Available | `{memory.available_gb}` GB |
| Slots Used / Total | `{memory.slots_used}` / `{memory.slots_total}` |
| Speed | `{memory.speed_mts}` MT/s |
| Type | `{memory.type}` |
| ECC | `{memory.ecc}` |

---

### Storage
For each disk in `storage[]`:

| Field | Value |
|---|---|
| Model | `{disk.model}` |
| Interface | `{disk.interface}` |
| Capacity | `{disk.size_gb}` GB |
| Serial (last 4) | `{disk.serial_last4}` |
| Partitions | `{disk.partitions}` |
| SMART Health | `{disk.smart_health}` _(if available)_ |

---

### GPU / Display
_Shown only when `--gpu` / `-GPU` flag was used._

For each adapter in `gpu[]`:

| Field | Value |
|---|---|
| Model | `{gpu.model}` |
| VRAM | `{gpu.vram_gb}` GB |
| Driver Version | `{gpu.driver_version}` |
| Resolution | `{gpu.resolution}` |
| Refresh Rate | `{gpu.refresh_hz}` Hz |

---

### Network Adapters
For each adapter in `network[]`:

| Name | MAC (partial) | Speed | Type |
|---|---|---|---|
| `{adapter.name}` | `{adapter.mac_partial}` | `{adapter.link_speed}` | `{adapter.adapter_type}` |

---

### Motherboard & BIOS
| Field | Value |
|---|---|
| Board Manufacturer | `{board.board_manufacturer}` |
| Board Model | `{board.board_model}` |
| BIOS Vendor | `{board.bios_vendor}` |
| BIOS Version | `{board.bios_version}` |
| BIOS Release Date | `{board.bios_release_date}` |
| Secure Boot | `{board.secure_boot}` |

---

### OS Baseline
| Field | Value |
|---|---|
| Edition | `{os.name}` |
| Version / Build | `{os.version}` / `{os.build}` |
| Architecture | `{os.architecture}` |
| Install Date | `{os.install_date}` |
| Locale | `{os.locale}` |
| Timezone | `{os.timezone}` |
| Uptime | `{os.uptime_seconds}` seconds |

---

### Thermals
_Shown only when `--temps` / `-Temps` flag was used._

| Zone | Temperature |
|---|---|
| `{zone.zone}` | `{zone.celsius}` °C |

---

### Benchmark
_Shown only when `--bench` / `-Bench` flag was used._

| Field | Value |
|---|---|
| Tool | `{benchmark.tool}` |
| Duration | `{benchmark.duration_seconds}` s |
| Iterations | `{benchmark.iterations}` |
| Rate | `{benchmark.loops_per_second}` iter/s |

---

### Anomalies
Emit this section only when one or more anomaly checks from `references/hardware-checks.md` trigger.

| ID | Severity | Component | Finding | Recommendation |
|---|---|---|---|---|
| HW-xxx | NOTICE / WARNING / CRITICAL | component | brief finding | what to do |

If no anomalies found, write:
> No anomalies detected.

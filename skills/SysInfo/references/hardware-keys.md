# Hardware Report JSON Keys

Authoritative field names in `hardware-report.json`. Use these when citing evidence in the report.

---

## `meta`
| Key | Type | Description |
|---|---|---|
| `meta.script_version` | string | Version of the collection script |
| `meta.generated_at` | string (ISO 8601 UTC) | Timestamp when the report was generated |
| `meta.hostname` | string | Machine hostname |
| `meta.os_type` | string | `"windows"`, `"linux"`, or `"macos"` |

---

## `os`
| Key | Type | Description |
|---|---|---|
| `os.name` | string | Full OS display name |
| `os.version` | string | OS version string |
| `os.build` | string | Build number or kernel version |
| `os.architecture` | string | CPU architecture as reported by OS |
| `os.install_date` | string (YYYY-MM-DD) | OS installation date |
| `os.locale` | string | BCP 47 language tag |
| `os.timezone` | string | IANA timezone ID |
| `os.uptime_seconds` | integer | Seconds since last boot |
| `os.kernel` | string | Kernel release string (Linux/macOS) |

---

## `cpu`
| Key | Type | Description |
|---|---|---|
| `cpu.model` | string | Full CPU model name |
| `cpu.architecture` | string | `x86_64`, `arm64`, etc. |
| `cpu.physical_cores` | integer | Physical (die) core count |
| `cpu.logical_cores` | integer | Logical (hyper-threaded) core count |
| `cpu.base_ghz` | number | Base clock in GHz |
| `cpu.max_ghz` | number | Max boost clock in GHz (if available) |
| `cpu.l1d_cache` | string | L1 data cache size (e.g. `"48K"`) |
| `cpu.l2_cache` | string | L2 cache size |
| `cpu.l3_cache` | string | L3 cache size |
| `cpu.socket` | string | Socket designation |
| `cpu.manufacturer` | string | CPU manufacturer |

---

## `memory`
| Key | Type | Description |
|---|---|---|
| `memory.total_gb` | number | Total installed RAM in GB |
| `memory.available_gb` | number | Currently free/available RAM in GB |
| `memory.slots_used` | integer | Number of occupied DIMM slots |
| `memory.slots_total` | integer | Total DIMM slot count on board |
| `memory.speed_mts` | integer | Configured memory speed in MT/s |
| `memory.type` | string | Memory type (`DDR4`, `DDR5`, etc.) |
| `memory.ecc` | string | `"Yes"` or `"No"` |

---

## `storage[]` (array)
| Key | Type | Description |
|---|---|---|
| `disk.model` | string | Disk model name |
| `disk.interface` | string | Interface type (`NVMe`, `SATA`, `USB`, `IDE`) |
| `disk.size_gb` | number | Disk capacity in GB |
| `disk.serial_last4` | string | Last 4 characters of serial number |
| `disk.partitions` | integer | Number of partitions |
| `disk.media_type` | string | Reported media type string |
| `disk.smart_health` | string | `PASSED`, `FAILED`, or `unknown` |

---

## `gpu[]` (array, optional)
| Key | Type | Description |
|---|---|---|
| `gpu.model` | string | GPU/adapter model name |
| `gpu.vram_gb` | number | Dedicated VRAM in GB (`0` = integrated) |
| `gpu.driver_version` | string | Installed driver version string |
| `gpu.resolution` | string | Active display resolution (e.g. `"1920x1080"`) |
| `gpu.refresh_hz` | integer | Refresh rate in Hz |

---

## `network[]` (array)
| Key | Type | Description |
|---|---|---|
| `adapter.name` | string | Adapter display name |
| `adapter.mac_partial` | string | MAC with first 3 octets masked (`**:**:**:AA:BB:CC`) |
| `adapter.link_speed` | string | Link speed (e.g. `"1000 Mbps"`) |
| `adapter.adapter_type` | string | Adapter type description |

---

## `board`
| Key | Type | Description |
|---|---|---|
| `board.board_manufacturer` | string | Motherboard/system manufacturer |
| `board.board_model` | string | Motherboard/system model |
| `board.board_version` | string | Board revision |
| `board.bios_vendor` | string | BIOS/UEFI firmware vendor |
| `board.bios_version` | string | BIOS/UEFI firmware version string |
| `board.bios_release_date` | string (YYYY-MM-DD) | BIOS release date |
| `board.secure_boot` | string | `"enabled"`, `"disabled"`, or `"unknown"` |

---

## `thermals[]` (array, optional)
| Key | Type | Description |
|---|---|---|
| `zone.zone` | string | Thermal zone name |
| `zone.celsius` | number | Temperature in °C |

---

## `benchmark` (optional)
| Key | Type | Description |
|---|---|---|
| `benchmark.tool` | string | Benchmark tool used |
| `benchmark.iterations` | integer | Loop iterations completed in 5 seconds |
| `benchmark.duration_seconds` | number | Actual elapsed time |
| `benchmark.loops_per_second` | integer | Computed throughput |

---

## Sentinel values
| Value | Meaning |
|---|---|
| `"unknown"` | Data was not available from the system |
| `"NOT AVAILABLE"` | Key missing from `hardware-report.json` |
| `[truncated]` | Field value exceeded 4 000-character limit |
| `{"skipped": "..."}` | Optional section not collected (flag not passed) |

# SysInfo Skill

A read-only skill that collects and reports a **complete hardware configuration snapshot** of the local machine.

## What it collects

| Section | Details |
|---|---|
| **CPU** | Model, architecture, physical/logical core count, base & boost clock, cache sizes |
| **Memory** | Total/available RAM, slot count and populating, speed (MT/s), ECC support |
| **Storage** | Disk model, interface (NVMe/SATA/USB), capacity, SMART health summary, partition table |
| **GPU / Display** | Adapter model, VRAM, driver version, connected monitors and resolution |
| **Network** | Adapter name, link speed, MAC (partially redacted), IPv4/IPv6 |
| **Motherboard** | Manufacturer, model, chipset, form factor |
| **BIOS / UEFI** | Vendor, version, release date, Secure Boot state |
| **OS Baseline** | Edition, build/kernel, install date, locale, uptime, timezone |

## Installation

### With OpenClaw

```bash
cd ~/.openclaw/workspace
mkdir -p skills
git clone https://github.com/yourorg/sysinfo-skill.git skills/sysinfo
openclaw gateway restart
```

### Standalone

```bash
git clone https://github.com/yourorg/sysinfo-skill.git
cd sysinfo-skill
```

## Usage

### Linux / macOS

```bash
bash scripts/collect.sh
```

Optional flags:

```bash
bash scripts/collect.sh --gpu     # detailed GPU info
bash scripts/collect.sh --temps   # thermal sensors (requires lm-sensors)
bash scripts/collect.sh --bench   # 5-second CPU benchmark
```

### Windows (PowerShell)

```powershell
.\scripts\collect.ps1
# With options:
.\scripts\collect.ps1 -GPU -Temps -Bench
```

Both scripts write `hardware-report.json` in the current directory.

## Output files

| File | Description |
|---|---|
| `hardware-report.json` | Machine-readable structured report |
| _(stdout)_ | Human-readable Markdown summary printed to the terminal |

## Privacy and security

- **Read-only:** no system files are modified.
- **Local only:** nothing is sent to any remote server.
- **Partial redaction:** MAC addresses show only the last 3 octets; serial numbers show only the last 4 characters.
- **No credentials:** SSH keys, passwords, and browser data are never collected.

## Requirements

| Platform | Requirements |
|---|---|
| Linux | `bash`, `dmidecode` (optional, needs root for full BIOS info), `lscpu`, `lsblk`, `smartmontools` (optional) |
| macOS | `bash`, `system_profiler` (built-in) |
| Windows | PowerShell 5.1+, WMI/CIM (built-in) |

## Sample output

```
## Hardware Report — DESKTOP-ABC123
Generated: 2026-03-15T10:00:00Z | OS: Windows 11 Pro 23H2 | Script: v1.0.0

### CPU
| Field | Value |
|---|---|
| Model | AMD Ryzen 9 7950X |
| Architecture | x86_64 |
| Physical Cores | 16 |
| Logical Cores | 32 |
| Base Clock | 4.5 GHz |
| Max Boost | 5.7 GHz |
| L3 Cache | 64 MB |

### Memory
| Field | Value |
|---|---|
| Total | 64 GB |
| Available | 48 GB |
| Slots Used / Total | 2 / 4 |
| Speed | 5600 MT/s |
| ECC | No |
...
```

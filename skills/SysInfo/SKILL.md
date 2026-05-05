---
name: SysInfo
description: "Collect and report full hardware configuration of the local machine: CPU, memory, storage, GPU, network adapters, motherboard, BIOS/UEFI, and OS baseline. Produces a structured hardware-report.json and a human-readable summary."
name_zh: "系统信息"
description_zh: "收集和报告本机完整硬件配置：CPU、内存、存储、GPU、网络等。"
name_ja: "システム情報"
description_ja: "ローカルマシンの完全なハードウェア構成を収集・報告：CPU・メモリ・ストレージ・GPU・ネットワーク等。"
---

# SysInfo — System Hardware Configuration Skill

## Goal
Collect a complete, accurate snapshot of the host machine's hardware and OS configuration. Produce `hardware-report.json` and a formatted Markdown summary that can be pasted into a ticket, wiki, or AI chat.

## Non-negotiable safety rules
1. **Read-only.** Never write to, modify, or delete system files. Only read hardware/OS metadata.
2. **No remote calls.** Do not send collected data to any external URL. All output stays local.
3. **No secret collection.** Do not capture passwords, API keys, SSH private keys, or browser credentials.
4. **Cross-platform.** Run the appropriate script for the detected OS (see §Collection scripts).
5. **No privilege escalation.** Run as the current user. Omit checks that require root/Administrator unless the user explicitly launches with elevated rights.
6. **Truncate verbose output.** Any single field must not exceed 4 000 characters; truncate with `[truncated]`.

## Collection scripts
| OS | Script |
|---|---|
| Linux / macOS | `scripts/collect.sh` |
| Windows | `scripts/collect.ps1` |

### Auto-detection
1. Detect OS from the shell environment (`$OSTYPE`, `uname -s`, or `$env:OS`).
2. Run the matching script **without arguments** for a standard report.
3. Optional flags:
   - `--gpu`   — include detailed GPU/display adapter info (may be slow)
   - `--temps` — include thermal sensor readings (requires `lm-sensors` on Linux)
   - `--bench` — run a 5-second CPU benchmark via `sysbench` or PowerShell stopwatch

## Collection workflow
1. Run the collection script. It writes `hardware-report.json` in the current directory.
2. Read `hardware-report.json`. Do **not** generate the report without it.
3. Build the Markdown summary following `references/report-format.md`.
4. Evaluate every hardware section against the checks in `references/hardware-checks.md`.
5. Flag anomalies (mismatched RAM slots, very old firmware, degraded disk health) as **NOTICE**.

## Report sections (required)
Follow `references/report-format.md` for exact headings and table schemas.

1. **Header** — hostname, collection timestamp (UTC), OS, kernel/build, script version
2. **CPU** — model, physical/logical cores, base & boost GHz, cache hierarchy, architecture
3. **Memory** — total installed, available, slot layout, speed (MT/s), ECC status
4. **Storage** — each disk: model, interface, capacity, health (SMART summary), partitions
5. **GPU / Display** — adapter model, VRAM, driver version, connected displays
6. **Network** — each adapter: name, MAC (last 3 octets shown), link speed, IPv4/IPv6 presence
7. **Motherboard & BIOS** — manufacturer, model, BIOS vendor, version, release date
8. **OS Baseline** — edition, version, install date, locale, uptime, hostname, timezone
9. **Anomalies** — any NOTICE items with check ID, evidence, and recommendation

## Evidence requirements
- Every row in the summary table must cite the `hardware-report.json` key that provided it.
- If a key is missing, mark the field `NOT AVAILABLE` and note the reason.
- MAC addresses: show only the last 3 octets (e.g., `**:**:**:AA:BB:CC`).
- Serial numbers: redact all but last 4 characters (e.g., `S/N: ****1234`).

## Anomaly classification
Use `references/hardware-checks.md` for thresholds and remediation guidance.

| Severity | Meaning |
|---|---|
| NOTICE | Worth reviewing; not necessarily a problem |
| WARNING | Likely to cause instability or security risk |
| CRITICAL | Immediate action recommended |

## References (read as needed)
- `references/report-format.md` — exact Markdown template for the summary
- `references/hardware-checks.md` — anomaly thresholds and remediation notes
- `references/hardware-keys.md` — authoritative field names in `hardware-report.json`

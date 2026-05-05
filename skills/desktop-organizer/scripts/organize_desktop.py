#!/usr/bin/env python3
"""
organize_desktop.py — DesktopOrganizer Skill

Two modes:
  --dry-run   Read desktop-manifest.json, compute the move plan, write
              organizer-plan.json, and print a human-readable table.
              No files are moved.

  --execute   Read organizer-plan.json (must exist from a prior dry-run),
              execute every move operation, and write organizer-result.json.

Usage:
  python organize_desktop.py --dry-run
  python organize_desktop.py --execute
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    if not path.is_file():
        print(f"[ERROR] Required file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def unique_dest(dest: Path) -> Path:
    """If dest already exists, append _1, _2 … until a free name is found."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def load_user_config(desktop: Path) -> dict:
    config_path = desktop / "organizer-config.json"
    if config_path.is_file():
        try:
            with config_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Dry-run: build plan
# ---------------------------------------------------------------------------

def build_plan(manifest: dict) -> list[dict]:
    """
    Compute the list of move operations from a manifest.
    Returns:
      [{"src": "...", "dest": "...", "category": "...", "conflict": false}, ...]
    """
    desktop = Path(manifest["desktop_path"])
    user_config = load_user_config(desktop)
    target_root_str: str | None = user_config.get("target_dir")
    target_root = Path(target_root_str) if target_root_str else desktop

    # Track filenames already claimed in this plan to detect intra-run conflicts
    claimed: set[Path] = set()
    ops = []

    for file_info in manifest["files"]:
        name: str = file_info["name"]
        category: str = file_info["category"]
        src = desktop / name
        dest_dir = target_root / category
        dest = dest_dir / name

        # Resolve conflicts against existing files AND already-claimed plan slots
        if dest.exists() or dest in claimed:
            stem = dest.stem
            ext = dest.suffix
            counter = 1
            while True:
                candidate = dest_dir / f"{stem}_{counter}{ext}"
                if not candidate.exists() and candidate not in claimed:
                    dest = candidate
                    break
                counter += 1
            conflict = True
        else:
            conflict = False

        claimed.add(dest)
        ops.append({
            "src": str(src),
            "dest": str(dest),
            "category": category,
            "conflict": conflict,
            "original_name": name,
            "dest_name": dest.name,
        })

    return ops


def run_dry_run() -> None:
    manifest_path = Path("desktop-manifest.json")
    manifest = load_json(manifest_path)
    ops = build_plan(manifest)

    plan = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "desktop_path": manifest["desktop_path"],
        "total_operations": len(ops),
        "operations": ops,
    }

    plan_path = Path("organizer-plan.json")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Human-readable output ----
    print("=" * 60)
    print("桌面整理计划（预览，未实际移动）")
    print("=" * 60)
    print(f"桌面路径: {manifest['desktop_path']}")
    print(f"待整理文件: {len(ops)} 个\n")

    # Summary by category
    cat_counts: dict[str, int] = {}
    for op in ops:
        cat_counts[op["category"]] = cat_counts.get(op["category"], 0) + 1

    print(f"{'分类':<12} {'数量':>6}")
    print("-" * 20)
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"{cat:<12} {count:>6} 个")
    print()

    # Detailed move list
    print(f"{'文件名':<35} {'目标路径'}")
    print("-" * 80)
    for op in ops:
        src_name = op["original_name"]
        dest_display = os.path.join(op["category"], op["dest_name"])
        conflict_marker = " ⚠ 冲突重命名" if op["conflict"] else ""
        print(f"  {src_name:<33} → {dest_display}{conflict_marker}")

    if any(op["conflict"] for op in ops):
        print("\n⚠  带「冲突重命名」标记的文件因目标已存在同名文件，将自动改名后移入。")

    print()
    print(f"计划已保存到 {plan_path.resolve()}")
    print()
    print("若确认无误，请运行：")
    print("  python organize_desktop.py --execute")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Execute: apply plan
# ---------------------------------------------------------------------------

def run_execute() -> None:
    plan_path = Path("organizer-plan.json")
    plan = load_json(plan_path)

    ops = plan["operations"]
    results = []
    moved = 0
    skipped_missing = 0
    conflicts_renamed = 0
    errors = 0

    for op in ops:
        src = Path(op["src"])
        dest = Path(op["dest"])
        dest_dir = dest.parent

        # Verify source still exists
        if not src.is_file():
            results.append({**op, "status": "skipped", "reason": "source_not_found"})
            skipped_missing += 1
            continue

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            # Re-check conflict at execution time (another process may have added a file)
            dest = unique_dest(dest)
            if str(dest) != op["dest"]:
                conflicts_renamed += 1

            shutil.move(str(src), str(dest))
            results.append({**op, "actual_dest": str(dest), "status": "moved"})
            moved += 1

        except OSError as exc:
            results.append({**op, "status": "error", "reason": str(exc)})
            errors += 1

    result_doc = {
        "executed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "desktop_path": plan["desktop_path"],
        "summary": {
            "total_planned": len(ops),
            "moved": moved,
            "skipped_missing": skipped_missing,
            "conflicts_renamed": conflicts_renamed,
            "errors": errors,
        },
        "operations": results,
    }

    result_path = Path("organizer-result.json")
    result_path.write_text(json.dumps(result_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Human-readable report ----
    print("=" * 60)
    print("桌面整理完成报告")
    print("=" * 60)
    print(f"时间:       {result_doc['executed_at']}")
    print(f"桌面路径:   {plan['desktop_path']}")
    print(f"已移动:     {moved} 个文件")
    if skipped_missing:
        print(f"跳过（源文件不存在）: {skipped_missing} 个")
    if conflicts_renamed:
        print(f"冲突重命名: {conflicts_renamed} 个")
    if errors:
        print(f"错误:       {errors} 个")

    if errors:
        print("\n错误详情:")
        for r in results:
            if r["status"] == "error":
                print(f"  {r['original_name']}: {r.get('reason', '未知错误')}")

    print()
    print(f"详细日志已保存到 {result_path.resolve()}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    if "--dry-run" in args:
        run_dry_run()
    elif "--execute" in args:
        run_execute()
    else:
        print("用法：")
        print("  python organize_desktop.py --dry-run    预览移动计划")
        print("  python organize_desktop.py --execute    执行整理（需先运行 --dry-run）")
        sys.exit(1)


if __name__ == "__main__":
    main()

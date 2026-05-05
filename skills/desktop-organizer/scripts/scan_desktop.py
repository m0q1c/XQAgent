#!/usr/bin/env python3
"""
scan_desktop.py — DesktopOrganizer Skill
Scans the user's Desktop directory and produces desktop-manifest.json.

Output schema:
{
  "generated_at": "<ISO-8601>",
  "desktop_path": "<absolute path>",
  "files": [
    {
      "name": "photo.jpg",
      "ext": "jpg",
      "category": "图片",
      "size_bytes": 204800,
      "modified_at": "2024-01-01T10:00:00"
    },
    ...
  ],
  "skipped": ["desktop.ini", ".DS_Store"],
  "summary": {
    "total_files": 30,
    "total_size_bytes": 52428800,
    "by_category": {
      "图片": 12,
      "文档": 8,
      ...
    }
  }
}
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Default category mapping (extension → category name)
# Overridden per-entry in organizer-config.json when present.
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES: dict[str, str] = {
    # 图片
    "jpg": "图片", "jpeg": "图片", "png": "图片", "gif": "图片",
    "bmp": "图片", "webp": "图片", "svg": "图片", "ico": "图片",
    "tiff": "图片", "tif": "图片", "raw": "图片", "heic": "图片",
    "heif": "图片", "avif": "图片", "psd": "图片", "ai": "图片",
    "eps": "图片", "indd": "图片",
    # 文档
    "pdf": "文档", "doc": "文档", "docx": "文档", "odt": "文档",
    "rtf": "文档", "txt": "文档", "md": "文档", "rst": "文档",
    "xls": "文档", "xlsx": "文档", "ods": "文档", "csv": "文档",
    "ppt": "文档", "pptx": "文档", "odp": "文档",
    "epub": "文档", "mobi": "文档", "pages": "文档",
    "numbers": "文档", "key": "文档",
    # 视频
    "mp4": "视频", "mkv": "视频", "avi": "视频", "mov": "视频",
    "wmv": "视频", "flv": "视频", "webm": "视频", "m4v": "视频",
    "mpeg": "视频", "mpg": "视频", "3gp": "视频", "ts": "视频",
    "mts": "视频", "m2ts": "视频", "vob": "视频", "rmvb": "视频",
    # 音频
    "mp3": "音频", "wav": "音频", "flac": "音频", "aac": "音频",
    "ogg": "音频", "wma": "音频", "m4a": "音频", "opus": "音频",
    "ape": "音频", "aiff": "音频", "aif": "音频", "mid": "音频",
    "midi": "音频",
    # 压缩包
    "zip": "压缩包", "rar": "压缩包", "7z": "压缩包", "tar": "压缩包",
    "gz": "压缩包", "bz2": "压缩包", "xz": "压缩包", "zst": "压缩包",
    "iso": "压缩包", "dmg": "压缩包", "pkg": "压缩包",
    "tgz": "压缩包", "tbz2": "压缩包",
    # 代码
    "py": "代码", "js": "代码", "ts": "代码", "jsx": "代码", "tsx": "代码",
    "java": "代码", "kt": "代码", "c": "代码", "cpp": "代码", "h": "代码",
    "hpp": "代码", "cs": "代码", "go": "代码", "rs": "代码", "rb": "代码",
    "php": "代码", "swift": "代码", "r": "代码", "m": "代码",
    "sh": "代码", "bash": "代码", "zsh": "代码", "ps1": "代码",
    "bat": "代码", "cmd": "代码",
    "sql": "代码", "json": "代码", "xml": "代码", "yaml": "代码",
    "yml": "代码", "toml": "代码", "ini": "代码", "cfg": "代码",
    "conf": "代码", "env": "代码", "tf": "代码", "hcl": "代码",
    "dockerfile": "代码",
    # 程序
    "exe": "程序", "msi": "程序", "app": "程序",
    "deb": "程序", "rpm": "程序", "apk": "程序", "xpi": "程序",
    # 字体
    "ttf": "字体", "otf": "字体", "woff": "字体", "woff2": "字体",
    "eot": "字体", "fon": "字体",
    # 网页
    "html": "网页", "htm": "网页", "css": "网页", "mhtml": "网页",
    "webloc": "网页", "url": "网页",
}

# Files that should always be skipped regardless of configuration
ALWAYS_SKIP: frozenset[str] = frozenset([
    "desktop.ini",
    ".ds_store",
    "thumbs.db",
    "ehthumbs.db",
    ".localized",
    "organizer-config.json",
    "desktop-manifest.json",
    "organizer-plan.json",
    "organizer-result.json",
])


def get_desktop_path() -> Path:
    """Return the platform-specific Desktop path."""
    system = platform.system()
    if system == "Windows":
        # Prefer the official shell folder location
        desktop_env = os.environ.get("USERPROFILE", "")
        candidate = Path(desktop_env) / "Desktop" if desktop_env else None
        if candidate and candidate.is_dir():
            return candidate
        # Fallback: XDG-style on Windows Subsystem for Linux or unusual installs
    # macOS / Linux / fallback
    home = Path.home()
    xdg_desktop = os.environ.get("XDG_DESKTOP_DIR", "")
    if xdg_desktop:
        p = Path(xdg_desktop)
        if p.is_dir():
            return p
    return home / "Desktop"


def load_user_config(desktop: Path) -> dict:
    """Load organizer-config.json from the desktop if present."""
    config_path = desktop / "organizer-config.json"
    if config_path.is_file():
        try:
            with config_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def build_ext_map(user_config: dict) -> dict[str, str]:
    """Merge default extension map with user-defined categories."""
    ext_map = dict(DEFAULT_CATEGORIES)
    user_cats: dict = user_config.get("categories", {})
    for category_name, extensions in user_cats.items():
        if not isinstance(extensions, list):
            continue
        for ext in extensions:
            if isinstance(ext, str):
                ext_map[ext.lower().lstrip(".")] = category_name
    return ext_map


def classify(name: str, ext_map: dict[str, str], skip_exts: set[str]) -> str | None:
    """Return category for a filename or None if it should be skipped."""
    ext = Path(name).suffix.lstrip(".").lower()
    if ext in skip_exts:
        return None
    return ext_map.get(ext, "其他")


def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


def main() -> None:
    desktop = get_desktop_path()
    if not desktop.is_dir():
        print(f"[ERROR] Desktop directory not found: {desktop}", file=sys.stderr)
        sys.exit(1)

    user_config = load_user_config(desktop)
    ext_map = build_ext_map(user_config)
    skip_exts: set[str] = {e.lower().lstrip(".") for e in user_config.get("skip_extensions", [])}

    files_data = []
    skipped = []
    summary_by_category: dict[str, int] = {}
    total_size = 0

    for entry in sorted(desktop.iterdir(), key=lambda e: e.name.lower()):
        # Only process files in the root desktop (no subdirectories)
        if not entry.is_file():
            continue

        name = entry.name
        name_lower = name.lower()

        # Skip hidden and always-skip files
        if name.startswith(".") or name_lower in ALWAYS_SKIP:
            skipped.append(name)
            continue

        category = classify(name, ext_map, skip_exts)
        if category is None:
            skipped.append(name)
            continue

        stat = entry.stat()
        size_bytes = stat.st_size
        modified_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
        ext = entry.suffix.lstrip(".").lower()

        files_data.append({
            "name": name,
            "ext": ext,
            "category": category,
            "size_bytes": size_bytes,
            "size_human": format_size(size_bytes),
            "modified_at": modified_at,
        })
        summary_by_category[category] = summary_by_category.get(category, 0) + 1
        total_size += size_bytes

    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "desktop_path": str(desktop),
        "files": files_data,
        "skipped": skipped,
        "summary": {
            "total_files": len(files_data),
            "total_size_bytes": total_size,
            "total_size_human": format_size(total_size),
            "by_category": summary_by_category,
        },
    }

    out_path = Path("desktop-manifest.json")
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable summary to stdout
    print(f"桌面路径: {desktop}")
    print(f"扫描完成: 共 {len(files_data)} 个文件，跳过 {len(skipped)} 个系统/隐藏文件")
    print(f"总大小:   {format_size(total_size)}")
    print()
    print("分类统计:")
    for cat, count in sorted(summary_by_category.items(), key=lambda x: -x[1]):
        print(f"  {cat:<10} {count:>4} 个")
    print()
    print(f"清单已保存到 {out_path.resolve()}")


if __name__ == "__main__":
    main()

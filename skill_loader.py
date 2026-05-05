"""
XQAgent - Skill 加载器（SKILL.md 格式）
手动安装/卸载模式，基于 installed.json 维护已安装列表。
不再自动扫描目录，只有显式安装的技能才会被索引。

SKILL.md 格式：
  ---
  name: skill-name
  description: 技能描述
  ---
  # 正文（Markdown 指令，注入到对话上下文供 LLM 执行）
"""
import os, json, time, shutil
from typing import Optional

# 技能索引（名称 + 描述，不含内容）
_SKILL_INDEX: dict[str, dict] = {}

# 按需加载追踪
_SKILL_ON_DEMAND: set[str] = set()

# 技能存储目录和清单文件
_SKILLS_DIR: str = ""
_INSTALLED_FILE: str = ""


def init(skills_dir: str):
    """初始化技能系统，设置存储目录路径"""
    global _SKILLS_DIR, _INSTALLED_FILE
    _SKILLS_DIR = skills_dir
    _INSTALLED_FILE = os.path.join(skills_dir, "installed.json")
    os.makedirs(skills_dir, exist_ok=True)


def _load_installed() -> list[dict]:
    """读取 installed.json 清单"""
    if not _INSTALLED_FILE or not os.path.isfile(_INSTALLED_FILE):
        return []
    try:
        with open(_INSTALLED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_installed(entries: list[dict]):
    """保存 installed.json 清单"""
    with open(_INSTALLED_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _parse_skill_md(skill_dir: str) -> Optional[dict]:
    """解析一个 SKILL.md 文件，返回技能信息"""
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return None

    with open(skill_md, "r", encoding="utf-8") as f:
        raw = f.read()

    name = ""
    description = ""
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end > 0:
            frontmatter = raw[3:end].strip()
            for line in frontmatter.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    name = line[len("name:"):].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line[len("description:"):].strip().strip('"').strip("'")
            raw = raw[end + 3:].strip()
        else:
            raw = raw.lstrip("-").strip()

    content = raw.strip()
    if not name:
        name = os.path.basename(skill_dir)

    return {
        "name": name,
        "description": description or name,
        "source_dir": skill_dir,
        "content": content,
    }


def _walk_skill_dirs(root: str) -> list[str]:
    """递归遍历目录，返回所有包含 SKILL.md 的子目录路径"""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not d.startswith("_")]
        if "SKILL.md" in filenames:
            results.append(dirpath)
    return results


def build_skill_index() -> list[dict]:
    """从 installed.json 构建技能索引（仅读取已安装的技能目录）"""
    _SKILL_INDEX.clear()
    installed = _load_installed()
    for entry in installed:
        name = entry.get("name", "")
        source_dir = entry.get("source_dir", "")
        # 优先：已安装目录在 skills/ 下
        if _SKILLS_DIR and source_dir and os.path.isdir(source_dir):
            info = _parse_skill_md(source_dir)
        elif _SKILLS_DIR:
            alt_dir = os.path.join(_SKILLS_DIR, name)
            if os.path.isdir(alt_dir):
                info = _parse_skill_md(alt_dir)
                source_dir = alt_dir
            else:
                continue
        else:
            continue

        if info:
            _SKILL_INDEX[name] = {
                "name": name,
                "description": info.get("description", ""),
                "source_dir": source_dir,
            }
    return list(_SKILL_INDEX.values())


def install_skill(source_path: str) -> dict:
    """从 source_path 安装一个技能到 skills/ 目录，返回安装结果"""
    if not _SKILLS_DIR:
        return {"success": False, "error": "技能系统未初始化"}

    source_path = os.path.expanduser(source_path)
    if not os.path.isdir(source_path):
        return {"success": False, "error": f"目录不存在: {source_path}"}

    info = _parse_skill_md(source_path)
    if not info:
        return {"success": False, "error": "该目录不包含 SKILL.md"}

    name = info["name"]
    target = os.path.join(_SKILLS_DIR, name)

    if os.path.isdir(target):
        # 目录已存在但未在 installed.json 中，注册它
        installed = _load_installed()
        already = [e for e in installed if e.get("name") == name]
        if already:
            return {"success": True, "name": name, "status": "已存在"}
        target_info = _parse_skill_md(target)
        installed.append({
            "name": name,
            "description": target_info.get("description", ""),
            "source_dir": target,
            "installed_at": time.time(),
        })
        _save_installed(installed)
        build_skill_index()
        return {"success": True, "name": name, "status": "已注册"}

    shutil.copytree(source_path, target)
    target_info = _parse_skill_md(target)

    # 记录到 installed.json
    installed = _load_installed()
    installed.append({
        "name": name,
        "description": target_info.get("description", ""),
        "source_dir": target,
        "installed_at": time.time(),
    })
    _save_installed(installed)

    # 重建索引
    build_skill_index()

    return {"success": True, "name": name, "status": "已安装"}


def uninstall_skill(skill_name: str) -> dict:
    """卸载一个技能：从 installed.json 移除 + 删除目录 + 重建索引"""
    if not _SKILLS_DIR:
        return {"success": False, "error": "技能系统未初始化"}

    installed = _load_installed()
    before = len(installed)
    installed = [e for e in installed if e.get("name") != skill_name]
    if len(installed) == before:
        return {"success": False, "error": f"技能「{skill_name}」未安装"}

    _save_installed(installed)

    # 删除目录
    target = os.path.join(_SKILLS_DIR, skill_name)
    if os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)

    # 重建索引
    build_skill_index()

    return {"success": True, "name": skill_name}


def get_skill_index_prompt() -> str:
    """构建技能索引文本，用于 system prompt"""
    if not _SKILL_INDEX:
        return ""
    lines = [
        "## 可用技能（按需加载）",
        "以下技能已安装但未加载。需要时请调用 `use_skill` 工具加载：",
        ""
    ]
    for name, info in sorted(_SKILL_INDEX.items()):
        desc = info.get("description", "")
        lines.append(f"- **{name}**" + (f": {desc}" if desc else ""))
    return "\n".join(lines)


def load_skill_on_demand(skill_name: str) -> str:
    """按需加载单个技能，返回内容文本或错误信息"""
    info = _SKILL_INDEX.get(skill_name)
    if not info:
        matches = [n for n in _SKILL_INDEX
                   if skill_name.lower() in n.lower() or n.lower() in skill_name.lower()]
        if len(matches) == 1:
            info = _SKILL_INDEX[matches[0]]
            skill_name = matches[0]
        elif len(matches) > 1:
            return f"错误：找到多个匹配技能：{', '.join(matches)}，请指定更精确的名称"
        else:
            available = "、".join(_SKILL_INDEX.keys()) if _SKILL_INDEX else "无可用技能"
            return f"错误：技能「{skill_name}」不存在。可用技能：{available}"

    full_info = _parse_skill_md(info["source_dir"])
    if not full_info:
        return f"错误：无法加载技能「{skill_name}」的内容"

    content = full_info.get("content", "")
    _SKILL_ON_DEMAND.add(skill_name)

    if content:
        return f"技能「{skill_name}」已加载，请按照以下内容执行：\n\n{content}"
    return f"技能「{skill_name}」已加载（无额外指令）"


def unload_temp_skills() -> int:
    """卸载本次对话中按需加载的技能"""
    count = len(_SKILL_ON_DEMAND)
    _SKILL_ON_DEMAND.clear()
    return count


def list_skill_names() -> list[str]:
    return sorted(_SKILL_INDEX.keys())


def get_skill_descriptions() -> str:
    if not _SKILL_INDEX:
        return "暂无可用技能"
    lines = []
    for name, info in sorted(_SKILL_INDEX.items()):
        lines.append(f"  - {name}: {info.get('description', '')}")
    return "\n".join(lines)

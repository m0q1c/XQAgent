"""
XQAgent 多层记忆系统

L1: L1_insight.txt — 索引层（≤30行），记录关键事实的索引
L2: L2_facts.txt — 事实层，跨会话持久化的用户偏好/配置/关键信息
L3: L3_records/ — 记录层，详细的项目笔记、避坑指南
L4: L4_sessions/ — 历史会话层，对话总结摘要

原则（源自 GenericAgent memory_management_sop）：
- Action-Verified Only: 只记录验证过的信息
- No Volatile State: 不记时间戳/PID/临时ID
- Minimum Sufficient Pointer: 上层只留索引，细节在下层
"""
import json, os, time, glob

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
L1_PATH = os.path.join(MEMORY_DIR, "L1_insight.txt")
L2_PATH = os.path.join(MEMORY_DIR, "L2_facts.txt")
L3_DIR = os.path.join(MEMORY_DIR, "L3_records")
L4_DIR = os.path.join(MEMORY_DIR, "L4_sessions")


# ══════════════════════════════════════════════════════════════════
# 初始化
# ══════════════════════════════════════════════════════════════════

def _ensure_files():
    os.makedirs(L3_DIR, exist_ok=True)
    os.makedirs(L4_DIR, exist_ok=True)
    if not os.path.isfile(L1_PATH):
        with open(L1_PATH, "w", encoding="utf-8") as f:
            f.write("# L1 记忆索引\n# 格式: topic -> layer:path\n# 例: 用户偏好 -> L2\n")
    if not os.path.isfile(L2_PATH):
        with open(L2_PATH, "w", encoding="utf-8") as f:
            f.write("# L2 事实库\n# 跨会话持久化的用户偏好、配置、关键路径等\n\n")

_ensure_files()


# ══════════════════════════════════════════════════════════════════
# 读/写/搜索
# ══════════════════════════════════════════════════════════════════

def read_layer(layer: str) -> str:
    """读取指定层的内容"""
    _ensure_files()
    if layer == "L1":
        with open(L1_PATH, "r", encoding="utf-8") as f:
            return f.read()
    elif layer == "L2":
        with open(L2_PATH, "r", encoding="utf-8") as f:
            return f.read()
    elif layer == "L3":
        files = sorted(glob.glob(os.path.join(L3_DIR, "*.txt")) + glob.glob(os.path.join(L3_DIR, "*.md")))
        parts = [f"--- {os.path.basename(p)} ---\n" + open(p, "r", encoding="utf-8").read() for p in files]
        return "\n\n".join(parts) if parts else "(空)"
    elif layer == "L4":
        files = sorted(glob.glob(os.path.join(L4_DIR, "*.txt")) + glob.glob(os.path.join(L4_DIR, "*.md")), reverse=True)[:10]
        parts = [f"--- {os.path.basename(p)} ---\n" + open(p, "r", encoding="utf-8").read() for p in files]
        return "\n\n".join(parts) if parts else "(空)"
    return f"无效层: {layer}"


def write_l1(content: str) -> dict:
    """写入 L1 索引（追加模式）"""
    _ensure_files()
    with open(L1_PATH, "r", encoding="utf-8") as f:
        existing = f.read()
    # 去重：如果已有相同内容则不追加
    if content.strip() in existing:
        return {"ok": True, "note": "内容已存在，未重复写入"}
    with open(L1_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + content.strip())
    return {"ok": True}


def write_l2(content: str) -> dict:
    """写入 L2 事实（追加模式）"""
    _ensure_files()
    with open(L2_PATH, "r", encoding="utf-8") as f:
        existing = f.read()
    if content.strip() in existing:
        return {"ok": True, "note": "内容已存在"}
    with open(L2_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + content.strip())
    return {"ok": True}


def write_l3(name: str, content: str) -> dict:
    """写入 L3 记录文件"""
    _ensure_files()
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-")[:60]
    path = os.path.join(L3_DIR, safe_name + ".txt")
    mode = "a" if os.path.isfile(path) else "w"
    with open(path, mode, encoding="utf-8") as f:
        if mode == "a":
            f.write("\n---\n")
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M')}] {content.strip()}\n")
    return {"ok": True, "path": path}


def write_l4(session_id: str, summary: str):
    """写入 L4 会话总结"""
    _ensure_files()
    path = os.path.join(L4_DIR, f"{session_id}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(summary)
    return {"ok": True, "path": path}


def search(keyword: str) -> list:
    """跨层搜索记忆"""
    _ensure_files()
    results = []
    for layer, path in [("L1", L1_PATH), ("L2", L2_PATH)]:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if keyword.lower() in line.lower():
                        results.append({"layer": layer, "content": line.strip()})
    # L3
    for fp in sorted(glob.glob(os.path.join(L3_DIR, "*.*"))):
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
            if keyword.lower() in content.lower():
                results.append({"layer": "L3", "file": os.path.basename(fp), "snippet": content[:200]})
    # L4 (只搜文件名)
    for fp in sorted(glob.glob(os.path.join(L4_DIR, "*.*"))):
        if keyword.lower() in os.path.basename(fp).lower():
            results.append({"layer": "L4", "file": os.path.basename(fp)})
    return results


def list_l3() -> list:
    """列出 L3 记录文件"""
    _ensure_files()
    return sorted([os.path.basename(p) for p in glob.glob(os.path.join(L3_DIR, "*.*"))])


def get_l3(name: str) -> str:
    """读取指定 L3 文件"""
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-")[:60]
    for ext in [".txt", ".md"]:
        path = os.path.join(L3_DIR, safe_name + ext)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return f"未找到: {name}"

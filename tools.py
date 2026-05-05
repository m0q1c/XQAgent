"""
XQAgent - 工具系统
采用 GenericAgent 的轻量化思路，纯函数 + JSON schema
"""
import json, os, subprocess, urllib.request, urllib.parse, urllib.error, re, mimetypes, base64, time, glob

# ── 工具注册 ──
_TOOL_REGISTRY: dict = {}
_TOOL_SCHEMAS: list = []


def _safe_path(path: str) -> str:
    expanded = os.path.expanduser(path)
    real = os.path.realpath(expanded)
    blocked = ["/System", "/Library/Apple", "/dev/sd", "/dev/disk", "/boot/"]
    for pat in blocked:
        if pat.lower() in path.lower():
            raise ValueError(f"已拦截: 路径匹配危险模式 '{pat}'")
    # 防止目录遍历: 展开后的路径不能包含关键系统目录
    real_lower = real.lower()
    for sys_dir in ["/etc", "/var/db", "/private/etc"]:
        if real_lower == sys_dir or real_lower.startswith(sys_dir + "/"):
            raise ValueError(f"已拦截: 禁止访问系统目录: {real}")
    return expanded


def register(name: str, description: str, params: dict, required: list = None):
    """注册工具"""
    def decorator(func):
        _TOOL_REGISTRY[name] = func
        _TOOL_SCHEMAS.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": required or []
                }
            }
        })
        return func
    return decorator


def get_schemas() -> list:
    return list(_TOOL_SCHEMAS)


def execute(name: str, args: dict) -> str:
    fn = _TOOL_REGISTRY.get(name)
    if not fn:
        return f"Error: Unknown tool '{name}'"
    try:
        result = fn(**args)
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, default=str)
        return str(result)
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


# ══════════════════════════════════════════════════════════════════════════
# 内置工具
# ══════════════════════════════════════════════════════════════════════════

@register(
    name="read_file",
    description="读取文件内容，最多返回 8000 字符。",
    params={"path": {"type": "string", "description": "文件路径"}},
    required=["path"]
)
def read_file(path: str) -> str:
    path = _safe_path(path)
    if not os.path.isfile(path):
        return f"错误: 文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"错误: {e}"


@register(
    name="write_file",
    description="将内容写入文件。父目录不存在会自动创建。",
    params={
        "path": {"type": "string", "description": "文件路径"},
        "content": {"type": "string", "description": "要写入的内容"}
    },
    required=["path", "content"]
)
def write_file(path: str, content: str) -> str:
    path = _safe_path(path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功: 已写入 {len(content)} 字符到 {path}"
    except Exception as e:
        return f"错误: {e}"


@register(
    name="run_shell",
    description="执行 Shell 命令，返回输出（最多 4000 字符）。超时 60 秒。",
    params={
        "command": {"type": "string", "description": "要执行的命令"},
        "timeout": {"type": "integer", "description": "超时秒数，默认60"}
    },
    required=["command"]
)
def run_shell(command: str, timeout: int = 60) -> str:
    # 命令长度限制（单个命令不超过 1000 字符）
    if len(command) > 1000:
        return f"已拦截: 命令过长 ({len(command)} 字符，上限 1000)"

    # 危险模式检测 — 子串匹配 + 正则双重校验
    blocked_patterns = [
        "rm -rf /", "rm -rf /*",
        "mkfs", "dd if=", "> /dev/sd",
        ":(){ :|:& };:", "fork()",
        "chmod 777 /", "chown ", "chattr -i",
        "> /etc/", "> /boot/",
        "wget ", "curl ",  # 阻止下载执行
        "python3 -c", "perl -e", "ruby -e",
        "base64 -d", "base64 --decode",
        "eval ", "exec ", "source /dev/stdin",
        "| bash", "| sh",  # 管道到 shell
    ]
    cmd_lower = command.lower()
    for pat in blocked_patterns:
        if pat.lower() in cmd_lower:
            return f"已拦截: 命令匹配危险模式"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=os.path.expanduser("~")
        )
        output = f"退出码: {result.returncode}\n"
        if result.stdout: output += f"标准输出:\n{result.stdout[:4000]}\n"
        if result.stderr: output += f"标准错误:\n{result.stderr[:2000]}\n"
        return output
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（{timeout} 秒）"
    except Exception as e:
        return f"错误: {e}"


@register(
    name="list_files",
    description="列出目录中的文件。",
    params={
        "path": {"type": "string", "description": "目录路径，默认 ~"},
        "recursive": {"type": "boolean", "description": "是否递归，默认 False"}
    }
)
def list_files(path: str = "~", recursive: bool = False) -> str:
    path = _safe_path(path)
    if not os.path.isdir(path):
        return f"错误: 不是目录: {path}"
    entries = []
    try:
        if recursive:
            for root, dirs, files in os.walk(path):
                for f in sorted(files)[:200]:
                    fp = os.path.join(root, f)
                    try: entries.append(f"{fp} ({os.path.getsize(fp)} 字节)")
                    except: pass
        else:
            for f in sorted(os.listdir(path)):
                fp = os.path.join(path, f)
                try:
                    is_dir = os.path.isdir(fp)
                    sz = os.path.getsize(fp) if not is_dir else 0
                    entries.append(f"{'[目录] ' if is_dir else ''}{f} ({sz} 字节)")
                except: pass
        return "\n".join(entries) if entries else "(空目录)"
    except Exception as e:
        return f"错误: {e}"


@register(
    name="web_fetch",
    description="从 URL 获取网页内容文本（最多 6000 字符）。",
    params={"url": {"type": "string", "description": "网页地址"}},
    required=["url"]
)
def web_fetch(url: str) -> str:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        req = urllib.request.Request(url, headers={"User-Agent": "XQAgent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            mime = resp.headers.get("Content-Type", "")
            if "image/" in mime:
                return f"[图片] {mime}, {len(data)} 字节"
            text = data.decode("utf-8", errors="replace")[:6000]
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:6000]
    except urllib.error.URLError as e:
        return f"错误: 无法获取网页 - {e}"
    except Exception as e:
        return f"错误: {e}"


@register(
    name="search_files",
    description="在目录中按文件名模式搜索文件。",
    params={
        "pattern": {"type": "string", "description": "搜索模式（支持通配符如 *.py）"},
        "path": {"type": "string", "description": "搜索目录"}
    },
    required=["pattern"]
)
def search_files(pattern: str, path: str = "~") -> str:
    path = _safe_path(path)
    matches = glob.glob(os.path.join(path, "**", pattern), recursive=True)
    if not matches:
        return f"未找到匹配 '{pattern}' 的文件"
    results = []
    for m in sorted(matches)[:50]:
        try: results.append(f"{m} ({os.path.getsize(m)} 字节)")
        except: pass
    return "\n".join(results)


@register(
    name="get_weather",
    description="查询天气信息，支持全球城市。返回当前天气和未来3天预报。无需 API Key。",
    params={
        "city": {"type": "string", "description": "城市名称（中文或英文，如 北京、Tokyo、London）"},
        "lang": {"type": "string", "description": "语言，zh=中文(默认)，en=英文"}
    },
    required=["city"]
)
def get_weather(city: str, lang: str = "zh") -> str:
    import urllib.parse
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?lang={lang}&format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        current = data.get("current_condition", [{}])[0]
        location = data.get("nearest_area", [{}])[0]
        area = location.get("areaName", [{}])[0].get("value", city)
        country = location.get("country", [{}])[0].get("value", "")
        region = location.get("region", [{}])[0].get("value", "")
        lines = [
            f"📍 {area}, {region}, {country}",
            f"🌡️ 当前: {current.get('temp_C', '?')}°C（体感 {current.get('FeelsLikeC', '?')}°C）",
            f"💧 湿度: {current.get('humidity', '?')}%",
            f"🌬️ 风速: {current.get('windspeedKmph', '?')} km/h",
            f"☁️ {current.get('lang_zh', [{}])[0].get('value', current.get('weatherDesc', [{}])[0].get('value', '?'))}",
        ]
        forecast = data.get("weather", [])
        if forecast:
            lines.append("\n📅 未来预报:")
            for day in forecast[:3]:
                date = day.get("date", "")
                max_t, min_t = day.get("maxtempC", "?"), day.get("mintempC", "?")
                desc = "?"; hourly = day.get("hourly", [])
                if hourly:
                    mid = hourly[len(hourly)//2]
                    zh = mid.get("lang_zh", [{}])
                    desc = zh[0].get("value", "") if zh else mid.get("weatherDesc", [{}])[0].get("value", "?")
                rain = day.get("hourly", [{}])[0].get("chanceofrain", "0") if day.get("hourly") else "0"
                lines.append(f"  {date}: {desc} {min_t}~{max_t}°C 🌧️{rain}%")
        return "\n".join(lines)
    except Exception as e:
        try:
            url2 = f"https://wttr.in/{urllib.parse.quote(city)}?lang={lang}&format=4"
            req2 = urllib.request.Request(url2, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req2, timeout=8) as resp2:
                return resp2.read().decode("utf-8").strip()
        except:
            return f"错误: 无法获取天气 - {e}"


# ══════════════════════════════════════════════════════════════════════
# 技能系统工具
# ══════════════════════════════════════════════════════════════════════

@register(
    name="list_skills",
    description="列出所有可用技能的名称和简介，调用前请先执行此工具了解有哪些技能",
    params={
        "_dummy": {"type": "string", "description": "无需参数，传入空字符串即可"}
    },
    required=[]
)
def list_skills() -> str:
    from skill_loader import get_skill_descriptions
    return "可用技能列表：\n" + get_skill_descriptions()


@register(
    name="use_skill",
    description="按需加载并使用一个技能。先使用 list_skills 查看可用技能，然后传入技能名称。加载后按照返回的指令执行",
    params={
        "name": {"type": "string", "description": "技能名称，如 weather（从 list_skills 获取）"}
    },
    required=["name"]
)
def use_skill(name: str) -> str:
    from skill_loader import load_skill_on_demand
    return load_skill_on_demand(name)


# ══════════════════════════════════════════════════════════════════════
# 记忆工具
# ══════════════════════════════════════════════════════════════════════

@register(
    name="read_memory",
    description="读取记忆系统中的信息。L1=索引(30行), L2=事实(跨会话持久), L3=详细记录, L3_list=列出记录文件, L3/xxx=读取特定记录, L4=最近会话总结",
    params={
        "layer": {"type": "string", "description": "层: L1/L2/L3/L3_list/L3/记录名/L4"}
    },
    required=["layer"]
)
def read_memory(layer: str) -> str:
    from memory import read_layer, list_l3, get_l3
    if layer == "L3_list":
        return "\n".join(list_l3())
    if layer.startswith("L3/"):
        return get_l3(layer[3:])
    return read_layer(layer)


@register(
    name="write_memory",
    description="写入一条记忆。L1=索引(简短关键词), L2=事实(用户偏好/配置/路径), L3=详细记录(项目笔记/避坑)。写入成功返回 OK",
    params={
        "layer": {"type": "string", "description": "层: L1/L2/L3"},
        "content": {"type": "string", "description": "记忆内容。L1: 'topic -> layer:path' 格式; L2: 一条事实; L3: 详细记录"},
        "name": {"type": "string", "description": "L3 专用：记录文件名（不含后缀）"}
    },
    required=["layer", "content"]
)
def write_memory(layer: str, content: str, name: str = "") -> str:
    from memory import write_l1, write_l2, write_l3
    if layer == "L1":
        r = write_l1(content)
    elif layer == "L2":
        r = write_l2(content)
    elif layer == "L3":
        r = write_l3(name or "note", content)
    else:
        return f"无效层: {layer}"
    return json.dumps(r, ensure_ascii=False)


@register(
    name="search_memory",
    description="跨层搜索记忆系统中与关键词相关的内容",
    params={
        "keyword": {"type": "string", "description": "搜索关键词"}
    },
    required=["keyword"]
)
def search_memory(keyword: str) -> str:
    from memory import search
    results = search(keyword)
    if not results:
        return "未找到相关记忆"
    return json.dumps(results, ensure_ascii=False, indent=2)

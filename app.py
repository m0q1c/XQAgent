"""
XQAgent - HTTP 服务器
纯 stdlib，零依赖。支持会话持久化、历史对话管理、/sync 同步。
"""
import json, os, sys, time, threading, urllib.request, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
WEB_DIR = os.path.join(SCRIPT_DIR, "web")
SESSION_DIR = os.path.join(SCRIPT_DIR, "sessions")

DEFAULT_CONFIG = {
    "model": "qwen/qwen3.5-9b",
    "api_key": "",
    "base_url": "http://127.0.0.1:1234/v1",
    "port": 18777,
    "models": [],
    "persona": ""
}

# ── 全局状态 ──
_config = None
_agent = None
_llm = None
_abort_flag = threading.Event()
_current_session_id = None


# ══════════════════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════════════════

def load_config():
    global _config
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        _config = cfg
    else:
        _config = dict(DEFAULT_CONFIG)
        save_config()
    # 迁移：如果 models 为空，从顶级字段创建默认模型条目
    if not _config.get("models"):
        _config["models"] = [{
            "id": "default",
            "name": "默认模型",
            "base_url": _config.get("base_url", ""),
            "api_key": _config.get("api_key", ""),
            "model": _config.get("model", ""),
            "is_default": True,
            "created_at": time.time()
        }]
        save_config()
    return _config

def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_config, f, ensure_ascii=False, indent=2)

def _ensure_default_model():
    """确保有且只有一个模型被标记为默认"""
    models = _config.get("models", [])
    if not models:
        return
    defaults = [m for m in models if m.get("is_default")]
    if len(defaults) == 0:
        models[0]["is_default"] = True
        save_config()
    elif len(defaults) > 1:
        for m in defaults[1:]:
            m["is_default"] = False
        save_config()

def _sync_top_level_from_default():
    """将默认模型的配置同步到顶级字段，供 init_agent() 使用"""
    models = _config.get("models", [])
    for m in models:
        if m.get("is_default"):
            _config["model"] = m["model"]
            _config["base_url"] = m["base_url"]
            _config["api_key"] = m.get("api_key", "")
            save_config()
            return

# ── 模型管理操作 ──

def add_model_entry(name: str, base_url: str, api_key: str, model: str, set_default: bool = False) -> dict:
    cfg = load_config()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "name": name or model,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "is_default": False,
        "created_at": time.time()
    }
    if set_default or not cfg.get("models"):
        entry["is_default"] = True
        # 取消之前默认标记
        for m in cfg["models"]:
            m["is_default"] = False
    cfg["models"].append(entry)
    _ensure_default_model()
    _sync_top_level_from_default()
    return entry

def update_model_entry(entry_id: str, updates: dict) -> bool:
    cfg = load_config()
    for m in cfg["models"]:
        if m["id"] == entry_id:
            if "name" in updates: m["name"] = updates["name"]
            if "base_url" in updates: m["base_url"] = updates["base_url"]
            if "api_key" in updates: m["api_key"] = updates["api_key"]
            if "model" in updates: m["model"] = updates["model"]
            save_config()
            if m.get("is_default"):
                _sync_top_level_from_default()
            return True
    return False

def delete_model_entry(entry_id: str) -> bool:
    cfg = load_config()
    was_default = False
    new_models = []
    for m in cfg["models"]:
        if m["id"] == entry_id:
            if m.get("is_default"):
                was_default = True
            continue
        new_models.append(m)
    if len(new_models) == len(cfg["models"]):
        return False  # 没找到
    cfg["models"] = new_models
    if was_default and new_models:
        new_models[0]["is_default"] = True
    _ensure_default_model()
    _sync_top_level_from_default()
    return True

def set_default_model(entry_id: str) -> bool:
    cfg = load_config()
    found = False
    for m in cfg["models"]:
        if m["id"] == entry_id:
            m["is_default"] = True
            found = True
        else:
            m["is_default"] = False
    if found:
        _sync_top_level_from_default()
    return found

def init_agent(reset_history=True):
    global _agent, _llm
    from xq_agent import Agent, LLMClient, build_system_prompt
    from tools import get_schemas
    cfg = load_config()
    _llm = LLMClient(
        model=cfg["model"],
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", "http://127.0.0.1:1234/v1"),
    )
    tool_schemas = get_schemas()
    system_prompt = build_system_prompt()
    _agent = Agent(tools=tool_schemas, system_prompt=system_prompt)
    return _agent, _llm


# ══════════════════════════════════════════════════════════════════════════
# 会话管理
# ══════════════════════════════════════════════════════════════════════════

def _ensure_session_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)

def _session_index_path():
    return os.path.join(SESSION_DIR, "index.json")

def _session_file_path(sid: str) -> str:
    """安全地构造会话文件路径，防止路径遍历"""
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', sid):
        raise ValueError(f"Invalid session ID: {sid}")
    return os.path.join(SESSION_DIR, f"{sid}.json")

def _load_index() -> list:
    _ensure_session_dir()
    path = _session_index_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []

def _save_index(index: list):
    _ensure_session_dir()
    path = _session_index_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def _generate_title(messages: list) -> str:
    """根据对话内容生成标题"""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # 取前 30 个字符作为标题
            content = content.replace("\n", " ").strip()
            if len(content) > 30:
                return content[:30] + "…"
            return content
    return "新对话"

def create_session(title: str = "") -> dict:
    """创建新会话"""
    _ensure_session_dir()
    sid = uuid.uuid4().hex[:12]
    now = time.time()
    session = {
        "id": sid,
        "title": title or "新对话",
        "created_at": now,
        "updated_at": now,
        "messages": []
    }
    # 写文件
    with open(_session_file_path(sid), "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    # 更新索引
    index = _load_index()
    index.insert(0, {"id": sid, "title": session["title"], "created_at": now, "updated_at": now, "message_count": 0})
    _save_index(index)
    return {"id": sid, "title": session["title"]}

def get_session(sid: str) -> dict:
    """获取完整会话数据"""
    try:
        path = _session_file_path(sid)
    except ValueError:
        return None
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def delete_session(sid: str) -> bool:
    """删除会话"""
    try:
        path = _session_file_path(sid)
    except ValueError:
        return False
    if os.path.isfile(path):
        os.remove(path)
    # 更新索引
    index = _load_index()
    index = [s for s in index if s["id"] != sid]
    _save_index(index)
    return True

def rename_session(sid: str, new_title: str) -> bool:
    """重命名会话"""
    session = get_session(sid)
    if not session:
        return False
    session["title"] = new_title.strip() or session["title"]
    with open(_session_file_path(sid), "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    # 更新索引
    index = _load_index()
    for s in index:
        if s["id"] == sid:
            s["title"] = session["title"]
            break
    _save_index(index)
    return True

def append_messages(sid: str, new_msgs: list):
    """向会话追加消息"""
    session = get_session(sid)
    if not session:
        return False
    session["messages"].extend(new_msgs)
    session["updated_at"] = time.time()
    session["title"] = _generate_title(session["messages"])
    session["message_count"] = len(session["messages"])
    with open(_session_file_path(sid), "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    # 更新索引
    index = _load_index()
    for s in index:
        if s["id"] == sid:
            s["updated_at"] = session["updated_at"]
            s["title"] = session["title"]
            s["message_count"] = session["message_count"]
            break
    _save_index(index)
    return True

def format_sync_context(sid: str, max_messages: int = 20) -> str:
    """将历史会话格式化为 /sync 上下文"""
    session = get_session(sid)
    if not session or not session.get("messages"):
        return None
    msgs = session["messages"]
    # 取最近的消息
    msgs = msgs[-max_messages:]
    lines = [f"以下是从历史对话「{session['title']}」同步的关键信息：", ""]
    for msg in msgs:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")[:500]
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════

class XQHandler(BaseHTTPRequestHandler):
    wbufsize = 0  # 禁用输出缓冲，确保 SSE 即时流式

    def log_message(self, format, *args):
        if "200" not in str(args[0]):
            print(f"[XQ] {args[0]} {args[1]}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, status=400):
        self._send_json({"error": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _parse_path(self):
        """解析路径和路径参数"""
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        return parsed.path, parts

    # ══════════════════════════════════════════════════════════════════════

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path, parts = self._parse_path()

        if path == "/":
            self._serve_html()
        elif path == "/api/config":
            self._send_json(load_config())
        elif path == "/api/models":
            self._handle_models()
        elif path == "/api/models-config":
            self._handle_list_models_config()
        elif path == "/api/skills":
            self._handle_list_skills()
        elif path == "/api/status":
            self._send_json({"running": _agent.is_running if _agent else False})
        elif path == "/api/sessions":
            self._handle_list_sessions()
        elif path == "/api/bridges":
            self._handle_bridges()
        elif path == "/api/bridges/config":
            self._handle_bridges_config_get()
        elif path == "/api/bridges/wechat/qr":
            self._handle_wechat_qr()
        elif len(parts) >= 3 and parts[:2] == ["api", "sessions"]:
            # GET /api/sessions/<id>
            session_id = parts[2]
            session = get_session(session_id)
            if session:
                self._send_json(session)
            else:
                self._send_error("Session not found", 404)
        else:
            self._send_error("Not Found", 404)

    def do_POST(self):
        path, parts = self._parse_path()
        body = self._read_body()

        if path == "/api/config":
            self._handle_set_config(body)
        elif path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/abort":
            self._handle_abort()
        elif path == "/api/reset":
            self._handle_reset()
        elif path == "/api/sync-all":
            self._handle_sync_all(body)
        elif path == "/api/fetch-models":
            self._handle_fetch_models(body)
        elif path == "/api/models-config":
            self._handle_upsert_model(body)
        elif len(parts) >= 3 and parts[:2] == ["api", "models-config"]:
            action = parts[2]
            if action == "delete":
                self._handle_delete_model(body)
            elif action == "default":
                self._handle_set_default_model(body)
            else:
                self._send_error("Unknown action", 404)
        elif path == "/api/skills/install":
            self._handle_install_skill(body)
        elif path == "/api/skills/remove":
            self._handle_remove_skill(body)
        elif path == "/api/skills/scan":
            self._handle_scan_skills(body)
        elif path == "/api/select-directory":
            self._handle_select_directory()
        elif path == "/api/select-file":
            self._handle_select_file()
        elif path == "/api/upload":
            self._handle_upload(body)
        elif path == "/api/bridges/config":
            self._handle_bridges_config(body)
        elif path == "/api/session/append":
            self._handle_session_append(body)
        elif path == "/api/memory/read":
            self._handle_memory_read(body)
        elif path == "/api/memory/write":
            self._handle_memory_write(body)
        elif path == "/api/memory/search":
            self._handle_memory_search(body)
        elif path == "/api/bridges/wechat/qr":
            self._handle_wechat_qr_action(body)
        elif path == "/api/sessions":
            self._handle_create_session(body)
        elif len(parts) >= 3 and parts[:2] == ["api", "sessions"]:
            session_id = parts[2]
            action = "/".join(parts[3:]) if len(parts) > 3 else ""
            if action == "sync":
                self._handle_sync(body, session_id)
            elif action == "rename":
                self._handle_rename_session(body, session_id)
            else:
                self._send_error("Unknown action", 404)
        else:
            self._send_error("Not Found", 404)

    def do_DELETE(self):
        path, parts = self._parse_path()
        if len(parts) >= 3 and parts[:2] == ["api", "sessions"]:
            session_id = parts[2]
            delete_session(session_id)
            self._send_json({"ok": True})
        else:
            self._send_error("Not Found", 404)

    # ══════════════════════════════════════════════════════════════════════
    # 前端
    # ══════════════════════════════════════════════════════════════════════

    def _serve_html(self):
        index_path = os.path.join(WEB_DIR, "index.html")
        if not os.path.isfile(index_path):
            self._send_error("index.html not found", 404)
            return
        with open(index_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    # ══════════════════════════════════════════════════════════════════════
    # 配置 API
    # ══════════════════════════════════════════════════════════════════════

    def _handle_bridges(self):
        """GET /api/bridges — 获取桥接器状态"""
        try:
            from bridges.manager import get_manager
            mgr = get_manager()
            status = mgr.get_status()
            # 合并独立微信桥接器状态（扫码连接的实例不在 mgr._bridges 中）
            wb = self._get_wechat_bridge()
            if wb:
                status["wechat"] = {
                    "running": wb._running,
                    "enabled": wb._login_status == "confirmed" or wb._running,
                    "label": "微信",
                    "error": wb._login_error,
                }
            self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_bridges_config(self, body):
        """POST /api/bridges/config — 保存桥接器配置并后台重启"""
        data = json.loads(body) if body else {}
        cfg_path = os.path.join(SCRIPT_DIR, "bridges", "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._send_json({"ok": True})
        # 后台重启桥接器（不阻塞响应）
        try:
            from bridges.manager import get_manager
            t = threading.Thread(target=get_manager().restart, daemon=True)
            t.start()
        except Exception:
            pass

    def _handle_bridges_config_get(self):
        """GET /api/bridges/config — 获取桥接器配置"""
        try:
            from bridges.config import load_bridge_config
            self._send_json(load_bridge_config())
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _get_wechat_bridge(self):
        """获取或创建微信桥接器实例（复用同一实例）"""
        if not hasattr(self.__class__, '_wechat_bridge') or not self.__class__._wechat_bridge:
            try:
                from bridges.manager import get_manager
                mgr = get_manager()
                if "wechat" in mgr._bridges:
                    self.__class__._wechat_bridge = mgr._bridges["wechat"]
                    return self.__class__._wechat_bridge
            except Exception:
                pass
            try:
                from bridges.wechat import WeChatBridge
                from bridges.config import load_bridge_config
                cfg = load_bridge_config()
                bridge = WeChatBridge(cfg.get("wechat", {}))
                bridge.start()  # 加载凭证并启动消息轮询
                self.__class__._wechat_bridge = bridge
            except Exception:
                self.__class__._wechat_bridge = None
        return self.__class__._wechat_bridge

    def _handle_wechat_qr(self):
        """GET /api/bridges/wechat/qr — 获取扫码登录状态"""
        bridge = self._get_wechat_bridge()
        if not bridge:
            self._send_json({"status": "error", "error": "微信桥接器不可用"})
            return
        try:
            result = bridge.get_qr_status()
            self._send_json(result)
        except Exception as e:
            self._send_json({"status": "error", "error": str(e)})

    def _handle_session_append(self, body):
        """POST /api/session/append — 向会话追加消息（不触发 agent）"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        session_id = data.get("session_id", _current_session_id)
        msg = data.get("message", "")
        reply = data.get("reply", "")
        if not session_id:
            self._send_json({"ok": False, "error": "无活跃会话"})
            return
        msgs = []
        if msg:
            msgs.append({"role": "user", "content": msg, "timestamp": time.time()})
        if reply:
            msgs.append({"role": "assistant", "content": reply, "timestamp": time.time() + 0.1})
        if msgs:
            ok = append_messages(session_id, msgs)
            self._send_json({"ok": ok, "session_id": session_id})
        else:
            self._send_json({"ok": False, "error": "没有消息"})

    # ══════════════════════════════════════════════════════════════════════
    # 记忆 API
    # ══════════════════════════════════════════════════════════════════════

    def _handle_memory_read(self, body):
        """POST /api/memory/read — 读取记忆层"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        layer = data.get("layer", "L1")
        try:
            from memory import read_layer, list_l3, get_l3
            if layer == "L3_list":
                result = list_l3()
            elif layer and layer.startswith("L3/"):
                result = get_l3(layer[3:])
            else:
                result = read_layer(layer)
            self._send_json({"layer": layer, "content": result})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_memory_write(self, body):
        """POST /api/memory/write — 写入记忆"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        layer = data.get("layer", "L2")
        content = data.get("content", "")
        name = data.get("name", "")
        if not content:
            self._send_error("content 不能为空")
            return
        try:
            from memory import write_l1, write_l2, write_l3
            if layer == "L1":
                result = write_l1(content)
            elif layer == "L2":
                result = write_l2(content)
            elif layer == "L3":
                result = write_l3(name or "note", content)
            else:
                self._send_error(f"不支持写入层: {layer}")
                return
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_memory_search(self, body):
        """POST /api/memory/search — 搜索记忆"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        keyword = data.get("keyword", "")
        if not keyword:
            self._send_error("keyword 不能为空")
            return
        try:
            from memory import search
            results = search(keyword)
            self._send_json({"results": results})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_wechat_qr_action(self, body):
        """POST /api/bridges/wechat/qr — 扫码登录操作"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        action = data.get("action", "status")
        bridge = self._get_wechat_bridge()
        if not bridge:
            self._send_json({"status": "error", "error": "微信桥接器不可用"})
            return
        try:
            if action == "login":
                result = bridge.qr_login()
                self._send_json(result)
            elif action == "logout":
                bridge.qr_logout()
                self._send_json({"status": "idle"})
            else:
                self._send_json(bridge.get_qr_status())
        except Exception as e:
            self._send_json({"status": "error", "error": str(e)})

    def _handle_models(self):
        cfg = load_config()
        try:
            req = urllib.request.Request(
                f"{cfg['base_url'].rstrip('/')}/models",
                headers={"Authorization": f"Bearer {cfg.get('api_key', '')}"}
            )
            resp = urllib.request.urlopen(req, timeout=5)
            self._send_json(json.loads(resp.read().decode("utf-8")))
        except Exception as e:
            self._send_json({"error": str(e)}, 502)

    def _handle_fetch_models(self, body):
        """POST /api/fetch-models — 用前端传入的 base_url + api_key 查询可用模型"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        base_url = data.get("base_url", "").strip()
        api_key = data.get("api_key", "").strip()
        if not base_url:
            self._send_json({"error": "接口地址不能为空"}, 400)
            return
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read().decode("utf-8"))
            # 提取模型 id 列表
            models = [m["id"] for m in result.get("data", []) if m.get("id")]
            self._send_json({"models": models})
        except Exception as e:
            self._send_json({"error": str(e)}, 502)

    def _handle_set_config(self, body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        cfg = load_config()
        for k in ("model", "api_key", "base_url", "port", "persona"):
            if k in data: cfg[k] = data[k]
        save_config()
        init_agent()
        self._send_json({"ok": True})

    # ══════════════════════════════════════════════════════════════════════
    # 模型管理 API
    # ══════════════════════════════════════════════════════════════════════

    def _handle_list_models_config(self):
        cfg = load_config()
        self._send_json(cfg.get("models", []))

    def _handle_list_skills(self):
        """GET /api/skills — 返回所有已安装的技能"""
        try:
            from skill_loader import _SKILL_INDEX
            skills = []
            for name, info in _SKILL_INDEX.items():
                skills.append({
                    "name": name,
                    "description": info.get("description", ""),
                })
            self._send_json(skills)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_install_skill(self, body):
        """POST /api/skills/install — 安装技能（从源目录复制到 skills/ + 记录到 installed.json）"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        source_path = data.get("path", "").strip()
        if not source_path:
            self._send_error("path 不能为空")
            return
        from skill_loader import install_skill, _walk_skill_dirs, _parse_skill_md
        source_path = os.path.expanduser(source_path)

        # 检查是单个技能目录还是包含多个技能目录的父目录
        if os.path.isfile(os.path.join(source_path, "SKILL.md")):
            # 单个技能
            result = install_skill(source_path)
            installed_list = [result] if result.get("success") else []
        else:
            # 批量扫描
            found = _walk_skill_dirs(source_path)
            installed_list = []
            for skill_dir in found:
                r = install_skill(skill_dir)
                if r.get("success"):
                    installed_list.append(r)

        if installed_list:
            self._send_json({"installed": installed_list})
        else:
            self._send_error("未找到可安装的技能")

    def _handle_remove_skill(self, body):
        """POST /api/skills/remove — 卸载技能"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        name = data.get("name", "").strip()
        if not name:
            self._send_error("name 不能为空")
            return
        from skill_loader import uninstall_skill
        result = uninstall_skill(name)
        if result.get("success"):
            self._send_json({"ok": True})
        else:
            self._send_error(result.get("error", "卸载失败"))

    def _handle_scan_skills(self, body):
        """POST /api/skills/scan — 扫描目录，返回可安装的技能列表（不安装）"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        source_path = data.get("path", "").strip()
        if not source_path:
            self._send_error("path 不能为空")
            return
        source_path = os.path.expanduser(source_path)
        if not os.path.isdir(source_path):
            self._send_error(f"目录不存在: {source_path}")
            return

        from skill_loader import _walk_skill_dirs, _parse_skill_md, _load_installed, _SKILLS_DIR
        installed_names = {e.get("name") for e in _load_installed()}

        found = _walk_skill_dirs(source_path)
        results = []
        for skill_dir in found:
            info = _parse_skill_md(skill_dir)
            if info:
                results.append({
                    "name": info["name"],
                    "description": info.get("description", ""),
                    "source_dir": skill_dir,
                    "already_installed": info["name"] in installed_names,
                })

        self._send_json({"skills": results})

    def _handle_select_directory(self):
        """POST /api/select-directory — 调用 macOS 原生文件夹选择器"""
        try:
            import subprocess
            result = subprocess.check_output(
                ["osascript", "-e",
                 'set theFolder to choose folder with prompt "选择包含 SKILL.md 的技能目录"\nreturn POSIX path of theFolder'],
                timeout=30)
            path = result.decode("utf-8").strip()
            if path:
                self._send_json({"path": path})
            else:
                self._send_error("未选择目录")
        except subprocess.TimeoutExpired:
            self._send_error("选择超时")
        except subprocess.CalledProcessError:
            self._send_error("用户取消选择")
        except Exception as e:
            self._send_error(str(e))

    def _handle_select_file(self):
        """POST /api/select-file — 调用 macOS 原生文件选择器，读取文件内容"""
        try:
            import subprocess
            result = subprocess.check_output(
                ["osascript", "-e",
                 'set theFile to choose file with prompt "选择要上传的文件"\nreturn POSIX path of theFile'],
                timeout=30)
            filepath = result.decode("utf-8").strip()
            if not filepath:
                self._send_error("未选择文件")
                return
            import os
            name = os.path.basename(filepath)
            fsize = os.path.getsize(filepath)
            max_size = 10 * 1024 * 1024
            if fsize > max_size:
                self._send_error(f"文件过大（最大 10MB）")
                return
            content = ""
            ext = name.split(".")[-1].lower() if "." in name else ""
            TEXT_EXTENSIONS = {'txt','md','py','js','ts','json','yaml','yml','xml','html','css','sh','bash','zsh','conf','ini','cfg','log','csv','tsv','sql','rb','go','rs','java','c','cpp','h','hpp','swift','kt','scala','php','pl','lua','r','m','mm','bat','ps1','env','gitignore','dockerfile','makefile','toml','svelte','vue','jsx','tsx','scss','less','sass'}
            if ext in TEXT_EXTENSIONS:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            self._send_json({"name": name, "content": content, "size": fsize, "path": filepath if not content else ""})
        except subprocess.TimeoutExpired:
            self._send_error("选择超时")
        except subprocess.CalledProcessError:
            self._send_error("用户取消选择")
        except Exception as e:
            self._send_error(str(e))

    def _handle_upload(self, body):
        """POST /api/upload — 文件上传（JSON base64）"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        name = data.get("name", "file")
        file_data = data.get("data", "")
        if not file_data:
            self._send_error("data 不能为空")
            return
        import base64
        try:
            raw = base64.b64decode(file_data)
        except Exception:
            self._send_error("Invalid base64 data")
            return
        max_size = 10 * 1024 * 1024  # 10MB
        if len(raw) > max_size:
            self._send_error(f"文件过大（最大 10MB）")
            return
        uploads_dir = os.path.join(SCRIPT_DIR, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        safe_name = os.path.basename(name)
        filepath = os.path.join(uploads_dir, safe_name)
        counter = 1
        while os.path.isfile(filepath):
            parts = os.path.splitext(safe_name)
            filepath = os.path.join(uploads_dir, f"{parts[0]}_{counter}{parts[1]}")
            counter += 1
        with open(filepath, "wb") as f:
            f.write(raw)
        self._send_json({
            "path": filepath,
            "name": os.path.basename(filepath),
            "size": len(raw)
        })

    def _handle_upsert_model(self, body):
        """POST /api/models-config — 添加或更新模型配置"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        entry_id = data.get("id", "")
        if entry_id:
            # 更新
            ok = update_model_entry(entry_id, data)
            if ok:
                init_agent()
                self._send_json({"ok": True})
            else:
                self._send_error("Model not found", 404)
        else:
            # 新增
            name = data.get("name", "").strip()
            base_url = data.get("base_url", "").strip()
            api_key = data.get("api_key", "").strip()
            model = data.get("model", "").strip()
            if not base_url or not model:
                self._send_error("base_url 和 model 不能为空")
                return
            cfg = load_config()
            entry = add_model_entry(name, base_url, api_key, model, set_default=not cfg.get("models"))
            if entry.get("is_default"):
                init_agent()
            self._send_json(entry)

    def _handle_delete_model(self, body):
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        entry_id = data.get("id", "")
        if not entry_id:
            self._send_error("id 不能为空")
            return
        ok = delete_model_entry(entry_id)
        if ok:
            init_agent()
            self._send_json({"ok": True})
        else:
            self._send_error("Model not found", 404)

    def _handle_set_default_model(self, body):
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        entry_id = data.get("id", "")
        if not entry_id:
            self._send_error("id 不能为空")
            return
        ok = set_default_model(entry_id)
        if ok:
            init_agent()
            self._send_json({"ok": True})
        else:
            self._send_error("Model not found", 404)

    # ══════════════════════════════════════════════════════════════════════
    # 会话管理 API
    # ══════════════════════════════════════════════════════════════════════

    def _handle_list_sessions(self):
        index = _load_index()
        # 按更新时间倒序
        index.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        self._send_json(index)

    def _handle_create_session(self, body):
        data = json.loads(body) if body else {}
        title = data.get("title", "")
        session = create_session(title)
        self._send_json(session)

    def _handle_sync(self, body, session_id):
        """/sync 接口：返回格式化后的历史上下文"""
        try:
            data = json.loads(body) if body else {}
            max_msgs = data.get("max_messages", 20)
        except:
            max_msgs = 20
        context = format_sync_context(session_id, max_msgs)
        if context:
            self._send_json({"context": context})
        else:
            self._send_error("Session not found", 404)

    def _handle_rename_session(self, body, session_id):
        """POST /api/sessions/<id>/rename — 重命名会话"""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return
        title = data.get("title", "").strip()
        if not title:
            self._send_error("title 不能为空")
            return
        ok = rename_session(session_id, title)
        if ok:
            self._send_json({"ok": True})
        else:
            self._send_error("Session not found", 404)

    def _handle_sync_all(self, body):
        """汇总所有历史对话，并持久化结果到当前会话"""
        index = _load_index()
        # 从请求体获取当前 session_id，或回退到全局状态
        try:
            req_data = json.loads(body) if body else {}
        except:
            req_data = {}
        current_id = req_data.get("session_id", _current_session_id)
        # 排除当前会话
        others = [s for s in index if s["id"] != current_id]
        if not others:
            self._send_json({"context": ""})
            return
        parts = []
        for s in others[:5]:  # 最多取最近 5 个
            session = get_session(s["id"])
            if not session:
                continue
            title = session.get("title", "对话")
            msgs = session.get("messages", [])[-10:]  # 每个对话取最近 10 条
            lines = []
            for msg in msgs:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")[:200]
                lines.append(f"  [{role}]: {content}")
            if lines:
                parts.append(f"## {title}\n" + "\n".join(lines))
        context = "\n\n".join(parts) if parts else ""

        # 持久化同步结果到当前会话
        if context and current_id:
            sync_content = f"📋 已汇总所有历史对话上下文：\n\n{context}"
            append_messages(current_id, [
                {"role": "user", "content": "/同步", "timestamp": time.time()},
                {"role": "assistant", "content": sync_content, "timestamp": time.time()},
            ])

        self._send_json({"context": context})

    # ══════════════════════════════════════════════════════════════════════
    # L4 会话摘要
    # ══════════════════════════════════════════════════════════════════════

    def _write_l4_summary(self, session_id, prompt, full_content, tool_msgs):
        """对话结束时自动写入 L4 会话摘要（纯文本，无需 LLM）"""
        if not session_id:
            return
        try:
            from memory import write_l4
            parts = []
            # 用户提问概要
            q = prompt.strip()[:200].replace("\n", " ")
            if q:
                parts.append(f"用户: {q}")
            # AI 回复概要
            a = full_content.strip()[:300].replace("\n", " ")
            if a:
                parts.append(f"AI: {a}")
            # 工具调用
            names = set()
            for tm in tool_msgs:
                n = tm.get("name", "")
                if n:
                    names.add(n)
            if names:
                parts.append(f"工具: {', '.join(sorted(names))}")
            summary = "\n".join(parts) if parts else "(空对话)"
            write_l4(session_id, summary)
        except Exception:
            pass  # L4 写入失败不影响主流程

    # ══════════════════════════════════════════════════════════════════════
    # 对话流式
    # ══════════════════════════════════════════════════════════════════════

    def _handle_chat(self, body):
        global _current_session_id, _abort_flag
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return

        prompt = data.get("prompt", "").strip()
        session_id = data.get("session_id", _current_session_id)
        if session_id:
            _current_session_id = session_id
        if not prompt:
            self._send_error("Empty prompt")
            return

        if _agent is None or _llm is None:
            init_agent()

        _abort_flag.clear()

        # SSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send(data_dict):
            try:
                msg = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
                self.request.sendall(msg)
            except (BrokenPipeError, ConnectionError, OSError):
                _agent.abort()

        # 保存用户消息到会话
        user_msg = {"role": "user", "content": prompt, "timestamp": time.time()}
        if session_id:
            append_messages(session_id, [user_msg])

        # 从持久化的会话文件还原 Agent 历史（刷新/切换会话/重启后仍保留上下文）
        if session_id:
            session = get_session(session_id)
            if session and session.get("messages"):
                _agent.reset()
                msgs = session["messages"]
                # 排除刚保存的最后一条用户消息（_agent.run() 会重新添加）
                for msg in msgs[:-1]:
                    role = msg.get("role", "")
                    if role in ("user", "assistant", "tool"):
                        entry = {"role": role, "content": msg.get("content", "")}
                        if role == "tool" and msg.get("tool_call_id"):
                            entry["tool_call_id"] = msg["tool_call_id"]
                        _agent.history.append(entry)

        full_content = ""
        assistant_msg = {"role": "assistant", "content": "", "timestamp": time.time()}
        tool_msgs = []  # 工具调用结果，随助手消息一起持久化

        # ── 全局 keepalive 定时器 ──
        # 无论 agent/LLM 在做什么，每隔 5 秒向前端发一次心跳
        _ka_stop = threading.Event()
        def _ka_loop():
            while not _ka_stop.wait(timeout=5):
                try:
                    msg = json.dumps({"type": "keepalive"}, ensure_ascii=False)
                    self.request.sendall(f"data: {msg}\n\n".encode("utf-8"))
                except (BrokenPipeError, ConnectionError, OSError):
                    break
        ka_thread = threading.Thread(target=_ka_loop, daemon=True)
        ka_thread.start()

        try:
            for event in _agent.run(_llm, prompt):
                if _abort_flag.is_set():
                    _agent.abort()
                    if assistant_msg["content"]:
                        assistant_msg["content"] += "\n\n⏹ 已中断"
                        if session_id:
                            append_messages(session_id, [assistant_msg] + tool_msgs)
                    send({"type": "done", "content": full_content, "aborted": True})
                    return

                if event["type"] == "text":
                    full_content += event["content"]
                    assistant_msg["content"] = full_content
                    send({"type": "delta", "content": event["content"]})

                elif event["type"] == "tool_call":
                    send({"type": "tool_call", "name": event["name"],
                          "args": json.dumps(event["args"], ensure_ascii=False)[:300]})

                elif event["type"] == "tool_result":
                    send({"type": "tool_result", "name": event["name"], "result": event["result"][:200]})
                    # 持久化工具调用结果
                    tool_msgs.append({
                        "role": "tool",
                        "content": str(event["result"])[:8000],
                        "tool_call_id": event.get("tool_call_id", ""),
                        "name": event["name"],
                        "timestamp": time.time()
                    })

                elif event["type"] == "done":
                    assistant_msg["content"] = full_content
                    if session_id:
                        append_messages(session_id, [assistant_msg] + tool_msgs)
                    send({"type": "done", "content": full_content})
                    # 自动写入 L4 会话摘要
                    self._write_l4_summary(session_id, prompt, full_content, tool_msgs)
                    return

                elif event["type"] == "error":
                    error_msg = full_content + "\n\n⚠️ " + event["content"] if full_content else "⚠️ " + event["content"]
                    assistant_msg["content"] = error_msg
                    if session_id:
                        append_messages(session_id, [assistant_msg] + tool_msgs)
                    send({"type": "error", "content": event["content"]})
                    self._write_l4_summary(session_id, prompt, full_content, tool_msgs)
                    return

        except Exception as e:
            import traceback
            print(f"[XQ] Chat error: {traceback.format_exc()}")
            if session_id:
                assistant_msg["content"] = full_content + "\n\n⚠️ " + str(e)
                append_messages(session_id, [assistant_msg] + tool_msgs)
            send({"type": "error", "content": str(e)})
        finally:
            _ka_stop.set()
            ka_thread.join(timeout=2)
            send({"type": "__end__"})
            # 对话结束，卸载按需加载的技能
            try:
                from skill_loader import unload_temp_skills
                unload_temp_skills()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════
    # 中断
    # ══════════════════════════════════════════════════════════════════════

    def _handle_abort(self):
        _abort_flag.set()
        if _agent: _agent.abort()
        self._send_json({"ok": True})

    def _handle_reset(self):
        # 重置当前会话
        self._send_json({"ok": True})


# ══════════════════════════════════════════════════════════════════════════

def run_server(port=18777):
    server = ThreadingHTTPServer(("127.0.0.1", port), XQHandler)
    print(f"\n  🎻 XQAgent 已启动")
    print(f"  ─────────────────")
    print(f"  📍 http://localhost:{port}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务已停止")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-bridges", action="store_true", help="禁用消息桥接器")
    args = parser.parse_args()

    _ensure_session_dir()
    load_config()
    init_agent()

    # 初始化技能系统（手动安装模式）
    try:
        from skill_loader import init, build_skill_index
        skills_dir = os.path.join(SCRIPT_DIR, "skills")
        init(skills_dir)
        count = len(build_skill_index())
        if count > 0:
            print(f"  📦 已安装 {count} 个技能")
    except Exception as e:
        print(f"  ⚠️ 技能加载失败: {e}")

    # 初始化消息桥接器
    if not args.no_bridges:
        try:
            from bridges import BridgeManager
            _bridge_manager = BridgeManager()
            _bridge_manager.load_all()
        except Exception as e:
            print(f"  ⚠️ 桥接器加载失败: {e}")

    port = args.port or _config.get("port", 18777)
    run_server(port)

"""
BridgeBase - 消息平台桥接器基类
纯 stdlib，零依赖。所有桥接器继承此类。
"""
import json, threading, time


class BridgeBase:
    """平台桥接器基类

    子类需实现:
        _run() — 主循环（连接平台、监听消息、调用 _call_xqagent、回复）
        _send_message(recipient: str, text: str) — 发送回复消息
    """

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.label = config.get("name", self.__class__.__name__)
        self._thread: threading.Thread = None
        self._stop_flag = threading.Event()
        self._running = False
        self._error = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def error(self) -> str:
        return self._error

    # ── 生命周期 ──

    def start(self):
        """启动桥接器（异步，后台线程）"""
        if not self.enabled:
            return
        if self._running:
            return
        self._stop_flag.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run_wrapper, daemon=True, name=f"bridge-{self.label}")
        self._thread.start()

    def stop(self):
        """停止桥接器"""
        self._stop_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._running = False

    def _run_wrapper(self):
        """包装 _run，捕获异常并更新状态"""
        self._running = True
        try:
            self._run()
        except Exception as e:
            self._error = str(e)
            import traceback
            print(f"  🌉 [{self.label}] 异常退出: {traceback.format_exc()}")
        finally:
            self._running = False

    def _run(self):
        """主循环（子类实现）"""
        raise NotImplementedError

    # ── 通信 ──

    def _call_xqagent(self, prompt: str, session_id: str = "") -> str:
        """调用 XQAgent 的 chat API（HTTP SSE），返回助手回复文本"""
        import urllib.request
        data = json.dumps({"prompt": prompt, "session_id": session_id}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:18777/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            content = ""
            while True:
                line = resp.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:])
                except json.JSONDecodeError:
                    continue
                t = event.get("type", "")
                if t == "delta":
                    content += event.get("content", "")
                elif t == "done":
                    content = event.get("content", content)
                    break
                elif t == "error":
                    return f"⚠️ 错误: {event.get('content', '未知')}"
            return content.strip()
        except Exception as e:
            return f"⚠️ 调用 XQAgent 失败: {e}"

    def _send_message(self, recipient: str, text: str):
        """发送消息到平台（子类实现）"""
        raise NotImplementedError

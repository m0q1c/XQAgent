"""
飞书桥接器（存根版）
基于飞书开放平台 Bot API + 事件订阅。

[配置说明]
1. 访问 https://open.feishu.cn/app → 创建企业自建应用
2. 获取 App ID 和 App Secret
3. 开启「机器人」能力
4. 配置事件回调：消息接收（im.message.receive_v1）
5. 回调 URL: http://<你的公网IP>:18778/feishu/callback
6. 发布应用并启用

[API 文档]
- 获取 tenant_access_token: POST /open-apis/auth/v3/tenant_access_token/internal
- 发送消息: POST /open-apis/im/v1/messages
- 事件回调: im.message.receive_v1

[注意事项]
- 需要公网 IP / 域名才能接收飞书回调
- 建议使用 ngrok / frp 内网穿透
- 签名验证：请求头 X-Lark-Signature
"""
import json, time, urllib.request
from .base import BridgeBase


class FeishuBridge(BridgeBase):
    """飞书 Bot（HTTP 回调模式，需公网地址）"""

    FEISHU_API = "https://open.feishu.cn/open-apis"

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self._tenant_token = ""
        self._token_expire = 0

    def _get_token(self) -> str:
        """获取 tenant_access_token"""
        if time.time() < self._token_expire and self._tenant_token:
            return self._tenant_token
        url = f"{self.FEISHU_API}/auth/v3/tenant_access_token/internal"
        data = json.dumps({"app_id": self.app_id, "app_secret": self.app_secret}).encode()
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0:
                    self._tenant_token = result["tenant_access_token"]
                    self._token_expire = time.time() + result.get("expire", 7200) - 60
                    return self._tenant_token
        except Exception as e:
            print(f"  [飞书] 获取 token 失败: {e}")
        return ""

    def _run(self):
        if not self.app_id or not self.app_secret:
            print(f"  ⚠️ 飞书未配置 app_id / app_secret，跳过")
            self._error = "缺少 app_id 或 app_secret"
            return

        # 验证配置
        token = self._get_token()
        if not token:
            print(f"  ❌ 飞书 token 获取失败，请检查 app_id 和 app_secret")
            self._error = "API 验证失败"
            return

        print(f"  🌉 飞书 Bot 配置已验证 ✅")
        print(f"  ⚠️  飞书需要 HTTP 回调服务器，启动监听...")

        # 启动轻量 HTTP 服务器接收飞书回调
        self._start_callback_server()

    def _start_callback_server(self):
        """启动回调 HTTP 服务器（线程内）"""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class FeishuHandler(BaseHTTPRequestHandler):
            bridge = self

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length > 0 else b""
                self._handle(body)

            def _handle(self, body: bytes):
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self._send_error("invalid json")
                    return

                # URL 验证
                if data.get("type") == "url_verification":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"challenge": data.get("challenge", "")}).encode())
                    return

                # 消息事件
                event = data.get("event", {})
                msg = event.get("message", {})
                content_str = msg.get("content", "{}")
                chat_id = msg.get("chat_id", "")
                sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

                try:
                    content = json.loads(content_str)
                    text = content.get("text", "")
                except (json.JSONDecodeError, TypeError):
                    text = ""

                if text:
                    session_id = f"feishu_{chat_id}_{sender_id}"
                    reply = self.bridge._call_xqagent(text, session_id)
                    if reply:
                        self.bridge._send_message(chat_id, reply)

                self._send_ok()

            def _send_ok(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"code":0}')

            def _send_error(self, msg):
                self.send_response(400)
                self.end_headers()

            def log_message(self, fmt, *args):
                pass  # 静默日志

        # 在 18778 端口启动回调服务器
        server = HTTPServer(("0.0.0.0", 18778), FeishuHandler)
        print(f"  🌉  飞书回调服务器已启动: http://0.0.0.0:18778/feishu/callback")
        print(f"  📖  请在飞书开放平台配置回调 URL: http://<公网IP>:18778/feishu/callback")

        while not self._stop_flag.is_set():
            server.handle_request()

        server.server_close()

    def _send_message(self, recipient: str, text: str):
        """发送飞书消息"""
        token = self._get_token()
        if not token:
            return
        url = f"{self.FEISHU_API}/im/v1/messages"
        data = json.dumps({
            "receive_id": recipient,
            "msg_type": "text",
            "content": json.dumps({"text": text[:2000]}, ensure_ascii=False)
        }).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            },
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"  [飞书] 发送失败: {e}")

"""
企业微信桥接器（存根版）
基于企业微信群机器人回调 + 应用消息推送。

[配置说明 - 应用消息模式]
1. 登录 https://work.weixin.qq.com/wework_admin → 应用管理 → 创建应用
2. 获取 Corp ID、Agent ID、Secret
3. 配置消息回调 URL: http://<公网IP>:18779/wecom/callback
4. 设置可信域名（需域名备案）

[配置说明 - 群机器人模式]
1. 在企业微信群 → 群设置 → 群机器人 → 添加机器人
2. 复制 Webhook URL

[API 文档]
- 获取 access_token: GET /cgi-bin/gettoken?corpid=ID&corpsecret=SECRET
- 发送应用消息: POST /cgi-bin/message/send?access_token=TOKEN
- 群机器人 Webhook: POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY

[注意事项]
- 企业微信回调需要公网 IP + 域名备案
- 可先用群机器人 Webhook 模式快速测试（只能主动发送，不能接收）
"""
import json, time, urllib.request, hashlib, xml.etree.ElementTree as ET
from .base import BridgeBase


class WeComBridge(BridgeBase):
    """企业微信 Bot（应用消息模式 + 群机器人）"""

    QYWX_API = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self, config: dict):
        super().__init__(config)
        self.corp_id = config.get("corp_id", "")
        self.agent_id = config.get("agent_id", "")
        self.secret = config.get("secret", "")
        self.webhook_url = config.get("webhook_url", "")
        self._access_token = ""
        self._token_expire = 0

    def _get_token(self) -> str:
        if time.time() < self._token_expire and self._access_token:
            return self._access_token
        url = f"{self.QYWX_API}/gettoken?corpid={self.corp_id}&corpsecret={self.secret}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                if result.get("errcode") == 0:
                    self._access_token = result["access_token"]
                    self._token_expire = time.time() + result.get("expires_in", 7200) - 60
                    return self._access_token
        except Exception as e:
            print(f"  [企业微信] 获取 token 失败: {e}")
        return ""

    def _run(self):
        if not self.corp_id or not self.secret:
            print(f"  ⚠️ 企业微信未配置，跳过")
            self._error = "缺少配置"
            return

        token = self._get_token()
        if not token:
            print(f"  ❌ 企业微信 token 获取失败")
            self._error = "API 验证失败"
            return

        print(f"  🌉 企业微信 Bot 配置已验证 ✅")
        print(f"  ⚠️  企业微信需要 HTTP 回调服务器接收消息")
        print(f"  ⚠️  当前仅支持主动发送消息（应用消息）")
        print(f"  📖  完整接入文档: https://developer.work.weixin.qq.com/")
        print(f"  🌉  等待回调接入...")

        # 启动回调服务器
        self._start_callback_server()

    def _start_callback_server(self):
        """启动回调 HTTP 服务器"""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class WeComHandler(BaseHTTPRequestHandler):
            bridge = self

            def do_GET(self):
                # 企业微信 URL 验证
                query = self.path.split("?")[-1] if "?" in self.path else ""
                params = dict(q.split("=") for q in query.split("&") if "=" in q)
                msg_signature = params.get("msg_signature", "")
                timestamp = params.get("timestamp", "")
                nonce = params.get("nonce", "")
                echostr = params.get("echostr", "")

                # 验证通过返回 echostr
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(echostr.encode())

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length > 0 else b""
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.end_headers()
                self.wfile.write(b"""
<xml>
<ToUserName><![CDATA[toUser]]></ToUserName>
<FromUserName><![CDATA[fromUser]]></FromUserName>
<CreateTime>%d</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[ok]]></Content>
</xml>
""" % int(time.time()))

            def log_message(self, fmt, *args):
                pass

        server = HTTPServer(("0.0.0.0", 18779), WeComHandler)
        print(f"  🌉  企业微信回调服务器: http://0.0.0.0:18779/wecom/callback")

        while not self._stop_flag.is_set():
            server.handle_request()
        server.server_close()

    def _send_message(self, recipient: str, text: str):
        """发送企业微信应用消息（recipient = user_id）"""
        token = self._get_token()
        if not token:
            return
        url = f"{self.QYWX_API}/message/send?access_token={token}"
        data = json.dumps({
            "touser": recipient,
            "msgtype": "text",
            "agentid": self.agent_id,
            "text": {"content": text[:2000]}
        }, ensure_ascii=False).encode()
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"  [企业微信] 发送失败: {e}")

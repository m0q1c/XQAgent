"""
钉钉桥接器（存根版）
基于钉钉开放平台机器人 + Stream 模式 / HTTP 回调。

[配置说明]
1. 访问 https://open-dev.dingtalk.com → 创建应用 → 添加机器人能力
2. 获取 App Key 和 App Secret
3. 配置消息接收模式：
   - Stream 模式（推荐）：无需公网，钉钉主动推送
   - HTTP 回调模式：需要公网 IP
4. 发布应用

[API 文档]
- 获取 access_token: POST /v1.0/oauth2/accessToken
- 发送消息: POST /v1.0/im/messages
- Stream 模式: 使用长连接接收消息

[注意事项]
- Stream 模式无需公网 IP，推荐使用
- 需要安装 dingtalk-stream 库（pip install dingtalk-stream）
- 目前暂用 HTTP 轮询占位
"""
import json, time, urllib.request
from .base import BridgeBase


class DingTalkBridge(BridgeBase):
    """钉钉 Bot"""

    DT_API = "https://oapi.dingtalk.com"

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_key = config.get("app_key", "")
        self.app_secret = config.get("app_secret", "")
        self._access_token = ""
        self._token_expire = 0

    def _get_token(self) -> str:
        if time.time() < self._token_expire and self._access_token:
            return self._access_token
        url = f"{self.DT_API}/gettoken?appkey={self.app_key}&appsecret={self.app_secret}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                result = json.loads(resp.read())
                if result.get("errcode") == 0:
                    self._access_token = result["access_token"]
                    self._token_expire = time.time() + result.get("expires_in", 7200) - 60
                    return self._access_token
        except Exception as e:
            print(f"  [钉钉] 获取 token 失败: {e}")
        return ""

    def _run(self):
        if not self.app_key or not self.app_secret:
            print(f"  ⚠️ 钉钉未配置 app_key / app_secret，跳过")
            self._error = "缺少配置"
            return

        token = self._get_token()
        if not token:
            print(f"  ❌ 钉钉 token 获取失败")
            self._error = "API 验证失败"
            return

        print(f"  🌉 钉钉 Bot 配置已验证 ✅")
        print(f"  ⚠️  钉钉推荐使用 Stream 模式（无需公网 IP）")
        print(f"  📖  完整接入文档: https://open.dingtalk.com/")
        print(f"  ⚠️  当前为占位模式，需要安装 dingtalk-stream SDK 实现完整功能")

        # 占位：不启动实际接收（等待用户配置 Stream 模式）
        while not self._stop_flag.is_set():
            time.sleep(1)

    def _send_message(self, recipient: str, text: str):
        """发送钉钉消息（recipient = 会话 ID）"""
        token = self._get_token()
        if not token:
            return
        url = f"{self.DT_API}/v1.0/im/messages"
        data = json.dumps({
            "receiver": {"receiver_type": "chat_id", "receiver_id": recipient},
            "msg_type": "text",
            "content": json.dumps({"text": text[:2000]}, ensure_ascii=False)
        }, ensure_ascii=False).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": token
            },
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"  [钉钉] 发送失败: {e}")

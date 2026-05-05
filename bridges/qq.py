"""
QQ 桥接器
基于 QQ 官方机器人 API（OpenShamrock / QQ 频道 / 官方 Bot API）。
支持：QQ 频道机器人（官方 API）+ 个人 QQ（通过 HTTP 中转）。
"""
import json, time, urllib.request, hmac, hashlib, base64
from .base import BridgeBase


class QQBridge(BridgeBase):
    """QQ 桥接器（官方机器人 API）"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_id = config.get("app_id", "")
        self.bot_token = config.get("token", "")
        self._api_base = "https://api.sgroup.qq.com"
        self._headers = {
            "Authorization": f"Bot {self.app_id}.{self.bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "XQAgent/1.0"
        }
        # 缓存：session_id -> last_seq
        self._last_seq = 0

    # ── QQ API ──

    def _get(self, path: str) -> dict:
        url = f"{self._api_base}{path}"
        req = urllib.request.Request(url, headers=self._headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            return {"error": True, "code": e.code, "body": err[:300]}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def _post(self, path: str, data: dict) -> dict:
        url = f"{self._api_base}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            return {"error": True, "code": e.code, "body": err[:300]}
        except Exception as e:
            return {"error": True, "message": str(e)}

    # ── WebSocket 信令接入（HTTP 轮询简化版）──
    # QQ 官方 API 标准是 WebSocket，这里用 REST API 轮询简化实现。
    # 实际部署建议使用官方 wss 网关，此处提供 HTTP 轮询作为轻量方案。

    def _run(self):
        if not self.app_id or not self.bot_token:
            print(f"  ⚠️ QQ 未配置 app_id / token，跳过")
            self._error = "缺少 app_id 或 token"
            return

        # 验证连接
        me = self._get("/v2/users/me")
        if me.get("error"):
            print(f"  ❌ QQ token 无效: {me.get('body', me.get('message', '无法连接'))}")
            self._error = "token 无效"
            return

        bot_name = me.get("username", me.get("id", "?"))
        print(f"  🌉 QQ Bot «{bot_name}» 已连接")

        # 获取 ws 网关地址（标准流程）
        ws_info = self._get("/gateway")
        if ws_info.get("error"):
            print(f"  ⚠️ QQ 无法获取网关: {ws_info}")
            self._error = "无法获取网关"
            return

        print(f"  🌉  网关: {ws_info.get('url', '?')}")
        print(f"  ⚠️  QQ 官方 API 标准接入需 WebSocket 连接")
        print(f"  📖  完整接入文档：https://bot.q.qq.com/wiki/")

        # HTTP 轮询模式：通过沙箱 API 获取消息
        print(f"  🌉  启动 HTTP 轮询模式（沙箱环境）...")

        while not self._stop_flag.is_set():
            try:
                # 获取 bot 所在的频道/群
                guilds = self._get("/users/@me/guilds")
                if isinstance(guilds, list):
                    for guild in guilds[:3]:
                        if self._stop_flag.is_set():
                            break
                        guild_id = guild.get("id", "")
                        self._poll_guild_messages(guild_id)
            except Exception as e:
                import traceback
                print(f"  [QQ] 轮询异常: {traceback.format_exc()}")
            time.sleep(3)

    def _poll_guild_messages(self, guild_id: str):
        """轮询频道消息（沙箱模式）"""
        channels = self._get(f"/guilds/{guild_id}/channels")
        if not isinstance(channels, list):
            return

        for ch in channels[:5]:  # 前 5 个频道
            if self._stop_flag.is_set():
                break
            if ch.get("type") != 0:  # 0=文字频道
                continue
            channel_id = ch.get("id", "")
            msgs = self._get(f"/channels/{channel_id}/messages?limit=3")
            if isinstance(msgs, list):
                for msg in msgs:
                    self._handle_message(msg, channel_id)

    def _handle_message(self, msg: dict, channel_id: str):
        """处理单条消息"""
        msg_id = msg.get("id", "")
        content = msg.get("content", "").strip()
        author = msg.get("author", {})

        if not content or content.startswith("/"):
            return
        # 忽略机器人自己的消息
        if author.get("bot"):
            return

        session_id = f"qq_{channel_id}_{author.get('id', '')}"
        reply = self._call_xqagent(content, session_id)
        if reply:
            self._send_message(channel_id, reply)

    # ── 发送消息 ──

    def _send_message(self, recipient: str, text: str):
        """发送 QQ 频道消息"""
        self._post(f"/channels/{recipient}/messages", {
            "content": text[:2000]
        })

"""
Discord 桥接器
基于 Discord REST API + Gateway 轮询模式。
纯 stdlib，通过 REST API 轮询最新消息（无 websocket 依赖）。
"""
import json, time, urllib.request
from .base import BridgeBase

DISCORD_API = "https://discord.com/api/v10"


class DiscordBridge(BridgeBase):
    """Discord Bot 桥接器（REST 轮询模式）"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("token", "")
        self._headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "XQAgent/1.0"
        }
        # 缓存：channel_id -> last_message_id
        self._last_msg: dict[str, str] = {}
        # 已知的频道列表
        self._channels: list[dict] = []

    # ── Discord REST API ──

    def _get(self, path: str) -> dict:
        url = f"{DISCORD_API}{path}"
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
        url = f"{DISCORD_API}{path}"
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

    # ── 主循环 ──

    def _run(self):
        if not self.bot_token:
            print(f"  ⚠️ Discord 未配置 token，跳过")
            self._error = "缺少 token"
            return

        # 验证 token - 获取 bot 信息
        me = self._get("/users/@me")
        if me.get("error"):
            print(f"  ❌ Discord token 无效: {me.get('body', me.get('message', '无法连接'))}")
            self._error = "token 无效"
            return

        bot_name = me.get("global_name", me.get("username", "?"))
        print(f"  🌉 Discord Bot «{bot_name}» 已连接")

        # 获取 bot 可访问的频道
        self._refresh_channels()

        print(f"  🌉  监控 {len(self._channels)} 个频道")

        while not self._stop_flag.is_set():
            try:
                for ch in self._channels:
                    if self._stop_flag.is_set():
                        break
                    self._poll_channel(ch["id"])
            except Exception as e:
                import traceback
                print(f"  [Discord] 轮询异常: {traceback.format_exc()}")
            time.sleep(3)  # 每 3 秒轮询一轮

    def _refresh_channels(self):
        """获取 bot 可见的文本频道"""
        # 获取 bot 所在的 guilds
        guilds = self._get("/users/@me/guilds")
        if isinstance(guilds, dict) and guilds.get("error"):
            return
        if not isinstance(guilds, list):
            return

        self._channels = []
        for guild in guilds[:5]:  # 最多 5 个服务器
            guild_id = guild.get("id")
            if not guild_id:
                continue
            channels = self._get(f"/guilds/{guild_id}/channels")
            if isinstance(channels, list):
                for ch in channels:
                    if ch.get("type") == 0:  # 文本频道
                        self._channels.append({
                            "id": ch["id"],
                            "name": ch.get("name", "?"),
                            "guild_name": guild.get("name", "?")
                        })

    def _poll_channel(self, channel_id: str):
        """轮询单个频道的新消息"""
        last_id = self._last_msg.get(channel_id, "")
        params = "?limit=1"
        if last_id:
            params = f"?after={last_id}&limit=5"

        msgs = self._get(f"/channels/{channel_id}/messages{params}")
        if isinstance(msgs, dict) and msgs.get("error"):
            return
        if not isinstance(msgs, list) or not msgs:
            return

        # 按时间正序处理（最早的先处理）
        for msg in reversed(msgs):
            msg_id = msg.get("id", "")
            # 忽略 bot 自己的消息
            author = msg.get("author", {})
            if author.get("id") == self._get_bot_id():
                continue
            # 忽略系统消息
            if msg.get("type", 0) != 0:
                continue

            content = msg.get("content", "").strip()
            if not content or content.startswith("/"):
                continue

            # 更新 last_msg
            if msg_id > self._last_msg.get(channel_id, ""):
                self._last_msg[channel_id] = msg_id

            # 处理消息
            author_name = author.get("global_name", author.get("username", "?"))
            guild_name = ""
            for ch in self._channels:
                if ch["id"] == channel_id:
                    guild_name = ch.get("guild_name", "")
                    break
            prefix = f"[{guild_name}] " if guild_name else ""

            session_id = f"discord_{channel_id}_{author.get('id', '')}"
            reply = self._call_xqagent(content, session_id)
            if reply:
                self._send_message(channel_id, reply)

    def _get_bot_id(self) -> str:
        """获取 bot 自己的用户 ID"""
        me = self._get("/users/@me")
        if isinstance(me, dict) and not me.get("error"):
            return me.get("id", "")
        return ""

    # ── 发送消息 ──

    def _send_message(self, recipient: str, text: str):
        """发送 Discord 消息（最多 2000 字符）"""
        if not text:
            return
        chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
        for chunk in chunks:
            self._post(f"/channels/{recipient}/messages", {"content": chunk})

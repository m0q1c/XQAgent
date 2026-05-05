"""
Telegram 桥接器
基于 Telegram Bot API 长轮询（getUpdates），纯 stdlib，零依赖。
"""
import json, time, urllib.request, urllib.parse
from .base import BridgeBase


class TelegramBridge(BridgeBase):
    """Telegram Bot 桥接器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("token", "")
        self._api_base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        self._offset = 0

    # ── Telegram API 调用 ──

    def _api(self, method: str, params: dict = None) -> dict:
        if not self._api_base:
            return {"ok": False}
        url = f"{self._api_base}/{method}"
        data = urllib.parse.urlencode(params or {}).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            print(f"  [Telegram] HTTP {e.code}: {err[:200]}")
            return {"ok": False, "error": err}
        except Exception as e:
            print(f"  [Telegram] 请求失败: {e}")
            return {"ok": False, "error": str(e)}

    # ── 主循环 ──

    def _run(self):
        if not self.bot_token:
            print(f"  ⚠️ Telegram 未配置 token，跳过")
            self._error = "缺少 token"
            return

        # 验证 token
        me = self._api("getMe")
        if not me.get("ok"):
            print(f"  ❌ Telegram token 无效: {me.get('error', '无法连接')}")
            self._error = "token 无效或无法连接"
            return

        bot_name = me.get("result", {}).get("first_name", "?")
        print(f"  🌉 Telegram Bot «{bot_name}» 已连接")

        while not self._stop_flag.is_set():
            try:
                result = self._api("getUpdates", {
                    "offset": self._offset,
                    "timeout": 30,
                    "allowed_updates": json.dumps(["message"])
                })
                if result.get("ok"):
                    for update in result.get("result", []):
                        self._offset = update["update_id"] + 1
                        self._handle_update(update)
            except Exception as e:
                import traceback
                print(f"  [Telegram] 轮询异常: {traceback.format_exc()}")
            time.sleep(0.5)

    def _handle_update(self, update: dict):
        """处理单条更新"""
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")

        if not chat_id or not text:
            return

        # 忽略机器人自己的消息和命令
        if msg.get("from", {}).get("is_bot"):
            return
        if text.startswith("/"):
            return

        # 调用 XQAgent
        session_id = f"telegram_{chat_id}"
        reply = self._call_xqagent(text, session_id)

        # 回复（Telegram 限制 4096 字符）
        if reply:
            self._send_message(str(chat_id), reply[:4000])

    # ── 发送消息 ──

    def _send_message(self, recipient: str, text: str):
        """发送 Telegram 消息"""
        self._api("sendMessage", {
            "chat_id": recipient,
            "text": text,
            "parse_mode": "HTML"
        })

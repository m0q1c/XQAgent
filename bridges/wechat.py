"""
微信桥接器 — 基于 ilink bot API（腾讯官方微信机器人服务）

扫码与微信 ClawBot 建立联系，通过 ilink bot 协议收发消息。
纯 stdlib 实现，零外部依赖。

流程：
  1. GET /ilink/bot/get_bot_qrcode → 获取机器人二维码
  2. 用户扫码 → 轮询 GET /ilink/bot/get_qrcode_status
  3. 确认后获得 bot_token → 后续用 token 收/发消息
"""
import json, time, threading, base64, urllib.request, urllib.error, os
from .base import BridgeBase

ILINK_BASE = "https://ilinkai.weixin.qq.com"
BOT_TYPE = "3"
CLIENT_VERSION = "131072"

LOGIN_TIMEOUT = 480
QR_POLL_INTERVAL = 1


class WeChatBridge(BridgeBase):
    """微信 ClawBot 桥接器 — 纯 HTTP，零依赖"""

    def __init__(self, config: dict = None):
        super().__init__(config or {})
        # ── 扫码登录状态 ──
        self._login_status = "idle"      # idle | waiting_scan | scanned | confirmed | error
        self._qrcode = None              # 二维码 base64 PNG（前端显示）
        self._qrcode_hash = None         # 二维码 hash（轮询状态用）
        self._qrcode_url = None          # 二维码链接
        self._bot_token = ""
        self._bot_id = ""
        self._user_id = ""
        self._login_error = None
        self._cred_path = os.path.expanduser("~/.xqagent_wechat_cred.json")

        # ── 消息收发 ──
        self._stop_flag = threading.Event()
        self._poll_thread = None
        self._get_updates_buf = ""
        self._context_tokens = {}        # user_id -> context_token

    # ══════════════════════════════════════════════════════════════════
    # 扫码登录
    # ══════════════════════════════════════════════════════════════════

    def qr_login(self) -> dict:
        """启动扫码登录流程，返回当前状态和二维码"""
        # 如果已有连接，直接返回状态
        if self._login_status == "confirmed":
            self._start_poll_loop()
            return self._get_state()

        if self._login_status in ("waiting_scan", "scanned"):
            return self._get_state()

        # 重置状态
        self._qrcode = None
        self._qrcode_hash = None
        self._qrcode_url = None
        self._bot_token = ""
        self._bot_id = ""
        self._user_id = ""
        self._login_error = None
        self._login_status = "waiting_scan"

        # 后台线程处理登录
        t = threading.Thread(target=self._do_login, daemon=True, name="wechat-login")
        t.start()

        # 等待二维码生成（最多 5s）
        for _ in range(50):
            if self._qrcode:
                break
            time.sleep(0.1)

        return self._get_state()

    def _do_login(self):
        """后台扫码登录流程"""
        try:
            # 1. 获取二维码
            qr_data = self._fetch_qrcode()
            if not qr_data:
                self._login_status = "error"
                self._login_error = "获取二维码失败"
                return

            self._qrcode = qr_data.get("qrcode_png", "")
            self._qrcode_hash = qr_data.get("qrcode", "")
            self._qrcode_url = qr_data.get("qrcode_img_content", "")

            if not self._qrcode:
                self._login_status = "error"
                self._login_error = "二维码数据为空"
                return

            # 2. 轮询扫码状态
            deadline = time.time() + LOGIN_TIMEOUT
            scanned = False

            while not self._stop_flag.is_set() and time.time() < deadline:
                status = self._poll_qr_status()
                if not status:
                    time.sleep(QR_POLL_INTERVAL)
                    continue

                s = status.get("status", "wait")

                if s == "wait":
                    pass  # 继续等
                elif s == "scaned":
                    if not scanned:
                        scanned = True
                        self._login_status = "scanned"
                elif s == "expired":
                    # 二维码过期，尝试重新获取
                    self._qrcode = None
                    self._qrcode_hash = None
                    self._qrcode_url = None
                    qr2 = self._fetch_qrcode()
                    if qr2:
                        self._qrcode = qr2.get("qrcode_png", "")
                        self._qrcode_hash = qr2.get("qrcode", "")
                        self._qrcode_url = qr2.get("qrcode_img_content", "")
                    scanned = False
                elif s == "confirmed":
                    token = status.get("bot_token", "")
                    bot_id = status.get("ilink_bot_id", "")
                    user_id = status.get("ilink_user_id", "")
                    if token and bot_id:
                        self._bot_token = token
                        self._bot_id = bot_id
                        self._user_id = user_id or ""
                        self._login_status = "confirmed"
                        self._running = True
                        # 保存凭证
                        self._save_cred()
                        # 启动消息轮询
                        self._start_poll_loop()
                        return
                    else:
                        self._login_status = "error"
                        self._login_error = "扫码确认后未获取到 token"
                        return

                time.sleep(QR_POLL_INTERVAL)

            # 超时
            if self._login_status not in ("confirmed", "error"):
                self._login_status = "idle"
                self._login_error = "扫码超时"

        except Exception as e:
            self._login_status = "error"
            self._login_error = str(e)

    def _fetch_qrcode(self) -> dict:
        """GET /ilink/bot/get_bot_qrcode — 获取机器人二维码"""
        url = f"{ILINK_BASE}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}"
        try:
            req = urllib.request.Request(url, headers={
                "iLink-App-Id": "bot",
                "iLink-App-ClientVersion": CLIENT_VERSION,
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            # 用 qrcode_img_content URL 生成二维码图片（用户扫码后打开微信授权页）
            qr_url = data.get("qrcode_img_content", "")
            if qr_url:
                data["qrcode_png"] = self._gen_qr_png(qr_url)
            return data
        except Exception as e:
            print(f"  [微信] 获取二维码失败: {e}")
            return {}

    @staticmethod
    def _gen_qr_png(text: str) -> str:
        """生成二维码 PNG 的 base64 数据"""
        try:
            import qrcode
            import io
            qr = qrcode.QRCode(box_size=5, border=2)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except ImportError:
            return ""

    def _poll_qr_status(self) -> dict:
        """GET /ilink/bot/get_qrcode_status — 轮询扫码状态"""
        import urllib.parse
        if not self._qrcode_hash:
            return {"status": "wait"}
        url = f"{ILINK_BASE}/ilink/bot/get_qrcode_status?qrcode={urllib.parse.quote(self._qrcode_hash)}"
        try:
            req = urllib.request.Request(url, headers={
                "iLink-App-Id": "bot",
                "iLink-App-ClientVersion": CLIENT_VERSION,
            })
            with urllib.request.urlopen(req, timeout=QR_POLL_INTERVAL + 5) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 408:
                return {"status": "wait"}
            raise
        except Exception as e:
            print(f"  [微信] 轮询状态失败: {e}")
            return {}

    def _save_cred(self):
        """保存凭证到文件"""
        try:
            with open(self._cred_path, "w") as f:
                json.dump({
                    "bot_token": self._bot_token,
                    "bot_id": self._bot_id,
                    "user_id": self._user_id,
                    "base_url": ILINK_BASE,
                }, f, indent=2)
        except Exception:
            pass

    def _load_cred(self):
        """尝试从文件加载凭证"""
        try:
            if os.path.isfile(self._cred_path):
                with open(self._cred_path) as f:
                    cred = json.load(f)
                self._bot_token = cred.get("bot_token", "")
                self._bot_id = cred.get("bot_id", "")
                self._user_id = cred.get("user_id", "")
                if self._bot_token and self._bot_id:
                    self._login_status = "confirmed"
                    self._running = True
                    return True
        except Exception:
            pass
        return False

    def get_qr_status(self) -> dict:
        """获取当前扫码状态"""
        result = {"status": self._login_status}
        if self._qrcode:
            result["qrcode"] = self._qrcode
        if self._bot_token:
            result["connected"] = True
            result["bot_id"] = self._bot_id
        if self._login_error:
            result["error"] = self._login_error
        return result

    def qr_logout(self):
        """断开连接"""
        self._login_status = "idle"
        self._qrcode = None
        self._qrcode_hash = None
        self._qrcode_url = None
        self._bot_token = ""
        self._bot_id = ""
        self._user_id = ""
        self._login_error = None
        self._running = False
        self._stop_flag.set()
        # 删除凭证文件
        try:
            if os.path.isfile(self._cred_path):
                os.remove(self._cred_path)
        except Exception:
            pass

    def _get_state(self) -> dict:
        """获取当前状态（用于 API 返回）"""
        return self.get_qr_status()

    # ══════════════════════════════════════════════════════════════════
    # 消息收发（ilink bot API）
    # ══════════════════════════════════════════════════════════════════

    def start(self):
        """启动桥接器（加载已有凭证或等待扫码）"""
        self._load_cred()
        if self._login_status == "confirmed":
            print(f"  🌉 微信 ClawBot 已加载凭证 (bot_id={self._bot_id})")
            self._start_poll_loop()
        else:
            print(f"  🌉 微信 ClawBot 待扫码连接")

    def stop(self):
        self._stop_flag.set()
        self._running = False

    def _start_poll_loop(self):
        """启动消息轮询线程"""
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="wechat-poll"
        )
        self._poll_thread.start()

    def _poll_loop(self):
        """长轮询收消息"""
        failures = 0
        while not self._stop_flag.is_set() and self._login_status == "confirmed":
            try:
                resp = self._get_updates()
                if resp:
                    ret = resp.get("ret", 0)
                    errcode = resp.get("errcode", 0)
                    # session 过期（token 失效或 bot 被删除）
                    if ret == -14 or errcode == -14:
                        print("  [微信] session 过期，需要重新扫码")
                        self._login_status = "idle"
                        self._running = False
                        try:
                            if os.path.isfile(self._cred_path):
                                os.remove(self._cred_path)
                        except Exception:
                            pass
                        break
                    msgs = resp.get("msgs", [])
                    for msg in msgs:
                        self._on_message(msg)
                    new_buf = resp.get("get_updates_buf", "")
                    if new_buf:
                        self._get_updates_buf = new_buf
                    failures = 0
                else:
                    failures += 1
            except Exception as e:
                failures += 1
                if not self._stop_flag.is_set():
                    if failures >= 10:
                        print(f"  [微信] 连续失败 {failures} 次，暂停 30s")
                        self._stop_flag.wait(30)
                    else:
                        time.sleep(5)
            time.sleep(0.5)

    def _get_updates(self) -> dict:
        """POST /ilink/bot/getupdates — 长轮询收消息"""
        if not self._bot_token:
            return {}
        url = f"{ILINK_BASE}/ilink/bot/getupdates"
        data = json.dumps({
            "get_updates_buf": self._get_updates_buf,
            "base_info": {"channel_version": "2.0.0"},
        }).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {self._bot_token}")
            req.add_header("AuthorizationType", "ilink_bot_token")
            req.add_header("iLink-App-Id", "bot")
            req.add_header("iLink-App-ClientVersion", CLIENT_VERSION)
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read())
        except Exception:
            return {}

    def _on_message(self, raw_msg: dict):
        """处理收到的消息"""
        msg_type = raw_msg.get("message_type", 0)
        if msg_type != 1:
            return
        from_user = raw_msg.get("from_user_id", "")
        context_token = raw_msg.get("context_token", "")
        content = ""
        items = raw_msg.get("item_list", [])
        for item in items:
            if item.get("type") == 1:
                text_item = item.get("text_item", {})
                content = text_item.get("text", "")
        if context_token and from_user:
            self._context_tokens[from_user] = context_token
        if not content or not from_user:
            return

        print(f"  [微信] 收到来自 {from_user}: {content[:80]}")
        try:
            # 1. 通过 agent 处理并获取回复
            reply = self._call_xqagent(content, session_id=f"wechat_{from_user}")
            if reply and not reply.startswith("⚠️"):
                self._send_message(from_user, reply)
            # 2. 同步到当前 XQAgent 会话（如果有）
            self._sync_to_active_session(from_user, content, reply)
        except Exception as e:
            print(f"  [微信] 处理消息失败: {e}")

    def _sync_to_active_session(self, from_user: str, msg: str, reply: str = ""):
        """同步微信消息到 XQAgent 当前活跃会话"""
        try:
            data = json.dumps({
                "message": f"[微信 {from_user[:8]}]: {msg}",
                "reply": reply or "（已处理）",
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:18777/api/session/append",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as e:
            print(f"  [微信] 同步到会话失败: {e}")

    def _send_message(self, recipient: str, text: str):
        """POST /ilink/bot/sendmessage — 发送消息"""
        if not self._bot_token:
            return
        import uuid
        context_token = self._context_tokens.get(recipient, "")
        url = f"{ILINK_BASE}/ilink/bot/sendmessage"
        data = json.dumps({
            "base_info": {"channel_version": "2.0.0"},
            "msg": {
                "from_user_id": "",
                "to_user_id": recipient,
                "client_id": uuid.uuid4().hex[:16],
                "message_type": 2,
                "message_state": 2,
                "item_list": [{"type": 1, "text_item": {"text": text[:2000]}}],
                "context_token": context_token,
            }
        }).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {self._bot_token}")
            req.add_header("AuthorizationType", "ilink_bot_token")
            req.add_header("iLink-App-Id", "bot")
            req.add_header("iLink-App-ClientVersion", CLIENT_VERSION)
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as e:
            print(f"  [微信] 发送失败: {e}")

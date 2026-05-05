"""
BridgeManager - 桥接器管理器
加载所有已启用的桥接器，统一管理启停和状态查询。
"""
import importlib, threading, time
from .config import load_bridge_config

# 已注册的桥接器类型：platform_name -> module_path.class_name
BUILTIN_BRIDGES = {
    "telegram": "bridges.telegram.TelegramBridge",
    "qq": "bridges.qq.QQBridge",
    "discord": "bridges.discord.DiscordBridge",
    "feishu": "bridges.feishu.FeishuBridge",
    "wecom": "bridges.wecom.WeComBridge",
    "dingtalk": "bridges.dingtalk.DingTalkBridge",
    "wechat": "bridges.wechat.WeChatBridge",
}


class BridgeManager:
    """统一桥接器管理器"""

    def __init__(self):
        self._bridges: dict[str, object] = {}
        self._loaded = False

    def load_all(self):
        """加载配置并启动所有已启用的桥接器"""
        if self._loaded:
            return
        self._loaded = True

        cfg = load_bridge_config()
        for platform, bridge_cfg in cfg.items():
            if platform not in BUILTIN_BRIDGES:
                continue
            if not bridge_cfg.get("enabled", False):
                continue

            bridge = self._create_bridge(platform, bridge_cfg)
            if bridge:
                self._bridges[platform] = bridge
                bridge.start()
                time.sleep(0.2)  # 逐个启动，避免日志乱序

    def _create_bridge(self, platform: str, bridge_cfg: dict):
        """动态导入并创建桥接器实例"""
        try:
            path = BUILTIN_BRIDGES[platform]
            module_path, class_name = path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls(bridge_cfg)
        except ImportError as e:
            print(f"  ⚠️ [{platform}] 模块加载失败: {e}")
        except Exception as e:
            print(f"  ⚠️ [{platform}] 创建失败: {e}")
        return None

    def stop_all(self):
        """停止所有桥接器"""
        for platform, bridge in self._bridges.items():
            bridge.stop()

    def get_status(self) -> dict:
        """获取所有桥接器状态"""
        status = {}
        for platform, bridge in self._bridges.items():
            status[platform] = {
                "running": bridge.running,
                "enabled": bridge.enabled,
                "label": bridge.label,
                "error": bridge.error,
            }
        # 补充未启用的平台
        for platform in BUILTIN_BRIDGES:
            if platform not in self._bridges:
                status[platform] = {
                    "running": False,
                    "enabled": False,
                    "label": "",
                    "error": None,
                }
        return status

    def restart(self, platform: str = None):
        """重启单个或所有桥接器"""
        if platform:
            bridge = self._bridges.get(platform)
            if bridge:
                bridge.stop()
                time.sleep(0.5)
                cfg = load_bridge_config().get(platform, {})
                new_bridge = self._create_bridge(platform, cfg)
                if new_bridge:
                    self._bridges[platform] = new_bridge
                    new_bridge.start()
        else:
            self.stop_all()
            time.sleep(0.5)
            self._bridges.clear()
            self._loaded = False
            self.load_all()


# 全局单例
_manager = BridgeManager()


def get_manager() -> BridgeManager:
    return _manager

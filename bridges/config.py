"""
桥接器配置管理
"""
import json, os

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "telegram": {
        "enabled": False,
        "name": "Telegram",
        "token": "",
        "description": "Telegram Bot - 在 @BotFather 创建 Bot 获取 token"
    },
    "qq": {
        "enabled": False,
        "name": "QQ",
        "app_id": "",
        "token": "",
        "description": "QQ 官方机器人 - 在 qq.qq.com 创建应用获取 app_id 和 token"
    },
    "discord": {
        "enabled": False,
        "name": "Discord",
        "token": "",
        "description": "Discord Bot - 在 Discord Developer Portal 创建 Bot 获取 token"
    },
    "feishu": {
        "enabled": False,
        "name": "飞书",
        "app_id": "",
        "app_secret": "",
        "description": "飞书 Bot - 在飞书开放平台创建应用获取 app_id 和 app_secret"
    },
    "wecom": {
        "enabled": False,
        "name": "企业微信",
        "corp_id": "",
        "agent_id": "",
        "secret": "",
        "description": "企业微信群机器人 - 在企业微信后台获取配置"
    },
    "dingtalk": {
        "enabled": False,
        "name": "钉钉",
        "app_key": "",
        "app_secret": "",
        "description": "钉钉机器人 - 在钉钉开放平台创建应用获取 app_key 和 app_secret"
    },
    "wechat": {
        "enabled": False,
        "name": "微信",
        "app_id": "",
        "app_secret": "",
        "token": "",
        "description": "微信公众号 - 在微信公众平台获取 app_id 和 app_secret"
    }
}


def load_bridge_config() -> dict:
    """加载桥接器配置，缺失字段用默认值填充"""
    if not os.path.isfile(CONFIG_PATH):
        return _merge_config(dict(DEFAULT_CONFIG))

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return _merge_config(dict(DEFAULT_CONFIG))

    # 确保所有平台都有默认字段
    for platform, defaults in DEFAULT_CONFIG.items():
        if platform not in cfg:
            cfg[platform] = dict(defaults)
        else:
            for k, v in defaults.items():
                cfg[platform].setdefault(k, v)
    return cfg


def save_bridge_config(cfg: dict):
    """保存桥接器配置"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _merge_config(cfg: dict) -> dict:
    """用默认值填充缺失字段"""
    for platform, defaults in DEFAULT_CONFIG.items():
        if platform not in cfg:
            cfg[platform] = dict(defaults)
        else:
            for k, v in defaults.items():
                cfg[platform].setdefault(k, v)
    return cfg


def get_bridge_status_text(bridges: dict) -> str:
    """生成桥接器状态文本"""
    lines = ["🌉 桥接器状态:"]
    for name, info in bridges.items():
        status = "✅ 运行中" if info.get("running") else "⏸️ 已停止"
        if info.get("error"):
            status += f" ⚠️ {info['error']}"
        lines.append(f"  {info.get('label', name)}: {status}")
    return "\n".join(lines)


# 首次启动时创建默认配置
if not os.path.isfile(CONFIG_PATH):
    save_bridge_config(dict(DEFAULT_CONFIG))

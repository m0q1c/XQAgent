#!/bin/bash
# ── XQAgent 分发打包脚本 ──
# 在另一台 Mac 上安装使用 XQAgent（内置 Python3，开箱即用）
#
# 使用方法:
#   本机: bash mac/distribute.sh              # 打包成 .zip
#   另一台 Mac: 解压后运行 install.sh          # 自动安装
#
# 前置依赖（另一台 Mac）:
#   1. LM Studio — 下载 https://lmstudio.ai/，加载 /Applications/XQAgent.app 可用的模型
#      推荐: qwen/qwen3.5-9b，也可用 lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF
#   2. 无需安装 Python3 (已内置)
#
# 安装后:
#   打开 /Applications/XQAgent.app 即可使用
#   在浏览器也可以访问: http://localhost:18777
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist"
APP_NAME="XQAgent"
VERSION="1.0.0"

echo ""
echo "  🎻 打包 XQAgent v${VERSION} 分发包"
echo "  ═══════════════════════════════════"

# ── 1. 确保 .app 是最新版本 ──
echo ""
echo "  📦 检查 .app..."
if [ ! -d "${PROJECT_DIR}/${APP_NAME}.app" ]; then
    echo "  ❌ 未找到 ${APP_NAME}.app，请先运行 mac/build.sh"
    exit 1
fi

# ── 2. 创建分发目录 ──
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

echo "  📁 复制应用..."
cp -R "${PROJECT_DIR}/${APP_NAME}.app" "${DIST_DIR}/${APP_NAME}.app"

# 清理运行时数据（sessions、bridges 配置等）
rm -f "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/sessions/"*.json 2>/dev/null
rm -f "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/sessions/index.json" 2>/dev/null
rm -f "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/bridges/config.json" 2>/dev/null
rm -rf "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/memory/L4_sessions/"* 2>/dev/null
rm -rf "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/uploads/"* 2>/dev/null
rm -f "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/skill_loader.py" 2>/dev/null

echo "  📄 生成安装脚本..."

# ── 3. 创建 install.sh ──
cat > "${DIST_DIR}/install.sh" << 'INSTALL'
#!/bin/bash
# ── XQAgent 安装脚本 ──
set -e

APP_NAME="XQAgent"

echo ""
echo "  🎻 安装 XQAgent"
echo "  ═══════════════════════════════════"

echo "  ✅ Python3 已内置（无需额外安装）"

# 安装到 /Applications/
if [ -d "/Applications/${APP_NAME}.app" ]; then
    echo "  🔄 更新已有安装..."
    rm -rf "/Applications/${APP_NAME}.app"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp -R "${SCRIPT_DIR}/${APP_NAME}.app" "/Applications/${APP_NAME}.app"
echo "  ✅ 已安装到 /Applications/${APP_NAME}.app"

echo ""
echo "  ─────────────────────────────────────"
echo "  🎉 安装完成！"
echo ""
echo "  下一步："
echo "    1. 安装 LM Studio → 加载模型 → 启动服务器（端口 1234）"
echo "      下载地址: https://lmstudio.ai/"
echo ""
echo "    2. 打开 XQAgent.app（支持 macOS 14+）"
echo "       macOS 15+ 首次打开会提示未验证开发者："
echo "       方法 A: 右键点击 XQAgent.app → 打开"
echo "       方法 B: 系统设置 → 隐私与安全性 → 仍要打开"
echo "       打开后显示「正在启动 XQAgent…」等待后端就绪，即可使用"
echo ""
echo "    3. 如需修改模型地址："
echo "       在浏览器打开 http://localhost:18777"
echo "       → 模型配置 → 修改接口地址"
echo ""
echo "  命令行访问："
echo "    curl http://localhost:18777"
echo ""
echo "  如需卸载："
echo "    rm -rf /Applications/${APP_NAME}.app"
echo "  ─────────────────────────────────────"
echo ""
INSTALL

chmod +x "${DIST_DIR}/install.sh"

# ── 4. 打包为 ZIP ──
echo "  📦 打包..."
cd "$DIST_DIR"
zip -rq "${APP_NAME}-v${VERSION}.zip" "${APP_NAME}.app" "install.sh"
cd - > /dev/null

echo ""
echo "  ✅ 分发包已生成！"
echo "  ─────────────────────────────────────"
echo "  分发包: ${DIST_DIR}/${APP_NAME}-v${VERSION}.zip"
echo "  大小: $(du -h "${DIST_DIR}/${APP_NAME}-v${VERSION}.zip" | cut -f1)"
echo ""
echo "  安装步骤："
echo "    1. 解压 ${APP_NAME}-v${VERSION}.zip"
echo "    2. 在目标 Mac 上运行: bash install.sh"
echo "    3. 按提示安装 LM Studio 并加载模型"
echo "    4. 打开 XQAgent.app"
echo "  ─────────────────────────────────────"
echo ""

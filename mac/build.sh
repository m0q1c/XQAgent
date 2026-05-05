#!/bin/bash
# ── XQAgent macOS 自包含 .app 构建脚本 ──
# 将 Python3 解释器 + 精简标准库打包进 .app，开箱即用
set -e

PROJECT_DIR="/Users/m0q1c/HackTools/AI/XQAgent"
APP_NAME="XQAgent"
BIN_NAME="XQAgent"
OUTPUT_DIR="${PROJECT_DIR}/${APP_NAME}.app"
RES_DIR="${OUTPUT_DIR}/Contents/Resources"

echo ""
echo "  🎻 构建 XQAgent macOS 自包含应用"
echo "  ═══════════════════════════════════"

# ── 1. 编译 Swift 二进制 ──
echo ""
echo "  📦 编译 Swift 二进制..."

swiftc \
    -o "/tmp/${BIN_NAME}Bin" \
    "${PROJECT_DIR}/mac/Sources/main.swift" \
    "${PROJECT_DIR}/mac/Sources/AppDelegate.swift" \
    -framework Cocoa \
    -framework WebKit \
    -target arm64-apple-macos14.0 \
    -suppress-warnings \
    2>&1

if [ $? -ne 0 ]; then
    echo "  ❌ 编译失败，请检查上方错误信息"
    exit 1
fi

echo "  ✅ 编译完成"

# ── 2. 创建 .app 包 ──
echo "  📁 创建 .app 包..."

# 备份运行时数据（sessions、记忆、配置、技能等）
BACKUP_DIR="/tmp/xqagent_backup_$$"
CURRENT_APP="/Applications/XQAgent.app"
if [ -d "$CURRENT_APP" ]; then
    echo "  💾 备份运行时数据..."
    mkdir -p "$BACKUP_DIR"
    for item in sessions memory/L2_facts.txt memory/L3_records memory/L4_sessions bridges/config.json uploads config.json skills/installed.json; do
        src="$CURRENT_APP/Contents/Resources/$item"
        dst="$BACKUP_DIR/$(dirname "$item")"
        if [ -e "$src" ]; then
            mkdir -p "$dst"
            cp -R "$src" "$BACKUP_DIR/$item" 2>/dev/null || true
        fi
    done
    echo "  ✅ 备份完成"
fi

rm -rf "$OUTPUT_DIR"
mkdir -p "${RES_DIR}"
mkdir -p "${OUTPUT_DIR}/Contents/MacOS"

# ── 3. 打包 Python3 运行环境 ──
echo ""
echo "  🐍 打包 Python3 运行环境..."

PYTHON3_PATH=""  # 最终使用的 python3 路径（内置或系统）

# 查找 brew 安装的 Python 3
BREW_PYTHON=""
for CELLAR in /opt/homebrew/Cellar /usr/local/Cellar; do
    for VER in 3.11 3.12 3.10 3.9; do
        DIR=$(ls -d "$CELLAR/python@$VER"/* 2>/dev/null | sort -V | tail -1)
        if [ -n "$DIR" ] && [ -f "$DIR/Frameworks/Python.framework/Versions/$VER/bin/python$VER" ]; then
            BREW_PYTHON="$DIR"
            BREW_VER="$VER"
            break 2
        fi
    done
done

if [ -n "$BREW_PYTHON" ]; then
    echo "  发现 brew Python $BREW_VER: $BREW_PYTHON"

    PY_DIR="${RES_DIR}/python"
    FW="$BREW_PYTHON/Frameworks/Python.framework/Versions/$BREW_VER"
    mkdir -p "$PY_DIR/bin" "$PY_DIR/lib"

    # ── 复制真正的 Python 可执行文件 ──
    # Homebrew 的 bin/python3.11 是一个 thin wrapper，它会 posix_spawn
    # Resources/Python.app/Contents/MacOS/Python（真正的 Python）。
    # 我们直接复制真正的二进制，跳过 wrapper。
    REAL_PYTHON="$FW/Resources/Python.app/Contents/MacOS/Python"
    if [ -f "$REAL_PYTHON" ]; then
        cp "$REAL_PYTHON" "$PY_DIR/bin/python3"
        echo "  ✅ 复制真正的 Python 二进制 (来自 Python.app/Contents/MacOS/Python)"
    else
        # fallback: 复制 wrapper（需要配合 Resources/Python.app 结构）
        cp "$FW/bin/python$BREW_VER" "$PY_DIR/bin/python3"
        echo "  ⚠️ 未找到 Python.app/MacOS/Python，回退到 wrapper"
    fi

    # 复制 Python 动态库（4.7MB）
    cp "$FW/Python" "$PY_DIR/"

    # ── 修正 dylib 路径：从硬编码的 brew 绝对路径改为 @executable_path ──
    # 原因：Python 二进制硬编码指向 /opt/homebrew/.../Python，
    #       在 macOS 15+ 上 DYLD_LIBRARY_PATH 被 hardened runtime 剥离，
    #       导致 Python 找不到 dylib → 静默崩溃 → 白屏。
    # 方案：install_name_tool -change 改为 @executable_path/../Python，
    #       再 ad-hoc 重签二进制，使其自身能找到 dylib，不再需要 DYLD。
    PY_BIN="$PY_DIR/bin/python3"
    OLD_DYLIB=$(otool -L "$PY_BIN" 2>/dev/null | grep -o '/.*Python.framework.*/Python' | head -1 || echo "")
    if [ -n "$OLD_DYLIB" ]; then
        echo "  修正 dylib 路径: $OLD_DYLIB → @executable_path/../Python"
        install_name_tool -change "$OLD_DYLIB" "@executable_path/../Python" "$PY_BIN" 2>&1
        # 重签二进制（install_name_tool 破坏了原有签名）
        codesign --force --sign - "$PY_BIN" 2>&1
        echo "  ✅ dylib 路径已修正，二进制已重签"
    else
        echo "  ⚠️ 未找到 Python dylib 链接，跳过修正"
    fi

    # 复制标准库并精简
    echo "  复制标准库..."
    cp -R "$FW/lib/python$BREW_VER" "$PY_DIR/lib/"

    # 精简
    echo "  精简标准库..."
    for dir in test tkinter idlelib turtledemo ensurepip venv distutils; do
        rm -rf "$PY_DIR/lib/python$BREW_VER/$dir" 2>/dev/null || true
    done
    rm -f "$PY_DIR/lib/python$BREW_VER/site-packages" 2>/dev/null || true
    find "$PY_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PY_DIR" -name '*.pyc' -delete 2>/dev/null || true

    PYTHON3_PATH="$PY_DIR/bin/python3"
    PY_SIZE=$(du -sh "$PY_DIR" | cut -f1)
    echo "  ✅ Python3 $BREW_VER 已打包 (${PY_SIZE})"
else
    echo "  ⚠️  未找到 brew Python，将使用系统 Python3"
    # 创建符号链接到系统 python3
    mkdir -p "${RES_DIR}/python/bin"
    SYSTEM_PY3=$(which python3 2>/dev/null || echo "/usr/bin/python3")
    ln -sf "$SYSTEM_PY3" "${RES_DIR}/python/bin/python3"
    PYTHON3_PATH="$SYSTEM_PY3"
fi

# ── 4. 复制项目文件 ──
echo ""
echo "  📄 复制项目文件到 Resources/..."
rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='XQAgent.app' \
    --exclude='mac/' \
    --exclude='xqagent_icon.png' \
    --exclude='dist/' \
    --exclude='python/' \
    "${PROJECT_DIR}/" "${RES_DIR}/"
chmod -R u+w "${RES_DIR}"

# 恢复运行时数据
if [ -d "$BACKUP_DIR" ]; then
    echo "  🔄 恢复运行时数据..."
    for item in sessions memory/L2_facts.txt memory/L3_records memory/L4_sessions bridges/config.json uploads config.json skills/installed.json; do
        src="$BACKUP_DIR/$item"
        dst="${RES_DIR}/$item"
        if [ -e "$src" ]; then
            mkdir -p "$(dirname "$dst")"
            cp -R "$src" "$dst" 2>/dev/null || true
        fi
    done
    rm -rf "$BACKUP_DIR"
    echo "  ✅ 运行时数据已恢复"
fi

cp "/tmp/${BIN_NAME}Bin" "${OUTPUT_DIR}/Contents/MacOS/${APP_NAME}"
chmod +x "${OUTPUT_DIR}/Contents/MacOS/${APP_NAME}"

# ── 5. 生成图标 ──
ICON_SRC="${PROJECT_DIR}/XQAgent.jpg"
if [ ! -f "$ICON_SRC" ]; then
    echo "  ⚠️  未找到 XQAgent.jpg，将使用无图标模式"
else
    echo "  🖼️  生成 .icns 图标..."
    python3 -c "
from PIL import Image; img=Image.open('${ICON_SRC}'); sz=min(img.size);
img=img.crop(((img.width-sz)//2,(img.height-sz)//2,(img.width+sz)//2,(img.height+sz)//2)).resize((1024,1024),Image.LANCZOS);
img.save('${RES_DIR}/xqagent_icon.png','PNG')"
    ICONSET="/tmp/xqagent_icon.iconset"
    rm -rf "$ICONSET" && mkdir -p "$ICONSET"
    for s in 16 32 64 128 256 512; do
        sips -z $s $s "${RES_DIR}/xqagent_icon.png" --out "$ICONSET/icon_${s}x${s}.png" &>/dev/null
        sips -z $((s*2)) $((s*2)) "${RES_DIR}/xqagent_icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" &>/dev/null
    done
    cp "${RES_DIR}/xqagent_icon.png" "$ICONSET/icon_512x512@2x.png"
    iconutil -c icns "$ICONSET" -o "${RES_DIR}/XQAgent.icns" 2>/dev/null
    rm -f "${RES_DIR}/xqagent_icon.png"
    echo "  ✅ 图标已生成 ($(du -h "${RES_DIR}/XQAgent.icns" | cut -f1))"
fi

# ── 6. Info.plist ──
cat > "${OUTPUT_DIR}/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>XQAgent</string>
    <key>CFBundleIdentifier</key>
    <string>com.xqagent.mac</string>
    <key>CFBundleName</key>
    <string>XQAgent</string>
    <key>CFBundleDisplayName</key>
    <string>XQAgent</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>XQAgent</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
</dict>
</plist>
PLIST

# ── 7. 签名（带 entitlements，允许 DYLD 环境和加载未签名库） ──
echo "  🔏 签名（带 entitlements）..."
ENTITLEMENTS="${PROJECT_DIR}/mac/XQAgent.entitlements"
codesign --force --deep --sign - --entitlements "${ENTITLEMENTS}" "${OUTPUT_DIR}" 2>&1 | grep -v "replacing existing signature" || true
xattr -cr "${OUTPUT_DIR}" 2>&1 || true

# ── 8. 完成 ──
echo ""
echo "  ✅ 自包含应用打包完成！"
echo "  ─────────────────────────────────────"
echo "  位置: ${OUTPUT_DIR}"
echo "  大小: $(du -sh "${OUTPUT_DIR}" | cut -f1)"
echo "  结构:"
echo "    .app/Contents/MacOS/XQAgent       ← 原生壳"
echo "    .app/Contents/Resources/python/   ← Python3 解释器 + 标准库"
echo "    .app/Contents/Resources/app.py    ← Python 后端"
echo "    .app/Contents/Resources/web/      ← 前端页面"
echo "    .app/Contents/Resources/sessions/  ← 运行时生成（会话数据）"
echo "    .app/Contents/Resources/bridges/   ← 桥接器（含运行时配置）"
echo "    .app/Contents/Resources/skills/    ← 技能"
echo ""
echo "  💡 开箱即用：无需额外安装 Python3"
echo "  💡 双击启动 → 自动拉起内置 Python 后端 → WebView 渲染"
echo ""

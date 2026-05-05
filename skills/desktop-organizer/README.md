# DesktopOrganizer Skill

一个用于自动整理桌面文件的 OpenClaw 技能（Skill）。它会扫描桌面根目录下的所有文件，按照文件类型分类后移动到对应子目录，并在执行前提供完整的移动计划预览，确保用户知晓所有变更。

## 功能特性

- **智能分类**：支持 10 大类、100+ 种扩展名自动归类（图片、文档、视频、音频、压缩包、代码、程序、字体、网页、其他）
- **安全第一**：强制预览（dry-run）模式，用户确认后才执行实际移动
- **冲突保护**：目标已存在同名文件时，自动添加编号后缀（`_1`, `_2`…），绝不覆盖
- **系统文件豁免**：自动跳过 `desktop.ini`、`.DS_Store`、`Thumbs.db` 等系统/隐藏文件
- **操作日志**：生成 `organizer-result.json` 记录所有已执行操作，方便审查
- **可自定义**：在桌面放置 `organizer-config.json` 即可自定义分类规则和目标目录
- **跨平台**：支持 Windows、macOS、Linux

## 安装方法

1. 进入 OpenClaw workspace 目录：
   ```
   cd ~/.openclaw/workspace
   ```

2. 确保 skills 目录存在：
   ```
   mkdir -p skills
   ```

3. 克隆本技能到 skills 目录：
   ```
   git clone https://github.com/your-org/desktop-organizer-skill.git skills/desktop-organizer
   ```

4. 重启 OpenClaw：
   ```
   openclaw gateway restart
   ```

## 使用方法

### 快速整理
直接对话：
> "帮我整理一下桌面文件"

技能会自动完成扫描 → 展示计划 → 请求确认 → 执行整理的完整流程。

### 仅预览，不执行
> "扫描一下我的桌面，看看有哪些文件需要整理"

### 手动运行脚本

```bash
# 第一步：扫描桌面，生成 desktop-manifest.json
python skills/desktop-organizer/scripts/scan_desktop.py

# 第二步：预览整理计划（不执行移动）
python skills/desktop-organizer/scripts/organize_desktop.py --dry-run

# 第三步：确认后执行整理
python skills/desktop-organizer/scripts/organize_desktop.py --execute
```

## 自定义分类

在桌面创建 `organizer-config.json`：

```json
{
  "categories": {
    "工作文档": ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf"],
    "个人图片": ["jpg", "jpeg", "png", "gif", "heic", "raw"],
    "开发文件": ["py", "js", "ts", "go", "rs", "java", "json", "yaml"],
    "安装包":   ["exe", "msi", "dmg", "pkg", "deb", "rpm"]
  },
  "skip_extensions": ["lnk", "url", "webloc"],
  "target_dir": null
}
```

- `categories`：键为目录名，值为属于该目录的扩展名列表（小写，不含点）
- `skip_extensions`：需要跳过（不整理）的扩展名列表
- `target_dir`：整理目标根目录，`null` 表示在桌面本地创建子目录

## 输出文件说明

| 文件 | 说明 |
|------|------|
| `desktop-manifest.json` | 桌面扫描结果，含每个文件的分类信息 |
| `organizer-plan.json` | dry-run 输出的移动计划，包含每条移动操作的来源和目标 |
| `organizer-result.json` | 执行后的操作结果记录，含成功/跳过/冲突统计 |

## 安全说明

- 本技能**只移动文件，不删除任何内容**
- 技能不会递归处理桌面中已有的子目录
- 执行前必须通过 `--dry-run` 预览，不支持跳过确认直接执行
- 所有操作均记录日志，可随时审查

## 参考资料

- `references/categories.md` — 完整扩展名分类映射表
- `references/report-format.md` — 报告格式说明

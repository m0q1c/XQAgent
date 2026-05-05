---
name: DesktopOrganizer
description: "Scan the user's desktop and move files into categorized subdirectories (Images, Documents, Videos, Audio, Archives, Code, Executables, Fonts, Web, Others). Supports dry-run preview and custom category mapping."
name_zh: "桌面整理"
description_zh: "扫描桌面并将文件自动分类到子目录（图片、文档、视频等）。"
name_ja: "デスクトップ整理"
description_ja: "デスクトップをスキャンしてファイルをサブディレクトリ（画像・文書・動画等）に自動分類する。"
---

# DesktopOrganizer — 桌面文件分目录整理

## 目标（Goal）
扫描用户的桌面目录，按照文件类型将文件移动到对应的分类子目录中，并生成整理报告。

## 安全规则（Non-negotiable safety rules）
1. **必须先执行预览（dry-run），将移动计划展示给用户确认后再实际操作。**
2. 只整理桌面根目录下的文件，不递归处理已有子目录内的文件。
3. 不删除任何文件；只做移动（rename/move）操作。
4. 若目标路径已存在同名文件，在文件名后附加数字后缀（`_1`, `_2` …），绝不覆盖。
5. 不移动隐藏文件（以 `.` 开头）和系统文件（desktop.ini、.DS_Store、Thumbs.db）。
6. 操作前将计划写入 `organizer-plan.json`，操作后将结果写入 `organizer-result.json`，供用户审查。
7. 只在用户明确确认后才执行实际移动（`--execute` 模式）。

## 工作流程（Workflow）

### 步骤 1 — 扫描桌面
```
python scripts/scan_desktop.py
```
输出 `desktop-manifest.json`，包含：
- 桌面路径
- 每个文件的名称、扩展名、推断分类、大小、修改时间
- 按分类统计汇总

### 步骤 2 — 生成整理计划（dry-run）
```
python scripts/organize_desktop.py --dry-run
```
读取 `desktop-manifest.json`，输出 `organizer-plan.json`，列出每次移动操作（来源 → 目标），**不实际移动任何文件**。  
将计划以人类可读的表格形式展示给用户，并请求确认。

### 步骤 3 — 展示计划给用户
以如下格式输出整理计划表：

```
待整理文件汇总（共 N 个）：

| 分类       | 数量 |
|-----------|------|
| 图片       |  12  |
| 文档       |   8  |
| 视频       |   3  |
| ...        |  ... |

具体移动计划：
  report.pdf          → 文档/report.pdf
  photo_001.jpg       → 图片/photo_001.jpg
  setup_app.exe       → 程序/setup_app.exe
  ...
```

询问用户：**"以上是整理计划，是否执行？(yes/no)"**

### 步骤 4 — 执行整理（仅在用户确认后）
```
python scripts/organize_desktop.py --execute
```
按计划逐项移动文件，遇到冲突自动重命名，输出 `organizer-result.json`。

### 步骤 5 — 输出整理报告
报告格式（参考 `references/report-format.md`）：

```
==============================
桌面整理完成报告
==============================
时间: 2024-01-01T12:00:00Z
桌面路径: C:\Users\User\Desktop
已整理: N 个文件
跳过: M 个文件

分类结果：
  图片 (12)       → Desktop\图片\
  文档 (8)        → Desktop\文档\
  ...

冲突重命名：
  data.zip → 压缩包/data_1.zip  （原文件已存在）

跳过文件（系统/隐藏）：
  desktop.ini, .DS_Store
==============================
```

## 分类规则（Category rules）
详见 `references/categories.md`。默认分类映射：

| 分类目录    | 说明          |
|------------|--------------|
| 图片        | 图像文件      |
| 文档        | 办公/PDF文档  |
| 视频        | 视频文件      |
| 音频        | 音频文件      |
| 压缩包      | 压缩/归档文件 |
| 代码        | 源码/配置文件 |
| 程序        | 可执行/安装包 |
| 字体        | 字体文件      |
| 网页        | HTML/CSS文件  |
| 其他        | 无法分类      |

## 自定义分类（Custom categories）
用户可在桌面创建 `organizer-config.json` 覆盖默认分类：
```json
{
  "categories": {
    "工作文档": ["doc", "docx", "xls", "xlsx", "ppt", "pptx"],
    "个人图片": ["jpg", "jpeg", "png", "heic"],
    "安装包":   ["exe", "msi", "pkg", "dmg"]
  },
  "skip_extensions": ["lnk", "url"],
  "target_dir": null
}
```
若存在该配置文件，`organize_desktop.py` 会自动使用它覆盖默认映射。`target_dir` 为空时，分类目录创建在桌面本身；设置路径后移至指定目录。

## 参考文件（References）
- `references/categories.md` — 完整扩展名-分类映射表
- `references/report-format.md` — 报告输出格式说明

# 分类规则参考表（Categories Reference）

本文档列出 DesktopOrganizer 技能默认使用的扩展名 → 分类目录映射表。  
用户可通过桌面的 `organizer-config.json` 覆盖或追加任意映射。

---

## 图片（Images）

| 扩展名 | 说明 |
|--------|------|
| jpg / jpeg | JPEG 位图 |
| png | PNG 位图 |
| gif | GIF 动图 |
| bmp | Windows 位图 |
| webp | WebP 图片 |
| svg | SVG 矢量图 |
| ico | 图标文件 |
| tiff / tif | TIFF 位图 |
| raw | RAW 相机原片 |
| heic / heif | Apple HEIF 格式 |
| avif | AV1 图片格式 |
| psd | Photoshop 源文件 |
| ai | Illustrator 源文件 |
| eps | PostScript 矢量图 |
| indd | InDesign 文档 |

---

## 文档（Documents）

| 扩展名 | 说明 |
|--------|------|
| pdf | PDF 文档 |
| doc / docx | Word 文档 |
| odt | OpenDocument 文字 |
| rtf | 富文本格式 |
| txt | 纯文本 |
| md | Markdown |
| rst | reStructuredText |
| xls / xlsx | Excel 表格 |
| ods | OpenDocument 表格 |
| csv | 逗号分隔值 |
| ppt / pptx | PowerPoint 演示 |
| odp | OpenDocument 演示 |
| epub | 电子书 |
| mobi | Kindle 电子书 |
| pages / numbers / key | Apple iWork 套件 |

---

## 视频（Videos）

| 扩展名 | 说明 |
|--------|------|
| mp4 | MPEG-4 视频 |
| mkv | Matroska 视频 |
| avi | AVI 视频 |
| mov | QuickTime 视频 |
| wmv | Windows Media 视频 |
| flv | Flash 视频 |
| webm | WebM 视频 |
| m4v | iTunes 视频 |
| mpeg / mpg | MPEG 视频 |
| 3gp | 3GPP 移动视频 |
| ts / mts / m2ts | MPEG-2 传输流 |
| vob | DVD 视频 |
| rmvb | RealMedia 视频 |

---

## 音频（Audio）

| 扩展名 | 说明 |
|--------|------|
| mp3 | MP3 音频 |
| wav | WAV 无压缩音频 |
| flac | FLAC 无损音频 |
| aac | AAC 音频 |
| ogg | Ogg Vorbis 音频 |
| wma | Windows Media 音频 |
| m4a | iTunes 音频 |
| opus | Opus 音频 |
| ape | APE 无损音频 |
| aiff / aif | AIFF 音频（Apple） |
| mid / midi | MIDI 序列 |

---

## 压缩包（Archives）

| 扩展名 | 说明 |
|--------|------|
| zip | ZIP 压缩包 |
| rar | RAR 压缩包 |
| 7z | 7-Zip 压缩包 |
| tar | TAR 归档 |
| gz | Gzip 压缩 |
| bz2 | Bzip2 压缩 |
| xz | XZ 压缩 |
| zst | Zstandard 压缩 |
| tgz | TAR+Gzip |
| tbz2 | TAR+Bzip2 |
| iso | 光盘镜像 |
| dmg | macOS 磁盘镜像 |
| pkg | macOS 安装包归档 |

---

## 代码（Code）

### 编程语言
| 扩展名 | 语言 |
|--------|------|
| py | Python |
| js / jsx | JavaScript |
| ts / tsx | TypeScript |
| java | Java |
| kt | Kotlin |
| c / h | C |
| cpp / hpp | C++ |
| cs | C# |
| go | Go |
| rs | Rust |
| rb | Ruby |
| php | PHP |
| swift | Swift |
| r | R |
| m | Objective-C / MATLAB |

### 脚本
| 扩展名 | 说明 |
|--------|------|
| sh / bash / zsh | Shell 脚本 |
| ps1 | PowerShell 脚本 |
| bat / cmd | Windows 批处理 |

### 配置与数据
| 扩展名 | 说明 |
|--------|------|
| json | JSON |
| xml | XML |
| yaml / yml | YAML |
| toml | TOML |
| ini / cfg / conf | INI 配置 |
| env | 环境变量文件 |
| sql | SQL 脚本 |
| tf / hcl | Terraform / HCL |
| dockerfile | Dockerfile |

---

## 程序（Executables）

| 扩展名 | 说明 |
|--------|------|
| exe | Windows 可执行文件 |
| msi | Windows 安装包 |
| app | macOS 应用程序包 |
| deb | Debian/Ubuntu 软件包 |
| rpm | Red Hat/CentOS 软件包 |
| apk | Android 应用包 |
| xpi | Firefox 扩展 |

---

## 字体（Fonts）

| 扩展名 | 说明 |
|--------|------|
| ttf | TrueType 字体 |
| otf | OpenType 字体 |
| woff | Web 字体 |
| woff2 | Web 字体（压缩版） |
| eot | IE 嵌入式字体 |
| fon | Windows 点阵字体 |

---

## 网页（Web）

| 扩展名 | 说明 |
|--------|------|
| html / htm | HTML 页面 |
| css | CSS 样式表 |
| mhtml | MHTML 网页存档 |
| webloc | macOS 网页快捷方式 |
| url | Windows 网络快捷方式 |

---

## 其他（Others）

所有未匹配任何以上分类的文件将被移动到 `其他/` 目录。

---

## 始终跳过的文件

以下文件无论配置如何，都不会被移动：

| 文件名 | 说明 |
|--------|------|
| `desktop.ini` | Windows 桌面配置文件 |
| `.DS_Store` | macOS 目录元数据 |
| `Thumbs.db` | Windows 缩略图缓存 |
| `ehthumbs.db` | Windows 扩展缩略图缓存 |
| `.localized` | macOS 本地化标记文件 |
| `organizer-config.json` | 技能配置文件 |
| `desktop-manifest.json` | 技能生成的扫描结果 |
| `organizer-plan.json` | 技能生成的移动计划 |
| `organizer-result.json` | 技能生成的执行日志 |
| `.`（任意隐藏文件） | 以点开头的隐藏文件 |

---

## 自定义分类示例

```json
{
  "categories": {
    "工作文档": ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf"],
    "个人图片": ["jpg", "jpeg", "png", "gif", "heic", "raw"],
    "开发文件": ["py", "js", "ts", "go", "rs", "java", "json", "yaml", "tf"],
    "安装包":   ["exe", "msi", "dmg", "pkg", "deb", "rpm"],
    "设计文件": ["psd", "ai", "sketch", "fig", "xd"]
  },
  "skip_extensions": ["lnk", "url", "webloc"],
  "target_dir": null
}
```

> **说明**：在 `organizer-config.json` 中定义的分类会完全覆盖默认映射中对应的扩展名；未在自定义配置中出现的扩展名仍使用默认规则。`skip_extensions` 中的扩展名将被跳过（不移动）。

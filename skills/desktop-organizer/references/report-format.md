# 报告格式说明（Report Format）

## 整理计划报告（dry-run 输出）

```
============================================================
桌面整理计划（预览，未实际移动）
============================================================
桌面路径: C:\Users\User\Desktop
待整理文件: 30 个

分类           数量
--------------------
图片             12 个
文档              8 个
视频              3 个
压缩包            4 个
代码              2 个
其他              1 个

文件名                              目标路径
--------------------------------------------------------------------------------
  photo_001.jpg                   → 图片/photo_001.jpg
  report_2024.pdf                 → 文档/report_2024.pdf
  setup.exe                       → 程序/setup.exe
  data.zip                        → 压缩包/data.zip
  data_old.zip                    → 压缩包/data_old_1.zip  ⚠ 冲突重命名
  ...

⚠  带「冲突重命名」标记的文件因目标已存在同名文件，将自动改名后移入。

计划已保存到 D:\...\organizer-plan.json

若确认无误，请运行：
  python organize_desktop.py --execute
============================================================
```

## 执行完成报告（execute 输出）

```
============================================================
桌面整理完成报告
============================================================
时间:       2024-01-01T12:00:00Z
桌面路径:   C:\Users\User\Desktop
已移动:     29 个文件
跳过（源文件不存在）: 1 个
冲突重命名: 1 个

详细日志已保存到 D:\...\organizer-result.json
============================================================
```

## organizer-result.json 结构

```json
{
  "executed_at": "2024-01-01T12:00:00Z",
  "desktop_path": "C:\\Users\\User\\Desktop",
  "summary": {
    "total_planned": 30,
    "moved": 29,
    "skipped_missing": 1,
    "conflicts_renamed": 1,
    "errors": 0
  },
  "operations": [
    {
      "src": "C:\\Users\\User\\Desktop\\photo_001.jpg",
      "dest": "C:\\Users\\User\\Desktop\\图片\\photo_001.jpg",
      "actual_dest": "C:\\Users\\User\\Desktop\\图片\\photo_001.jpg",
      "category": "图片",
      "conflict": false,
      "original_name": "photo_001.jpg",
      "dest_name": "photo_001.jpg",
      "status": "moved"
    },
    ...
  ]
}
```

## 状态码说明

| status | 含义 |
|--------|------|
| `moved` | 文件已成功移动 |
| `skipped` | 文件被跳过（源文件不存在） |
| `error` | 移动时发生错误（见 `reason` 字段） |

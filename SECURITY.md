# XQAgent 安全策略

## 网络安全

- HTTP 服务器绑定 `127.0.0.1`，仅本机可访问
- CORS 允许所有来源（仅限本地开发）
- 无认证令牌（仅适用于本地环境）

## 输入安全

### Shell 命令黑名单

`run_shell` 工具内置 16 条危险模式检测：
- 文件系统破坏：`rm -rf /`、`mkfs`、`dd if=`、`> /dev/sd`
- 权限提升：`chmod 777 /`、`chown`
- 远程执行：`wget`、`curl`、`| bash`、`| sh`
- 解释器注入：`python3 -c`、`perl -e`、`eval`、`exec`
- 编码混淆：`base64 -d`
- Fork 炸弹：`:(){ :|:& };:`

命令长度限制为 1000 字符。

### 文件路径保护

`_safe_path()` 函数拦截对以下系统目录的访问：
- `/System`
- `/Library/Apple`
- `/dev/sd`、`/dev/disk`
- `/boot`
- `/etc`
- `/var/db`
- `/private/etc`

### 会话 ID 保护

会话 ID 仅允许 `[a-zA-Z0-9_-]` 字符，防止路径遍历攻击。

## 报告漏洞

请通过 GitHub Issues 提交安全相关问题。
